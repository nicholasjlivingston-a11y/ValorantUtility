#!/usr/bin/env python3
"""Build the attributed ability-effect table from the reconstructed casts."""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument("--export", default="out", help="vrfkit export directory")
ap.add_argument("--casts", default="casts_raw.parquet",
                help="output of extract_casts.py")
ap.add_argument("--out", default="ability_effects.csv")
args = ap.parse_args()

exp = Path(args.export)
ev = pd.read_parquet(exp / "events.parquet")
f = pd.read_parquet(exp / "fields.parquet")
raw = pd.read_parquet(args.casts)

# ---- roster: PlayerState guid <-> subject uuid <-> team ----------------------
ps = f[f["group_path"].astype(str)
       == "/Game/GameModes/Bomb/BombPlayerState.BombPlayerState_C"]
subj = (ps[ps["field_name"].astype(str) == "Subject"]
        [["actor_net_guid", "value_str"]]
        .drop_duplicates()
        .rename(columns={"actor_net_guid": "ps_guid", "value_str": "uuid"}))

# The two teams occupy separate contiguous PlayerState GUID blocks. Derive the
# split from the largest gap between sorted GUIDs rather than a fixed threshold,
# so extra PlayerStates (leavers/reconnects) don't land on the wrong side.
g = np.sort(subj["ps_guid"].unique())
cut = g[int(np.argmax(np.diff(g))) + 1] if len(g) > 1 else g[0]
subj["team"] = np.where(subj["ps_guid"] < cut, "Team A", "Team B")

uuid_to_agent = (raw.drop_duplicates("cast_uid")[["caster", "agent"]]
                 .dropna().drop_duplicates()
                 .set_index("caster")["agent"].to_dict())
subj["agent"] = subj["uuid"].map(uuid_to_agent)

# stable display label; two players share Omen and two share Sova
subj = subj.sort_values(["team", "agent"]).reset_index(drop=True)
labels, seen = [], {}
for _, r in subj.iterrows():
    a = r["agent"]
    seen[a] = seen.get(a, 0) + 1
    dupes = (subj["agent"] == a).sum()
    labels.append(f"{a}#{seen[a]}" if dupes > 1 else a)
subj["label"] = labels

guid_to_label = subj.set_index("ps_guid")["label"].to_dict()
guid_to_team = subj.set_index("ps_guid")["team"].to_dict()
uuid_to_label = subj.set_index("uuid")["label"].to_dict()
uuid_to_team = subj.set_index("uuid")["team"].to_dict()

# ---- absolute match time ----------------------------------------------------
# CastTime's zero is the barrier drop (end of buy phase), not roundStarted:
# +30 s normally, +45 s on the first round of each half (rounds 0 and 12).
starts = {i: t for i, t in
          enumerate(ev[ev["group"] == "roundStarted"].sort_values("time1")["time1"])}


# Barrier drop is OBSERVED: the first ClientBuyPhaseEnd field inside each round window. Only rounds without one
# fall back to the fixed 30 s / 45 s guess (and are counted in the printed summary).
_bp = np.sort(f[f["field_name"].astype(str).str.contains("ClientBuyPhaseEnd")]["time_ms"].to_numpy())
_obs = {}
for _i, _t in starts.items():
    _x = _bp[(_bp >= _t) & (_bp < starts.get(_i + 1, 10 ** 12))]
    if len(_x):
        _obs[_i] = int(_x[0]) - int(_t)
print(f"barrier drop observed for {len(_obs)} of {len(starts)} rounds (rest use the fixed fallback)")


def barrier_offset(r):
    if r in _obs:
        return _obs[r]
    # fallback only
    return 45000 if r in (0, 12) else 30000


df = raw.copy()
df = df[df["tag"].notna()].copy()
df["round"] = df["round"].astype("Int64")
df["abs_ms"] = (df["round"].map(starts)
                + df["cast_time_s"] * 1000
                + df["round"].map(barrier_offset))

df["caster_label"] = df["caster"].map(uuid_to_label)
df["caster_team"] = df["caster"].map(uuid_to_team)
df["target_label"] = df["target"].map(
    lambda v: guid_to_label.get(int(v)) if pd.notna(v) else None)
df["target_team"] = df["target"].map(
    lambda v: guid_to_team.get(int(v)) if pd.notna(v) else None)


def mmss(ms):
    if pd.isna(ms):
        return None
    s = int(ms // 1000)
    return f"{s // 60}:{s % 60:02d}"


df["match_clock"] = df["abs_ms"].map(mmss)

out = df[[
    "cast_uid", "round", "match_clock", "abs_ms", "cast_time_s",
    "caster_label", "caster_team", "agent", "slot", "round_phase",
    "tag", "tag_id", "tag_value",
    "target_label", "target_team", "target_value",
    "cast_x", "cast_y", "cast_z", "destroyed_count",
]].rename(columns={
    "caster_label": "caster", "target_label": "target",
    "slot": "slot_id", "tag_value": "value", "target_value": "per_target_value",
}).sort_values(["round", "abs_ms", "cast_uid", "tag"]).reset_index(drop=True)

# A cast's true identity is (caster, round, CastTime) -- the array position it
# occupies can change between snapshots, so cast_uid alone over-splits. Collapse
# each (cast identity, tag, target) to its final accumulated state.
out["cast_id"] = (out["caster"].astype(str) + "|"
                  + out["round"].astype(str) + "|"
                  + out["cast_time_s"].round(3).astype(str))
agg = {c: "first" for c in out.columns}
agg.update({"value": "max", "per_target_value": "max",
            "destroyed_count": "max", "abs_ms": "min", "match_clock": "first"})
out = (out.groupby(["cast_id", "tag", "target"], dropna=False, as_index=False)
          .agg(agg))
out = out.drop(columns=["cast_uid"]).rename(columns={"cast_id": "cast"})
out = out.sort_values(["round", "abs_ms", "cast", "tag"]).reset_index(drop=True)

col_order = [c for c in [
    "cast", "round", "match_clock", "caster", "caster_team", "agent",
    "slot_id", "round_phase", "tag", "tag_id", "value",
    "target", "target_team", "per_target_value",
    "cast_x", "cast_y", "cast_z", "destroyed_count", "abs_ms", "cast_time_s",
] if c in out.columns]
out = out[col_order]

out.to_csv(args.out, index=False)
out.to_parquet(str(Path(args.out).with_suffix(".parquet")), index=False)

print("roster")
print(subj[["team", "label", "ps_guid", "uuid"]].to_string(index=False))
print()
print("rows:", len(out), " casts:", out["cast"].nunique(),
      " tags:", out["tag"].nunique())
unresolved = int((out["per_target_value"].notna() & out["target"].isna()).sum())
print(f"target resolution: {int(out['target'].notna().sum())} resolved, "
      f"{unresolved} unresolved")
print("wrote", args.out)

# Validate the barrier-drop time base against an independent signal. If the
# kill-tagged casts don't line up with death events, the offset or the round
# indexing is wrong and the timings must not be reported as fact.
deaths = np.sort(ev[ev["group"] == "characterDeath"]["time1"].values)
ka = out.loc[out["tag"] == "Kills", "abs_ms"].dropna().values
if len(ka) and len(deaths):
    d = np.array([np.min(np.abs(ka - x)) for x in deaths])
    near = int((d < 2500).sum())
    print(f"time-base check: {near} of {len(deaths)} death events have a "
          f"kill-tagged cast within 2.5 s")
    if near == 0:
        print("  WARNING: no alignment -- do not trust match_clock/abs_ms.")
