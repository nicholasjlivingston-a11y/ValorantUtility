---
type: runbook
status: current
updated: 2026-10-30
tags: [valosaber, pipeline, runbook]
---
# Run order (replay to page)

Regenerates everything from a parsed export. Verified end to end on the sample match: the rebuilt page is byte-identical to the published one.

## Setup (once per session)
```
pip install --break-system-packages pyarrow pandas
```
Run Python with `-I` when it reads untrusted files. Put the skill scripts and the project scripts in different folders.

## Steps
1. **Export.** The replay is parsed by `vrfkit` (the coding agent's pipeline). Expected tables in `export/`: `fields`, `checkpoint_fields`, `actors`, `events`, `net_guids`, `movement`, plus `manifest.json`. Exported files may carry a hash prefix; strip it so they are named `fields.parquet` and so on.
2. **Casts.** From the `valorant-vrf` skill folder:
   `python3 -I extract_casts.py --export export --out out/casts_raw.parquet`
3. **Effects table.** For Swiftplay use the patched copy; for standard modes the skill's own `build_table.py` should work:
   `python3 -I build_table_swiftplay.py --export export --casts out/casts_raw.parquet --out out/ability_effects.csv`
4. **Metrics and shard.**
   `python3 -I valosaber.py export out/ability_effects.csv name_lookup_build13_08.json metrics/valosaber.json [shard_dir match_id raw_vrf_bytes]`
   Run from the folder that contains `export/` and `out/`; the script reads `out/casts_raw.parquet` next to `export/`.
5. **Page.**
   `python3 -I build_site.py metrics/valosaber.json valosaber_template.html valosaber.html`
6. **Publish** `valosaber.html` as an artifact. Publishing the same file path redeploys to the same URL.
7. **Merge shards.**
   `python3 -I ingest.py inbox warehouse --max-mb 8`

## Files (all in the Claude project)
`valosaber.py`, `build_table_swiftplay.py`, `build_site.py`, `valosaber_template.html`, `ingest.py`, `name_lookup_build13_08.json`.

## Known limits of the scripts
- `valosaber.py` hardcodes the replay duration (480.87 s), the mode label (`Swiftplay`), a 5×5 player assumption, and the shard path layout. Generalize these when the main pipeline takes over.
- The roster step matches any PlayerState class ending in `PlayerState_C`, which works for Swiftplay and should work for standard modes. Untested on standard modes.
- The time-base check printed by the skill's own script is skipped when no kill-tagged casts exist; `valosaber.py` does its own kill-to-death check instead.
- Heavy assumptions about the sample (10 players, 2 teams of 5) are asserted, so a different layout fails loudly.
