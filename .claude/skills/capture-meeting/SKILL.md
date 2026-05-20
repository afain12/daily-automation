---
name: capture-meeting
description: >-
  Meeting note splitter: takes raw meeting notes and intelligently routes them.
  Action items go to Notion (Master Tasks), insights go to Obsidian (notes/),
  follow-up meetings go to Google Calendar, decisions go to Notion (Activity Log)
  with an Obsidian link. Provider updates go to CRM. Trust gate before any writes.
coo_twin:
  category: capture
  mode_required: any
  writes_external: true
  preflight: required
  phi_gate: true
  experimental: false
---

# /capture-meeting — Meeting Note Splitter

You are acting as Aaron's Chief of Staff. Your job is to take raw meeting notes,
parse them into structured categories, and route each item to the right system.

**Read-first, write-on-approval.** Show all proposed routing at a trust gate.
Each routing action is individually approvable.

## Constants

```
REPO_DIR = "C:/Users/aaron/daily-automation"
CONFIG   = "${REPO_DIR}/config/sources.yaml"
ROUTING  = "${REPO_DIR}/config/routing-rules.yaml"
LOGS_DIR = "${REPO_DIR}/logs"
VAULT    = "${REPO_DIR}/vault"
TODAY    = <current date in YYYY-MM-DD format>
RUN_ID   = "cm-${TODAY//-/}-$(date +%H%M%S)"
```

## Step 0: Mode Check (AAC GOVERNED)

```bash
MODE=$(scripts/check_mode.sh) || {
  echo "🛑 Agent is locked. /capture-meeting refuses to run."
  exit 0
}
```

- `locked` → refuse.
- `observe` → set `SKIP_WRITES=1`; run all parsing + display the routing plan, but skip every Step 6 write.
- `draft` (default) → standard trust gate.
- `approved` → if every routed item's action_id has a prefix in `approved_action_prefixes`, auto-approve at Step 5. Otherwise gate normally.

Capture `RUN_START_MS` for Step 8 telemetry.

## Step 1: Load Configuration

Read both config files:
- `${CONFIG}` — for Notion database IDs, field mappings, business keywords, vault path
- `${ROUTING}` — for routing rules, indicators, and destinations

## Step 2: Collect Meeting Notes

Use AskUserQuestion to ask:

**"How would you like to provide the meeting notes?"**

Options:
- **A) Paste them now** — User pastes raw notes in the next message
- **B) From a file** — User provides a file path to read
- **C) From today's meetings folder** — Check `${VAULT}/meetings/` for today's files
- **D) From a Granola → Notion recap page** — User provides a Notion page URL or page ID
  from the **Meeting Notes** database (data_source `22ba3158-59b4-804d-9c1c-000b9fad40ae`).
  This is the standard path when Granola has already synced a meeting to Notion.

If option A: wait for the user to paste notes, then proceed.
If option B: read the file at the provided path.
If option C: use Glob to find files in `${VAULT}/meetings/` matching today's date
  pattern. If multiple found, ask the user which one to process.
If option D: extract the page ID from the URL (last 32 hex chars, with or without
  hyphens), then GET the page to retrieve metadata and the page body blocks:

  ```bash
  # Page properties (title, Date, Workspace, Attendees, existing Related Tasks)
  curl -s --max-time 60 "https://api.notion.com/v1/pages/${PAGE_ID}" \
    -H "Authorization: Bearer $NOTION_API_TOKEN" \
    -H "Notion-Version: 2025-09-03"

  # Page body — Granola writes its summary + transcript as block children
  curl -s --max-time 60 "https://api.notion.com/v1/blocks/${PAGE_ID}/children?page_size=100" \
    -H "Authorization: Bearer $NOTION_API_TOKEN" \
    -H "Notion-Version: 2025-09-03"
  ```

  Concatenate the `Summary` rich_text property + every text-bearing child block
  (paragraph, bulleted_list_item, numbered_list_item, heading_*, quote, callout,
  to_do) into a single notes string, then proceed as if the user had pasted it.
  Remember the source `PAGE_ID` and existing `Workspace` value for Step 7
  (Granola back-link + workspace tagging).

## Step 2.5: PHI Input Gate (AAC GATED — input gate)

