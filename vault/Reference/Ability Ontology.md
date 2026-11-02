---
type: reference
status: current
updated: 2026-10-30
tags: [valosaber, reference, abilities, ontology]
---
# Ability ontology

Source: `ontology/ability_ontology.json` and `decision_ledger.json` in the [[Bootstrap Package]] (ontology version 1.0.0, exported 2026-10-26). Only two abilities so far. Per-ability lifecycle stages describe what a replay should show (cast, deploy, activation, destruction).

| Ability | Agent | Ontology status | Our status | Lifecycle | Evidence |
|---|---|---|---|---|---|
| Trademark | Chamber | USER_CONFIRMED_MECHANIC | confirmed by user | cast, deploy, activation, destruction; trap range 500 units; needs ground | Event `TrademarkPlaced`; ledger Q_CHAMBER_TRADEMARK_001 confirmed |
| Sonic Sensor | Deadlock | REGISTRY_CANDIDATE | unconfirmed | cast, deploy, activation; needs a wall | No evidence; ledger Q_DEADLOCK_SONIC_SENSOR_001 unanswered |

## Mapping to our status words
`USER_CONFIRMED_MECHANIC` behaves like `confirmed_by_user`; `REGISTRY_CANDIDATE` like `unconfirmed`. Do not show an ability as confirmed on the strength of a candidate. See [[Abilities]] and [[ADR-005 Names only when confirmed]].

## Open
- The two ability records need to be linked to class names seen in replays (the ability class paths in [[Abilities]]).
- Deadlock's Sonic Sensor question has no answer yet.
- Hush's abilities (Telekinesis passive, Flow C, Flashbulb Q, Displacement E, Suspension X) are not in the ontology; names are sourced in [[Agents]], replay class names are unknown.
