---
type: handoff
status: current
updated: 2026-10-31
tags: [valosaber, handoff]
---
# START HERE

This note gets a new chat (or a new person) productive in a few minutes. Keep it under one screen of facts. Details live in the linked notes.

## What this project is
**Valosaber** applies sabermetric thinking to Valorant. Baseball moved from counting stats to measuring what a player adds to winning, with context and luck removed. We do the same for Valorant, using data parsed out of match replay files (`.vrf`). The project in Claude is called **"Utility retry"**.

A first version exists for **one** Swiftplay match: a published page with win probability added (WPA), leverage, indexed rate stats, trade and clutch stats, and a utility-adjusted credit model with adjustable weights. See [[02 Current State]].

## Read in this order
1. [[02 Current State]] for what is done, in progress and blocked
2. [[01 Project Overview]] for goals, scope and constraints
3. [[Replay Data Guide]] for the traps in the data (read before touching any table)
4. [[Agents]], [[Maps]], [[Abilities]] for names, with a status on every entry
5. [[Metrics Index]] for what each statistic means
6. [[03 Roadmap]] and [[04 Open Questions]] for where we are going
7. [[Data Pipeline]] and [[Run Order]] for how to regenerate everything

## Paste this into a new chat
```
I'm continuing the Valosaber project (Claude project "Utility retry"): sabermetric-style statistics for Valorant, built from parsed replay (.vrf) data.

Before doing anything:
1. Read the project docs, starting with claude/START_HERE.md. If the Obsidian vault notes are attached or pasted, "00 START HERE" and "02 Current State" take priority.
2. Reply in five lines or fewer: what the project is, the current state, and the next step you would take.

Rules:
- Never state an agent, map or ability name that is not marked confirmed in the lookup file or the Reference notes. Show the codename and the status instead.
- Verify before asserting. Say which numbers are assumptions.
- I want results without retrying. Act on clear requests. Ask only when a wrong guess is expensive.

Today's goal: <fill in>
```

## Where the files are
Saved in the Claude project "Utility retry" (these are what a new chat can read):
- `claude/START_HERE.md`: this handoff
- `claude/name_lookup_build13_08.json`: agent, map and ability names with evidence
- `claude/valosaber.py`: computes all metrics and the compact shard
- `claude/build_table_swiftplay.py`: patched copy of the skill's table builder (the original breaks on Swiftplay)
- `claude/valosaber_template.html` and `claude/build_site.py`: regenerate the page
- `claude/ingest.py`: verifies and merges shards
- `claude/data_pipeline.md`: the size-safe pipeline guide

**GitHub:** `nicholasjlivingston-a11y/ValorantUtility` (branch `main`) holds `vault/`, `parser/`, `data/`, `inbox/`. Attach it at the start of a chat, clone it, and read `vault/00 START HERE.md`. Process new uploads with "process the inbox" ([[Queue]]).

The published page: https://claude.ai/artifact/S1xAQwFf29rMUka9zPoa1b (private, owner only).

## Colab parsing (the coding agent's job)
1. Clone the repo (`nicholasjlivingston-a11y/ValorantUtility`).
2. `python3 parser/colab_bootstrap.py` mounts Drive, reads `vrfkit` from the bootstrap zip in `MyDrive/valosaber/bin/`, checks it against `parser/vrfkit.sha256`, and refuses on a mismatch.
3. Parse replays, write shards, push to `inbox/` or save to Drive. Then say "process the inbox" here. See [[Bootstrap Package]], [[Queue]], [[Unified Pipeline Brief]].

## Rules that are not negotiable
- **Names are confirmed or they stay as codenames.** See [[ADR-005 Names only when confirmed]].
- **No metric without its assumptions written down.** See [[Win Probability Model]] and [[ADR-003 Simple win probability model]].
- **Reconcile before trusting.** Kills must match death events and damage dealt must equal damage received. See [[Replay Data Guide]].
- **Ship shards, never raw replays.** See [[ADR-004 Ship shards not raw files]].
- **One match is a small sample.** Say so whenever a number depends on it.

## How the user works
- Wants results on the first try. Repeating a request is a failure signal.
- Says "I say build" or "do this now" when he wants action, not options.
- Likes a short summary of what changed, what to trust, and one next step.
- Free Claude plan: no scheduled tasks, no browser or computer control. This session runs in a cloud environment with no access to his files unless he attaches them.

## Close every session
Follow [[06 How to update this vault]]: update [[02 Current State]], add a line to [[05 Changelog]], fix any reference entry whose status changed.
