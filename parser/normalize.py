#!/usr/bin/env python3
"""Normalization layer: ONE vrfkit export folder -> linked, provenance-stamped parquet tables (schema norm-1).

usage: normalize.py EXPORT_DIR OUT_DIR [--config pipeline_config.json] [--source-sha256 HEX] [--run-id ID]
                    [--codenames JSON] [--map-registry JSON]

Consumes the raw export (manifest, events, actors, net_guids, fields, movement). It never re-parses the .vrf.
Principles (docs/DATA_CONTRACT.md):
  * Raw observations are kept; interpretations live in separate tables or columns with an evidence class.
  * evidence: OBSERVED (read from one source record) | DERIVED (computed from several) | INFERRED (a reading that needs
    confirmation) | HYPOTHESIZED. resolution_status says whether identities/links resolved; nothing unresolved is dropped
    or guessed, it is written to an unresolved_* table.
  * Nothing here fails because one actor/player/event does not resolve. A step that raises is recorded in
    parser_diagnostics.json and its tables are written empty with their documented schema and a coverage status.
  * No tactical conclusions, no performance scores, no map regions, no invented coordinate transforms.
"""
import argparse, hashlib, json, re, sys, time, traceback
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "skill"))
SCHEMA = "norm-1"
STD = ["match_id", "record_id", "source_file", "source_table", "source_ref", "transformation", "evidence", "resolution_status"]

# ---------------------------------------------------------------------------------------------------- documented schemas
S = {
 "players": ["player_id", "playerstate_actor_net_guid", "character_net_guids", "controller_net_guids", "team_id", "team_basis", "agent_code", "agent_name", "agent_class_guid", "characterId", "display_name", "name_status"],
 "teams": ["team_id", "n_players", "player_ids", "team_basis", "first_half_side", "side_status"],
 "agents": ["agent_code", "agent_name", "name_status", "player_id", "character_net_guid", "class_path"],
 "actors": ["actor_instance_id", "actor_net_guid", "instance_seq", "channel_index", "class_path", "class_name", "actor_kind", "open_ms", "close_ms", "open_packet_id", "close_packet_id", "spawn_x", "spawn_y", "spawn_z", "round_index_at_open", "round_ms_at_open", "player_id", "owner_player_id"],
 "actor_lifecycle": ["actor_instance_id", "actor_net_guid", "event", "time_ms", "packet_id", "channel_index", "class_path", "round_index", "round_ms"],
 "netguid_mappings": ["net_guid", "path", "outer_net_guid", "outer_path", "full_path"],
 "actor_ownership_intervals": ["actor_instance_id", "actor_net_guid", "actor_class", "relation", "target_net_guid", "target_instance_id", "target_class", "target_player_id", "start_ms", "end_ms", "end_reason", "start_round_index", "start_round_ms", "player_id", "packet_id", "channel_index"],
 "identity_crosswalk": ["player_id", "id_space", "id_value", "valid_from_ms", "valid_to_ms", "note"],
 "roster": ["player_id", "round_index", "team_id", "agent_code", "agent_name", "half_index", "sides_swapped_vs_first_half", "side", "side_status"],
 "unresolved_identities": ["subject_kind", "net_guid", "class_path", "first_seen_ms", "n_records", "reason", "needed_to_resolve"],
 "map_metadata": ["replay_id", "map_code", "level_path", "level_time_ms", "map_name", "internal_asset_id", "id_source", "map_identity_status", "geometry_status", "map_reference_package"],
 "coordinate_systems": ["coordinate_system_id", "units", "units_basis", "origin", "axes", "elevation_axis", "handedness", "space", "angle_units", "transformations_applied", "status"],
 "movement": ["time_ms", "packet_id", "tick", "mover_net_guid", "actor_instance_id", "pos_x", "pos_y", "pos_z", "yaw", "pitch", "vel_x", "vel_y", "vel_z", "timestamp", "movement_state", "move_type", "round_index", "round_ms", "mover_kind", "player_id", "map_code", "coordinate_system_id", "position_source"],
 "player_positions": ["player_id", "team_id", "agent_code", "round_index", "round_ms", "time_ms", "mover_net_guid", "pos_x", "pos_y", "pos_z", "yaw", "pitch", "dt_ms", "dx", "dy", "dz", "step_xy", "step_xyz", "speed_xy_per_s", "speed_xyz_per_s", "dyaw", "dpitch", "movement_row_ref", "map_code", "coordinate_system_id", "derived_valid"],
 "position_coverage": ["scope", "player_id", "round_index", "mover_net_guid", "n_samples", "first_ms", "last_ms", "span_ms", "median_dt_ms", "p95_dt_ms", "max_gap_ms", "n_gaps_over_threshold", "gap_threshold_ms", "coverage_basis", "round_start_ms", "round_end_ms", "n_zero_dt", "fraction_attributed"],
 "position_anomalies": ["anomaly", "player_id", "round_index", "time_ms", "mover_net_guid", "value", "threshold", "movement_row_ref"],
 "rounds": ["round_index", "round_started_ms", "round_end_ms", "round_end_basis", "buy_end_ms", "buy_end_basis", "half_index", "side_switch_before_round_ms", "winning_team_label", "winning_team_role", "round_result", "round_number", "winner_team_id", "winner_status"],
 "events": ["event_id", "event_group", "event_name", "time_ms", "time2_ms", "round_index", "round_ms", "tick", "packet_id", "channel_index", "event_sequence", "payload_tag", "word0", "word1", "actor_guid", "object_guid", "instigator", "target", "related_field_rows", "source_event_row"],
 "event_payloads": ["event_id", "payload_size", "payload_tag", "payload_name", "payload_seconds", "word0", "word1", "raw_payload_hex", "interpretation", "interpretation_status"],
 "replicated_fields": ["field_row", "time_ms", "packet_id", "channel_index", "actor_net_guid", "actor_instance_id", "object_net_guid", "group_path", "field_name", "value", "value_type", "pattern_group", "round_index", "round_ms"],
 "round_boundaries": ["round_index", "boundary", "time_ms", "basis", "value"],
 "spike_events": ["event_type", "time_ms", "round_index", "round_ms", "subject_player_id", "subject_net_guid", "value", "site", "location_x", "location_y", "location_z", "basis"],
 "ability_casts": ["cast_id", "cast_uid_first", "player_id", "agent_code", "agent_name", "round_index", "slot", "ability_id", "ability_name", "round_phase", "cast_time_s", "barrier_ms", "cast_abs_ms", "time_basis", "cast_x", "cast_y", "cast_z", "destroyed_count", "n_effect_records", "cast_status", "replicator_actor_net_guid"],
 "utility_objects": ["utility_object_id", "actor_instance_id", "actor_net_guid", "class_name", "class_path", "object_role", "agent_code_from_class", "slot_token", "open_ms", "close_ms", "round_index", "spawn_x", "spawn_y", "spawn_z", "spawn_vx", "spawn_vy", "spawn_vz", "owner_net_guid", "owner_player_id", "owner_basis", "candidate_cast_ids", "cast_id", "n_movement_rows"],
 "utility_object_observations": ["utility_object_id", "actor_net_guid", "observation", "time_ms", "round_index", "round_ms", "pos_x", "pos_y", "pos_z", "yaw", "pitch", "vel_x", "vel_y", "vel_z", "movement_row_ref"],
 "utility_lifecycle_events": ["lifecycle_event_id", "stage", "time_ms", "round_index", "round_ms", "player_id", "agent_code", "cast_id", "utility_object_id", "actor_net_guid", "target_player_id", "target_net_guid", "value", "detail", "pos_x", "pos_y", "pos_z"],
 "utility_effects": ["effect_id", "cast_id", "player_id", "agent_code", "round_index", "effect_idx", "statistic", "effect_category", "statistic_id", "value", "effect_time_s", "n_targets", "sum_target_value", "effect_status"],
 "utility_targets": ["target_id", "effect_id", "cast_id", "target_player_state_guid", "target_player_id", "target_team_id", "caster_team_id", "relation_to_caster", "target_value", "target_idx", "target_status"],
 "utility_statistics": ["field_row", "time_ms", "packet_id", "channel_index", "actor_net_guid", "object_net_guid", "group_path", "serialized_field_name", "field_leaf", "array_path", "value", "value_type", "round_index", "player_id", "ability_slot", "stat_kind", "resets_by_round", "cumulative", "counter_delta", "delta_status"],
 "utility_statistic_reconciliation": ["check", "player_id", "round_index", "statistic", "observed_a", "observed_b", "difference", "status", "detail"],
 "unresolved_utility_records": ["record_type", "ref_id", "time_ms", "round_index", "reason", "needed_to_resolve"],
 "combat_events": ["combat_event_id", "event_type", "time_ms", "round_index", "round_ms", "actor_player_id", "target_player_id", "actor_net_guid", "target_net_guid", "source_kind", "source_class", "amount", "damage_event_id", "death_event_id", "kill_ledger_id", "attribution_status"],
 "damage_events": ["damage_event_id", "time_ms", "packet_id", "channel_index", "victim_actor_net_guid", "victim_class", "victim_player_id", "damager_player_id", "kill_credit_player_id", "damage_dealt", "damage_taken", "killed_target", "alive_after", "damage_type", "damaged_bone", "regional_damage", "is_wall_penetration", "equippable_class", "damage_causer_class", "damage_causer_net_guid", "damage_origin", "assists_list", "kills_for_killer", "kills_for_victim", "round_index", "round_ms", "source_kind", "fields_row_first"],
 "kill_death_ledger": ["kill_ledger_id", "death_event_id", "damage_event_id", "time_ms", "round_index", "killer_player_id", "victim_player_id", "killer_char_guid", "victim_char_guid", "killer_basis", "victim_basis", "killer_credit_player_id", "assist_candidate_player_ids", "assist_list_raw", "source_kind", "weapon_class", "attribution_status", "match_gap_ms"],
 "combat_reconciliation": ["check", "scope", "round_index", "expected", "observed", "difference", "status", "detail"],
 "normalized_match": ["table", "rows", "coverage_status", "note"],
 "map_position_index": ["map_code", "player_id", "round_index", "team_id", "mover_net_guid", "n_rows", "first_ms", "last_ms", "pos_row_start", "pos_row_end", "source_table"],
 "utility_lifecycle_index": ["player_id", "round_index", "cast_id", "utility_object_id", "lifecycle_event_id", "stage", "effect_id", "target_id", "target_player_id", "time_ms"],
 "event_provenance_index": ["table", "record_id", "source_file", "source_table", "source_ref", "original_time_ms", "original_actor_ids", "transformation", "evidence", "resolution_status"],
}
GAP = {}  # table -> (code, note) for tables that stay empty because the export lacks evidence


class Ctx:
    pass


def hexes(b):
    return b.hex() if isinstance(b, (bytes, bytearray)) else None


def coalesce(df):
    v = df["value_str"].astype(object)
    for c in ("value_f64", "value_i64", "value_bool"):
        v = v.where(v.notna(), df[c].astype(object))
    return v


def vtype(df):
    t = pd.Series(None, index=df.index, dtype=object)
    for c, n in (("value_bool", "bool"), ("value_i64", "int"), ("value_f64", "float"), ("value_str", "str")):
        t = t.where(~(df[c].notna() & t.isna()), n)
    return t


def short_class(p):
    if p is None or (isinstance(p, float) and np.isnan(p)):
        return None
    s = str(p).rstrip("/").split("/")[-1]
    return s.split(".")[-1]


