#!/usr/bin/env python3
"""Valosaber ingest: verify match shards and merge them into size-capped combined parts.

usage: ingest.py INBOX_DIR WAREHOUSE_DIR [--max-mb 8]

INBOX_DIR     folder of shard folders, each holding index.json plus parquet tables
WAREHOUSE_DIR output: <table>/part-0001.parquet ... plus catalog.json

Idempotent: a match already in catalog.json is skipped, so the same inbox can be
re-ingested after new shards arrive. A shard that fails any check is rejected whole
and listed in the report; nothing partial is merged.
"""
import argparse, hashlib, json, sys
from pathlib import Path
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
    if idx.get("schema_version") != 1: return None, "unsupported schema_version"
    for name, meta in idx["tables"].items():
        fp = d / f"{name}.parquet"
        if not fp.exists(): return None, f"{name}: file missing"
        if hashlib.sha256(fp.read_bytes()).hexdigest() != meta["sha256"]: return None, f"{name}: checksum mismatch"
        n = pd.read_parquet(fp, columns=[pd.read_parquet(fp).columns[0]]).shape[0]
        if n != meta["rows"]: return None, f"{name}: expected {meta['rows']} rows, found {n}"
    return idx, None

accepted, rejected, skipped = [], [], []
for d in sorted(p.parent for p in inbox.glob("*/index.json")):
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

print(f"accepted {len(accepted)} | already ingested {len(skipped)} | rejected {len(rejected)}")
for n, e in rejected: print("  REJECTED", n, "-", e)
tot = 0
for tdir in sorted(p for p in wh.iterdir() if p.is_dir()):
    for f in sorted(tdir.glob("*.parquet")):
        tot += f.stat().st_size; print(f"  {tdir.name}/{f.name:18s} {f.stat().st_size:>10,d} bytes")
print(f"warehouse: {len(catalog['matches'])} matches, {tot:,d} bytes total, every part <= {a.max_mb} MB")
