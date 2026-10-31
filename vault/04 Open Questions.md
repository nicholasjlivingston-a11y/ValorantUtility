---
type: questions
status: current
updated: 2026-10-30
tags: [valosaber, questions]
---
# Open Questions

Add new questions at the top. When one is answered, move it to the "Answered" section with the answer and where it is recorded.

## Open
| # | Question | Why it matters | What would answer it | Owner |
|---|---|---|---|---|
| 1 | Is economy really zero in this build or only in Swiftplay? Where do real values live? | No economy metrics until solved | A competitive replay; coding agent checks the source | Coding agent |
| 2 | What do the `Slot` numbers (3, 4, 5, 9) mean for ability casts? | Per-ability results | Coding agent decodes, or a replay with known casts | Coding agent |
| 3 | What do `AssistType` values (0, 1, 10, 14) and hit `Region` codes mean? | Assists, headshots | Coding agent decodes | Coding agent |
| 4 | Is map code `Pitt` Pearl? | Map names and factors | An official source or the agent's map table | User or reference table |
| 5 | Is Pine's manifest ID `92eeef5d-…` Veto? | Confirm the name from the ID, not only the kit | An agent-ID page for that ID or the official API | Reference table |
| 6 | Is Phoenix's codename in this build `Phoenix`? One source lists `Apollo` | Name is kit-only | An official source | Reference table |
| 7 | How should the win-probability model treat the spike and sides? | Post-plant rounds are mispredicted | Many rounds with spike and side data | Phase 2 |
| 8 | What is the unit of per-target effect values (seconds? fraction? damage?) | Weighting utility effects | Effect start and end times plus the coding agent's decoding | Coding agent |
| 9 | Can the Drive connector create binary files? | Whether Claude can write shards back | A test write | Claude |
| 13 | Does the agent list miss one agent? Outlets number Veto 29th and Hush 31st, but lists show 28 agents before Miks | A complete class table | An official agent list | Reference table |
| 10 | Who are the 10 players across matches? Is `Subject` UUID stable between matches? | Player baselines | Two matches with the same player | Needs more replays |
| 11 | Why did the stats layer fill defaults instead of decoded values? | No trustworthy tables from the pipeline | Resend the brief; require acceptance checks on the Swiftplay sample | Coding agent |

## Answered
| Question | Answer | Recorded in |
|---|---|---|
| Which combat-report component belongs to which player? | Match damage dealt against damage received; one zero-cost assignment out of 14,400 | [[ADR-001 Owner resolution by damage reciprocity]] |
| Why did only 7 of 10 players get positions? | Casts use public names for 3 confirmed codenames, actor paths use raw codenames | [[Replay Data Guide]] |
| Is Sequoia Tejo? | No. Its manifest ID resolves to Iso | [[Agents]] |
| Is the kill time reliable? | Yes, within 9 ms of death events using field row timestamps | [[ADR-002 Event timing from field timestamps]] |
| Which source confirms each agent's class? | Two agent-list pages agree on all 28 listed agents; Miks from a reveal article (Controller). Rechecked per patch | [[Agent Classes]] |
