#!/usr/bin/env python3
"""Reconstruct ability casts + tagged effects from vrfkit's fields.parquet.

AbilityCastsThisRound is a delta-replicated Unreal array: a snapshot only
carries the members that changed, and the array indices are reused as the
round's cast list grows and resets. So we replay the packet stream in order
and maintain per-(actor, cast_index) state, cutting a new cast identity
whenever the cast's own identity members (Player/Round/CastTime) change.
"""
import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent

GROUP = ("/Game/Characters/_Core/Comp_AbilityStatisticsReplicator."
         "Comp_AbilityStatisticsReplicator_C")

SUFFIX_RE = re.compile(r"_\d+_[0-9A-F]{32}$")
CAST_RE = re.compile(r"^AbilityCastsThisRound\[(\d+)\]\.(.+)$")
EFFECT_RE = re.compile(r"^Effects\[(\d+)\]\.(.+)$")
TARGET_RE = re.compile(r"^AffectedTargetsArray\[(\d+)\]\.(.+)$")

AGENT_BY_GUID = {}  # filled from actors.parquet

def load_codenames():
    """Verified codename -> agent map. Unknown codenames pass through unchanged,
    which is always correct; a guessed name is not. See identify_agents.py."""
    p = HERE / "codenames.json"
    if not p.is_file():
        return {}
    return json.loads(p.read_text()).get("map", {})


CODENAMES = load_codenames()


def load_agents(actors_path):
    act = pd.read_parquet(actors_path)
    pc = act[act["class_path"].astype(str).str.endswith("_PC_C")]
    out = {}
    for _, r in pc.iterrows():
        code = re.search(r"/Game/Characters/([A-Za-z0-9_]+)/", str(r["class_path"])).group(1)
        out[int(r["actor_net_guid"])] = CODENAMES.get(code, code)
    return out


def member_of(field_name):
    """Split a field name into (cast_idx, effect_idx, target_idx, leaf)."""
    m = CAST_RE.match(field_name)
    if not m:
        return None
    cast_idx = int(m.group(1))
    rest = SUFFIX_RE.sub("", m.group(2))
    em = EFFECT_RE.match(rest)
    if not em:
        return cast_idx, None, None, rest
    eff_idx = int(em.group(1))
    rest2 = em.group(2)
    tm = TARGET_RE.match(rest2)
    if not tm:
        return cast_idx, eff_idx, None, rest2
    return cast_idx, eff_idx, int(tm.group(1)), tm.group(2)


def scalar(row):
    for col in ("value_str", "value_i64", "value_f64", "value_bool"):
        v = row[col]
        if v is not None and not (isinstance(v, float) and pd.isna(v)):
            return v
    return None


def parse_vec(s):
    if not isinstance(s, str) or not s.startswith("("):
        return (None, None, None)
    try:
        parts = [float(p) for p in s.strip("()").split(",")]
        return tuple(parts[:3])
    except Exception:
        return (None, None, None)


