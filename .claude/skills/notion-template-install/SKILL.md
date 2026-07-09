---
name: notion-template-install
description: >-
  Bootstrap an empty Notion workspace with the four canonical COO Twin
  databases (Master Tasks, Contact CRM, Activity Log, Meeting Notes) from
  version-controlled JSON templates. Creates new data sources under a
  user-picked parent page, wires the cross-DB relations correctly, and writes
  a {role: data_source_id} map that /notion-map consumes directly. Trust-gated
  external write — refuses in `observe` and `locked` modes.
coo_twin:
  category: admin
  mode_required: draft+    # refuses in observe and locked
  writes_external: true
  preflight: required
  experimental: false
---

# /notion-template-install — Bootstrap Notion DBs from Templates

You are installing the four canonical Notion databases for a fresh workspace.
This is the **one external-write skill** in the discovery chain
(`/notion-probe` → `/notion-template-install` → `/notion-map`). After it runs,
`/notion-probe` should rediscover each created DB at ≥ 0.80 confidence for its
target role.

Templates live at `templates/notion/*.json` and are version-controlled. The
installer fills in the `parent` field at run time and substitutes the
master-tasks data source id into the `Related Tasks` relations on Contact CRM
and Meeting Notes.

## Constants

```
REPO_DIR    = "/path/to/daily-automation"
STATE       = "${REPO_DIR}/state"
TMP_DIR     = "${STATE}/tmp"
TPL_DIR     = "${REPO_DIR}/templates/notion"
TODAY       = <current date in YYYY-MM-DD format>
RUN_ID      = "nti-${TODAY//-/}-$(date +%H%M)"
OUT         = "${STATE}/notion-template-install-${TODAY}.yaml"
ORDER       = ["master_tasks", "contact_crm", "activity_log", "meeting_notes"]
```

Roles → template files:

| role             | template file                       | depends on       |
|------------------|-------------------------------------|------------------|
| `master_tasks`   | `templates/notion/master_tasks.json` | —                |
| `contact_crm`   | `templates/notion/contact_crm.json` | `master_tasks`   |
| `activity_log`   | `templates/notion/activity_log.json` | —                |
| `meeting_notes`  | `templates/notion/meeting_notes.json`| `master_tasks`   |

**master_tasks MUST be created first** — Contact CRM and Meeting Notes carry
relations to it. The templates use the literal placeholder string
`{{MASTER_TASKS_DS_ID}}` inside the `relation.data_source_id` field; the
installer substitutes it at Step 4. If `master_tasks` is not in the user's
selection but `contact_crm` or `meeting_notes` is, abort with a clear error —
the relations cannot be wired and the dependent DBs would score lower against
/notion-probe.

## Step 0: Mode Check (AAC GOVERNED) + Write Refusal

```bash
MODE=$(scripts/check_mode.sh) || {
  echo "🛑 Agent is locked. Refusing to run /notion-template-install."
  exit 0
}

case "$MODE" in
  observe|locked)
    echo "🛑 Mode is '$MODE'. /notion-template-install writes to Notion and is not"
    echo "   permitted in this mode. Flip state/coo_mode.yaml to 'draft' or higher."
    # Telemetry: status=aborted, extra={reason:"mode_refused"}
    exit 0
    ;;
  draft|approved|auto)
    ;;
  *)
    echo "🛑 Unknown mode '$MODE'. Refusing for safety."
    exit 0
    ;;
esac
```

Capture `RUN_START_MS=$(date +%s%3N 2>/dev/null || python -c "import time; print(int(time.time()*1000))")` for telemetry.

`draft` is the standard path — the trust gate at Step 3 enforces explicit
confirmation. `approved` and `auto` still go through the trust gate; this is a
one-time, schema-shaping operation and the cost of an accidental run is high.

## Step 1: Auth + Parent Page Selection

Read `NOTION_API_TOKEN` from env. Abort with the standard auth message if
missing or if a 1-row search returns `"object":"error"` (telemetry status
`auth_failed`).

