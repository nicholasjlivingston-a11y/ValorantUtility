---
type: metric
status: current
updated: 2026-10-30
tags: [valosaber, metrics, rates]
---
# Rate indexes and sequencing stats

Indexed stats read **100 as the match average**, like OPS+ in baseball.

| Metric | Definition |
|---|---|
| ADR | Damage dealt divided by rounds played |
| **ADR+** | `100 × ADR / mean ADR of all players` |
| **Finishing+** | `100 × (player kills / player damage) / (total kills / total damage)`. Above 100 means kills came cheaply in damage; usually kills that other damage set up. Very noisy at small samples (Cypher scored 173 on two kills) |
| **KST%** | Share of rounds where the player got a kill, survived, or died and was traded |
| Trade kill | A kill on a victim who killed a teammate of the killer in the previous 5 s |
| Traded death | A death where the killer died within the next 5 s |
| First K / First D | The round's first kill, or first death (opening duel) |
| Clutch K | A kill made while the killer's team had one player alive against two or more |
| Util-assisted K | A kill on a victim affected by a teammate's ability in the previous 8 s. Ability timing is accurate to about 2 s |

## Limits
- Damage includes overkill and damage on already-low targets, so Finishing+ is rough.
- Trades use any killer within 5 s, not only a teammate of the victim.
- Util-assisted counts depend on ability timing, which is the loosest clock in the data.
- All of these need many matches before a single player's number means much. Baseball regresses small samples toward the mean; we should too ([[03 Roadmap]] Phase 2).

## Code
`P` table in `claude/valosaber.py`.
