---
type: schema
status: prototype
updated: 2026-10-30
tags: [valosaber, pipeline, schema]
schema_version: 1
---
# Shard schema (version 1, prototype)

One folder per match, named by `match_id` (the replay's GUID or friendly name). Parquet, zstd compressed. See [[Data Pipeline]] for the flow and [[ADR-004 Ship shards not raw files]] for why.

## `index.json`
`schema_version`, `match_id`, `build`, `mode`, `rounds`, `created_utc`, `position_actor_coverage`, and `tables`: for each table `rows`, `bytes`, `sha256`.

## Tables
| Table | Columns |
|---|---|
| `players` | `match_id`, `uuid`, `agent`, `codename`, `team`, plus computed stats (`kills`, `deaths`, `dmg`, `dmg_taken`, `adr`, `adr_idx`, `wpa`, `kwpa`, `dwpa`, `kst_pct`, `fb`, `fd`, `trade_kills`, `traded_deaths`, `clutch_kills`, `util_assisted_kills`, `util_assists_given`, `avg_li_kills`, `xk`, `kill_luck`, `rank_wpa`, …) |
| `kills` | `match_id`, `rnd` (int8), `t` (int32 ms), `killer`, `victim`, `kteam`, `k_alive`, `v_alive`, `wpa`, `li`, `opening`, `victim_traded`, `trade_kill`, `clutch`, `util_assist` |
| `damage` | `match_id`, `rnd`, `owner`, `other`, `dealt`, `recv`, `hits_d`, `hits_r`, `did_kill` |
| `effects` | `match_id`, `cast`, `round`, `abs_ms`, `caster`, `slot_id`, `tag`, `value`, `target`, `per_target_value` |
| `positions_4hz` | `match_id`, `uuid`, `t` (ms, 250 ms buckets), `x`, `y`, `z` (int16 world units), `yaw_cd` (int16 centidegrees) |

Player references (`killer`, `victim`, `owner`, `other`, `uuid`, `caster`, `target`) are subject UUIDs or agent labels as noted in the code. Check `valosaber.py` for the exact one per column before joining.

## Known flaws to fix in version 2
- `players` and `kills` mix **raw facts** with **model outputs** (`wpa`, `li`, derived stats). Raw tables should hold only facts; metrics should be computed downstream so a model change does not need re-shipping.
- `mode` and `build` are hardcoded in the prototype; they should come from `manifest.json`.
- No `rounds`, `spike_events`, `economy`, `ability_casts` with decoded names, `utility_objects` or `player_state` tables yet. These are in the [[Coding Agent Brief]].
- Player references use a mix of UUIDs and names; use UUIDs everywhere and join names from a `players` table.

## Validation on read
`ingest.py` checks `schema_version`, file presence, SHA-256 and row counts. Any failure rejects the whole shard.
