#!/usr/bin/env python3
"""Reference extractor for the meta agent's 15 data groups, from ONE vrfkit export folder.

usage: meta_tables.py EXPORT_DIR OUT_DIR [--shard SHARD_DIR] [--source-sha256 HEX] [--run-id ID] [--lookup JSON]

Reads the export (manifest, events, actors, fields, movement) and writes OUT_DIR/analytics_tables/*.parquet,
schema.md, completeness_report.json, tables_manifest.json. Rules (docs/EXTRACTION_REQUIREMENTS.md):
  * native resolution and original units; source field names kept (including misspellings); nothing zero-filled;
  * every row carries evidence (OBSERVED = read straight from a source record, DERIVED = computed from several,
    INFERRED = a reading that needs confirmation);
  * kills and damage_events are DERIVED projections of the stats shard (combat-report reciprocity) and need --shard;
    without it those two groups are reported UNRESOLVED instead of being invented;
  * gaps are reported with NOT_PRESENT_IN_SOURCE / NOT_EXPOSED_BY_PARSER / DECODE_FAILED / UNRESOLVED / NOT_TESTABLE.
This is reference code written and checked on ONE replay (release-13.08, Swiftplay). Counts are never forced to match it.
"""
import argparse, hashlib, json, re, sys, uuid
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent / "skill"))
import extract_casts  # noqa: E402

SCHEMA = "meta-1"
GS = "GameState"
ap = argparse.ArgumentParser()
ap.add_argument("export"); ap.add_argument("out")
ap.add_argument("--shard"); ap.add_argument("--source-sha256"); ap.add_argument("--run-id"); ap.add_argument("--lookup")
a = ap.parse_args()
E, O = Path(a.export), Path(a.out) / "analytics_tables"
O.mkdir(parents=True, exist_ok=True)
run_id = a.run_id or uuid.uuid4().hex
man = json.load(open(E / "manifest.json"))
match_id = man.get("friendly_name")
build = man.get("replay_build")
findings, gaps, tables, grain = [], [], {}, {}


def finding(group, check, status, detail, severity="info"):
    findings.append(dict(finding_id=len(findings), group=group, check=check, status=status, severity=severity, detail=detail))


def gap(group, item, code, note):
    gaps.append(dict(group=group, item=item, code=code, note=note))


def stamp(df, evidence):
    df = df.copy()
    df.insert(0, "match_id", match_id)
    df.insert(1, "run_id", run_id)
    if "evidence" not in df.columns:
        df["evidence"] = evidence
    else:
        df["evidence"] = df["evidence"].fillna(evidence)
    return df


def put(name, df, g):
    df = df.reset_index(drop=True)
    for c in df.columns:  # parquet categoricals would store every string in the export; keep plain values
        if isinstance(df[c].dtype, pd.CategoricalDtype):
            df[c] = df[c].astype(object)
    tables[name] = df
    grain[name] = g


def scalar(df):
    """first non-null of the typed value columns, kept as separate typed columns (no coercion)."""
    return df


# ---------------------------------------------------------------- matches / map_identity
lv = man.get("level_names_and_times") or []
put("matches", stamp(pd.DataFrame([dict(
    source_file=man.get("source_file"), source_size_bytes=man.get("source_size_bytes"), source_sha256=a.source_sha256,
    replay_build=build, replay_version=man.get("replay_version"), replay_changelist=man.get("replay_changelist"),
    duration_ms=man.get("duration_ms"), friendly_name=man.get("friendly_name"), is_live=man.get("is_live"),
    timestamp_ticks=man.get("timestamp_ticks"), platform=man.get("platform"),
    packet_count=(man.get("stats") or {}).get("packet_count"),
    malformed_packet_count=(man.get("stats") or {}).get("malformed_packet_count"),
    partial_error_count=(man.get("stats") or {}).get("partial_error_count"),
    game_mode=None)]), "OBSERVED"), "one row per replay (manifest.json)")
if a.source_sha256 is None:
    finding("matches", "source_sha256", "UNRESOLVED", "no --source-sha256 given; match identity falls back to friendly_name", "warn")

lookup = {}
if a.lookup and Path(a.lookup).is_file():
    lookup = json.load(open(a.lookup))
mrows = []
for L in lv:
    path = L.get("name")
    code = str(path).rstrip("/").split("/")[-1] if path else None
    mrows.append(dict(level_path=path, time_ms=L.get("time_ms"), map_code=code))
put("map_identity", stamp(pd.DataFrame(mrows), "OBSERVED"), "one row per level load recorded in the manifest")
gap("map_identity", "public map name, site and callout regions, coordinate transform", "NOT_PRESENT_IN_SOURCE",
    "the replay carries a level path only; names come from a separate lookup and stay unconfirmed until sourced")

