---
type: review
status: rejected
updated: 2026-10-30
tags: [valosaber, pipeline, review]
---
# Stats layer delivery 1: review

File: `inbox/valorant_analytics_stats_layer_delivery (2).zip` (8 tables plus `schema.md`, match `39748ae1-c383-4f5e-a5d9-57e2da2befe2`). **Rejected, nothing ingested.** Part of [[Coding Agent Brief]] work.

## Findings
| Table | Problem |
|---|---|
| kills (683 rows) | One distinct (round, killer, victim); all at time 0; weapon Vandal on every row |
| damage_events (683) | All 150 damage, all lethal |
| rounds (94) | Every row 0 to 90,000 ms; no winner, no side |
| spike_events (76) | All at time 0 |
| economy (1,316) | Loadout 3,900, credits 2,100, armor Heavy on every row |
| players (14) | A match has 10; agent names with no evidence ([[ADR-005 Names only when confirmed]]) |
| player_state | `norm_x`/`norm_y` range about -8,258 to 11,243 (not 0 to 1); keyed by engine GUID so it cannot join to players |
| quality.json | Reports 2 tests passed; they did not check values |

## Likely cause
Decode failures were filled with defaults instead of nulls.

## Action
Resend with the updated brief. Acceptance: run the checks on the Swiftplay sample `4c1d14ba` (34 kills, 5 rounds, 10 players, damage dealt equals damage received) and paste the output. See [[Run Order]] for how I validate.

## Delivery 5 (2026-10-31): rejected
Nine tables over 7 matches (129 rounds, 941 kills, 385,281 position rows). Same pattern as delivery 1: 941 kill rows but 1 distinct (round, killer, victim), all at time 0 and all 'Vandal'; every damage 150 and lethal; all rounds 0 to 90,000 ms; economy 3,900 / 2,100 / Heavy on every row; all casts `CharacterUltimateUsed` at 0; players 14 rows with no match ID; `norm_x` from -50,845 to 15,101 with only 42% inside 0 to 1. The match IDs, per-match round counts and position times looked real, so the parser found the structure but defaulted the detail columns. No `quality.json`. A prior attachment (delivery 3 and its "independent audit") arrived as empty 22-byte zips. See [[Raw Replay Parsing Prompt]] for the fix.
