#!/usr/bin/env python3
"""Identify which agents are in a replay, from the file rather than from memory.

Internal codenames in class_path do not match public agent names, and guessing
them produces a wrong roster that looks entirely plausible. This prints each
codename alongside the ability class names the replay actually carries, so the
kit can be identified directly.

    python3 identify_agents.py --export out
"""
import argparse
import json
import re
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent


def load_map():
    p = HERE / "codenames.json"
    if not p.is_file():
        return {}
    return json.loads(p.read_text()).get("map", {})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--export", default="out", help="vrfkit export directory")
    args = ap.parse_args()

    known = load_map()
    act = pd.read_parquet(Path(args.export) / "actors.parquet")
    cp = act["class_path"].astype(str)
    act = act.assign(code=cp.str.extract(r"/Game/Characters/([A-Za-z0-9_]+)/")[0])

    pawns = act[cp.str.endswith("_PC_C")]
    picks = (pawns.groupby("code")["actor_net_guid"].nunique()
             .sort_values(ascending=False))

    print("Agents in this replay\n")
    for code, n in picks.items():
        if code == "_Core":
            continue
        name = known.get(code)
        label = name if name else f"{code}  <-- UNKNOWN CODENAME"
        extra = f"  ({n} players)" if n > 1 else ""
        print(f"  {code:<10} -> {label}{extra}")

        abil = sorted({
            m.group(1)
            for p in act.loc[act["code"] == code, "class_path"].astype(str).unique()
            for m in [re.search(rf"/(Ability_{code}_[A-Za-z0-9_]+)\.", p)]
            if m
        })
        for a in abil:
            print(f"                 {a}")
        print()

    unknown = [c for c in picks.index if c not in known and c != "_Core"]
    if unknown:
        print("Unrecognized codenames:", ", ".join(unknown))
        print("Identify these from the ability names above. If the kit doesn't")
        print("match an agent you know, say so and keep the codename -- agents")
        print("ship after any given knowledge cutoff. Do not guess a name.")


if __name__ == "__main__":
    main()
