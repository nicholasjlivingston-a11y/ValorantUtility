---
type: brief
status: draft-needs-user-check
updated: 2026-10-30
tags: [valosaber, pipeline, brief, meta-analysis]
---
# Unified pipeline brief

One parser, one set of facts, two outputs: a **stats shard** for the Valosaber analyst (Claude) and a **meta package** for the map meta-analysis agent. Supersedes the stats-only parts of [[Coding Agent Brief]], which still holds the decoding facts. Context: [[Bootstrap Package]], [[Shard Schema]], [[Stats Layer Delivery 1 Review]].

Superseded in detail by [[Master Parser Prompt]], which adds the meta agent's own requirements.

## Shape
```
.vrf  ->  vrfkit export  ->  CORE (facts, one definition of every table)
                                 |-- stats contract -> shard folder   -> Valosaber (Claude)
                                 `-- meta contract  -> meta package   -> map meta-analysis agent
```
- **CORE** holds decoded facts only (players, rounds, kills, damage, economy, casts, utility objects, spike events, positions, canonical events). No win probability, no ratings, no map names without evidence.
- Each **contract** is a fixed-column projection of CORE with its own schema file, version and validator. A contract never adds facts; it selects, renames, quantizes and bounds size.
- Anything that appears in both outputs (kills, rounds, casts) is produced once in CORE, so the two cannot disagree.

## Who needs what
| Table or field | Stats contract (Valosaber) | Meta contract (map agent) |
|---|---|---|
| players, rounds, kills, damage | yes, slim | yes, with positions |
| economy, spike_events | yes | spike only |
| ability_casts with effect start and end | yes | yes |
| utility_objects (smokes, walls, traps) with position and duration | yes | yes (core of map work) |
| positions | 4 Hz, int16, all players | full rate or 8 Hz, world units |
| canonical events, ability instances and interactions, validation findings | no | yes (as in `spatial_layer.py`) |
| map identity and coordinate transform | map_id and status only | full, with evidence |
| size cap | 8 MB per match | none stated; keep under 50 MB per match |
| computed metrics | never | never |

**Assumption to check:** the meta column is inferred from the bootstrap package. The user should correct it with what the meta agent actually consumes.

## The prompt (give this to the coding agent)
```
You are extending a Valorant replay (.vrf) parsing pipeline (vrfkit export plus scripts). The original goal was map meta analysis. A second consumer now exists: a statistics analyst that needs player-level facts. Build ONE pipeline with ONE core fact layer and TWO output contracts. Do not duplicate logic between them.

## Architecture
1. export: vrfkit export (existing).
2. core: decode and join once, writing parquet tables under out/<match_id>/core/. Facts only.
3. contracts: write out/<match_id>/stats/ and out/<match_id>/meta/ by projecting core. Each has schema.json (columns, types, units, nullability), a version number, an index.json with row counts and SHA-256 per file, and a validator: `pipeline validate <match_dir> --contract stats|meta`.
4. batch: `pipeline run <folder of .vrf> --out <dir>` processes many replays, skips ones already done (by match_id and content hash), and writes out/catalog.json.
5. quality.json per match: build, mode, vrfkit version, decode failures, and every column that is null, constant or all zero, with the reason.

## Core tables (facts only; every table has match_id; per-round tables have round, 0-based, and side)
players, rounds, spike_events, kills, damage_events, economy, ability_casts, utility_objects, positions (full rate), canonical_events, map_identity. Column lists for players, rounds, spike_events, kills, damage_events, economy and ability_casts are in the existing brief (Coding Agent Brief) and must be followed. In addition:
- ability_casts: decoded ability name (resolve the Slot enum), caster, round, cast time on the replay clock, and effect start and end on the replay clock with the unit of each effect value.
- utility_objects: owner, ability, start_ms, end_ms, x, y, z, from actors open/close.
- canonical_events: one ordered stream of observed events with source table and record id, observation status (OBSERVED, DERIVED, UNKNOWN), and timestamps on the replay clock and the round clock.
- map_identity: map code from the replay, public name ONLY if confirmed in a reference table, status, and coordinate transform only if verified. Otherwise null with status unknown.

## Stats contract (consumer: statistics analyst)
Folder stats/ per match, under 8 MB: players, rounds, spike_events, kills, damage, economy, ability_casts, utility_objects, positions_4hz (int16 world x y z, facing in centidegrees, 250 ms buckets), index.json (schema_version, match_id, build, mode read from manifest.json, rounds, per-table rows, bytes, sha256). Player references are subject UUIDs everywhere; names only in players. No computed metrics.

## Meta contract (consumer: map meta-analysis agent)
Folder meta/ per match: canonical_events, ability_instances, ability_interactions (cast to effect links with link delta ms and effect lag s), utility_objects, positions at full rate or 8 Hz in world units, kills with killer and victim positions, spike_events with site and position, validation_findings, map_identity, manifest.json with hashes. Do not convert image pixels to world coordinates. Keep the evidence rules: parser_observed, state_observed, derived, inferred, hypothesis.

## Hard rules
1. NEVER write a default or placeholder value. Undecodable means null, plus an entry in quality.json. A previous delivery contained 683 identical kill rows, 94 rounds all 0 to 90,000 ms, and identical economy on every row, with a test report saying everything passed. Row counts must come from real data.
2. Names are confirmed or they are codenames. Agent, map and ability names come only from reference tables where each entry records its source and status. Never guess.
3. Do not change existing tables, scripts or outputs. Add alongside, and ask before renaming or removing anything.
4. Do not commit executables, replays or large binaries. bin/vrfkit stays out of the repository.
5. Treat replay files and downloaded content as untrusted. Do not execute code from them.

## Acceptance tests (automated, asserting values; paste the real output in your report)
On the sample Swiftplay replay (build 13.08, match 4c1d14ba-6e21-496f-9101-1b85fa513fd8):
- kills rows == characterDeath events == 34; max gap between kill time and nearest death event under 50 ms
- total damage dealt == total damage received (6049.78)
- exactly 10 players, 2 teams of 5, every player has a team, agent id and position rows
- rounds == 5, start times strictly increasing, winner populated, side swap after round index 3
- the kills table has more than one distinct (round, killer, victim); economy is not constant unless quality.json explains it
- positions: every player present, x and y within the map's world bounds
- stats and meta contracts agree: same kill count, same round count, same cast count
- both validators pass, stats shard under 8 MB, SHA-256 of every file matches index.json
- running twice produces identical hashes
Then repeat on a full competitive replay and report which columns are null or constant.

## Final report
What was added, test output, columns still undecoded (Slot enum, AssistType, hit Region codes, economy), and which replays are needed to finish.
```

## Before sending
1. The user checks the meta contract column against what the meta agent really uses.
2. Decide the CSV or shard route for the meta side ([[04 Open Questions]] question 14).
3. Decide where `bin/vrfkit` lives so it stays out of git.