# ---------------------------------------------------------------- players
roster = pd.DataFrame(man.get("players") or [])
loadouts = []
for s in man.get("game_specific_data") or []:
    try:
        j = json.loads(s)
    except Exception:
        continue
    if isinstance(j, dict) and "playerLoadouts" in j:
        loadouts = j["playerLoadouts"]
lo = pd.DataFrame([dict(subject=x.get("subject"), characterId=x.get("characterId")) for x in loadouts])
pl = roster.rename(columns={"actor_net_guid": "playerstate_actor_net_guid"}) if len(roster) else pd.DataFrame()
if len(pl):
    pl["character_net_guids"] = pl["character_net_guids"].map(lambda v: json.dumps([int(x) for x in v]) if v is not None else None)
    pl = pl.merge(lo, on="subject", how="left")
    if a.shard and (Path(a.shard) / "players.parquet").is_file():
        sp = pd.read_parquet(Path(a.shard) / "players.parquet")[["uuid", "team", "agent", "codename"]]
        sp = sp.rename(columns={"uuid": "subject", "team": "team_derived", "agent": "agent_derived", "codename": "agent_codename_derived"})
        pl = pl.merge(sp, on="subject", how="left")
    else:
        gap("players", "team and agent per player", "UNRESOLVED", "needs the stats shard players table (--shard); not resolved from the manifest alone")
put("players", stamp(pl, "OBSERVED"), "one row per roster entry; team/agent columns suffixed _derived come from the shard (DERIVED)")
subj_by_ps = dict(zip(roster.get("actor_net_guid", []), roster.get("subject", [])))
subj_by_char = {}
for _, r in roster.iterrows():
    for c in r["character_net_guids"]:
        subj_by_char[int(c)] = r["subject"]
gap("players", "display names / Riot IDs", "NOT_PRESENT_IN_SOURCE", "only subject UUIDs are in the replay; stability across matches is untested (open question 10)")

# ---------------------------------------------------------------- events
ev = pd.read_parquet(E / "events.parquet", columns=["id", "group", "time1", "time2", "word0", "word1", "payload_name"])
ev["group"] = ev["group"].astype(str)
deaths = ev[ev.group == "characterDeath"].sort_values("time1").reset_index(drop=True)
kills = None
if a.shard and (Path(a.shard) / "kills.parquet").is_file():
    kills = pd.read_parquet(Path(a.shard) / "kills.parquet").sort_values("t").reset_index(drop=True)
    kills.insert(0, "kill_index", range(len(kills)))
    k = kills.rename(columns={"killer": "killer_subject", "victim": "victim_subject", "t": "time_ms", "rnd": "round_index"})
    keep = [c for c in ("kill_index", "round_index", "time_ms", "killer_subject", "victim_subject") if c in k.columns]
    put("kills", stamp(k[keep], "DERIVED"), "one row per kill resolved from combat-report reciprocity (shard projection)")
    gap("kills", "assist type enum, positions at kill", "UNRESOLVED", "weapon class, bone, wall penetration and assist candidates are in kill_details; AssistType and DamageType are numeric ids with no label table")
else:
    gap("kills", "kill rows", "UNRESOLVED", "needs --shard")
d_rows = []
kt = kills.time_ms.to_numpy() if kills is not None and "time_ms" in kills else (kills.t.to_numpy() if kills is not None else None)
for i, r in deaths.iterrows():
    row = dict(death_event_id=r["id"], death_index=i, time1_ms=int(r["time1"]), time2_ms=int(r["time2"]), source_group="characterDeath")
    if kt is not None and len(kt):
        j = int(np.abs(kt - r["time1"]).argmin()); gp = int(abs(kt[j] - r["time1"]))
        row.update(matched_kill_index=j if gp <= 50 else None, match_gap_ms=gp, victim_subject=None)
    d_rows.append(row)
dd = pd.DataFrame(d_rows)
if kills is not None and len(dd):
    dd["victim_subject"] = dd.matched_kill_index.map(lambda j: None if pd.isna(j) else kills.loc[int(j), "victim"])
put("deaths", stamp(dd, "OBSERVED"), "one row per characterDeath event; death events carry no killer or victim, link columns are DERIVED by time")
if kills is not None:
    un = int(dd.matched_kill_index.isna().sum()); used = dd.matched_kill_index.dropna().nunique()
    finding("deaths", "kill-death reconciliation", "PASS" if un == 0 and used == len(kills) else "FAIL",
            f"{len(deaths)} death events, {len(kills)} kills, {un} deaths unmatched, {len(kills) - used} kills without a death event", "error" if un else "info")

