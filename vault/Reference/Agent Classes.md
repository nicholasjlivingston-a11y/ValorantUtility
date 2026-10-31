---
type: reference
status: current
updated: 2026-10-30
tags: [valosaber, reference, classes]
---
# Agent classes

Used for the class peer group in [[ADR-007 Three peer groups for comparison]]. The data lives in `data/agent_classes.json` in the repo; keep the two in step.

Status words follow [[ADR-005 Names only when confirmed]]. **All 29 agents are now `confirmed`**, sourced on 2026-10-30.

| Class | Agents |
|---|---|
| Duelist | Jett, Phoenix, Reyna, Raze, Yoru, Neon, Iso, Waylay |
| Initiator | Sova, Fade, Breach, Skye, KAY/O, Gekko, Tejo |
| Controller | Omen, Brimstone, Viper, Astra, Harbor, Clove, Miks |
| Sentinel | Cypher, Killjoy, Sage, Chamber, Deadlock, Vyse, Veto |

## Sources
- [Valorant Fandom wiki, Agents](https://valorant.fandom.com/wiki/Agents) lists 28 agents by role (everything above except Miks).
- [ExitLag agent guide](https://www.exitlag.com/blog/valorant-characters-all-agents/) gives the same roles for the same 28 agents.
- Miks: [GosuGamers reveal article](https://www.gosugamers.net/valorant/news/78131-valorant-reveals-miks-the-newest-controller-in-season-2026-act-2-launch) calls Miks "the newest Controller". Miks is not on the wiki list pages checked. Other outlets' headlines also say Controller.
- Veto: also headlined as the newest Sentinel by [GosuGamers](https://www.gosugamers.net/valorant/news/77429-veto-joins-valorant-as-the-newest-sentinel-agent).
- Iso: also confirmed earlier by the agent ID page ([[Agents]]).

## Keep current
- Riot can move an agent's role in a later patch. Recheck when a new build is processed, and record the date.
- New agents: add a row with status `unverified` or `unknown`, then source it. Never delete a row.
- Agents seen in the replay have codenames, see [[Agents]]. The class table uses public names, so a class is only used once the name is confirmed.
