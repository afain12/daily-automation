# Mac setup

Sanitized public setup notes.

```bash
git clone https://github.com/your-org/daily-automation.git
cd daily-automation
python3 -m pip install pyyaml
cp .claude/settings.local.json.example .claude/settings.local.json
cp examples/coo_mode.yaml state/coo_mode.yaml
python -m unittest discover -s tests
```

Add real credentials only to ignored local files such as `.secrets/*.env`, `.env`, or `.claude/settings.local.json`.
