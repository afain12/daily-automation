# Roadmap — Future Enhancements (not yet built)

Speculative work, not current project state. Extracted from CLAUDE.md 2026-05-19.

- **/weekly-review (Phase 4):** Requires 2+ weeks of daily logs before building. Will read all logs from past 7 days, surface cross-day patterns, recurring carry-forwards, cross-business balance, and suggested priorities for next week.

- **Time-blocking integration:** /start-day should offer to block calendar time for Top 3 outcomes. /end-day should suggest time slots for tomorrow's carry-forwards.

- **Notion EOD scan depth:** Expand /end-day to check Client Tracker and Nestmate Account Tracking databases beyond the three configured DBs, once those are shared with the integration.

- **Hooks integration** — add to `.claude/settings.json`:
  - `SessionStart` → auto-sync vault from OneDrive (replaces the manual `cp -ru` step at the top of `/start-day`)
  - `PostToolUse` matching `Bash` + `curl` to api.notion.com → append a one-line Notion-write audit to `logs/YYYY-MM-DD.md`
  - `Stop` → write a session summary to the day's log for easier `/end-day` retro

- **Promote shared config to committed `.claude/settings.json`** — once a second machine or collaborator appears, move `autoMode.environment` and non-secret `permissions.allow` entries into the committed project settings, keeping only `NOTION_API_TOKEN` in `.local.json`.
