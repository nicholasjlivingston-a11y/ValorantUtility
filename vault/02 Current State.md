---
type: status
status: current
updated: 2026-10-30
tags: [valosaber, status]
---
# Current State

> Update this note at the end of every session. Move items between the lists. Do not delete done items; move them to [[05 Changelog]] when they get old.

## Done
- Single-match prototype: published page with WPA, leverage, ADR+, finishing index, KST, trades, clutch, openers, head-to-head, death map, win expectancy table. See [[4c1d14ba Swiftplay Pitt]].
- **Stage 1 utility credit**: kill value split between killer, utility setters and damage assisters, with sliders and a zero-sum check. See [[Utility Credit]].
- Reference lookup with evidence for 9 of 10 agents ([[Agents]]).
- Size-safe pipeline prototype: shard format plus ingest tool, tested on one real shard and one corrupted copy. See [[Data Pipeline]].
- Briefs for the coding agent ([[Coding Agent Brief]]).
- This vault.

## In progress
- Aligning the coding-agent brief with the shard format ([[Shard Schema]]). The brief still describes the stats layer without the exact shard layout.

## Blocked or waiting
| Item | Waiting on |
|---|---|
| More replays (30+ for stable player numbers, hundreds for a fitted model) | User |
| A full competitive replay, to check economy and spike fields | User |
| Allow `valorant-api.com` for official agent, map and ability tables | User (network settings) |
| Link GitHub for a warehouse repo | User |
| Decode `Slot`, `AssistType`, hit region codes; find real economy values | Coding agent |

## Next up (in order)
1. Hand the coding agent the brief and the shard format.
2. Get 5 to 10 replays, at least one full competitive match, and rerun everything.
3. Fit a real win-probability model once there are enough rounds (spike, side, time in the state).
4. Stage 2 utility lift (needs effect start and end times and about 30 matches).

## Key numbers (sample match)
- Build `++Ares-Core+release-13.08`, Swiftplay, map code Pitt, 5 rounds, 34 kills
- Reconciliation: 34 of 34 kills match death events, largest time gap 9 ms, damage dealt equals damage received (6049.78), owner resolution unique
- Shard size 183 KB against 16 MB raw replay

## Known gaps in what exists today
- The shard is produced by `valosaber.py`, not by the main pipeline.
- Only one match has been through it.
- Economy values were all zero in this match.
- The win-probability model ignores the spike, clock, weapons and position.
