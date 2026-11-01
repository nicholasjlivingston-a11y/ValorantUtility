#!/usr/bin/env python3
"""Evidence-based value checks for a Valosaber shard.

usage: shard_checks.py SHARD_DIR [EXPORT_DIR]
EXPORT_DIR (the vrfkit export the shard came from) lets the checks compare against that replay's own
records: its roster size, its characterDeath events, its duration. Nothing here assumes a fixed number of
players, rounds, kills or damage; exact values for the golden sample live in golden_sample_test.py.

Each check has a level:
  invariant    must hold for any replay; a failure rejects the shard
  expectation  usually true; a failure is reported as a warning, never forced
Exit code 0 only if every invariant passes.
"""
import hashlib, json, sys
from pathlib import Path
import pandas as pd


def roster_size(export: Path):
    """Number of distinct player Subject ids recorded in the replay's own PlayerState actors."""
    try:
        f = pd.read_parquet(export / "fields.parquet", columns=["group_path", "field_name", "value_str"],
                            filters=[("field_name", "==", "Subject")])
    except Exception:
        f = pd.read_parquet(export / "fields.parquet", columns=["group_path", "field_name", "value_str"])
        f = f[f.field_name.astype(str) == "Subject"]
    f = f[f.group_path.astype(str).str.endswith("PlayerState_C")]
    return int(f.value_str.dropna().nunique())


def run_checks(shard: Path, export: Path | None = None):
    R = []
    def add(name, ok, detail, level="invariant"):
        R.append({"check": name, "ok": bool(ok), "detail": detail, "level": level})

    idx = json.load(open(shard / "index.json"))
    bad = []
    for n, m in idx["tables"].items():
        fp = shard / f"{n}.parquet"
        if not fp.exists() or hashlib.sha256(fp.read_bytes()).hexdigest() != m["sha256"]:
            bad.append(n)
    add("index hashes match files", not bad, f"mismatched or missing: {bad}" if bad else f"{len(idx['tables'])} tables")
    T = {n: pd.read_parquet(shard / f"{n}.parquet") for n in idx["tables"]}
    p, k, d, pos = T["players"], T["kills"], T["damage"], T["positions_4hz"]
    nk, nr = len(k), int(idx.get("rounds", 0))

    roster = roster_size(export) if export is not None and (export / "fields.parquet").exists() else None
    if roster is not None:
        add("players equal the replay's own roster", len(p) == roster and roster > 0, f"{len(p)} players in shard, {roster} Subject ids in the export")
    else:
        add("players present", len(p) > 0, f"{len(p)} players")
    add("every player has a team and an agent", p.team.notna().all() and p.agent.notna().all(),
        f"teams {p.team.value_counts().to_dict()}, {int(p.agent.isna().sum())} agents missing")
    add("at least one round", nr >= 1, f"{nr} rounds")
    key = k[["rnd", "t", "killer", "victim"]].drop_duplicates().shape[0] if nk else 0
    add("kill rows are distinct events", key == nk, f"{nk} rows, {key} distinct (round,time,killer,victim)")
    if nk > 1:
        add("kill times vary", k.t.nunique() > 1, f"{k.t.nunique()} distinct times, range {k.t.min()}..{k.t.max()} ms")
    add("killers and victims are known players", bool(nk == 0 or (k.killer.isin(p.uuid).all() and k.victim.isin(p.uuid).all())),
        f"{int((~k.killer.isin(p.uuid)).sum())} unknown killers, {int((~k.victim.isin(p.uuid)).sum())} unknown victims")
    dealt, recv = float(d.dealt.sum()), float(d.recv.sum())
    add("damage dealt equals damage received", abs(dealt - recv) < 0.01, f"dealt {dealt:.2f}, received {recv:.2f}")
    add("every player has position rows", pos.uuid.nunique() == len(p), f"{pos.uuid.nunique()} of {len(p)} players have positions")
    if len(pos) > 100:
        add("positions are not constant", pos.x.nunique() > 1 and pos.y.nunique() > 1, f"{pos.x.nunique()} distinct x, {pos.y.nunique()} distinct y")
    if export is not None and (export / "events.parquet").exists():
        ev = pd.read_parquet(export / "events.parquet", columns=["group"])
        nd = int((ev["group"].astype(str) == "characterDeath").sum())
        add("kills equal characterDeath events", nd == nk, f"{nk} kills, {nd} death events")
    shard_bytes = sum(f.stat().st_size for f in shard.iterdir() if f.is_file())
    add("shard under 8 MB", shard_bytes < 8 * 1024 * 1024, f"{shard_bytes:,} bytes")
    # expectations (warnings only)
    if nr > 1 and nk >= 2:
        add("kills occur in more than one round", k.rnd.nunique() > 1, f"rounds with kills: {k.rnd.nunique()} of {nr}", "expectation")
    if len(d) >= 10:
        add("damage values vary", d.dealt.nunique() > 3, f"{d.dealt.nunique()} distinct damage values", "expectation")
    if export is not None and (export / "manifest.json").exists():
        dur = json.load(open(export / "manifest.json")).get("duration_ms", 0)
        if dur:
            add("positions cover at least half the replay", pos.t.max() >= 0.5 * dur, f"last position {pos.t.max()} ms of {dur} ms", "expectation")
    return R


def passed(results):
    return all(r["ok"] for r in results if r["level"] == "invariant")


if __name__ == "__main__":
    res = run_checks(Path(sys.argv[1]), Path(sys.argv[2]) if len(sys.argv) > 2 else None)
    for r in res:
        print(("PASS " if r["ok"] else ("FAIL " if r["level"] == "invariant" else "WARN ")) + r["check"] + " | " + r["detail"])
    sys.exit(0 if passed(res) else 1)
