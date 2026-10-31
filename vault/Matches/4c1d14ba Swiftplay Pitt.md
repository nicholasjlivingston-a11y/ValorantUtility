---
type: match
status: processed
updated: 2026-10-30
match_id: 4c1d14ba-6e21-496f-9101-1b85fa513fd8
build: "++Ares-Core+release-13.08"
replay_version: 5.3.2
mode: Swiftplay
map_code: Pitt
rounds: 5
kills: 34
duration_s: 480.87
source_bytes: 15957425
shard_bytes: 183000
winner: Team A
tags: [valosaber, match]
---
# Match 4c1d14ba (Swiftplay, map code Pitt)

The only match processed so far. See [[Replay Data Guide]] for how the numbers were reconciled.

## Facts
- Team A won all five rounds by elimination.
- Sides swapped after round index 3 (a `switchTeams` event at 366.4 s). Team A attacked rounds 0 to 3 and defended round 4, inferred from the plants and the single defuse (480.4 s).
- Spike planted in every round (70.9, 179.5, 277.4, 329.5, 448.2 s).
- Team A: Jett, Phoenix, Iso, Sova, Reyna. Team B: Fade, Cypher, Miks, Omen, Veto. Names per [[Agents]]; Phoenix is kit-only and Veto is confirmed by the user plus kit.

## Checks
- 34 of 34 kills match the death events, largest time gap 9 ms
- Damage dealt equals damage received, 6049.78
- Owner resolution unique; positions for all 10 players

## Round summary
| Round | Kills | Team A alive at end | Plant (s) |
|---|---|---|---|
| 1 | 6 | 4 | 70.9 |
| 2 | 8 | 2 | 179.5 |
| 3 | 6 | 4 | 277.4 |
| 4 | 6 | 4 | 329.5 |
| 5 | 8 | 2 | 448.2 |

## Leaderboard snapshot
WPA is in rounds (see [[WPA and Leverage]]). Adjusted uses the default utility split in [[Utility Credit]] (60/25/15, healing at 150 HP).

| Agent | Team | K | D | ADR | WPA | Adjusted WPA |
|---|---|---|---|---|---|---|
| Phoenix | A | 6 | 0 | 175 | +1.40 | +1.12 |
| Reyna | A | 6 | 1 | 148 | +1.03 | +1.00 |
| Iso | A | 6 | 3 | 205 | +0.70 | +0.73 |
| Omen | B | 4 | 5 | 133 | −0.15 | −0.22 |
| Jett | A | 5 | 3 | 161 | −0.22 | −0.19 |
| Sova | A | 2 | 2 | 138 | −0.41 | −0.08 |
| Veto | B | 2 | 5 | 124 | −0.42 | −0.37 |
| Fade | B | 0 | 5 | 50 | −0.60 | −0.56 |
| Miks | B | 1 | 5 | 34 | −0.62 | −0.58 |
| Cypher | B | 2 | 5 | 41 | −0.71 | −0.73 |

## Caveats
Five rounds. The numbers describe this match and say little about the players in general ([[Rate Indexes]]).

Page: https://claude.ai/artifact/S1xAQwFf29rMUka9zPoa1b
