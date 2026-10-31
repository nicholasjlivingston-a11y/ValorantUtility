---
type: decision
status: accepted
updated: 2026-10-30
tags: [valosaber, decision, names]
---
# ADR-005: Names go in outputs only when confirmed

## Context
Early in the project, guessed names looked right and were wrong. The skill itself records that two agents were guessed wrong from memory. Sequoia was suggested as Tejo and turned out to be Iso.

## Decision
- Output shows the **codename** unless the lookup marks the name `confirmed`.
- `confirmed` needs a public source or the replay's own ID plus kit evidence that agrees.
- `kit_only`, `confirmed_by_user_and_kit` and `unconfirmed` are labeled as such wherever the name appears.
- Never rely on memory for a name. Do not add a guess to `codenames.json`.

## Consequences
- Some outputs show a codename for a while. That is correct.
- The lookup carries evidence per row ([[Agents]], [[Maps]], [[Abilities]]).
- Allowing the official API would resolve most names at once ([[Limits and Access]]).
