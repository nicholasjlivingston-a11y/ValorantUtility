#!/usr/bin/env python3
"""Assemble the Valosaber bootstrap package (a zip that mirrors the repo layout) and verify it by reopening.

usage: tools/build_bootstrap.py OUT.zip [--with-vrfkit PATH] [--source-zip OLD_BOOTSTRAP.zip] [--golden-export DIR]
 --source-zip     previous bootstrap; its meta-agent files (scripts/, schemas/, config/, ontology/, run_pipeline.py) are kept
 --golden-export  folder with the golden sample export (events.parquet and manifest.json are packed)
 --golden-full    also pack the whole export as golden_sample/export_full.zip (needed to run parser/meta_tables_test.py)
 --with-vrfkit    include a binary; refused unless its SHA-256 is in parser/vrfkit.sha256. Default: not included.
"""
import argparse, hashlib, json, re, subprocess, sys, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser()
ap.add_argument("out")
ap.add_argument("--with-vrfkit")
ap.add_argument("--source-zip")
ap.add_argument("--golden-export")
ap.add_argument("--golden-full", action="store_true")
a = ap.parse_args()
VERSION, BUILT = "3.1.0", "2026-11-01"
sha = lambda b: hashlib.sha256(b).hexdigest()
files = {}  # path in zip -> bytes


def add(zpath, data):
    assert zpath not in files, zpath
    files[zpath] = data if isinstance(data, bytes) else data.encode("utf-8")


def add_tree(src, dst, pat="*", skip=("__pycache__",)):
    for p in sorted(Path(src).rglob(pat)):
        if p.is_file() and not any(s in p.parts for s in skip) and p.suffix != ".pyc":
            add(f"{dst}/{p.relative_to(src).as_posix()}", p.read_bytes())


# 1. our code and data
add_tree(ROOT / "parser", "parser", skip=("__pycache__",))
files = {k: v for k, v in files.items() if not k.endswith(".zip")}  # never nest old packages
add_tree(ROOT / "tools", "tools")
for f in ("agent_classes.json", "name_lookup_build13_08.json", "vrfkit_supported_builds.json", "data_pipeline.md"):
    add(f"data/{f}", (ROOT / "data" / f).read_bytes())

# 2. knowledge: the vault notes an agent needs (Obsidian links kept as they are)
V = ROOT / "vault"
for sub in ("Reference", "Decisions", "Metrics"):
    add_tree(V / sub, f"knowledge/{sub}")
for n in ("Shard Schema", "Run Order", "Data Pipeline", "Limits and Access", "Raw Replay Parsing Prompt",
          "Master Parser Prompt", "Bootstrap Package", "Unified Pipeline Brief", "First Real Run Checklist"):
    add(f"knowledge/Pipeline/{n}.md", (V / "Pipeline" / f"{n}.md").read_bytes())
for n in ("00 START HERE", "02 Current State", "04 Open Questions"):
    p = next(V.glob(f"{n}*.md"), None)
    if p:
        add(f"knowledge/{p.name}", p.read_bytes())
add("docs/EXTRACTION_REQUIREMENTS.md", re.sub(r"\A---.*?---\n> [^\n]*\n\n", "", (V / "Reference/Extraction Requirements.md").read_text(encoding="utf-8"), flags=re.S))

# 3. the agent task = the fenced prompt inside the master prompt note
mp = (V / "Pipeline/Master Parser Prompt.md").read_text(encoding="utf-8")
m = re.search(r"## The prompt\n```\n(.*?)\n```\n", mp, flags=re.S)
assert m and "ADDENDUM" in m.group(1), "master prompt block not found"
add("AGENT_TASK.md", m.group(1) + "\n")

# 4. meta agent's files, kept as delivered
if a.source_zip:
    with zipfile.ZipFile(a.source_zip) as z:
        for n in z.namelist():
            if n.endswith("/") or n == "bin/vrfkit":
                continue
            if n.startswith(("scripts/", "schemas/", "config/", "ontology/")) or n == "run_pipeline.py":
                add(n, z.read(n))

# 5. golden sample: shard + the two export files the golden test reads + expectations
for p in sorted((ROOT / "inbox/shard-4c1d14ba").glob("*")):
    add(f"golden_sample/shard/{p.name}", p.read_bytes())
if a.golden_export:
    for n in ("events.parquet", "manifest.json"):
        add(f"golden_sample/export/{n}", (Path(a.golden_export) / n).read_bytes())
if a.golden_full:
    import io
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zz:
        for p in sorted(Path(a.golden_export).glob("*")):
            if p.is_file():
                zz.write(p, f"export/{p.name}")
    add("golden_sample/export_full.zip", buf.getvalue())
add("golden_sample/expected.json", json.dumps({
    "match_id": "4c1d14ba-6e21-496f-9101-1b85fa513fd8", "build": "release-13.08", "mode": "Swiftplay", "rounds": 5,
    "kills": 34, "players": 10, "teams": [5, 5], "damage_dealt_equals_received": 6049.78,
    "max_kill_to_death_event_gap_ms": 9, "team_a_won_all_rounds": True, "side_swap_after_round_index": 3,
    "note": "Values for this one replay only. Never apply them to another replay. The package holds only events.parquet and "
            "manifest.json of the export; that is enough for golden_sample_test.py."}, indent=2))

# 6. vrfkit stays out unless explicitly asked and registered
reg = {l.split()[0].lower() for l in (ROOT / "parser/vrfkit.sha256").read_text().splitlines() if l.strip()}
if a.with_vrfkit:
    b = Path(a.with_vrfkit).read_bytes()
    assert sha(b) in reg, f"REFUSING to pack unregistered binary {sha(b)}"
    add("bin/vrfkit", b)