def run(fields_path, actors_path):
    global AGENT_BY_GUID
    AGENT_BY_GUID = load_agents(actors_path)

    f = pd.read_parquet(fields_path)
    a = f[f["group_path"] == GROUP].copy()
    a = a.sort_values(["packet_id", "time_ms"], kind="stable")

    # slot_state[(actor, cast_idx)] -> last known value of every member at that
    # array position. Unreal deltas against the *position*, so a member absent
    # from a snapshot still holds its previous value even across a cast change.
    slot_state = defaultdict(dict)
    live = {}
    casts = {}          # cast_uid -> cast record
    order = []
    counter = 0
    cut_marker = {}   # (packet_id, actor, cast_idx) -> already cut this snapshot

    def new_cast(actor, cast_idx, key):
        nonlocal counter
        counter += 1
        uid = f"c{counter:05d}"
        prev = slot_state[key]
        st = {
            "uid": uid, "actor": actor, "cast_idx": cast_idx,
            # seed from the position's last known values
            "attrs": dict(prev),
            "effects": {},
        }
        live[key] = st
        casts[uid] = st
        order.append(uid)
        return st

    for row in a.itertuples(index=False):
        parsed = member_of(str(row.field_name))
        if parsed is None:
            continue
        cast_idx, eff_idx, tgt_idx, leaf = parsed
        actor = int(row.actor_net_guid)
        key = (actor, cast_idx)
        val = scalar(row._asdict())
        st = live.get(key)

        if eff_idx is None:
            # A change in CastTime or Round at this position = a different cast.
            if leaf in ("CastTime", "Round"):
                prev = slot_state[key].get(leaf)
                marker = (int(row.packet_id), actor, cast_idx)
                if st is None or (prev is not None and prev != val
                                  and not cut_marker.get(marker)):
                    st = new_cast(actor, cast_idx, key)
                    cut_marker[marker] = True
            if st is None:
                st = new_cast(actor, cast_idx, key)
            slot_state[key][leaf] = val
            st["attrs"][leaf] = val
            continue

        if st is None:
            st = new_cast(actor, cast_idx, key)

        eff = st["effects"].setdefault(eff_idx, {"targets": {}})
        if tgt_idx is None:
            eff[leaf] = val
        else:
            eff["targets"].setdefault(tgt_idx, {})[leaf] = val

    # flatten
    rows = []
    for uid in order:
        c = casts[uid]
        agent = AGENT_BY_GUID.get(c["actor"], f"guid{c['actor']}")
        player = c["attrs"].get("Player")
        rnd = c["attrs"].get("Round")
        ctime = c["attrs"].get("CastTime")
        slot = c["attrs"].get("Slot")
        phase = c["attrs"].get("RoundPhase")
        destroyed = c["attrs"].get("DestroyedCount")
        cx, cy, cz = parse_vec(c["attrs"].get("CastLocation"))
        if not c["effects"]:
            rows.append(dict(cast_uid=uid, agent=agent, caster=player,
                             round=rnd, slot=slot, round_phase=phase,
                             cast_time_s=ctime, cast_x=cx, cast_y=cy, cast_z=cz,
                             destroyed_count=destroyed, tag=None, tag_id=None,
                             tag_value=None, effect_time_s=None,
                             target=None, target_value=None))
            continue
        for ei in sorted(c["effects"]):
            e = c["effects"][ei]
            tag = e.get("LocalizedStat")
            tag_id = e.get("Statistic")
            tval = e.get("Value")
            etime = e.get("Time")
            tgts = e.get("targets", {})
            if not tgts:
                rows.append(dict(cast_uid=uid, agent=agent, caster=player,
                                 round=rnd, slot=slot, round_phase=phase,
                                 cast_time_s=ctime, cast_x=cx, cast_y=cy, cast_z=cz,
                                 destroyed_count=destroyed, tag=tag, tag_id=tag_id,
                                 tag_value=tval, effect_time_s=etime,
                                 target=None, target_value=None))
            else:
                for ti in sorted(tgts):
                    t = tgts[ti]
                    rows.append(dict(cast_uid=uid, agent=agent, caster=player,
                                     round=rnd, slot=slot, round_phase=phase,
                                     cast_time_s=ctime, cast_x=cx, cast_y=cy, cast_z=cz,
                                     destroyed_count=destroyed, tag=tag, tag_id=tag_id,
                                     tag_value=tval, effect_time_s=etime,
                                     target=t.get("AffectedPlayer"),
                                     target_value=t.get("Value")))
    return pd.DataFrame(rows)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--export", default="out", help="vrfkit export directory")
    ap.add_argument("--out", default="casts_raw.parquet")
    args = ap.parse_args()

    exp = Path(args.export)
    df = run(exp / "fields.parquet", exp / "actors.parquet")
    print("position-records:", df["cast_uid"].nunique(),
          " rows:", len(df),
          " tagged rows:", int(df["tag"].notna().sum()))
    print("NOTE: these are array-position records, not deduplicated casts.")
    print("      build_table.py collapses them on (caster, round, CastTime).")
    df.to_parquet(args.out, index=False)
    print("wrote", args.out)
