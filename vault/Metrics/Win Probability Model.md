---
type: metric
status: current
updated: 2026-10-30
tags: [valosaber, metrics, model]
---
# Win probability model

## What it is
The chance a team wins the round, given how many players are alive on each side. It is the base for [[WPA and Leverage]] and [[Utility Credit]].

## Definition (current, theoretical)
Assume each living player is equally likely to get the next kill, so the next kill goes to the team with `a` alive against `b` alive with probability `a / (a + b)`.

```
WP(a, b) = a/(a+b) * WP(a, b-1) + b/(a+b) * WP(a-1, b)
WP(a, 0) = 1   (a > 0)
WP(0, b) = 0   (b > 0)
```

| You alive \ Them | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| 1 | 50% | 17% | 4% | 1% | 0% |
| 2 | 83% | 50% | 23% | 8% | 2% |
| 3 | 96% | 78% | 50% | 26% | 11% |
| 4 | 99% | 92% | 74% | 50% | 28% |
| 5 | 100% | 98% | 89% | 72% | 50% |

## What it ignores
The spike (plant, defuse, time), the round clock, weapons and armor, health, positions, side (attack or defense), and utility. A plant changes who is favored a lot, so post-plant rounds are mispredicted. See [[ADR-003 Simple win probability model]].

## How to improve it
1. Replace "alive count" with effective players (total health divided by about 150).
2. Add spike state, side and time.
3. Fit on many rounds (logistic or gradient boosting), validate on held-out rounds with log loss.
4. Add utility and ultimate state (Stage 3 in [[Utility Credit]]).

Needs hundreds of matches. See [[03 Roadmap]] Phase 2.

## Code
`wp(a, b)` in `claude/valosaber.py`. The table is also embedded in the page.
