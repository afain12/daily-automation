#!/usr/bin/env bash
# scripts/action_id.sh — generate idempotency key + check whether the action already ran.
#
# Usage:
#   action_id.sh generate <skill> <target> <date> <payload_hash_input>
#     Prints the action_id to stdout. Format: {skill}:{target}:{date}:{8-char-hash}
#
#   action_id.sh check <action_id>
#     Exit 0 if .context/applied/{action_id}.json exists (action already ran).
#     Exit 1 if not (action is fresh, safe to proceed).
#
#   action_id.sh stamp <action_id> [extra_json]
#     Create .context/applied/{action_id}.json with timestamp + optional extra metadata.
#     Caller invokes this AFTER the external write succeeds.
#
# Why: AAC GATED §2.3 action-gate — every external write needs idempotency. PRD §8.8
# undo-payload protocol uses these same action_ids as the join key.
#
# Examples:
#   AID=$(scripts/action_id.sh generate capture-meeting 22ba3158-recap-page 2026-05-18 "send_email to provider X")
#   scripts/action_id.sh check "$AID" && echo "already ran, skipping" || run_the_write
#   # ... do the write ...
#   scripts/action_id.sh stamp "$AID" '{"notion_page_id":"abc-123"}'

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APPLIED_DIR="${REPO_DIR}/.context/applied"

SUBCMD="${1:?usage: action_id.sh <generate|check|stamp> ...}"

case "${SUBCMD}" in
  generate)
    SKILL="${2:?missing skill}"
    TARGET="${3:?missing target}"
    DATE="${4:?missing date (YYYY-MM-DD)}"
    PAYLOAD_INPUT="${5:?missing payload_hash_input}"

    # 8-char hex hash of the payload input. Use python hashlib — portable.
    HASH="$(printf '%s' "${PAYLOAD_INPUT}" | python -c "
import hashlib, sys
print(hashlib.sha256(sys.stdin.read().encode()).hexdigest()[:8])
")"

    # Sanitize skill/target for filename safety (colons and slashes are fine on
    # the action_id itself, but check/stamp will normalize for the filename).
    echo "${SKILL}:${TARGET}:${DATE}:${HASH}"
    ;;

  check)
    AID="${2:?missing action_id}"
    # Filenames can't contain colons on Windows. Map ':' -> '_' for the on-disk name.
    FNAME="${AID//:/_}.json"
    if [ -f "${APPLIED_DIR}/${FNAME}" ]; then
      exit 0
    else
      exit 1
    fi
    ;;

  stamp)
    AID="${2:?missing action_id}"
    # Avoid `${3:-{}}` — Git Bash mis-parses the brace-only default and leaks a `}`.
    EXTRA_JSON="${3-}"
    [ -z "${EXTRA_JSON}" ] && EXTRA_JSON='{}'
    FNAME="${AID//:/_}.json"
    mkdir -p "${APPLIED_DIR}"
    TS="$(date -Iseconds 2>/dev/null || date +"%Y-%m-%dT%H:%M:%S%z")"

    python - <<PY > "${APPLIED_DIR}/${FNAME}"
import json
extra = json.loads('''${EXTRA_JSON}''')
row = {"action_id": "${AID}", "applied_at": "${TS}", "status": "applied"}
row.update(extra)
print(json.dumps(row, indent=2))
PY
    ;;

  *)
    echo "action_id.sh: unknown subcommand '${SUBCMD}'" >&2
    echo "usage: action_id.sh <generate|check|stamp> ..." >&2
    exit 2
    ;;
esac
