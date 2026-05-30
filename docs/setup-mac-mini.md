# Setting up the COO Twin / Hermes replica on the Mac mini

This repo is the transport for running the COO Twin system as the **Hermes agent on a
Mac mini (localhost)**. The private repo carries everything except secrets: the full
Obsidian vault (incl. business folders), all skills, config, scripts, state, and logs.
Secrets are supplied locally on the Mac — never committed.

## One-command setup

```bash
git clone https://github.com/afain12/daily-automation.git
cd daily-automation
bash scripts/bootstrap-mac.sh
```

`bootstrap-mac.sh` is idempotent (safe to re-run). It:
1. Checks prerequisites (`git`, `python3`, `curl`, `jq`, `node`/`npm`, `gws`, `claude`).
2. `chmod +x scripts/*.sh`.
3. Generates `.claude/settings.local.json` from `.claude/settings.local.json.example`,
   substituting this host's real paths and prompting (hidden input) for your
   `NOTION_API_TOKEN`. Writes it `chmod 600`. **Skips if the file already exists.**
4. Checks `gws` auth and tells you the login command if needed.
5. Runs `scripts/preflight.sh` and prints `MODE / NOTION_OK / GWS_OK / VAULT_OK`.

## Secrets you supply on the Mac (never in git)

See `.env.example` for the full list. The essentials:

| Secret | How it's used | How to set |
|--------|---------------|------------|
| `NOTION_API_TOKEN` | Notion REST API | Pasted into `.claude/settings.local.json` by the bootstrap (or edit by hand) |
| Google (Calendar/Tasks) | `gws` CLI, OAuth | `gws auth login --scopes calendar,tasks` (interactive, opens a browser) |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | MVE Telegram loop | Only if you port the Telegram scripts (see below) |

## Platform differences from the Windows laptop

- **No OneDrive sync on the Mac.** On Windows the business vault folders were `cp -ru`'d
  from OneDrive. Here they ship *inside the repo*, so the clone already has the full vault.
  They are a point-in-time snapshot — source of truth stays OneDrive on the Windows box.
  To refresh later, pull from the Windows side after it re-syncs and commits.
- **Telegram scripts are Windows-only.** `scripts/mve-telegram-send.ps1` and
  `mve-telegram-receive.ps1` are PowerShell and will not run on macOS. Port to bash/python
  if you need the Telegram capture loop on the Mac.
- **Paths.** The Mac config uses repo-relative / `$HOME` paths the bootstrap fills in —
  no hard-coded `C:/Users/...`. The `taskkill` and `railway` allow-entries from the
  Windows config are dropped (not needed here).

## Verify it works

```bash
eval "$(scripts/preflight.sh)" && echo "MODE=$MODE NOTION_OK=$NOTION_OK GWS_OK=$GWS_OK VAULT_OK=$VAULT_OK"
```

All three `*_OK` should be `1`. Then open Claude Code in this directory and run `/start-day`.

## Keeping the replica current

`git pull` whenever the Windows side pushes new vault/log/config content. The Windows box
remains the place where the daily `cp -ru` OneDrive sync and most authoring happen; the
Mac mini consumes the repo and runs the agent.
