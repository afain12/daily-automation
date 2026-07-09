---
name: notion-map
description: >-
  Property-role mapper for Notion. Consumes /notion-probe output, picks the
  best-guess DB per canonical role, and derives a draft `sources.yaml`-shaped
  mapping (status_field, date_field, assignee_field, workspace_field, etc.)
  using deterministic rules. Writes the proposal to
  state/notion-mapping-{date}.yaml for review. No Notion writes.
coo_twin:
  category: admin
  mode_required: any
  writes_external: false
  preflight: required
  experimental: false
---

# /notion-map — Property-Role Mapper

You are deriving the **field mapping** layer of generic onboarding. The probe
told us "this DB looks like Master Tasks at 0.92 confidence"; this skill says
"and its Status field is called `Status`, its Due date is called `Due`, its
Assignee is `Owner`, its Workspace bucket is `Category`."

Read-only with respect to Notion. Writes a single local YAML proposal.

## Constants

```
REPO_DIR = "/path/to/daily-automation"
STATE    = "${REPO_DIR}/state"
TMP_DIR  = "${STATE}/tmp"
TODAY    = <current date in YYYY-MM-DD format>
RUN_ID   = "nm-${TODAY//-/}-$(date +%H%M)"
OUT      = "${STATE}/notion-mapping-${TODAY}.yaml"
```

## Step 0: Mode Check

```bash
MODE=$(scripts/check_mode.sh) || { echo "🛑 Locked"; exit 0; }
```

Runs in any mode except `locked` (read-only with respect to Notion).
Capture `RUN_START_MS` for telemetry.

## Step 1: Locate Probe Output

This skill consumes `/notion-probe`'s output. Look for the most recent
`${STATE}/notion-probe-*.md` report and its sibling scored JSON. If none
exists or the latest is > 24h old, run `/notion-probe` first, then continue.

The scorer also needs the normalized schema JSONL. The probe leaves it at
`${TMP_DIR}/np-*-schemas.jsonl` but cleans up after itself in Step 7. So
re-pull schemas now (cheaper than re-running the whole probe):

```bash
mkdir -p "$TMP_DIR"
SCHEMA_FILE="${TMP_DIR}/${RUN_ID}-schemas.jsonl"
: > "$SCHEMA_FILE"

NEXT=""
while : ; do
  if [ -z "$NEXT" ]; then
    BODY='{"page_size":100,"filter":{"value":"data_source","property":"object"}}'
  else
    BODY=$(printf '{"page_size":100,"filter":{"value":"data_source","property":"object"},"start_cursor":"%s"}' "$NEXT")
  fi
  RESP=$(curl -s --max-time 30 -X POST https://api.notion.com/v1/search \
    -H "Authorization: Bearer ${NOTION_API_TOKEN}" \
    -H "Notion-Version: 2025-09-03" \
    -H "Content-Type: application/json" \
    -d "$BODY")
  echo "$RESP" | jq -c '.results[] | {
    id, url, last_edited_time,
    title: (.title[0].plain_text // "Untitled"),
    properties: (.properties | to_entries | map({
      name: .key,
      type: .value.type,
      options: ((.value.select.options // .value.status.options // .value.multi_select.options // []) | map(.name)),
      relation_data_source_id: (.value.relation.data_source_id // null)
    }))
  }' >> "$SCHEMA_FILE"
  HAS_MORE=$(echo "$RESP" | jq -r '.has_more')
  NEXT=$(echo "$RESP" | jq -r '.next_cursor // empty')
  [ "$HAS_MORE" = "true" ] || break
done
```

## Step 2: Pick Role Candidates from the Probe Report

