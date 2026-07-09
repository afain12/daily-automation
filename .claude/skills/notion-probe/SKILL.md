---
name: notion-probe
description: >-
  Read-only Notion workspace scanner. Enumerates databases visible to the
  integration, fetches their schemas, and scores each against four canonical
  roles (Master Tasks, Contact CRM, Activity Log, Meeting Notes). Writes a
  ranked report — never writes to Notion. Use as the diagnostic step before
  generic onboarding, or as a standalone workspace audit.
coo_twin:
  category: admin
  mode_required: any
  writes_external: false
  preflight: required
  experimental: false
---

# /notion-probe — Notion Workspace Scanner

You are auditing a Notion workspace to discover what's there. **Read-only.**
Never write to Notion. The output is a ranked report — confidence per
canonical role, with the supporting evidence — that downstream onboarding
(future `/setup`) will consume.

This is the load-bearing block of generic onboarding. If heuristics can
re-derive the operator's `config/sources.yaml` roles from schema alone, they'll
work for a stranger's workspace.

## Constants

```
REPO_DIR = "/path/to/daily-automation"
STATE    = "${REPO_DIR}/state"
TMP_DIR  = "${STATE}/tmp"
TODAY    = <current date in YYYY-MM-DD format>
RUN_ID   = "np-${TODAY//-/}-$(date +%H%M)"
REPORT   = "${STATE}/notion-probe-${TODAY}.md"
```

## Step 0: Mode Check (AAC GOVERNED)

```bash
MODE=$(scripts/check_mode.sh) || {
  echo "🛑 Agent is locked. Refusing to run /notion-probe."
  exit 0
}
```

`/notion-probe` is read-only, so it runs in every mode except `locked`. Record
the mode in the report header for traceability.

Capture `RUN_START_MS=$(date +%s%3N 2>/dev/null || python -c "import time; print(int(time.time()*1000))")` for telemetry.

## Step 1: Auth Check

Read `NOTION_API_TOKEN` from env. If missing or empty:

> ❌ `NOTION_API_TOKEN` not set. Add it to `.claude/settings.local.json`
> (env block) or export in your shell, then re-run.

Verify the token works with a 1-result search:

```bash
PING=$(curl -s --max-time 30 -X POST https://api.notion.com/v1/search \
  -H "Authorization: Bearer ${NOTION_API_TOKEN}" \
  -H "Notion-Version: 2025-09-03" \
  -H "Content-Type: application/json" \
  -d '{"page_size":1,"filter":{"value":"database","property":"object"}}')
```

If `$PING` contains `"object":"error"`, surface the error message and abort
(record telemetry status `auth_failed`).

## Step 2: Enumerate Data Sources

**Note on the 2025-09-03 API:** The searchable object is `data_source`, not
`database`. In the new model a "database" is a container that holds one or more
data sources; the data_source carries the schema + rows. `/v1/search` with
`filter.value = "data_source"` returns each data source with its full
`properties` map inline, so we don't need a second fetch.

```bash
mkdir -p "${TMP_DIR}"
DS_FILE="${TMP_DIR}/np-${RUN_ID}-datasources.jsonl"
: > "$DS_FILE"

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
  echo "$RESP" | jq -c '.results[]' >> "$DS_FILE"
  HAS_MORE=$(echo "$RESP" | jq -r '.has_more')
  NEXT=$(echo "$RESP" | jq -r '.next_cursor // empty')
  [ "$HAS_MORE" = "true" ] || break
done

N_DBS=$(wc -l < "$DS_FILE" | tr -d ' ')
```

If `N_DBS == 0`, render the **permission onboarding hint** and exit 0
(this is a setup gap, not an error — telemetry status `no_access`):

> 🚪 No databases visible to this integration.
>
> Notion only exposes databases that have been explicitly shared with the
> integration. To fix:
> 1. Open the database (or its parent page) in Notion.
> 2. Click `⋯` (top-right) → `Add connections` → pick your integration.
> 3. Re-run `/notion-probe`.
>
> Sharing a parent page grants access to every database nested inside it.

## Step 3: Normalize Schemas

Reshape each data source into a compact scorable form:

```bash
SCHEMA_FILE="${TMP_DIR}/np-${RUN_ID}-schemas.jsonl"

jq -c '{
  id,
  url,
  last_edited_time,
  title: (.title[0].plain_text // "Untitled"),
  properties: (.properties | to_entries | map({
    name: .key,
    type: .value.type,
    options: ((.value.select.options // .value.status.options // .value.multi_select.options // []) | map(.name)),
    relation_data_source_id: (.value.relation.data_source_id // null)
  }))
}' "$DS_FILE" > "$SCHEMA_FILE"
```

