---
type: changelog
status: current
updated: 2026-10-30
tags: [valosaber, changelog]
---
# Changelog

Newest first. One line per change that someone starting fresh would care about. Link to the note that has the detail.

## 2026-11-02
- **Reference extractor extended** (`parser/meta_tables.py`): hit-grain `damage_events` from the per-hit damage RPC (reconciles exactly with combat reports), `kill_details` (weapon class, bone, wall penetration, kill credit, assist candidates), `purchases`, `economy_snapshots` (DERIVED), spike plant location, carrier observations and an INFERRED planter, `bomb_timer_observations`. The old aggregate table is now `damage_by_pair_round`. 15 tests pass ([[Replay Data Guide]]).
- **`ingest.py` merges analytics tables** (schema meta-1): verifies hashes, rows and match_id, rejects any FAIL finding or a source_sha256 already ingested under another match, splits large tables by rows to stay under the cap, finds shards and analytics under `outbox/<match>/`. Tested: fresh, rerun, corrupted file, FAIL finding, small cap.

## 2026-11-01 (later)
- **Reference extractor for the 15 meta data groups:** `parser/meta_tables.py` + `meta_tables_test.py` (10 checks incl. a placeholder mutation test). Run automatically by `batch_process.py` into `<match>/analytics_tables/`, with `completeness_report.json` and gap codes. Checked on the one 13.08 sample only ([[Bootstrap Package]]).
- **Correction:** economy is not all zero. `MoneyManagementComponent` holds real money (800 to 8,850); `RoundInfos.EndOfRound*` are real; only `RoundInfos.StartOfRound*` is zero ([[Replay Data Guide]] item 11, [[04 Open Questions]] question 1). Master prompt updated.
- Other findings from the sample: round winners and results are in `GameState.RoundResults[n]` (WinningTeam Red, role, result); the 43,982 movement rows with no roster player belong to utility pawns (Cypher camera, Fade pet); `AffectedPlayer` values in effects are PlayerState actor guids and resolve to roster players.
- Build gate re-tested with stub binaries: a replay whose build the binary does not know, or an unregistered binary, stops with `unsupported_build` and writes no tables.
- Hush's kit sourced from the official 13.09 notes and a second outlet ([[Agents]]); codename and ID still unknown.
- Proposed [[ADR-008 Parquet tables are the primary route]] (CSV route becomes an adapter) and wrote [[First Real Run Checklist]].

## 2026-11-01
- **Bootstrap package v3** (`tools/build_bootstrap.py`): one zip for both the statistics analyst and the meta agent. It carries the agent task (master prompt with addendum), the meta agent's 15-group requirements (`docs/EXTRACTION_REQUIREMENTS.md`, also [[Extraction Requirements]]), the knowledge notes, our code, the registry, the meta agent's earlier files unchanged, and the golden sample with expected values. vrfkit is **not** inside; see [[Bootstrap Package]].
- Master prompt section 6 now points to the 15 data groups and the completeness statuses ([[Master Parser Prompt]]).
- `colab_bootstrap.py` now checks every candidate (passed path, `bin/vrfkit`, loose Drive file, every zip in Drive `bin/` holding `bin/vrfkit`), prints each hash, and installs the first registered one.
- The bootstrap the user re-attached holds the same 13.08-era vrfkit (hash `afe615e8...c04a`), so it does not add 13.09 support.