def run(export, out, cfg=None, source_sha256=None, run_id=None, codenames=None, map_registry=None):
    t0 = time.time()
    E, O = Path(export), Path(out)
    O.mkdir(parents=True, exist_ok=True)
    cfg = cfg or json.load(open(HERE / "pipeline_config.json"))
    NC = cfg["normalize"]
    man = json.load(open(E / "manifest.json"))
    match_id = man.get("friendly_name") or E.parent.name
    m8 = str(match_id)[:8]
    run_id = run_id or f"{m8}-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}"
    diag = dict(schema_version=SCHEMA, match_id=match_id, run_id=run_id, source_build=man.get("replay_build"),
                source_sha256=source_sha256, steps={}, gaps=[], checks=[], notes=[])
    T = {}
    C = Ctx()

    def check(name, status, detail, level="info"):
        diag["checks"].append(dict(check=name, status=status, level=level, detail=detail))

    def gap(table, code, note):
        diag["gaps"].append(dict(table=table, code=code, note=note))

    def emit(name, df, source_file, source_table, transformation, evidence, status="RESOLVED", id_col=None):
        """Stamp standard provenance columns, keep documented columns even when empty."""
        df = df.reset_index(drop=True).copy()
        for c in df.columns:
            if isinstance(df[c].dtype, pd.CategoricalDtype):
                df[c] = df[c].astype(object)
        if len(df) == 0:
            df = pd.DataFrame({c: pd.Series(dtype=object) for c in S.get(name, [])})
        df.insert(0, "match_id", match_id)
        df.insert(1, "record_id", [f"{m8}:{name}:{i:07d}" for i in range(len(df))])
        if "source_ref" not in df:
            df["source_ref"] = None
        for k, v in (("source_file", source_file), ("source_table", source_table), ("transformation", transformation)):
            if k not in df:
                df[k] = v
        if "evidence" not in df:
            df["evidence"] = evidence
        else:
            df["evidence"] = df["evidence"].fillna(evidence)
        if "resolution_status" not in df:
            df["resolution_status"] = status
        else:
            df["resolution_status"] = df["resolution_status"].fillna(status)
        want = [c for c in S.get(name, []) if c not in df.columns]
        for c in want:
            df[c] = None
        rest = [c for c in df.columns if c not in STD and c not in S.get(name, [])]
        T[name] = df[["match_id", "record_id"] + S.get(name, []) + rest + [c for c in STD[2:]]]
        dups = T[name].columns[T[name].columns.duplicated()].tolist()
        if dups:
            diag["notes"].append(f"{name}: duplicate columns {dups} dropped")
            T[name] = T[name].loc[:, ~T[name].columns.duplicated()]
        return T[name]

    def step(name):
        def deco(fn):
            ts = time.time()
            try:
                fn()
                diag["steps"][name] = dict(ok=True, secs=round(time.time() - ts, 1))
            except Exception:
                diag["steps"][name] = dict(ok=False, secs=round(time.time() - ts, 1), error=traceback.format_exc()[-900:])
            return fn
        return deco

    # ------------------------------------------------------------------------------------------------ load
    ev = pd.read_parquet(E / "events.parquet")
    ev["group"] = ev["group"].astype(str)
    ev = ev.reset_index(drop=True)
    act = pd.read_parquet(E / "actors.parquet").reset_index(drop=True)
    act["class_path"] = act["class_path"].astype(str)
    ng = pd.read_parquet(E / "net_guids.parquet") if (E / "net_guids.parquet").exists() else pd.DataFrame(columns=["net_guid", "path", "outer_net_guid"])
    F = pd.read_parquet(E / "fields.parquet", columns=["time_ms", "packet_id", "channel_index", "actor_net_guid", "object_net_guid", "group_path", "field_name",
                                                       "value_i64", "value_f64", "value_bool", "value_str"])
    F["group_path"] = F["group_path"].astype(str)
    F["field_name"] = F["field_name"].astype(str)
    mv = pd.read_parquet(E / "movement.parquet").reset_index(drop=True)
    mv["_row"] = np.arange(len(mv))
    roster = pd.DataFrame(man.get("players") or [])
    codes = {}
    cp = Path(codenames) if codenames else HERE / "skill" / "codenames.json"
    if cp.is_file():
        codes = json.load(open(cp)).get("map", {})

    # ------------------------------------------------------------------------------------------------ rounds clock
    rs = ev[ev.group == "roundStarted"].sort_values("time1")
    R_idx = rs.word0.astype(int).to_numpy() if len(rs) else np.array([], dtype=int)
    R_t = rs.time1.astype("int64").to_numpy() if len(rs) else np.array([], dtype="int64")
    C.R_idx, C.R_t = R_idx, R_t

    def round_of(t):
        t = np.asarray(t, dtype="int64")
        if len(R_t) == 0:
            return np.full(t.shape, -1)
        i = np.searchsorted(R_t, t, side="right") - 1
        out_ = np.where(i >= 0, R_idx[np.clip(i, 0, None)], -1)
        return out_

    def round_ms(t):
        t = np.asarray(t, dtype="int64")
        if len(R_t) == 0:
            return np.full(t.shape, -1)
        i = np.searchsorted(R_t, t, side="right") - 1
        return np.where(i >= 0, t - R_t[np.clip(i, 0, None)], -1)

    C.round_of, C.round_ms = round_of, round_ms

    # ------------------------------------------------------------------------------------------------ actors with instance ids
    opens = act[act.event == "open"].sort_values(["time_ms", "packet_id"]).copy()
    closes = act[act.event == "close"].sort_values(["time_ms", "packet_id"]).copy()
    opens["instance_seq"] = opens.groupby("actor_net_guid").cumcount()
    opens["actor_instance_id"] = opens.actor_net_guid.astype(str) + "#" + opens.instance_seq.astype(str)
    # pair each close with the latest open of the same guid at or before it
    opens_s = opens.sort_values("time_ms")
    cl = pd.merge_asof(closes.sort_values("time_ms")[["actor_net_guid", "time_ms", "packet_id"]].rename(columns={"time_ms": "close_ms", "packet_id": "close_packet_id"}),
                       opens_s[["actor_net_guid", "time_ms", "actor_instance_id"]].rename(columns={"time_ms": "open_ms"}),
                       left_on="close_ms", right_on="open_ms", by="actor_net_guid", direction="backward")
    cl = cl.dropna(subset=["actor_instance_id"]).drop_duplicates("actor_instance_id", keep="first")
    opens = opens.merge(cl[["actor_instance_id", "close_ms", "close_packet_id"]], on="actor_instance_id", how="left")
    opens["class_name"] = opens.class_path.map(short_class).astype(object)
    C.opens = opens
    cls_of_guid = opens.drop_duplicates("actor_net_guid", keep="last").set_index("actor_net_guid").class_path
    C.cls_of_guid = cls_of_guid

    def inst_for(guids, times):
        """actor_instance_id live at `times` for `guids` (merge_asof on open time; closed instances still match if time <= close)."""
        q = pd.DataFrame({"actor_net_guid": pd.Series(guids).astype("float64").to_numpy(), "t": np.asarray(times, dtype="float64")})
        q["_i"] = np.arange(len(q))
        valid = q.actor_net_guid.notna()
        res = pd.Series([None] * len(q), dtype=object)
        if valid.any():
            qq = q[valid].sort_values("t")
            o = opens.sort_values("open_ms" if "open_ms" in opens else "time_ms")
            o = o.assign(_ot=o.time_ms.astype("float64"), actor_net_guid=o.actor_net_guid.astype("float64"))
            m = pd.merge_asof(qq, o[["actor_net_guid", "_ot", "actor_instance_id"]], left_on="t", right_on="_ot", by="actor_net_guid", direction="backward")
            res.iloc[m._i.to_numpy()] = m.actor_instance_id.to_numpy()
        return res.to_numpy()

    C.inst_for = inst_for

    # roster fallback: manifest.players is the primary source; when a build's manifest has none, rebuild it from the fields
    diag["roster_source"] = "manifest.players"
    if len(roster) == 0:
        psr = F[(F.field_name == "Subject") & F.group_path.str.contains("PlayerState") & F.value_str.notna()].drop_duplicates("actor_net_guid")
        pw = F[(F.field_name == "PlayerState") & F.value_i64.notna()]
        pw = pw[pw.actor_net_guid.map(lambda g: str(cls_of_guid.get(int(g), "")).endswith("_PC_C"))]
        rr_ = []
        for r in psr.itertuples():
            chars = sorted({int(g) for g in pw[pw.value_i64 == r.actor_net_guid].actor_net_guid})
            rr_.append(dict(actor_net_guid=int(r.actor_net_guid), subject=r.value_str, character_net_guids=chars, character_net_guid=chars[0] if chars else None))
        roster = pd.DataFrame(rr_)
        diag["roster_source"] = "FALLBACK: PlayerState.Subject fields + pawn.PlayerState fields (manifest had no players)"
        diag["notes"].append(diag["roster_source"])

    # ------------------------------------------------------------------------------------------------ identity maps
    subj_by_ps, subj_by_char = {}, {}
    for _, r in roster.iterrows():
        subj_by_ps[int(r["actor_net_guid"])] = r["subject"]
        for c in (r.get("character_net_guids") or []):
            subj_by_char[int(c)] = r["subject"]
    C.subj_by_ps, C.subj_by_char = subj_by_ps, subj_by_char
    # team split: PlayerState GUIDs form two contiguous blocks; cut at the largest gap
    team_of = {}
    team_basis = "UNRESOLVED"
    if len(roster):
        g = np.sort(roster["actor_net_guid"].astype(int).to_numpy())
        if len(g) > 1:
            cut = g[int(np.argmax(np.diff(g))) + 1]
            for _, r in roster.iterrows():
                team_of[r["subject"]] = "A" if int(r["actor_net_guid"]) < cut else "B"
            team_basis = "PlayerState GUID blocks split at largest gap (DERIVED; not a replicated team field)"
        else:
            for _, r in roster.iterrows():
                team_of[r["subject"]] = None
    C.team_of = team_of

    def pid_ps(v):
        return subj_by_ps.get(int(v)) if v is not None and pd.notna(v) else None

    def pid_ch(v):
        return subj_by_char.get(int(v)) if v is not None and pd.notna(v) else None

    def emit_df_poss(pp, match_id, m8, n0):
        d = pd.DataFrame(dict(player_id=pp.player_id, id_space="possessed_character_net_guid", id_value=pp.id_value, valid_from_ms=pp.valid_from_ms, valid_to_ms=None,
                              note="PlayerState.PossessedCharacter change (possession time)"))
        d.insert(0, "match_id", match_id)
        d.insert(1, "record_id", [f"{m8}:identity_crosswalk:{n0 + i:07d}" for i in range(len(d))])
        for k, v in (("source_file", "fields.parquet"), ("source_table", "fields"), ("source_ref", None), ("transformation", "possession field observation"), ("evidence", "OBSERVED"), ("resolution_status", "RESOLVED")):
            d[k] = v
        return d.reindex(columns=T["identity_crosswalk"].columns)

    def classify_actor(p):
        p = p if isinstance(p, str) else ""
        n = short_class(p) or ""
        if re.search(r"_PC_C$", p):
            return "player_character"
        if "PlayerState" in n:
            return "player_state"
        if "Controller" in n:
            return "controller"
        if re.match(r"^(Projectile_|GameObject_|Pawn_|Ability_)", n) and not n.startswith("Ability_Melee"):
            return "utility_object"
        if n.startswith(("Bomb", "TimedBomb")):
            return "spike"
        if re.search(r"(Pistol|Rifle|MachineGun|Shotgun|Sniper|Revolver|Unarmed|Melee|Equippable|Armor)", n):
            return "equippable"
        if "GameState" in n or "TeamState" in n or "OwnerExclusivePlayerInfo" in n:
            return "game_info"
        return "other"


    # ================================================================================================ IDENTITY
    @step("identity")
    def _identity():
        char_code = {}
        for g, p in cls_of_guid.items():
            if not isinstance(p, str):
                continue
            m = re.search(r"/Game/Characters/([A-Za-z0-9_]+)/[^/]*_PC\.", p)
            if m and m.group(1) != "_Core":
                char_code[int(g)] = (m.group(1), p)
        loadouts = []
        for s in man.get("game_specific_data") or []:
            try:
                j = json.loads(s)
            except Exception:
                continue
            if isinstance(j, dict) and "playerLoadouts" in j:
                loadouts = j["playerLoadouts"]
        char_id = {x.get("subject"): x.get("characterId") for x in loadouts}
        # controller / possession observations
        poss = F[F.field_name.isin(["PossessedCharacter"]) & F.group_path.str.contains("PlayerState")]
        ctrl = F[(F.field_name == "Controller") & F.group_path.str.contains("_PC")]
        rows = []
        for _, r in roster.iterrows():
            sub = r["subject"]
            chars = [int(c) for c in (r.get("character_net_guids") or [])]
            code = None; cpath = None; cg = None
            for c in chars:
                if c in char_code:
                    code, cpath = char_code[c]; cg = c; break
            ctr = sorted({int(v) for v in ctrl[ctrl.actor_net_guid.isin(chars)].value_i64.dropna()})
            rows.append(dict(player_id=sub, playerstate_actor_net_guid=int(r["actor_net_guid"]), character_net_guids=json.dumps(chars),
                             controller_net_guids=json.dumps(ctr), team_id=team_of.get(sub), team_basis=team_basis, agent_code=code,
                             agent_name=codes.get(code, code) if code else None, agent_class_guid=cg, characterId=char_id.get(sub),
                             display_name=None, name_status="NOT_PRESENT_IN_SOURCE",
                             resolution_status="RESOLVED" if (code and team_of.get(sub)) else "PARTIAL", evidence="OBSERVED"))
        P = pd.DataFrame(rows)
        emit("players", P, "manifest.json+fields.parquet+actors.parquet", "manifest.players / actors.open / fields(Controller)", "roster join; agent from character class path; team from PlayerState block split", "OBSERVED")
        T["players"].loc[T["players"].team_id.notna(), "evidence"] = "DERIVED"
        gap("players", "NOT_PRESENT_IN_SOURCE", "display names / Riot IDs: only subject UUIDs are in the replay; UUID stability across matches is untested")
        # teams
        tr = []
        for tid, gdf in P.groupby("team_id", dropna=False):
            tr.append(dict(team_id=tid, n_players=len(gdf), player_ids=json.dumps(list(gdf.player_id)), team_basis=team_basis, first_half_side=None, side_status="UNRESOLVED"))
        emit("teams", pd.DataFrame(tr), "manifest.json", "manifest.players", "PlayerState block split", "DERIVED", "PARTIAL")
        gap("teams", "UNRESOLVED", "attacker/defender side per team: not read; RoundResults.WinningTeamRole gives the winner's role per round only (see rounds.winning_team_role)")
        # agents
        ag = P[["agent_code", "agent_name", "player_id", "agent_class_guid"]].rename(columns={"agent_class_guid": "character_net_guid"}).copy()
        ag["class_path"] = ag.character_net_guid.map(lambda g: cls_of_guid.get(int(g)) if pd.notna(g) else None)
        ag["name_status"] = np.where(ag.agent_code.isin(codes.keys()), "MAPPED_FROM_CODENAMES_JSON", np.where(ag.agent_code.notna(), "CODENAME_ONLY", "UNRESOLVED"))
        emit("agents", ag, "actors.parquet", "actors.open class_path", "codename parsed from /Game/Characters/<code>/", "OBSERVED")
        # actors
        a = opens.copy()
        a["actor_kind"] = a.class_path.map(classify_actor)
        a["round_index_at_open"] = round_of(a.time_ms); a["round_ms_at_open"] = round_ms(a.time_ms)
        a["player_id"] = a.actor_net_guid.map(lambda g: pid_ch(g) or pid_ps(g))
        a = a.rename(columns={"time_ms": "open_ms", "packet_id": "open_packet_id"})
        a["source_ref"] = "actors.parquet#" + a["index"].astype(str) if "index" in a else None
        a["owner_player_id"] = None
        emit("actors", a, "actors.parquet", "actors(open,close)", "open rows with matching close attached by guid+time", "OBSERVED")
        # lifecycle
        lc = act.copy()
        lc["actor_instance_id"] = inst_for(lc.actor_net_guid, lc.time_ms.astype("float64"))
        lc["round_index"] = round_of(lc.time_ms); lc["round_ms"] = round_ms(lc.time_ms)
        lc["source_ref"] = "actors.parquet#" + lc.index.astype(str)
        emit("actor_lifecycle", lc.rename(columns={"time_ms": "time_ms"})[["actor_instance_id", "actor_net_guid", "event", "time_ms", "packet_id", "channel_index", "class_path", "round_index", "round_ms", "source_ref"]],
             "actors.parquet", "actors", "row copy plus instance id and round clock", "OBSERVED")
        # netguid mappings
        n = ng.copy()
        pm = n.drop_duplicates("net_guid").set_index("net_guid").path.astype(str)
        n["outer_path"] = n.outer_net_guid.map(lambda g: pm.get(int(g)) if pd.notna(g) else None)
        n["full_path"] = np.where(n.outer_path.notna(), n.outer_path.astype(str) + "/" + n.path.astype(str), n.path.astype(str))
        n["source_ref"] = "net_guids.parquet#" + n.index.astype(str)
        emit("netguid_mappings", n, "net_guids.parquet", "net_guids", "outer path joined one level", "OBSERVED")
        C.P = P
        # crosswalk
        xr = []
        for r in P.itertuples():
            xr.append(dict(player_id=r.player_id, id_space="subject_uuid", id_value=r.player_id, note="manifest players[].subject"))
            xr.append(dict(player_id=r.player_id, id_space="playerstate_actor_net_guid", id_value=str(r.playerstate_actor_net_guid), note="manifest players[].actor_net_guid"))
            for c in json.loads(r.character_net_guids):
                xr.append(dict(player_id=r.player_id, id_space="character_pawn_net_guid", id_value=str(c), note="manifest players[].character_net_guids"))
            for c in json.loads(r.controller_net_guids):
                xr.append(dict(player_id=r.player_id, id_space="controller_net_guid", id_value=str(c), note="fields Controller on the character actor", evidence="OBSERVED"))
            if r.characterId:
                xr.append(dict(player_id=r.player_id, id_space="characterId", id_value=r.characterId, note="manifest game_specific_data playerLoadouts"))
            if r.agent_code:
                xr.append(dict(player_id=r.player_id, id_space="agent_codename", id_value=r.agent_code, note="character class path"))
        emit("identity_crosswalk", pd.DataFrame(xr), "manifest.json+fields.parquet", "manifest.players, loadouts", "one row per identifier per player", "OBSERVED")
        # possession change times
        if len(poss):
            pp = poss.copy(); pp["player_id"] = pp.actor_net_guid.map(pid_ps)
            pp["id_value"] = pp.value_i64.map(lambda v: str(int(v)) if pd.notna(v) else None)
            pp["valid_from_ms"] = pp.time_ms
            T["identity_crosswalk"] = pd.concat([T["identity_crosswalk"], emit_df_poss(pp, match_id, m8, len(T["identity_crosswalk"]))], ignore_index=True)

    # ================================================================================================ OWNERSHIP INTERVALS
    @step("ownership")
    def _own():
        rel = F[F.field_name.isin(["Owner", "Instigator", "Controller", "PossessedCharacter", "Possessed"]) & ~F.group_path.str.endswith("ClassNetCache")].copy()
        rel = rel[rel.value_i64.notna()].reset_index().rename(columns={"index": "field_row"})
        rel["actor_instance_id"] = inst_for(rel.actor_net_guid, rel.time_ms)
        rel = rel.sort_values(["actor_net_guid", "field_name", "time_ms", "packet_id"])
        rel["target"] = rel.value_i64.astype("int64")
        rel["prev_t"] = rel.groupby(["actor_instance_id", "field_name"], dropna=False).time_ms.shift(-1)
        rel["prev_target"] = rel.groupby(["actor_instance_id", "field_name"], dropna=False).target.shift(1)
        rel = rel[~((rel.target == rel.prev_target))]  # a restated unchanged value is not a new interval
        rel["end_ms"] = rel.groupby(["actor_instance_id", "field_name"], dropna=False).time_ms.shift(-1)
        close_of = opens.set_index("actor_instance_id").close_ms
        rel["end_reason"] = np.where(rel.end_ms.notna(), "relation_changed", "")
        miss = rel.end_ms.isna()
        rel.loc[miss, "end_ms"] = rel.loc[miss, "actor_instance_id"].map(close_of)
        rel["end_reason"] = np.where(rel.end_ms.notna() & (rel.end_reason == ""), "actor_closed", np.where(rel.end_ms.isna(), "open_at_replay_end", rel.end_reason))
        rel["target_instance_id"] = inst_for(rel.target, rel.time_ms)
        d = pd.DataFrame(dict(actor_instance_id=rel.actor_instance_id, actor_net_guid=rel.actor_net_guid, actor_class=rel.actor_net_guid.map(lambda g: short_class(cls_of_guid.get(int(g)))),
                              relation=rel.field_name, target_net_guid=rel.target, target_instance_id=rel.target_instance_id,
                              target_class=rel.target.map(lambda g: short_class(cls_of_guid.get(int(g)))),
                              target_player_id=rel.target.map(lambda g: pid_ch(g) or pid_ps(g)), start_ms=rel.time_ms, end_ms=rel.end_ms, end_reason=rel.end_reason,
                              start_round_index=round_of(rel.time_ms), start_round_ms=round_ms(rel.time_ms),
                              player_id=rel.actor_net_guid.map(lambda g: pid_ch(g) or pid_ps(g)), packet_id=rel.packet_id, channel_index=rel.channel_index,
                              source_ref="fields.parquet#" + rel.field_row.astype(str)))
        d["resolution_status"] = np.where(d.target_player_id.notna() | d.player_id.notna(), "RESOLVED_TO_PLAYER", "TARGET_NOT_A_ROSTER_ENTITY")
        emit("actor_ownership_intervals", d, "fields.parquet", "fields(Owner|Instigator|Controller|PossessedCharacter|Possessed)", "consecutive observations of one relation on one actor instance become an interval", "OBSERVED")
        C.own = d

    # ================================================================================================ MAP / COORDINATES
    @step("map")
    def _map():
        rows = []
        reg = {}
        mp = Path(map_registry) if map_registry else None
        if mp and mp.is_file():
            for m in json.load(open(mp)).get("maps", []):
                reg[str(m["map_id"]).lower()] = m
        for L in man.get("level_names_and_times") or []:
            path = L.get("name"); code = str(path).rstrip("/").split("/")[-1] if path else None
            hit = reg.get(str(code).lower())
            rows.append(dict(replay_id=match_id, map_code=code, level_path=path, level_time_ms=L.get("time_ms"),
                             map_name=hit["display_name"] if hit else None, internal_asset_id=path,
                             id_source="manifest.level_names_and_times (+map_registry name match)" if hit else "manifest.level_names_and_times",
                             map_identity_status="CODE_OBSERVED_NAME_MATCHED" if hit else "CODE_OBSERVED_NAME_UNMATCHED",
                             geometry_status=(hit or {}).get("geometry_status", "NO_REFERENCE_PACKAGE"), map_reference_package=None))
        if not rows:
            rows = [dict(replay_id=match_id, map_code=None, map_identity_status="UNRESOLVED", id_source="manifest has no level_names_and_times", geometry_status="NO_REFERENCE_PACKAGE")]
        emit("map_metadata", pd.DataFrame(rows), "manifest.json", "manifest.level_names_and_times", "level path split into map code; optional registry name match", "OBSERVED")
        T["map_metadata"].loc[T["map_metadata"].map_code.isna(), "resolution_status"] = "UNRESOLVED"
        C.map_code = rows[0].get("map_code")
        gap("map_metadata", "NOT_PRESENT_IN_SOURCE", "public map name beyond the registry, site regions and a versioned geometry package are not in the replay; none were invented")
        cs = [dict(coordinate_system_id="UE_WORLD_NATIVE", units="unreal_units", units_basis="Unreal Engine convention (1 uu = 1 cm); the replay does not state units", origin="level world origin (0,0,0) as stored; per-map origin offset NOT_PRESENT_IN_SOURCE",
                   axes="X,Y horizontal; Z up (Unreal left-handed convention); axis polarity vs the visual map NOT_PRESENT_IN_SOURCE", elevation_axis="Z", handedness="left (Unreal convention, unverified in replay)",
                   space="world", angle_units="degrees (yaw 0..360 observed as stored)", transformations_applied="none", status="CONVENTION_NOT_VERIFIED_FROM_REPLAY")]
        emit("coordinate_systems", pd.DataFrame(cs), "manifest.json+movement.parquet", "movement pos_x/pos_y/pos_z", "documented convention; values kept exactly as stored", "INFERRED", "CONVENTION_NOT_VERIFIED_FROM_REPLAY")
        gap("coordinate_systems", "NOT_PRESENT_IN_SOURCE", "no per-map transform in the replay; world coordinates are preserved for later enrichment")

    # ================================================================================================ MOVEMENT
    @step("movement")
    def _move():
        d = mv.copy()
        d["mover_net_guid"] = d.character_net_guid
        d["tick"] = None
        d["round_index"] = round_of(d.time_ms); d["round_ms"] = round_ms(d.time_ms)
        d["player_id"] = d.mover_net_guid.map(pid_ch)
        d["mover_kind"] = np.where(d.player_id.notna(), "roster_character", np.where(d.mover_net_guid.map(lambda g: str(cls_of_guid.get(int(g), "")).endswith("_PC_C")), "character_not_in_roster", "non_roster_mover"))
        d["actor_instance_id"] = inst_for(d.mover_net_guid, d.time_ms)
        d["map_code"] = C.map_code; d["coordinate_system_id"] = "UE_WORLD_NATIVE"; d["position_source"] = "movement.parquet (native, no resampling)"
        d["source_ref"] = "movement.parquet#" + d._row.astype(str)
        d["resolution_status"] = np.where(d.player_id.notna(), "RESOLVED", "NOT_A_ROSTER_MOVER")
        emit("movement", d.drop(columns=["_row", "character_net_guid"]), "movement.parquet", "movement", "native rows kept; adds round clock, mover kind and player id", "OBSERVED")
        gap("movement", "NOT_EXPOSED_BY_PARSER", "server tick is not in movement.parquet; 'timestamp' is the movement component's own counter and is preserved in column timestamp")
        # player positions with derived steps (sorted per player; first row of each player-round has no predecessor)
        p = d[d.player_id.notna()].copy()
        p = p.sort_values(["player_id", "time_ms", "_row"]).reset_index(drop=True)
        g = p.groupby("player_id")
        same = (p.player_id == g.player_id.shift(1)) & (p.round_index == g.round_index.shift(1))
        dt = (p.time_ms - g.time_ms.shift(1)).where(same)
        dx = (p.pos_x - g.pos_x.shift(1)).where(same); dy = (p.pos_y - g.pos_y.shift(1)).where(same); dz = (p.pos_z - g.pos_z.shift(1)).where(same)
        dyaw = ((p.yaw - g.yaw.shift(1) + 180) % 360 - 180).where(same); dpitch = (p.pitch - g.pitch.shift(1)).where(same)
        step_xy = np.hypot(dx, dy); step_xyz = np.sqrt(dx ** 2 + dy ** 2 + dz ** 2)
        ok = same & (dt > 0) & (dt <= NC["position_max_dt_for_velocity_ms"])
        pp = pd.DataFrame(dict(player_id=p.player_id, team_id=p.player_id.map(team_of), agent_code=p.player_id.map(C.P.set_index("player_id").agent_code),
                               round_index=p.round_index, round_ms=p.round_ms, time_ms=p.time_ms, mover_net_guid=p.mover_net_guid, pos_x=p.pos_x, pos_y=p.pos_y, pos_z=p.pos_z,
                               yaw=p.yaw, pitch=p.pitch, dt_ms=dt, dx=dx, dy=dy, dz=dz, step_xy=step_xy, step_xyz=step_xyz,
                               speed_xy_per_s=(step_xy / dt * 1000).where(ok), speed_xyz_per_s=(step_xyz / dt * 1000).where(ok), dyaw=dyaw, dpitch=dpitch,
                               movement_row_ref=p.source_ref, map_code=C.map_code, coordinate_system_id="UE_WORLD_NATIVE", derived_valid=ok))
        pp["resolution_status"] = "RESOLVED"
        emit("player_positions", pp, "movement.parquet", "movement", "roster rows only; differences to the previous sample of the same player in the same round; velocity only where 0<dt<=limit", "OBSERVED")
        T["player_positions"].loc[T["player_positions"].derived_valid.fillna(False).astype(bool), "evidence"] = "DERIVED"
        C.pp = T["player_positions"]
        # coverage
        cov = []
        rstart = dict(zip(R_idx, R_t))
        ends = {}
        thr = NC["position_gap_ms"]
        sc = "player_round"
        for keys, gdf in p.groupby(["player_id", "round_index"]):
            pid, ri = keys
            dts = gdf.time_ms.diff().dropna()
            cov.append(dict(scope=sc, player_id=pid, round_index=int(ri), mover_net_guid=int(gdf.mover_net_guid.iloc[0]), n_samples=len(gdf), first_ms=int(gdf.time_ms.min()), last_ms=int(gdf.time_ms.max()),
                            span_ms=int(gdf.time_ms.max() - gdf.time_ms.min()), median_dt_ms=float(dts[dts > 0].median()) if (dts > 0).any() else None,
                            p95_dt_ms=float(dts.quantile(.95)) if len(dts) else None, max_gap_ms=float(dts.max()) if len(dts) else None, n_gaps_over_threshold=int((dts > thr).sum()),
                            gap_threshold_ms=thr, coverage_basis="samples of this player within the round", round_start_ms=rstart.get(ri), n_zero_dt=int((dts == 0).sum())))
        for gid, gdf in d.groupby("mover_net_guid"):
            dts = gdf.time_ms.diff().dropna()
            cov.append(dict(scope="actor", player_id=gdf.player_id.iloc[0], mover_net_guid=int(gid), n_samples=len(gdf), first_ms=int(gdf.time_ms.min()), last_ms=int(gdf.time_ms.max()),
                            span_ms=int(gdf.time_ms.max() - gdf.time_ms.min()), median_dt_ms=float(dts[dts > 0].median()) if (dts > 0).any() else None,
                            max_gap_ms=float(dts.max()) if len(dts) else None, n_gaps_over_threshold=int((dts > thr).sum()), gap_threshold_ms=thr, coverage_basis=gdf.mover_kind.iloc[0], n_zero_dt=int((dts == 0).sum())))
        att = float(d.player_id.notna().mean()) if len(d) else None
        cov.append(dict(scope="match_mapping", n_samples=len(d), fraction_attributed=att, coverage_basis="movement rows attributed to a roster player / all movement rows"))
        emit("position_coverage", pd.DataFrame(cov), "movement.parquet", "movement", "per player-round, per actor, and match-level attribution coverage", "DERIVED")
        check("position attribution", "PASS" if att and att > 0.5 else "WARN", f"{att:.3f} of {len(d)} movement rows attributed to roster players" if att is not None else "no movement rows", "info" if att and att > 0.5 else "warn")
        # anomalies (flags only; nothing removed)
        an = []
        def add(mask, name, val, thr_):
            x = pp[mask.fillna(False)]
            for r in x.itertuples():
                an.append(dict(anomaly=name, player_id=r.player_id, round_index=r.round_index, time_ms=r.time_ms, mover_net_guid=r.mover_net_guid, value=getattr(r, val), threshold=thr_, movement_row_ref=r.movement_row_ref))
        pp_ = pp.copy()
        add(pp_.speed_xy_per_s > NC["position_max_speed_units_per_s"], "implied_speed_xy_above_threshold", "speed_xy_per_s", NC["position_max_speed_units_per_s"])
        add(pp_.step_xyz > NC["position_max_step_units"], "step_above_threshold", "step_xyz", NC["position_max_step_units"])
        add((pp_.dt_ms == 0) & (pp_.step_xyz > 0), "same_time_different_position", "step_xyz", 0)
        add(pp_.pos_x.isna() | pp_.pos_y.isna() | pp_.pos_z.isna(), "missing_coordinate", "pos_x", None)
        add((pp_.pos_x == 0) & (pp_.pos_y == 0) & (pp_.pos_z == 0), "all_zero_position", "pos_x", 0)
        add(pp_.dt_ms > thr, "gap_above_threshold", "dt_ms", thr)
        emit("position_anomalies", pd.DataFrame(an), "movement.parquet", "movement", "flags against thresholds in pipeline_config.json; rows are not removed or altered", "DERIVED")
        C.n_anom = len(an)

    # ================================================================================================ EVENTS / ROUNDS
    @step("events")
    def _events():
        e = ev.copy()
        e["event_id"] = e["id"]; e["event_group"] = e["group"]; e["event_name"] = e["payload_name"]
        e["time_ms"] = e.time1.astype("int64"); e["time2_ms"] = e.time2.astype("int64")
        e["round_index"] = round_of(e.time_ms); e["round_ms"] = round_ms(e.time_ms)
        e["tick"] = None; e["packet_id"] = None; e["channel_index"] = None; e["event_sequence"] = e.index
        e["actor_guid"] = None; e["object_guid"] = None
        dead = e.event_group == "characterDeath"
        e["instigator"] = np.where(dead, e.word0, np.nan); e["target"] = np.where(dead, e.word1, np.nan)
        e["source_event_row"] = e.index
        e["source_ref"] = "events.parquet#" + e.index.astype(str)
        # related replicated-field rows by time proximity only
        w = NC["event_field_window_ms"]
        ft = np.sort(F.time_ms.to_numpy())
        e["related_field_rows"] = np.searchsorted(ft, e.time_ms + w, side="right") - np.searchsorted(ft, e.time_ms - w, side="left")
        emit("events", e[["event_id", "event_group", "event_name", "time_ms", "time2_ms", "round_index", "round_ms", "tick", "packet_id", "channel_index", "event_sequence", "payload_tag", "word0", "word1",
                           "actor_guid", "object_guid", "instigator", "target", "related_field_rows", "source_event_row", "source_ref"]], "events.parquet", "events", "row copy plus round clock; related_field_rows counts field rows within +-window ms (time proximity only)", "OBSERVED")
        gap("events", "NOT_EXPOSED_BY_PARSER", "events.parquet has no packet id, channel index or server tick per event; those columns are null by design")
        ep = pd.DataFrame(dict(event_id=e.event_id, payload_size=e.payload_size, payload_tag=e.payload_tag, payload_name=e.payload_name, payload_seconds=e.payload_seconds, word0=e.word0, word1=e.word1,
                               raw_payload_hex=e.raw_payload.map(hexes), source_ref=e.source_ref))
        ep["interpretation"] = np.where(dead, "word0=killer character net guid, word1=victim character net guid", "words uninterpreted")
        ep["interpretation_status"] = np.where(dead, "INFERRED_CHECKED_AGAINST_KILL_CREDIT", "NOT_INTERPRETED")
        emit("event_payloads", ep, "events.parquet", "events.raw_payload", "payload bytes as hex; words as decoded by vrfkit", "OBSERVED")
        # replicated fields: selected patterns
        pats = NC["field_patterns_replicated"]
        sel = pd.Series(False, index=F.index); grp = pd.Series("", index=F.index, dtype=object)
        for gname, pl in pats.items():
            rx = re.compile("|".join(pl))
            msk = F.field_name.map(lambda s: bool(rx.search(s))) if False else F.field_name.str.contains(rx)
            grp = grp.where(~(msk & ~sel), gname); sel |= msk
        rf = F[sel].copy(); rf["field_row"] = rf.index; rf["pattern_group"] = grp[sel]
        rf = rf[~rf.field_name.str.contains(r"^(?:MulticastNotifyDamage|Rounds\[)", regex=True)]
        rf["value"] = coalesce(rf).map(lambda v: None if v is None else str(v)); rf["value_type"] = vtype(rf)
        rf["actor_instance_id"] = inst_for(rf.actor_net_guid, rf.time_ms)
        rf["round_index"] = round_of(rf.time_ms); rf["round_ms"] = round_ms(rf.time_ms)
        rf["source_ref"] = "fields.parquet#" + rf.field_row.astype(str)
        emit("replicated_fields", rf[["field_row", "time_ms", "packet_id", "channel_index", "actor_net_guid", "actor_instance_id", "object_net_guid", "group_path", "field_name", "value", "value_type", "pattern_group", "round_index", "round_ms", "source_ref"]],
             "fields.parquet", "fields", "rows whose field name matches pipeline_config field_patterns_replicated; ALL rows stay in fields.parquet", "OBSERVED")
        # rounds
        rr = F[F.group_path.str.contains("GameState") & F.field_name.str.match(r"^RoundResults\[\d+\]\.")].copy()
        rr["idx"] = rr.field_name.str.extract(r"\[(\d+)\]")[0].astype(int); rr["leaf"] = rr.field_name.str.replace(r"^RoundResults\[\d+\]\.", "", regex=True)
        res = rr.pivot_table(index="idx", columns="leaf", values="value_str", aggfunc="first") if len(rr) else pd.DataFrame()
        rn = rr[rr.leaf == "RoundNumber"].set_index("idx").value_i64 if len(rr) else pd.Series(dtype=float)
        rtime = rr.groupby("idx").time_ms.min() if len(rr) else pd.Series(dtype=float)
        # buy-phase end: first ClientBuyPhaseEnd observation inside each round window (evidence for the CastTime zero point)
        bp = F[F.field_name.str.contains("ClientBuyPhaseEnd")].time_ms.sort_values().to_numpy()
        sw = ev[ev.group == "switchTeams"].time1.astype("int64").tolist()
        rows = []
        for k, (ri, t) in enumerate(zip(R_idx, R_t)):
            nxt = R_t[k + 1] if k + 1 < len(R_t) else None
            b = bp[(bp >= t) & ((bp < nxt) if nxt is not None else True)]
            first_of_half = ri == 0 or any(t0 >= s_ and (k == 0 or R_t[k - 1] < s_) for s_ in sw for t0 in [t])
            fb = NC["barrier_fallback_ms"]["first_round_of_half" if first_of_half else "default"]
            sw_before = next((s_ for s_ in sw if (R_t[k - 1] if k else -1) < s_ <= t), None)
            rows.append(dict(round_index=int(ri), round_started_ms=int(t), round_end_ms=int(rtime[ri]) if ri in rtime.index else None,
                             round_end_basis="first RoundResults[n].* field observed" if ri in rtime.index else "UNRESOLVED",
                             buy_end_ms=int(b[0]) if len(b) else int(t + fb), buy_end_basis="first ClientBuyPhaseEnd in the round window (OBSERVED)" if len(b) else f"fallback roundStarted+{fb} ms (INFERRED)",
                             half_index=int(sum(1 for s_ in sw if s_ <= t)), side_switch_before_round_ms=sw_before,
                             winning_team_label=res["WinningTeam"].get(ri) if "WinningTeam" in res else None, winning_team_role=res["WinningTeamRole"].get(ri) if "WinningTeamRole" in res else None,
                             round_result=res["RoundResult"].get(ri) if "RoundResult" in res else None, round_number=rn.get(ri) if len(rn) else None,
                             winner_team_id=None, winner_status="UNRESOLVED: WinningTeam is a string label with no established mapping to the roster team blocks"))
        emit("rounds", pd.DataFrame(rows), "events.parquet+fields.parquet", "events(roundStarted,switchTeams), GameState RoundResults[n].*", "one row per roundStarted; outcome fields copied by name", "OBSERVED")
        T["rounds"].loc[T["rounds"].buy_end_basis.str.contains("INFERRED"), "evidence"] = "INFERRED"
        C.rounds = T["rounds"]
        gap("rounds", "UNRESOLVED", "round end time is the first RoundResults observation (INFERRED as end); attacker/defender side per team not read")
        # boundaries
        b = []
        for r in rows:
            b.append(dict(round_index=r["round_index"], boundary="round_start", time_ms=r["round_started_ms"], basis="events.roundStarted", value=None))
            b.append(dict(round_index=r["round_index"], boundary="buy_phase_end", time_ms=r["buy_end_ms"], basis=r["buy_end_basis"], value=None))
            if r["round_end_ms"] is not None:
                b.append(dict(round_index=r["round_index"], boundary="round_result_observed", time_ms=r["round_end_ms"], basis=r["round_end_basis"], value=r["winning_team_label"]))
            if r["side_switch_before_round_ms"] is not None:
                b.append(dict(round_index=r["round_index"], boundary="side_switch", time_ms=r["side_switch_before_round_ms"], basis="events.switchTeams", value=None))
        ph = F[F.field_name.str.contains(r"MulticastSetPhase\.NewPhase|ClientGamePhaseBegin\.NewPhase")]
        for r in ph.itertuples():
            b.append(dict(round_index=int(round_of([r.time_ms])[0]), boundary="phase_begin", time_ms=int(r.time_ms), basis=r.field_name, value=r.value_i64))
        emit("round_boundaries", pd.DataFrame(b).sort_values("time_ms") if b else pd.DataFrame(), "events.parquet+fields.parquet", "events, fields(phase)", "boundaries from events and phase fields; phase numbers are unlabelled", "OBSERVED")
        gap("round_boundaries", "UNRESOLVED", "phase number meanings are not labelled in the export")
        # spike
        sp = []
        for r in ev[ev.group.isin(["spikePlanted", "spikeDefused"])].itertuples():
            sp.append(dict(event_type="plant" if r.group == "spikePlanted" else "defuse_complete", time_ms=int(r.time1), basis=f"events.{r.group}", source_ref=f"events.parquet#{r.Index}"))
        for r in F[F.group_path.str.contains("GameState") & (F.field_name == "BombState")].itertuples():
            sp.append(dict(event_type="bomb_state_change", time_ms=int(r.time_ms), value=r.value_i64, basis="GameState.BombState (numeric, unlabelled)", source_ref=f"fields.parquet#{r.Index}"))
        for r in F[F.field_name.str.contains("BombLocation") & F.group_path.str.contains("BombDestination")].itertuples():
            m = re.findall(r"-?\d+\.?\d*", str(r.value_str)); xyz = [float(x) for x in m[:3]] if len(m) >= 3 else [None] * 3
            sp.append(dict(event_type="plant_location", time_ms=int(r.time_ms), location_x=xyz[0], location_y=xyz[1], location_z=xyz[2], basis="BombDestination.MulticastActivateBombSiteEffects.BombLocation", source_ref=f"fields.parquet#{r.Index}"))
        be = F[F.group_path.str.contains("BombEquippable") & F.field_name.isin(["Owner", "PreventPickupCharacter", "MulticastPlayBombPickedUpAudio.NewCharacter"]) & F.value_i64.notna()].sort_values(["time_ms", "packet_id"])
        last_owner = None
        for r in be.itertuples():
            g = int(r.value_i64); sub = pid_ch(g)
            if r.field_name == "Owner":
                et = "carrier_set" if g != last_owner else None
                if et:
                    sp.append(dict(event_type="carrier_set", time_ms=int(r.time_ms), subject_net_guid=g, subject_player_id=sub, basis="BombEquippable.Owner change (pickup or drop target; a non-roster owner such as the world means dropped) - INFERRED reading", source_ref=f"fields.parquet#{r.Index}", evidence="INFERRED"))
                    if sub is None:
                        sp.append(dict(event_type="drop_candidate", time_ms=int(r.time_ms), subject_net_guid=g, basis="Owner moved to a non-roster entity", source_ref=f"fields.parquet#{r.Index}", evidence="INFERRED"))
                    elif last_owner is not None or True:
                        sp.append(dict(event_type="pickup_candidate", time_ms=int(r.time_ms), subject_net_guid=g, subject_player_id=sub, basis="Owner became a roster character", source_ref=f"fields.parquet#{r.Index}", evidence="INFERRED"))
                last_owner = g
            elif "PickedUpAudio" in r.field_name:
                sp.append(dict(event_type="pickup_audio_cue", time_ms=int(r.time_ms), subject_net_guid=g, subject_player_id=sub, basis=r.field_name, source_ref=f"fields.parquet#{r.Index}"))
        dp = F[F.group_path.str.contains("TimedBomb") & F.field_name.isin(["DefuseProgress", "CurrentDefuser", "BombHasBeenDefused", "BombDefuseState", "PlantedAtSite"])].sort_values(["time_ms", "packet_id"])
        prev = 0.0; defusing = False
        for r in dp.itertuples():
            if r.field_name == "DefuseProgress" and pd.notna(r.value_f64):
                v = float(r.value_f64)
                if v > 0 and not defusing:
                    defusing = True; sp.append(dict(event_type="defuse_start_candidate", time_ms=int(r.time_ms), value=v, basis="DefuseProgress rose above 0", source_ref=f"fields.parquet#{r.Index}", evidence="INFERRED"))
                if v <= 0 and defusing:
                    defusing = False; sp.append(dict(event_type="defuse_interrupt_or_end_candidate", time_ms=int(r.time_ms), value=v, basis="DefuseProgress returned to 0 (compare with defuse_complete event)", source_ref=f"fields.parquet#{r.Index}", evidence="INFERRED"))
            elif r.field_name == "CurrentDefuser" and pd.notna(r.value_i64):
                sp.append(dict(event_type="defuser_observed", time_ms=int(r.time_ms), subject_net_guid=int(r.value_i64), subject_player_id=pid_ch(r.value_i64) or pid_ps(r.value_i64), basis="TimedBomb.CurrentDefuser", source_ref=f"fields.parquet#{r.Index}"))
            elif r.field_name == "PlantedAtSite":
                sp.append(dict(event_type="planted_at_site_value", time_ms=int(r.time_ms), value=r.value_i64 if pd.notna(r.value_i64) else r.value_str, basis="TimedBomb.PlantedAtSite (unlabelled)", source_ref=f"fields.parquet#{r.Index}"))
        tr_ = F[F.group_path.str.contains("TimedBomb") & (F.field_name == "TimeRemainingToExplode") & F.value_f64.notna()]
        for ri, t in zip(R_idx, R_t):
            nx = R_t[list(R_idx).index(ri) + 1] if list(R_idx).index(ri) + 1 < len(R_t) else 10 ** 12
            x = tr_[(tr_.time_ms >= t) & (tr_.time_ms < nx)]
            if len(x) and x.value_f64.min() <= 0:
                r0 = x[x.value_f64 <= 0].iloc[0]
                sp.append(dict(event_type="detonation_candidate", time_ms=int(r0.time_ms), value=float(r0.value_f64), basis="TimeRemainingToExplode reached <=0 in the round window; check against defuse_complete", source_ref=f"fields.parquet#{x[x.value_f64 <= 0].index[0]}", evidence="INFERRED"))
        s = pd.DataFrame(sp)
        if len(s):
            s["round_index"] = round_of(s.time_ms); s["round_ms"] = round_ms(s.time_ms); s = s.sort_values("time_ms", kind="stable")
        emit("spike_events", s, "events.parquet+fields.parquet", "events(spike*), fields(BombState,BombEquippable,TimedBomb,BombDestination)", "events and field observations with the source names kept; *_candidate rows are INFERRED readings", "OBSERVED")
        gap("spike_events", "UNRESOLVED", "BombState enum labels, site label (A/B/C) and an explicit pickup/drop event are not in the export; pickup/drop/defuse-start/interrupt/detonation rows are INFERRED candidates")

    # ================================================================================================ COMBAT
    @step("combat")
    def _combat():
        P_ = "MulticastNotifyDamage_Point."
        dm = F[F.field_name.str.startswith(P_)]
        recs, cur, key = [], None, None
        for r in zip(dm.index, dm.time_ms, dm.packet_id, dm.channel_index, dm.actor_net_guid, dm.field_name, dm.value_i64, dm.value_f64, dm.value_bool, dm.value_str):
            idx, t, pk, ch, ag, fn, vi, vf, vb, vs = r
            k = (pk, ag); nm = fn[len(P_):]
            if k != key or nm in cur:
                cur = dict(time_ms=int(t), packet_id=int(pk), channel_index=int(ch), victim_actor_net_guid=int(ag), fields_row_first=int(idx)); recs.append(cur); key = k
            v = vs if (vs is not None and not (isinstance(vs, float) and np.isnan(vs))) else (vf if pd.notna(vf) else (vi if pd.notna(vi) else vb))
            cur[nm] = v
        h = pd.DataFrame(recs)
        if len(h) == 0:
            emit("damage_events", pd.DataFrame(), "fields.parquet", "fields", "none found", "OBSERVED", "NOT_EXPOSED_BY_PARSER")
            gap("damage_events", "NOT_EXPOSED_BY_PARSER", "no MulticastNotifyDamage_Point records in the export")
        else:
            g = lambda c: h[c] if c in h else pd.Series([None] * len(h))
            def cn(col):
                return g(col).map(lambda v: short_class(cls_of_guid.get(int(v))) if pd.notna(v) else None)
            dmg = pd.DataFrame(dict(
                time_ms=h.time_ms, packet_id=h.packet_id, channel_index=h.channel_index, victim_actor_net_guid=h.victim_actor_net_guid,
                victim_class=h.victim_actor_net_guid.map(lambda v: short_class(cls_of_guid.get(int(v)))),
                victim_player_id=h.victim_actor_net_guid.map(pid_ch), damager_player_id=g("DamagerPlayerState").map(pid_ps), kill_credit_player_id=g("KillCreditPlayerState").map(pid_ps),
                damage_dealt=g("DamageDealt"), damage_taken=g("DamageTaken"), killed_target=g("bDamageKilledTarget"), alive_after=g("bAliveAfterDamage"), damage_type=g("DamageType"),
                damaged_bone=g("DamagedBone"), regional_damage=g("RegionalDamage"), is_wall_penetration=g("bIsWallPenetration"), equippable_class=cn("EquippableUsed"),
                damage_causer_class=cn("DamageCauser"), damage_causer_net_guid=g("DamageCauser"), damage_origin=g("DamageOrigin").map(lambda v: None if v is None or (isinstance(v, float) and np.isnan(v)) else str(v)),
                assists_list=g("AssistsList").map(lambda v: None if v is None or (isinstance(v, float) and np.isnan(v)) else str(v)), kills_for_killer=g("KillsForKiller"), kills_for_victim=g("KillsForVictim"),
                fields_row_first=h.fields_row_first))
            dmg["round_index"] = round_of(dmg.time_ms); dmg["round_ms"] = round_ms(dmg.time_ms)
            def skind(r):
                c = str(r.damage_causer_class or "")
                if r.victim_player_id is None:
                    return "damage_to_non_roster_target"
                if re.match(r"^(Projectile_|GameObject_|Pawn_|Ability_)", c):
                    return "utility_damage"
                if c.startswith("Bomb") or c.startswith("TimedBomb"):
                    return "spike_damage"
                if r.equippable_class:
                    return "weapon_damage"
                return "unknown_source"
            dmg["source_kind"] = dmg.apply(skind, axis=1)
            dmg["source_ref"] = "fields.parquet#" + dmg.fields_row_first.astype(str)
            dmg["damage_event_id"] = [f"{m8}:dmg:{i:06d}" for i in range(len(dmg))]
            dmg["resolution_status"] = np.where(dmg.victim_player_id.notna() & (dmg.damager_player_id.notna() | dmg.damager_player_id.isna() & dmg.damage_causer_net_guid.isna()), "RESOLVED", "PARTIAL")
            dmg = dmg.sort_values(["time_ms", "packet_id"]).reset_index(drop=True)
            emit("damage_events", dmg, "fields.parquet", "fields(MulticastNotifyDamage_Point.*)", "one RPC call = consecutive fields in one packet on one actor; repeated field name starts the next call", "OBSERVED")
        D = T["damage_events"]
        C.D = D
        # kill/death ledger: the death EVENT carries killer and victim character guids in word0/word1
        tol = NC["death_to_hit_tolerance_ms"]
        dth = ev[ev.group == "characterDeath"].sort_values("time1").reset_index()
        kh = D[(D.killed_target == True) & D.victim_player_id.notna()].copy() if len(D) else pd.DataFrame()
        used = set(); led = []
        for r in dth.itertuples():
            kg, vg = int(r.word0), int(r.word1)
            ksub, vsub = pid_ch(kg), pid_ch(vg)
            cand = kh[(kh.victim_player_id == vsub) & ((kh.time_ms - r.time1).abs() <= tol)] if len(kh) and vsub else pd.DataFrame()
            cand = cand[~cand.damage_event_id.isin(used)] if len(cand) else cand
            hit = None
            if len(cand):
                hit = cand.iloc[(cand.time_ms - r.time1).abs().argmin()]; used.add(hit.damage_event_id)
            credit = hit.kill_credit_player_id if hit is not None else None
            if ksub is None and vsub is None:
                st = "KILLER_AND_VICTIM_NOT_ROSTER"
            elif vsub is None:
                st = "VICTIM_UNRESOLVED"
            elif ksub is None and credit is None:
                st = "KILLER_UNRESOLVED"
            elif hit is None:
                st = "NO_KILLING_HIT_FOUND"
            elif credit is not None and ksub is not None and credit != ksub:
                st = "KILLER_CONFLICT_EVENT_VS_CREDIT"
            else:
                st = "ATTRIBUTED_EVENT_AND_CREDIT_AGREE" if ksub is not None and credit is not None else "ATTRIBUTED_FROM_ONE_SOURCE"
            ri = int(round_of([r.time1])[0])
            ad = []
            if len(D) and vsub:
                ad = sorted(set(D[(D.victim_player_id == vsub) & (D.round_index == ri) & (D.time_ms <= r.time1 + tol) & D.damager_player_id.notna()].damager_player_id) - {ksub, credit})
            led.append(dict(death_event_id=r.id, damage_event_id=hit.damage_event_id if hit is not None else None, time_ms=int(r.time1), round_index=ri,
                            killer_player_id=ksub or credit, victim_player_id=vsub, killer_char_guid=kg, victim_char_guid=vg,
                            killer_basis="characterDeath.word0 (INFERRED reading) " + ("agrees with" if (ksub and credit and ksub == credit) else "vs") + " KillCreditPlayerState" if ksub else ("KillCreditPlayerState only" if credit else "none"),
                            victim_basis="characterDeath.word1 (INFERRED reading) + killing hit victim" if vsub else "none", killer_credit_player_id=credit, assist_candidate_player_ids=json.dumps(ad),
                            assist_list_raw=hit.assists_list if hit is not None else None, source_kind=hit.source_kind if hit is not None else None,
                            weapon_class=(hit.equippable_class if hit is not None else None), attribution_status=st, match_gap_ms=int(abs(hit.time_ms - r.time1)) if hit is not None else None,
                            source_ref=f"events.parquet#{r.index}", resolution_status="RESOLVED" if st.startswith("ATTRIBUTED") else "PARTIAL"))
        for h_ in (kh.itertuples() if len(kh) else []):
            if h_.damage_event_id not in used:
                led.append(dict(death_event_id=None, damage_event_id=h_.damage_event_id, time_ms=int(h_.time_ms), round_index=int(h_.round_index), killer_player_id=h_.kill_credit_player_id,
                                victim_player_id=h_.victim_player_id, killer_basis="KillCreditPlayerState only", killer_credit_player_id=h_.kill_credit_player_id, source_kind=h_.source_kind,
                                weapon_class=h_.equippable_class, attribution_status="KILLING_HIT_WITHOUT_DEATH_EVENT", source_ref=h_.source_ref, resolution_status="PARTIAL"))
        L = pd.DataFrame(led)
        if len(L):
            L = L.sort_values("time_ms", kind="stable").reset_index(drop=True); L["kill_ledger_id"] = [f"{m8}:kd:{i:05d}" for i in range(len(L))]
        emit("kill_death_ledger", L, "events.parquet+fields.parquet", "events(characterDeath) joined to killing damage hits", "one row per death event; killing hit joined by victim and time (<=tol, one-to-one); killer from event words and credit field, conflicts kept", "DERIVED")
        # combat events: raw damage hits + deaths, linked
        ce = []
        for r in (D.itertuples() if len(D) else []):
            ce.append(dict(event_type="damage_hit", time_ms=r.time_ms, round_index=r.round_index, round_ms=r.round_ms, actor_player_id=r.damager_player_id, target_player_id=r.victim_player_id,
                           target_net_guid=r.victim_actor_net_guid, source_kind=r.source_kind, source_class=r.equippable_class or r.damage_causer_class, amount=r.damage_dealt, damage_event_id=r.damage_event_id,
                           attribution_status="DAMAGER_RESOLVED" if r.damager_player_id else "DAMAGER_NOT_A_ROSTER_PLAYER", source_ref=r.source_ref))
        for r in (T["kill_death_ledger"].itertuples() if len(L) else []):
            ce.append(dict(event_type="kill" if r.death_event_id else "kill_hit_only", time_ms=r.time_ms, round_index=r.round_index, actor_player_id=r.killer_player_id, target_player_id=r.victim_player_id,
                           actor_net_guid=r.killer_char_guid, target_net_guid=r.victim_char_guid, source_kind=r.source_kind, source_class=r.weapon_class, death_event_id=r.death_event_id,
                           damage_event_id=r.damage_event_id, kill_ledger_id=r.kill_ledger_id, attribution_status=r.attribution_status, source_ref=r.source_ref))
        C_ = pd.DataFrame(ce)
        if len(C_):
            C_ = C_.sort_values(["time_ms"], kind="stable").reset_index(drop=True); C_["combat_event_id"] = [f"{m8}:ce:{i:06d}" for i in range(len(C_))]
        emit("combat_events", C_, "fields.parquet+events.parquet", "damage_events + kill_death_ledger", "normalized view; raw rows stay in damage_events and kill_death_ledger and are linked by id", "DERIVED")
        # reconciliation
        rec = []
        def add(check, scope, rnd, exp, obs, detail=""):
            diff = None if (exp is None or obs is None) else float(obs) - float(exp)
            rec.append(dict(check=check, scope=scope, round_index=rnd, expected=exp, observed=obs, difference=diff, status="MATCH" if diff == 0 else ("NOT_COMPARABLE" if diff is None else "MISMATCH"), detail=detail))
        n_death = len(dth); n_kh = len(kh) if len(kh) else 0
        add("death events vs killing hits on roster victims", "match", None, n_death, n_kh, "expected = characterDeath events; observed = hits with bDamageKilledTarget on roster characters")
        add("ledger rows with a killing hit", "match", None, n_death, int(L.damage_event_id.notna().sum() - (L.death_event_id.isna()).sum()) if len(L) else 0)
        if len(L):
            add("kill attribution agreement (event words vs KillCreditPlayerState)", "match", None, int(L.killer_credit_player_id.notna().sum()), int((L.attribution_status == "ATTRIBUTED_EVENT_AND_CREDIT_AGREE").sum()))
            for st_, n_ in L.attribution_status.value_counts().items():
                add(f"ledger status: {st_}", "match", None, None, int(n_))
            for ri in sorted(L.round_index.dropna().unique()):
                a_ = int(((L.round_index == ri) & L.death_event_id.notna()).sum()); b_ = int(((kh.round_index == ri).sum())) if len(kh) else 0
                add("deaths vs killing hits", "round", int(ri), a_, b_)
        if len(D):
            v = D[D.victim_player_id.notna()]
            add("sum DamageDealt vs sum DamageTaken on roster victims", "match", None, float(v.damage_taken.astype(float).sum()), float(v.damage_dealt.astype(float).sum()), "per-hit values; DamageTaken can differ from DamageDealt (armor/overkill); difference preserved, not forced")
            add("damage hits by source_kind", "match", None, None, len(D), json.dumps(D.source_kind.value_counts().to_dict()))
        emit("combat_reconciliation", pd.DataFrame(rec), "events.parquet+fields.parquet", "kill_death_ledger, damage_events", "counts compared; discrepancies kept", "DERIVED")
        if len(L):
            ag = int((L.attribution_status == "ATTRIBUTED_EVENT_AND_CREDIT_AGREE").sum())
            check("killer attribution", "PASS" if ag == len(L) else "WARN", f"{ag} of {len(L)} ledger rows have event-word killer == KillCreditPlayerState", "info" if ag == len(L) else "warn")
        check("deaths vs killing hits", "PASS" if n_death == n_kh else "WARN", f"{n_death} characterDeath events, {n_kh} killing hits on roster characters", "info" if n_death == n_kh else "warn")

    # ================================================================================================ UTILITY
    @step("utility")
    def _util():
        import extract_casts
        casts = extract_casts.run(E / "fields.parquet", E / "actors.parquet")
        rnd = T["rounds"].set_index("round_index")
        if len(casts):
            c = casts.copy()
            c["round"] = c["round"].astype("Int64")
            c["cast_id"] = c.caster.astype(str) + "|" + c["round"].astype(str) + "|" + c.cast_time_s.round(3).astype(str)
            c["barrier_ms"] = c["round"].map(lambda r: rnd.buy_end_ms.get(int(r)) if pd.notna(r) and int(r) in rnd.index else None)
            c["time_basis"] = c["round"].map(lambda r: rnd.buy_end_basis.get(int(r)) if pd.notna(r) and int(r) in rnd.index else "UNRESOLVED")
            c["cast_abs_ms"] = c.barrier_ms.astype("float64") + c.cast_time_s * 1000
            base = c.drop_duplicates("cast_id").copy()
            ne = c[c.tag.notna()].groupby("cast_id").size()
            ab = pd.DataFrame(dict(cast_id=base.cast_id, cast_uid_first=base.cast_uid, player_id=base.caster, agent_code=base.agent, agent_name=base.agent.map(lambda a: codes.get(a, a)),
                                   round_index=base["round"], slot=base.slot, ability_id=None, ability_name=None, round_phase=base.round_phase, cast_time_s=base.cast_time_s, barrier_ms=base.barrier_ms,
                                   cast_abs_ms=base.cast_abs_ms, time_basis=base.time_basis, cast_x=base.cast_x, cast_y=base.cast_y, cast_z=base.cast_z, destroyed_count=base.destroyed_count,
                                   n_effect_records=base.cast_id.map(ne).fillna(0).astype(int), cast_status="RECORDED_IN_ABILITYCASTSTHISROUND", replicator_actor_net_guid=base.actor_net_guid))
            ab["resolution_status"] = np.where(ab.player_id.notna() & ab.barrier_ms.notna(), "RESOLVED", "PARTIAL")
            emit("ability_casts", ab, "fields.parquet", "fields(Comp_AbilityStatisticsReplicator AbilityCastsThisRound[])", "array-position records collapsed on (caster, round, CastTime); abs time = buy-phase end + CastTime", "OBSERVED")
            T["ability_casts"].loc[T["ability_casts"].time_basis.astype(str).str.contains("INFERRED"), "evidence"] = "INFERRED"
            gap("ability_casts", "NOT_EXPOSED_BY_PARSER", "ability id/name and a Slot label table are not in the export (Slot is numeric); cast attempt, failure and interruption are not represented, only recorded casts")
        else:
            emit("ability_casts", pd.DataFrame(), "fields.parquet", "fields", "none", "OBSERVED", "NOT_PRESENT_IN_SOURCE")
            c = pd.DataFrame(columns=["cast_id"])
        # utility objects
        rx = re.compile(NC["utility_class_regex"])
        uo = opens[opens.class_name.map(lambda n: bool(rx.match(n if isinstance(n, str) else "")))].copy()
        own_tbl = C.own if hasattr(C, "own") else pd.DataFrame()
        def owner_of(row):
            if not len(own_tbl):
                return None, None, "NO_OWNERSHIP_OBSERVATIONS"
            o = own_tbl[(own_tbl.actor_instance_id == row.actor_instance_id) & own_tbl.relation.isin(["Owner", "Instigator"])]
            o = o[o.target_player_id.notna()]
            if len(o):
                f = o.sort_values("start_ms").iloc[0]
                return int(f.target_net_guid), f.target_player_id, f"{f.relation} field on the object actor (OBSERVED)"
            return None, None, "NO_OWNER_OR_INSTIGATOR_FIELD_ON_THIS_ACTOR"
        ow = uo.apply(owner_of, axis=1, result_type="expand") if len(uo) else pd.DataFrame(columns=[0, 1, 2])
        uo[["owner_net_guid", "owner_player_id", "owner_basis"]] = ow.values if len(uo) else None
        mvn = mv[~mv.character_net_guid.map(lambda g: g in subj_by_char)]
        cnt = mvn.groupby("character_net_guid").size()
        uo["n_movement_rows"] = uo.actor_net_guid.map(cnt).fillna(0).astype(int)
        def tok(n):
            m = re.match(r"^(Projectile|GameObject|Pawn|Ability)_([A-Za-z]+?)_([A-Za-z0-9]+)_", n or "")
            return (m.group(1), m.group(2), m.group(3)) if m else (None, None, None)
        tk = uo.class_name.map(tok)
        uo["object_role"] = tk.map(lambda x: x[0]); uo["agent_code_from_class"] = tk.map(lambda x: x[1]); uo["slot_token"] = tk.map(lambda x: x[2])
        uo["utility_object_id"] = [f"{m8}:uo:{i:05d}" for i in range(len(uo))]
        uo["round_index"] = round_of(uo.time_ms)
        win = NC["utility_cast_link_window_ms"]
        cand_ids, cid = [], []
        ab_ = T["ability_casts"]
        for r in uo.itertuples():
            cl_ = []
            if len(ab_) and r.owner_player_id:
                x = ab_[(ab_.player_id == r.owner_player_id) & (ab_.round_index == r.round_index) & ((ab_.cast_abs_ms.astype(float) - r.time_ms).abs() <= win)]
                cl_ = list(x.cast_id)
            cand_ids.append(json.dumps(cl_)); cid.append(cl_[0] if len(cl_) == 1 else None)
        uo["candidate_cast_ids"] = cand_ids; uo["cast_id"] = cid
        uo = uo.rename(columns={"time_ms": "open_ms", "spawn_vx": "spawn_vx", "spawn_vy": "spawn_vy", "spawn_vz": "spawn_vz"})
        uo["source_ref"] = "actors.parquet#" + uo.index.astype(str)
        uo["resolution_status"] = np.where(uo.owner_player_id.notna(), "OWNER_RESOLVED", "OWNER_UNRESOLVED")
        emit("utility_objects", uo, "actors.parquet+fields.parquet", "actors(open/close) + fields(Owner/Instigator)", "ability-related actor classes; owner from Owner/Instigator field on the same actor; cast link only when exactly one cast of that owner/round lies within the time window (INFERRED)", "OBSERVED")
        T["utility_objects"].loc[T["utility_objects"].cast_id.notna(), "evidence"] = "INFERRED"
        U = T["utility_objects"]
        # observations: spawn, movement, close
        ob = []
        for r in U.itertuples():
            ob.append(dict(utility_object_id=r.utility_object_id, actor_net_guid=r.actor_net_guid, observation="spawn", time_ms=r.open_ms, round_index=r.round_index, pos_x=r.spawn_x, pos_y=r.spawn_y, pos_z=r.spawn_z, vel_x=r.spawn_vx, vel_y=r.spawn_vy, vel_z=r.spawn_vz, source_ref=r.source_ref))
            if pd.notna(r.close_ms):
                ob.append(dict(utility_object_id=r.utility_object_id, actor_net_guid=r.actor_net_guid, observation="close", time_ms=r.close_ms, round_index=int(round_of([r.close_ms])[0]), source_ref=r.source_ref))
        obdf = pd.DataFrame(ob)
        mm = mvn[mvn.character_net_guid.isin(U.actor_net_guid)].merge(U[["utility_object_id", "actor_net_guid", "open_ms", "close_ms"]], left_on="character_net_guid", right_on="actor_net_guid")
        mm = mm[(mm.time_ms >= mm.open_ms) & (mm.close_ms.isna() | (mm.time_ms <= mm.close_ms + 1))]
        if len(mm):
            mo = pd.DataFrame(dict(utility_object_id=mm.utility_object_id, actor_net_guid=mm.character_net_guid, observation="movement", time_ms=mm.time_ms, round_index=round_of(mm.time_ms), round_ms=round_ms(mm.time_ms),
                                   pos_x=mm.pos_x, pos_y=mm.pos_y, pos_z=mm.pos_z, yaw=mm.yaw, pitch=mm.pitch, vel_x=mm.vel_x, vel_y=mm.vel_y, vel_z=mm.vel_z, movement_row_ref="movement.parquet#" + mm._row.astype(str), source_ref="movement.parquet#" + mm._row.astype(str)))
            obdf = pd.concat([obdf, mo], ignore_index=True)
        emit("utility_object_observations", obdf, "actors.parquet+movement.parquet", "actors, movement", "spawn/close from actor records; movement rows of the same guid inside the instance window", "OBSERVED")
        gap("utility_object_observations", "NOT_EXPOSED_BY_PARSER", "per-object state fields (activation, pulse, trigger, hit) are not decoded into the export; only spawn, movement and close are observable")
        # effects & targets
        if len(c) and c.tag.notna().any():
            ef = c[c.tag.notna()].copy()
            ef["effect_key"] = ef.cast_id + "|" + ef.effect_idx.astype(str)
            g = ef.groupby("effect_key")
            e1 = g.agg(cast_id=("cast_id", "first"), player_id=("caster", "first"), agent_code=("agent", "first"), round_index=("round", "first"), effect_idx=("effect_idx", "first"), statistic=("tag", "first"),
                       statistic_id=("tag_id", "first"), value=("tag_value", "max"), effect_time_s=("effect_time_s", "max"), n_targets=("target", lambda s: int(s.notna().sum())), sum_target_value=("target_value", lambda s: float(s.fillna(0).sum()))).reset_index()
            e1["effect_category"] = e1.statistic.map(lambda s: NC["effect_category"].get(s, "unmapped"))
            e1["effect_id"] = [f"{m8}:fx:{i:05d}" for i in range(len(e1))]
            e1["effect_status"] = np.where(e1.effect_category == "unmapped", "STATISTIC_NAME_NOT_MAPPED", "RECORDED")
            emit("utility_effects", e1.drop(columns=["effect_key"]), "fields.parquet", "fields(AbilityCastsThisRound[].Effects[])", "one row per (cast, Effects[] index); Statistic is a per-cast aggregate, not a per-target event", "OBSERVED")
            tg = ef[ef.target.notna()].merge(e1[["effect_key", "effect_id"]] if "effect_key" in e1 else e1[["effect_id"]].assign(effect_key=None), on="effect_key", how="left") if False else None
            ef = ef.merge(e1[["cast_id", "effect_idx", "effect_id"]], on=["cast_id", "effect_idx"], how="left")
            tg = ef[ef.target.notna()].drop_duplicates(["effect_id", "target", "target_idx"]).copy()
            tgt = pd.DataFrame(dict(effect_id=tg.effect_id, cast_id=tg.cast_id, target_player_state_guid=tg.target.astype(int), target_player_id=tg.target.map(pid_ps),
                                    target_team_id=tg.target.map(lambda v: team_of.get(pid_ps(v))), caster_team_id=tg.caster.map(team_of), target_value=tg.target_value, target_idx=tg.target_idx))
            tgt["relation_to_caster"] = np.where(tgt.target_team_id.isna() | tgt.caster_team_id.isna(), "UNRESOLVED", np.where(tgt.target_player_id == tg.caster.values, "self", np.where(tgt.target_team_id == tgt.caster_team_id, "teammate", "opponent")))
            tgt["target_status"] = np.where(tgt.target_player_id.notna(), "RESOLVED", "TARGET_NOT_A_ROSTER_PLAYERSTATE")
            tgt["target_id"] = [f"{m8}:tg:{i:05d}" for i in range(len(tgt))]
            tgt["resolution_status"] = tgt.target_status
            emit("utility_targets", tgt, "fields.parquet", "fields(AbilityCastsThisRound[].Effects[].AffectedTargetsArray[])", "one row per affected target entry; PlayerState guid resolved through the roster", "OBSERVED")
            check("utility target resolution", "PASS" if (tgt.target_player_id.notna().all()) else "WARN", f"{int(tgt.target_player_id.isna().sum())} of {len(tgt)} targets not a roster PlayerState", "info" if tgt.target_player_id.notna().all() else "warn")
        else:
            emit("utility_effects", pd.DataFrame(), "fields.parquet", "fields", "none", "OBSERVED", "NOT_PRESENT_IN_SOURCE")
            emit("utility_targets", pd.DataFrame(), "fields.parquet", "fields", "none", "OBSERVED", "NOT_PRESENT_IN_SOURCE")
        # lifecycle events from evidence only
        lf = []
        for r in T["ability_casts"].itertuples():
            lf.append(dict(stage="cast_recorded", time_ms=r.cast_abs_ms, player_id=r.player_id, agent_code=r.agent_code, cast_id=r.cast_id, detail=f"slot {r.slot}; CastTime {r.cast_time_s:.3f}s after buy-phase end ({r.time_basis})" if pd.notna(r.cast_time_s) else None,
                           pos_x=r.cast_x, pos_y=r.cast_y, pos_z=r.cast_z, source_ref=r.source_ref, evidence="OBSERVED" if "OBSERVED" in str(r.time_basis) else "INFERRED"))
        for r in U.itertuples():
            lf.append(dict(stage="projectile_launch" if r.object_role == "Projectile" else "object_creation", time_ms=r.open_ms, player_id=r.owner_player_id, agent_code=r.agent_code_from_class, cast_id=r.cast_id, utility_object_id=r.utility_object_id,
                           actor_net_guid=r.actor_net_guid, detail=r.class_name, pos_x=r.spawn_x, pos_y=r.spawn_y, pos_z=r.spawn_z, source_ref=r.source_ref))
            if pd.notna(r.close_ms):
                lf.append(dict(stage="object_closed", time_ms=r.close_ms, player_id=r.owner_player_id, agent_code=r.agent_code_from_class, cast_id=r.cast_id, utility_object_id=r.utility_object_id, actor_net_guid=r.actor_net_guid,
                               detail=r.class_name + " (close cause not exposed: destruction, expiry, impact and removal are indistinguishable)", source_ref=r.source_ref))
            if r.n_movement_rows:
                x = mvn[(mvn.character_net_guid == r.actor_net_guid) & (mvn.time_ms >= r.open_ms)]
                if len(x):
                    lf.append(dict(stage="object_movement_first", time_ms=int(x.time_ms.min()), player_id=r.owner_player_id, utility_object_id=r.utility_object_id, actor_net_guid=r.actor_net_guid, value=r.n_movement_rows, detail="first native movement sample; count in value", source_ref="movement.parquet#" + str(int(x._row.iloc[0]))))
        for r in (T["utility_effects"].itertuples() if len(T["utility_effects"]) else []):
            cr = T["ability_casts"][T["ability_casts"].cast_id == r.cast_id]
            t0 = (cr.barrier_ms.iloc[0] + r.effect_time_s * 1000) if len(cr) and pd.notna(r.effect_time_s) and pd.notna(cr.barrier_ms.iloc[0]) else None
            lf.append(dict(stage=f"effect_{r.effect_category}", time_ms=t0, player_id=r.player_id, agent_code=r.agent_code, cast_id=r.cast_id, value=r.value, detail=f"{r.statistic}: per-cast aggregate; effect_id={r.effect_id}", evidence="DERIVED", source_ref=r.source_ref))
        for r in (T["utility_targets"].itertuples() if len(T["utility_targets"]) else []):
            lf.append(dict(stage="target_listed", time_ms=None, cast_id=r.cast_id, target_player_id=r.target_player_id, target_net_guid=r.target_player_state_guid, value=r.target_value, detail=f"effect_id={r.effect_id}; {r.relation_to_caster}", source_ref=r.source_ref))
        if len(C.D):
            ud = C.D[(C.D.source_kind == "utility_damage")]
            byguid = U.drop_duplicates("actor_net_guid").set_index("actor_net_guid")
            for r in ud.itertuples():
                g_ = r.damage_causer_net_guid
                o = byguid.loc[int(g_)] if pd.notna(g_) and int(g_) in byguid.index else None
                lf.append(dict(stage="damage", time_ms=r.time_ms, player_id=r.damager_player_id or (o.owner_player_id if o is not None else None), utility_object_id=o.utility_object_id if o is not None else None, cast_id=o.cast_id if o is not None else None,
                               actor_net_guid=int(g_) if pd.notna(g_) else None, target_player_id=r.victim_player_id, target_net_guid=r.victim_actor_net_guid, value=r.damage_dealt, detail=f"DamageCauser {r.damage_causer_class}; damage_event_id={r.damage_event_id}", source_ref=r.source_ref))
        LF = pd.DataFrame(lf)
        if len(LF):
            LF["round_index"] = np.where(LF.time_ms.notna(), round_of(LF.time_ms.fillna(0)), None); LF["round_ms"] = np.where(LF.time_ms.notna(), round_ms(LF.time_ms.fillna(0)), None)
            LF = LF.sort_values("time_ms", kind="stable", na_position="last").reset_index(drop=True); LF["lifecycle_event_id"] = [f"{m8}:lc:{i:06d}" for i in range(len(LF))]
        emit("utility_lifecycle_events", LF, "fields.parquet+actors.parquet+movement.parquet", "ability_casts, utility_objects, utility_effects, utility_targets, damage_events", "one row per stage that has evidence; stages without evidence are NOT created", "OBSERVED")
        if len(LF):
            T["utility_lifecycle_events"].loc[T["utility_lifecycle_events"].stage.str.startswith(("effect_", "target_")), "resolution_status"] = "AGGREGATE_NOT_TARGET_EVENT"
        for s_ in ("cast_attempt", "failed_or_interrupted_cast", "activation", "trigger", "potential_exposure", "confirmed_effect_application_per_target_time", "pulse", "submunition", "expiration_cause"):
            gap("utility_lifecycle_events", "NOT_EXPOSED_BY_PARSER", f"stage '{s_}' has no decoded source field in the export; not inferred from neighbouring records")
        # statistic observations
        stt = F[F.group_path.str.contains("Comp_AbilityStatisticsReplicator") & ~F.group_path.str.endswith("ClassNetCache")].copy()
        stt["field_row"] = stt.index
        stt["serialized_field_name"] = stt.field_name
        stt["array_path"] = stt.field_name.str.replace(r"_\d+_[0-9A-F]{32}$", "", regex=True)
        stt["field_leaf"] = stt.array_path.str.replace(r"^.*\.", "", regex=True)
        stt["value"] = coalesce(stt).map(lambda v: None if v is None else str(v)); stt["value_type"] = vtype(stt)
        stt["round_index"] = round_of(stt.time_ms)
        stt["player_id"] = None
        sem = NC["statistic_semantics"]
        stt["stat_kind"] = stt.field_leaf.map(lambda s: sem.get(s, sem["default"])["kind"])
        stt["resets_by_round"] = stt.field_leaf.map(lambda s: sem.get(s, sem["default"])["resets_by_round"])
        stt["cumulative"] = stt.field_leaf.map(lambda s: sem.get(s, sem["default"])["cumulative"])
        stt["ability_slot"] = None
        stt = stt.sort_values(["actor_net_guid", "array_path", "time_ms", "packet_id"])
        is_cnt = stt.stat_kind.isin(["counter", "snapshot_array_size"]) & stt.value_i64.notna()
        prev = stt.groupby(["actor_net_guid", "array_path"]).value_i64.shift(1)
        stt["counter_delta"] = np.where(is_cnt & prev.notna(), stt.value_i64 - prev, np.nan)
        stt["delta_status"] = np.where(~is_cnt, "NOT_A_COUNTER_BY_CONFIG", np.where(prev.isna(), "FIRST_OBSERVATION", np.where(stt.counter_delta < 0, "DECREASE_RESET_OR_ARRAY_REPLACED", "SAME_ACTOR_SAME_FIELD")))
        stt["source_ref"] = "fields.parquet#" + stt.field_row.astype(str)
        stt["resolution_status"] = "RAW_PRESERVED_NOT_INTERPRETED"
        emit("utility_statistics", stt[["field_row", "time_ms", "packet_id", "channel_index", "actor_net_guid", "object_net_guid", "group_path", "serialized_field_name", "field_leaf", "array_path", "value", "value_type", "round_index", "player_id", "ability_slot",
                                       "stat_kind", "resets_by_round", "cumulative", "counter_delta", "delta_status", "source_ref"]].sort_values(["time_ms", "packet_id"]),
             "fields.parquet", "fields(Comp_AbilityStatisticsReplicator.*)", "raw observations; kind/reset/cumulative come only from pipeline_config statistic_semantics (default unknown); delta only for same actor and same field", "OBSERVED")
        gap("utility_statistics", "UNRESOLVED", "whether each Effects[].Value is a counter or an event, and whether it resets, is not stated by the export; stat_kind stays 'unknown' except where configured")
        # reconciliation
        rc = []
        def radd(check, pid, ri, stat, a, b, detail):
            diff = None if a is None or b is None else float(a) - float(b)
            rc.append(dict(check=check, player_id=pid, round_index=ri, statistic=stat, observed_a=a, observed_b=b, difference=diff, status="NOT_COMPARABLE" if diff is None else ("MATCH" if diff == 0 else "MISMATCH"), detail=detail))
        EF = T["utility_effects"]; TG = T["utility_targets"]
        if len(EF):
            for r in EF.itertuples():
                radd("effect value vs listed targets", r.player_id, r.round_index, r.statistic, r.value, r.n_targets, f"effect_id={r.effect_id}; Value is an aggregate, targets listed are AffectedTargetsArray entries; they are not assumed equal")
            for (pid, ri, st_), x in EF.groupby(["player_id", "round_index", "statistic"]):
                radd("sum of effect values vs sum of per-target values", pid, ri, st_, float(x.value.sum()), float(x.sum_target_value.sum()), "same cast records")
        ac = T["ability_casts"]
        if len(ac) and len(stt):
            sz = stt[stt.field_leaf == "AbilityCastsThisRound"]
            for (g_, ri), x in sz.groupby(["actor_net_guid", "round_index"]):
                last = x.sort_values("time_ms").iloc[-1]
                pl_ = ac[(ac.replicator_actor_net_guid == g_) & (ac.round_index == ri)]
                if len(pl_):
                    radd("AbilityCastsThisRound size (last observed) vs distinct recorded casts", pl_.player_id.iloc[0], ri, "AbilityCastsThisRound", float(last.value) if last.value is not None else None, len(pl_), "array size can count reused positions; difference preserved")
        U_ = T["utility_objects"]
        radd("utility objects with a unique cast link", None, None, "objects", int(U_.cast_id.notna().sum()) if len(U_) else 0, len(U_), "objects whose owner and time window give exactly one candidate cast")
        emit("utility_statistic_reconciliation", pd.DataFrame(rc), "fields.parquet", "utility_effects, utility_targets, utility_statistics", "pairs compared inside one cast or one actor; no cross-actor or cross-packet pairing", "DERIVED")
        # unresolved
        ur = []
        for r in U_.itertuples():
            if pd.isna(r.owner_player_id):
                ur.append(dict(record_type="utility_object_owner", ref_id=r.utility_object_id, time_ms=r.open_ms, round_index=r.round_index, reason=r.owner_basis, needed_to_resolve="decoded Owner/Instigator on projectile and gameobject actors (not present for this class in fields.parquet)"))
            if pd.notna(r.open_ms) and pd.isna(r.close_ms):
                ur.append(dict(record_type="utility_object_no_close", ref_id=r.utility_object_id, time_ms=r.open_ms, round_index=r.round_index, reason="no close record", needed_to_resolve="close may be dropped by the parser or persist to replay end"))
        for r in (EF.itertuples() if len(EF) else []):
            if r.effect_category == "unmapped":
                ur.append(dict(record_type="statistic_name_unmapped", ref_id=r.effect_id, round_index=r.round_index, reason=f"statistic '{r.statistic}' has no effect_category in config", needed_to_resolve="add mapping after the statistic is understood"))
        for r in (TG.itertuples() if len(TG) else []):
            if r.target_status != "RESOLVED":
                ur.append(dict(record_type="utility_target", ref_id=r.target_id, reason=r.target_status, needed_to_resolve="target guid is not a roster PlayerState"))
        for r in (ac.itertuples() if len(ac) else []):
            if pd.isna(r.player_id):
                ur.append(dict(record_type="cast_without_player", ref_id=r.cast_id, round_index=r.round_index, reason="Player field not observed for this cast record", needed_to_resolve="a later snapshot carrying Player"))
        emit("unresolved_utility_records", pd.DataFrame(ur), "derived", "utility_*", "records that did not resolve, with the reason and what would resolve them", "DERIVED", "UNRESOLVED")

    # ================================================================================================ UNRESOLVED IDENTITIES
    @step("unresolved")
    def _unres():
        rows = []
        mvu = T["movement"][T["movement"].mover_kind == "character_not_in_roster"] if "movement" in T else pd.DataFrame()
        for g, x in (mvu.groupby("mover_net_guid") if len(mvu) else []):
            rows.append(dict(subject_kind="character_mover_not_in_roster", net_guid=int(g), class_path=cls_of_guid.get(int(g)), first_seen_ms=int(x.time_ms.min()), n_records=len(x), reason="character-class mover whose guid is not in manifest players[].character_net_guids", needed_to_resolve="manifest roster entry for this guid (replacement/reconnect?)"))
        oe = opens[opens.class_path.str.contains("OwnerExclusivePlayerInfo")]
        for r in oe.itertuples():
            rows.append(dict(subject_kind="combat_report_owner_actor", net_guid=int(r.actor_net_guid), class_path=r.class_path, first_seen_ms=int(r.time_ms), n_records=None, reason="OwnerExclusivePlayerInfo has no field naming its player; the legacy shard resolves it by damage reciprocity (ADR-001)", needed_to_resolve="a decoded Owner/PlayerState reference on this actor, or reciprocity success (see shard)"))
        if hasattr(C, "own") and len(C.own):
            o = C.own[C.own.target_player_id.isna() & C.own.relation.isin(["Owner", "Instigator"]) & C.own.player_id.isna()]
            for (cls_, rel), x in o.groupby(["actor_class", "relation"]):
                rows.append(dict(subject_kind="ownership_target_not_roster", net_guid=None, class_path=cls_, first_seen_ms=int(x.start_ms.min()), n_records=len(x), reason=f"{rel} points at a non-roster entity", needed_to_resolve="none if intended (world, map object); otherwise roster entry"))
        emit("unresolved_identities", pd.DataFrame(rows), "multiple", "actors, movement, fields", "identity references that did not resolve to a roster player", "DERIVED", "UNRESOLVED")

    # roster (per player per round)
    @step("roster")
    def _roster():
        rr = []
        for r in C.P.itertuples():
            for x in T["rounds"].itertuples():
                rr.append(dict(player_id=r.player_id, round_index=x.round_index, team_id=r.team_id, agent_code=r.agent_code, agent_name=r.agent_name, half_index=x.half_index,
                               sides_swapped_vs_first_half=bool(x.half_index % 2 == 1), side=None, side_status="UNRESOLVED: attacker/defender not read; swap flag only"))
        emit("roster", pd.DataFrame(rr), "derived", "players x rounds", "one row per player and round; side is not guessed", "DERIVED", "PARTIAL")

    # ================================================================================================ INDEXES
    @step("indexes")
    def _idx():
        pp = T["player_positions"]
        if len(pp):
            pp_ = pp.reset_index().rename(columns={"index": "_pos"})
            g = pp_.groupby(["player_id", "round_index", "mover_net_guid"])
            mi = g.agg(n_rows=("time_ms", "size"), first_ms=("time_ms", "min"), last_ms=("time_ms", "max"), pos_row_start=("_pos", "min"), pos_row_end=("_pos", "max"), team_id=("team_id", "first")).reset_index()
            mi["map_code"] = C.map_code; mi["source_table"] = "player_positions"
        else:
            mi = pd.DataFrame()
        emit("map_position_index", mi, "player_positions.parquet", "player_positions", "Replay -> Map -> Round -> Player -> Actor -> Position row range (rows are contiguous per player, sorted by time)", "DERIVED")
        ul = T["utility_lifecycle_events"]; ue = T["utility_effects"]; ut = T["utility_targets"]
        rows = []
        for r in ul.itertuples():
            rows.append(dict(player_id=r.player_id, round_index=r.round_index, cast_id=r.cast_id, utility_object_id=r.utility_object_id, lifecycle_event_id=r.lifecycle_event_id, stage=r.stage, time_ms=r.time_ms,
                             target_player_id=r.target_player_id))
        X = pd.DataFrame(rows)
        if len(X) and len(ue):
            em = ue.set_index("cast_id").effect_id.groupby(level=0).apply(list).to_dict()
            X["effect_id"] = X.apply(lambda r: r.cast_id and em.get(r.cast_id) and (em[r.cast_id][0] if r.stage.startswith("effect_") else None), axis=1)
        emit("utility_lifecycle_index", X, "derived", "utility_*", "Replay -> Round -> Player -> Cast -> Object -> Lifecycle -> Effect -> Target flattened; blanks mean no evidence of that link", "DERIVED")
        if len(ut) and len(T["utility_lifecycle_index"]):
            tx = ut.rename(columns={"target_player_id": "tp"})[["cast_id", "effect_id", "target_id", "tp"]]
            ext = tx.merge(ue[["effect_id", "player_id", "round_index"]], on="effect_id", how="left")
            ext = pd.DataFrame(dict(player_id=ext.player_id, round_index=ext.round_index, cast_id=ext.cast_id, effect_id=ext.effect_id, target_id=ext.target_id, target_player_id=ext.tp))
            ext.insert(0, "match_id", match_id); ext.insert(1, "record_id", [f"{m8}:utility_lifecycle_index:{len(T['utility_lifecycle_index']) + i:07d}" for i in range(len(ext))])
            for k, v in (("source_file", "derived"), ("source_table", "utility_*"), ("source_ref", None), ("transformation", "effect->target rows"), ("evidence", "DERIVED"), ("resolution_status", "RESOLVED")):
                ext[k] = v
            T["utility_lifecycle_index"] = pd.concat([T["utility_lifecycle_index"], ext.reindex(columns=T["utility_lifecycle_index"].columns)], ignore_index=True)

    # ================================================================================================ run + provenance
    for fn_name in ("_identity", "_own", "_map", "_events", "_move", "_combat", "_util", "_unres", "_roster", "_idx"):
        pass  # decorators already ran each step in order of definition below

    return diag, T, C, dict(match_id=match_id, m8=m8, run_id=run_id, t0=t0, man=man, check=check, gap=gap, emit=emit)


