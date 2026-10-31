---
type: overview
status: current
updated: 2026-10-30
tags: [valosaber, scope]
---
# Project Overview

## Goal
Build a statistical framework for Valorant that measures what players and utility actually contribute to winning rounds, the way sabermetrics did for baseball. See [[07 Sabermetrics Notes]] for the ideas we borrow.

## Questions the framework should answer
- How much did each player add to their team's chance of winning, once the situation is accounted for?
- Which kills were high-stakes, and who set them up?
- Is a player's kill count skill or luck? (Needs many matches.)
- How much of a round win comes from utility: smokes, flashes, heals, traps? See [[Utility Credit]].
- What is a replacement-level player, and how do maps and sides change expectations? (Needs many matches.)

## Scope
**In scope**
- Parse replays into clean tables (a coding agent maintains the parser; see [[Coding Agent Brief]])
- Metrics: [[Win Probability Model]], [[WPA and Leverage]], [[Rate Indexes]], [[Utility Credit]]
- A published page showing the results
- A reference layer so names are right: [[Agents]], [[Maps]], [[Abilities]]
- A pipeline that moves data around without file size limits: [[Data Pipeline]]

**Out of scope for now**
- Live, in-match tracking
- Player rank or MMR (not in the replay)
- Anything that identifies real players (replay names are anonymized)

## Success looks like
1. A win-probability model fitted on hundreds of matches, including spike, side and time
2. Replacement level and map or side factors defined from a pool of matches
3. Utility effectiveness measured from lift, not assumed weights (Stage 2 and 3 in [[03 Roadmap]])
4. A new replay goes from file to updated page with one repeatable run ([[Run Order]])
5. Every name on every output is confirmed or labeled as unconfirmed

## People and tools
- **Owner and decision maker:** the user.
- **Claude:** analysis, metrics, the page, the vault.
- **Coding agent (Gemini):** maintains the replay parsing pipeline. Its brief is in [[Coding Agent Brief]].
- **Replay parser:** `vrfkit` plus the `valorant-vrf` skill (extract casts, build tables, identify agents).

## Constraints
- The Claude session runs in a cloud environment. It cannot see the user's computer or Obsidian unless the user attaches files. See [[Limits and Access]].
- Network access is an allowlist. `valorant-api.com` is blocked. Web search and fetch work for allowed pages.
- The Google Drive connector downloads at most 10 MB per file. A 159 MB replay zip could not be read.
- GitHub is not linked to the account.
