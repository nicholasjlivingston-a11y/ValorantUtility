---
type: decision
status: accepted
updated: 2026-10-30
tags: [valosaber, decision, pipeline]
---
# ADR-004: Ship compact shards, never raw replays

## Context
The Google Drive connector downloads at most 10 MB per file. A 159 MB replay package could not be read at all. Raw replays are about 16 MB each and the parquet export about 9 MB.

## Decision
Parse where the replay lives. Move only a compact, checksummed shard per match ([[Shard Schema]]), merged into parts of 8 MB or less ([[Data Pipeline]]).

## Result
Sample shard: 183 KB, about 1% of the raw replay.

## Consequences
- Shard tables must contain everything the statistics need, so the coding agent's stats layer must emit this format ([[Coding Agent Brief]]).
- Raw replays stay in cold storage; they are needed again only if the parser changes.
- Any change to a shard table needs a new `schema_version`.
