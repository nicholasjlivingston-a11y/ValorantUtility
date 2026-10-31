---
type: reference
status: current
updated: 2026-10-30
tags: [valosaber, reference, abilities]
---
# Abilities

Class names in the replay are internal. A display name is used only when marked `matched`. `likely` rests on slot pattern or elimination. Folder letters (`Ability_Q`, `Ability_E`, `Ability_4`, `Ability_X`) are **not** keybinds in general. In the three agents below `Ability_4` was the grenade-slot ability, but do not assume that for others.

The cast `Slot` number (3, 4, 5, 9 observed) is **undecoded**. See [[04 Open Questions]].

## Matched or likely
| Agent | Replay class | Display name | Status | Why |
|---|---|---|---|---|
| Iso | `Ability_Sequoia_Q_FragileMissilePrototypeEquipped` | Undercut | matched | Applies a "fragile" (vulnerable) debuff; projectile with trajectory warning |
| Iso | `Ability_Sequoia_E_WreckingBall` | Double Tap | matched | Energy orb and shield objects spawned |
| Iso | `Ability_X_Sequoia_ArenaLineCapture` and `Actor_Sequoia_X_StandardArena` | Kill Contract | matched | Arena with teleport; target displaced |
| Iso | `Ability_Sequoia_4_Wave` | Contingency | likely | Wall ability; grenade slot |
| Veto | `Ability_Pine_Q_SeizeTrap` | Chokehold | matched | Trap grenade that deploys a tether sphere |
| Veto | `Ability_Pine_4_UsableTP` | Crosscut | likely | Teleport |
| Veto | `Ability_Pine_E_RadEater` | Interceptor | likely | By elimination |
| Veto | `Ability_Pine_X_SelfBuffVers_Engineering` | Evolution | likely | Self-buff ultimate |
| Miks | `Ability_Iris_Harmonize` | Harmonize | matched | Same name; allies stimmed |
| Miks | `Ability_Iris_E_MT_Smoke_Production` | Waveform | likely | Smoke object; enemies blocked |
| Miks | `Ability_Iris_Thumper` | M-Pulse | likely | Grenade slot; spawns a heal projectile and object, which is worth rechecking |
| Miks | `Ability_Iris_X_SonicWave` | Bassquake | likely | Ultimate slot |

## Raw classes, display names not mapped
| Agent | Classes |
|---|---|
| Cypher (Gumshoe) | `4_TripWire`, `E_Camera`, `E_Camera_Dart`, `E_UnpossessCamera`, `Q_CageTrap`, `X_InterrogateV2` |
| Fade (BountyHunter) | `4_WolfHoundBendable`, `Passive`, `X_WaveForm` |
| Phoenix | `4_Molotov_Production`, `E_FlareCurve_Production`, `Q_FireballWall_Production`, `X_SelfRes_Production`, `Passive` |
| Sova (Hunter) | `4_BoltExplosive`, `E_DeployDrone`, `Q_RevealBolt_Signature`, `X_LaserMulti` |
| Reyna (Vampire) | `4_NearsightAoE`, `E_Escape`, `Passive`, `Q_Heal`, `X_Frenzy` |

## Rules
- Actor spawns are not casts. One Recon Bolt spawns a projectile plus reveal pings. Count casts from `AbilityCastsThisRound`; use actor spawns only for where persistent effects were.
- Objects that spawn at about 0.1 s are loadout slots, not casts.
