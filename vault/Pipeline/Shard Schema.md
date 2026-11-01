---
type: schema
status: prototype
updated: 2026-10-30
tags: [valosaber, pipeline, schema]
schema_version: 2
---
# Shard schema (version 2, prototype)

One folder per match, named by `match_id` (the replay's GUID or friendly name). Parquet, zstd compressed. See [[Data Pipeline]] for the flow and [[ADR-004 Ship shards not raw files]] for why.

## `index.json`
`schema_version` (2), `match_id`, `build` and `source_build`, `mode`, `rounds`, `created_utc`, `position_actor_coverage`, `source_sha256`, `run_id`, `parser` (vrfkit SHA-256 and repo commit), `positions_4hz_conversion` (bucket rule, rounding, integer types, missing handling), and `tables`: for each table `rows`, `bytes`, `sha256`.

## Tables
| Table | Columns |
|---|---|
| `players` | `match_id`, `uuid`, `agent`, `codename`, `team`, plus computed stats (`kills`, `deaths`, `dmg`, `dmg_taken`, `adr`, `adr_idx`, `wpa`, `kwpa`, `dwpa`, `kst_pct`, `fb`, `fd`, `trade_kills`, `traded_deaths`, `clutch_kills`, `util_assisted_kills`, `util_assists_given`, `avg_li_kills`, `xk`, `kill_luck`, `rank_wpa`, …) |
| `kills` | `match_id`, `rnd` (int8), `t` (int32 ms), `killer`, `victim`, `kteam`, `k_alive`, `v_alive`, `wpa`, `li`, `opening`, `victim_traded`, `trade_kill`, `clutch`, `util_assist` |
| `damage` | `match_id`, `rnd`, `owner`, `other`, `dealt`, `recv`, `hits_d`, `hits_r`, `did_kill` |
| `effects` | `match_id`, `cast`, `round`, `abs_ms`, `caster`, `slot_id`, `tag`, `value`, `target`, `per_target_value` |
| `positions_4hz` | `match_id`, `uuid`, `t` (ms, 250 ms buckets), `x`, `y`, `z` (nullable int16 world units, rounded), `yaw_cd` (nullable uint16, degrees x 100, 0 to 36000) |

Player references (`killer`, `victim`, `owner`, `other`, `uuid`, `caster`, `target`) are subject UUIDs or agent labels as noted in the code. Check `valosaber.py` for the exact one per column before joining.

## Fixed in version 2 (2026-10-31)
- **Yaw was silently clipped.** Version 1 stored yaw in int16 and clipped at 32,767, so every facing above 327.67 degrees was wrong: 1,726 of 16,152 rows (10.7%) in the sample. Version 2 stores uint16 and fails the shard on any out-of-range value instead of clipping. The version 1 shard was replaced and the warehouse rebuilt; `ingest.py` rejects version 1.
- Coordinates and yaw may be missing (null); they are never replaced by zero.
- The roster join no longer depends on a skill folder that does not exist in Colab (it now reads `parser/skill/codenames.json`); without that, three players would have been silently dropped.

## Known flaws still to fix
- `players` and `kills` mix **raw facts** with **model outputs** (`wpa`, `li`, derived stats). Raw tables should hold only facts; metrics should be computed downstream so a model change does not need re-shipping.
- `mode` and `build` are hardcoded in the prototype; they should come from `manifest.json`.
- No `rounds`, `spike_events`, `economy`, `ability_casts` with decoded names, `utility_objects` or `player_state` tables yet. These are in the [[Coding Agent Brief]].
- Player references use a mix of UUIDs and names; use UUIDs everywhere and join names from a `players` table.

## Validation on read
`ingest.py` checks `schema_version`, file presence, SHA-256 and row counts. Any failure rejects the whole shard.
