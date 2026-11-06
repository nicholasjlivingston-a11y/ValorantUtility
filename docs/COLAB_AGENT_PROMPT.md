# Prompt for the Colab debugging agent (paste as is)

You are running the Valosaber bootstrap (v3.2) on raw Valorant replays in Colab. Your job is to run the pipeline, fix only what the evidence shows is broken, and deliver the output tables. Work in this order and do not skip the checks.

## 0. Ground rules
- Never invent, default or fill a value. A missing value stays missing with a status. Never run a binary that is not the one uploaded with this bootstrap.
- Do not re-run the same replays blindly. Run ONE replay, read its outputs, fix, then run the rest.
- After each numbered step, write one line to `outbox/PROGRESS.md` (step, result, files touched). If you are interrupted, resume from the last line there; do not start over.
- Do not paste tokens or secrets anywhere.

## 1. Locate and identify the inputs
1. Unzip the bootstrap. Read `README.md`, `docs/HANDOFF.md`, `docs/DATA_CONTRACT.md`, `COMMIT`.
2. Find the vrfkit uploaded with it: `bin/vrfkit` (if absent, search the upload folder for a file named `vrfkit*` and move it to `bin/vrfkit`; `chmod +x`). Print: file size, SHA-256, `bin/vrfkit --version`, and the list of `release-NN.NN` strings inside the binary (`strings bin/vrfkit | grep -o "release-[0-9][0-9]*\.[0-9][0-9]*" | sort -u`).
3. List the replays (`*.vrf`) with size and SHA-256. Read each replay's build from the vrfkit export manifest later; do not guess it.
4. Do not stop if the binary hash is not in `parser/vrfkit.sha256`. `batch_process.py` registers a shipped binary from its own strings (config `parser.self_register_binary`). It refuses a replay whose build the binary does not contain. That refusal is correct; report it, do not work around it.

## 2. Test the package before touching replays
```
python3 parser/golden_sample_test.py golden_sample/shard golden_sample/export      # expect EXPORT_PIPELINE_VALIDATED
mkdir g && unzip -q golden_sample/export_full.zip -d g && python3 parser/normalize_test.py g/export   # expect 22 of 22
```
If either fails, stop and report; do not continue to replays.

## 3. Run ONE replay end to end
```
python3 parser/run_pipeline.py --replays replays --vrfkit bin/vrfkit --out outbox --only <ONE>.vrf
```
Then read, in this order: `outbox/<id>/status.json`, `outbox/<id>/normalized/parser_diagnostics.json`, `outbox/<id>/normalized/pipeline_handoff.json`, `outbox/<id>/normalized/normalized_match.parquet`.

Known facts from the first 13.09 Standard run (do not rediscover them): vrfkit exported with 0 decode errors; the old shard step failed on owner resolution (reciprocity cost 706); `repo_commit` read "fatal: not a"; cast time-base matched only 5 of 120 deaths.

Report for this replay: build, mode, map_code, rounds, players, deaths, movement rows; which steps failed (`failed_steps`); every check with level `warn`; the `kill_death_ledger.attribution_status` counts; `rounds.buy_end_basis` counts (OBSERVED vs fallback); fraction of movement attributed to players (`position_coverage` scope `match_mapping`); `roster_source`; team sizes (`teams.n_players`, expect 5/5).

## 4. Fix only what the evidence shows
For each failed step or warning: print the traceback or the offending rows, state the cause with the evidence, make the smallest change, rerun that replay (`--force`), and compare before/after. Allowed fixes: code in `parser/`, thresholds in `parser/pipeline_config.json`. Not allowed: editing vrfkit output, hard-coding values for one replay, weakening a check to make it pass, deleting rows.
Things most likely to need attention on Standard 13.09: team split (largest-gap rule with 10 players), roster fallback, overtime rounds, barrier time (`ClientBuyPhaseEnd`), `valosaber.py` owner resolution (shard only; normalization does not depend on it), new agent (Hush) codename not in `parser/skill/codenames.json` (leave the codename, report it).
Record each fix in `outbox/FIXES.md` (symptom, evidence, change, result).

## 5. Run the rest
```
python3 parser/run_pipeline.py --replays replays --vrfkit bin/vrfkit --out outbox
```
If a replay fails, continue with the others and list the failure. If you only have existing exports, use `--from-exports <folder> --out normalized_out` instead.

## 6. Deliver
Produce in `outbox/`:
- per replay: `normalized/` (39 parquet tables), `parser_diagnostics.json`, `pipeline_handoff.json`, `status.json`, and `normalized_core.zip` (everything except movement, player_positions, replicated_fields, utility_object_observations, event_provenance_index, netguid_mappings, actor_lifecycle, position_anomalies; keep each file small enough to download through Drive, 10 MB limit).
- `cohort_report.csv` (one row per replay: status, build, map, rounds, players, deaths, movement rows, failed steps, warnings).
- `PROGRESS.md`, `FIXES.md`.
- A final summary: replays processed OK / partial / failed; for each partial or failed, the exact reason; the list of tables that are empty with their `coverage_status`; anything you changed in the code; anything you could not resolve and what decoder output would be needed. No tactical conclusions and no player scores.

Copy `outbox` to Drive (`MyDrive/valosaber/outbox`) and print the Drive path. Commit code changes if a git remote is configured; otherwise save a zip of the changed files as `outbox/code_changes.zip`.
