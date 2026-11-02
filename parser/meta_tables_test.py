#!/usr/bin/env python3
"""Tests for parser/meta_tables.py. usage: meta_tables_test.py EXPORT_DIR SHARD_DIR
Golden values are for replay 4c1d14ba only (release-13.08, Swiftplay). Also a mutation test: a shard whose kills are all
identical must make the reconciliation finding FAIL (a delivery cannot pass on placeholder data)."""
import json, shutil, subprocess, sys, tempfile
from pathlib import Path
import pandas as pd

exp, shard = Path(sys.argv[1]), Path(sys.argv[2])
here = Path(__file__).resolve().parent
tmp = Path(tempfile.mkdtemp())


def run(sh, out):
    r = subprocess.run([sys.executable, "-I", str(here / "meta_tables.py"), str(exp), str(out), "--shard", str(sh), "--run-id", "t"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-800:]
    return Path(out) / "analytics_tables"


T = run(shard, tmp / "good")
rd = lambda n: pd.read_parquet(T / f"{n}.parquet")
find = rd("validation_findings")
res = {}
res["15 groups present"] = all((T / f"{n}.parquet").is_file() for n in ["matches", "players", "rounds", "player_state", "kills", "deaths", "damage_events", "economy", "spike_events", "ability_events", "utility_objects", "player_effects", "world_state", "map_identity", "validation_findings"])
res["rounds == 5, all with WinningTeam"] = len(rd("rounds")) == 5 and rd("rounds").WinningTeam.notna().all()
res["deaths == 34, none unmatched"] = len(rd("deaths")) == 34 and rd("deaths").matched_kill_index.notna().all()
res["money not all zero"] = (rd("economy").query("field_name == 'Money'").value_i64.dropna() > 0).any()
res["players == 10 with characterId"] = len(rd("players")) == 10 and rd("players").characterId.notna().all()
res["no FAIL findings"] = not (find.status == "FAIL").any()
const = [n for n in ("kills", "deaths", "economy", "player_state", "rounds") if len(rd(n)) > 1 and rd(n).drop(columns=["match_id", "run_id", "evidence"]).drop_duplicates().shape[0] <= 1]
res["no constant table"] = not const
ps = rd("player_state")
res["player_state: every roster player has rows, positions vary"] = ps.subject.nunique() == len(rd("players")) and ps.pos_x.nunique() > 100
rep = json.load(open(tmp / "good" / "analytics_tables" / ".." / "completeness_report.json")) if (tmp / "good" / "completeness_report.json").exists() else None
res["completeness report lists gaps with allowed codes"] = bool(rep) and all(g["code"] in rep["statuses"] for g in rep["gaps"]) and len(rep["gaps"]) > 0

# mutation: all kills identical
bad = tmp / "badshard"; shutil.copytree(shard, bad)
k = pd.read_parquet(bad / "kills.parquet"); k["t"] = 0; k["rnd"] = 0
k.to_parquet(bad / "kills.parquet", index=False)
Tb = run(bad, tmp / "bad")
fb = pd.read_parquet(Tb / "validation_findings.parquet")
res["mutation: identical kills -> reconciliation FAIL"] = ((fb.check == "kill-death reconciliation") & (fb.status == "FAIL")).any()

for c, ok in res.items():
    print(("PASS " if ok else "FAIL ") + c)
shutil.rmtree(tmp, ignore_errors=True)
sys.exit(0 if all(res.values()) else 1)
