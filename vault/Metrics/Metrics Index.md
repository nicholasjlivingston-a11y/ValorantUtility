---
type: metrics-index
status: current
updated: 2026-10-30
tags: [valosaber, metrics]
---
# Metrics index

Every metric has a note with its definition, formula, assumptions and limits. Add a row when a metric is added.

| Metric | Note | Status |
|---|---|---|
| Round win probability | [[Win Probability Model]] | Built (simple model) |
| Kill WPA, death cost, WPA | [[WPA and Leverage]] | Built |
| Leverage index | [[WPA and Leverage]] | Built |
| ADR, ADR+, Finishing+, KST%, trades, clutch, openers, util-assisted kills | [[Rate Indexes]] | Built |
| Utility-adjusted credit | [[Utility Credit]] | Built (Stage 1, heuristic weights) |
| Utility lift (Stage 2) | [[Utility Credit]] | Planned |
| Utility in the win-probability model (Stage 3) | [[Utility Credit]] | Planned |
| Replacement level | [[07 Sabermetrics Notes]] | Needs many matches |
| Map and side factors | [[07 Sabermetrics Notes]] | Needs many matches |

Code: `claude/valosaber.py` computes all of these. The page that shows them is built from `claude/valosaber_template.html` ([[Run Order]]).
