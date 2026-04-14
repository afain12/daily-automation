# COO Twin — Daily Automation System

Personal Chief of Staff system that unifies Notion, Obsidian, Google Calendar,
and Google Tasks into a single terminal workflow.

## Project Structure

```
config/sources.yaml        — All source definitions, DB IDs, field mappings, business tags
config/routing-rules.yaml  — Meeting note routing rules (Phase 2)
state/priorities.yaml      — Carry-forward items between days (Phase 3)
logs/YYYY-MM-DD.md         — Daily briefing logs (retained 90 days)
vault/                     — Obsidian vault (inbox, daily, notes, meetings)
.agents/skills/start-day/  — /start-day skill (Phase 1)
```

## Skills

| Skill | Phase | Status | Description |
|-------|-------|--------|-------------|
| `/start-day` | 1 | Active | Morning briefing + daily plan |
| `/capture-meeting` | 2 | Planned | Meeting note splitter (Notion + Obsidian) |
| `/end-day` | 3 | Planned | Day close retro, planned vs actual |
| `/weekly-review` | 4 | Planned | Weekly patterns + insights |

## Data Sources

- **Google Calendar**: via `gws calendar` CLI
- **Google Tasks**: via `gws tasks` CLI
- **Notion**: via REST API (`curl`) using `$NOTION_API_TOKEN` — uses `/v1/data_sources/` endpoint (API v2025-09-03)
- **Obsidian**: direct file read/write at `vault/`

## Key Principles

- **Read-first, write-on-approval.** Never auto-write without trust gate confirmation.
- **Graceful degradation.** If any source is unavailable, run with what's available.
- **Local state is primary.** Config and logs live in this repo, not Claude memory.
- **Business tagging.** Every item tagged lab/ipa/nestmate via config rules.

## Design Doc

Full approved design: `~/.gstack/projects/daily-automation/aaron-master-design-20260414-103924.md`
