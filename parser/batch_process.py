#!/usr/bin/env python3
"""Batch-process Valorant replays: .vrf -> vrfkit export -> stats shard (+ raw export zip).

usage: batch_process.py --replays DIR --outbox DIR --vrfkit PATH --lookup name_lookup.json
                        [--work DIR] [--limit N] [--force] [--no-zip]

For every *.vrf in --replays (not in subfolders named 'done'):
  1. vrfkit export <file> --out <work>/<id>/export --checkpoints
  2. skill/extract_casts.py          -> <work>/<id>/out/casts_raw.parquet
  3. effects table: build_table_swiftplay.py for Swiftplay, skill/build_table.py otherwise
  4. valosaber.py                    -> <outbox>/<id>/shard/   (index.json + parquet, checksummed)
  5. zips the raw export             -> <outbox>/<id>/export.zip   (skipped with --no-zip)
Each match gets <outbox>/<id>/status.json recording every step, its error text if it failed, the
build, mode and sizes. A match whose status is 'ok' is skipped on re-run; failed ones are retried.
A failure in one replay never stops the batch. <outbox>/batch_report.csv summarizes all matches.
Nothing is guessed: a failed step leaves no partial shard behind.
"""
import argparse, csv, hashlib, json, shutil, subprocess, sys, time, zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from shard_checks import run_checks, passed


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def run(cmd, cwd=None, log=None):
    t = time.time()
    p = subprocess.run([str(c) for c in cmd], cwd=cwd, capture_output=True, text=True)
    out = (p.stdout or "") + (p.stderr or "")
    if log is not None:
        log.append({"cmd": " ".join(str(c) for c in cmd)[:300], "rc": p.returncode, "secs": round(time.time() - t, 1),
                    "tail": out[-1500:]})
    return p.returncode, out


