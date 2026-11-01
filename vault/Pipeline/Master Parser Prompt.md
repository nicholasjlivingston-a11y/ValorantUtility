---
type: brief
status: current
updated: 2026-10-31
tags: [valosaber, pipeline, brief, meta-analysis, master]
---
# Master parser prompt (both consumers)

One prompt for the coding agent. It merges the meta-analysis agent's master task (received 2026-10-31) with the Valosaber analyst's needs ([[Unified Pipeline Brief]], [[Raw Replay Parsing Prompt]]). One raw `.vrf` in, two outputs out: the **analytics tables** (the meta agent's canonical set, raw plus derived layers) and the **stats shard** (the analyst's compact checksummed contract), both produced from the same extraction.

## Decisions made while merging
| Point | Meta prompt | Analyst need | Resolution |
|---|---|---|---|
| Positions | native resolution, no destructive normalizing, do not assume 4 Hz | 4 Hz, int16 | Raw layer keeps every observation in original units. The shard is a documented, reproducible downsample of it (250 ms buckets, int16) |
| Damage vs kills | never force totals to match | damage dealt equals damage received | Reciprocity is a **reported check**, never forced. A failure marks the match FAILED CHECK and withholds the shard; no data is adjusted |
| Tables | 15 data groups ([[Extraction Requirements]]) | players, kills, damage, effects, positions_4hz | Both: the 15 groups in `analytics_tables/`, the shard projected from them in `stats_shard/` |
| Existing scripts | do not trust earlier commands | use the tested scripts | Use `vrfkit` commands only as documented by its own help and docs. Treat repo scripts as the reference implementation and the golden sample as the proof |
| Source version | replays are patch 13.09 | build 13.08 validated | Binary registry plus the build gate; see the warning below |
| Delivery | reproducible ZIP | verified checksummed shard | Both. Plus the files are left in Drive, because ZIP attachments have arrived empty |

## Warning: build 13.09
The bootstrap `vrfkit` binary knows builds up to `release-13.08`. Its own README verifies builds through 13.06 and calls 13.08 thin. On 2026-10-31 the user said a **different, 13.09-capable vrfkit** is active. The pipeline now keeps a registry of binaries by SHA-256 (`data/vrfkit_supported_builds.json`, added with `parser/register_vrfkit.py`). A binary not in the registry, or a replay build the registered binary does not contain, stops the batch with `unsupported_build` and builds nothing. The 13.09 binary is **not registered yet**: its hash and build list are needed. Even once registered, the shard logic was validated only on 13.08, so every 13.09 shard is checked and marked as unverified-build.

