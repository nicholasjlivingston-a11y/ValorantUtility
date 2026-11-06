#!/usr/bin/env python3
"""Single entry point.

  Existing exports (no vrfkit, no .vrf needed)  -- migration path for the seven-match cohort:
      python3 parser/run_pipeline.py --from-exports EXPORTS_DIR --out OUT_DIR
      EXPORTS_DIR may hold export folders (each with manifest.json + parquet) and/or export.zip files from the outbox
      (<match_id>/*.parquet inside). Each match is normalized on its own; one failing match never stops the others.

  Raw replays (needs the shipped vrfkit in bin/):
      python3 parser/run_pipeline.py --replays replays/ --vrfkit bin/vrfkit --out outbox/
      (delegates to parser/batch_process.py, which now also runs the normalization layer)

Writes per match  OUT/<match_id>/normalized/*.parquet, parser_diagnostics.json, pipeline_handoff.json
and for the cohort OUT/cohort_handoff.json + OUT/cohort_report.csv.
"""
import argparse, csv, json, subprocess, sys, tempfile, time, zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent

# which outputs are built from an existing vrfkit export, and which would need new decoder output
SOURCE_MATRIX = {
    "from_existing_export": ["players", "teams", "agents", "actors", "actor_lifecycle", "netguid_mappings", "actor_ownership_intervals", "identity_crosswalk", "roster",
                             "unresolved_identities", "map_metadata", "coordinate_systems", "movement", "player_positions", "position_coverage", "position_anomalies", "rounds",
                             "events", "event_payloads", "replicated_fields", "round_boundaries", "spike_events", "ability_casts", "utility_objects", "utility_object_observations",
                             "utility_lifecycle_events", "utility_effects", "utility_targets", "utility_statistics", "utility_statistic_reconciliation", "unresolved_utility_records",
                             "combat_events", "damage_events", "kill_death_ledger", "combat_reconciliation", "normalized_match", "map_position_index", "utility_lifecycle_index",
                             "event_provenance_index"],
    "needs_new_decoder_output": [
        {"item": "server tick / packet id / channel index per event and per movement row", "why": "events.parquet and movement.parquet carry only time_ms; fields.parquet has packet and channel but events do not"},
        {"item": "ability id / ability name / slot label table", "why": "Slot is numeric in AbilityCastsThisRound; no label enum is exported"},
        {"item": "cast attempt / failed / interrupted cast", "why": "only recorded casts exist in AbilityCastsThisRound"},
        {"item": "per-object state fields for projectiles and game objects (activation, trigger, pulse, impact, hit)", "why": "utility actors expose spawn, movement and close only; Owner/Instigator are often missing on them"},
        {"item": "object close cause (destroyed, expired, impacted, removed)", "why": "actor close records carry no reason"},
        {"item": "per-target timing for utility effects", "why": "Effects[].AffectedTargetsArray has targets and values but no per-target timestamp"},
        {"item": "BombState / phase enum labels, site label, explicit pickup/drop events", "why": "numeric values only; pickup/drop/defuse-start/interrupt/detonation are INFERRED candidates"},
        {"item": "attacker/defender side per team per round", "why": "only RoundResults.WinningTeamRole (winner's role) is exported; the WinningTeam label has no mapping to the roster team blocks"},
        {"item": "map name, per-map coordinate transform and geometry", "why": "level path gives a map code only; no origin/scale/axis data in the replay"},
        {"item": "player display names / account ids", "why": "only subject UUIDs are present"},
    ],
}


def find_exports(root: Path, tmp: Path):
    """Yield (match_name, export_dir). Accepts a single export folder, a folder of export folders, or export.zip files."""
    root = Path(root)
    if (root / "manifest.json").is_file():
        yield root.parent.name if root.name == "export" else root.name, root
        return
    for p in sorted(root.rglob("manifest.json")):
        d = p.parent
        yield (d.parent.name if d.name == "export" else d.name), d
    for z in sorted(root.rglob("*.zip")):
        try:
            zf = zipfile.ZipFile(z)
        except Exception:
            continue
        names = zf.namelist()
        if not any(n.endswith("manifest.json") for n in names):
            continue
        dest = tmp / z.parent.name / z.stem
        dest.mkdir(parents=True, exist_ok=True)
        zf.extractall(dest)
        for m in sorted(dest.rglob("manifest.json")):
            yield (m.parent.name if m.parent.name != "export" else m.parent.parent.name), m.parent


