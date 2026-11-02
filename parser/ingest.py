#!/usr/bin/env python3
"""Valosaber ingest: verify match shards and merge them into size-capped combined parts.

usage: ingest.py INBOX_DIR WAREHOUSE_DIR [--max-mb 8]

Two kinds of entries are recognised under INBOX_DIR:
  * shards: <dir>/index.json (schema_version 2) -> WAREHOUSE/<table>/part-NNNN.parquet
  * analytics tables: <dir>/tables_manifest.json (schema meta-1, written by parser/meta_tables.py, with an analytics_tables/ folder)
    -> WAREHOUSE/analytics/<table>/ ; small tables are merged into size-capped parts, large ones (for example player_state) are
    written per match and split by rows to stay under the cap. Rejected whole if a file hash or row count differs, a table
    carries another match_id, the same source_sha256 is already ingested under another match_id, or validation_findings has a FAIL.

INBOX_DIR     folder of shard folders, each holding index.json plus parquet tables
WAREHOUSE_DIR output: <table>/part-0001.parquet ... plus catalog.json

Idempotent: a match already in catalog.json is skipped, so the same inbox can be
re-ingested after new shards arrive. A shard that fails any check is rejected whole
and listed in the report; nothing partial is merged.
"""
import argparse, hashlib, json, sys
from pathlib import Path
import numpy as np
import pandas as pd

ap = argparse.ArgumentParser()
ap.add_argument("inbox"); ap.add_argument("warehouse"); ap.add_argument("--max-mb", type=float, default=8.0)
a = ap.parse_args()
inbox, wh = Path(a.inbox), Path(a.warehouse); wh.mkdir(parents=True, exist_ok=True)
cap = int(a.max_mb * 1024 * 1024)
cat_path = wh / "catalog.json"
catalog = json.load(open(cat_path)) if cat_path.exists() else {"schema_version": 1, "matches": {}}

def verify(d: Path):
    idx = json.load(open(d / "index.json"))
    if idx.get("schema_version") != 2: return None, "unsupported schema_version (need 2; version 1 shards have clipped yaw)"
    for name, meta in idx["tables"].items():
        fp = d / f"{name}.parquet"
        if not fp.exists(): return None, f"{name}: file missing"
        if hashlib.sha256(fp.read_bytes()).hexdigest() != meta["sha256"]: return None, f"{name}: checksum mismatch"
        n = pd.read_parquet(fp, columns=[pd.read_parquet(fp).columns[0]]).shape[0]
        if n != meta["rows"]: return None, f"{name}: expected {meta['rows']} rows, found {n}"
    return idx, None

accepted, rejected, skipped = [], [], []
for d in sorted(p.parent for p in list(inbox.glob("*/index.json")) + list(inbox.glob("*/shard/index.json"))):
    idx, err = verify(d)
    if err: rejected.append((d.name, err)); continue
    if idx["match_id"] in catalog["matches"]: skipped.append(idx["match_id"]); continue
    accepted.append((d, idx))

# merge: append new rows to the newest part until it reaches the cap, then start a new part
for table in sorted({t for _, idx in accepted for t in idx["tables"]}):
    tdir = wh / table; tdir.mkdir(exist_ok=True)
    parts = sorted(tdir.glob("part-*.parquet"))
    for d, idx in accepted:
        if table not in idx["tables"]: continue
        new = pd.read_parquet(d / f"{table}.parquet")
        if parts and parts[-1].stat().st_size < cap * 0.8:
            cur = pd.concat([pd.read_parquet(parts[-1]), new], ignore_index=True); target = parts[-1]
        else:
            cur = new; target = tdir / f"part-{len(parts)+1:04d}.parquet"; parts.append(target)
        for c in cur.columns:
            if cur[c].dtype == object or str(cur[c].dtype) == "category": cur[c] = cur[c].astype("category")
        cur.to_parquet(target, compression="zstd", compression_level=12, index=False)
        if target.stat().st_size > cap: sys.exit(f"{target} exceeds cap; lower per-part batch size")

for d, idx in accepted:
    catalog["matches"][idx["match_id"]] = {"build": idx["build"], "mode": idx["mode"], "rounds": idx["rounds"],
        "tables": {t: m["rows"] for t, m in idx["tables"].items()}}
json.dump(catalog, open(cat_path, "w"), indent=1)