Before any LLM parsing, scan the raw notes for PHI markers. This is the input gate
required by AAC §2.3 (GATED). It does NOT make the system HIPAA-compliant; it
stops the dumbest leakage (an accidentally pasted SSN, DOB, or MRN).

```bash
printf '%s' "${RAW_NOTES}" | scripts/phi_scan.sh
PHI_EXIT=$?
```

- `PHI_EXIT == 0` → clean, proceed.
- `PHI_EXIT == 1` → PHI markers detected. **Refuse to parse.** Display the
  line numbers + sanitized snippets from phi_scan.sh stderr. Ask Aaron to
  paste cleaned notes (with identifiers removed or replaced by placeholders
  like `[PATIENT_ID]`). Do NOT proceed to Step 3 until clean input is received.
- `PHI_EXIT == 2` → read error (empty input). Refuse and ask for actual notes.

Log every PHI refusal in `logs/_phi_refusals.jsonl` (append-only) with timestamp,
RUN_ID, and the labels (`SSN | DOB | MRN | …`) detected — NOT the raw matched text.
This is the GOVERNED hard-refuse audit trail (AAC §2.5).

## Step 3: Collect Meeting Context

Use AskUserQuestion to ask:

**"What's the context for this meeting?"**

Options:
- **Lab (Lincoln Reference)** — lab business meeting
- **United IPA** — IPA business meeting
- **Nestmate** — Nestmate meeting
- **Dock Pro / Cardio Pro** — Dock Pro or Cardio Pro meeting

This sets the `business_tag` for all items extracted from this meeting.
The user can also type a custom context.

Also ask: **"Who was in this meeting?"** (free text — names of attendees).
Store as `attendees` for use in action item assignment.

## Step 4: Parse and Categorize

Read the routing rules from `${ROUTING}`. For each paragraph, sentence, or
bullet point in the raw notes, determine which category it belongs to by
matching against the indicator patterns defined in the routing config.

### Categories (from routing-rules.yaml):

**Action Items** → Notion Master Tasks
- Indicators: "action", "TODO", "deadline", "by [date]", "assigned to",
  "follow up with", "need to", "should", "will do", "next step"
- Extract: task title, owner (if mentioned), due date (if mentioned)
- Auto-set: Status = "Not started", Workspace = inferred from business_tag

**Insights** → Obsidian notes/
- Indicators: "idea", "insight", "pain point", "remember", "key takeaway",
  "interesting", "observation", "learned", "realization"
- Extract: the insight text, relevant tags

**Follow-ups** → Google Calendar
- Indicators: "schedule", "meet again", "follow-up meeting",
  "next steps meeting", "reconvene", "circle back"
- Extract: who to meet with, suggested timeframe, topic

**Decisions** → Notion Activity Log (single source of truth)
- Indicators: "decided", "agreed", "approved", "we will", "going with",
  "confirmed", "finalized"
- Extract: what was decided, who decided
- Also: Obsidian gets a wikilink reference, not a duplicate

**Provider Updates** → Notion Provider CRM
- Indicators: "spoke with Dr", "provider said", "practice update",
  "credentialing", "panel size", "NPI"
- Extract: provider name, update details, next step
- Action: update existing CRM record (Last Contact, Next Step fields)

### Parsing Rules (AAC BOUNDED + GROUNDED, revised 2026-05-18):

- **Pick ONE primary category per item.** Do not duplicate the same line across
  multiple categories. If a sentence reads like both ACTION and DECISION, pick the
  one with the stronger indicator and surface the alternative as a `secondary_hint`
  for that item only. (Previous behavior over-routed and inflated trust-gate load.)
- **Assign a confidence score 0.0–1.0** to every categorization, based on indicator
  strength:
  - 0.95+ : explicit verb match ("decided", "TODO", "follow up with") AND clear owner/date OR clear subject
  - 0.80  : strong verb match, partial owner/date
  - 0.65  : single weak indicator OR ambiguous owner
  - < 0.65: low confidence — see threshold rule below
- **Confidence threshold rule:** any item with confidence < 0.70 routes to the
  **Uncategorized** bucket regardless of which indicators matched. Aaron classifies
  it manually at the trust gate. This collapses cognitive load on borderline items.