def process(vrf: Path, a, work_root: Path):
    mid = vrf.stem
    od = Path(a.outbox) / mid
    st_path = od / "status.json"
    if st_path.exists() and not a.force:
        try:
            if json.load(open(st_path)).get("overall") == "ok":
                return "skipped", json.load(open(st_path))
        except Exception:
            pass
    if od.exists():
        shutil.rmtree(od)
    od.mkdir(parents=True)
    w = work_root / mid
    if w.exists():
        shutil.rmtree(w)
    (w / "out").mkdir(parents=True)
    log, st = [], {"match_id": mid, "source_file": vrf.name, "source_bytes": vrf.stat().st_size,
                   "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "steps": {}, "overall": "failed",
                   "run_id": f"{mid[:8]}-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}",
                   "source_sha256": sha256_file(vrf), "vrfkit_sha256": sha256_file(a.vrfkit),
                   "repo_commit": (run(["git", "rev-parse", "--short", "HEAD"], cwd=HERE, log=None)[1] or "").strip()[:12]}

    def step(name, cmd, cwd=None):
        rc, out = run(cmd, cwd, log)
        st["steps"][name] = {"ok": rc == 0, **({} if rc == 0 else {"error": out[-800:]})}
        return rc == 0

    try:
        exp = w / "export"
        if not step("export", [a.vrfkit, "export", vrf, "--out", exp, "--checkpoints"]):
            return "failed", st
        for need in ("fields.parquet", "events.parquet", "actors.parquet", "manifest.json"):
            if not (exp / need).exists():
                st["steps"]["export"] = {"ok": False, "error": f"export is missing {need}"}
                return "failed", st
        man = json.load(open(exp / "manifest.json"))
        st["build"] = man.get("replay_build"); st["duration_s"] = round(man.get("duration_ms", 0) / 1000, 1)
        import re as _re
        m_ = _re.search(r"release-\d+\.\d+", st["build"] or "")
        reg = json.load(open(a.registry))["binaries"]
        sup = reg.get(st["vrfkit_sha256"])
        st["release"] = m_.group(0) if m_ else "UNKNOWN"
        if sup is None:
            st["steps"]["build_support"] = {"ok": False, "error": f"this vrfkit binary ({st['vrfkit_sha256'][:12]}) is not in {a.registry}; "
                "run parser/register_vrfkit.py on it and add it before processing"}
            st["overall"] = "unsupported_build"
            return "unsupported_build", st
        if st["release"] not in sup["known_in_binary"]:
            st["steps"]["build_support"] = {"ok": False, "error": f"replay build {st['build']} is not one this vrfkit knows "
                f"(newest known {sup['known_in_binary'][-1]}); output for it cannot be trusted, so nothing was built"}
            st["overall"] = "unsupported_build"
            return "unsupported_build", st
        if st["release"] in sup.get("thin_support", []):
            st["build_note"] = "build has thin vrfkit support (see data/vrfkit_supported_builds.json)"
        if st["release"] != "release-13.08":
            st["build_note"] = (st.get("build_note", "") + " shard logic validated only on release-13.08; check every number on this build").strip()
        import pandas as pd
        act = pd.read_parquet(exp / "actors.parquet", columns=["class_path"])
        st["mode"] = "Swiftplay" if act.class_path.astype(str).str.contains("Swiftplay").any() else "Standard"
        st["export_bytes"] = sum(f.stat().st_size for f in exp.iterdir() if f.is_file())

        if not step("casts", [sys.executable, HERE / "skill" / "extract_casts.py", "--export", exp,
                              "--out", w / "out" / "casts_raw.parquet"]):
            return "failed", st
        table = HERE / ("build_table_swiftplay.py" if st["mode"] == "Swiftplay" else "skill/build_table.py")
        if not step("effects", [sys.executable, table, "--export", exp, "--casts", w / "out" / "casts_raw.parquet",
                                "--out", w / "out" / "ability_effects.csv"]):
            st["note"] = "effects table failed; shard not built"
        else:
            shard = od / "shard"
            ok = step("shard", [sys.executable, HERE / "valosaber.py", "export", "out/ability_effects.csv", a.lookup,
                                "metrics.json", shard, mid, vrf.stat().st_size], cwd=w)
            if not ok and shard.exists():
                shutil.rmtree(shard)
            if ok:
                checks = run_checks(shard, exp)
                st["checks"] = checks
                if not passed(checks):
                    shutil.move(str(shard), str(od / "shard_FAILED_CHECK"))
                    st["steps"]["shard"] = {"ok": False, "error": "value checks failed: " +
                                            "; ".join(f"{c['check']} ({c['detail']})" for c in checks if not c["ok"] and c["level"] == "invariant")[:700]}
                    ok = False
            if ok:
                idx = json.load(open(shard / "index.json"))
                idx.update({"source_sha256": st["source_sha256"], "run_id": st["run_id"], "source_build": st["build"],
                            "parser": {"vrfkit_sha256": st["vrfkit_sha256"], "repo_commit": st["repo_commit"]}})
                json.dump(idx, open(shard / "index.json", "w"), indent=1)
                st["rounds"] = idx.get("rounds"); st["shard_bytes"] = sum(f.stat().st_size for f in shard.iterdir())
        # meta agent's 15 data groups: same export, same run; needs the shard for kills/damage/teams (DERIVED), else those stay UNRESOLVED
        mt_cmd = [sys.executable, HERE / "meta_tables.py", exp, od, "--source-sha256", st["source_sha256"], "--run-id", st["run_id"], "--lookup", a.lookup]
        if (od / "shard").exists():
            mt_cmd += ["--shard", od / "shard"]
        if step("analytics_tables", mt_cmd):
            tm = json.load(open(od / "tables_manifest.json"))
            st["analytics_rows"] = {k: v["rows"] for k, v in tm["tables"].items()}
        if not a.no_zip:
            zp = od / "export.zip"
            with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED, compresslevel=1) as z:
                for f in sorted(exp.iterdir()):
                    if f.is_file():
                        z.write(f, f"{mid}/{f.name}")
            st["export_zip_bytes"] = zp.stat().st_size
            st["steps"]["zip"] = {"ok": True}
        st["overall"] = ("ok" if st["steps"].get("shard", {}).get("ok") else
                         "failed_check" if (od / "shard_FAILED_CHECK").exists() else "export_only")
        if st["mode"] != "Swiftplay":
            st["warning"] = "standard-mode shard logic is untested; check the numbers before trusting them"
        return st["overall"], st
    except Exception as e:  # keep the batch alive
        import traceback
        st["exception"] = traceback.format_exc()[-800:]
        return "failed", st
    finally:
        st["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        st["log"] = log
        json.dump(st, open(st_path, "w"), indent=1)
        shutil.rmtree(w, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--replays", required=True); ap.add_argument("--outbox", required=True)
    ap.add_argument("--vrfkit", required=True); ap.add_argument("--lookup", required=True)
    ap.add_argument("--work", default="/tmp/valosaber_work"); ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--only", nargs="+", default=None, help="process only these replay names (file name or stem)")
    ap.add_argument("--registry", default=str(HERE.parent / "data" / "vrfkit_supported_builds.json"))
    ap.add_argument("--force", action="store_true"); ap.add_argument("--no-zip", action="store_true")
    a = ap.parse_args()
    for k in ("replays", "outbox", "vrfkit", "lookup", "work", "registry"):  # steps run in other folders, so paths must be absolute
        setattr(a, k, str(Path(getattr(a, k)).resolve()))
    vrfs = sorted(p for p in Path(a.replays).glob("*.vrf"))
    if not vrfs:
        sys.exit(f"no .vrf files in {a.replays}")
    if not Path(a.vrfkit).exists():
        sys.exit(f"vrfkit not found at {a.vrfkit}; run parser/colab_bootstrap.py first")
    Path(a.outbox).mkdir(parents=True, exist_ok=True)
    work = Path(a.work); work.mkdir(parents=True, exist_ok=True)
    if a.only:
        want = {Path(x).stem for x in a.only}
        vrfs = [v for v in vrfs if v.stem in want]
        missing = want - {v.stem for v in vrfs}
        if missing:
            sys.exit(f"--only names not found in {a.replays}: {sorted(missing)}")
    if a.limit:
        vrfs = vrfs[: a.limit]
    print(f"{len(vrfs)} replay(s) to consider")
    results = []
    for i, v in enumerate(vrfs, 1):
        t = time.time()
        res, st = process(v, a, work)
        print(f"[{i}/{len(vrfs)}] {v.name}: {res} ({time.time() - t:.0f}s)" +
              (f" | {st.get('mode')} {st.get('build')} rounds={st.get('rounds')}" if res != "failed" else ""))
        if res in ("failed", "unsupported_build"):
            bad = [k for k, s in st["steps"].items() if not s.get("ok")]
            print("    failed step:", bad, (st["steps"][bad[0]].get("error", "")[-300:] if bad else st.get("exception", "")))
        results.append(res)
    rows = []
    for sp in sorted(Path(a.outbox).glob("*/status.json")):
        s = json.load(open(sp))
        rows.append({k: s.get(k) for k in ("match_id", "overall", "mode", "build", "rounds", "duration_s", "source_sha256", "vrfkit_sha256", "repo_commit", "source_bytes",
                                            "export_bytes", "shard_bytes", "export_zip_bytes", "warning", "note")})
    if rows:
        with open(Path(a.outbox) / "batch_report.csv", "w", newline="") as f:
            wr = csv.DictWriter(f, fieldnames=list(rows[0])); wr.writeheader(); wr.writerows(rows)
    print({r: results.count(r) for r in sorted(set(results))})


if __name__ == "__main__":
    main()
