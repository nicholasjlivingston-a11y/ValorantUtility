#!/usr/bin/env python3
"""Valosaber baselines: compare each player-agent against three peer groups.

usage: baselines.py WAREHOUSE AGENT_CLASSES_JSON OUT_DIR [--min-rounds 20] [--min-peers 8] [--k 50]
                    [--confirmed-classes-only]
       baselines.py --selftest

Scopes (see vault ADR-007):
  overall  all player-agent rows in the same mode
  class    same mode and same class (Duelist, Initiator, Controller, Sentinel)
  agent    same mode and the exact agent

Unit = (player uuid, agent, mode). Rates are per round, summed over matches.
Peer mean and spread are round-weighted and EXCLUDE the player being scored (leave-one-out).
The player's rate is shrunk toward the parent scope's peer mean (agent -> class -> overall):
    shrunk = (rounds * raw + k * prior) / (rounds + k)
Nothing is invented: if a group has fewer than --min-peers other rows, the comparison columns are null
and status is 'insufficient_peers'. 'low_rounds' marks players under --min-rounds.

Outputs (OUT_DIR): player_agent.parquet, baselines.parquet, comparisons.parquet
"""
import argparse, json, sys
from pathlib import Path
import numpy as np
import pandas as pd

BASELINE_VERSION = "1"
# additive per-match counts and sums in the shard players table; turned into per-round rates
METRICS = ["wpa", "kwpa", "dwpa", "kills", "deaths", "dmg", "dmg_taken", "fb", "fd", "trade_kills",
           "traded_deaths", "clutch_kills", "util_assisted_kills", "util_assists_given", "xk"]
# metrics where a ratio index (100 = peer average) is meaningful: always positive
RATIO = {"kills", "dmg", "dmg_taken", "fb", "trade_kills", "clutch_kills", "util_assisted_kills",
         "util_assists_given", "xk"}


def load_warehouse(wh: Path) -> pd.DataFrame:
    parts = sorted((wh / "players").glob("part-*.parquet"))
    if not parts:
        sys.exit(f"no players parts under {wh}")
    P = pd.concat([pd.read_parquet(p) for p in parts], ignore_index=True)
    for c in P.columns:
        if str(P[c].dtype) == "category":
            P[c] = P[c].astype(object)
    cat = json.load(open(wh / "catalog.json"))["matches"]
    meta = pd.DataFrame([{"match_id": k, "rounds": v["rounds"], "mode": v["mode"]} for k, v in cat.items()])
    P = P.merge(meta, on="match_id", how="left", validate="m:1")
    if P["rounds"].isna().any():
        sys.exit("players rows with a match_id missing from catalog.json")
    return P


def aggregate(P: pd.DataFrame, classes: dict, confirmed_only: bool) -> pd.DataFrame:
    miss = [m for m in METRICS if m not in P.columns]
    if miss:
        sys.exit(f"players table lacks columns: {miss}")
    g = P.groupby(["uuid", "agent", "mode"], as_index=False).agg(
        rounds=("rounds", "sum"), matches=("match_id", "nunique"), **{m: (m, "sum") for m in METRICS})

    def cls(a):
        e = classes["agents"].get(a)
        if not e or not e.get("class"):
            return None
        if confirmed_only and e.get("status") != "confirmed":
            return None
        return e["class"]

    g["class"] = g["agent"].map(cls)
    g["class_status"] = g["agent"].map(lambda a: (classes["agents"].get(a) or {}).get("status", "unlisted"))
    return g


def loo_stats(df, keys, rcol, w):
    """Round-weighted leave-one-out mean/sd of rcol within keys. Returns (mean, sd, peers)."""
    grp = df.groupby(keys, dropna=True)
    Sw = grp[w].transform("sum")
    Swr = (df[w] * df[rcol]).groupby([df[k] for k in keys]).transform("sum")
    Swr2 = (df[w] * df[rcol] ** 2).groupby([df[k] for k in keys]).transform("sum")
    n = grp[w].transform("size") - 1
    dw = Sw - df[w]
    with np.errstate(divide="ignore", invalid="ignore"):
        mean = (Swr - df[w] * df[rcol]) / dw
        var = (Swr2 - df[w] * df[rcol] ** 2) / dw - mean ** 2
    sd = np.sqrt(np.clip(var, 0, None))
    mean = mean.where(dw > 0)
    sd = sd.where(dw > 0)
    return mean, sd, n