- **Carry source citation on every item:**
  ```
  {
    "category": "ACTION",
    "confidence": 0.91,
    "source_line": 14,
    "source_text": "Tell Abos to follow up with Dr Remzy by Friday",
    "owner": "Abos",  "owner_resolved_from": "attendee match",
    "due": "2026-05-22", "due_resolved_from": "'by Friday' relative parse",
    "secondary_hint": null
  }
  ```
- Preserve the original text alongside the extracted structured fields.
- When an owner is mentioned, extract it. If no owner is mentioned, default to Aaron.
- Parse date references into ISO dates: "next Tuesday" → actual date,
  "by end of week" → that Friday's date, "ASAP" → today. Always record
  `due_resolved_from` so Aaron can spot misparses at the trust gate.

## Step 4.5: Idempotency Cache Check (AAC GATED — action gate)

For each parsed item, generate an `action_id` and check whether it has already
been applied in a prior /capture-meeting run (e.g. user re-ran on the same
Granola URL):

```bash
for ITEM_HASH in <each parsed item's stable hash>; do
  AID=$(scripts/action_id.sh generate capture-meeting "${RECAP_PAGE_ID_OR_MEETING_KEY}" "${TODAY}" "${ITEM_HASH}")
  if scripts/action_id.sh check "${AID}"; then
    # Already applied. Mark item as `skip_idempotent` — don't show at trust gate.
    echo "skip ${AID} (already applied in prior run)"
  else
    # Fresh item. Carry the AID forward to Step 5 trust gate display.
    item.action_id = "${AID}"
  fi
done
```

`ITEM_HASH` is a deterministic hash of the routed item's key fields (category +
source_text + owner + due). Re-running on the same meeting will regenerate the
same AID; if Step 6 succeeded last time and called `action_id.sh stamp`, the
re-run is a clean no-op for that item. This preserves the existing
"Re-running on the same meeting" edge case in Step 6a-3 but makes it explicit
and visible *before* the trust gate, not after the writes.

Items where `skip_idempotent == true` are listed at the bottom of the trust gate
display as `Skipped (already applied previously): N items`, with the option to
force-rerun if needed.

## Step 5: Present Trust Gate

Display a numbered routing plan grouped by destination. Every routable item now
shows **confidence** and **source line** alongside the destination (AAC GROUNDED):

```markdown
# Meeting Notes Routing — {meeting context}
Run: {RUN_ID} · Mode: {MODE} · Attendees: {attendees} · Date: {TODAY}

## Notion: Master Tasks ({count} items)
1. [ACTION conf:0.92] {task title}
   Owner: {name} (from: {owner_resolved_from}) · Due: {date} (from: {due_resolved_from}) · Workspace: {business}
   Source line {N}: "{source_text}"
   action_id: {capture-meeting:meeting-key:date:hash}
2. [ACTION conf:0.78] {task title}
   ...

## Notion: Activity Log ({count} items)
3. [DECISION conf:0.88] {what was decided}
   Source line {N}: "{source_text}"
   action_id: {…}

## Notion: Provider CRM ({count} items)
4. [PROVIDER conf:0.85] Update {provider name} — Last Contact: {date}, Next Step: {detail}
   Source line {N}: "{source_text}"
   action_id: {…}

## Obsidian: notes/ ({count} items)
5. [INSIGHT conf:0.81] {insight title} — Tags: #{business_tag}, #meeting
   Source line {N}: "{source_text}"

## Google Calendar ({count} items)
6. [FOLLOW-UP conf:0.79] {meeting topic} with {attendees} — Suggested: {timeframe}
   Source line {N}: "{source_text}"

## Obsidian Links (auto-created with decisions)
- Decision #3 will also be linked from Obsidian meeting note

## Uncategorized — needs Aaron's call ({count} items)
7. [conf:0.61] "{raw text}" — primary guess: ACTION, but low confidence. Possible alternatives: INSIGHT.
8. [conf:0.0]  "{raw text}" — no category matched.

## Skipped — already applied in prior run ({count} items)
- "{item}" — action_id matches .context/applied/. Use "force re-run" to override.
```

The visible `conf:` value + the `Source line N:` citation are load-bearing — they let
Aaron approve in seconds for high-confidence items and read carefully only on the
borderline ones.

Use AskUserQuestion:

**"Which items should I route? (Enter numbers, 'all', or 'none')"**

