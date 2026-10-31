---
type: metric
status: built-awaiting-data
updated: 2026-10-30
tags: [valosaber, metrics, baselines]
---
# Baselines (three peer groups)

Decision: [[ADR-007 Three peer groups for comparison]]. Code: `parser/baselines.py`.

## What it computes
For each player-agent-mode and each metric, a per-round rate compared against the overall, class and agent peer groups. Metrics: WPA (and kill and death parts), kills, deaths, damage dealt and taken, first kills and deaths, trade kills, traded deaths, clutch kills, util-assisted kills, util assists given, expected kills. See [[Metrics Index]].

## Reading the output
| Column | Meaning |
|---|---|
| `raw_rate`, `shrunk_rate` | Player's per-round rate, and the rate pulled toward the parent peer mean for small samples |
| `peer_mean`, `peer_sd`, `peer_n` | Round-weighted, leave-one-out peer baseline and group size |
| `above_peer`, `z` | Shrunk rate minus peer mean, and in peer standard deviations |
| `percentile` | Position of the shrunk rate within the group, 0 to 1 |
| `index` | 100 = peer average; only for always-positive metrics |
| `status` | `ok`, `low_rounds` (under 20 rounds), `insufficient_peers` (fewer than 8 others, so no score) |

Emphasis by class is a reading guide, not a different formula: opening-duel rates matter most in the Duelist comparison; util-assisted kills and util assists given in Initiator and Controller; trades, clutches and survival in Sentinel.

## Run
```
python3 -I parser/baselines.py data/warehouse data/agent_classes.json data/baselines
python3 -I parser/baselines.py --selftest
```
Options: `--min-rounds 20`, `--min-peers 8`, `--k 50`, `--confirmed-classes-only`.

## Limits
- Class names are confirmed for all 29 agents (2026-10-30); recheck when Riot changes a role.
- With one match nothing is scored at class or agent level. The overall scope runs but every row is `low_rounds`.
- `kst_pct` is not included because it cannot be summed across matches without its round counts. Add it when the shard holds the counts.
- Peer baselines use raw rates, while the player's score uses the shrunk rate. Revisit if groups stay small.
- Skill bracket and rank are not controlled for.
