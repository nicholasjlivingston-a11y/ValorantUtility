#!/usr/bin/env python3
"""Read-only audit of normalized output. usage: audit_cohort.py OUTBOX_DIR [--out audit_cohort.csv]
For every <match>/normalized folder: failed steps, warnings, kill attribution, round/buy-time basis, team sizes, roster source,
position attribution, utility resolution, empty tables. Prints a table and writes CSV + JSON. Changes nothing."""
import argparse, json
from pathlib import Path
import pandas as pd

ap = argparse.ArgumentParser(); ap.add_argument("outbox"); ap.add_argument("--out", default="audit_cohort")
a = ap.parse_args()
rows, detail = [], {}
for d in sorted(Path(a.outbox).glob("*/normalized")):
    m = d.parent.name
    rd = lambda n: pd.read_parquet(d / f"{n}.parquet") if (d / f"{n}.parquet").exists() else pd.DataFrame()
    try:
        diag = json.load(open(d / "parser_diagnostics.json"))
        L, R, T, pc, uo, ut, ef, nm = rd("kill_death_ledger"), rd("rounds"), rd("teams"), rd("position_coverage"), rd("utility_objects"), rd("utility_targets"), rd("utility_effects"), rd("normalized_match")
        st = L.attribution_status.value_counts().to_dict() if len(L) else {}
        ev = rd("events"); nd = int((ev.event_group == "characterDeath").sum()) if len(ev) else 0
        att = pc[pc.scope == "match_mapping"].fraction_attributed
        r = dict(match=m, build=diag.get("source_build"), roster_source=str(diag.get("roster_source"))[:40], failed_steps=";".join(diag.get("failed_steps") or []),
                 warn_checks=sum(1 for c in diag["checks"] if c["level"] == "warn"), rounds=len(R), deaths=nd,
                 ledger_attributed=sum(v for k, v in st.items() if k.startswith("ATTRIBUTED")), ledger_conflict=sum(v for k, v in st.items() if "CONFLICT" in k),
                 ledger_other=sum(v for k, v in st.items() if not k.startswith("ATTRIBUTED") and "CONFLICT" not in k),
                 buy_observed=int(R.buy_end_basis.str.contains("OBSERVED").sum()) if len(R) else 0, buy_fallback=int(R.buy_end_basis.str.contains("INFERRED").sum()) if len(R) else 0,
                 team_sizes="/".join(map(str, sorted(T.n_players.tolist()))) if len(T) else "", position_attributed=round(float(att.iloc[0]), 3) if len(att) else None,
                 n_unresolved_identities=len(rd("unresolved_identities")), utility_objects=len(uo), utility_owner_resolved=int((uo.resolution_status == "OWNER_RESOLVED").sum()) if len(uo) else 0,
                 casts=len(rd("ability_casts")), targets=len(ut), targets_resolved=int((ut.target_status == "RESOLVED").sum()) if len(ut) else 0,
                 empty_tables=";".join(nm[nm.rows == 0].table.tolist()) if len(nm) else "")
        detail[m] = dict(ledger_status=st, warn=[c for c in diag["checks"] if c["level"] == "warn"], failed=diag.get("failed_steps"), step_errors={k: v.get("error", "")[-500:] for k, v in diag["steps"].items() if not v["ok"]})
    except Exception as e:
        r = dict(match=m, failed_steps=f"AUDIT_ERROR {e}")
    # shard outcome from status.json when present
    sj = d.parent / "status.json"
    if sj.exists():
        s = json.load(open(sj)); r["overall"] = s.get("overall"); r["shard_ok"] = s.get("steps", {}).get("shard", {}).get("ok"); r["shard_error"] = str(s.get("steps", {}).get("shard", {}).get("error", ""))[-200:]
        r["vrfkit_sha256"] = str(s.get("vrfkit_sha256"))[:12]
    rows.append(r)
df = pd.DataFrame(rows)
pd.set_option("display.width", 250, "display.max_columns", 40, "display.max_colwidth", 40)
print(df.T.to_string() if len(df) <= 3 else df.to_string())
df.to_csv(a.out + ".csv", index=False); json.dump(detail, open(a.out + ".json", "w"), indent=1, default=str)
print("wrote", a.out + ".csv", a.out + ".json")
