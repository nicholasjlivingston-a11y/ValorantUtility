---
type: checklist
status: current
updated: 2026-11-01
tags: [valosaber, pipeline, colab, checklist]
---
# First real run checklist (Colab, 13.09)

Goal: answer every open question about the 13.09 vrfkit in one round. Do the steps in order and paste the outputs back. Part of [[Run Order]]; background in [[Bootstrap Package]].

## 1. Register the binary (once)
In Colab, with the repo or the bootstrap v3 unpacked:
```
python3 parser/register_vrfkit.py /content/drive/MyDrive/valosaber/bin/<your vrfkit file or zip> --label "13.09 vrfkit"
```
Paste the whole printout: the SHA-256, the size, the list of `release-NN.NN` strings it contains (does it include `release-13.09`?). If the 13.09 string is missing, stop: that binary cannot be registered as 13.09-capable. Then rerun with `--write` and commit the changed `data/vrfkit_supported_builds.json` and `parser/vrfkit.sha256` (or send them to Claude).

## 2. Install it
`python3 parser/colab_bootstrap.py` and paste its hash lines (REGISTERED or unregistered). If it prints REFUSING, stop and paste it.

## 3. Run ONE replay
```
python3 parser/batch_process.py --replays <replays folder> --outbox <outbox> --vrfkit bin/vrfkit --lookup data/name_lookup_build13_08.json --only <one 13.09 replay file> --no-zip
```

## 4. Paste back
- `<outbox>/<match>/status.json` in full (steps, build, release, checks, `analytics_rows`, errors).
- `<outbox>/<match>/completeness_report.json` (or its `gaps` list) and `analytics_tables/validation_findings.parquet` printed as a table.
- Output of `ls -l` for the match folder.
- The agent roster: `python3 -c "import pandas as pd; print(pd.read_parquet('<outbox>/<match>/analytics_tables/players.parquet')[['subject','characterId']])"`. This gives the 10 characterIds; one of them is Hush's.
- Whether any status is `unsupported_build`, `failed_check` or `export_only`, with the error text. These are valid results; do not work around them.

## What each outcome tells us
| Result | Meaning | Next |
|---|---|---|
| `unsupported_build` with the 13.09 string missing | the binary does not know 13.09 | get or build a newer vrfkit; no data is produced |
| `export_only` or `failed_check` | export worked, our shard logic or checks fail on 13.09 | read the failed check; likely a format change |
| `ok` | export, shard, checks and 15 tables produced | compare findings, record Hush's characterId and codename ([[Agents]]) |

## Things to look at in an `ok` result
- Findings with WARN or FAIL (kill-death reconciliation, dealt equals received, money resolution, movement by mover).
- Whether `economy` has `MoneyManagementComponent` rows and whether `RoundInfos.StartOfRound*` is zero again.
- Rounds in a standard-mode replay: halves, side switch timing, overtime.
- Any gap code that changed from the 13.08 sample.