else:
    add("bin/README.txt", "The parser binary is not part of this package on purpose.\n"
        "Keep one registered vrfkit in Google Drive (MyDrive/valosaber/bin/) and run: python3 parser/colab_bootstrap.py\n"
        "It checks the SHA-256 against parser/vrfkit.sha256 and installs bin/vrfkit. The binary pinned today (afe615e8...c04a)\n"
        "knows builds up to release-13.08 only. Replays from patch 13.09 (Hush) need a newer vrfkit: run\n"
        "python3 parser/register_vrfkit.py <file> --label \"...\" to get its registry entry. Nothing here ever runs an unregistered binary.\n")

# 7. README
commit = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
add("README.md", f"""# Valosaber pipeline bootstrap v{VERSION}

Built {BUILT} from repo commit {commit}. Serves two consumers from one raw `.vrf` replay:
the **meta-analysis agent** (15 native-resolution data groups, `analytics_tables/`) and the **statistics analyst** (schema-2 shard, `stats_shard/`).

## Start here (in this order)
1. `AGENT_TASK.md` is the task you are given. Read all of it, including the ADDENDUM at the end.
2. `docs/EXTRACTION_REQUIREMENTS.md` is the meta agent's contract for `analytics_tables/` (verbatim).
3. `knowledge/` holds what the project has learned: `Reference/Replay Data Guide.md` (traps in the data), agents, classes, maps, abilities,
   ADRs (`Decisions/`), shard schema, metrics. Names are confirmed or they stay as codenames.
4. `parser/meta_tables.py` is reference code that already builds the 15 data groups from one export (read it before writing your own) and `parser/meta_tables_test.py` tests it; unzip `golden_sample/export_full.zip` and run `python3 parser/meta_tables_test.py <unzipped>/export golden_sample/shard`. Its gap list says what is still unbuilt. `knowledge/Pipeline/First Real Run Checklist.md` says what to report after the first real replay.
5. `golden_sample/` is the one replay whose correct answer is known. Run `python3 parser/golden_sample_test.py golden_sample/shard golden_sample/export`
   before trusting any code change. A pass means EXPORT_PIPELINE_VALIDATED (export to shard logic only), not that a raw replay was parsed.

## Layout
| Path | Contents |
|---|---|
| `parser/` | `colab_bootstrap.py` (installs a registered vrfkit), `batch_process.py` (folder of replays to shards), `valosaber.py`, `shard_checks.py`, `golden_sample_test.py`, `ingest.py`, `baselines.py`, `register_vrfkit.py`, `meta_tables.py` + test, `skill/` (cast and table builders, `codenames.json`), notebook |
| `data/` | name lookup (build 13.08), `agent_classes.json`, `vrfkit_supported_builds.json` (registry), pipeline guide |
| `scripts/ schemas/ config/ ontology/ run_pipeline.py` | the meta agent's earlier files, unchanged. `run_pipeline.py` is the old exporter (fixed folders); use `parser/batch_process.py` instead. `scripts/spatial_layer.py` expects CSV tables this pipeline does not yet produce |
| `golden_sample/` | shard, events and manifest of the sample export, the full export zipped, expected values |
| `bin/` | empty on purpose (see `bin/README.txt`) |
| `PACKAGE_MANIFEST.json` | SHA-256 of every file here |

## Run
```
python3 parser/colab_bootstrap.py          # stops with REFUSING if no registered vrfkit is found
python3 parser/batch_process.py --replays REPLAYS --outbox OUTBOX --vrfkit bin/vrfkit --lookup data/name_lookup_build13_08.json --only ONE_REPLAY.vrf
```
Run one replay first and read its `status.json`. A replay whose build is not in the registry stops with `unsupported_build`; that is the correct
result, not something to work around. Never fill, default or invent a value; never run a binary that is not registered.

## Known limits (today)
- Only release-13.08 Swiftplay is verified. Patch 13.09 (Hush) is unsupported by the pinned vrfkit; its codename and ID are unknown.
- `RoundInfos.StartOfRound*` is zero in the sample (money elsewhere is real). `characterUltimateUsed` over-reports about 50%.
- Built as reference only (13.08 sample): the 15 groups in `parser/meta_tables.py`. Not built: per-hit damage and regions, kill weapon and assists, spike site and planter, ability lifecycle beyond cast and actor open/close, effect intervals, health and alive state, purchases, capability report, tests A to I.
- Economy is not all zero: see `knowledge/Reference/Replay Data Guide.md` item 11.
""")

# 8. manifest, write, verify
manifest = {"package": "valosaber-bootstrap", "version": VERSION, "built": BUILT, "repo_commit": commit,
            "registered_vrfkit_sha256": sorted(reg), "vrfkit_included": bool(a.with_vrfkit),
            "files": {k: {"bytes": len(v), "sha256": sha(v)} for k, v in sorted(files.items())}}
add("PACKAGE_MANIFEST.json", json.dumps(manifest, indent=2))
out = Path(a.out)
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for k in sorted(files):
        z.writestr(k, files[k])
with zipfile.ZipFile(out) as z:
    assert z.testzip() is None
    mf = json.loads(z.read("PACKAGE_MANIFEST.json"))
    for k, v in mf["files"].items():
        d = z.read(k)
        assert len(d) == v["bytes"] and sha(d) == v["sha256"], k
    names = z.namelist()
print(f"wrote {out} ({out.stat().st_size:,} bytes, {len(names)} entries); every manifest hash re-checked after reopening")
