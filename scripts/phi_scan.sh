#!/usr/bin/env bash
# scripts/phi_scan.sh — input gate for /capture-meeting. Scans stdin for PHI markers.
#
# Usage:
#   echo "$NOTES" | scripts/phi_scan.sh
#   if scripts/phi_scan.sh < notes.txt; then echo "clean"; else echo "PHI detected"; fi
#
# Exit codes:
#   0  — no PHI markers detected. Safe to proceed.
#   1  — PHI markers detected. Caller MUST refuse and prompt user to clean the input.
#   2  — read error.
#
# What it scans for (regex, case-insensitive where applicable):
#   - SSN-shaped: \b\d{3}-\d{2}-\d{4}\b
#   - DOB-shaped with year: \b\d{1,2}[/-]\d{1,2}[/-](19|20)\d{2}\b
#   - MRN-shaped: \bMRN[: ]?\d{4,}\b
#   - DOB:/DOB- explicit labels: \b(DOB|D\.O\.B\.|date of birth)\b
#
# Why these and not more:
#   - This is NOT a HIPAA-compliance tool. It's a "stop the dumbest leakage" gate.
#   - Aaron's actual workflow rarely involves patient identifiers; the meetings
#     are operational (providers, urgent cares, panels). PHI showing up is almost
#     always an accident.
#
# Output on detection: line numbers + sanitized snippets to stderr.

set -euo pipefail

INPUT="$(cat)"
if [ -z "${INPUT}" ]; then
  echo "phi_scan.sh: empty input" >&2
  exit 2
fi

# Pass input via env var. Cannot use both a heredoc body AND a here-string for stdin.
export PHI_SCAN_INPUT="${INPUT}"

python - <<'PY'
import os, re, sys

text = os.environ.get("PHI_SCAN_INPUT", "")
lines = text.splitlines()

patterns = [
    ("SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("DOB (date)", re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-](?:19|20)\d{2}\b")),
    ("MRN", re.compile(r"\bMRN[\s:]*\d{4,}\b", re.IGNORECASE)),
    ("DOB label", re.compile(r"\b(?:DOB|D\.O\.B\.|date of birth)\b", re.IGNORECASE)),
]

hits = []
for i, line in enumerate(lines, start=1):
    for label, pat in patterns:
        m = pat.search(line)
        if m:
            sanitized = line[:m.start()] + "***" + line[m.end():]
            hits.append((i, label, sanitized[:120]))

if hits:
    print("PHI markers detected:", file=sys.stderr)
    for i, label, snippet in hits:
        print(f"  line {i} [{label}]: {snippet}", file=sys.stderr)
    sys.exit(1)

sys.exit(0)
PY