def handoff(out_m: Path, name, diag, hdr, cfg):
    tables = diag.get("tables", {})
    h = dict(
        pipeline_handoff_version="1", match=name, schema_version=diag.get("schema_version"), run_id=diag.get("run_id"), source_build=diag.get("source_build"),
        header=hdr, failed_steps=diag.get("failed_steps"), roster_source=diag.get("roster_source"),
        populated_tables=[k for k, v in tables.items() if v["rows"]], empty_tables={k: v["coverage_status"] for k, v in tables.items() if not v["rows"]},
        table_rows={k: v["rows"] for k, v in tables.items()}, gaps=diag.get("gaps"), checks=diag.get("checks"),
        source_matrix=SOURCE_MATRIX, location=str(out_m), data_contract="docs/DATA_CONTRACT.md",
        not_included="No tactical conclusions, no player scores, no map regions, no invented coordinate transforms.")
    json.dump(h, open(out_m / "pipeline_handoff.json", "w"), indent=2, default=str)
    return h


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from-exports", help="folder with existing vrfkit exports (folders and/or export.zip)")
    ap.add_argument("--replays", help="folder of raw .vrf replays (needs --vrfkit)")
    ap.add_argument("--vrfkit", default=str(HERE.parent / "bin" / "vrfkit"))
    ap.add_argument("--lookup", default=str(HERE.parent / "data" / "name_lookup_build13_08.json"))
    ap.add_argument("--out", required=True)
    ap.add_argument("--config", default=str(HERE / "pipeline_config.json"))
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    if a.replays:
        cmd = [sys.executable, str(HERE / "batch_process.py"), "--replays", a.replays, "--outbox", str(out), "--vrfkit", a.vrfkit, "--lookup", a.lookup, "--config", a.config]
        if a.only:
            cmd += ["--only", *a.only]
        if a.force:
            cmd += ["--force"]
        sys.exit(subprocess.run(cmd).returncode)
    if not a.from_exports:
        ap.error("give --from-exports or --replays")
    cfg = json.load(open(a.config))
    rows, cohort = [], []
    sys.path.insert(0, str(HERE))
    import normalize
    mr = HERE.parent / cfg["paths"]["map_registry"]
    with tempfile.TemporaryDirectory() as td:
        seen = set()
        for name, exp in find_exports(Path(a.from_exports), Path(td)):
            if (a.only and name not in a.only):
                continue
            try:
                name = json.load(open(exp / "manifest.json")).get("friendly_name") or name
            except Exception:
                pass
            if name in seen:
                continue
            seen.add(name)
            om = out / name / "normalized"
            if (om / "pipeline_handoff.json").exists() and not a.force:
                print(f"skip {name} (already normalized; --force to redo)"); continue
            t0 = time.time()
            try:
                om.mkdir(parents=True, exist_ok=True)
                diag, T, C, ctx = normalize.run(exp, om, cfg, None, None, None, str(mr) if mr.is_file() else None)
                wrote, hdr = normalize.finalize(diag, T, C, ctx, om, cfg)
                h = handoff(om, name, diag, hdr, cfg)
                status = "ok" if not diag["failed_steps"] else "partial"
                rows.append(dict(match=name, status=status, build=hdr.get("source_build"), map_code=hdr.get("map_code"), rounds=hdr.get("n_rounds"), players=hdr.get("n_players"),
                                 deaths=hdr.get("n_death_events"), movement_rows=hdr.get("n_movement_rows"), failed_steps=";".join(diag["failed_steps"]),
                                 warnings=sum(1 for c in diag["checks"] if c["level"] == "warn"), secs=round(time.time() - t0, 1)))
            except Exception as e:  # one match never stops the batch
                import traceback
                rows.append(dict(match=name, status="failed", failed_steps=str(e)[:200]))
                (out / name).mkdir(parents=True, exist_ok=True)
                json.dump({"error": traceback.format_exc()[-2000:]}, open(out / name / "FAILED.json", "w"))
            print(rows[-1])
    if rows:
        with open(out / "cohort_report.csv", "w", newline="") as f:
            keys = sorted({k for r in rows for k in r}, key=lambda k: list(rows[0]).index(k) if k in rows[0] else 99)
            wr = csv.DictWriter(f, fieldnames=keys); wr.writeheader(); wr.writerows(rows)
        json.dump(dict(matches=rows, source_matrix=SOURCE_MATRIX, config=a.config), open(out / "cohort_handoff.json", "w"), indent=2, default=str)
    print(f"{len(rows)} matches processed -> {out}")


if __name__ == "__main__":
    main()