Options:
- **All items** — Route everything as shown
- **Select specific items** — User enters comma-separated numbers (e.g., "1,2,3,5")
- **Edit first** — User wants to modify categorization before routing
- **None — just save the notes** — Save raw notes to Obsidian meetings folder only

If "Edit first": ask which item numbers to re-categorize and what the new
category should be. Then re-display the updated routing plan.

## Step 6: Execute Approved Routing

Process each approved item by destination. Execute in this order:
1. Notion writes (tasks, decisions, CRM updates)
2. Google Calendar drafts
3. Obsidian notes
4. Meeting note file (always)

### 6a: Create Notion Master Tasks (parent + subtasks)

Master Tasks has two self-referential relation properties — `Parent Task` and
`Subtasks` (dual_property). Setting `Parent Task` on a child auto-populates
`Subtasks` on the parent. Use this to wrap every meeting's action items under
a single parent task, so Aaron sees `[Meeting] Docpro/Nestmate 2026-04-30` in
Master Tasks with each Granola action as an expandable subtask.

**Step 6a-1: Create the parent meeting task first.**

Title format: `[Meeting] <meeting name> <YYYY-MM-DD>`. Workspace = the
meeting's primary business tag (Aaron will see it in the right department
section of `/start-day`). If the source was Option D (Granola recap page),
also link `Related to Meeting Notes (Related Tasks)` to the recap page_id so
the parent task points back at the meeting.

```bash
curl -s -X POST "https://api.notion.com/v1/pages" \
  -H "Authorization: Bearer $NOTION_API_TOKEN" \
  -H "Notion-Version: 2025-09-03" \
  -H "Content-Type: application/json" \
  --max-time 60 \
  -d '{
    "parent": {"data_source_id": "528d24b8-e1e6-4ca0-a7ee-87f70a4f7980"},
    "properties": {
      "Task": {"title": [{"text": {"content": "[Meeting] <meeting name> <YYYY-MM-DD>"}}]},
      "Status": {"status": {"name": "In progress"}},
      "Workspace": {"select": {"name": "<workspace value from config>"}},
      "Assignee": {"people": [{"id": "<aaron_user_id>"}]},
      "Related to Meeting Notes (Related Tasks)": {"relation": [{"id": "<recap_page_id_if_option_D>"}]}
    }
  }'
```

Capture the response `id` as `PARENT_TASK_ID`.

**Step 6a-2: Create each action item as a subtask of `PARENT_TASK_ID`.**

For each approved action item, set `Parent Task` to `PARENT_TASK_ID`. Notion
auto-fills the `Subtasks` relation on the parent, so the tree shows up in
the UI without a second write.

```bash
curl -s -X POST "https://api.notion.com/v1/pages" \
  -H "Authorization: Bearer $NOTION_API_TOKEN" \
  -H "Notion-Version: 2025-09-03" \
  -H "Content-Type: application/json" \
  --max-time 60 \
  -d '{
    "parent": {"data_source_id": "528d24b8-e1e6-4ca0-a7ee-87f70a4f7980"},
    "properties": {
      "Task": {"title": [{"text": {"content": "<action item text>"}}]},
      "Status": {"status": {"name": "Not started"}},
      "Workspace": {"select": {"name": "<workspace value>"}},
      "Due": {"date": {"start": "<YYYY-MM-DD or null>"}},
      "Assignee": {"people": [{"id": "<resolved attendee or aaron>"}]},
      "Parent Task": {"relation": [{"id": "<PARENT_TASK_ID>"}]},
      "Related to Meeting Notes (Related Tasks)": {"relation": [{"id": "<recap_page_id_if_option_D>"}]}
    }
  }'
```

**Assignee mapping:** if the action item is owned by an attendee whose name
matches a person on the workspace, resolve to their user_id via
`GET /v1/users` (cache the lookup once per skill run). Otherwise default to
Aaron.

**Step 6a-3: Google Tasks mirror for Aaron-owned items (primary checklist).**

Google Tasks is Aaron's primary daily checklist; Notion is the team-visible
archive. Routing rule per subtask:

