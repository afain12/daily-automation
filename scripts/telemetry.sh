#!/usr/bin/env bash
# scripts/telemetry.sh — append one JSONL row to logs/_telemetry.jsonl
#
# Usage:
#   scripts/telemetry.sh <skill> <run_id> <duration_ms> <status> [extra_json]
#
# Example:
#   scripts/telemetry.sh start-day sd-20260518-0703 18420 ok '{"sources_ok":["calendar","notion"],"top3_scores":[8,7,5]}'
#
# Notes:
# - Append-only, idempotent (re-running with same run_id creates two rows; caller's responsibility to keep run_id unique).
# - Cross-platform: pure bash, no jq dependency. Caller passes pre-formed JSON for extras.
# - The file is the OBSERVED discipline's load-bearing artifact. Never modify rows in place.

set -euo pipefail

SKILL="${1:?usage: telemetry.sh <skill> <run_id> <duration_ms> <status> [extra_json]}"
RUN_ID="${2:?missing run_id}"
DURATION_MS="${3:?missing duration_ms}"
STATUS="${4:?missing status (ok|partial|failed)}"
# Avoid `${5:-{}}` — Git Bash mis-parses the brace-only default and leaks a `}`.
EXTRA_JSON="${5-}"
[ -z "${EXTRA_JSON}" ] && EXTRA_JSON='{}'

# Resolve repo root regardless of cwd.
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_FILE="${REPO_DIR}/logs/_telemetry.jsonl"

# ISO 8601 with timezone offset. `date -Iseconds` works on GNU + BSD + Git Bash.
TS="$(date -Iseconds 2>/dev/null || date +"%Y-%m-%dT%H:%M:%S%z")"

mkdir -p "${REPO_DIR}/logs"

# Validate extra_json is parseable. If it isn't, fail loudly rather than write garbage.
if ! printf '%s' "${EXTRA_JSON}" | python -c "import sys,json; json.loads(sys.stdin.read())" 2>/dev/null; then
  echo "telemetry.sh: extra_json is not valid JSON: ${EXTRA_JSON}" >&2
  exit 2
fi

# Compose the row. Use python for safe JSON encoding of string fields.
python - <<PY >> "${LOG_FILE}"
import json, sys
row = {
    "ts": "${TS}",
    "skill": "${SKILL}",
    "run_id": "${RUN_ID}",
    "duration_ms": int("${DURATION_MS}"),
    "status": "${STATUS}",
}
extra = json.loads('''${EXTRA_JSON}''')
row.update(extra)
print(json.dumps(row, separators=(",", ":")))
PY
