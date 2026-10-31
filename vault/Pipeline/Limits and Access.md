---
type: reference
status: current
updated: 2026-10-30
tags: [valosaber, pipeline, limits]
---
# Limits and access

What the Claude session can and cannot reach. Check this before promising something.

| Area | Situation | Workaround |
|---|---|---|
| Claude's environment | A cloud Linux container, separate from the user's computer. Nothing on his machine or in Obsidian is visible unless he attaches it | Attach files; keep the project docs current |
| Plan | Free plan: no scheduled tasks, browser control or computer control | Write reusable steps and run them on request |
| Network | Allowlist. `valorant-api.com` is blocked. Package registries work | Ask the user to allow the domain in network settings; use web search and fetch for pages that appear in results |
| Web fetch | Only URLs that appeared in the conversation or search results | Search first, then fetch the result link |
| Drive layout | `MyDrive/valosaber/bin/` holds the bootstrap zip with `vrfkit` inside; `vrfkit_bin/` is an unrelated older binary | Colab reads the zip through `parser/colab_bootstrap.py`; the connector cannot download it (over 10 MB) |
| Google Drive connector | Reads metadata and text; downloads up to 10 MB per file | Shards under 8 MB ([[ADR-004 Ship shards not raw files]]); raw replays cannot go through it |
| GitHub | Linked. Repo `nicholasjlivingston-a11y/ValorantUtility`, branch `main`; clone, pull and push work from the session. Needed the Claude GitHub app installed on the account and the repo attached with push access | Keep each file under 100 MB (25 MB for web uploads). New chats must attach the repo again |
| Project docs | Text documents; they persist across sessions | Keep scripts and lookup JSON here; do not store parquet |
| Obsidian | Not reachable from the session; it does not update itself | Vault lives in the repo under `vault/`; the user pulls it (Obsidian Git plugin can auto-pull) |
| Artifacts | Published pages are private to the owner until shared | Tell the user when a page is meant for others |
| Replay files | Original `.vrf` and the 159 MB package are not readable here | Parse on the user's side and send shards |

## Plain-words rule
When speaking to the user, say "linked to your computer" or "not linked", not internal tool names.
