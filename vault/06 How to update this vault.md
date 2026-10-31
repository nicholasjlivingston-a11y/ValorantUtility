---
type: guide
status: current
updated: 2026-10-30
tags: [valosaber, maintenance]
---
# How to update this vault

This vault is meant to change constantly. Keep it cheap to update.

## At the end of every session (five minutes)
1. **[[02 Current State]]**: move items between Done, In progress, Blocked and Next up. Update the key numbers.
2. **[[05 Changelog]]**: add one line per meaningful change, newest first.
3. **[[04 Open Questions]]**: add new unknowns; move answered ones down with the answer.
4. **Reference notes**: if a name's status changed, edit its row in [[Agents]], [[Maps]] or [[Abilities]], and the `updated` date.
5. **Project copy**: re-save changed files into the Claude project so the next chat sees them (lookup JSON, scripts, `START_HERE.md`).
6. Set `updated:` in the frontmatter of every note you touched.

## Status words (use exactly these so queries work)
| Status | Meaning |
|---|---|
| `confirmed` | A public source or the replay's own IDs agree with the kit or data |
| `confirmed_by_user_and_kit` | The user stated it and the kit matches; no independent source |
| `kit_only` | The kit matches but nothing published confirms the codename |
| `unconfirmed` | Keep the raw codename in all output |
| `current` | A note is up to date |
| `stale` | A note needs checking against reality |

## Adding things
- **New decision:** copy [[Decision Record]] into `Decisions/`, number it, link it from the notes it affects.
- **New match:** copy [[Match Note]] into `Matches/`.
- **New reference entry:** copy [[Reference Entry]] fields into the right table.
- **Session log:** copy [[Session Log]] into `Sessions/` when a session is long enough to be worth reconstructing.

## Rules of thumb
- If it changes often, it goes in a table or the changelog, not in prose.
- If two notes say the same thing, keep one and link to it.
- Never delete evidence. Mark a claim `stale` and say why.
- If a note disagrees with the code or the data, the code and data win. Fix the note.

## Optional: Dataview
With the Dataview plugin you can list everything not yet confirmed. Put this in any note:
```dataview
TABLE status, updated
FROM "Reference"
WHERE status != "confirmed"
```
