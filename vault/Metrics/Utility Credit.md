---
type: metric
status: current
updated: 2026-10-30
tags: [valosaber, metrics, utility]
---
# Utility credit

Goal: make better utility count toward round wins without taking credit from the player who got the kill. Decision record: [[ADR-006 Utility credit is zero-sum and adjustable]].

## Stage 1 (built, heuristic)
Each kill's [[WPA and Leverage]] value is split between components that exist for that kill:

| Component | Who | Default weight |
|---|---|---|
| Killer | The killer | 60 |
| Utility setup | Teammates (including the killer) whose ability affected the victim in the previous 8 s; equal shares | 25 |
| Damage assists | Teammates who damaged the victim that round; shares in proportion to damage | 15 |

Shares are the weights divided by the weights of the components present, so a kill with no utility setup hands that share back to the others. **The split is zero-sum:** shares add back to the kill's WPA (sample: 5.96 of 5.96).

**Healing credit:** HP restored divided by 150, times the win-probability cost of a death at that moment. Set to 0 to turn off. Heals are additive, not zero-sum.

**Deaths** cost the victim the full kill WPA.

All weights are sliders on the page. With killer-only weights (100/0/0, healing off) the result equals plain WPA. That is the built-in consistency check.

Sample at defaults: Sova moves up two places on utility and damage assists; Omen drops two. Only 7 of 34 kills had a utility setup.

## Limits
- The weights are a starting guess, not measured.
- Ability effect times are accurate to about 2 s; the 8 s window is wide on purpose.
- Healing is credited at the state when the heal was cast.
- Effect units (seconds, fraction, damage) are unknown, so effects are counted, not weighted by size.
- Utility used by teams already winning looks better than it is (selection bias). Use change in win probability, not level, when measuring.

## Stage 2 (planned): measure lift
Compare fights where the enemy was affected against fights where they were not, matched on alive counts. The difference in kill and trade rates is each effect's value, and it replaces the guessed weights. Also per-cast metrics: enemy-seconds affected, vision-blocked seconds, win probability gained in the window after the cast, casts that hit nobody, utility left unspent at death.
Needs: precise effect start and end times on the replay clock, about 30 matches.

## Stage 3 (planned): utility in the model
Add smokes and walls active, utility remaining and ultimate charge to the win-probability state. A cast's value is the model's win probability with the cast minus the model's estimate without it. Compare each ability to typical casts of that ability (the replacement-level idea).
Needs: hundreds of matches, charges and costs, utility object lifetimes and positions, decoded ability names.

## Data needed from the pipeline
Effect start and end times, effect value units, charges and costs, utility object lifetimes and positions, decoded ability names. Listed in [[Coding Agent Brief]].
