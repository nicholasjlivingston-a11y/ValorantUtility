---
type: decision
status: proposed
updated: 2026-11-01
tags: [valosaber, decision, pipeline]
---
# ADR-008: Parquet analytics tables are the primary route; the CSV route becomes an adapter

**Status:** proposed, waiting for the user (open question 14).

## The two routes
- **CSV route (meta agent's bootstrap):** `scripts/spatial_layer.py` reads eight CSV tables (`match`, `timeline`, `rounds`, `kills`, `utility_casts`, `utility_casts_linked`, `utility_effects`, `player_positions`) that no script in the package produces, and writes canonical events, ability instances and interactions, validation findings and map metadata.
- **Parquet route (ours):** `parser/meta_tables.py` writes the 15 data groups the meta agent's requirements define, as native-resolution parquet tables with source field names, an evidence column, a completeness report and gap codes. The stats shard is projected from the same export.

## Decision
Make the parquet `analytics_tables/` the only producer contract. Keep `spatial_layer.py`, but feed it through a small adapter that writes its eight CSVs from the parquet tables, so there is one definition of each table and the spatial layer still works.

## Why
- The requirements document names the 15 groups and demands native resolution and lineage; the CSV names do not match them and the CSV route has no producer.
- Parquet keeps types and is already the shard format (ADR-004).
- The adapter is a thin projection and can be written once ability lifecycle stages exist; until then the CSV tables would be mostly empty (only cast records and actor open/close are extracted).

## Consequences
- The CSV layer is not a source of truth. Its outputs are DERIVED.
- Nothing is lost: if the meta agent prefers CSV for its own use, the adapter produces it on demand.
- If the user rejects this, the CSV route needs a producer that someone must write and validate against the parquet tables anyway.
