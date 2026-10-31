---
type: decision
status: accepted-temporary
updated: 2026-10-30
tags: [valosaber, decision, utility]
---
# ADR-006: Utility credit is zero-sum and adjustable

## Context
We want utility to count toward round wins. Crediting utility on top of the killer would double count and inflate totals.

## Decision
Split each kill's win probability between killer, utility setters and damage assisters so the shares add back to the kill's value. Make the weights visible sliders. Healing is separate and additive. Details in [[Utility Credit]].

## Why adjustable
The weights are guesses until Stage 2 can measure lift. Showing how rankings move with the weights is more honest than hiding one choice.

## Checks
- Total shared equals total kill WPA (5.96 of 5.96).
- Killer-only weights reproduce plain WPA exactly.

## Consequences
Replace the default weights with measured ones when there are about 30 matches and precise effect timing ([[03 Roadmap]] Phase 3).
