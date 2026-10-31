---
type: changelog
status: current
updated: 2026-10-30
tags: [valosaber, changelog]
---
# Changelog

Newest first. One line per change that someone starting fresh would care about. Link to the note that has the detail.

## 2026-10-31
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
