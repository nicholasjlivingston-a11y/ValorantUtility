---
type: queue
status: current
updated: 2026-10-30
tags: [valosaber, queue]
---
# Shard queue

Add one row when you push a shard to `inbox/`. Claude updates the status after ingest.

| match_id | date pushed | mode | status | note |
|---|---|---|---|---|
| 4c1d14ba | 2026-10-30 | Swiftplay | ingested | raw export zip pushed, parsed to a 183 KB shard, merged into data/warehouse. See [[4c1d14ba Swiftplay Pitt]] |

Status values: waiting, ingested, rejected (with reason).
Process: see [[Run Order]] and [[Limits and Access]].

## Two kinds of upload
- **Raw export zip** (vrfkit output: fields, movement, manifest and so on, about 9 MB). Claude parses it into a shard first, then ingests. This is what the test used.
- **Shard folder** (has `index.json`). Claude ingests it directly.
Raw exports can be pushed to `inbox/`; once ingested they can be deleted from the repo, since the shard holds what the statistics need.
