# Valosaber normalized data contract (schema norm-1)

Generated from `parser/normalize.py` by `tools/gen_contract.py`. Do not edit by hand.

## Rules

1. Raw observations are preserved. Interpretations live in their own columns/tables with an `evidence` class: OBSERVED (read from one source record), DERIVED (computed from several), INFERRED (a reading that needs confirmation), HYPOTHESIZED.
2. `resolution_status` says whether identities and links resolved. Unresolved items are written to `unresolved_*` tables with the reason; nothing is dropped and nothing is guessed.
3. A step that fails is recorded in `parser_diagnostics.json`; its tables are still written (empty, documented columns). One unresolved player/actor/event never fails the match.
4. Movement is native. There is no 4 Hz table here. Velocity is computed only where 0 < dt <= `position_max_dt_for_velocity_ms`.
5. No map regions, no coordinate transforms, no tactical conclusions, no player scores.
6. Every table carries `match_id, record_id, source_file, source_table, source_ref, transformation, evidence, resolution_status`. `source_ref` is `<table>.parquet#<row>` into the raw export (or the id of the upstream normalized record).
7. Clocks: `time_ms` is global replay time (field/event rows); `round_ms` is time since that round's `roundStarted`; `cast_time_s` is seconds after the buy-phase end of its round (`rounds.buy_end_ms`, OBSERVED from `ClientBuyPhaseEnd`, fallback 30/45 s marked INFERRED). Server tick is not in the export.
8. Kill attribution: a `characterDeath` event payload carries killer (word0) and victim (word1) character guids. This is an INFERRED reading that agrees with `KillCreditPlayerState` on the 13.08 golden replay (34 of 34). Disagreements are kept as `KILLER_CONFLICT_EVENT_VS_CREDIT`.
9. Empty tables keep their documented columns; `normalized_match.coverage_status` says why they are empty (`NOT_PRESENT_IN_SOURCE`, `NOT_EXPOSED_BY_PARSER`, `UNRESOLVED`).

## Tables

### players
- grain: one row per roster player
- source: manifest players + actors + fields(Controller)
- note: Identity, agent from character class, team from PlayerState GUID blocks (DERIVED).
- columns: `player_id, playerstate_actor_net_guid, character_net_guids, controller_net_guids, team_id, team_basis, agent_code, agent_name, agent_class_guid, characterId, display_name, name_status` + standard provenance columns

### teams
- grain: one row per team
- source: manifest players
- note: Team labels A/B are blocks of PlayerState GUIDs, not a replicated team id. Side per team is UNRESOLVED.
- columns: `team_id, n_players, player_ids, team_basis, first_half_side, side_status` + standard provenance columns

### agents
- grain: one row per player agent
- source: actors class path
- note: Codename from /Game/Characters/<code>/; public name only where codenames.json maps it.
- columns: `agent_code, agent_name, name_status, player_id, character_net_guid, class_path` + standard provenance columns

