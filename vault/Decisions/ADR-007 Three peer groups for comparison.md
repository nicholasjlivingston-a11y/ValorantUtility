---
type: decision
status: accepted
updated: 2026-10-30
tags: [valosaber, decision, baselines]
---
# ADR-007: Compare every player against three peer groups

## Context
Baseball compares a player to others at the same position. A Valorant duelist's opening kills and a sentinel's holds produce different numbers, so one leaderboard hides who is good at the job. Wins are the common currency, so one overall comparison is still needed.

## Decision
Every metric is stored once per **player-agent-mode** (the unit), as a per-round rate with its round count, and compared against three peer groups in the same mode:
1. **overall**: all units
2. **class**: same class (Duelist, Initiator, Controller, Sentinel)
3. **agent**: the exact agent

Rules:
- Peer mean and spread are round-weighted and **leave-one-out** (the player is not in their own baseline).
- The player's rate is **shrunk** toward the parent peer mean (agent to class to overall): `shrunk = (rounds*raw + k*prior)/(rounds+k)`, default k = 50 rounds.
- A group with fewer than 8 other units gets **no score**, only the status `insufficient_peers`. Units under 20 rounds get `low_rounds`. Both are defaults that can be changed on the command line.
- Output per comparison: raw rate, shrunk rate, peer mean and spread, peer count, above-peer difference, z, percentile, ratio index (100 = peer average, positive metrics only), status.
- Only overall is comparable across classes. Class and agent scores say who is best at the job.
- Class names follow [[ADR-005 Names only when confirmed]]: every class in [[Agent Classes]] has a status; agents with no class stay out of the class scope.
- Baselines are computed downstream from raw shards, with a `baseline_version`, so changing the definition never needs re-shipping data.

## Result or evidence
`parser/baselines.py --selftest` passes: percentiles stay in 0 to 1, shrinkage never moves a score away from the peer mean, the leave-one-out mean matches a hand calculation, small groups are flagged and not scored, an agent without a class drops out of the class scope only. On the real warehouse (one Swiftplay match) the class and agent scopes are all `insufficient_peers`, as expected.

## Consequences
- Real numbers need many matches: roughly 30 or more for stable overall and class values, many more for agent-level values.
- Depends on a stable player ID across matches, see [[04 Open Questions]] (question 10). Until confirmed, comparisons between matches treat each UUID as one player.
- Mode and build are partitions. Rank is not available yet and is not used.
- See [[Baselines]] for how to run it.
