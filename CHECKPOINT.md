# CHECKPOINT (update after every step; read this first after any reset)

Task: make bootstrap run on 13.09 vrfkit + add ChatGPT agent's data requests (identity, native movement, map, events, utility lifecycle, stats reconciliation, combat, indexes, handoff).

## DONE (committed)
- parser/normalize.py: complete normalization (38 parquet tables, norm-1), tested on golden 13.08 export: all steps ok, 34/34 kills attributed (characterDeath word0/word1 = killer/victim character guid, agrees with KillCredit).
- parser/pipeline_config.json: single config (thresholds, effect categories, provenance bulk list).
- Barrier time from observed ClientBuyPhaseEnd (build_table.py, build_table_swiftplay.py, normalize.py), not fixed 30/45 s.
- valosaber.py owner resolution: direct controller chain first (already in repo).
- batch_process.py: self-register binary from its strings, repo_commit fallback, calls normalize.py.

- batch_process.py aligned with normalize.py (out = <id>/normalized). parser/run_pipeline.py written and tested (--from-exports on golden export.zip -> 38 tables, cohort_handoff.json).

- Bootstrap rebuilt: bootstrap/valosaber_bootstrap_v3.2.zip (verified from clean unzip: normalize_test 22/22, golden test pass, run_pipeline --from-exports ok).

## TODO
1. First real 13.09 Standard run: run_pipeline --from-exports on the 7 exports, read cohort_report.csv + warnings.
2. Hush codename/characterId, ADR-008 approval, open questions 1,4,5,6,10,13,14,15,16.
## Facts found in the Colab outbox (7 Standard 13.09 matches)
vrfkit 72adcd5e... exported all 7, decode errors 0; shard failed in old valosaber (reciprocity cost 706); repo_commit "fatal: not a"; time-base check only 5/120 deaths.
