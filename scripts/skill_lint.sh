#!/usr/bin/env bash
# scripts/skill_lint.sh — AAC discipline validator for COO Twin SKILL.md files.
#
# Identifies "ours" by presence of a `coo_twin:` block in the YAML frontmatter,
# so vendored external skills (auth-implementation-patterns, find-docs, etc.)
# are auto-skipped. Vendored skills don't have this block.
#
# What it checks per COO Twin skill:
#   1. coo_twin block has required fields: category, mode_required,
#      writes_external, preflight, experimental
#   2. Field values are in their allowed sets
#   3. SKILL.md body contains a Step 0 mode check (check_mode.sh OR preflight.sh)
#   4. SKILL.md body invokes telemetry.sh somewhere (OBSERVED discipline)
#   5. If writes_external==true, body mentions trust gate / approval language
#   6. If phi_gate==true, body invokes phi_scan.sh
#
# Usage:
#   scripts/skill_lint.sh              # lint all skills, exit non-zero on failures
#   scripts/skill_lint.sh --quiet      # only print failures
#   scripts/skill_lint.sh --json       # JSON report for CI consumption
#   scripts/skill_lint.sh path/to/SKILL.md  # lint one file
#
# Exit codes:
#   0 — all COO Twin skills pass
#   1 — at least one skill failed
#   2 — usage error

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

QUIET=0
OUTPUT_JSON=0
TARGETS=()

for arg in "$@"; do
  case "$arg" in
    --quiet) QUIET=1 ;;
    --json)  OUTPUT_JSON=1; QUIET=1 ;;
    -h|--help)
      sed -n '2,/^$/p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *) TARGETS+=("$arg") ;;
  esac
done

if [ "${#TARGETS[@]}" -eq 0 ]; then
  # Default: every SKILL.md under .claude/skills/
  while IFS= read -r -d '' f; do
    TARGETS+=("$f")
  done < <(find "${REPO_DIR}/.claude/skills" -name SKILL.md -print0 2>/dev/null)
fi

# --- Python helper: parse one SKILL.md, return findings as JSON ----------
# Embedding Python keeps the script dependency-free (Python is already required
# by other COO Twin scripts). Returns either "skip" (not a COO Twin skill) or
# a JSON object with "violations":[].

python_lint() {
  python - "$1" <<'PY'
import sys, re, json, pathlib

ALLOWED = {
  "category":       {"briefing", "capture", "admin", "setup"},
  "mode_required":  {"any", "draft+", "approved+"},
  "preflight":      {"required", "optional", "none"},
}
REQUIRED_FIELDS = ["category", "mode_required", "writes_external", "preflight", "experimental"]

path = pathlib.Path(sys.argv[1])
text = path.read_text(encoding="utf-8")

# Extract YAML frontmatter (between first two `---` lines)
m = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
if not m:
    print(json.dumps({"status": "skip", "reason": "no_frontmatter"}))
    sys.exit(0)

fm_text = m.group(1)
body = text[m.end():]

# Detect coo_twin block. Cheap parser: look for `^coo_twin:` then collect
# indented key: value lines until a non-indented line.
ct_match = re.search(r"^coo_twin:\s*\n((?:[ \t]+.*(?:\n|$))+)", fm_text, re.MULTILINE)
if not ct_match:
    print(json.dumps({"status": "skip", "reason": "not_coo_twin"}))
    sys.exit(0)

block = ct_match.group(1)
fields = {}
for line in block.splitlines():
    s = line.strip()
    if not s or s.startswith("#"):
        continue
    if ":" not in s:
        continue
    k, _, v = s.partition(":")
    v = v.strip()
    # strip inline comments
    v = re.sub(r"\s+#.*$", "", v).strip()
    # strip quotes
    if v.startswith(('"', "'")) and v.endswith(('"', "'")) and len(v) >= 2:
        v = v[1:-1]
    fields[k.strip()] = v

violations = []

# 1. Required fields present
for f in REQUIRED_FIELDS:
    if f not in fields:
        violations.append(f"missing_field:{f}")

# 2. Field values in allowed sets (skip if missing)
for f, allowed in ALLOWED.items():
    if f in fields and fields[f] not in allowed:
        violations.append(f"bad_value:{f}={fields[f]}")

# Booleans
for f in ("writes_external", "experimental", "phi_gate"):
    if f in fields and fields[f] not in ("true", "false"):
        violations.append(f"bad_bool:{f}={fields[f]}")

# 3. Step 0 / mode check present in body. Accept direct script call OR the
#    "## Step 0" marker (team skills reference the baseline skill's Step 0 by name).
if not re.search(r"(check_mode\.sh|preflight\.sh|Step\s*0|coo_mode\.yaml)", body):
    if fields.get("preflight") != "optional":
        violations.append("missing_mode_check")

# 4. Telemetry — accept script call OR the artifact name (team skills emit
#    custom telemetry rows inline rather than via the shared script).
if not re.search(r"(telemetry\.sh|_telemetry\.jsonl)", body):
    violations.append("missing_telemetry")

# 5. Trust gate language for external writers
if fields.get("writes_external") == "true":
    if not re.search(r"(trust gate|AskUserQuestion|approval|approve)", body, re.IGNORECASE):
        violations.append("missing_trust_gate")

# 6. sensitive info gate wiring
if fields.get("phi_gate") == "true":
    if "phi_scan.sh" not in body:
        violations.append("missing_phi_scan")

print(json.dumps({
    "status": "checked",
    "name": fields.get("category", "?") + "/" + path.parent.name,
    "skill": path.parent.name,
    "fields": fields,
    "violations": violations,
}))
PY
}

