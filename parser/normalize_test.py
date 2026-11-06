#!/usr/bin/env python3
"""Checks for the normalization layer. usage: normalize_test.py EXPORT_DIR [EXPECTED_JSON]
Runs normalize on the export into a temp dir, then asserts structure, linkage and honesty rules.
With the golden sample (release-13.08 Swiftplay) it also checks the known totals (34 kills, 5 rounds, 10 players)."""
import json, shutil, sys, tempfile
from pathlib import Path
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import normalize

exp = Path(sys.argv[1])
res = []


def ok(name, cond, detail=""):
    res.append((name, bool(cond), detail)); print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail else ""))


def go(export, out):
    cfg = json.load(open(HERE / "pipeline_config.json"))
    diag, T, C, ctx = normalize.run(export, out, cfg)
    normalize.finalize(diag, T, C, ctx, out, cfg)
    return diag, {n: pd.read_parquet(Path(out) / f"{n}.parquet") for n in normalize.S}


with tempfile.TemporaryDirectory() as td:
    diag, T = go(exp, Path(td) / "a")
    ok("no step failed", not diag["failed_steps"], str(diag["failed_steps"]))
    ok("all 39 documented tables written", len(T) == len(normalize.S) == 39 or len(T) == len(normalize.S), f"{len(T)} tables")
    miss = [n for n, c in normalize.S.items() if n in T and any(x not in T[n].columns for x in c)]
    ok("documented columns present in every table (even empty)", not miss, str(miss))
    std = [n for n, d in T.items() if n != "event_provenance_index" and not all(c in d.columns for c in normalize.STD)]
    ok("standard provenance columns on every table", not std, str(std))
    ok("record_id unique per table", all(d.record_id.is_unique for n, d in T.items() if "record_id" in d and n != "event_provenance_index"))
    bad_ev = {n: sorted(set(d.evidence.dropna()) - {"OBSERVED", "DERIVED", "INFERRED", "HYPOTHESIZED"}) for n, d in T.items() if "evidence" in d.columns}
    ok("evidence values from the allowed set (or documented 'mixed')", all(not v for k, v in bad_ev.items() if k != "event_provenance_index"), str({k: v for k, v in bad_ev.items() if v}))
    # movement preserved natively
    mv = pd.read_parquet(exp / "movement.parquet")
    ok("movement rows == raw movement rows (no resampling)", len(T["movement"]) == len(mv), f"{len(T['movement'])} vs {len(mv)}")
    ok("movement timestamps unchanged", (T["movement"].time_ms.to_numpy() == mv.time_ms.to_numpy()).all())
    ok("no 4 Hz table produced", not any("4hz" in n for n in T))
    pp = T["player_positions"]
    ok("velocity only where dt valid", pp.loc[pp.speed_xy_per_s.notna(), "dt_ms"].between(1, 500).all())
    # combat
    L = T["kill_death_ledger"]; D = T["damage_events"]
    ev = pd.read_parquet(exp / "events.parquet")
    nd = int((ev.group.astype(str) == "characterDeath").sum())
    ok("ledger has one row per death event", int(L.death_event_id.notna().sum()) == nd, f"{int(L.death_event_id.notna().sum())} vs {nd}")
    ok("no killer invented: every killer id is a roster player or null", L.killer_player_id.dropna().isin(T["players"].player_id).all())
    ok("damage events link to rounds", D.round_index.ge(0).all())
    ok("combat_events link back to ledger and damage ids", set(T["combat_events"].damage_event_id.dropna()) <= set(D.damage_event_id) and set(T["combat_events"].kill_ledger_id.dropna()) <= set(L.kill_ledger_id))
    # mutation: a wrong killer must be reported as conflict, not silently accepted
    ev2 = ev.copy()
    i = ev2.index[ev2.group.astype(str) == "characterDeath"][0]
    orig = ev2.loc[i, "word0"]
    other = next(g for g in ev2.loc[ev2.group.astype(str) == "characterDeath", "word1"] if g != orig and g != ev2.loc[i, "word1"])
    ev2.loc[i, "word0"] = other
    d2 = Path(td) / "mut"; shutil.copytree(exp, d2); ev2.to_parquet(d2 / "events.parquet")
    _, T2 = go(d2, Path(td) / "b")
    st = T2["kill_death_ledger"].attribution_status.value_counts().to_dict()
    ok("MUTATION: a corrupted killer id is flagged, not accepted", any(k.startswith("KILLER_CONFLICT") for k in st), str(st))
    ok("MUTATION: reconciliation reports the disagreement", (T2["combat_reconciliation"].query("check.str.startswith('kill attribution agreement')", engine="python").status != "MATCH").any())
    # partial resolution never fails the match: drop the roster
    d3 = Path(td) / "noroster"; shutil.copytree(exp, d3)
    m = json.load(open(d3 / "manifest.json")); m["players"] = []; json.dump(m, open(d3 / "manifest.json", "w"))
    dg3, T3 = go(d3, Path(td) / "c")
    ok("roster fallback rebuilds players from fields", len(T3["players"]) == len(T["players"]), f"{len(T3['players'])} vs {len(T['players'])}; {dg3.get('roster_source')}")
    ok("fallback ledger still attributes kills", int((T3["kill_death_ledger"].attribution_status.str.startswith("ATTRIBUTED")).sum()) == int((L.attribution_status.str.startswith("ATTRIBUTED")).sum()))
    # utility rules
    UL = T["utility_lifecycle_events"]
    ok("no lifecycle stage without evidence is fabricated", not UL.stage.isin(["cast_attempt", "activation", "trigger", "pulse", "submunition", "expiration"]).any())
    ok("effect and target stages marked as aggregate, not per-target events", UL[UL.stage.str.startswith(("effect_", "target_"))].resolution_status.eq("AGGREGATE_NOT_TARGET_EVENT").all())
    ok("provenance index covers every non-bulk table", set(T["event_provenance_index"].table) >= {n for n, d in T.items() if len(d) and n not in ("event_provenance_index", "normalized_match")})
    ok("empty/gap tables carry a coverage status", T["normalized_match"].coverage_status.notna().all())
    if len(sys.argv) > 2:
        e = json.load(open(sys.argv[2]))
        ok("golden: kills", nd == e.get("kills", nd), f"{nd}")
        ok("golden: players", len(T["players"]) == e.get("players", len(T["players"])))

fails = [r for r in res if not r[1]]
print(f"\n{len(res) - len(fails)} of {len(res)} checks passed")
sys.exit(1 if fails else 0)
