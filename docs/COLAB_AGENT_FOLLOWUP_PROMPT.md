# Follow-up prompt for the Colab debug agent (round 2)

Paste everything below the line into the Colab agent.

---

You ran the 13.09 cohort and reported success. I read your `batch_report.csv` on Drive and the report does not yet show the cohort is done. Your job now is to close the gaps below with evidence. Do not re-run steps that already succeeded, do not weaken any check, and do not rebuild vrfkit again unless step 2 says it is needed. Work with checkpoints: after each step write one line to `PROGRESS.md` and continue from it if you are restarted.

## What I found
1. All 7 matches are `normalized_only`. The shard step produced nothing and no reason is reported.
2. The vrfkit you used (`e742ed22…`, built from `vrfkit-main` source) does not match the first-run binary (`72adcd5e…`) or the registered one (`afe615e8…`). Your claim that it supports builds 11.06–13.09 is unverified.
3. You ran all 7 replays without the one-replay-first check.
4. `PROGRESS.md`, `FIXES.md` and `cohort_report.csv` were not delivered.
5. There are no per-match warnings, kill-ledger statuses, team sizes or barrier-time basis. Nothing about 13.09 Standard is confirmed yet.

## Steps (in order)
1. **Update the code.** Pull the latest `wip/normalize-13.09` (or the new bootstrap zip). `run_pipeline.py --replays` must forward `--lookup` (fixed in commit 6614bd3). Make sure `parser/audit_cohort.py` exists. Drop any local patch that duplicates this.
2. **vrfkit provenance.** Report in `FIXES.md`: the git commit of `vrfkit-main` you built from, cargo version, the SHA-256, `--version`, the builds list it contains (from its strings), and whether it equals `72adcd5e…`. If you cannot show that it contains `release-13.09`, say so and stop for that match.
3. **Why the shard produced nothing.** For every match, quote `status.json` → `steps.shard` (ok, error) and `owner_resolution.json` if present. Give the cause in one line per match. Fix it only if the cause is a bug in our code. If the cause is the known reciprocity failure on 13.09, say so; the normalization layer does not depend on the shard.
4. **One replay first.** Pick one 13.09 Standard replay. Re-run it with `--force` into a fresh outbox and confirm the steps pass before touching the other six. Then run the remaining six.
5. **Audit.** Run `python3 parser/audit_cohort.py <outbox> --out audit_cohort` and paste the table for every match: failed_steps, warn_checks, rounds, deaths, ledger_attributed/conflict/other, buy_observed/buy_fallback, team_sizes, position_attributed, n_unresolved_identities, utility_owner_resolved, targets_resolved, empty_tables, shard_ok.
6. **Judge the results against these expectations** (golden 13.08 Swiftplay: ledger 34/34, team sizes 5/5, buy_observed 5/5, position_attributed ≈0.92). For 13.09 Standard report where it differs: ledger_conflict > 0, team sizes not 5/5, buy_fallback > 0, empty roster, failed steps. Each difference needs a cause from the data (event counts, field names, manifest content), not a guess.
7. **Fix only what the evidence shows.** Keep every fix small, list it in `FIXES.md` with the failing evidence and the after-fix numbers, and re-run `parser/normalize_test.py` on the golden export (must stay 22/22). Never turn a warning into a pass by relaxing a threshold.
8. **Deliver** (small files, readable through Drive): `PROGRESS.md`, `FIXES.md`, `cohort_report.csv`, `audit_cohort.csv`, `audit_cohort.json`, one match's `status.json` and `parser_diagnostics.json`, and the big zip as before. Finish with a table of the 7 matches and one honest line each: ok / partial / failed and why.

## Rules
- Report what you observed. If a step was not run or failed, say that.
- No tactical conclusions or player scores.
- No real tokens in any file or message.