### actors
- grain: one row per actor instance (guid reuse gets #n)
- source: actors.parquet
- note: Open/close, class, kind, spawn position, round at open.
- columns: `actor_instance_id, actor_net_guid, instance_seq, channel_index, class_path, class_name, actor_kind, open_ms, close_ms, open_packet_id, close_packet_id, spawn_x, spawn_y, spawn_z, round_index_at_open, round_ms_at_open, player_id, owner_player_id` + standard provenance columns

### actor_lifecycle
- grain: one row per open/close record
- source: actors.parquet
- note: Raw lifecycle with instance id and round clock.
- columns: `actor_instance_id, actor_net_guid, event, time_ms, packet_id, channel_index, class_path, round_index, round_ms` + standard provenance columns

### netguid_mappings
- grain: one row per net guid
- source: net_guids.parquet
- note: Path, outer guid and full path.
- columns: `net_guid, path, outer_net_guid, outer_path, full_path` + standard provenance columns

### actor_ownership_intervals
- grain: one row per relation interval
- source: fields Owner/Instigator/Controller/PossessedCharacter/Possessed
- note: Start/end of each relation on an actor instance; includes possession changes.
- columns: `actor_instance_id, actor_net_guid, actor_class, relation, target_net_guid, target_instance_id, target_class, target_player_id, start_ms, end_ms, end_reason, start_round_index, start_round_ms, player_id, packet_id, channel_index` + standard provenance columns

### identity_crosswalk
- grain: one row per identifier per player
- source: manifest + fields
- note: subject uuid, PlayerState guid, character/pawn guids, controller guids, characterId, codename, possession changes.
- columns: `player_id, id_space, id_value, valid_from_ms, valid_to_ms, note` + standard provenance columns

### roster
- grain: player x round
- source: derived
- note: Team, agent, half and swap flag. side is never guessed.
- columns: `player_id, round_index, team_id, agent_code, agent_name, half_index, sides_swapped_vs_first_half, side, side_status` + standard provenance columns

### unresolved_identities
- grain: one row per unresolved reference
- source: actors/movement/fields
- note: What did not resolve and what would resolve it.
- columns: `subject_kind, net_guid, class_path, first_seen_ms, n_records, reason, needed_to_resolve` + standard provenance columns

### map_metadata
- grain: one row per level observed
- source: manifest level_names_and_times
- note: Map code, level path, name only if the map registry matches.
- columns: `replay_id, map_code, level_path, level_time_ms, map_name, internal_asset_id, id_source, map_identity_status, geometry_status, map_reference_package` + standard provenance columns

### coordinate_systems
- grain: one row
- source: convention
- note: Documented Unreal convention, status CONVENTION_NOT_VERIFIED_FROM_REPLAY, transformations_applied none.
- columns: `coordinate_system_id, units, units_basis, origin, axes, elevation_axis, handedness, space, angle_units, transformations_applied, status` + standard provenance columns

### movement
- grain: one row per native movement sample (no resampling)
- source: movement.parquet
- note: All movers, with round clock, mover kind, player id when roster.
- columns: `time_ms, packet_id, tick, mover_net_guid, actor_instance_id, pos_x, pos_y, pos_z, yaw, pitch, vel_x, vel_y, vel_z, timestamp, movement_state, move_type, round_index, round_ms, mover_kind, player_id, map_code, coordinate_system_id, position_source` + standard provenance columns

### player_positions
- grain: one row per roster movement sample
- source: movement.parquet
- note: Adds dt, displacement, speed (only where 0<dt<=limit), yaw/pitch change. Native rate.
- columns: `player_id, team_id, agent_code, round_index, round_ms, time_ms, mover_net_guid, pos_x, pos_y, pos_z, yaw, pitch, dt_ms, dx, dy, dz, step_xy, step_xyz, speed_xy_per_s, speed_xyz_per_s, dyaw, dpitch, movement_row_ref, map_code, coordinate_system_id, derived_valid` + standard provenance columns

### position_coverage
- grain: player-round, actor, and match rows
- source: movement.parquet
- note: Sampling intervals, gaps, attribution coverage.
- columns: `scope, player_id, round_index, mover_net_guid, n_samples, first_ms, last_ms, span_ms, median_dt_ms, p95_dt_ms, max_gap_ms, n_gaps_over_threshold, gap_threshold_ms, coverage_basis, round_start_ms, round_end_ms, n_zero_dt, fraction_attributed` + standard provenance columns

### position_anomalies
- grain: one row per flag
- source: movement.parquet
- note: Flags only; thresholds in pipeline_config.json.
- columns: `anomaly, player_id, round_index, time_ms, mover_net_guid, value, threshold, movement_row_ref` + standard provenance columns

### rounds
- grain: one row per round
- source: events + GameState RoundResults
- note: Start, result-observed time, buy-phase end (OBSERVED from ClientBuyPhaseEnd), half, switch, winner label/role.
- columns: `round_index, round_started_ms, round_end_ms, round_end_basis, buy_end_ms, buy_end_basis, half_index, side_switch_before_round_ms, winning_team_label, winning_team_role, round_result, round_number, winner_team_id, winner_status` + standard provenance columns

### events
- grain: one row per event
- source: events.parquet
- note: All events with global and round clock. packet/channel/tick are NOT_EXPOSED_BY_PARSER for events.
- columns: `event_id, event_group, event_name, time_ms, time2_ms, round_index, round_ms, tick, packet_id, channel_index, event_sequence, payload_tag, word0, word1, actor_guid, object_guid, instigator, target, related_field_rows, source_event_row` + standard provenance columns

### event_payloads
- grain: one row per event
- source: events.raw_payload
- note: Raw payload hex and words; characterDeath word0/word1 interpreted as killer/victim character guid (INFERRED, checked against kill credit).
- columns: `event_id, payload_size, payload_tag, payload_name, payload_seconds, word0, word1, raw_payload_hex, interpretation, interpretation_status` + standard provenance columns

### replicated_fields
- grain: one row per selected field observation
- source: fields.parquet
- note: Fields matching config field_patterns_replicated; the full table remains in fields.parquet.
- columns: `field_row, time_ms, packet_id, channel_index, actor_net_guid, actor_instance_id, object_net_guid, group_path, field_name, value, value_type, pattern_group, round_index, round_ms` + standard provenance columns

### round_boundaries
- grain: one row per boundary
- source: events + phase fields
- note: round_start, buy_phase_end, round_result_observed, side_switch, phase_begin.
- columns: `round_index, boundary, time_ms, basis, value` + standard provenance columns

### spike_events
- grain: one row per spike observation
- source: events + BombState/BombEquippable/TimedBomb fields
- note: Plant, location, state changes, carrier, pickup/drop/defuse-start/interrupt/detonation as INFERRED candidates.
- columns: `event_type, time_ms, round_index, round_ms, subject_player_id, subject_net_guid, value, site, location_x, location_y, location_z, basis` + standard provenance columns

### ability_casts
- grain: one row per distinct cast (caster, round, CastTime)
- source: AbilityCastsThisRound
- note: Slot numeric; ability id/name not exposed; time = buy-phase end + CastTime.
- columns: `cast_id, cast_uid_first, player_id, agent_code, agent_name, round_index, slot, ability_id, ability_name, round_phase, cast_time_s, barrier_ms, cast_abs_ms, time_basis, cast_x, cast_y, cast_z, destroyed_count, n_effect_records, cast_status, replicator_actor_net_guid` + standard provenance columns

### utility_objects
- grain: one row per ability-related actor instance
- source: actors + fields(Owner/Instigator)
- note: Owner only when a field names it; cast link only when exactly one candidate (INFERRED).
- columns: `utility_object_id, actor_instance_id, actor_net_guid, class_name, class_path, object_role, agent_code_from_class, slot_token, open_ms, close_ms, round_index, spawn_x, spawn_y, spawn_z, spawn_vx, spawn_vy, spawn_vz, owner_net_guid, owner_player_id, owner_basis, candidate_cast_ids, cast_id, n_movement_rows` + standard provenance columns

### utility_object_observations
- grain: one row per spawn/movement/close observation
- source: actors + movement
- note: Native samples of the object's own guid.
- columns: `utility_object_id, actor_net_guid, observation, time_ms, round_index, round_ms, pos_x, pos_y, pos_z, yaw, pitch, vel_x, vel_y, vel_z, movement_row_ref` + standard provenance columns

### utility_lifecycle_events
- grain: one row per stage with evidence
- source: casts, objects, effects, targets, damage
- note: Stages without evidence are not created. effect_/target_ stages are per-cast aggregates.
- columns: `lifecycle_event_id, stage, time_ms, round_index, round_ms, player_id, agent_code, cast_id, utility_object_id, actor_net_guid, target_player_id, target_net_guid, value, detail, pos_x, pos_y, pos_z` + standard provenance columns

### utility_effects
- grain: one row per (cast, Effects[] index)
- source: AbilityCastsThisRound Effects[]
- note: Statistic name, aggregate value, category from config.
- columns: `effect_id, cast_id, player_id, agent_code, round_index, effect_idx, statistic, effect_category, statistic_id, value, effect_time_s, n_targets, sum_target_value, effect_status` + standard provenance columns

### utility_targets
- grain: one row per listed target
- source: Effects[].AffectedTargetsArray
- note: Target PlayerState guid resolved through roster; relation to caster.
- columns: `target_id, effect_id, cast_id, target_player_state_guid, target_player_id, target_team_id, caster_team_id, relation_to_caster, target_value, target_idx, target_status` + standard provenance columns

### utility_statistics
- grain: one row per raw statistic field observation
- source: Comp_AbilityStatisticsReplicator fields
- note: Raw name/value/packet/channel; kind unknown unless configured; delta only same actor and field.
- columns: `field_row, time_ms, packet_id, channel_index, actor_net_guid, object_net_guid, group_path, serialized_field_name, field_leaf, array_path, value, value_type, round_index, player_id, ability_slot, stat_kind, resets_by_round, cumulative, counter_delta, delta_status` + standard provenance columns

### utility_statistic_reconciliation
- grain: one row per comparison
- source: effects, targets, statistics
- note: Aggregate value vs listed targets, array size vs distinct casts, object-cast links. Differences kept.
- columns: `check, player_id, round_index, statistic, observed_a, observed_b, difference, status, detail` + standard provenance columns

### unresolved_utility_records
- grain: one row per unresolved record
- source: utility tables
- note: Reason and what would resolve it.
- columns: `record_type, ref_id, time_ms, round_index, reason, needed_to_resolve` + standard provenance columns

### combat_events
- grain: one row per damage hit or kill
- source: damage_events + kill_death_ledger
- note: Normalized view linked by damage_event_id, death_event_id, kill_ledger_id.
- columns: `combat_event_id, event_type, time_ms, round_index, round_ms, actor_player_id, target_player_id, actor_net_guid, target_net_guid, source_kind, source_class, amount, damage_event_id, death_event_id, kill_ledger_id, attribution_status` + standard provenance columns

### damage_events
- grain: one row per damage hit (RPC call)
- source: MulticastNotifyDamage_Point.*
- note: Raw per-hit values and classes; source_kind weapon/utility/spike/unknown.
- columns: `damage_event_id, time_ms, packet_id, channel_index, victim_actor_net_guid, victim_class, victim_player_id, damager_player_id, kill_credit_player_id, damage_dealt, damage_taken, killed_target, alive_after, damage_type, damaged_bone, regional_damage, is_wall_penetration, equippable_class, damage_causer_class, damage_causer_net_guid, damage_origin, assists_list, kills_for_killer, kills_for_victim, round_index, round_ms, source_kind, fields_row_first` + standard provenance columns

### kill_death_ledger
- grain: one row per death event (+ killing hits without a death event)
- source: events + damage_events
- note: Killer from event word0 and from KillCredit kept separately; conflicts flagged; no nearest-damage guess.
- columns: `kill_ledger_id, death_event_id, damage_event_id, time_ms, round_index, killer_player_id, victim_player_id, killer_char_guid, victim_char_guid, killer_basis, victim_basis, killer_credit_player_id, assist_candidate_player_ids, assist_list_raw, source_kind, weapon_class, attribution_status, match_gap_ms` + standard provenance columns

### combat_reconciliation
- grain: one row per check
- source: ledger, damage
- note: Counts compared; mismatches kept, never forced.
- columns: `check, scope, round_index, expected, observed, difference, status, detail` + standard provenance columns

### normalized_match
- grain: one row per table
- source: inventory
- note: rows and coverage_status for every output.
- columns: `table, rows, coverage_status, note` + standard provenance columns

### map_position_index
- grain: replay -> map -> round -> player -> actor
- source: player_positions
- note: Row range into player_positions.
- columns: `map_code, player_id, round_index, team_id, mover_net_guid, n_rows, first_ms, last_ms, pos_row_start, pos_row_end, source_table` + standard provenance columns

### utility_lifecycle_index
- grain: round -> player -> cast -> object -> lifecycle -> effect -> target
- source: utility tables
- note: Flattened links; blank = no evidence of that link.
- columns: `player_id, round_index, cast_id, utility_object_id, lifecycle_event_id, stage, effect_id, target_id, target_player_id, time_ms` + standard provenance columns

### event_provenance_index
- grain: one row per normalized record (bulk tables: one table-level row)
- source: all
- note: Source file/table/ref, original time and ids, transformation, evidence, status.
- columns: `table, record_id, source_file, source_table, source_ref, original_time_ms, original_actor_ids, transformation, evidence, resolution_status`
