# Daily Automation — Hermes Agent COO Twin Example

This repository is a public-safe example of a Hermes Agent personal operations system.
It shows how to combine:

- Hermes/Claude-style skills under `.claude/skills/`
- Notion as an operations database
- Google Calendar and Google Tasks as execution surfaces
- Obsidian-style Markdown notes as a local knowledge base
- Trust-gated scripts for daily planning, meeting capture, end-of-day review, and automation

The private production data has intentionally been removed. Runtime state, logs, Notion exports, daily notes, contact/customer data, and OAuth tokens should live locally and remain ignored by git.

## What is included

- Skill definitions for the main workflows: `start-day`, `capture-meeting`, `end-day`, `meeting-prep`, `automation`, `vault-health`, and setup/probing helpers.
- Python/Bash helper scripts for preflight checks, routing, validation, PHI scanning, idempotency, calendar planning, and vault search.
- Sanitized sample configuration in `config/`.
- Unit tests for the pure helper logic.
- GitHub validation workflow and local git hooks.

## What is intentionally excluded

- `.secrets/`, `.env`, OAuth token files, local Claude/Hermes settings.
- Runtime state under `state/` except placeholders and safe defaults.
- Logs under `logs/`.
- Obsidian vault contents under `vault/`.
- `.context/` staged/applied write payloads.
- Any exported Notion pages, customer/contact records, personal daily notes, or presentation-private business material.

## Quick start

```bash
python3 --version
python3 -m pip install pyyaml
cp .env.example .env   # optional; do not commit filled values
python -m unittest discover -s tests
bash scripts/skill_lint.sh
python scripts/streams_check.py
```

Create local runtime files as needed:

```bash
mkdir -p .secrets .context/preview .context/applied logs state vault/inbox vault/daily
chmod 700 .secrets
cp examples/coo_mode.yaml state/coo_mode.yaml
```

## Runtime model

The system is deliberately gated:

1. `scripts/preflight.sh` checks mode and resource availability.
2. Skills read from Notion/Google/Obsidian first.
3. External writes are staged as previews or action IDs.
4. A human approval gate is required before Notion, Calendar, Tasks, or vault writes.
5. Telemetry/logs remain local and ignored.

## Public-safety note

Before making a fork or demo repo public, run:

```bash
git status --short
python -m unittest discover -s tests
bash scripts/skill_lint.sh
python scripts/streams_check.py
git grep -n -E 'token|secret|password|client_secret|refresh_token|access_token|BEGIN .*PRIVATE|sk-|ghp_|github_pat_|ntn_' -- . ':!.env.example'
```

If any real identifiers or private business records appear, remove or replace them before publishing.
