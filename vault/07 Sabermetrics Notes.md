---
type: research
status: current
updated: 2026-10-30
tags: [valosaber, research, sabermetrics]
---
# Sabermetrics notes

What sabermetrics is and which ideas we borrowed. Sources are at the bottom.

## The ideas
| Baseball idea | What it fixes | Valosaber version | Status |
|---|---|---|---|
| Win expectancy | A situation has a chance of being won, based on history | Round win probability from alive counts ([[Win Probability Model]]) | Built, simple model |
| Win probability added (WPA) | Credit events by how much they moved the win chance | Kill WPA and death cost ([[WPA and Leverage]]) | Built |
| Leverage index | Some moments matter more | Leverage of each kill | Built |
| Context-neutral and indexed stats (OPS+, ERA-) | Compare across parks and eras; 100 is average | ADR+, Finishing+ ([[Rate Indexes]]) | Built |
| BABIP and HR/FB luck | Separate skill from luck, regress small samples | Finishing index; needs many matches to regress | Partly built |
| Defense adjusted for difficulty | Do not reward easy plays | Not built | Needs positions and map geometry |
| Replacement level and WAR | Value over a freely available baseline | Not built | Needs a pool of matches |
| Park factors | Adjust for where the game is played | Map and side factors | Needs many matches per map and side |
| Projection with uncertainty (PECOTA) | Ranges instead of single numbers | Not built | Needs many matches |

## Cautions baseball analysts themselves give
- WPA depends on context and is noisy; it is better for reviewing moments than for predicting skill. We carry the same caution: one match of WPA is description, not prediction.
- Theoretical models are used where history is thin. Our simple alive-count model is that, and says so ([[ADR-003 Simple win probability model]]).

## Sources
- [Tango: A brief history of WAR (SABR)](https://sabr.org/latest/tango-a-brief-history-of-war/)
- [Sabermetrics 101: WPA and leverage (Lookout Landing)](https://www.lookoutlanding.com/2010/3/1/1329943/sabermetrics-101-wpa-and-leverage)
- [Sabermetrics for Dummies: An A-Z guide (theScore)](https://www.thescore.com/mlb/news/981930/sabermetrics-for-dummies-an-a-z-guide)
