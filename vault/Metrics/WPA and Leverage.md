---
type: metric
status: current
updated: 2026-10-30
tags: [valosaber, metrics, wpa, leverage]
---
# WPA and leverage

## Kill WPA
For a kill, with `a_k` players alive on the killer's team and `a_v` on the victim's team before it:

```
kill WPA = WP(a_k, a_v - 1) - WP(a_k, a_v)
```

The killer gets `+kill WPA`. The victim gets `-kill WPA` (the "death cost"). A player's **WPA** is the sum of their kill WPA minus the sum of their death costs. Units are **rounds**: +1.00 means the player added the equivalent of one round win. Values come from [[Win Probability Model]].

Sum of all kill WPA in the sample match: 5.96 rounds.

## Leverage index (LI)
```
raw leverage(a, b) = | WP(a, b-1) - WP(a-1, b) |
LI = raw leverage / mean raw leverage over the match's kills
```
LI of 1.0 is an average-stakes kill. Higher means more was on the line. In the sample the highest was 1.83 (Phoenix's kill in round 2, taking a 2v2 to 2v1, worth +33.3 points).

## Caveats
- WPA depends on context and is noisy. Treat one match as description, not prediction. (Baseball analysts say the same about WPA.)
- Kill credit is zero-sum between killer and victim; [[Utility Credit]] then shares the killer's side with teammates.
- The model is simple. See [[ADR-003 Simple win probability model]].

## Code
`K` table and `li_raw` in `claude/valosaber.py`.