Then ask the user where the new DBs should live. **Plain-text prompt** — do
NOT use AskUserQuestion (the auto-mode classifier can't see those answers —
see `memory/feedback_automode_trust_gate.md`).

Offer two paths:

```
Where should the new databases live?

  (A) Paste a Notion page ID — copy the URL of the destination page,
      grab the 32-char hex at the end (with or without dashes).

  (B) Type 'list' to see the 10 most-recently-edited pages this integration
      can access; I'll number them.

Reply with the page ID, or 'list'.
```

If user replies `list`, call `/v1/search` for pages and print a numbered list:

```bash
RESP=$(curl -s --max-time 30 -X POST https://api.notion.com/v1/search \
  -H "Authorization: Bearer ${NOTION_API_TOKEN}" \
  -H "Notion-Version: 2025-09-03" \
  -H "Content-Type: application/json" \
  -d '{
    "page_size": 10,
    "filter": {"value": "page", "property": "object"},
    "sort": {"direction": "descending", "timestamp": "last_edited_time"}
  }')

echo "$RESP" | jq -r '.results[] | "  \(.id)  \(.properties | to_entries | map(select(.value.type=="title")) | first.value.title[0].plain_text // "Untitled")  (\(.last_edited_time))"' | nl -ba
```

Ask the user to reply with a row number or paste a page ID directly. Validate
the chosen `PARENT_PAGE_ID` matches `^[a-f0-9-]{32,36}$`. If invalid, re-prompt.

Verify the integration has write access by GETting the page:

```bash
PROBE=$(curl -s --max-time 30 -X GET "https://api.notion.com/v1/pages/${PARENT_PAGE_ID}" \
  -H "Authorization: Bearer ${NOTION_API_TOKEN}" \
  -H "Notion-Version: 2025-09-03")
```

