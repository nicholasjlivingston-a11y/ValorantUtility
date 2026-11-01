---
type: reference
status: current
updated: 2026-11-01
tags: [valosaber, reference, requirements, meta-analysis]
---
> Verbatim extraction requirements from the meta-analysis agent (received 2026-11-01). Authoritative for the `analytics_tables/` contract. The stats shard contract is in [[Shard Schema]]. How both fit: [[Master Parser Prompt]]. Packaged as `docs/EXTRACTION_REQUIREMENTS.md` in the bootstrap ([[Bootstrap Package]]).

# VALORANT Replay Extraction Requirements
## Exact data requirements for the parsed output

### 1. Core extraction rule

Extract every supported piece of information from the replay that can describe:

- Who was present and which team they belonged to.
- Where each player was, and how their position changed over time.
- What happened, when it happened, and who was involved.
- What abilities and utility objects were used, and how their states changed.
- What damage, kills, deaths, objective events, and economic events occurred.
- How the round and match developed over time.
- How the extracted information can be traced to its original replay data.

Preserve the original information at its native resolution and original granularity wherever available.

Do not replace missing values with zero, infer unobserved events, collapse separate events into summary records, or discard information because it is not currently used by an analysis.

Every extracted record must retain enough information to identify its match, source, time, and relevant player or object.

### 2. Match-level information

Extract:

- Match identifier, if present.
- Original replay filename.
- Replay source SHA-256.
- Game build/version.
- Game mode.
- Map identifier/code.
- Map name, only if supported by a confirmed reference.
- Match start/end timestamps, if available.
- Match duration.
- Number of rounds.
- Match result and winning team, if available.
- Team identifiers.
- Replay/parser version and extraction run identifier.

Preserve the original values. If a value is unavailable or cannot be reliably decoded, leave it null and record that it is unavailable.

### 3. Player and roster information

For every player in the replay, extract:

- Replay-specific player/subject identifier.
- Player name, if available.
- Team identifier.
- Agent identifier or codename.
- Agent display name, only when confirmed by a source-backed lookup.
- Player's starting side, if available.
- Player's side by round.
- Player roster presence and participation intervals, if available.
- Any source identifiers needed to connect the player to other replay records.

Preserve replay-specific identifiers. Do not assume player IDs or names are stable across matches.

Do not discard a player because their agent name or identity cannot be resolved. Preserve the available identifier and mark the unresolved information.

### 4. Round information

For every round, extract:

- Round index and source round identifier.
- Round start and end timestamps.
- Round duration.
- Attacking team.
- Defending team.
- Team sides.
- Side-switch events and timestamps.
- Round winner.
- Round-ending condition, if available.
- Round outcome or result.
- Buy phase and active round phase boundaries, if available.
- Objective state and relevant objective timestamps.
- Player participation and alive/dead status, where available.

Do not assume a fixed number of rounds per half or a fixed side-switch round. Extract actual side-switch events.

### 5. Player-state and movement information

This is a critical extraction requirement.

For every available player-state observation, preserve:

- Match identifier.
- Player/subject identifier.
- Timestamp in the original source time unit.
- Original source time value.
- Round association, if resolvable.
- X coordinate.
- Y coordinate.
- Z coordinate.
- Facing direction/yaw.
- Pitch, if available.
- Velocity components, if available.
- Speed, if directly available.
- Player alive/dead state, if available.
- Player team and agent association, if available at that observation.
- Other movement or player-state fields exposed by the parser.

Preserve every native-resolution observation available from the replay. Do not assume the source is sampled at 4 Hz.

Do not discard intermediate observations or replace native-resolution movement with downsampled positions.

Preserve original coordinates and units. Any coordinate transformation, normalization, speed calculation, region assignment, or downsampling must be a separate derived value with its inputs and transformation documented.

For each player, retain enough information to determine:

- Number of observations.
- First and last observation timestamps.
- Duration covered by observations.
- Missing intervals and gaps.
- Whether the player has no position observations.
- Whether position coverage is incomplete.

Missing positions must remain missing. Never substitute zero or indefinitely repeat a previous position.

### 6. Combat events

#### 6.1 Kill events

Extract every distinct kill record with:

- Event identifier, if available.
- Timestamp in original source units.
- Round association.
- Killer/player identifier.
- Victim/player identifier.
- Killer team.
- Victim team.
- Weapon identifier/name, if available.
- Weapon category, if available.
- Headshot/body/leg or hit-location information, if available.
- Wall penetration information, if available.
- Distance, if available.
- Relevant source event fields.
- Source actor/object references.

Preserve each kill as an individual event. Do not infer a kill solely from a death counter or collapse multiple events.

#### 6.2 Death events

Extract every distinct death event with:

