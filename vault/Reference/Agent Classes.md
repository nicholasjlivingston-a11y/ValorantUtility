---
type: reference
status: current
updated: 2026-10-30
tags: [valosaber, reference, classes]
---
# Agent classes

Used for the class peer group in [[ADR-007 Three peer groups for comparison]]. The data lives in `data/agent_classes.json` in the repo; keep the two in step.

Status words follow [[ADR-005 Names only when confirmed]]: `confirmed` needs a source written in the evidence, `unverified` means recalled from general knowledge and not yet sourced, `unknown` means no class yet.

| Agent | Class | Status | Evidence |
|---|---|---|---|
| Iso | Duelist | confirmed | ID page lists Iso as a Duelist ([[Agents]]) |
| Jett, Phoenix, Reyna, Raze, Yoru, Neon, Waylay | Duelist | unverified | |
| Sova, Fade, Breach, Skye, KAY/O, Gekko, Tejo | Initiator | unverified | |
| Omen, Brimstone, Viper, Astra, Harbor, Clove | Controller | unverified | |
| Cypher, Killjoy, Sage, Chamber, Deadlock, Vyse | Sentinel | unverified | |
| Veto | Sentinel | unverified | Kit seen in the replay (trap, teleport) fits, but class not sourced |
| Miks | none | unknown | Find a source before adding |

## To do
- Source each `unverified` row (official agent table or an agent page) and change the status in the JSON and here.
- Run `baselines.py --confirmed-classes-only` to ignore unverified classes until then.
- New agents: add a row with status `unverified` or `unknown`; never delete one.
