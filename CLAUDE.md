# Daily Automation — Claude Code Operating Guide

This file mirrors `AGENTS.md` for Claude Code. Keep the public safety rules and validation commands in sync with `AGENTS.md`.

## Safety principles

- Read first, write only after approval.
- Keep secrets outside git: `.secrets/`, `.env`, OAuth token files, local settings, and browser profiles are ignored.
- Keep runtime data outside git: `.context/`, `logs/`, `state/tmp/`, and `vault/` are local-only.
- Use sanitized placeholders in `config/sources.yaml`; never commit real Notion IDs, customer records, contact records, calendar exports, or daily notes.
- External writes must be staged or previewed before execution.

## Validation commands

```bash
python -m unittest discover -s tests
bash scripts/skill_lint.sh
python scripts/streams_check.py
bash scripts/test_phi_gate.sh
```

## Main workflows

| Skill | Purpose |
| --- | --- |
| `/setup` | Collect source availability and stream definitions. |
| `/start-day` | Generate morning briefing and execution plan. |
| `/meeting-prep` | Build a pre-meeting dossier from available sources. |
| `/capture-meeting` | Split meeting notes into tasks, decisions, insights, and follow-ups. |
| `/end-day` | Compare planned vs actual output and carry forward next steps. |
| `/automation` | Run saved prompts on a cadence. |
| `/vault-health` | Audit local Markdown vault health. |

## Runtime gates

1. Run `scripts/preflight.sh` to check mode and source availability.
2. Read from configured sources.
3. Stage proposed writes with an action ID or preview file.
4. Ask for approval.
5. Execute writes only after approval.
6. Log telemetry locally.

## Notes for public demos

This repository intentionally excludes the private production vault, task exports, Notion payloads, CRM/contact data, personal daily notes, and logs. Use `README.md` and the sanitized config examples for demos. If you adapt it for your own environment, keep your production data in ignored local paths.