If `$PROBE` contains `"object":"error"`, surface the message and abort with
status `auth_failed` (most likely the page wasn't shared with the integration).

## Step 2: Select Which Templates to Install

Plain-text prompt:

```
Which databases should I create? (default: all 4)

  1. Master Tasks   — canonical tasks DB
  2. Contact CRM   — contacts / pipeline (depends on Master Tasks)
  3. Activity Log   — decisions + outcomes
  4. Meeting Notes  — meeting records (depends on Master Tasks)

Reply with a comma-separated list (e.g. '1,3') or 'all'. Default: all.
```

Resolve to a `SELECTED` list of role keys in the canonical `ORDER`. If the
user picked `contact_crm` or `meeting_notes` WITHOUT `master_tasks`, refuse:

```
🛑 Cannot install 'contact_crm' or 'meeting_notes' without 'master_tasks' —
   they carry relations to it. Add master_tasks to your selection or pick
   only activity_log + master_tasks separately.
```

## Step 3: Trust Gate (AAC GATED)

Print a structured plan and require explicit text confirmation. This is the
hard gate; AskUserQuestion is NOT acceptable here.

```
About to create N databases under parent page <PARENT_PAGE_ID>:

  ┌─────────────────────────────────────────────────────────────────────────┐
  │ 1. Master Tasks                                                         │
  │    properties: Task (title), Status (status: Not started / In progress  │
  │                / Waiting / Done), Due (date), Assignee (people),        │
  │                Workspace (select), Priority (select), Last Activity     │
  │                (rich_text), Notes (rich_text)                           │
  │                                                                         │
  │ 2. Contact CRM                                                         │
  │    properties: Name (title), Email, Phone, Stage (select),              │
  │                Workspace (select), Last Contact (date), Next Step       │
  │                (rich_text), Related Tasks (relation → Master Tasks),    │
  │                Notes (rich_text)                                        │
  │                                                                         │
  │ 3. Activity Log                                                         │
  │    properties: Entry (title), Date, Type (select), Workspace (select),  │
  │                Outcome (rich_text), Next Action (rich_text),            │
  │                Particsalesnts (people), Tags (multi_select)               │
  │                                                                         │
  │ 4. Meeting Notes                                                        │
  │    properties: Meeting (title), Date, Attendees (people), External      │
  │                Attendees (rich_text), Workspace (select), Summary       │
  │                (rich_text), Related Tasks (relation → Master Tasks),    │
  │                Source (select)                                          │
  └─────────────────────────────────────────────────────────────────────────┘

This is a REAL external write to your Notion workspace.

Type INSTALL exactly to proceed. Anything else aborts.
```

Read user reply. If `$REPLY != "INSTALL"` (exact case-sensitive match),
abort with status `aborted` and exit 0 — no writes made, no leftover state.

## Step 4: Create Data Sources (in dependency order)

Process `SELECTED` in `ORDER`. For each role:

```bash
TPL_FILE="${TPL_DIR}/${role}.json"
PAYLOAD_FILE="${TMP_DIR}/nti-${RUN_ID}-${role}.json"

# Substitute master_tasks placeholder + inject parent.
# MASTER_TASKS_DS_ID is set after the master_tasks POST; empty before then.
python - <<PY > "$PAYLOAD_FILE"
import json, os
tpl = json.load(open("$TPL_FILE", encoding="utf-8"))
tpl["parent"] = {"type": "page_id", "page_id": "$PARENT_PAGE_ID"}
mt = os.environ.get("MASTER_TASKS_DS_ID", "")
def sub(node):
    if isinstance(node, dict):
        for k, v in list(node.items()):
            if isinstance(v, str) and v == "{{MASTER_TASKS_DS_ID}}":
                if not mt:
                    raise SystemExit("MASTER_TASKS_DS_ID not yet set — order bug")
                node[k] = mt
            else:
                sub(v)
    elif isinstance(node, list):
        for item in node:
            sub(item)
sub(tpl)
json.dump(tpl, __import__("sys").stdout, ensure_ascii=False)
PY
```

Generate the action_id from the template body + parent:

```bash
PAYLOAD_HASH_INPUT="${role}|${PARENT_PAGE_ID}|$(python -c "import hashlib,sys; print(hashlib.sha256(open('$TPL_FILE','rb').read()).hexdigest()[:16])")"
AID=$(scripts/action_id.sh generate notion-template-install "${role}" "${TODAY}" "${PAYLOAD_HASH_INPUT}")

if scripts/action_id.sh check "$AID"; then
  echo "  ↪︎ ${role}: already installed (action_id ${AID}) — skipping"
  DS_ID=$(python -c "import json; print(json.load(open('.context/applied/${AID//:/_}.json'))['notion_data_source_id'])")
else
  RESP=$(curl -s --max-time 60 -X POST https://api.notion.com/v1/data_sources \
    -H "Authorization: Bearer ${NOTION_API_TOKEN}" \
    -H "Notion-Version: 2025-09-03" \
    -H "Content-Type: application/json" \
    --data @"$PAYLOAD_FILE")

  if echo "$RESP" | jq -e '.object == "error"' >/dev/null 2>&1; then
    ERR_MSG=$(echo "$RESP" | jq -r '.message')
    echo "  ❌ ${role}: ${ERR_MSG}"
    FAILED+=("$role")
    continue
  fi

  DS_ID=$(echo "$RESP" | jq -r '.id')
  scripts/action_id.sh stamp "$AID" "$(printf '{"notion_data_source_id":"%s","role":"%s","parent_page_id":"%s"}' "$DS_ID" "$role" "$PARENT_PAGE_ID")"
  echo "  ✓ ${role}: ${DS_ID}"
fi

# If this was master_tasks, export the id for downstream substitution.
if [ "$role" = "master_tasks" ]; then
  export MASTER_TASKS_DS_ID="$DS_ID"
fi

RESULTS+=("${role}=${DS_ID}")
```

**Failure semantics.** If a POST fails (network, 4xx, 5xx) the action_id is
NOT stamped — re-running the skill will retry that role while skipping the
ones that succeeded. Partial success is reported in Step 5; status is
`partial` if any role failed.

If `master_tasks` itself fails, abort the remaining work — there's no id to
substitute into the dependent templates. Telemetry status `partial`.

## Step 5: Write Role → Data-Source Map

Write the install map to `$OUT` so `/notion-map` can immediately read it:

```yaml
# Notion template install — {{TODAY}}
# Generated by /notion-template-install run {{RUN_ID}}.
# Pass this map directly to /notion-map (it skips the discovery step when
# the install file is newer than the latest probe report).

parent_page_id: "{{PARENT_PAGE_ID}}"
installed_at: "{{TS_ISO}}"
run_id: "{{RUN_ID}}"

data_sources:
  master_tasks: "{{ds_id}}"
  contact_crm: "{{ds_id}}"
  activity_log: "{{ds_id}}"
  meeting_notes: "{{ds_id}}"
```

Only include roles that successfully installed. Roles that failed get
written as commented-out lines with the error message so the user can see
what's missing without parsing telemetry.

Echo the file path + a one-line summary:

```
✓ Wrote state/notion-template-install-{{TODAY}}.yaml ({{N_OK}} of {{N_SELECTED}} roles)

Next: run /notion-map to derive field mappings (it will pick this file up
automatically), or /notion-probe to verify each new DB scores ≥ 0.80 for
its target role.
```

## Step 6: Telemetry (AAC OBSERVED)

```bash
END_MS=$(date +%s%3N 2>/dev/null || python -c "import time; print(int(time.time()*1000))")
DURATION=$((END_MS - RUN_START_MS))

EXTRA=$(python -c "import json; print(json.dumps({
  'mode': '$MODE',
  'parent_page_id': '$PARENT_PAGE_ID',
  'roles_selected': $N_SELECTED,
  'roles_ok': $N_OK,
  'roles_failed': $N_FAILED,
  'out_file': '$OUT'
}))")

scripts/telemetry.sh notion-template-install "$RUN_ID" "$DURATION" "$STATUS" "$EXTRA"
```

Status values:

| status         | meaning                                                       |
|----------------|---------------------------------------------------------------|
| `ok`           | all selected roles installed successfully                     |
| `partial`      | at least one role installed, at least one failed              |
| `aborted`      | user did not type INSTALL, or selection was empty             |
| `auth_failed`  | 401/403 from Notion (bad token, unshared page)                |
| `error`        | unexpected failure (network, parsing, etc.)                   |

## Step 7: Cleanup

```bash
rm -f "${TMP_DIR}/nti-${RUN_ID}-"*.json
```

Keep `$OUT` and the stamped action_ids in `.context/applied/`. They are the
audit trail and the idempotency layer.

## Success Criterion

After running against an empty workspace:

1. `state/notion-template-install-${TODAY}.yaml` exists with 4 data_source ids.
2. Running `/notion-probe` immediately afterwards scores each created DB at
   ≥ 0.80 confidence for its target role — Master Tasks ≈ 1.00, Contact CRM
   ≈ 1.00, Activity Log ≥ 0.80, Meeting Notes ≈ 1.00.
3. Re-running `/notion-template-install` with the same selection is a no-op
   (action_ids match; all roles skipped; status `ok`).

## Idempotency Model

The action_id for each role is

```
notion-template-install:{role}:{date}:{8-char-hash-of(role|parent|template-sha)}
```

If the user re-runs on the same day with the same parent + the same template
file content, the action_id collides and the existing data_source_id is reused
from `.context/applied/{action_id}.json`. Editing the template content (which
shifts the sha) yields a new action_id and a fresh POST — useful for schema
revisions during template development; safe in production because of the
trust gate.

## Why this exists

`/notion-probe` rediscovers canonical DBs. `/notion-map` derives field
mappings. Both presume the DBs already exist. For an empty workspace, this
installer is the missing link — and by making the templates the same artifact
that `/notion-probe` later scores ≥ 0.80, we get a closed loop:
install → probe → map → use. No hand-editing required.