# ---------------------------------------------------------------- analytics tables
def verify_an(m: Path):
    man = json.load(open(m / "tables_manifest.json"))
    if man.get("schema_version") != "meta-1": return None, f"unsupported analytics schema_version {man.get('schema_version')!r}"
    td = m / "analytics_tables"
    for name, meta in man["tables"].items():
        fp = td / f"{name}.parquet"
        if not fp.exists(): return None, f"{name}: file missing"
        if hashlib.sha256(fp.read_bytes()).hexdigest() != meta["sha256"]: return None, f"{name}: checksum mismatch"
        df = pd.read_parquet(fp)
        if len(df) != meta["rows"]: return None, f"{name}: expected {meta['rows']} rows, found {len(df)}"
        if "match_id" in df and len(df) and set(df.match_id.dropna().unique()) != {man["match_id"]}:
            return None, f"{name}: rows carry a match_id different from the manifest"
    if "validation_findings" not in man["tables"]: return None, "validation_findings table missing"
    vf = pd.read_parquet(td / "validation_findings.parquet")
    if (vf.status == "FAIL").any():
        return None, "validation_findings has FAIL: " + "; ".join(vf[vf.status == "FAIL"].check.astype(str))[:300]
    if not (m / "completeness_report.json").exists(): return None, "completeness_report.json missing"
    return man, None

an_acc, an_rej, an_skip = [], [], []
an_cat = catalog.setdefault("analytics", {})
for m in sorted(p.parent for p in inbox.glob("**/tables_manifest.json") if len(p.relative_to(inbox).parts) <= 3):
    man, err = verify_an(m)
    if err: an_rej.append((m.name, err)); continue
    mid, sh = man["match_id"], man.get("source_sha256")
    if mid in an_cat: an_skip.append(mid); continue
    clash = [k for k, v in an_cat.items() if sh and v.get("source_sha256") == sh]
    if clash: an_rej.append((m.name, f"source_sha256 already ingested as match {clash[0]}")); continue
    if any(x[1]["match_id"] == mid for x in an_acc): an_skip.append(mid); continue
    an_acc.append((m, man))
adir = wh / "analytics"
for m, man in an_acc:
    for table, meta in man["tables"].items():
        tdir = adir / table; tdir.mkdir(parents=True, exist_ok=True)
        new = pd.read_parquet(m / "analytics_tables" / f"{table}.parquet")
        for c in new.columns:
            if new[c].dtype == object or str(new[c].dtype) == "category": new[c] = new[c].astype(object)
        if meta["bytes"] > cap * 0.2:  # large table: own files for this match, sliced by rows to stay under the cap
            n = max(1, int(meta["bytes"] / (cap * 0.5)) + 1)
            for i, sl in enumerate(np.array_split(np.arange(len(new)), n)):
                f = tdir / f"{man['match_id'][:8]}-{i+1:02d}.parquet"
                new.iloc[sl].to_parquet(f, compression="zstd", compression_level=12, index=False)
                if f.stat().st_size > cap: sys.exit(f"{f} exceeds cap; lower --max-mb or split further")
        else:
            parts = sorted(tdir.glob("part-*.parquet"))
            if parts and parts[-1].stat().st_size < cap * 0.5:
                cur = pd.concat([pd.read_parquet(parts[-1]), new], ignore_index=True); target = parts[-1]
            else:
                cur = new; target = tdir / f"part-{len(parts)+1:04d}.parquet"
            cur.to_parquet(target, compression="zstd", compression_level=12, index=False)
            if target.stat().st_size > cap: sys.exit(f"{target} exceeds cap")
    an_cat[man["match_id"]] = {"source_sha256": man.get("source_sha256"), "run_id": man.get("run_id"), "source_build": man.get("source_build"),
                               "tables": {t: v["rows"] for t, v in man["tables"].items()}}
json.dump(catalog, open(cat_path, "w"), indent=1)
if an_acc or an_rej or an_skip:
    print(f"analytics: accepted {len(an_acc)} | already ingested {len(an_skip)} | rejected {len(an_rej)}")
    for n, e in an_rej: print("  REJECTED analytics", n, "-", e)

print(f"accepted {len(accepted)} | already ingested {len(skipped)} | rejected {len(rejected)}")
for n, e in rejected: print("  REJECTED", n, "-", e)
tot = 0
for f in sorted(wh.rglob("*.parquet")):
    tot += f.stat().st_size; print(f"  {f.parent.name}/{f.name:18s} {f.stat().st_size:>10,d} bytes")
print(f"warehouse: {len(catalog['matches'])} shard matches, {len(catalog.get('analytics', {}))} analytics matches, {tot:,d} bytes total, every part <= {a.max_mb} MB")
