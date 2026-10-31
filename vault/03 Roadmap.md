---
type: roadmap
status: current
updated: 2026-10-30
tags: [valosaber, roadmap]
---
# Roadmap

Each phase has an exit test. Do not call a phase done until its test passes.

## Phase 0: single-match prototype (done)
Exit test: one replay produces a published page whose numbers reconcile with the replay's own event log.
Result: passed. See [[4c1d14ba Swiftplay Pitt]].

## Phase 1: data foundation
- Coding agent adds the stats layer ([[Coding Agent Brief]]): players, rounds, spike events, kills, damage, economy, casts, utility objects, player state
- Shards in the agreed format ([[Shard Schema]]), moved with [[Data Pipeline]]
- Reference tables for agents, maps, weapons, abilities ([[Agents]], [[Maps]], [[Abilities]])
- 30+ matches including competitive

Exit test: run `ingest.py` on 30 shards with no rejects, and rebuild the page from the warehouse with no manual identity or time workarounds.

## Phase 2: real model
- Fit round win probability on many matches with alive counts, health, spike state, side, time ([[Win Probability Model]])
- Define replacement level and shrink small samples toward the mean (peer-group shrinkage is built: [[Baselines]])
- Run overall, class and agent comparisons on real data ([[ADR-007 Three peer groups for comparison]]); source agent classes ([[Agent Classes]])
- Map and side factors

Exit test: the fitted model beats the simple alive-count model on held-out rounds (log loss).

## Phase 3: utility effectiveness
- Stage 2: lift analysis (affected vs unaffected fights, matched on state), data-driven weights ([[Utility Credit]])
- Stage 3: utility in the model state, with counterfactual cast value

Needs: effect start and end times on the replay clock, charges and costs, utility object lifetimes and positions, decoded ability names.
Exit test: weights come from data, with confidence intervals, and agree across maps.

## Phase 4: product
- Multi-match page: player pages, agent pages, map and side views
- Scheduled refresh when new shards arrive (needs a paid plan or an external runner)

## Parking lot
- Positioning metrics (spacing, trade distance, site control) once map geometry exists
- Accuracy and shot data
- Vision and information metrics
