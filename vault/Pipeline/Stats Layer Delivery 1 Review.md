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
