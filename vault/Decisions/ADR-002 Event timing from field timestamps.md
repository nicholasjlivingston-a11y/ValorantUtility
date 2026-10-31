---
type: decision
status: accepted
updated: 2026-10-30
tags: [valosaber, decision, data]
---
# ADR-002: Take event time from the field row timestamp

## Context
Kill times could come from the combat report's `GameTime` (whole seconds), from ability `CastTime` plus an offset (accurate to about 2 s), or from the field row's own `time_ms`.

## Decision
Use the `time_ms` of the row where `bDidKill` becomes true. It is the replay's own clock.

## Result
Largest gap from a rebuilt kill to its `characterDeath` event: **9 ms**, across 34 kills. The ability timing offset check, by comparison, put casts within about 0.1 to 1.7 s of deaths on the few kill-tagged casts.

## Consequences
- Kill, damage and death timing are precise.
- Ability effect timing is the loosest clock in the data, so utility windows are wide (8 s). The coding agent should provide effect start and end times on the replay clock ([[Coding Agent Brief]]).