def finalize(diag, T, C, ctx, out, cfg, source_sha256=None):
    O = Path(out)
    match_id, m8 = ctx["match_id"], ctx["m8"]
    emit = ctx["emit"]
    # make sure every documented table exists
    for name in S:
        if name in ("normalized_match", "event_provenance_index"):
            continue
        if name not in T:
            ctx["gap"](name, "UNRESOLVED", "table not produced in this run (a step failed; see steps)")
            emit(name, pd.DataFrame(), "none", "none", "not produced", "OBSERVED", "NOT_PRODUCED")
    # provenance index over every record-bearing table
    pr = []
    time_cols = ["time_ms", "open_ms", "start_ms", "first_ms", "cast_abs_ms", "level_time_ms", "round_started_ms"]
    guid_cols = ["actor_net_guid", "mover_net_guid", "victim_actor_net_guid", "target_net_guid", "subject_net_guid", "playerstate_actor_net_guid", "damage_causer_net_guid", "net_guid", "target_player_state_guid"]
    for name, df in T.items():
        if name in ("event_provenance_index",) or len(df) == 0:
            continue
        if name in cfg["normalize"].get("provenance_table_level_only", []):
            pr.append(pd.DataFrame([dict(table=name, record_id=f"{m8}:{name}:*", source_file=df.source_file.iloc[0], source_table=df.source_table.iloc[0], source_ref=f"per-row: column source_ref in {name}.parquet ({len(df)} rows)",
                                         original_time_ms=None, original_actor_ids=None, transformation=df.transformation.iloc[0], evidence="mixed: see evidence column in the table", resolution_status="mixed: see resolution_status column in the table")]))
            continue
        tc = next((c for c in time_cols if c in df.columns), None)
        gc = [c for c in guid_cols if c in df.columns]
        ids = df[gc].apply(lambda r: json.dumps({k: (None if pd.isna(v) else (int(v) if isinstance(v, (int, float, np.integer, np.floating)) else str(v))) for k, v in r.items()}), axis=1) if gc else pd.Series([None] * len(df))
        pr.append(pd.DataFrame(dict(table=name, record_id=df.record_id, source_file=df.source_file, source_table=df.source_table, source_ref=df.source_ref, original_time_ms=df[tc] if tc else None,
                                    original_actor_ids=ids.to_numpy(), transformation=df.transformation, evidence=df.evidence, resolution_status=df.resolution_status)))
    PI = pd.concat(pr, ignore_index=True) if pr else pd.DataFrame(columns=S["event_provenance_index"])
    PI.insert(0, "match_id", match_id); PI.insert(1, "provenance_id", [f"{m8}:prov:{i:08d}" for i in range(len(PI))])
    T["event_provenance_index"] = PI
    # table status + normalized_match
    man = ctx["man"]
    rows = []
    for name in S:
        if name == "normalized_match":
            continue
        n = len(T[name]) if name in T else 0
        st = "POPULATED" if n else "EMPTY"
        note = next((g["note"] for g in diag["gaps"] if g["table"] == name), "")
        code = next((g["code"] for g in diag["gaps"] if g["table"] == name), None)
        if not n:
            st = f"EMPTY_{code or 'NO_EVIDENCE_IN_EXPORT'}"
        elif code:
            st = f"POPULATED_WITH_GAPS({code})"
        rows.append(dict(table=name, rows=n, coverage_status=st, note=note))
    NM = pd.DataFrame(rows)
    NM.insert(0, "match_id", match_id)
    NM.insert(1, "record_id", [f"{m8}:normalized_match:{i:03d}" for i in range(len(NM))])
    for k, v in (("source_file", "derived"), ("source_table", "all"), ("source_ref", None), ("transformation", "table inventory"), ("evidence", "DERIVED"), ("resolution_status", "RESOLVED")):
        NM[k] = v
    T["normalized_match"] = NM
    # one-row match header (meta) saved as part of the package
    md = T["map_metadata"].iloc[0] if len(T["map_metadata"]) else {}
    hdr = dict(match_id=match_id, run_id=ctx["run_id"], schema_version=SCHEMA, source_build=man.get("replay_build"), duration_ms=man.get("duration_ms"), map_code=md.get("map_code") if len(T["map_metadata"]) else None,
               map_identity_status=md.get("map_identity_status") if len(T["map_metadata"]) else None, n_players=len(T["players"]), n_rounds=len(T["rounds"]), n_death_events=int((T["events"].event_group == "characterDeath").sum()) if len(T["events"]) else 0,
               n_movement_rows=len(T["movement"]), source_sha256=source_sha256, partially_resolved=bool(any(not s["ok"] for s in diag["steps"].values()) or (T["unresolved_identities"].shape[0] > 0)))
    # write
    wrote = {}
    for name, df in T.items():
        for c in df.columns:
            if df[c].dtype == object:
                if df[c].map(lambda v: isinstance(v, (list, dict, np.ndarray))).any():
                    df[c] = df[c].map(lambda v: json.dumps(v, default=str) if isinstance(v, (list, dict, np.ndarray)) else v)
                else:
                    non = df[c].dropna()
                    if len(non) and non.map(lambda v: isinstance(v, (bool, np.bool_))).all():
                        df[c] = df[c].astype("boolean")
                    elif len(non) and non.map(lambda v: isinstance(v, (int, float, np.integer, np.floating)) and not isinstance(v, (bool, np.bool_))).all():
                        df[c] = pd.to_numeric(df[c], errors="coerce")
                    elif len(non) and non.map(lambda v: isinstance(v, str)).all():
                        pass
                    elif len(non):
                        df[c] = df[c].map(lambda v: None if (v is None or (isinstance(v, float) and np.isnan(v))) else str(v))
        fp = O / f"{name}.parquet"
        df.to_parquet(fp, index=False, compression="zstd")
        wrote[name] = dict(rows=len(df), bytes=fp.stat().st_size, sha256=hashlib.sha256(fp.read_bytes()).hexdigest())
    json.dump(hdr, open(O / "match_header.json", "w"), indent=2, default=str)
    diag["tables"] = {k: dict(rows=v["rows"], coverage_status=NM.set_index("table").coverage_status.get(k)) for k, v in wrote.items() if k != "normalized_match"}
    diag["secs_total"] = round(time.time() - ctx["t0"], 1)
    diag["failed_steps"] = [k for k, v in diag["steps"].items() if not v["ok"]]
    json.dump(diag, open(O / "parser_diagnostics.json", "w"), indent=2, default=str)
    manifest = dict(schema_version=SCHEMA, match_id=match_id, run_id=ctx["run_id"], tables=wrote)
    json.dump(manifest, open(O / "normalized_manifest.json", "w"), indent=2)
    return wrote, hdr