- Event identifier, if available.
- Timestamp.
- Round association.
- Dead player identifier.
- Killer or instigator identifier, if available.
- Death cause or damage type, if available.
- Relevant source event fields.
- Source actor/object references.

Keep death events separate from kill events. Preserve unmatched kill/death records rather than forcing a one-to-one match.

#### 6.3 Damage events

Extract every distinct damage record with:

- Event identifier, if available.
- Timestamp.
- Round association.
- Attacking/damaging player identifier.
- Damaged player identifier.
- Attacker and victim teams, if available.
- Damage amount.
- Damage type.
- Weapon or ability source, if available.
- Hit location, if available.
- Health damage and shield damage separately, if exposed.
- Whether the event is direct, periodic, or otherwise classified by the source.
- Relevant source actor/object references.
- Original source fields.

Preserve individual damage ticks and events. Do not aggregate damage by player, weapon, round, or ability in place of the underlying records.

Preserve the source's original field names and values, including misspelled field names. Do not silently reinterpret ambiguous damage fields.

### 7. Ability and utility information

This section requires the greatest possible granularity.

Extract every ability-related record exposed by the replay, including:

- Ability cast attempts.
- Confirmed ability casts.
- Ability activation.
- Utility deployment.
- Utility object creation.
- Utility movement.
- Utility state changes.
- Utility trigger events.
- Utility effects.
- Player exposure to effects.
- Player status changes caused by abilities.
- Damage caused by abilities.
- Destruction of utility.
- Utility expiration.
- Utility removal.
- Ability cancellation or failure, if available.

For each record, extract:

- Event identifier.
- Timestamp.
- Round association.
- Acting player identifier.
- Acting player's team.
- Acting player's agent.
- Ability identifier.
- Ability codename or source name.
- Confirmed public ability name, if supported by a reliable lookup.
- Ability slot or source enum, if available.
- Event/lifecycle stage.
- Utility object identifier.
- Parent ability/cast identifier, if available.
- Target player identifier, if available.
- Target team, if available.
- Target object or location, if available.
- Position X/Y/Z, if available.
- Direction/orientation, if available.
- Duration, if directly available.
- Relevant state/value fields.
- Source actor/object references.

#### 7.1 Keep lifecycle stages separate

Do not combine these into a single ability event:

1. Cast attempt.
2. Successful cast.
3. Deployment.
4. Object creation.
5. Object movement.
6. Activation or trigger.
7. Effect beginning.
8. Effect exposure.
9. Effect ending.
10. Damage or status application.
11. Destruction.
12. Expiration or removal.

Only extract stages actually supported by source data. A deployment does not prove activation. An object existing does not prove a player was affected. An effect being present does not prove damage occurred.

#### 7.2 Preserve individual affected-player records

When an ability can affect multiple players, preserve each affected-player observation or event separately.

Extract, where available:

- Affected player.
- Effect type.
- Effect start timestamp.
- Effect end timestamp.
- Duration.
- Effect intensity or magnitude.
- Status state transitions.
- Whether the effect was applied, removed, resisted, or interrupted.
- Source utility object.
- Source ability/cast.

Do not treat potential exposure as confirmed exposure. Do not treat a field's presence as proof that a player experienced a measurable effect.

#### 7.3 Preserve utility object identity

When the replay exposes utility objects, extract each object independently:

- Object identifier.
- Creating player.
- Team.
- Agent.
- Ability.
- Creation/deployment timestamp.
- Position and orientation.
- Movement observations.
- State transitions.
- Activation/trigger timestamp.
- Effect intervals.
- Targets and affected players.
- Damage events.
- Destruction timestamp and cause, if available.
- Expiration/removal timestamp.

Keep child events linked to their parent utility object and ability cast wherever the source permits.

### 8. Objective and spike information

Extract every available objective-related event, including:

- Spike pickup.
- Spike carrier changes.
- Spike plant start.
- Spike plant completion.
- Spike planted state.
- Spike location.
- Spike position observations, if available.
- Spike defuse start.
- Defuse progress/state changes, if available.
- Defuse completion.
- Spike detonation.
- Spike drop.
- Spike recovery.
- Objective-related round-ending events.

For every event, preserve:

- Event identifier.
- Timestamp.
- Round association.
- Player identifier.
- Team.
- Event type.
- Position, if available.
- Objective state before and after, if available.
- Source actor/object references.

Do not infer a completed plant from a plant attempt or infer a completed defuse from a defuse start.

### 9. Economy information

Extract every available economic record at its original grain:

- Player identifier.
- Team.
- Round.
- Credits.
- Starting credits.
- Ending credits.
- Purchase-phase credits.
- Weapon purchases.
- Weapon inventory.
- Armor purchases and state.
- Ability purchases and charges.
- Remaining ability charges.
- Equipment/inventory changes.
- Round rewards.
- Kill rewards.
- Plant/defuse rewards.
- Other credit changes.
- Source purchase or snapshot timestamps.

