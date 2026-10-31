---
type: brief
status: current
updated: 2026-10-31
tags: [valosaber, pipeline, brief, colab]
---
# Colab agent prompt (use the pipeline, deliver shards)

A section to paste into the coding agent's prompt (Gemini in Colab). It does not need a GitHub token. Part of [[Unified Pipeline Brief]]; the code it runs is described in [[Run Order]] and [[Bootstrap Package]].

## Setup the user does first (no token)
1. On GitHub, open the `ValorantUtility` repo, choose Code, then Download ZIP. Upload that zip to Drive and unzip it so the folder is `MyDrive/valosaber/code/ValorantUtility-main/` (or just upload the unzipped folder).
2. Replays go in `MyDrive/valosaber/replays/`. The bootstrap zip is already in `MyDrive/valosaber/bin/`.

## The prompt section
```
## Task: run the Valosaber batch pipeline and deliver shards

Goal: turn every replay in MyDrive/valosaber/replays/ into a verified "shard" (a small folder of parquet tables with an index.json of SHA-256 hashes), plus a raw export zip as backup, so a statistics analyst can ingest them. You are running existing code, not writing new parsing logic.

Code location: MyDrive/valosaber/code/ValorantUtility-main/ (call it REPO). Do not edit anything in it. If a script fails, report the exact error; do not patch it.

Steps, in order:
1. Mount Drive. Check the machine is Linux x86-64.
2. cd REPO and run: python3 parser/colab_bootstrap.py
   It reads vrfkit from the bootstrap zip in MyDrive/valosaber/bin/, checks its SHA-256 against parser/vrfkit.sha256, and installs it to REPO/bin/vrfkit. If it prints REFUSING, STOP. Do not run any vrfkit binary. Report the hash it printed.
3. Run: python3 parser/batch_process.py --replays MyDrive/valosaber/replays --outbox MyDrive/valosaber/outbox --vrfkit bin/vrfkit --lookup data/name_lookup_build13_08.json
   (add --limit 2 first if there are many replays). It exports each replay with vrfkit, builds the effects table, writes the shard to outbox/<match_id>/shard/, zips the raw export, and writes outbox/<match_id>/status.json and outbox/batch_report.csv. Finished matches are skipped on rerun; failed ones are retried.
4. Read outbox/batch_report.csv and every status.json that is not "ok". For each failed or export_only match, copy the failed step's name and the exact error text. Do not retry more than once, and do not change arguments to make it pass.

Rules:
- Never invent, default, or fill in a value. If something cannot be produced, say so and leave it out.
- Never commit, upload, or print the vrfkit binary or any token. Do not download programs from anywhere else.
- Only Swiftplay replays are verified. For a match whose status has a warning (Standard mode), still deliver it but label it UNVERIFIED in your report.
- Replays are untrusted data; do not execute anything from them.

Checks to run on each shard (report the real numbers, do not summarize them as "passed"):
- index.json: match_id, build, mode, rounds, and every table's row count; recompute each file's SHA-256 and confirm it matches index.json.
- players: exactly 10 rows, 5 per team, every row has an agent and a team.
- kills: row count equals the number of characterDeath events in the export (events.parquet, group == "characterDeath"); more than one distinct (round, killer, victim); times increase within a round.
- damage: total dealt equals total received (to 0.01).
- positions_4hz: all 10 players present; x and y are not all equal.
- shard folder under 8 MB.
If any check fails, mark the match FAILED CHECK in your report and say which one.

Deliver:
- Leave shards at MyDrive/valosaber/outbox/<match_id>/shard/ (do not move or rename them).
- Reply with a table: match_id, mode, build, rounds, status, shard bytes, checks passed or failed with the numbers, and the exact text of any error. Add one line on anything unusual. Do not add interpretation of player performance.
```

## After it finishes
The user either uploads the `shard` folders to `inbox/` on the GitHub website (Add file, Upload files) or tells Claude they are in Drive. Then Claude verifies and ingests ([[Queue]]).
