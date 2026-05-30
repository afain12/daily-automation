#!/usr/bin/env bash
# bootstrap-mac.sh — one-command setup for the COO Twin / Hermes replica on macOS
# (Mac mini localhost). Idempotent: safe to re-run. Does NOT transport secrets —
# you paste the Notion token here, and run the interactive Google login yourself.
#
#   git clone https://github.com/afain12/daily-automation.git
#   cd daily-automation
#   bash scripts/bootstrap-mac.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
echo "==> Repo root: $REPO_ROOT"

# ── 1. Prerequisite check ───────────────────────────────────────────────────
echo "==> Checking prerequisites..."
missing=()
for cmd in git python3 curl jq node npm; do
  command -v "$cmd" >/dev/null 2>&1 || missing+=("$cmd")
done
command -v gws    >/dev/null 2>&1 || missing+=("gws (npm i -g @googleworkspace/gws or your install)")
command -v claude >/dev/null 2>&1 || missing+=("claude (Claude Code CLI)")
if [ ${#missing[@]} -gt 0 ]; then
  echo "    Missing (install these, then re-run):"
  printf '      - %s\n' "${missing[@]}"
  echo "    On macOS most are: brew install git jq node ; node provides npm."
  # gws / claude are not blockers for writing config, so warn but continue.
fi

# ── 2. Make bash scripts executable ─────────────────────────────────────────
echo "==> chmod +x scripts/*.sh"
chmod +x scripts/*.sh 2>/dev/null || true

# ── 3. Generate .claude/settings.local.json from template ───────────────────
SETTINGS=".claude/settings.local.json"
TEMPLATE=".claude/settings.local.json.example"
if [ -f "$SETTINGS" ]; then
  echo "==> $SETTINGS already exists — leaving it untouched."
else
  echo "==> Creating $SETTINGS from template (paths substituted for this host)."
  # Substitute placeholder paths to this host's real values.
  sed -e "s|__REPO_ROOT__|$REPO_ROOT|g" -e "s|__HOME__|$HOME|g" "$TEMPLATE" > "$SETTINGS"
  # Prompt for the Notion token (hidden input). Skip with empty to fill in later.
  printf "    Paste your NOTION_API_TOKEN (ntn_...), or press Enter to fill in later: "
  read -rs NOTION_TOKEN; echo
  if [ -n "${NOTION_TOKEN:-}" ]; then
    python3 - "$SETTINGS" "$NOTION_TOKEN" <<'PY'
import json, sys
path, token = sys.argv[1], sys.argv[2]
with open(path) as f: d = json.load(f)
d.setdefault("env", {})["NOTION_API_TOKEN"] = token
with open(path, "w") as f: json.dump(d, f, indent=2)
print("    Token written.")
PY
  else
    echo "    Left __NOTION_API_TOKEN__ placeholder — edit $SETTINGS before running skills."
  fi
  chmod 600 "$SETTINGS"
fi

# ── 4. Google Workspace auth (interactive — must be you) ─────────────────────
echo "==> Checking Google Workspace (gws) auth..."
if command -v gws >/dev/null 2>&1 && gws auth status >/dev/null 2>&1; then
  echo "    gws already authenticated."
else
  echo "    gws NOT authenticated. Run this yourself (opens a browser):"
  echo "      gws auth login --scopes calendar,tasks"
fi

# ── 5. Validate via preflight ───────────────────────────────────────────────
echo "==> Running preflight (mode + source availability)..."
if [ -f scripts/preflight.sh ]; then
  eval "$(scripts/preflight.sh)" || true
  echo "    MODE=${MODE:-?}  NOTION_OK=${NOTION_OK:-?}  GWS_OK=${GWS_OK:-?}  VAULT_OK=${VAULT_OK:-?}"
else
  echo "    scripts/preflight.sh not found — skipped."
fi

cat <<EOF

==> Done. Replica is set up at $REPO_ROOT
    Remaining manual steps (interactive / host-specific):
      1. If you skipped it: gws auth login --scopes calendar,tasks
      2. If you left the token placeholder: edit $SETTINGS
      3. Telegram MVE scripts (scripts/mve-telegram-*.ps1) are PowerShell / Windows-only
         and will NOT run here — port to bash/python on the Mac if you need that loop.
    Then launch Claude Code in this dir and try:  /start-day
EOF