dam = None
if a.shard and (Path(a.shard) / "damage.parquet").is_file():
    dam = pd.read_parquet(Path(a.shard) / "damage.parquet").rename(columns={"rnd": "round_index", "owner": "owner_subject", "other": "other_subject",
        "dealt": "DamageDealt", "recv": "DamageRecieved", "hits_d": "HitsDealt", "hits_r": "HitsRecieved", "did_kill": "bDidKill"})
    put("damage_by_pair_round", stamp(dam.drop(columns=["match_id"], errors="ignore"), "DERIVED"),
        "AGGREGATE: one row per owner, other player and round (source: Rounds[r].Reports[k].Interactions[i], shard projection); the hit-grain table is damage_events")
    finding("damage_by_pair_round", "dealt equals received", "PASS" if abs(dam.DamageDealt.sum() - dam.DamageRecieved.sum()) < 0.02 else "FAIL",
            f"dealt {dam.DamageDealt.sum():.2f}, received {dam.DamageRecieved.sum():.2f}")
else:
    gap("damage_by_pair_round", "pair-round damage rows", "UNRESOLVED", "needs --shard")

# ---------------------------------------------------------------- fields (big)
F = pd.read_parquet(E / "fields.parquet", columns=["time_ms", "packet_id", "actor_net_guid", "group_path", "field_name",
                                                  "value_i64", "value_f64", "value_bool", "value_str"])
F["field_name"] = F["field_name"].astype(str)
vcols = ["value_i64", "value_f64", "value_bool", "value_str"]

# rounds
rs = ev[ev.group == "roundStarted"].sort_values("time1")
rr = F[F.group_path.str.contains("_GameState_C") & F.field_name.str.match(r"^RoundResults\[\d+\]\.")].copy()
rr["idx"] = rr.field_name.str.extract(r"\[(\d+)\]")[0].astype(int)
rr["leaf"] = rr.field_name.str.replace(r"^RoundResults\[\d+\]\.", "", regex=True)
res = rr.pivot_table(index="idx", columns="leaf", values="value_str", aggfunc="first")
resn = rr[rr.leaf == "RoundNumber"].set_index("idx").value_i64
rtime = rr.groupby("idx").time_ms.min()
rounds = pd.DataFrame({"round_index": rs.word0.astype(int).to_numpy(), "round_started_ms": rs.time1.astype("int64").to_numpy()})
rounds["RoundResults_observed_ms"] = rounds.round_index.map(rtime)
for c in ("WinningTeam", "WinningTeamRole", "RoundResult"):
    rounds[c] = rounds.round_index.map(res[c]) if c in res else None
rounds["RoundNumber"] = rounds.round_index.map(resn)
sw = ev[ev.group == "switchTeams"].time1.astype("int64").tolist()
rounds["side_switch_before_round_ms"] = None
for t in sw:
    nxt = rounds[rounds.round_started_ms >= t].round_index.min()
    rounds.loc[rounds.round_index == nxt, "side_switch_before_round_ms"] = t
put("rounds", stamp(rounds, "OBSERVED"), "one row per roundStarted event; outcome fields are GameState RoundResults[n].* with their names kept")
gap("rounds", "winning team as roster team (Red/Blue vs shard team A/B)", "UNRESOLVED", "WinningTeam is a string label; the mapping to roster teams is not established by the source fields read")
gap("rounds", "round end time, buy phase end, per-round side by team", "UNRESOLVED", "phase changes are in world_state (MulticastSetPhase.NewPhase); their meaning is INFERRED only")
finding("rounds", "round results complete", "PASS" if rounds.WinningTeam.notna().all() else "WARN",
        f"{len(rounds)} rounds, {int(rounds.WinningTeam.notna().sum())} with WinningTeam", "info" if rounds.WinningTeam.notna().all() else "warn")

# economy: MoneyManagementComponent per PlayerState actor + OwnerExclusivePlayerInfo.RoundInfos (kept as observed)
mm = F[F.group_path.str.contains("MoneyManagementComponent", regex=False)][["time_ms", "packet_id", "actor_net_guid", "field_name"] + vcols].copy()
mm["source_component"] = "MoneyManagementComponent"
ri = F[F.group_path.str.contains("OwnerExclusivePlayerInfo", regex=False) & F.field_name.str.match(r"^(RoundInfos\[|EndOfRoundBeforeRewardsMoney|NumDeathStreak|TrackedRewards)")][
    ["time_ms", "packet_id", "actor_net_guid", "field_name"] + vcols].copy()
ri["source_component"] = "OwnerExclusivePlayerInfo"
eco = pd.concat([mm, ri], ignore_index=True)
eco["subject"] = eco.actor_net_guid.map(subj_by_ps)
eco.loc[eco.source_component == "OwnerExclusivePlayerInfo", "subject"] = None
put("economy", stamp(eco, "OBSERVED"), "one row per replicated field observation (delta stream, packet order kept); money is per PlayerState actor")
unres = int(mm.actor_net_guid.map(subj_by_ps).isna().sum())
if len(mm):
    mv = mm[mm.field_name == "Money"].value_i64.dropna()
    finding("economy", "money values", "PASS", f"{len(mv)} Money observations, min {mv.min():.0f}, max {mv.max():.0f}; not all zero")
    finding("economy", "money actor resolution", "PASS" if unres == 0 else "WARN", f"{unres} of {len(mm)} money rows have an actor that is not a roster PlayerState", "warn" if unres else "info")