def compare(pa: pd.DataFrame, min_rounds, min_peers, k) -> tuple[pd.DataFrame, pd.DataFrame]:
    out, base = [], []
    for m in METRICS:
        d = pa[["uuid", "agent", "class", "mode", "rounds"]].copy()
        d["raw"] = pa[m] / pa["rounds"]
        d["key_all"] = "all"
        # overall is the parent of class, class is the parent of agent
        ov_mean, _, _ = loo_stats(d.assign(g="all"), ["mode", "g"], "raw", "rounds")
        d["prior_overall"] = ov_mean
        has_cls = d["class"].notna()
        cl = d[has_cls].copy()
        cl_mean, _, _ = loo_stats(cl, ["mode", "class"], "raw", "rounds")
        d["prior_class"] = cl_mean.reindex(d.index)
        for scope, keys in (("overall", ["mode"]), ("class", ["mode", "class"]), ("agent", ["mode", "agent"])):
            s = d if scope != "class" else d[has_cls]
            s = s.copy()
            if scope == "overall":
                s["g"] = "all"; keys = ["mode", "g"]; parent = s["prior_overall"]
                s["group"] = "all"
            elif scope == "class":
                parent = s["prior_overall"]; s["group"] = s["class"]
            else:
                parent = s["prior_class"].fillna(s["prior_overall"]); s["group"] = s["agent"]
            mean, sd, peers = loo_stats(s, keys, "raw", "rounds")
            prior = parent.where(parent.notna(), s["raw"])
            s["shrunk"] = (s["rounds"] * s["raw"] + k * prior) / (s["rounds"] + k)
            ok = peers >= min_peers
            s["peer_mean"] = mean.where(ok); s["peer_sd"] = sd.where(ok); s["peer_n"] = peers
            s["above_peer"] = (s["shrunk"] - s["peer_mean"])
            s["z"] = (s["above_peer"] / s["peer_sd"]).where(s["peer_sd"] > 0)
            # percentile of shrunk rate among the group (average rank, 0 to 1), null when too few peers
            gk = [s[c] for c in keys]
            rank = s.groupby(keys)["shrunk"].rank(method="average") - 1
            s["percentile"] = (rank / peers.where(peers > 0)).where(ok)
            s["index"] = np.where((m in RATIO) & (s["peer_mean"] > 0), 100 * s["shrunk"] / s["peer_mean"], np.nan)
            s["status"] = np.where(~ok, "insufficient_peers", np.where(s["rounds"] < min_rounds, "low_rounds", "ok"))
            s["metric"] = m; s["scope"] = scope; s["raw_rate"] = s["raw"]; s["shrunk_rate"] = s["shrunk"]
            out.append(s[["uuid", "agent", "class", "mode", "scope", "group", "metric", "rounds", "raw_rate",
                          "shrunk_rate", "peer_mean", "peer_sd", "peer_n", "above_peer", "z", "percentile",
                          "index", "status"]])
            b = s.assign(w=s["rounds"], wr=s["rounds"] * s["raw"], wr2=s["rounds"] * s["raw"] ** 2) \
                 .groupby(["mode", "group"]).agg(n_rows=("uuid", "size"), n_rounds=("w", "sum"),
                                                 swr=("wr", "sum"), swr2=("wr2", "sum")).reset_index()
            b["mean"] = b["swr"] / b["n_rounds"]
            b["sd"] = np.sqrt(np.clip(b["swr2"] / b["n_rounds"] - b["mean"] ** 2, 0, None))
            b["scope"] = scope; b["metric"] = m
            base.append(b[["scope", "mode", "group", "metric", "mean", "sd", "n_rows", "n_rounds"]])
    C = pd.concat(out, ignore_index=True); B = pd.concat(base, ignore_index=True)
    C["baseline_version"] = BASELINE_VERSION; B["baseline_version"] = BASELINE_VERSION
    return C, B


def run(P, classes, min_rounds, min_peers, k, confirmed_only):
    pa = aggregate(P, classes, confirmed_only)
    C, B = compare(pa, min_rounds, min_peers, k)
    return pa, B, C