# --- Iterate targets ------------------------------------------------------
ALL_RESULTS="["
FIRST=1
N_TOTAL=0
N_COO=0
N_FAIL=0
FAIL_DETAIL=""

for f in "${TARGETS[@]}"; do
  N_TOTAL=$((N_TOTAL+1))
  RESULT="$(python_lint "$f")"

  STATUS="$(printf '%s' "$RESULT" | python -c "import sys,json; print(json.loads(sys.stdin.read()).get('status','?'))")"

  if [ "$STATUS" = "skip" ]; then
    if [ "$QUIET" -eq 0 ] && [ "$OUTPUT_JSON" -eq 0 ]; then
      printf '  skip   %s\n' "${f#${REPO_DIR}/}"
    fi
    continue
  fi

  N_COO=$((N_COO+1))
  N_VIOL="$(printf '%s' "$RESULT" | python -c "import sys,json; print(len(json.loads(sys.stdin.read()).get('violations',[])))")"

  if [ "$N_VIOL" -gt 0 ]; then
    N_FAIL=$((N_FAIL+1))
    VIOLS="$(printf '%s' "$RESULT" | python -c "import sys,json; print(','.join(json.loads(sys.stdin.read()).get('violations',[])))")"
    if [ "$OUTPUT_JSON" -eq 0 ]; then
      printf 'FAIL    %s\n        violations: %s\n' "${f#${REPO_DIR}/}" "$VIOLS"
    fi
    FAIL_DETAIL="${FAIL_DETAIL}${f#${REPO_DIR}/}: $VIOLS"$'\n'
  else
    if [ "$QUIET" -eq 0 ] && [ "$OUTPUT_JSON" -eq 0 ]; then
      printf '  ok     %s\n' "${f#${REPO_DIR}/}"
    fi
  fi

  if [ "$OUTPUT_JSON" -eq 1 ]; then
    [ "$FIRST" -eq 0 ] && ALL_RESULTS="${ALL_RESULTS},"
    ALL_RESULTS="${ALL_RESULTS}${RESULT}"
    FIRST=0
  fi
done

ALL_RESULTS="${ALL_RESULTS}]"

if [ "$OUTPUT_JSON" -eq 1 ]; then
  python - <<PY
import json
results = json.loads('''${ALL_RESULTS}''')
summary = {
  "total_skills": ${N_TOTAL},
  "coo_twin_skills": ${N_COO},
  "failures": ${N_FAIL},
  "results": results,
}
print(json.dumps(summary, indent=2))
PY
else
  echo ""
  printf 'skill_lint: %d total, %d COO Twin, %d failures\n' "$N_TOTAL" "$N_COO" "$N_FAIL"
fi

if [ "$N_FAIL" -gt 0 ]; then
  exit 1
fi

exit 0
