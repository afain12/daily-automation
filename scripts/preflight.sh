#!/usr/bin/env bash
# scripts/preflight.sh — unified Step 0 for every COO Twin skill.
#
# Consolidates mode check + resource availability checks into a single call.
# Replaces the per-skill pattern of `MODE=$(scripts/check_mode.sh) || exit`
# followed by scattered NOTION_API_TOKEN / gws / vault path checks in later steps.
#
# Usage:
#   eval "$(scripts/preflight.sh)"          # source key=value output into shell
#   # → sets MODE, NOTION_OK, GWS_OK, VAULT_OK, PREFLIGHT_WARNINGS, SKIP_WRITES
#
#   scripts/preflight.sh --json             # JSON form for jq/python consumers
#
#   scripts/preflight.sh --require notion,gws,vault   # hard-fail on missing reqs
#
# Exit codes:
#   0  — preflight ok (mode != locked, all required resources present)
#   1  — mode is locked. Skill MUST refuse.
#   2  — required resource missing (per --require flag).
#   3  — coo_mode.yaml unreadable. Fail closed.
#
# Output (key=value form, default):
#   MODE=draft
#   NOTION_OK=1
#   GWS_OK=1
#   VAULT_OK=1
#   SKIP_WRITES=0
#   PREFLIGHT_WARNINGS=''      # space-separated short codes; empty if none
#
# Design notes:
# - Skills can keep calling check_mode.sh directly if they only need the mode.
#   preflight.sh is the consolidated entry point for skills that also touch
#   Notion / gws / vault — it short-circuits the scattered checks.
# - Resource checks are non-fatal by default (set NOTION_OK=0 etc, add a warning,
#   exit 0). Use --require to escalate specific resources to hard failures.
# - Matches scripts/check_mode.sh exit semantics for mode handling.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

OUTPUT_FORMAT="kv"
REQUIRE=""
for arg in "$@"; do
  case "$arg" in
    --json)         OUTPUT_FORMAT="json" ;;
    --kv)           OUTPUT_FORMAT="kv" ;;
    --require)      shift ;;
    --require=*)    REQUIRE="${arg#--require=}" ;;
    *)
      if [ -n "${PREV_FLAG:-}" ] && [ "${PREV_FLAG}" = "--require" ]; then
        REQUIRE="$arg"
      fi
      ;;
  esac
  PREV_FLAG="$arg"
done

WARNINGS=()
add_warning() { WARNINGS+=("$1"); }

# --- 1. Mode check (delegates to check_mode.sh) -----------------------------
MODE=""
MODE_EXIT=0
MODE="$("${REPO_DIR}/scripts/check_mode.sh" 2>/dev/null)" || MODE_EXIT=$?

if [ "$MODE_EXIT" -eq 1 ]; then
  # locked — emit minimal output and exit non-zero
  if [ "$OUTPUT_FORMAT" = "json" ]; then
    printf '{"mode":"locked","preflight_ok":false,"warnings":["locked"]}\n'
  else
    printf 'MODE=locked\nPREFLIGHT_OK=0\nPREFLIGHT_WARNINGS=locked\n'
  fi
  exit 1
fi

if [ "$MODE_EXIT" -ne 0 ] || [ -z "$MODE" ]; then
  if [ "$OUTPUT_FORMAT" = "json" ]; then
    printf '{"mode":"unknown","preflight_ok":false,"warnings":["mode_unreadable"]}\n'
  else
    printf 'MODE=unknown\nPREFLIGHT_OK=0\nPREFLIGHT_WARNINGS=mode_unreadable\n'
  fi
  exit 3
fi

# --- 2. Notion token --------------------------------------------------------
NOTION_OK=0
if [ -n "${NOTION_API_TOKEN:-}" ]; then
  NOTION_OK=1
else
  add_warning "notion_token_missing"
fi

# --- 3. gws CLI -------------------------------------------------------------
GWS_OK=0
if command -v gws >/dev/null 2>&1; then
  # Don't actually call `gws auth status` — too slow for a hot path. Presence
  # of the binary is enough for preflight; failures surface when a skill calls gws.
  GWS_OK=1
else
  add_warning "gws_cli_missing"
fi

# --- 4. Vault path ----------------------------------------------------------
VAULT_OK=0
VAULT_PATH="${REPO_DIR}/vault"
if [ -d "$VAULT_PATH" ]; then
  VAULT_OK=1
else
  add_warning "vault_missing"
fi

# --- 5. Apply --require gates -----------------------------------------------
# REQUIRE is a comma-separated list: notion,gws,vault
if [ -n "$REQUIRE" ]; then
  IFS=',' read -ra REQ <<< "$REQUIRE"
  for r in "${REQ[@]}"; do
    case "$r" in
      notion) [ "$NOTION_OK" -eq 1 ] || { emit_and_exit_required="notion_required"; break; } ;;
      gws)    [ "$GWS_OK" -eq 1 ]    || { emit_and_exit_required="gws_required"; break; } ;;
      vault)  [ "$VAULT_OK" -eq 1 ]  || { emit_and_exit_required="vault_required"; break; } ;;
    esac
  done
fi

# --- 6. SKIP_WRITES (derived) -----------------------------------------------
SKIP_WRITES=0
if [ "$MODE" = "observe" ]; then
  SKIP_WRITES=1
fi

# --- 7. Emit ----------------------------------------------------------------
WARN_STR="${WARNINGS[*]:-}"

if [ "$OUTPUT_FORMAT" = "json" ]; then
  python - <<PY
import json
print(json.dumps({
  "mode": "$MODE",
  "notion_ok": bool($NOTION_OK),
  "gws_ok": bool($GWS_OK),
  "vault_ok": bool($VAULT_OK),
  "skip_writes": bool($SKIP_WRITES),
  "preflight_ok": True,
  "warnings": "$WARN_STR".split() if "$WARN_STR" else [],
}, separators=(",",":")))
PY
else
  printf 'MODE=%s\n' "$MODE"
  printf 'NOTION_OK=%s\n' "$NOTION_OK"
  printf 'GWS_OK=%s\n' "$GWS_OK"
  printf 'VAULT_OK=%s\n' "$VAULT_OK"
  printf 'SKIP_WRITES=%s\n' "$SKIP_WRITES"
  printf 'PREFLIGHT_OK=1\n'
  printf "PREFLIGHT_WARNINGS='%s'\n" "$WARN_STR"
fi

# --- 8. Required-resource hard failure exit ---------------------------------
if [ -n "${emit_and_exit_required:-}" ]; then
  echo "preflight.sh: required resource failed: ${emit_and_exit_required}" >&2
  exit 2
fi

exit 0