def selftest():
    rng = np.random.default_rng(7)
    agents = {"Jett": "Duelist", "Reyna": "Duelist", "Sova": "Initiator", "Fade": "Initiator",
              "Omen": "Controller", "Viper": "Controller", "Cypher": "Sentinel", "Sage": "Sentinel"}
    classes = {"agents": {a: {"class": c, "status": "confirmed"} for a, c in agents.items()}}
    rows = []
    for mid in range(60):
        for i in range(10):
            a = list(agents)[rng.integers(0, 8)]
            u = f"p{rng.integers(0, 25)}"
            r = {"match_id": f"m{mid}", "uuid": u, "agent": a, "mode": "Test", "rounds": 20}
            for m in METRICS:
                r[m] = float(rng.poisson(8)) if m in RATIO else float(rng.normal(0, 1))
            rows.append(r)
    P = pd.DataFrame(rows).drop_duplicates(["match_id", "uuid"])
    pa, B, C = run(P, classes, 20, 8, 50, False)
    assert len(pa) == P.groupby(["uuid", "agent"]).ngroups
    ok = C[C.status != "insufficient_peers"]
    assert len(ok) > 0 and ok.percentile.between(0, 1).all()
    # shrinkage pulls toward the prior: |shrunk - peer| <= |raw - peer| for the overall scope
    o = ok[ok.scope == "overall"]
    assert ((o.shrunk_rate - o.peer_mean).abs() <= (o.raw_rate - o.peer_mean).abs() + 1e-9).all()
    # leave-one-out: peer mean excludes the player (check one row by hand)
    row = o[o.metric == "kills"].iloc[0]; pool = pa[pa["mode"] == row["mode"]].copy()
    me = pool[(pool["uuid"] == row["uuid"]) & (pool["agent"] == row["agent"])].iloc[0]
    others = pool.drop(me.name); w = others["rounds"]
    exp = (others["kills"] / others["rounds"] * w).sum() / w.sum()
    assert abs(exp - row["peer_mean"]) < 1e-9, (exp, row["peer_mean"])
    # small group is flagged, not scored
    tiny = P[P.agent.isin(["Jett"])].head(5)
    pa2, B2, C2 = run(tiny, classes, 20, 8, 50, False)
    assert (C2.status == "insufficient_peers").all() and C2.z.isna().all() and C2.percentile.isna().all()
    # a class group of one stays unscored; missing class drops out of class scope only
    classes2 = {"agents": {**classes["agents"], "Sova": {"class": None, "status": "unknown"}}}
    pa3, B3, C3 = run(P, classes2, 20, 8, 50, False)
    assert "Sova" not in set(C3[C3.scope == "class"].agent) and "Sova" in set(C3[C3.scope == "agent"].agent)
    print(f"selftest ok: {len(pa)} player-agent rows, {len(C)} comparisons, "
          f"{(C.status == 'ok').sum()} ok, {(C.status == 'low_rounds').sum()} low_rounds, "
          f"{(C.status == 'insufficient_peers').sum()} insufficient_peers")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("warehouse", nargs="?"); ap.add_argument("classes", nargs="?"); ap.add_argument("out", nargs="?")
    ap.add_argument("--min-rounds", type=int, default=20); ap.add_argument("--min-peers", type=int, default=8)
    ap.add_argument("--k", type=float, default=50.0)
    ap.add_argument("--confirmed-classes-only", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        selftest(); sys.exit()
    if not (a.warehouse and a.classes and a.out):
        ap.error("need WAREHOUSE AGENT_CLASSES_JSON OUT_DIR")
    P = load_warehouse(Path(a.warehouse)); classes = json.load(open(a.classes))
    pa, B, C = run(P, classes, a.min_rounds, a.min_peers, a.k, a.confirmed_classes_only)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    pa.to_parquet(out / "player_agent.parquet", index=False)
    B.to_parquet(out / "baselines.parquet", index=False)
    C.to_parquet(out / "comparisons.parquet", index=False)
    print(f"player_agent {len(pa)} rows | baselines {len(B)} | comparisons {len(C)}")
    print(C.groupby(["scope", "status"]).size().to_string())