## 2026-10-31
- Applied the meta agent's addendum ([[Master Parser Prompt]]). Code now matches it: evidence-based shard checks (no fixed player or kill counts), a separate golden regression test labelled EXPORT_PIPELINE_VALIDATED, `source_sha256` and `run_id` in every shard, a vrfkit registry keyed by binary hash, `register_vrfkit.py`.
- **Bug fixed:** shard yaw was clipped at 327.67 degrees (10.7% of sample rows wrong). Shard schema is now version 2; the warehouse was rebuilt from the corrected sample ([[Shard Schema]]).
- **Bug fixed:** the roster join read `codenames.json` from a skill folder that Colab does not have, which would have dropped 3 of 10 players.
- The user reports a 13.09-capable vrfkit is active; it still needs registering ([[Bootstrap Package]]).
- Merged the meta agent's master task with the analyst's needs into [[Master Parser Prompt]]. Added a build support gate (`data/vrfkit_supported_builds.json`): replays from builds the pinned vrfkit does not know, such as 13.09, stop with `unsupported_build`.
- Delivery 5 from the coding agent rejected (same placeholder pattern, 7 matches). Added value checks (`parser/shard_checks.py`) to the batch so a shard with placeholder data is quarantined, provenance hashes in `status.json`, and `--only`. Wrote [[Raw Replay Parsing Prompt]].
- Wrote [[Colab Agent Prompt]] (no GitHub token needed): the coding agent runs the batch pipeline from a downloaded copy of the repo and delivers shards through Drive.
- Added the Colab batch notebook and `parser/batch_process.py`; `valosaber.py` no longer hardcodes build, duration or mode; skill scripts copied into `parser/skill/` ([[Run Order]]).
- Bootstrap zip moved to `MyDrive/valosaber/bin/` (confirmed); `colab_bootstrap.py` now finds it there by default ([[Bootstrap Package]]).
- Checked Drive for vrfkit: source zip and a 40.9 MB binary of unknown origin found; the pinned binary was built from the same source and supports builds to 13.08 ([[Bootstrap Package]]).

## 2026-10-30 (latest)
- Colab plan for vrfkit: kept in Drive, pinned by SHA-256, verified by `parser/colab_bootstrap.py`; `bin/` and replays are git-ignored ([[Bootstrap Package]]).
- Drafted [[Unified Pipeline Brief]]: one core fact layer, a stats contract and a meta contract.
- Reviewed the pipeline bootstrap package; not integrated, nothing run ([[Bootstrap Package]], [[Ability Ontology]]).
- Added Hush (Duelist, patch 13.09) to the class table; 30 agents confirmed ([[Agent Classes]]). Noted an agent-count mismatch to check.
- Sourced all agent classes: 29 agents confirmed, including Miks (Controller) and Veto (Sentinel) ([[Agent Classes]]).
- Added three-tier peer comparison: [[ADR-007 Three peer groups for comparison]], [[Baselines]], [[Agent Classes]], `parser/baselines.py`, `data/agent_classes.json`.

## 2026-10-30 (later)
- GitHub linked; repo `ValorantUtility` holds `vault/`, `parser/`, `data/`, `inbox/` ([[Limits and Access]]).
- Added `inbox/`, `data/warehouse/` and [[Queue]]. Tested the inbox flow with the raw export of `4c1d14ba`: parsed to a shard, ingested, idempotent on rerun ([[Run Order]]).
- Reviewed the coding agent's first stats-layer delivery and rejected it: placeholder values ([[Stats Layer Delivery 1 Review]]).
- Updated [[Coding Agent Brief]] with the shard layout and a no-defaults rule.

## 2026-10-30
- Built this vault and the project handoff (`claude/START_HERE.md`).
- Saved the patched table builder, page template and site build script to the project. The page regenerates byte-for-byte. See [[Run Order]].
- Stage 1 utility credit published: zero-sum split with sliders ([[Utility Credit]], [[ADR-006 Utility credit is zero-sum and adjustable]]).
- Pipeline prototype: 183 KB shard, `ingest.py` verifies checksums and merges into parts of 8 MB or less ([[Data Pipeline]]).
- Fixed a join that dropped 3 players from the position data ([[Replay Data Guide]]).
- Agent names: Iris is Miks (ID confirmed), Sequoia is Iso (ID confirmed, not Tejo), Pine is Veto (kit plus user statement) ([[Agents]]).

## 2026-10-29
- Researched sabermetrics ([[07 Sabermetrics Notes]]).
- Built Valosaber v1 from the combat reports: WPA, leverage, ADR+, KST, trades, clutch, openers ([[Metrics Index]]).
- Resolved combat-report owners by damage reciprocity ([[ADR-001 Owner resolution by damage reciprocity]]).
- Wrote the coding-agent briefs ([[Coding Agent Brief]]).

## 2026-10-28
- First contact with the replay data. Google Drive connector could read file metadata but not download a 159 MB zip (10 MB limit).
- Parsed the exported tables; built the ability-effects table. Fixed the Swiftplay roster and half-start handling in a patched `build_table.py` ([[Run Order]]).
- Created the lookup file for names ([[Agents]]).
