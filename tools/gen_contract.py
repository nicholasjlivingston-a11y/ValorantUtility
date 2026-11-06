#!/usr/bin/env python3
"""Write docs/DATA_CONTRACT.md from the schema dictionary in parser/normalize.py (so the contract cannot drift from the code)."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "parser"))
import normalize

D = {
 "players": ("one row per roster player", "manifest players + actors + fields(Controller)", "Identity, agent from character class, team from PlayerState GUID blocks (DERIVED)."),
 "teams": ("one row per team", "manifest players", "Team labels A/B are blocks of PlayerState GUIDs, not a replicated team id. Side per team is UNRESOLVED."),
 "agents": ("one row per player agent", "actors class path", "Codename from /Game/Characters/<code>/; public name only where codenames.json maps it."),
 "actors": ("one row per actor instance (guid reuse gets #n)", "actors.parquet", "Open/close, class, kind, spawn position, round at open."),
 "actor_lifecycle": ("one row per open/close record", "actors.parquet", "Raw lifecycle with instance id and round clock."),
 "netguid_mappings": ("one row per net guid", "net_guids.parquet", "Path, outer guid and full path."),
 "actor_ownership_intervals": ("one row per relation interval", "fields Owner/Instigator/Controller/PossessedCharacter/Possessed", "Start/end of each relation on an actor instance; includes possession changes."),
 "identity_crosswalk": ("one row per identifier per player", "manifest + fields", "subject uuid, PlayerState guid, character/pawn guids, controller guids, characterId, codename, possession changes."),
 "roster": ("player x round", "derived", "Team, agent, half and swap flag. side is never guessed."),
 "unresolved_identities": ("one row per unresolved reference", "actors/movement/fields", "What did not resolve and what would resolve it."),
 "map_metadata": ("one row per level observed", "manifest level_names_and_times", "Map code, level path, name only if the map registry matches."),
 "coordinate_systems": ("one row", "convention", "Documented Unreal convention, status CONVENTION_NOT_VERIFIED_FROM_REPLAY, transformations_applied none."),
 "movement": ("one row per native movement sample (no resampling)", "movement.parquet", "All movers, with round clock, mover kind, player id when roster."),
 "player_positions": ("one row per roster movement sample", "movement.parquet", "Adds dt, displacement, speed (only where 0<dt<=limit), yaw/pitch change. Native rate."),
 "position_coverage": ("player-round, actor, and match rows", "movement.parquet", "Sampling intervals, gaps, attribution coverage."),
 "position_anomalies": ("one row per flag", "movement.parquet", "Flags only; thresholds in pipeline_config.json."),
 "rounds": ("one row per round", "events + GameState RoundResults", "Start, result-observed time, buy-phase end (OBSERVED from ClientBuyPhaseEnd), half, switch, winner label/role."),
 "events": ("one row per event", "events.parquet", "All events with global and round clock. packet/channel/tick are NOT_EXPOSED_BY_PARSER for events."),
 "event_payloads": ("one row per event", "events.raw_payload", "Raw payload hex and words; characterDeath word0/word1 interpreted as killer/victim character guid (INFERRED, checked against kill credit)."),
 "replicated_fields": ("one row per selected field observation", "fields.parquet", "Fields matching config field_patterns_replicated; the full table remains in fields.parquet."),
 "round_boundaries": ("one row per boundary", "events + phase fields", "round_start, buy_phase_end, round_result_observed, side_switch, phase_begin."),
 "spike_events": ("one row per spike observation", "events + BombState/BombEquippable/TimedBomb fields", "Plant, location, state changes, carrier, pickup/drop/defuse-start/interrupt/detonation as INFERRED candidates."),
 "ability_casts": ("one row per distinct cast (caster, round, CastTime)", "AbilityCastsThisRound", "Slot numeric; ability id/name not exposed; time = buy-phase end + CastTime."),
 "utility_objects": ("one row per ability-related actor instance", "actors + fields(Owner/Instigator)", "Owner only when a field names it; cast link only when exactly one candidate (INFERRED)."),
 "utility_object_observations": ("one row per spawn/movement/close observation", "actors + movement", "Native samples of the object's own guid."),
 "utility_lifecycle_events": ("one row per stage with evidence", "casts, objects, effects, targets, damage", "Stages without evidence are not created. effect_/target_ stages are per-cast aggregates."),
 "utility_effects": ("one row per (cast, Effects[] index)", "AbilityCastsThisRound Effects[]", "Statistic name, aggregate value, category from config."),
 "utility_targets": ("one row per listed target", "Effects[].AffectedTargetsArray", "Target PlayerState guid resolved through roster; relation to caster."),
 "utility_statistics": ("one row per raw statistic field observation", "Comp_AbilityStatisticsReplicator fields", "Raw name/value/packet/channel; kind unknown unless configured; delta only same actor and field."),
 "utility_statistic_reconciliation": ("one row per comparison", "effects, targets, statistics", "Aggregate value vs listed targets, array size vs distinct casts, object-cast links. Differences kept."),
 "unresolved_utility_records": ("one row per unresolved record", "utility tables", "Reason and what would resolve it."),
 "combat_events": ("one row per damage hit or kill", "damage_events + kill_death_ledger", "Normalized view linked by damage_event_id, death_event_id, kill_ledger_id."),
 "damage_events": ("one row per damage hit (RPC call)", "MulticastNotifyDamage_Point.*", "Raw per-hit values and classes; source_kind weapon/utility/spike/unknown."),
 "kill_death_ledger": ("one row per death event (+ killing hits without a death event)", "events + damage_events", "Killer from event word0 and from KillCredit kept separately; conflicts flagged; no nearest-damage guess."),
 "combat_reconciliation": ("one row per check", "ledger, damage", "Counts compared; mismatches kept, never forced."),
 "normalized_match": ("one row per table", "inventory", "rows and coverage_status for every output."),
 "map_position_index": ("replay -> map -> round -> player -> actor", "player_positions", "Row range into player_positions."),
 "utility_lifecycle_index": ("round -> player -> cast -> object -> lifecycle -> effect -> target", "utility tables", "Flattened links; blank = no evidence of that link."),
 "event_provenance_index": ("one row per normalized record (bulk tables: one table-level row)", "all", "Source file/table/ref, original time and ids, transformation, evidence, status."),
}
out = ["# Valosaber normalized data contract (schema norm-1)", "",
 "Generated from `parser/normalize.py` by `tools/gen_contract.py`. Do not edit by hand.", "",
 "## Rules", "",
 "1. Raw observations are preserved. Interpretations live in their own columns/tables with an `evidence` class: OBSERVED (read from one source record), DERIVED (computed from several), INFERRED (a reading that needs confirmation), HYPOTHESIZED.",
 "2. `resolution_status` says whether identities and links resolved. Unresolved items are written to `unresolved_*` tables with the reason; nothing is dropped and nothing is guessed.",
 "3. A step that fails is recorded in `parser_diagnostics.json`; its tables are still written (empty, documented columns). One unresolved player/actor/event never fails the match.",
 "4. Movement is native. There is no 4 Hz table here. Velocity is computed only where 0 < dt <= `position_max_dt_for_velocity_ms`.",
 "5. No map regions, no coordinate transforms, no tactical conclusions, no player scores.",
 "6. Every table carries `match_id, record_id, source_file, source_table, source_ref, transformation, evidence, resolution_status`. `source_ref` is `<table>.parquet#<row>` into the raw export (or the id of the upstream normalized record).",
 "7. Clocks: `time_ms` is global replay time (field/event rows); `round_ms` is time since that round's `roundStarted`; `cast_time_s` is seconds after the buy-phase end of its round (`rounds.buy_end_ms`, OBSERVED from `ClientBuyPhaseEnd`, fallback 30/45 s marked INFERRED). Server tick is not in the export.",
 "8. Kill attribution: a `characterDeath` event payload carries killer (word0) and victim (word1) character guids. This is an INFERRED reading that agrees with `KillCreditPlayerState` on the 13.08 golden replay (34 of 34). Disagreements are kept as `KILLER_CONFLICT_EVENT_VS_CREDIT`.",
 "9. Empty tables keep their documented columns; `normalized_match.coverage_status` says why they are empty (`NOT_PRESENT_IN_SOURCE`, `NOT_EXPOSED_BY_PARSER`, `UNRESOLVED`).", "",
 "## Tables", ""]
for name, cols in normalize.S.items():
    g, src, note = D[name]
    out += [f"### {name}", f"- grain: {g}", f"- source: {src}", f"- note: {note}", f"- columns: `{', '.join(cols)}`" + ("" if name in ("event_provenance_index",) else " + standard provenance columns"), ""]
(ROOT / "docs").mkdir(exist_ok=True)
(ROOT / "docs/DATA_CONTRACT.md").write_text("\n".join(out), encoding="utf-8")
print("wrote docs/DATA_CONTRACT.md", len(normalize.S), "tables")