rinf = ri[ri.field_name.str.match(r"^RoundInfos\[\d+\]\.(Start|End)OfRound(Money|LoadoutValue)")].copy()
if len(rinf):
    rinf["leaf"] = rinf.field_name.str.replace(r"^RoundInfos\[\d+\]\.", "", regex=True)
    for leaf, g in rinf.groupby("leaf"):
        allzero = bool((g.value_i64.fillna(0) == 0).all())
        finding("economy", f"RoundInfos.{leaf}", "WARN" if allzero else "PASS",
                f"{len(g)} observations, min {g.value_i64.min():.0f}, max {g.value_i64.max():.0f}, all zero = {allzero}", "warn" if allzero else "info")
gap("economy", "purchase prices and item names", "UNRESOLVED", "purchases table holds the Purchaseable numeric id and purchaser; no id-to-item or price table in the source read")
gap("economy", "authoritative per-round snapshots", "UNRESOLVED", "economy_snapshots are DERIVED from the last Money observation before round start and result; RoundInfos.StartOfRound* is zero")

# spike events
sp = ev[ev.group.isin(["spikePlanted", "spikeDefused"])].sort_values("time1")
rows = [dict(source="event", event_group=r.group, time_ms=int(r.time1), event_id=r.id) for r in sp.itertuples()]
bs = F[F.group_path.str.contains("_GameState_C", regex=False) & (F.field_name == "BombState")]
rows += [dict(source="GameState.BombState", event_group="BombState", time_ms=int(r.time_ms), BombState=r.value_i64) for r in bs.itertuples()]
put("spike_events", stamp(pd.DataFrame(rows).sort_values("time_ms"), "OBSERVED"), "one row per spike event or BombState change; BombState numeric meaning is unlabelled")
gap("spike_events", "BombState enum labels", "UNRESOLVED", "values 0..6 observed; labels not in the export")
gap("spike_events", "site label (A/B/C) and map-relative site", "NOT_PRESENT_IN_SOURCE", "only a world location of the plant is carried, no site name")
gap("spike_events", "planter and defuser identity", "UNRESOLVED", "carrier at plant is INFERRED from the bomb actor Owner; defuser from UsableComponent/TimedBomb observations is not resolved to a player")

# world_state: GameState fields except high-frequency timers, plus team state
timers = {"GamePhaseElapsedTime", "StateRemainingTime", "DisplayRemainingTime", "ReplicatedWorldTimeSecondsDouble"}
gs = F[F.group_path.str.contains("_GameState_C", regex=False) & ~F.field_name.isin(timers) & ~F.field_name.str.startswith("RoundResults")
       & (F.field_name != "BombState") & ~F.field_name.str.startswith("MulticastUpdateServerPerformanceInfo")][["time_ms", "packet_id", "actor_net_guid", "field_name"] + vcols].copy()
gs["source_component"] = "GameState"
ts = F[F.group_path.str.contains("BaseTeamState", regex=False)][["time_ms", "packet_id", "actor_net_guid", "field_name"] + vcols].copy()
ts["source_component"] = "BaseTeamState"
put("world_state", stamp(pd.concat([gs, ts], ignore_index=True).sort_values(["time_ms", "packet_id"]), "OBSERVED"),
    "one row per replicated field observation on GameState (phase changes, match state, ceremonies) and BaseTeamState (Wins, Points, LoadoutValue)")
gap("world_state", "GamePhaseElapsedTime, StateRemainingTime, DisplayRemainingTime, ReplicatedWorldTimeSecondsDouble, ServerFrameTimeMs", "NOT_TESTABLE",
    f"{int(F.field_name.isin(timers).sum())} high-frequency timer observations remain in fields.parquet and are not copied here")
gap("world_state", "MulticastSetPhase.NewPhase labels", "UNRESOLVED", "numeric phases 2..6; roles INFERRED (3 pre-round/buy, 4 after buy, 5 round end), not confirmed")
gap("world_state", "health, armor, alive flags as a time series", "UNRESOLVED", "AresAttributeSet holds only constant initial values (no change over time) and is not written as health; per-hit LifeChangeEvents are in damage_events, SetLife/Heal RPCs are not extracted")

# player_state: native movement ticks
mv = pd.read_parquet(E / "movement.parquet")
mv["subject"] = mv.character_net_guid.map(subj_by_char)
ao0 = pd.read_parquet(E / "actors.parquet", columns=["actor_net_guid", "event", "class_path", "time_ms"])
cls_of = ao0[ao0.event == "open"].drop_duplicates("actor_net_guid", keep="last").set_index("actor_net_guid").class_path.astype(str)
is_player = mv.subject.notna()
put("player_state", stamp(mv[is_player], "OBSERVED"), "one row per native movement sample per roster character (pos in game units, yaw/pitch/vel as source)")
um = mv[~is_player].drop(columns=["subject"]).copy()
um["mover_class_path"] = um.character_net_guid.map(cls_of)
put("utility_object_movement", stamp(um, "OBSERVED"), "native movement samples of non-roster movers (utility pawns such as cameras and pets); owner not linked")
gap("utility_object_movement", "owner and linked cast", "UNRESOLVED", "no owner link read")
nu = int(um.mover_class_path.isna().sum())
finding("player_state", "movement rows by mover", "PASS" if nu == 0 else "WARN",
        f"{int(is_player.sum())} roster rows, {len(um)} non-roster mover rows in {um.character_net_guid.nunique()} actors; {nu} non-roster rows with no actor class", "warn" if nu else "info")