| Owner | Google Tasks | Notion subtask |
|---|---|---|
| Aaron | ✅ create (primary) | ✅ create (audit trail) |
| Teammate (Ahmed, Guerrechon, etc.) | ❌ skip | ✅ create (it's on their plate) |
| External / track-only (e.g. Oksana → Ella) | ❌ skip | ✅ create (Aaron is tracking, not doing) |

For each Aaron-owned subtask, after the Notion subtask is created, immediately
create a Google Task on the default tasklist (`MDE5NTgyMDkwMjMxNjkwNzQyMTk6MDow`):

```bash
gws tasks tasks insert \
  --params '{"tasklist":"MDE5NTgyMDkwMjMxNjkwNzQyMTk6MDow"}' \
  --json '{"title":"<same as Notion subtask title>","notes":"Notion subtask: <NOTION_SUBTASK_ID>\nParent: https://www.notion.so/<PARENT_TASK_ID_no_dashes>"}'
```

Capture the response `id` as `GTASK_ID`. Then PATCH the Notion subtask to
record the back-pointer for bidirectional sync:

```bash
curl -s -X PATCH "https://api.notion.com/v1/pages/<NOTION_SUBTASK_ID>" \
  -H "Authorization: Bearer $NOTION_API_TOKEN" \
  -H "Notion-Version: 2025-09-03" \
  -H "Content-Type: application/json" \
  --max-time 60 \
  -d '{"properties": {"Last Activity": {"rich_text": [{"type":"text","text":{"content":"gtask:<GTASK_ID>"}}]}}}'
```

The `Last Activity` field is a rich_text property on Master Tasks; storing
the gtask ID with a `gtask:` prefix lets `/end-day` and tomorrow's
`/start-day` Step 1c parse it for exact-ID bidirectional sync. Both
directions of completion (tick in Google Tasks → close Notion subtask, OR
flip Notion Status=Done → complete Google Task) become possible without
fuzzy title matching.

**Skip Google Tasks entirely** if `gws` CLI is unavailable. Log the missing
mirror in the routing summary so Aaron knows to re-run later.

**Note:** Google Tasks output banner `Using keyring backend: keyring` prefixes
the JSON response. Strip it before parsing: `re.sub(r'^Using keyring.*\n', '', raw)`
or pipe through `tail -n +2`.

Map business_tag to Workspace using `workspace_values` from sources.yaml:
- lab → "Link & Reference Laboratory"
- ipa → "United IPA"
- nestmate → "Nestmate"
- dock_pro → "Dock Pro"
- other → "Other"

**Edge cases:**
- **Zero action items extracted** → still create the parent task with Status
  "Done" and a body block summarizing the meeting. Better to have a stub than
  to drop a meeting entirely; Aaron can re-run later if action items emerge.
- **Mixed-business action items** (e.g. a Docpro/Nestmate joint meeting) →
  parent gets the more specific business (Nestmate beats Other). Each
  subtask carries its own Workspace tag, so departmental routing in
  `/start-day` still works correctly per-subtask.
- **Re-running on the same meeting** → before creating the parent, query
  Master Tasks where `Related to Meeting Notes` contains the recap page_id
  AND title starts with `[Meeting]`. If a parent already exists, reuse its
  ID and only add the missing subtasks. Never duplicate the parent.

If $NOTION_API_TOKEN is empty: skip all Notion writes, warn user, save items
to a local file `${VAULT}/meetings/{TODAY}-pending-notion.md` for manual entry.

### 6a-bonus: Granola recap back-link (Option D only)

If the meeting source was a Meeting Notes recap page (Option D), do two extra
writes after the Master Tasks are created:

1. **Tag the recap with Workspace** if it was untagged. PATCH the recap page:

   ```bash
   curl -s -X PATCH "https://api.notion.com/v1/pages/${RECAP_PAGE_ID}" \
     -H "Authorization: Bearer $NOTION_API_TOKEN" \
     -H "Notion-Version: 2025-09-03" \
     -H "Content-Type: application/json" \
     --max-time 60 \
     -d '{
       "properties": {
         "Workspace": {"select": {"name": "<workspace value>"}},
         "Related Tasks": {"relation": [{"id": "<PARENT_TASK_ID>"}, {"id": "<subtask_1_id>"}, {"id": "<subtask_2_id>"}]}
       }
     }'
   ```

   Include the parent task **and** every subtask in the relation array — the
   Meeting Notes page should expose the full task tree, not just the parent.
   Step 6a-2 already linked subtasks via `Related to Meeting Notes` from the
   task side, so this PATCH is redundant for those rows but cheap; the value
   is including `PARENT_TASK_ID` which the per-subtask writes don't cover.
   The relation is dual-property; if the recap already had relations, fetch
   existing IDs first and merge so we don't clobber prior links.

2. **Skip this section entirely** if the source was Option A/B/C — no recap
   page exists to link.

### 6b: Log Decisions to Activity Log

For each approved decision:

```bash
curl -s -X POST "https://api.notion.com/v1/pages" \
  -H "Authorization: Bearer $NOTION_API_TOKEN" \
  -H "Notion-Version: 2025-09-03" \
  -H "Content-Type: application/json" \
  --max-time 60 \
  -d '{
    "parent": {"data_source_id": "3db174bf-c997-4a41-93ee-36f280e511db"},
    "properties": {
      "Task": {"title": [{"text": {"content": "<decision summary>"}}]},
      "Type": {"select": {"name": "Decision"}},
      "Date": {"date": {"start": "<TODAY>"}},
      "Workspace": {"select": {"name": "<workspace value>"}}
    }
  }'
```

### 6c: Update Provider CRM

For each approved provider update, first search for the existing provider:

```bash
curl -s -X POST "https://api.notion.com/v1/data_sources/ae0a3158-59b4-8235-b7ca-0758daa2322a/query" \
  -H "Authorization: Bearer $NOTION_API_TOKEN" \
  -H "Notion-Version: 2025-09-03" \
  -H "Content-Type: application/json" \
  --max-time 60 \
  -d '{
    "filter": {
      "property": "Name",
      "title": {"contains": "<provider name>"}
    },
    "page_size": 5
  }'
```

If found, update the existing record:
```bash
curl -s -X PATCH "https://api.notion.com/v1/pages/{page_id}" \
  -H "Authorization: Bearer $NOTION_API_TOKEN" \
  -H "Notion-Version: 2025-09-03" \
  -H "Content-Type: application/json" \
  --max-time 60 \
  -d '{
    "properties": {
      "Last Contact": {"date": {"start": "<TODAY>"}},
      "Next Step": {"rich_text": [{"text": {"content": "<next step>"}}]}
    }
  }'
```

If NOT found, create a new CRM entry:
```bash
curl -s -X POST "https://api.notion.com/v1/pages" \
  -H "Authorization: Bearer $NOTION_API_TOKEN" \
  -H "Notion-Version: 2025-09-03" \
  -H "Content-Type: application/json" \
  --max-time 60 \
  -d '{
    "parent": {"data_source_id": "ae0a3158-59b4-8235-b7ca-0758daa2322a"},
    "properties": {
      "Task": {"title": [{"text": {"content": "<provider name>"}}]},
      "Last Contact": {"date": {"start": "<TODAY>"}},
      "Next Step": {"rich_text": [{"text": {"content": "<next step>"}}]},
      "Stage": {"select": {"name": "New Lead"}},
      "Workspace": {"select": {"name": "<workspace value>"}}
    }
  }'
```

### 6d: Draft Google Calendar Events

For each approved follow-up meeting, use the gws CLI:

```bash
gws calendar +quickadd "<meeting topic> with <attendees>" --calendar "primary"
```

If gws is not available, fall back to the Google Calendar MCP tool
`mcp__claude_ai_Google_Calendar__create_event` with:
- summary: meeting topic
- description: context from the meeting notes
- attendees: if email addresses are known

If neither works, output the calendar items as text for Aaron to add manually.

### 6e: Write Obsidian Notes

**Insights:** For each approved insight, write a note to `${VAULT}/notes/`:

Filename: `{TODAY}-{slugified-title}.md`

```markdown
---
date: {TODAY}
tags: [meeting, {business_tag}]
source: meeting with {attendees}
---

# {Insight Title}

{Original text from meeting notes}

---
_Extracted from meeting on {TODAY} ({meeting context})_
```

**Meeting note file:** Always write the full meeting notes (whether or not
individual items were routed) to `${VAULT}/meetings/`:

Filename: `{TODAY}-{slugified-meeting-context}.md`

```markdown
---
date: {TODAY}
meeting: {meeting context}
attendees: [{attendees}]
tags: [meeting, {business_tag}]
---

# Meeting: {meeting context} — {TODAY}

**Attendees:** {attendees}

## Raw Notes

{original raw meeting notes, preserved exactly}

## Routed Items

{list of items that were routed, with destination}
- [ACTION → Notion] {task title}
- [DECISION → Notion] {decision}
- [INSIGHT → Obsidian] {insight title}
- [FOLLOW-UP → Calendar] {meeting topic}
- [PROVIDER → CRM] {provider update}

## Decision Links

{For each decision routed to Notion, add a wikilink}
- [[{TODAY}-{decision-slug}]] — {decision summary} (canonical in Notion Activity Log)
```

**Decision links in Obsidian:** Decisions live in Notion as the single source
of truth. The meeting note in Obsidian gets a reference/link, not a copy.
This prevents two versions of the same decision from drifting apart.

## Step 7: Summary

After all routing is complete, display a summary:

```markdown
# Routing Complete

**Created in Notion Master Tasks:** {count} items
**Logged to Notion Activity Log:** {count} decisions
**Updated in Provider CRM:** {count} providers
**Drafted in Google Calendar:** {count} follow-up meetings
**Written to Obsidian notes/:** {count} insight notes
**Meeting note saved:** vault/meetings/{filename}

{If any items failed, list them with the error}
```

## Step 8: Stamp Applied action_ids + Emit Telemetry (AAC OBSERVED)

After every successful write in Step 6, stamp the action_id so future runs no-op:

```bash
for AID in <each successfully-written item's action_id>; do
  scripts/action_id.sh stamp "${AID}" "$(python -c "
import json
print(json.dumps({
    'skill': 'capture-meeting',
    'run_id': '${RUN_ID}',
    'category': '${CATEGORY}',
    'notion_page_id': '${NOTION_PAGE_ID_IF_ANY}',
    'gtask_id': '${GTASK_ID_IF_ANY}',
    'source_line': ${SOURCE_LINE_NUMBER}
})
")"
done
```

If a write failed, do NOT stamp the action_id — the next run will retry.

Then emit telemetry:

```bash
DURATION_MS=$(( $(date +%s%3N 2>/dev/null || python -c "import time; print(int(time.time()*1000))") - RUN_START_MS ))

scripts/telemetry.sh capture-meeting "${RUN_ID}" "${DURATION_MS}" "${STATUS}" "$(python -c "
import json
print(json.dumps({
    'mode': '${MODE}',
    'source': '${SOURCE_TYPE}',                # one of: paste | file | meetings_folder | granola_recap
    'items_parsed': ${ITEMS_PARSED},
    'items_high_conf': ${ITEMS_GE_0_8},        # count with confidence >= 0.8
    'items_low_conf': ${ITEMS_LT_0_7},         # count routed to Uncategorized
    'items_skipped_idempotent': ${SKIPPED_COUNT},
    'items_approved': ${APPROVED_COUNT},
    'items_rejected': ${REJECTED_COUNT},
    'phi_refused': ${PHI_REFUSED_BOOL},
    'writes': {
        'master_tasks_created': ${MT_COUNT},
        'gtasks_created': ${GT_COUNT},
        'activity_log_created': ${AL_COUNT},
        'crm_updated': ${CRM_COUNT},
        'calendar_drafted': ${CAL_COUNT},
        'obsidian_notes_written': ${OBS_COUNT}
    },
    'write_failures': ${WRITE_FAILURES_LIST}
})
")"
```

`STATUS` is `ok` (all approved items written), `partial` (≥1 write failed), `refused` (PHI gate), or `failed` (Notion auth, total outage).

## Error Handling

- **scripts/check_mode.sh exits 1 (locked):** Refuse. No telemetry — locked runs don't happen.
- **scripts/phi_scan.sh exits 1 (PHI detected):** Refuse parsing. Append to `logs/_phi_refusals.jsonl`. Telemetry status = `refused`.
- **Notion API failure:** Log the failed item to `${VAULT}/meetings/{TODAY}-pending-notion.md`
  with all the structured fields so Aaron can manually enter it. Continue with other items.
  Do NOT stamp the action_id for failed writes — they need to retry next run.
- **Calendar failure:** Output the calendar item as text. Continue.
- **Obsidian write failure:** Warn and continue. This should be rare since it's local file writes.
- **Never retry automatically.** Report clearly and continue with other items.
- **Never crash on a single item failure.** Process all items, report failures at the end.
- **Notion timeout:** Use `--max-time 60` on all curl calls. If timeout, treat as failure.
