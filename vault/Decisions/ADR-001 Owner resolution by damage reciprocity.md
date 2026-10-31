---
type: decision
status: accepted
updated: 2026-10-30
tags: [valosaber, decision, data]
---
# ADR-001: Resolve combat-report owners by damage reciprocity

## Context
Each player's combat report lives on an `OwnerExclusivePlayerInfo` actor (10 per match). Nothing in the export says which player owns which. The `Owner` and `AresController` fields point at GUIDs (actor GUID plus 2) that are missing from `actors`. See [[Replay Data Guide]].

## Decision
Match owners to players by requiring that the damage player X dealt to Y equals the damage Y received from X, in every round. Team comes from the participants (a player's report only lists enemies). Search all 5! × 5! assignments for zero mismatch.

## Result
Exactly one assignment has zero cost (the runner-up cost 3,100). Total damage dealt equals total damage received (6049.78).

## Consequences
- Exact and self-validating, and it fails loudly if ambiguous.
- Fragile in matches with little damage (ties). The coding agent should find the real link ([[Coding Agent Brief]]) and keep this as a check.
