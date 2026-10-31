---
type: reference
status: current
updated: 2026-10-30
tags: [valosaber, reference, data, traps]
---
# Replay data guide

Read this before touching any table. Every item here is a trap that produces confident wrong numbers. Verified on build `++Ares-Core+release-13.08`, Swiftplay.

## Tables (from the vrfkit export)
`fields`, `checkpoint_fields`, `actors`, `events`, `net_guids`, `movement`, plus `manifest.json`.
- `fields`: `time_ms`, `packet_id`, `channel_index`, `actor_net_guid`, `object_net_guid`, `group_path`, `handle`, `field_name`, value columns `value_i64`, `value_f64`, `value_bool`, `value_str`. **Booleans are in `value_bool`.** Text columns can load as a categorical type; convert to `object` before filling.
- `events` groups: `roundStarted`, `characterDeath`, `spikePlanted`, `spikeDefused`, `characterUltimateUsed`, `switchTeams`. Death events carry **no killer or victim**.
- `movement`: per-tick position, facing and velocity per `character_net_guid`. 22 pawn GUIDs in the sample (10 primary plus respawned pawns). Coordinates are raw world units.
- `manifest.json`: `replay_build`, `duration_ms`, and `game_specific_data[1]` is JSON with `playerLoadouts` (subject UUID to public `characterId`).

## Traps
1. **Delta replication.** Only changed properties are sent. A missing array member keeps its old value. For cumulative counters inside per-round arrays, the last value per (actor, full field name) is the final state. Array positions are reused, so cast identity is `(caster, round, CastTime)`, not row or position. The skill's `extract_casts.py` handles casts.
2. **Event time.** The row `time_ms` of a field is replay time and matches `events.time1` to within 9 ms. Use it for kills. Ability `CastTime` is different: its zero is the barrier drop, so absolute time is `roundStart + CastTime + 30 s` (45 s on the first round of each half). Cast timing is accurate to about 2 s. See [[ADR-002 Event timing from field timestamps]].
3. **Halves.** Derive them from `switchTeams`. Swiftplay swaps sides after round index 3. Standard modes swap after round 12. The skill's script hardcodes round 12 and breaks on Swiftplay (patched in `build_table_swiftplay.py`).
4. **PlayerState class depends on mode.** Standard: `BombPlayerState`. Swiftplay: `Swiftplay_EoRCredits_PlayerState`. Both have a `Subject` field. Match on the field, not a hardcoded class. Teams are two contiguous PlayerState GUID blocks (sample: 254 to 262 and 272 to 280); split at the largest gap.
5. **Combat reports.** Group path `/Game/GameModes/Bomb/Bomb_CombatReportComponent.Bomb_CombatReportComponent_C`. One component per player on an `OwnerExclusivePlayerInfo` actor. Fields `Rounds[r].Reports[k].Interactions[i].…`: `ParticipantSubject` (the **other** player), `DamageDealt`, `DamageRecieved` (sic), `HitsDealt`, `HitsRecieved`, `bDidKill`, `bWasKiller`, `AssistType`, `GameTime`, `GamePhase`; plus nested `DealtInteractions` and `ReceivedInteractions` with `Regions[]`. Report fields: `bDied`, `DeathLocation`, `RoundNumber`.
6. **Which player owns a component is not in the export.** The `Owner` and `AresController` fields point at GUIDs missing from `actors`. Solved by damage reciprocity ([[ADR-001 Owner resolution by damage reciprocity]]).
7. **Codename vs public name mismatch.** The cast table already translates 3 confirmed codenames (Wushu to Jett, Wraith to Omen, Hunter to Sova) while actor paths keep raw codenames. Joining them silently drops those players. Translate through `codenames.json`.
8. **Three player identifiers.** Subject UUID (`Subject`, casts), PlayerState net GUID (effect targets), pawn/controller GUID (`actors`). They do not interchange.
9. **Actor spawns are not casts.** Spawns overcount by 3 to 4 times.
10. **`characterUltimateUsed` over-reports by about 50%.** Use `UltimateActive` False to True transitions.
11. **Economy is all zero** in the Swiftplay sample (`RoundInfos[n].StartOfRoundMoney` and loadout values). Do not build economy metrics until a competitive replay shows real values.
12. **Undecoded:** cast `Slot`, `AssistType` (0, 1, 10, 14 seen), hit `Region`.
13. **Anonymized names.** Competitive replays store anonymized display names. The per-player `Subject` UUID is the stable key.

## Reconciliation checks (run these on every match)
- Rebuilt kills equal `characterDeath` events (sample: 34 and 34).
- Largest gap between a rebuilt kill and its death event is under 50 ms (sample: 9 ms).
- Total damage dealt equals total damage received (sample: 6049.78).
- Every combat-report component resolves to exactly one player (sample: one zero-cost solution, runner-up cost 3,100).
- All 10 players have positions (sample: 100%).
