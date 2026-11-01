---
type: pipeline
status: reviewed-not-integrated
updated: 2026-10-30
tags: [valosaber, pipeline, bootstrap]
---
# Bootstrap package

## Version 3 (2026-11-01), the one to hand to agents
Built by `python3 tools/build_bootstrap.py OUT.zip --source-zip <old bootstrap> --golden-export <export dir>`; it mirrors the repo layout and re-checks every file hash after reopening. Contents: `README.md`, `AGENT_TASK.md` (master prompt plus addendum), `docs/EXTRACTION_REQUIREMENTS.md`, `knowledge/` (Reference, Decisions, Metrics, shard schema, run order, current state, open questions), `parser/`, `data/` (lookup, classes, registry), the meta agent's `scripts/ schemas/ config/ ontology/ run_pipeline.py` unchanged, `golden_sample/` (shard, events, manifest, expected values), `bin/README.txt`, `PACKAGE_MANIFEST.json`. About 0.4 MB.
- **vrfkit is deliberately left out.** The old bootstrap's binary is the 13.08-era build (`afe615e8...c04a`); including it invites the agent to run it on 13.09 replays. Keep the real one in Drive `valosaber/bin/`; `colab_bootstrap.py` finds it and refuses anything unregistered. `--with-vrfkit` can pack a registered binary if wanted.
- Tested from a fresh extraction: golden test passes (EXPORT_PIPELINE_VALIDATED), an unregistered file is refused, all scripts compile. Not yet run in Colab.
- Rebuild it after any change to the parser, registry or master prompt, and note the repo commit (stored in the manifest).

## Version 1 (reviewed 2026-10-30)

File: `parser/valorant_complete_pipeline_bootstrap_package (2).zip` (8.7 MB, 38 MB unpacked). Reviewed 2026-10-30. Nothing from it was run.

## Contents
| Path | What it is |
|---|---|
| `bin/vrfkit` | 38 MB Linux x86-64 executable. **Not inspected or run.** Presumably the parser that made our exports |
| `run_pipeline.py` | Runs `./bin/vrfkit export <file> --out parsed_outputs/<name> --checkpoints` on every `.vrf` in `./raw_replays` |
| `scripts/spatial_layer.py` | Builds a canonical event layer from **CSV** tables (`match.csv`, `timeline.csv`, `rounds.csv`, `kills.csv`, `utility_casts.csv`, `utility_casts_linked.csv`, `utility_effects.csv`, `player_positions.csv`). Writes `canonical_events.csv`, `ability_instances.csv`, `ability_interactions.csv`, `validation_findings.csv`, `map_metadata.json` and a hashed `manifest.json` |
| `schemas/utility_recovery_event.schema.json` | Schema for recovered or candidate utility evidence, with evidence classes and a recovery status |
| `config/map_registry.json`, `config/maps/icebox.json` | 13 maps, each only a reference image: no regions, no connections, geometry unverified |
| `ontology/` | Ability ontology (2 entries) and a decision ledger (2 questions) |

## How it fits
- **Same principles as ours.** Evidence classes (observed, derived, inferred), unknowns stay unknown, no invented map names. Matches [[ADR-005 Names only when confirmed]].
- **Not plug-and-play.** `spatial_layer.py` reads CSV tables from "the existing parser", which are not the parquet export or the shard tables we use. Its table names and columns differ from ours, and our pipeline does not produce them. Treat it as a second route to utility events until the two are reconciled.
- **Utility timing.** Its cast-to-effect linking (`link_delta_ms`, `effect_lag_s`) is the same need as the effect start and end times we asked for in [[Coding Agent Brief]]. Compare it with `effects` in [[Shard Schema]].
- **Maps.** Registry covers Abyss, Ascent, Bind, Breeze, Corrode, Fracture, Haven, Icebox, Lotus, Pearl, Split, Summit, Sunset. There is no map code mapping, so it does not settle whether `Pitt` is Pearl ([[04 Open Questions]] question 4). The referenced `source_maps/` images are **not in the zip**.
- **Ontology.** See [[Ability Ontology]].

## Safety review
Text files only read and write local files. `run_pipeline.py` uses `subprocess` to call the bundled binary; `spatial_layer.py` makes no network calls and runs no external commands. The binary cannot be verified from here.

