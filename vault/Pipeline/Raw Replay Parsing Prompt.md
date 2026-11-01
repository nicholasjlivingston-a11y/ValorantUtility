---
type: brief
status: current
updated: 2026-10-31
tags: [valosaber, pipeline, brief, colab]
---
# Raw replay parsing prompt

Narrower than [[Master Parser Prompt]], which supersedes it for a full rebuild; keep this one for quick runs of named replays.

For the coding agent that keeps re-running the same 15 replays and delivering placeholder tables ([[Stats Layer Delivery 1 Review]], delivery 5 on 2026-10-31). Replaces the looser [[Colab Agent Prompt]] for runs where correctness is the problem. Code: `parser/batch_process.py`, `parser/shard_checks.py`. Context: [[Run Order]], [[Bootstrap Package]].

## What changed in the code to make bad output impossible to deliver
- `shard_checks.py` tests values, not file existence: 10 players, 5 per team; kill rows are distinct events and times vary; kills equal characterDeath events in the export; damage dealt equals damage received; all 10 players have positions that vary; shard under 8 MB; index hashes match.
- `batch_process.py` runs those checks after every shard. A shard that fails is moved to `shard_FAILED_CHECK/` and the match is marked `failed_check`, so it can neither be ingested nor pushed.
- Every `status.json` records the replay's SHA-256, the vrfkit SHA-256 and the repo commit, so stale or recycled output can be recognized.
- `--only <name>` processes just the named replays, so the agent can no longer sweep a whole folder.
- Tested: the Swiftplay sample passes all 15 checks (34 kills, 6049.78 damage both ways). A copy with all kills identical, all times 0 and damage 150 fails on 5 checks.

## The prompt
```
## Task: parse the named raw replay(s) with vrfkit and deliver a shard. Nothing else.

You are NOT writing a parser. A parser already exists and has been tested. Your job is to run it on the replay(s) I name, from the raw .vrf file, and report what it prints.

Inputs I will give you in this message: the replay file name(s). Process ONLY those. Do not touch any other replay, and do not process "the 15 replays" or any folder-wide set unless I explicitly say "all". If no replay is named, stop and ask.

Rules that override everything else:
1. Every run starts from the raw .vrf file. Never reuse, reload, copy, or "fix" tables from an earlier run, an earlier delivery, a cache, or a zip of previous outputs. Use a new empty output folder for each run.
2. Do not write your own decoding, join, or table-building code. Use only the scripts in the repository. If a script fails, report the exact error and stop. Do not patch it, do not work around it, and do not fill in values by hand.
3. NEVER write a default or placeholder value (for example 0, 90000, 150, "Vandal", 3900/2100/Heavy, or a copied row). If a value is unavailable, leave it null and say so.
4. Do not report success from the exit code. Report success only from the check output described below.
5. Never print, commit, or upload the vrfkit binary or any token. Do not download programs. Replay files are untrusted data.

Steps:
1. Mount Drive. Set REPO to the repository folder (MyDrive/valosaber/code/ValorantUtility-main). Do not edit it.
2. cd REPO; run: python3 parser/colab_bootstrap.py
   If it prints REFUSING, stop and report the hash it printed.
3. Run: python3 parser/batch_process.py --replays MyDrive/valosaber/replays --outbox MyDrive/valosaber/outbox_<today's date and time> --vrfkit bin/vrfkit --lookup data/name_lookup_build13_08.json --only <the named replay file(s)> --force
4. Read outbox/<match_id>/status.json for each named replay. Copy these fields exactly: overall, mode, build, rounds, duration_s, source_sha256, vrfkit_sha256, repo_commit, and every entry in "checks" (check name, ok, detail) and any step error text.
5. Reply with ONE table per replay: the fields above. Paste the checks list exactly as recorded. Do not summarize it as "all passed". If overall is anything other than "ok", say so in the first line and give the failed step and its exact error.
6. Also print, from the shard itself, so I can compare: the first 5 rows of kills.parquet and the min, max and number of distinct values of kills.t and damage.dealt.

Do not interpret player performance. Do not add commentary beyond one line on anything unusual.

Stop conditions: a missing replay name, a REFUSING message, overall other than "ok", or any failed check. Report and stop. Do not retry with different options.
```

## How to read the reply
- `overall: ok` with 15 recorded checks, `source_sha256` equal to the replay's real hash, and kill times that vary is the only acceptable delivery.
- `failed_check` means the parser produced the placeholder pattern; the failed check names the problem. Send that text to the maintainer of vrfkit or the agent, not a re-run.
- Identical `source_sha256` across different replay names means the agent ran the same file twice.