def crosscheck_shard(diag, T, ctx, shard):
    """Compare the ledger with the legacy shard's reciprocity-derived kills. Differences are reported, never forced."""
    try:
        k = pd.read_parquet(Path(shard) / "kills.parquet")
        L = T["kill_death_ledger"]; L = L[L.death_event_id.notna()]
        a = set(zip(L.round_index.astype(int), L.killer_player_id, L.victim_player_id))
        b = set(zip(k.rnd.astype(int), k.killer, k.victim))
        st = "MATCH" if a == b else "MISMATCH"
        ctx["check"]("ledger vs legacy shard kills", "PASS" if st == "MATCH" else "WARN", f"ledger {len(a)} kills, shard {len(b)} kills, only-in-ledger {len(a - b)}, only-in-shard {len(b - a)}", "info" if st == "MATCH" else "warn")
        T["combat_reconciliation"] = pd.concat([T["combat_reconciliation"], pd.DataFrame([dict(
            match_id=T["combat_reconciliation"].match_id.iloc[0] if len(T["combat_reconciliation"]) else None,
            record_id=f"{ctx['m8']}:combat_reconciliation:shard", check="ledger vs legacy shard kills (round,killer,victim)", scope="match", expected=len(b), observed=len(a),
            difference=len(a) - len(b), status=st, detail=f"only-in-ledger {sorted(map(str, a - b))[:5]}; only-in-shard {sorted(map(str, b - a))[:5]}",
            source_file="shard/kills.parquet", source_table="kills", transformation="set comparison", evidence="DERIVED", resolution_status="RESOLVED")])], ignore_index=True)
    except Exception as e:
        ctx["check"]("ledger vs legacy shard kills", "SKIPPED", str(e)[:200], "warn")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("export"); ap.add_argument("out")
    ap.add_argument("--config", default=str(HERE / "pipeline_config.json"))
    ap.add_argument("--source-sha256"); ap.add_argument("--run-id"); ap.add_argument("--codenames"); ap.add_argument("--map-registry"); ap.add_argument("--lookup", help="accepted for compatibility with batch_process; names come from codenames.json")
    ap.add_argument("--shard", help="optional legacy shard dir; its kills.parquet is cross-checked against the ledger")
    a = ap.parse_args()
    cfg = json.load(open(a.config))
    mr = a.map_registry or str((HERE.parent / cfg["paths"]["map_registry"]))
    diag, T, C, ctx = run(a.export, a.out, cfg, a.source_sha256, a.run_id, a.codenames, mr if Path(mr).is_file() else None)
    if a.shard:
        crosscheck_shard(diag, T, ctx, a.shard)
    wrote, hdr = finalize(diag, T, C, ctx, a.out, cfg, a.source_sha256)
    print(json.dumps({k: v["rows"] for k, v in wrote.items()}))
    print("failed steps:", diag["failed_steps"] or "none")
    sys.exit(0)


if __name__ == "__main__":
    main()
