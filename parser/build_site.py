#!/usr/bin/env python3
"""Build the Valosaber page from the metrics JSON.

usage: build_site.py METRICS_JSON TEMPLATE_HTML OUT_HTML

METRICS_JSON   output of valosaber.py (metrics/valosaber.json)
TEMPLATE_HTML  valosaber_template.html (contains the __DATA__ placeholder)
OUT_HTML       page to publish (self-contained)
"""
import json, sys

metrics, template, out = sys.argv[1:4]
d = json.load(open(metrics))
KEEP = ["agent", "team", "kills", "deaths", "dmg", "adr", "adr_idx", "wpa", "kwpa", "dwpa", "kst_pct", "fb", "fd",
        "trade_kills", "traded_deaths", "clutch_kills", "util_assisted_kills", "util_assists_given", "avg_li_kills"]
site = dict(
    build=d["build"], rounds=d["rounds"],
    players=[{k: (round(p[k], 4) if isinstance(p[k], float) else p[k]) for k in KEEP} for p in d["players"]],
    rounds_detail=[{k: r[k] for k in ["rnd", "start_ms", "plant_ms", "timeline", "winner_by_elim", "alive_A", "alive_B"]}
                   for r in d["rounds_detail"]],
    duels=d["duels"],
    deaths=[{k: x[k] for k in ["agent", "rnd", "x", "y"]} for x in d["death_locations"]],
    wp=d["model"]["wp_table"], checks=d["checks"],
    kill_records=d["kill_records"], heal_records=d["heal_records"],
)
html = open(template).read()
assert "__DATA__" in html, "template has no __DATA__ placeholder"
open(out, "w").write(html.replace("__DATA__", json.dumps(site, separators=(",", ":"))))
print("wrote", out, len(html), "bytes of template +", len(json.dumps(site)), "bytes of data")