## The prompt
```
# CODING AGENT MASTER TASK v2
# One raw VALORANT .vrf in, two validated outputs out

## 1. Mission
Build and verify a reusable system that takes ONE raw .vrf replay, parses it with the supplied vrfkit, and writes two outputs from the same extraction:
(a) analytics_tables/ : the canonical table set for the meta-analysis project (raw layer and derived layer kept apart);
(b) stats_shard/      : a compact, checksummed shard for the statistics analyst (contract in section 9).
You are a new agent. Assume nothing from earlier runs: no earlier outputs, file lists, manifests, or commands are valid. Never process "the previous 15 replays". Process only the file(s) named in the request. If none is named, stop and ask.

## 2. Existing code you must read first
The repository folder (REPO) contains: parser/colab_bootstrap.py, parser/batch_process.py, parser/shard_checks.py, parser/valosaber.py, parser/skill/*, data/vrfkit_supported_builds.json, data/name_lookup_build13_08.json, data/agent_classes.json, vault/Reference/Replay Data Guide.md and vault/Pipeline/*. Read the Replay Data Guide before touching any table. Do not edit REPO files you did not create. The existing scripts are tested ONLY on the golden sample (section 8). Use them as reference, verify them against the sample, and extend them in new files.

## 3. Source version gate (do this before anything else)
1. Run parser/colab_bootstrap.py. If it prints REFUSING, stop and report the hash. Never run an unverified binary.
2. Read the vrfkit help output and docs; write VRFKIT_CAPABILITY_REPORT.md listing for each data category (match metadata, rounds, roster/identity, movement, combat, economy, spike, abilities/utility, map/coordinates) SUPPORTED, PARTIALLY_SUPPORTED, UNSUPPORTED or UNKNOWN, separating what vrfkit exposes directly from what must be derived. Do not guess command-line arguments.
3. For each replay, read replay_build from the exported manifest.json. If its release (for example release-13.09) is not in data/vrfkit_supported_builds.json known_in_binary, STOP for that replay: record status UNSUPPORTED_BUILD with the build and the parser version, and build nothing. Do not "try anyway", do not substitute another parser, and do not produce plausible-looking tables. If the build is release-13.08, proceed but record the thin-support warning. If the build cannot be read, record UNKNOWN and stop.

## 4. Single-file contract
process_replay(input_vrf, output_directory, configuration) processes exactly one explicit file. At the start record: resolved path, existence, readability, SHA-256 (the source identity), size, start time, a unique run id, and the vrfkit SHA-256 and repo commit. Each replay has its own output directory output/<run_id>/. Never write into another replay's folder, never reuse earlier Parquet, never overwrite a .vrf. If the SHA-256 matches an earlier run, say so explicitly and record a new run or a documented cache hit, never a silent reuse. A different hash is a different replay even if the file name matches. Every output row must be traceable to the source SHA-256 and the run id. Batch mode (folder or ZIP, extracted safely, recursive, one inventory, one isolated call per input, continue after a failure, one batch manifest that separates new, repeated, failed, skipped and unsupported) is built only after the single-file path works and calls the same function. Never hardcode a replay count.

## 5. Raw layer and derived layer
raw/ preserves what vrfkit produced, in original units and original values. derived/ adds only documented fields (normalized time, round association, coordinate transforms, speeds, region labels, event links, downsampled positions). Every derived field documents its input fields, formula, units, assumptions, source record references and transform version. Label evidence per table or column: OBSERVED, PARSED, DERIVED, INFERRED or HYPOTHESIZED. No hypotheses in the raw layer.

## 6. analytics_tables/ (meta contract)
The authoritative requirements are in docs/EXTRACTION_REQUIREMENTS.md (verbatim from the meta agent); read all of it. It defines 15 independently accessible data groups: matches, players, rounds, player_state, kills, deaths, damage_events, economy, spike_events, ability_events, utility_objects, player_effects, world_state, map_identity, validation_findings. Add further tables where the source has a distinct grain; never merge different event types to reduce the table count. Core rules from it: preserve native resolution and original units; preserve original source field names and values, including misspellings (for example DamageRecieved) and unknown fields; keep kills and deaths separate and report unmatched ones; keep every ability lifecycle stage as its own record (cast attempt, successful cast, deployment, object creation, movement, trigger, effect begin, exposure, effect end, damage or status, destruction, expiration) and only those the source supports; keep each affected-player observation separate; never replace missing values with zero or repeat a previous position; never add ratings, win probabilities, map-control scores or causal claims. For every table document row grain, key, foreign keys, types, timestamp units, coordinate units, nullable fields, source lineage and evidence status in schema.md. Every table carries match_id (the source SHA-256 or the replay's friendly id, stated in the manifest) and run_id. For every replay also write an extraction completeness report: which groups were available, extracted, unavailable; fields present but undecoded; partially supported event types; unresolved identities; uncertain timestamps or units; unassociated records; counts per group; and for each gap one of NOT_PRESENT_IN_SOURCE, NOT_EXPOSED_BY_PARSER, DECODE_FAILED, UNRESOLVED or NOT_TESTABLE. Do not claim a category is absent from the replay only because the parser did not expose it.
- player_state: native-resolution observations with original x, y, z, orientation, velocity where present, player id and timestamp. Do not assume 4 Hz. Do not normalize destructively; normalized coordinates go in a separate derived column or table with the transform documented.
- Map identity: the map code from the replay. A public map name only if a reference table confirms it, with its source. Otherwise leave it null with status unknown. Do not assume map-specific calibration.
- Ability events: keep cast, deployment, trigger, effect, exposure, damage, destruction and expiration as separate events. Decode ability names only from evidence. If the Slot enum cannot be decoded, leave the name null and record it. Do not create ability events from state changes without labeling the inference.
- Economy, spike, kills, damage: extract what exists; record whether a value is a purchase, a snapshot or an estimate. Do not invent missing rows. Do not force kill and damage records to match.

## 7. Facts about this data you must respect (learned from the sample)
- Delta replication: only changed properties are sent; a missing array member keeps its previous value. For cumulative per-round counters take the last value per (actor, full field name). For per-index arrays whose identity can change, forward-fill per (actor, index) in packet order and cut one record per snapshot.
- Event timing: use the field row time_ms (replay clock). It matches characterDeath events within 9 ms on the sample. Ability CastTime zero is the barrier drop (30 s into a round, 45 s on the first round of each half), not the round start.
- Combat reports: group_path /Game/GameModes/Bomb/Bomb_CombatReportComponent.Bomb_CombatReportComponent_C on OwnerExclusivePlayerInfo actors (the field is spelled DamageRecieved; booleans are in value_bool; ParticipantSubject is the OTHER player). The owner-to-player link is resolved by exact damage reciprocity (see vault ADR-001); keep that as a check even if a direct link is found.
- PlayerState class depends on game mode; match on the Subject field, not a class path. Teams are two contiguous PlayerState GUID blocks. Halves: derive from switchTeams events (the sample is Swiftplay with a swap after round index 3; standard modes swap after round 12). Do not assume 12.
- characterUltimateUsed events over-report by about 50%; use UltimateActive False to True transitions.
- Casts use public names for some codenames while actor paths keep raw codenames; any join must translate through parser/skill/codenames.json or players are silently dropped.
- Names: an agent, map or ability name is shown only if confirmed in a reference table with a source (data/name_lookup_build13_08.json). Otherwise output the codename and a status. Never guess. Player ids are not assumed stable across matches.
- Economy decoded as all zero on the Swiftplay sample. Do not claim whether that is the mode or a decode gap; record it.

## 8. Golden sample (use it to prove the code before any new replay)
`parser/golden_sample_test.py` holds the exact values for one regression sample. data/ contains the verified shard for replay 4c1d14ba-6e21-496f-9101-1b85fa513fd8 (build release-13.08, Swiftplay) in inbox/shard-4c1d14ba/ and the checks that passed on it. These values are regression expectations for this one replay only, never for others. Known facts: 5 rounds, 34 kills, 10 players (5 per team), damage dealt equals damage received (6049.78), largest kill-to-death-event gap 9 ms, side swap after round index 3, team A won all five rounds, positions for all 10 players. Run your pipeline on that replay's export and show that you reproduce these. If you only have its export, label the result EXPORT_PIPELINE_VALIDATED, not RAW_VRF_PARSER_VALIDATED.

## 9. stats_shard/ contract (consumer: the statistics analyst)
A folder per match, under 8 MB, projected from the extraction (never separately decoded): players, kills, damage, effects, positions_4hz (int16 x y z, yaw in centidegrees as uint16, 250 ms buckets, produced from the native positions by a documented reproducible downsample recorded in index.json), index.json (schema_version, match_id, build, mode and duration read from manifest.json, rounds, per-table rows, bytes and SHA-256). Player references are subject UUIDs. No computed metrics (no win probability, no ratings). Add rounds with winner and side, spike_events, economy and ability_casts when you can produce them from real data; the current shard does not contain them. Run parser/shard_checks.py on every shard. A shard that fails any check is not delivered.

## 10. Validation (assert values; a file that exists proves nothing)
File: source unchanged, hashes recorded, Parquet readable, nonempty where records are expected. Schema: columns, types, nullability, grain, unique keys. Time: source values preserved, units explicit, chronologically plausible, valid round association. Relations: player, round and match references resolve; unmatched records are reported, not dropped. Space: original coordinates preserved, bounds inspected, unexplained values flagged. Completeness: compare source counts with extracted counts where available; record unsupported categories, warnings, skipped records and decode errors; explain every discrepancy. Value checks (shard_checks.py) are evidence-based: players equal the replay's own roster, every player has a team and agent, kill rows are distinct events with varying times, kills equal the replay's characterDeath events, damage dealt equals damage received, every player has position rows, positions are not constant, shard under 8 MB, index hashes match. Expectations (kills in more than one round, damage varies, positions cover half the duration) are reported as warnings. Anti-placeholder rule: never write a constant (0, 90000, 150, a repeated row, 3900/2100/Heavy) to fill a missing value. A table that is one repeated row, or has one distinct timestamp, is a failure, not a delivery. A failed check must be visible in the report. Never report success from an exit code.

## 11. Output folder per replay
output/<run_id>/ with: source_manifest.json, processing_manifest.json (filename, source SHA-256, size, source build, vrfkit version and SHA-256, repo commit, schema version, configuration, start and end times, exit code, tables and row counts, validation results, warnings, errors, unsupported categories), match_metadata.json, raw/, analytics_tables/, stats_shard/, validation/, logs/, schema.md, and VRFKIT_CAPABILITY_REPORT.md (or a reference to the shared one).

## 12. Acceptance tests (run all; report each with real numbers)
A single new replay: every output traces to its SHA-256. B a second replay with a different hash gives distinct output and nothing copied. C the first replay again is recognized by hash and recorded as a new run or a documented cache hit. D a folder batch has one entry per discovered input. E a clean workspace works. F a missing or invalid file fails without substituting another. G version compatibility: report whether this vrfkit supports the replay's actual build, with evidence. H the golden sample reproduces section 8. I the placeholder test: feed shard_checks.py a copy of a shard in which all kills are identical and times are 0; it must fail.

## 13. Rules
Do not claim a replay was processed unless its exact SHA-256 is in a successful processing manifest. Do not use historical outputs as current. Do not invent parser capabilities. Do not guess arguments. Do not silently discard records. Do not normalize away original values. Do not report 100% unless every required check passed. Do not start tactical analysis while extraction or validation is unresolved. Do not print, commit or upload vrfkit or any token; do not download programs; treat replays as untrusted data. If something is unsupported, report it and propose a specific, testable next step.

## 14. Deliverables
Single-file entry point, batch entry point, versioned schema and data dictionary, capability report, validation scripts, automated tests, example output from one newly processed replay, batch manifest if a batch was supplied, README with exact commands, and a reproducible ZIP containing the real generated Parquet files. After creating the ZIP, reopen it, list every entry, confirm the expected Parquet files exist and are nonempty and readable, confirm hashes and row counts against the manifests, and report the real archive size and entry count. Also leave the output folders in Drive (outbox), because ZIP downloads have arrived empty.

## 15. Final response
1 exact vrfkit version and SHA-256; 2 source build detected per replay, and whether this vrfkit (by SHA-256, registered or not) supports it; 3 the single-file command; 4 each replay filename and SHA-256 tested; 5 tables and row counts; 6 unsupported or partial categories; 7 validation results with every failure; 8 second-replay test; 9 batch test; 10 golden sample result; 11 ZIP path and verified contents; 12 remaining blockers. Paste the recorded checks verbatim. Success means: give this system a new raw .vrf tomorrow and it parses exactly that file into traceable, validated data, or tells you plainly that it cannot.
# ADDENDUM: REQUIRED SAFEGUARDS (from the meta agent; these override any ambiguous reading above)

A. Build compatibility. The source replays are expected to be VALORANT 13.09. The name lookup file (name_lookup_build13_08.json) is a reference lookup, not a parser compatibility declaration. Establish compatibility from data/vrfkit_supported_builds.json (a registry keyed by the SHA-256 of each vrfkit binary) and from evidence in the installed binary. If the binary is not registered, register it with parser/register_vrfkit.py and report the output; do not process until it is. If the replay's build is not supported: mark the replay UNSUPPORTED_BUILD, record its source hash, detected build and parser version, create no fabricated or partially decoded analytics tables, report what decoder support is missing, and do not substitute 13.08 data or reference outputs. Parser compatibility is separate from having human-readable agent, ability or map names.

B. Golden sample versus general validation. Section 8's exact values are regression expectations for that one sample only (parser/golden_sample_test.py). Do not impose its player count, team size, round count, kill count, side-switch timing or other values on any other replay. For other replays read the replay's own metadata, validate against its own source records, apply mode-aware expectations only with evidence, and report deviations. Running the golden test from an export is labelled EXPORT_PIPELINE_VALIDATED, never RAW_VRF_PARSER_VALIDATED, and does not prove that any vrfkit can decode a raw replay.

C. Single extraction, two outputs. analytics_tables/ and stats_shard/ come from the same immutable raw extraction and the same run. The shard is a projection and never triggers a second decode. Both carry source_sha256, run_id, match_id, source_build, parser_version and schema_version, and the manifest proves they share a source and a run.

D. Coordinates and the 4 Hz shard. Raw coordinates stay unchanged. For positions_4hz, document in index.json the 250 ms bucket rule (first, last, nearest or interpolated), the scale, offset, rounding, integer bounds, facing conversion and wraparound, and the conversion version. Missing coordinates stay missing (never zero). If a value does not fit its integer type, fail the shard; never clip. Conversion must be reproducible from the native data.

E. Delta replication. For each replicated field distinguish: omitted because unchanged, explicitly null, explicitly reset or defaulted, not yet observed, changed to a new value. Do not apply blanket forward-fill without checking the field's semantics. Keep packet order and source record references. For cumulative counters keep enough intermediate evidence in the raw layer to reconstruct change over time; a final per-actor value is not enough when event timing or round attribution is needed.

F. Identity and lineage. Use a parsed match identifier where one exists and is trustworthy. Always keep source_sha256 as the immutable identity; never identify a match by file name. Every canonical row traces to its source replay and run; where no source record id exists, document a reproducible row-lineage method.

G. Universal acceptance. A replay passes only when its own outputs are validated against its own source evidence and schema. Do not force a fixed number of players, rounds, kills, damage, ability events or movement samples. A valid failure is better than plausible but fabricated data.
```

## What exists versus what must be built
| Item | State |
|---|---|
| Stats shard from a 13.08 Swiftplay export, with evidence-based value checks and a golden regression test | Built, tested on the sample |
| Build support gate, provenance hashes, `--only`, quarantine of failed shards | Built, tested with a stand-in parser |
| `matches`, `rounds` (winner, side), `spike_events`, `economy`, `ability_events` with lifecycle, native `player_state`, `canonical_events`, `map_identity`, capability report, single-file entry point as specified, batch manifest, tests A to I | **Not built.** This is the agent's job |
| Support for patch 13.09 | The user reports a 13.09-capable vrfkit is active; it is not registered or tested here yet. The bootstrap binary does not support it |