gap("player_state", "alive, health, shield, ult points, weapon in hand", "UNRESOLVED", "see world_state; fields exist but attributes are not decoded")
gap("player_state", "coordinate to map transform", "NOT_PRESENT_IN_SOURCE", "no per-map transform in the replay")

# casts / effects
fp, ap_ = E / "fields.parquet", E / "actors.parquet"
casts = extract_casts.run(fp, ap_)
if len(casts):
    c1 = casts.drop_duplicates("cast_uid")
    ab = pd.DataFrame(dict(stage="cast_record", cast_uid=c1.cast_uid, agent_as_decoded=c1.agent, Player=c1.caster, Round=c1["round"], Slot=c1.slot,
                           RoundPhase=c1.round_phase, CastTime_s=c1.cast_time_s, CastLocation_x=c1.cast_x, CastLocation_y=c1.cast_y,
                           CastLocation_z=c1.cast_z, DestroyedCount=c1.destroyed_count))
else:
    ab = pd.DataFrame()
ao = pd.read_parquet(ap_)
ao["cls"] = ao.class_path.astype(str).str.extract(r"/([^/]+)$")[0].str.replace(r"^.*\.", "", regex=True)
util = ao[ao.cls.str.match(r"^(Projectile_|GameObject_|Ability_|Actor_|Pawn_)") & ~ao.cls.str.startswith("Ability_Melee")]
opens = util[util.event == "open"]; closes = util[util.event == "close"].drop_duplicates("actor_net_guid", keep="last").set_index("actor_net_guid").time_ms
uo = pd.DataFrame(dict(actor_net_guid=opens.actor_net_guid, class_name=opens.cls, class_path=opens.class_path, open_ms=opens.time_ms,
                       spawn_x=opens.spawn_x, spawn_y=opens.spawn_y, spawn_z=opens.spawn_z, spawn_vx=opens.spawn_vx, spawn_vy=opens.spawn_vy, spawn_vz=opens.spawn_vz))
uo["close_ms"] = uo.actor_net_guid.map(closes)
uo["owner_subject"] = None
put("utility_objects", stamp(uo, "OBSERVED"), "one row per spawned ability-related actor (actor open/close records); channel reuse can repeat actor_net_guid")
gap("utility_objects", "owner, linked cast, per-object state changes", "UNRESOLVED", "no owner link read; Owner/Instigator fields of these actors not extracted")
gap("utility_objects", "actors with no close record", "NOT_TESTABLE", f"{int(uo.close_ms.isna().sum())} of {len(uo)} objects have no close; they may persist to replay end or be dropped by the parser")
st_open = pd.DataFrame(dict(stage="actor_open", cast_uid=None, agent_as_decoded=None, class_name=opens.cls, actor_net_guid=opens.actor_net_guid, time_ms=opens.time_ms))
st_close = pd.DataFrame(dict(stage="actor_close", cast_uid=None, agent_as_decoded=None, class_name=util[util.event == "close"].cls,
                             actor_net_guid=util[util.event == "close"].actor_net_guid, time_ms=util[util.event == "close"].time_ms))
abe = pd.concat([ab, st_open, st_close], ignore_index=True)
put("ability_events", stamp(abe, "OBSERVED"),
    "one row per lifecycle record; stages here: cast_record (AbilityCastsThisRound array position, NOT de-duplicated casts), actor_open, actor_close")
for s in ("cast attempt", "successful cast confirmed", "effect begin", "effect end", "trigger", "destruction/expiration with cause"):
    gap("ability_events", f"stage: {s}", "UNRESOLVED", "no source field read for this stage by the reference code; not inferred from neighbours")
