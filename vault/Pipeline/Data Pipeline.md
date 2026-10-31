---
type: pipeline
status: current
updated: 2026-10-30
tags: [valosaber, pipeline]
---
# Data pipeline

Decision behind it: [[ADR-004 Ship shards not raw files]]. Format: [[Shard Schema]]. Limits: [[Limits and Access]].

Goal: move replay-derived data between machines without ever hitting a file size limit, and without losing consistency as the number of matches grows.

## The rule

**Never ship raw replays or the full export. Ship shards.**

Parse where the replay lives. The only thing that travels is a compact, checksummed shard of the tables the statistics need.

Measured on the Swiftplay sample (5 rounds, 8 minutes):

| Stage | Size |
|---|---|
| Raw .vrf | 15,957,425 bytes |
| Full parquet export | 9,152,735 bytes |
| **Shard (what travels)** | **183,000 bytes (1.1% of raw)** |

Shard contents: players 19 KB, kills 10 KB, damage 7 KB, effects 8 KB, positions at 4 Hz 139 KB.

Estimate, not measured: a 25-round competitive match is roughly 4 to 5 times longer, so about 1 MB per shard (positions dominate). At that size, 100 matches is about 100 MB total, stored as about 13 parts of 8 MB or less.

## Flow

1. **Parse locally.** Replays go through the stats-layer export ([[Coding Agent Brief]]). Raw files stay in cold storage and are never uploaded.
2. **Pack.** One folder per match, `shards/<match_id>/`, containing the parquet tables and `index.json`.
3. **Ship.** Upload the shard folders to a shared inbox (options below).
4. **Ingest.** `python ingest.py INBOX WAREHOUSE` verifies every shard and merges them into `WAREHOUSE/<table>/part-0001.parquet` and so on. Every part is capped at 8 MB (adjustable with `--max-mb`).
5. **Rebuild.** Metrics and the Valosaber page are recomputed from the warehouse.

## Consistency guarantees (built into the shard and ingest)

- **Stable match ID**: the replay's own GUID or friendly name. The same replay always produces the same ID.
- **`schema_version`** in every `index.json`. An unknown version is rejected, not guessed at.
- **SHA-256 and row count per table**. A truncated or corrupted upload fails verification.
- **Reject whole shards, never partial ones.** A bad shard is listed by name and nothing from it is merged.
- **Idempotent.** `catalog.json` records every ingested match, so re-running the same inbox skips what is already in. Re-uploading is always safe.
- **Size-capped parts.** No file in the warehouse exceeds the cap, so every part can pass through a 10 MB connector.

Tested on the sample: one valid shard accepted, one deliberately corrupted copy rejected ("kills: checksum mismatch"), and a second run skipped the already-ingested match.

## Where to put the files

| Option | Limit that matters | Verdict |
|---|---|---|
| **Google Drive folder** (`valosaber/inbox`, `valosaber/warehouse`) | The Drive connector downloads at most 10 MB per file | Works now. Keep parts at 8 MB or less, and keep `catalog.json` in the same folder. |
| **Attach in chat** | Attachment size per message | Fine for a handful of shards at about 0.2 to 1 MB each. Zip several together. |
| **GitHub repo** (not linked to this account yet) | 100 MB per file | Best long-term: the whole warehouse lives in one place and a session can clone it. Needs GitHub connected in settings. |
| **Project docs** | Text documents only | Use for scripts, lookup tables and this guide. Not for parquet. |

## What is still prototype

- The shard is produced by my script (`valosaber.py`), not yet by the main pipeline. The stats-layer task for the coding agent should output this same shard format so the two line up.
- Only one real match has been through it.
- I have not confirmed that the Drive connector can create binary files, so uploads should come from your side.
- Position data is at 4 Hz and quantized to int16. If map-level analysis needs finer positions, that is the first thing to revisit, since it is most of the shard.
- A bug found while building this: the cast extractor translates three codenames to public names (Wushu to Jett, Wraith to Omen, Hunter to Sova) while actor paths keep the raw codenames. A join between them silently drops those players. The shard script now translates through `codenames.json`, and asserts that all 10 players have positions.
