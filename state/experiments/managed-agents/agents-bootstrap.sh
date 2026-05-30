#!/usr/bin/env bash
# scripts/agents-bootstrap.sh — create Managed Agents from state/agents-roster.yaml.
#
# Reads the declarative roster, POSTs /v1/agents for each specialist, then
# creates the coordinator with multiagent.agents pinned to the returned
# specialist IDs. Idempotent: stamps action_ids via scripts/action_id.sh and
# skips agents already created.
#
# Usage:
#   scripts/agents-bootstrap.sh            # bootstrap all roster entries
#   scripts/agents-bootstrap.sh --dry-run  # print payloads without POSTing
#   scripts/agents-bootstrap.sh --rebuild  # ignore stamps; force recreate (new IDs)
#
# Prerequisites:
#   ANTHROPIC_API_KEY in .secrets/anthropic.env (mirrored to env per CLAUDE.md secrets pattern)
#   python3 with pyyaml (`pip install pyyaml`) — used for YAML parsing only
#   curl
#
# Output:
#   state/agents-bootstrap.lock.json — { "<name>": { "id": "agnt_…", "version": N } }
#   logs/_telemetry.jsonl row per run (skill=agents-bootstrap)
#   .context/applied/agents-bootstrap_*.json — one per created agent

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROSTER="${REPO_DIR}/state/agents-roster.yaml"
LOCK="${REPO_DIR}/state/agents-bootstrap.lock.json"
DATE="$(date -u +%Y-%m-%d)"
RUN_ID="bootstrap-$(date -u +%Y%m%dT%H%M%SZ)"
START_NS="$(date +%s%N 2>/dev/null || python -c 'import time;print(int(time.time()*1e9))')"

DRY_RUN=0
REBUILD=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --rebuild) REBUILD=1 ;;
    *) echo "unknown arg: $arg" >&2; exit 2 ;;
  esac
done

# Source secret. .secrets/anthropic.env is the canonical store per CLAUDE.md;
# the bash export pattern lives there.
if [ -f "${REPO_DIR}/.secrets/anthropic.env" ]; then
  # shellcheck disable=SC1091
  . "${REPO_DIR}/.secrets/anthropic.env"
fi
: "${ANTHROPIC_API_KEY:?ANTHROPIC_API_KEY not set — populate .secrets/anthropic.env}"

API="https://api.anthropic.com/v1/agents"
HDR_KEY="x-api-key: ${ANTHROPIC_API_KEY}"
HDR_VER="anthropic-version: 2023-06-01"
HDR_BETA="anthropic-beta: managed-agents-2026-04-01"
HDR_JSON="content-type: application/json"

mkdir -p "${REPO_DIR}/.context/applied" "${REPO_DIR}/state" "${REPO_DIR}/logs"
[ -f "${LOCK}" ] || echo '{}' > "${LOCK}"

# ----------------------------------------------------------------------------
# Helper: parse roster via python (avoids bash YAML parsing pain).
# Emits one TSV row per specialist + one row for the coordinator block.
# Columns: kind \t name \t json_payload
# ----------------------------------------------------------------------------
python_parse() {
  python - <<PY
import json, sys, yaml, pathlib
repo = pathlib.Path("${REPO_DIR}")
roster = yaml.safe_load((repo / "state" / "agents-roster.yaml").read_text())

def build_system(entry):
    prompt_path = repo / entry["system_prompt_file"]
    if not prompt_path.exists():
        return entry.get("pre_prompt", "")
    base = prompt_path.read_text(encoding="utf-8", errors="replace")
    return entry.get("pre_prompt", "") + "\n\n---\n\n" + base

for s in roster.get("specialists", []):
    payload = {
        "name": s["name"],
        "model": s["model"],
        "system": build_system(s),
        "tools": s.get("tools", []),
        # mcp_servers is informational in the roster; bootstrap leaves wiring
        # to a follow-up step (G7-MA step 1 surveys MCP coverage first).
    }
    print("specialist\t" + s["name"] + "\t" + json.dumps(payload, separators=(",", ":")))

c = roster["coordinator"]
coord_payload = {
    "name": c["name"],
    "model": c["model"],
    "system": c["system"],
    "tools": c.get("tools", []),
    # multiagent.agents is filled in below from the lock file after specialists
    # are created. This row carries only the base payload.
}
print("coordinator\t" + c["name"] + "\t" + json.dumps(coord_payload, separators=(",", ":")))
PY
}