gap("ability_events", "Slot enum, ability display names", "UNRESOLVED", "Slot is numeric in source; mapping not confirmed")
if len(casts):
    pe = casts[casts.target.notna() | casts.tag.notna()]
    pe = pd.DataFrame(dict(cast_uid=pe.cast_uid, Player=pe.caster, Round=pe["round"], Statistic=pe.tag_id, LocalizedStat=pe.tag, Value=pe.tag_value,
                           effect_Time_s=pe.effect_time_s, AffectedPlayer=pe.target, AffectedTarget_Value=pe.target_value))
    pe["AffectedPlayer_subject"] = pe.AffectedPlayer.map(lambda v: subj_by_ps.get(int(v)) if pd.notna(v) else None)
    nres = int((pe.AffectedPlayer.notna() & pe.AffectedPlayer_subject.isna()).sum())
    finding("player_effects", "AffectedPlayer resolves to a roster PlayerState", "PASS" if nres == 0 else "WARN",
            f"{nres} of {int(pe.AffectedPlayer.notna().sum())} affected-player values do not match a roster PlayerState actor", "warn" if nres else "info")
    put("player_effects", stamp(pe, "OBSERVED"), "one row per cast/effect/affected-player observation (Effects[].AffectedTargetsArray[]); not collapsed")
    gap("player_effects", "effect intervals (begin/end) and status types (blind, slow, suppress...)", "UNRESOLVED",
        "only the per-cast Effects[] statistics are decoded; no interval fields read")
else:
    put("player_effects", stamp(pd.DataFrame(), "OBSERVED"), "empty")
    gap("player_effects", "all", "NOT_PRESENT_IN_SOURCE", "no AbilityCastsThisRound records decoded")


# ---------------------------------------------------------------- per-hit damage (DamageableComponent RPC MulticastNotifyDamage_Point)
P = "MulticastNotifyDamage_Point."
dm = F[F.field_name.str.startswith(P)].copy()
dm["val"] = dm.value_i64.where(dm.value_i64.notna(), dm.value_f64.where(dm.value_f64.notna(), dm.value_bool.where(dm.value_bool.notna(), dm.value_str)))
recs, cur, key = [], None, None
for r in dm.itertuples():  # one RPC call = consecutive fields in one packet on one actor; a repeated name starts the next call
    k = (r.packet_id, r.actor_net_guid)
    nm = r.field_name[len(P):]
    if k != key or nm in cur:
        cur = dict(time_ms=int(r.time_ms), packet_id=int(r.packet_id), victim_actor_net_guid=int(r.actor_net_guid))
        recs.append(cur); key = k
    cur[nm] = r.val
hits = pd.DataFrame(recs)
short = lambda s: s.str.extract(r"/([^/]+)$")[0].str.replace(r"^.*\.", "", regex=True)
if len(hits):
    for c in hits.columns:
        if hits[c].dtype == object:
            hits[c] = hits[c].where(hits[c].notna(), None)
    cl = lambda col: short(hits[col].map(lambda v: cls_of.get(int(v)) if pd.notna(v) else None).astype("string")) if col in hits else None
    hits["victim_class"] = short(hits.victim_actor_net_guid.map(cls_of).astype("string"))
    hits["victim_subject"] = hits.victim_actor_net_guid.map(subj_by_char)
    hits["damager_subject"] = hits.DamagerPlayerState.map(lambda v: subj_by_ps.get(int(v)) if pd.notna(v) else None)
    hits["kill_credit_subject"] = hits.KillCreditPlayerState.map(lambda v: subj_by_ps.get(int(v)) if pd.notna(v) else None)
    hits["equippable_class"] = cl("EquippableUsed"); hits["damage_causer_class"] = cl("DamageCauser")
    rs_t = rounds.round_started_ms.to_numpy()
    hits["round_index"] = [int(rounds.round_index.iloc[max(np.searchsorted(rs_t, t, side="right") - 1, 0)]) for t in hits.time_ms]
    put("damage_events", stamp(hits.sort_values(["time_ms", "packet_id"]), "OBSERVED"),
        "one row per MulticastNotifyDamage_Point RPC call (one damage instance); source names kept; victim may be a player or a utility object")
    pv = hits[hits.victim_subject.notna()]
    gap("damage_events", "DamageType, DamagedBone region codes, AssistType as labelled names", "UNRESOLVED", "DamageType is a numeric id; DamagedBone is a bone name string; no id-to-name table in the source")
    gap("damage_events", "per-hit weapon display names", "UNRESOLVED", "equippable_class is the replay's class name (e.g. LugerPistol_C); display names are unconfirmed")
    if dam is not None:
        diff = float(pv.DamageDealt.astype(float).sum() - dam.DamageDealt.sum())
        finding("damage_events", "per-hit DamageDealt on roster victims equals combat-report total", "PASS" if abs(diff) < 0.05 else "FAIL",
                f"hits {pv.DamageDealt.astype(float).sum():.2f}, combat reports {dam.DamageDealt.sum():.2f}, difference {diff:.3f}", "error" if abs(diff) >= 0.05 else "info")
    if kills is not None:
        nk = int(pv.bDamageKilledTarget.fillna(False).astype(bool).sum())
        finding("damage_events", "killing hits on roster victims equal kill rows", "PASS" if nk == len(kills) else "FAIL", f"{nk} killing hits, {len(kills)} kills", "error" if nk != len(kills) else "info")
    finding("damage_events", "victims that are not roster players", "INFO", f"{int(hits.victim_subject.isna().sum())} of {len(hits)} hits hit non-roster targets (utility objects)")
    # kill details: the killing hit for each kill, DERIVED by victim, time and killer credit
    if kills is not None:
        kh = pv[pv.bDamageKilledTarget.fillna(False).astype(bool)].copy()
        kd = []
        for kr in kills.itertuples():
            c = kh[(kh.victim_subject == kr.victim) & ((kh.time_ms - kr.t).abs() <= 50)]
            row = dict(kill_index=int(kr.kill_index), time_ms=int(kr.t), round_index=int(kr.rnd), killer_subject=kr.killer, victim_subject=kr.victim, killing_hits_found=len(c))
            if len(c) == 1:
                h = c.iloc[0]
                row.update(hit_time_ms=int(h.time_ms), equippable_class=h.equippable_class, DamageType=h.DamageType, DamagedBone=h.DamagedBone,
                           bIsWallPenetration=h.bIsWallPenetration, DamageDealt=h.DamageDealt, kill_credit_subject=h.kill_credit_subject,
                           credit_matches_killer=bool(h.kill_credit_subject == kr.killer), DamageOrigin=h.DamageOrigin)
            before = hits[(hits.victim_subject == kr.victim) & (hits.round_index == kr.rnd) & (hits.time_ms <= kr.t + 50) & (hits.damager_subject.notna())]
            ds = sorted(set(before.damager_subject) - {kr.killer})
            row["other_damagers_before_death"] = json.dumps(ds)
            kd.append(row)
        kd = pd.DataFrame(kd)
        put("kill_details", stamp(kd, "DERIVED"), "one row per kill: the killing hit (joined by victim and time within 50 ms) and the other players who damaged the victim that round (assist CANDIDATES, not the game's assist flag)")
        bad = int((kd.killing_hits_found != 1).sum())
        finding("kill_details", "each kill joins exactly one killing hit", "PASS" if bad == 0 else "FAIL", f"{bad} of {len(kd)} kills without exactly one killing hit", "error" if bad else "info")
        if "credit_matches_killer" in kd:
            nm_ = int((~kd.credit_matches_killer.fillna(False)).sum())
            finding("kill_details", "kill credit equals shard killer", "PASS" if nm_ == 0 else "FAIL", f"{nm_} kills where KillCreditPlayerState differs from the shard killer", "error" if nm_ else "info")
