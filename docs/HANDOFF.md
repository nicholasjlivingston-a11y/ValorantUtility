# Handoff: normalization layer (schema norm-1), bootstrap v3.2

## What changed in the existing pipeline
- New `parser/normalize.py` reads ONE vrfkit export and writes 39 linked parquet tables plus `parser_diagnostics.json`, `normalized_manifest.json`, `match_header.json`, `pipeline_handoff.json`. It never re-parses the `.vrf`.
- New `parser/run_pipeline.py`: `--from-exports` (existing exports or export.zip, no vrfkit) or `--replays` (raw, delegates to `batch_process.py`).
- `parser/pipeline_config.json`: thresholds, effect categories, which statistics are known counters, bulk tables for the provenance index, paths.
- `batch_process.py`: runs normalize after the shard step regardless of the shard result; self-registers a shipped vrfkit from its own strings (a replay build the binary does not contain is still refused); stamps the commit from a `COMMIT` file when there is no `.git` (the 7-match run showed `fatal: not a`).
- Cast clock: the barrier drop (CastTime zero) is now OBSERVED from `ClientBuyPhaseEnd` per round, not a fixed 30/45 s. On the 13.08 sample it differs from the fixed rule by up to 142 ms. The fixed rule remains only as a labelled fallback.
- `valosaber.py` owner resolution uses the direct Controller chain first, reciprocity only as a checked fallback (the 13.09 Standard runs failed on reciprocity: best cost 706).

## New in what is available
- Identity: player, team block, agent, character/pawn/controller guids, possession and ownership intervals, actor instances (guid reuse separated), crosswalk, unresolved list.
- Native movement for every mover; per-player-round coverage, gaps, displacement, speed, yaw/pitch change, anomaly flags. No resampling.
- Kill/death ledger from the death event's own killer/victim guids, cross-checked with KillCredit (34/34 on the golden replay); per-hit damage with source kind.
- Spike timeline (plant, location, state, carrier, candidates for pickup/drop/defuse start/interrupt/detonation).
- Utility: casts, ability-related objects with owner where a field names it, effects, targets, raw statistic observations, reconciliation. Lifecycle stages only where evidence exists.
- Provenance index and the three indexes.

## Still unresolved (parser does not expose it)
See `pipeline_handoff.json -> source_matrix.needs_new_decoder_output`: tick/packet/channel for events and movement, ability id/name and slot labels, cast attempt/failure, object state fields (activation, trigger, pulse, impact), object close cause, per-target effect timing, BombState/phase enum labels and site, attacker/defender side per team, map name/transform/geometry, display names.

## Which outputs come from where
All 39 tables are built from the existing vrfkit export (`manifest, events, actors, net_guids, fields, movement`). Nothing requires re-decoding the raw replay today; the list above is what a future decoder change would add.

## Run on the seven-match cohort
Existing exports (no vrfkit): `python3 parser/run_pipeline.py --from-exports <folder with the 7 export folders or export.zip files> --out normalized_out`
From raw replays: `python3 parser/run_pipeline.py --replays replays --vrfkit bin/vrfkit --out outbox`
Check `normalized_out/cohort_report.csv`, then each match's `pipeline_handoff.json` and `parser_diagnostics.json` (checks with level warn).

## What was tested and what was not
Tested on the 13.08 Swiftplay golden export: `python3 parser/normalize_test.py <export>` (22 checks incl. mutation and roster-fallback). NOT tested on any 13.09 Standard export (none available here). First run on the cohort: read warnings, especially team split, roster source, ledger status counts, barrier basis.

## Location
Repo `nicholasjlivingston-a11y/ValorantUtility`, branch `wip/normalize-13.09`; package `bootstrap/valosaber_bootstrap_v3.2.zip`; contract `docs/DATA_CONTRACT.md`.
