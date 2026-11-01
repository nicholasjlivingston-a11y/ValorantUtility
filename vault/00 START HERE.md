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
**GitHub (source of truth):** `nicholasjlivingston-a11y/ValorantUtility`, branch `main`: `vault/` (these notes), `parser/` (code), `data/` (lookup, classes, registry, warehouse), `inbox/`, `tools/build_bootstrap.py`, `bootstrap/valosaber_bootstrap_v3.zip` (package for the coding agents; no vrfkit inside). Attach it at the start of a chat, clone it, read this note. Process uploads with "process the inbox" ([[Queue]]).

**Claude project "Utility retry"** holds copies for a chat with no repo: `claude/START_HERE.md` (this handoff), `claude/Master_Parser_Prompt.md`, `claude/Extraction_Requirements.md`, `claude/Current_State.md`, plus the code (`valosaber.py`, `batch_process.py`, `shard_checks.py`, `golden_sample_test.py`, `colab_bootstrap.py`, `register_vrfkit.py`, `ingest.py`, `baselines.py`, `build_site.py`, `build_table_swiftplay.py`, `valosaber_template.html`) and data (`name_lookup_build13_08.json`, `agent_classes.json`, `vrfkit_supported_builds.json`, `data_pipeline.md`). If the repo and the project disagree, the repo wins. Refresh the project copies at the end of any session that changed code.

Published page: https://claude.ai/artifact/S1xAQwFf29rMUka9zPoa1b (private).

## Two agents, one pipeline
The coding agent (Gemini in Colab) turns raw `.vrf` into `analytics_tables/` (meta agent's 15 data groups, [[Extraction Requirements]]) and a schema-2 `stats_shard/` (this analyst). Its task is [[Master Parser Prompt]]. Only a **registered** vrfkit may run ([[Bootstrap Package]]); the pinned one knows builds to 13.08, so 13.09 (Hush) replays need a newer vrfkit registered first. Golden test: `parser/golden_sample_test.py`.

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