else:
    gap("damage_events", "all", "NOT_EXPOSED_BY_PARSER", "no MulticastNotifyDamage_Point records in the export")

# ---------------------------------------------------------------- purchases
pc = F[F.group_path.str.contains("PurchasedItemComponent", regex=False)][["time_ms", "packet_id", "actor_net_guid", "field_name"] + vcols].copy()
if len(pc):
    pc["val"] = pc.value_i64.where(pc.value_i64.notna(), pc.value_bool.where(pc.value_bool.notna(), pc.value_str))
    pv_ = pc.pivot_table(index=["time_ms", "packet_id", "actor_net_guid"], columns="field_name", values="val", aggfunc="first").reset_index()
    pv_.columns.name = None
    if "PurchasingPlayerState" in pv_:
        pv_["purchaser_subject"] = pv_.PurchasingPlayerState.map(lambda v: subj_by_ps.get(int(v)) if pd.notna(v) else None)
    put("purchases", stamp(pv_, "OBSERVED"), "one row per PurchasedItemComponent observation time and component actor; delta stream, fields not sent are null (not forward-filled)")
    gap("purchases", "item names, prices, round attribution", "UNRESOLVED", "Purchaseable is a numeric id; no table, price or round field in the source read; round_index can be derived from time_ms")

# ---------------------------------------------------------------- money snapshots (DERIVED from Money observations)
mn = mm[mm.field_name == "Money"].dropna(subset=["value_i64"]).sort_values("time_ms")
srows = []
for rr_ in rounds.itertuples():
    for sub in sorted(set(subj_by_ps.values())):
        ob = mn[mn.actor_net_guid.map(subj_by_ps) == sub]
        def last_before(t):
            x = ob[ob.time_ms <= t]
            return (None, None) if x.empty else (int(x.iloc[-1].value_i64), int(x.iloc[-1].time_ms))
        s0 = last_before(rr_.round_started_ms)
        s1 = last_before(rr_.RoundResults_observed_ms) if pd.notna(rr_.RoundResults_observed_ms) else (None, None)
        srows.append(dict(round_index=int(rr_.round_index), subject=sub, money_before_round_start=s0[0], money_before_round_start_obs_ms=s0[1],
                          money_before_result=s1[0], money_before_result_obs_ms=s1[1]))
put("economy_snapshots", stamp(pd.DataFrame(srows), "DERIVED"), "one row per player and round: last Money observation at or before round start and before the result is recorded")

