# Claude Code setup

This public demo keeps local Claude Code configuration out of git.

Tracked:
- `.claude/settings.local.json.example` with placeholders only.

Ignored:
- `.claude/settings.local.json`
- `.env`
- `.secrets/`
- OAuth token files and browser profiles.

Recommended local flow:

```bash
cp .claude/settings.local.json.example .claude/settings.local.json
mkdir -p .secrets && chmod 700 .secrets
python -m unittest discover -s tests
bash scripts/skill_lint.sh
```

Do not commit filled tokens, workspace-specific IDs, daily notes, logs, or exported source data.
