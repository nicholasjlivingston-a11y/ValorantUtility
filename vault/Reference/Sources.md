---
type: reference
status: current
updated: 2026-10-30
tags: [valosaber, reference, sources]
---
# Sources

What each source was used for, so a claim can be traced.

## Sabermetrics
- [Tango: A brief history of WAR](https://sabr.org/latest/tango-a-brief-history-of-war/): origin of WAR and replacement level
- [Sabermetrics 101: WPA and leverage](https://www.lookoutlanding.com/2010/3/1/1329943/sabermetrics-101-wpa-and-leverage): win expectancy, WPA, leverage index, and their limits
- [Sabermetrics for Dummies: An A-Z guide](https://www.thescore.com/mlb/news/981930/sabermetrics-for-dummies-an-a-z-guide): list of concepts

## Names and kits
- [Valorant Agents: real names, codenames](https://valorfeed.gg/guides/all-valorant-agents-names-codenames-countries): codename table, dated 2023, so newer agents are missing
- `valorant-info-oumi.onrender.com/agent/<characterId>`: agent ID pages. Worked for Miks (`7c8a4701-…`), Iso (`0e38b510-…`) and Tejo (`b444168c-…`). Only fetchable when the URL had appeared in a search result
- [Veto ability guide (esports.gg)](https://esports.gg/news/valorant/guide-veto-ability-kit-valorant): Chokehold, Crosscut, Interceptor, Evolution
- [Iso abilities explained (One Esports)](https://www.oneesports.gg/valorant/iso-abilities-explained/): Contingency, Undercut, Double Tap, Kill Contract
- [Tejo abilities (Shacknews)](https://shacknews.com/article/142659/all-tejo-abilities-in-valorant): used to rule Tejo out for Sequoia
- [Valorant agents list (ValorantHub)](https://valoranthub.com/agents): roster of 30 agents, newest Hush
- `oanor.com/api/valorant-api/get-v1-agents`: example response that listed Jett's ID `add6443a-…`

## Blocked
- `valorant-api.com` (the official community API) is not on the sandbox allowlist. Allowing it would resolve agents, maps and abilities in one pass.

## Tools
- The `valorant-vrf` skill: `extract_casts.py`, `build_table.py`, `identify_agents.py`, `codenames.json`, format notes