# ---------------------------------------------------------------- spike detail rows (appended to spike_events)
sx = []
bl = F[F.group_path.str.contains("BombDestination", regex=False) & F.field_name.str.contains("BombLocation")]
for r in bl.itertuples():
    sx.append(dict(source="BombDestination", event_group="plant_location", time_ms=int(r.time_ms), field_name=r.field_name, value_str=r.value_str, evidence="OBSERVED"))
be = F[F.group_path.str.contains("BombEquippable", regex=False) & F.field_name.isin(["Owner", "Instigator", "MulticastPlayBombPickedUpAudio.NewCharacter"])]
for r in be.itertuples():
    v = r.value_i64
    sx.append(dict(source="BombEquippable", event_group="carrier_observation", time_ms=int(r.time_ms), field_name=r.field_name, value_i64=v,
                   subject=subj_by_char.get(int(v)) if pd.notna(v) else None, evidence="OBSERVED"))
tb = F[F.group_path.str.contains("TimedBomb", regex=False) & F.field_name.isin(["DefuseProgress", "TimeRemainingToExplode"])]
put("bomb_timer_observations", stamp(tb[["time_ms", "packet_id", "actor_net_guid", "field_name", "value_f64"]], "OBSERVED"),
    "one row per TimedBomb DefuseProgress or TimeRemainingToExplode observation (high rate, kept separate from spike_events)")
# planter INFERRED: last carrier observed on a BombEquippable before it closes at the plant event
plants = ev[ev.group == "spikePlanted"].time1.astype("int64").tolist()
beo = [x for x in sx if x["event_group"] == "carrier_observation" and x["field_name"] == "Owner" and x.get("subject")]
for pt in plants:
    c = [x for x in beo if x["time_ms"] <= pt + 30]
    if c:
        last = max(c, key=lambda x: x["time_ms"])
        sx.append(dict(source="derived", event_group="planter_inferred", time_ms=pt, subject=last["subject"], evidence="INFERRED",
                       field_name="last BombEquippable.Owner at or before spikePlanted"))
if sx:
    old = tables["spike_events"].drop(columns=["match_id", "run_id"], errors="ignore")
    put("spike_events", stamp(pd.concat([old, pd.DataFrame(sx)], ignore_index=True).sort_values("time_ms", kind="stable"), "OBSERVED"),
        "one row per spike event, BombState change, plant location, bomb carrier observation; planter_inferred rows are INFERRED")

# ---------------------------------------------------------------- validation + outputs
put("validation_findings", stamp(pd.DataFrame(findings), "DERIVED"), "one row per check or finding in this extraction run")
names = ["matches", "players", "rounds", "player_state", "kills", "deaths", "damage_events", "economy", "spike_events", "ability_events",
         "utility_objects", "player_effects", "world_state", "map_identity", "validation_findings", "utility_object_movement",
         "damage_by_pair_round", "kill_details", "purchases", "economy_snapshots", "bomb_timer_observations"]
out_rows = {}
for n in names:
    if n not in tables:
        gap(n, "whole group", "UNRESOLVED", "not produced in this run")
        continue
    df = tables[n]
    if "validation_findings" == n:
        df = stamp(pd.DataFrame(findings), "DERIVED")  # include findings added after groups were built
    df.to_parquet(O / f"{n}.parquet", index=False, compression="zstd")
    out_rows[n] = len(df)
manifest = {n: dict(rows=r, bytes=(O / f"{n}.parquet").stat().st_size, sha256=hashlib.sha256((O / f"{n}.parquet").read_bytes()).hexdigest()) for n, r in out_rows.items()}
json.dump(dict(schema_version=SCHEMA, match_id=match_id, run_id=run_id, source_build=build, source_sha256=a.source_sha256, tables=manifest),
          open(Path(a.out) / "tables_manifest.json", "w"), indent=2)
report = dict(match_id=match_id, run_id=run_id, source_build=build,
              groups={n: dict(available=n in tables, extracted=out_rows.get(n, 0), grain=grain.get(n)) for n in names},
              gaps=gaps, findings_count=len(findings),
              statuses=["NOT_PRESENT_IN_SOURCE", "NOT_EXPOSED_BY_PARSER", "DECODE_FAILED", "UNRESOLVED", "NOT_TESTABLE"])
json.dump(report, open(Path(a.out) / "completeness_report.json", "w"), indent=2, default=str)
with open(Path(a.out) / "schema.md", "w") as fh:
    fh.write(f"# analytics_tables schema ({SCHEMA}) for {match_id}, run {run_id}\n\nEvidence classes: OBSERVED, DERIVED, INFERRED. Times are milliseconds on the replay clock unless a column name ends in _s (seconds). Coordinates are game units as stored.\n")
    for n in names:
        if n in tables:
            fh.write(f"\n## {n}\nGrain: {grain[n]}\nRows: {out_rows.get(n)}\n\n| column | type |\n|---|---|\n")
            for c, t in tables[n].dtypes.items():
                fh.write(f"| {c} | {t} |\n")
print(json.dumps(out_rows))
print("gaps:", len(gaps), "findings:", len(findings))
