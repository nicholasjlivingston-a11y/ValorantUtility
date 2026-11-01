#!/usr/bin/env python3
"""Value checks for a Valosaber shard. Fails on the placeholder patterns seen in rejected deliveries.

usage: shard_checks.py SHARD_DIR [EXPORT_DIR]      (EXPORT_DIR lets it compare kills with characterDeath events)
Exit code 0 only if every check passes. Each check prints its real numbers.
"""
import hashlib, json, sys
from pathlib import Path
import pandas as pd


def run_checks(shard: Path, export: Path | None = None):
    R = []
    def add(name, ok, detail):
        R.append({"check": name, "ok": bool(ok), "detail": detail})

    idx = json.load(open(shard / "index.json"))
    bad = []
    for n, m in idx["tables"].items():
        fp = shard / f"{n}.parquet"
        if not fp.exists() or hashlib.sha256(fp.read_bytes()).hexdigest() != m["sha256"]:
            bad.append(n)
    add("index hashes match files", not bad, f"mismatched or missing: {bad}" if bad else f"{len(idx['tables'])} tables")
    T = {n: pd.read_parquet(shard / f"{n}.parquet") for n in idx["tables"]}
    p, k, d, pos = T["players"], T["kills"], T["damage"], T["positions_4hz"]

    add("10 players, 5 per team", len(p) == 10 and sorted(p.team.value_counts().tolist()) == [5, 5],
        f"{len(p)} players, teams {p.team.value_counts().to_dict()}")
    add("every player has an agent", p.agent.notna().all(), f"{int(p.agent.isna().sum())} missing")
    add("rounds present", idx.get("rounds", 0) >= 2, f"{idx.get('rounds')} rounds")
    nk = len(k)
    key = k[["rnd", "t", "killer", "victim"]].drop_duplicates().shape[0]
    add("kill rows are distinct events", nk > 0 and key == nk, f"{nk} rows, {key} distinct (round,time,killer,victim)")
    add("kill times vary", k.t.nunique() > 1, f"{k.t.nunique()} distinct times, range {k.t.min()}..{k.t.max()} ms")
    add("kills happen in more than one round", k.rnd.nunique() > 1, f"rounds with kills: {k.rnd.nunique()}")
    add("killers and victims are known players", k.killer.isin(p.uuid).all() and k.victim.isin(p.uuid).all(),
        f"{int((~k.killer.isin(p.uuid)).sum())} unknown killers, {int((~k.victim.isin(p.uuid)).sum())} unknown victims")
    dealt, recv = float(d.dealt.sum()), float(d.recv.sum())
    add("damage dealt equals damage received", abs(dealt - recv) < 0.01 and dealt > 0, f"dealt {dealt:.2f}, received {recv:.2f}")
    add("damage values vary", d.dealt.nunique() > 3, f"{d.dealt.nunique()} distinct damage values")
    add("all 10 players have positions", pos.uuid.nunique() == 10, f"{pos.uuid.nunique()} players with positions")
    add("positions vary", pos.x.nunique() > 10 and pos.y.nunique() > 10, f"{pos.x.nunique()} distinct x, {pos.y.nunique()} distinct y")
    add("positions span time", pos.t.max() > 60000, f"max t {pos.t.max()} ms")
    if export is not None and (export / "events.parquet").exists():
        ev = pd.read_parquet(export / "events.parquet")
        gcol = "group" if "group" in ev.columns else None
        if gcol:
            nd = int((ev[gcol].astype(str) == "characterDeath").sum())
            add("kills equal characterDeath events", nd == nk, f"{nk} kills, {nd} death events")
    shard_bytes = sum(f.stat().st_size for f in shard.iterdir() if f.is_file())
    add("shard under 8 MB", shard_bytes < 8 * 1024 * 1024, f"{shard_bytes:,} bytes")
    return R


if __name__ == "__main__":
    res = run_checks(Path(sys.argv[1]), Path(sys.argv[2]) if len(sys.argv) > 2 else None)
    for r in res:
        print(("PASS " if r["ok"] else "FAIL ") + r["check"] + " | " + r["detail"])
    sys.exit(0 if all(r["ok"] for r in res) else 1)