No second fetch needed — `/v1/search` already returned the full property map
for each data source.

## Step 4: Role Scoring

Pipe the schema JSONL through `scripts/notion_probe_score.py` to compute
per-role scores deterministically:

```bash
SCORED="${TMP_DIR}/np-${RUN_ID}-scored.json"
python scripts/notion_probe_score.py < "$SCHEMA_FILE" > "$SCORED"
```

The scorer applies four rubrics — Master Tasks, Contact CRM, Activity Log,
Meeting Notes — adding points for each matching indicator and dividing by
the role's max (100). See the module docstring + functions for the exact
rules. Confidence bands:

- `≥ 0.80` → **high** — propose this DB as the canonical match
- `0.50 – 0.79` → **medium** — show as alternative
- `0.30 – 0.49` → **low** — show only when no high/medium candidate exists
- `< 0.30` → omit from the role's section

A single DB can be a candidate for multiple roles. That's expected. The
scorer reports a score for every (DB, role) pair; the report renderer
filters by band.

**Rubric calibration.** If a role drops below 0.80 against the operator's
workspace on a future Notion API shape change, tune the rubric in
`scripts/notion_probe_score.py` — never by peeking at `config/sources.yaml`
during the calibration run.

## Step 5: Render Report

Read `$SCORED` (the array of `{id, title, scores: {role: {score, band, evidence}}}`)
and render markdown. For each role, group candidates by band (high → medium →
low), deduplicate by `(title, id-pair)` (Notion's 2025-09-03 model can return
two data sources for the same database container — note them as
"container has multiple data sources" rather than as separate candidates).

Write the report to `$REPORT` and echo to stdout. Template:

```markdown
# Notion Workspace Probe — {{TODAY}}

**Run ID:** {{RUN_ID}}
**Mode:** {{MODE}}
**Databases visible:** {{N_DBS}}

## Role Candidates

### Master Tasks
1. **"{{title}}"** — confidence **{{band}}** ({{score:.2f}})
   - id: `{{id}}`
   - Matched: {{comma-separated list of indicators that fired}}
   - Properties: {{name (type), name (type), ...}}
{{additional candidates}}

→ **Best guess:** "{{top.title}}" — confidence {{top.score:.2f}}
   (or: "→ **No high-confidence match** — manual mapping required")

### Contact CRM
...

### Activity Log
...

### Meeting Notes
...

## Unrelated Databases ({{count}})

Not a strong match for any canonical role (max score across roles < 0.30):

- "{{title}}" — `{{id}}`
- ...

## Next Steps

- Carry "Best guess" picks into `config/sources.yaml`, or wait for `/setup` to
  walk you through role mapping interactively.
- For any role with no high-confidence match:
  - Check whether the expected DB is shared with the integration (re-run probe).
  - Or plan to create it from template during `/setup`.
  - Or skip the feature that depends on it.
```

For the **best guess** per role: pick the highest-confidence candidate at
`≥ 0.80`. If none clears 0.80 but the top candidate is `≥ 0.50`, suggest it
with a "needs confirmation" tag. Below 0.50 → "No high-confidence match."

## Step 6: Telemetry

```bash
END_MS=$(date +%s%3N 2>/dev/null || python -c "import time; print(int(time.time()*1000))")
DURATION=$((END_MS - RUN_START_MS))

EXTRA=$(python -c "import json; print(json.dumps({
  'n_dbs': $N_DBS,
  'roles_high': $N_HIGH,
  'roles_medium': $N_MED,
  'mode': '$MODE'
}))")

scripts/telemetry.sh notion-probe "$RUN_ID" "$DURATION" "$STATUS" "$EXTRA"
```

Status values:
- `ok` — probe completed, ≥ 1 DB scanned
- `no_access` — auth ok but zero DBs visible
- `auth_failed` — 401/403 from Notion
- `error` — anything else

## Step 7: Cleanup

```bash
rm -f "${TMP_DIR}/np-${RUN_ID}-"*.jsonl
```

Keep the report at `${REPORT}`. Don't delete prior reports — they're a small
audit trail.

## Success Criterion

When run against the operator's workspace, the report must identify these four
canonical DBs at **high** confidence (≥ 0.80) **without reading
`config/sources.yaml`**:

- Master Tasks → "Master Tasks"
- Contact CRM → "Contact CRM"
- Activity Log → "Activity Log"
- Meeting Notes → "Meeting Notes"

If any role lands below 0.80, the rubric needs tuning before this skill is
useful for an unknown workspace. **Do not calibrate by peeking at
`sources.yaml` during a calibration run** — the test is whether heuristics
rediscover canonical roles from schema alone.
