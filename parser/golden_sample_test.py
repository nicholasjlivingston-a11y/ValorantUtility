#!/usr/bin/env python3
"""Exact regression test on the one golden sample (replay 4c1d14ba-6e21-496f-9101-1b85fa513fd8, build
release-13.08, Swiftplay). These values are expectations for THAT replay only; they are never applied to others.

usage: golden_sample_test.py SHARD_DIR EXPORT_DIR
A pass proves the export-to-shard logic still reproduces the sample. When started from an export and not the raw
.vrf it is labelled EXPORT_PIPELINE_VALIDATED. It says nothing about whether any vrfkit can decode a raw replay.
"""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd

shard, exp = Path(sys.argv[1]), Path(sys.argv[2])
idx = json.load(open(shard / "index.json"))
assert idx["match_id"] == "4c1d14ba-6e21-496f-9101-1b85fa513fd8", f"not the golden sample: {idx['match_id']}"
k, d, p = (pd.read_parquet(shard / f"{n}.parquet") for n in ("kills", "damage", "players"))
ev = pd.read_parquet(exp / "events.parquet", columns=["group", "time1"])
deaths = np.sort(ev[ev["group"].astype(str) == "characterDeath"].time1.astype("int64").to_numpy())
gap = max(int(np.abs(deaths - t).min()) for t in k.t.astype("int64"))
checks = {"rounds == 5": idx["rounds"] == 5, "kills == 34": len(k) == 34, "players == 10": len(p) == 10,
          "teams 5 and 5": sorted(p.team.value_counts().tolist()) == [5, 5],
          "damage dealt == received == 6049.78": abs(float(d.dealt.sum()) - 6049.78) < 0.02 and abs(float(d.recv.sum()) - 6049.78) < 0.02,
          f"largest kill-to-death-event gap {gap} ms <= 50": gap <= 50,
          "build is release-13.08 and mode Swiftplay": idx["build"].endswith("release-13.08") and idx["mode"] == "Swiftplay"}
for c, ok in checks.items():
    print(("PASS " if ok else "FAIL ") + c)
print("EXPORT_PIPELINE_VALIDATED" if all(checks.values()) else "GOLDEN SAMPLE FAILED")
sys.exit(0 if all(checks.values()) else 1)
