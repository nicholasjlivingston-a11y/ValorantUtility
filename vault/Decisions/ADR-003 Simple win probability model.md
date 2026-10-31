---
type: decision
status: accepted-temporary
updated: 2026-10-30
tags: [valosaber, decision, model]
---
# ADR-003: Start with a simple, theoretical win-probability model

## Context
A fitted model needs hundreds of matches. We have one.

## Decision
Use the alive-count recurrence in [[Win Probability Model]], clearly labeled as theoretical, the way early run-expectancy tables were before enough data existed.

## Consequences
- Every WPA and leverage number inherits its assumptions: equal skill, no spike, no clock, no weapons or position.
- Post-plant rounds are mispredicted.
- Replace it in Phase 2 ([[03 Roadmap]]). Keep the old model in the code so old and new can be compared.
- The page says what the model ignores in its "How far to trust it" section.
