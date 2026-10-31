---
type: reference
status: current
updated: 2026-10-30
tags: [valosaber, reference, agents]
---
# Agents

Internal codenames in the replay are **not** public agent names. A name goes in the output only when its status is `confirmed`. Status words are defined in [[06 How to update this vault]]. The same data lives in `claude/name_lookup_build13_08.json` in the project; keep them in step.

Build: `++Ares-Core+release-13.08`

## This replay's ten players
| Codename | Public name | Status | Manifest characterId | Evidence |
|---|---|---|---|---|
| Wushu | Jett | confirmed | `add6443a-41bd-e414-f6ad-e58d267f4e95` | The ID is listed as Jett on an API example page; kit Smoke, Dash, CycloneBoost, Dagger |
| Wraith | Omen | confirmed | `8e253930-4c05-31dd-1b6c-968525494517` (ID not independently resolved) | Skill codename map from the kit; codename table lists Wraith as Omen |
| Hunter | Sova | confirmed | `320b2a48-4d9b-a075-30f1-1f93a9b638fa` (not resolved) | Skill codename map from the kit; codename table |
| Gumshoe | Cypher | confirmed | `117ed9e3-49f3-6512-3ccf-0cada7e3823b` (not resolved) | Codename table; kit TripWire, Camera, CageTrap, Interrogate |
| Vampire | Reyna | confirmed | `a3bfb853-43b2-7238-a4f1-ad90e9e46bcc` (not resolved) | Codename table; kit NearsightAoE, Escape, Heal, Frenzy; effects HealingDone, EnemiesNearsighted |
| BountyHunter | Fade | confirmed | `dade69b4-4f5a-8528-247b-219e5a1facd6` (not resolved) | Codename table lists "Bounty Hunter" for Fade (2023 article); effects Seized, Marked, Nearsighted, Spotted |
| Iris | Miks | confirmed | `7c8a4701-4de6-9355-b254-e09bc2a34b72` | The ID page lists Miks with M-pulse, Waveform, Harmonize, Bassquake; kit matches |
| Sequoia | Iso | confirmed | `0e38b510-41a8-5780-5e8f-568b2a4f2d6c` | The ID page lists Iso (Duelist); kit matches Undercut, Double Tap, Contingency, Kill Contract. **Not Tejo** |
| Pine | Veto | confirmed_by_user_and_kit | `92eeef5d-43b5-1d4a-8d03-b3927a09034b` (not resolved) | User stated it; kit matches Chokehold (trap), Crosscut (teleport), Interceptor, Evolution |
| Phoenix | Phoenix | kit_only | `eb93336a-449b-9c1b-0a54-a891f7921d69` (not resolved) | Kit Molotov, FlareCurve, FireballWall, SelfRes. One source lists the codename Apollo for Phoenix, so the codename here differs from that source |

## Teams in the sample match
- **Team A:** Jett, Phoenix, Iso, Sova, Reyna (won all five rounds)
- **Team B:** Fade, Cypher, Miks, Omen, Veto

## Other codenames confirmed earlier (not in this replay)
Deadeye = Chamber, Killjoy = Killjoy, Nox = Vyse, Sprinter = Neon, Terra = Waylay. Source: the skill's `codenames.json`, each confirmed from ability class names.

## Not in this replay
Hush (Duelist) arrived in patch 13.09 on October 27, 2026, after this build. Her codename and characterId are unknown until a 13.09 or later replay is processed. Add them here then, with evidence.

Tejo's agent ID is `b444168c-4e35-8076-db47-ef9bf368f384`. It does not match any player here.

## How to resolve a name properly
1. Join `manifest.json` `game_specific_data[1].playerLoadouts[].characterId` to `PlayerState.Subject`.
2. Look the `characterId` up in an official agent table. `valorant-api.com` is blocked in the sandbox. Individual ID pages at `valorant-info-oumi.onrender.com/agent/<id>` could be fetched only when the URL had appeared in a search result.
3. Cross-check with the ability class names from `identify_agents.py`.
4. Record the evidence in the row and set the status.