## Repository note
A 38 MB binary in git stays in the history for good. Preferred: keep `bin/vrfkit` out of the repo (add it to `.gitignore`, or use Git LFS or a release asset). The zip is already committed; do not add the unpacked binary on top of it.

## What vrfkit is, and which binary is right (checked 2026-10-31)
- vrfkit is an open-source parser (Apache-2.0, version 0.3.0, repository `yakisoba0728/vrfkit`, derived from `michel-giehl/ValorantReplayParser`). The source is in Drive as `valosaber/bin/vrfkit-main.zip` (1.5 MB).
- **The bootstrap binary** (38,327,056 bytes, SHA pinned in `parser/vrfkit.sha256`) contains the build path `/content/vrfkit-src/vrfkit-main`, so it was compiled in Colab from that same source. It knows replay builds up to `release-13.08`, and it produced our sample export. This is the one with evidence.
- **The Drive binary** `vrfkit_bin/vrfkit` (40,934,608 bytes, dated 2026-10-18) could not be hashed or inspected because the Drive connector stops at 10 MB. Its provenance is unknown. Do not pin it until its hash is known and the sample still passes.
- **Build support is thin at 13.08.** The source README says builds 11.06 to 13.06 were verified on 1,018 replays, but 13.08 on only 2, and one of those fails a checkpoint cross-check. It also says structured-array child rows (the kind the combat reports use) are admitted on **no** measured route yet for 13.08. Our sample decoded anyway, but treat 13.08 results as less proven than older builds.
- **Patch 13.09 (Hush) is not supported** by this source (it lists builds through 13.08). Replays from 13.09 or later may fail or decode partially; expect to need a newer vrfkit.

## vrfkit registry (added 2026-10-31)
`data/vrfkit_supported_builds.json` lists each vrfkit binary by SHA-256 with the replay builds it contains. `parser/register_vrfkit.py <binary or bootstrap zip> --label "text"` computes the hash and the build list by reading the file as bytes, never by running it, and prints the entry (add `--write` to store it). `colab_bootstrap.py` accepts any registered hash. The user reported on 2026-10-31 that a 13.09-capable vrfkit is active; it is **not registered yet**. To register it, run the command in Colab on that file and send the output.

## vrfkit in Colab with a Gemini agent
Colab machines are temporary, so the binary must be put there at the start of every session.
- Keep one copy of `vrfkit` in Google Drive, not in git. As of 2026-10-31 it is held inside the bootstrap zip at `MyDrive/valosaber/bin/valorant_complete_pipeline_bootstrap_package (2).zip` (confirmed in Drive; 8,690,453 bytes). The other folder `vrfkit_bin/` holds an unrelated 40.9 MB binary of unknown origin; do not use it.
- `parser/vrfkit.sha256` pins the exact binary (SHA-256 `afe615e8...c04a`, 38,327,056 bytes, from this package). `parser/colab_bootstrap.py` mounts Drive, copies the file, checks the hash, marks it executable, and stops on a mismatch. It never downloads and never runs the binary. Tested locally for both a match and a mismatch; not yet tested inside Colab.
- When vrfkit is updated, replace the Drive copy and the `.sha256` file in the same commit, and write the new build in [[05 Changelog]].
- Replays and outputs also live in Drive; Colab's disk is lost when the session ends.
- Give the agent a GitHub token only through Colab Secrets (a fine-grained token limited to this one repo, contents write). Never paste it in a cell or a notebook.
- With no argument, `colab_bootstrap.py` looks in `MyDrive/valosaber/bin/` for the bootstrap zip first, then a loose `vrfkit`. It also accepts the bootstrap zip itself as the source and reads `bin/vrfkit` from inside it, still checking the hash. A copy of the zip (8,690,453 bytes, the same size as the one reviewed here) sits at the root of the user's Drive; it could not be downloaded to compare, because the connector fails above 10 MB of transfer.
- The agent must run `colab_bootstrap.py` first and must not fetch a binary from anywhere else.

## Next steps
1. Decide whether the CSV route or the parquet shard route is the main one. They should not both define the utility tables.
2. If CSV stays: ask the coding agent what produces those eight CSV tables and for a sample match.
3. Supply the `source_maps/` images if the map work continues.
