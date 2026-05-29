#!/usr/bin/env bash
# scripts/check_mode.sh — print the current COO_MODE; exit non-zero if locked.
#
# Usage:
#   MODE=$(scripts/check_mode.sh) || { echo "agent is locked"; exit 1; }
#   if [ "$MODE" = "observe" ]; then SKIP_WRITES=1; fi
#
# Exit codes:
#   0  — mode read successfully (printed to stdout)
#   1  — mode is `locked`. Caller must refuse to run.
#   2  — coo_mode.yaml missing or unreadable. Fail closed (treat as locked).
#
# Why a script: skills are markdown that Claude reads. A skill instruction like
# "run scripts/check_mode.sh and stop if it exits non-zero" is shorter and more
# reliable than "parse YAML and check the mode field."

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE_FILE="${REPO_DIR}/state/coo_mode.yaml"

if [ ! -r "${MODE_FILE}" ]; then
  echo "check_mode.sh: ${MODE_FILE} missing or unreadable — failing closed (treating as locked)" >&2
  exit 2
fi

# Extract `mode:` value. Use python for robust YAML parsing — no PyYAML dependency,
# just regex match since coo_mode.yaml has a stable simple shape.
MODE="$(python - <<'PY'
import re, sys, pathlib
text = pathlib.Path("state/coo_mode.yaml").read_text()
m = re.search(r"^\s*mode\s*:\s*(\w+)\s*$", text, re.MULTILINE)
print(m.group(1) if m else "")
PY
)"

if [ -z "${MODE}" ]; then
  echo "check_mode.sh: could not parse mode from ${MODE_FILE} — failing closed" >&2
  exit 2
fi

echo "${MODE}"

if [ "${MODE}" = "locked" ]; then
  exit 1
fi