# ----------------------------------------------------------------------------
# Helper: post one agent, return its ID. Stamps an action_id on success.
# ----------------------------------------------------------------------------
create_agent() {
  local name="$1"
  local payload="$2"

  # Idempotency: hash name+payload-shape. Re-running with identical roster no-ops.
  local aid
  aid="$(${REPO_DIR}/scripts/action_id.sh generate agents-bootstrap "${name}" "${DATE}" "${payload}")"

  if [ "${REBUILD}" -eq 0 ] && "${REPO_DIR}/scripts/action_id.sh" check "${aid}" 2>/dev/null; then
    echo "[skip] ${name} — already created (action_id=${aid})" >&2
    # Return cached ID from lock
    python -c "import json,sys; d=json.load(open('${LOCK}'));print(d.get('${name}',{}).get('id',''))"
    return 0
  fi

  if [ "${DRY_RUN}" -eq 1 ]; then
    echo "[dry-run] would POST ${name}:" >&2
    echo "${payload}" | python -m json.tool >&2
    echo ""
    return 0
  fi

  local response
  response="$(curl -fsS --max-time 60 "${API}" \
    -H "${HDR_KEY}" -H "${HDR_VER}" -H "${HDR_BETA}" -H "${HDR_JSON}" \
    -d "${payload}")" || {
      echo "[fail] POST ${name} failed" >&2
      return 1
    }

  local id version
  id="$(echo "${response}" | python -c 'import json,sys;print(json.load(sys.stdin).get("id",""))')"
  version="$(echo "${response}" | python -c 'import json,sys;print(json.load(sys.stdin).get("version",""))')"

  if [ -z "${id}" ]; then
    echo "[fail] ${name} — no id in response: ${response}" >&2
    return 1
  fi

  # Update lock file (in-place merge).
  python - <<PY
import json
lock = json.load(open("${LOCK}"))
lock["${name}"] = {"id": "${id}", "version": ${version:-null}}
json.dump(lock, open("${LOCK}", "w"), indent=2)
PY

  "${REPO_DIR}/scripts/action_id.sh" stamp "${aid}" "{\"agent_id\":\"${id}\",\"version\":${version:-null}}"
  echo "[ok] ${name} → ${id} (v${version})" >&2
  echo "${id}"
}

# ----------------------------------------------------------------------------
# Phase 1: create all specialists.
# ----------------------------------------------------------------------------
declare -a SPEC_IDS=()
COORD_PAYLOAD=""

while IFS=$'\t' read -r kind name payload; do
  case "${kind}" in
    specialist)
      id="$(create_agent "${name}" "${payload}")" || exit 1
      [ -n "${id}" ] && SPEC_IDS+=("${id}")
      ;;
    coordinator)
      COORD_PAYLOAD="${payload}"
      COORD_NAME="${name}"
      ;;
  esac
done < <(python_parse)

# ----------------------------------------------------------------------------
# Phase 2: create the coordinator with multiagent.agents pinned to specialist IDs.
# ----------------------------------------------------------------------------
if [ -z "${COORD_PAYLOAD}" ]; then
  echo "no coordinator in roster" >&2
  exit 1
fi

FINAL_COORD="$(python - <<PY
import json
base = json.loads('''${COORD_PAYLOAD}''')
lock = json.load(open("${LOCK}"))
roster_specs = ["start-day", "capture-meeting", "end-day", "sync-sweep"]
agents = []
for n in roster_specs:
    entry = lock.get(n)
    if not entry or not entry.get("id"):
        continue
    pin = {"type": "agent", "id": entry["id"]}
    if entry.get("version"):
        pin["version"] = entry["version"]
    agents.append(pin)
base["multiagent"] = {"type": "coordinator", "agents": agents}
print(json.dumps(base, separators=(",", ":")))
PY
)"

create_agent "${COORD_NAME}" "${FINAL_COORD}" > /dev/null

# ----------------------------------------------------------------------------
# Telemetry.
# ----------------------------------------------------------------------------
END_NS="$(date +%s%N 2>/dev/null || python -c 'import time;print(int(time.time()*1e9))')"
DURATION_MS=$(( (END_NS - START_NS) / 1000000 ))
SPEC_COUNT="${#SPEC_IDS[@]}"
EXTRA="$(printf '{"specialist_count":%d,"dry_run":%d,"rebuild":%d}' "${SPEC_COUNT}" "${DRY_RUN}" "${REBUILD}")"
"${REPO_DIR}/scripts/telemetry.sh" agents-bootstrap "${RUN_ID}" "${DURATION_MS}" ok "${EXTRA}"

echo ""
echo "Bootstrap complete. Lock file: ${LOCK}"
echo "Next step: register webhook endpoint per scripts/webhook-handler.py docstring."