Preserve whether each value is a purchase event, inventory snapshot, round snapshot, or calculated estimate.

Do not assume zero means the player had no credits or made no purchases. Preserve unavailable or undecoded economy fields as unavailable and identify the limitation.

### 10. Other player and world state

Extract any additional replay-supported state that may help reconstruct tactical conditions, including:

- Health.
- Shield.
- Alive/dead state.
- Weapon held.
- Inventory.
- Ability charges.
- Ultimate charge and ultimate-ready state.
- Ultimate activation state.
- Suppression or other status states.
- Movement mode.
- Crouch/jump/fall state, if exposed.
- Interactions with objects.
- Player visibility or reveal state, if exposed.
- Relevant world-object state.

Preserve state transitions and snapshots separately. Do not turn a state snapshot into an event unless the transition is directly supported or explicitly recorded as derived.

### 11. Map and spatial information

Extract:

- Original map identifier/code from the replay.
- Original player coordinates.
- Utility coordinates.
- Spike/objective coordinates.
- World-object coordinates, if exposed.
- Elevation.
- Orientation.
- Coordinate units and coordinate-system information, if available.
- Map bounds or spatial metadata, if exposed.
- Source references to map or world objects.

Do not invent map-region labels or infer connections, sightlines, cover, or traversability from coordinates alone.

Any map calibration, coordinate transformation, region assignment, topology, route, or spatial classification must be stored separately as derived information, with the original coordinates preserved.

### 12. Source and provenance information

Every extracted table and record must retain or be traceable to:

- Source replay SHA-256.
- Match identifier.
- Extraction run identifier.
- Parser/version identity.
- Original source table, object, actor, or event reference.
- Original source timestamp and units.
- Evidence classification.

Use these evidence classifications:

- `OBSERVED`: directly present in the replay source.
- `PARSED`: decoded or exposed by the parser.
- `DERIVED`: calculated from source observations using a documented method.
- `INFERRED`: reconstructed from multiple pieces of evidence.
- `HYPOTHESIZED`: a proposed explanation requiring further testing.

Raw extracted records must not contain hypotheses.

Preserve original source fields and values alongside any normalized representation. Do not discard unknown fields merely because their meaning is not yet understood.

### 13. Required output data groups

The parsed output must make the following independently accessible:

1. `matches` — match metadata.
2. `players` — replay roster and player identity.
3. `rounds` — round structure, teams, sides, and outcomes.
4. `player_state` — native-resolution player observations and movement.
5. `kills` — individual kill events.
6. `deaths` — individual death events.
7. `damage_events` — individual damage events.
8. `economy` — economic events and snapshots.
9. `spike_events` — individual objective events.
10. `ability_events` — individual ability and lifecycle events.
11. `utility_objects` — individual utility object identity and state.
12. `player_effects` — individual player-effect intervals and observations, where available.
13. `world_state` — other exposed player/world-state observations.
14. `map_identity` — source-backed map identification and spatial metadata.
15. `validation_findings` — missing, unresolved, inconsistent, unsupported, or unverified extraction information.

Separate tables may be added when the source contains a distinct event or observation grain. Do not merge different event types merely to reduce the number of tables.

### 14. Extraction completeness report

For every replay, report:

- Which data groups were available.
- Which data groups were extracted.
- Which data groups were unavailable.
- Which fields were present but undecoded.
- Which event types were partially supported.
- Which identities could not be resolved.
- Which timestamps or units are uncertain.
- Which records could not be associated with a player, round, team, or object.
- Counts of extracted records by data group.
- Counts of missing or unresolved records.
- Any source-to-output discrepancies.

Distinguish `NOT_PRESENT_IN_SOURCE`, `NOT_EXPOSED_BY_PARSER`, `DECODE_FAILED`, `UNRESOLVED`, and `NOT_TESTABLE` wherever the evidence permits.

Do not claim that a category is absent from the replay merely because the parser did not expose it.

### 15. Final extraction principle

The output must preserve enough information to reconstruct the match as a time-ordered tactical system:

- Players occupy and move through space.
- Teams establish, contest, deny, and exploit access.
- Players use abilities and create utility objects.
- Utility objects change the state of the environment.
- Players are exposed to effects.
- Combat and objective events occur.
- Team positions and available options change over time.
- Rounds reach outcomes.

The extraction must preserve the underlying observations needed to investigate these relationships later. It must not decide the tactical meaning or causal explanation during extraction.

**Do not add tactical ratings, coaching judgments, map-control scores, win probabilities, strategic conclusions, or causal claims to the parsed output. Those belong to later analytical stages.**