For each canonical role, pick the top-confidence candidate at `≥ 0.80` (the
probe's "Best guess"). Skip any role with no high-confidence match — those
need either template install or manual mapping during `/setup`.

Parse the probe report (markdown) OR re-score in-process by piping
`$SCHEMA_FILE` through `scripts/notion_probe_score.py`. The in-process route
is more robust:

```bash
SCORED="${TMP_DIR}/${RUN_ID}-scored.json"
python scripts/notion_probe_score.py < "$SCHEMA_FILE" > "$SCORED"

# Extract best-guess assignments (highest score per role, gated at 0.80)
ASSIGNMENTS=$(python - <<'PY'
import json, sys
with open("'"$SCORED"'") as f:
    data = json.load(f)
out = []
for role in ["master_tasks", "contact_crm", "activity_log", "meeting_notes"]:
    ranked = sorted(data, key=lambda d: -d["scores"][role]["score"])
    if ranked and ranked[0]["scores"][role]["score"] >= 0.80:
        out.append(f'{role}={ranked[0]["id"]}')
print(" ".join(out))
PY
)
```

If `ASSIGNMENTS` is empty, surface a warning and exit with status
`no_candidates` — there's nothing to map.

## Step 3: Derive Field Mappings

```bash
MAPPING_JSON="${TMP_DIR}/${RUN_ID}-mapping.json"
python scripts/notion_field_map.py --schemas "$SCHEMA_FILE" $ASSIGNMENTS > "$MAPPING_JSON"
```

`notion_field_map.py` applies deterministic rules per role:

- **Master Tasks**: status/date/assignee/workspace fields + status option
  buckets (done/in-progress/waiting/not-started) derived from the `status`
  or `select` property's option names against canonical word sets.
- **Contact CRM**: stage/last_contact/next_step/workspace fields.
- **Activity Log**: type/date/outcome/next_action/workspace fields.
- **Meeting Notes**: title/date/summary/attendees/workspace + related-tasks
  relation (matched against the Master Tasks data source id from Step 2).

For ambiguous `select` properties (a DB might have both `Workspace` and
`Category` selects), the scanner prefers more specific keyword matches in
priority order: `workspace > department > project > category > area`. See
`scripts/notion_field_map.py :: find_prop` for the rule.

## Step 4: Render YAML Proposal

Write `$OUT` in the same shape as `config/sources.yaml :: notion_databases`,
with one block per role that landed a high-confidence assignment:

```yaml
# Notion mapping proposal — {{TODAY}}
# Generated by /notion-map from probe run {{RUN_ID}}.
# Review against your actual workspace before adopting into config/sources.yaml.

notion_databases:
  - name: "Master Tasks"
    data_source: "collection://528d24b8-..."
    status_field: "Status"
    status_done_values: ["Done"]
    status_in_progress_values: ["In progress"]
    status_waiting_values: ["Waiting"]
    status_not_started_values: ["Not started"]
    date_field: "Due"
    assignee_field: "Assignee"
    workspace_field: "Workspace"
    # Detected workspace option values — map these to your streams during /setup:
    # ["Operations", "Sales", "Product", "Product", "Other"]
    last_activity_field: "Last Activity"
    updated_field: "Updated"

  - name: "Contact CRM"
    ...
```

Convert `notion_field_map.py`'s JSON output to YAML inline (use Python
`yaml.safe_dump`, fall back to manual rendering if `pyyaml` is missing —
the project's `state/coo_mode.yaml` does this manually if needed).

For each role's `workspace_values_raw` / `stage_options_raw` / `type_values_raw`
arrays from the mapper, render them as a YAML comment above the field — they
are seed data for the upcoming `/setup` stream-mapping step, not authoritative
config values yet.

## Step 5: Trust Gate

Print a summary to stdout:

```
Notion field mapping proposal — {{TODAY}}
Roles mapped: {{N_ROLES}} / 4

  Master Tasks  → "Master Tasks"   (10 fields)
  Contact CRM  → "Contact CRM"   ( 4 fields)
  Activity Log  → "Activity Log"   ( 5 fields)
  Meeting Notes → "Meeting Notes"  ( 6 fields)

Proposal written to: state/notion-mapping-{{TODAY}}.yaml

Next steps:
  - Open the file, review each field name.
  - If anything looks wrong, edit and re-run.
  - When /setup ships, it will read this file as the field-mapping seed.
```

No further interaction. The file IS the trust-gate artifact. The user reviews
on disk and either lives with it or hand-edits.

## Step 6: Telemetry

```bash
END_MS=$(date +%s%3N 2>/dev/null || python -c "import time; print(int(time.time()*1000))")
DURATION=$((END_MS - RUN_START_MS))

EXTRA=$(python -c "import json; print(json.dumps({
  'n_roles_mapped': $N_ROLES,
  'n_dbs_probed': $N_DBS,
  'mode': '$MODE',
  'out_file': '$OUT'
}))")

scripts/telemetry.sh notion-map "$RUN_ID" "$DURATION" "$STATUS" "$EXTRA"
```

Status values:
- `ok` — ≥ 1 role mapped
- `no_candidates` — probe ran but no role cleared 0.80
- `auth_failed` / `error` — as in /notion-probe

## Step 7: Cleanup

```bash
rm -f "${TMP_DIR}/${RUN_ID}-"*
```

Keep `$OUT`. Don't delete prior mappings.

## Success Criterion

Run against the operator's workspace. The proposal at `state/notion-mapping-{TODAY}.yaml`
must match `config/sources.yaml :: notion_databases` field-for-field for the
4 canonical DBs:

- Master Tasks: status_field, status_done_values, status_in_progress_values,
  status_waiting_values, status_not_started_values, date_field, assignee_field,
  workspace_field, last_activity_field, updated_field
- Contact CRM: stage_field, last_contact_field, next_step_field, workspace_field
- Activity Log: type_field, date_field, outcome_field, next_action_field, workspace_field
- Meeting Notes: title_field, date_field, summary_field, attendees_field,
  workspace_field, related_tasks_field

If any field deviates, fix the rule in `notion_field_map.py` — never hand-edit
the proposal to make it match (that defeats the calibration).
