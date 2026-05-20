---
name: start-day
description: >-
  Daily briefing skill: pulls Google Calendar, Notion databases, Obsidian vault,
  and Google Tasks into a prioritized morning plan. Scores top outcomes, flags
  stale items and delegation candidates, and optionally writes an Obsidian daily
  note. Run every morning to replace opening four apps.
coo_twin:
  category: briefing
  mode_required: any
  writes_external: true
  preflight: required
  experimental: false
---

# /start-day — Daily Briefing

You are acting as Aaron's Chief of Staff. Your job is to read every connected
source, synthesize what matters, and propose a plan for the day.

**Read-first, write-on-approval.** Never write to any system without explicit
approval at the trust gate.

## Constants

```
REPO_DIR = "C:/Users/aaron/daily-automation"
CONFIG   = "${REPO_DIR}/config/sources.yaml"
LOGS_DIR = "${REPO_DIR}/logs"
VAULT    = "${REPO_DIR}/vault"
STATE    = "${REPO_DIR}/state"
TODAY    = <current date in YYYY-MM-DD format>
RUN_ID   = "sd-${TODAY//-/}-$(date +%H%M)"   # e.g. sd-20260518-0703
```

## Step 0: Mode Check (AAC GOVERNED)

Run `scripts/check_mode.sh` and capture stdout + exit code:

```bash
MODE=$(scripts/check_mode.sh) || {
  echo "🛑 Agent is locked (state/coo_mode.yaml). Refusing to run /start-day."
  echo "To unlock: edit state/coo_mode.yaml and set mode: draft (or send /UNLOCK AGENT once Telegram is live)."
  exit 0
}
```

If `MODE == "observe"`: set `SKIP_WRITES=1`. Step 8 and Step 9 will display proposed
writes but never execute. Step 8 trust gate becomes informational only.

If `MODE == "draft"` (default): proceed normally.

If `MODE == "approved"`: trust gate auto-approves any action_id whose prefix matches
`state/coo_mode.yaml :: approved_action_prefixes`. Other writes still gated.

Record the mode in the briefing header (`Mode: draft`) so Aaron sees the operating
posture at a glance.

Capture `RUN_START_MS=$(date +%s%3N 2>/dev/null || python -c "import time; print(int(time.time()*1000))")` for telemetry at Step 10.

## Step 1: Load Configuration

Read `${CONFIG}` (config/sources.yaml) to get:
- Obsidian vault path and folder structure
- Notion database definitions with field mappings
- Google Tasks settings
- Calendar business keywords
- Team members and delegation tags
- Staleness threshold (default: 7 days)

Also read `${REPO_DIR}/config/streams.yaml` — the generic stream definitions
(formerly "departments"). Skills are mid-migration from hardcoded department
names to iterating this file; for now /start-day loads it for visibility +
runs a consistency check.

### Streams ↔ sources consistency check (non-blocking)

```bash
DRIFT=$(python scripts/streams_check.py --json 2>/dev/null)
N_BLOCKING=$(echo "$DRIFT" | jq -r '.n_blocking // 0')
N_INFO=$(echo "$DRIFT" | jq -r '.n_info // 0')
```

If `N_BLOCKING > 0`, add a `⚠️ Stream config drift` warning to the briefing
header in Step 7 (don't block the run; surface so Aaron can fix). If only
INFO items, mention briefly (`ℹ️ Stream config: 2 info notes`) and move on —
this is expected when Notion has workspace-option drift relative to
`sources.yaml`.

Full drift detail (if surfaced) lives in `state/streams-drift-${TODAY}.json`
for inspection.

## Step 1b: Pre-flight Validation (before pulling sources)

### Calendar ↔ memory consistency check

Read `${STATE}/priorities.yaml` (loaded already in Step 1) and scan auto-memory for any item whose notes mention an explicit upcoming meeting time, day, or phrase like "potentially Friday", "tomorrow", "this week" (e.g. "Roman ↔ CardioPro team meeting").

For each flagged meeting, run a quick `gws calendar +agenda --week --format json` search and check whether a calendar event matches by title keyword AND falls within the implied window. If no match, add the item to a `memory_calendar_gaps` list. Do NOT block the briefing — show the gaps as a warning at the top of the briefing in Step 7.

This prevents drift like the 2026-04-20→2026-04-23 Roman meeting that was flagged in priorities.yaml but never showed on the calendar, then carried forward unresolved for 5 days.

### Pending-writes audit

Glob `${REPO_DIR}/.context/*.json` (top-level only — explicitly **skip `${REPO_DIR}/.context/applied/`**, which holds files whose writes have already landed) and `${REPO_DIR}/.context/pending/*.json` if that subdir exists.

For each file, read the top-level `intent` / `pending` / `status` field:

- If the field is set to `pending`, `awaiting_approval`, or `denied` → add to `pending_writes` with category `confirmed`.
- If **no** status field exists → add to `pending_writes` with category `unverified` and the note "verify push status — file may already be applied." Do **not** assert it is unwritten.
- If the field is set to `applied`, `done`, `completed` → ignore.

Render in Step 7's briefing as **"⚠️ Pending writes from prior session"**, with the two categories visually distinguished (e.g. confirmed vs unverified). Suggest moving applied files to `.context/applied/<name>-<YYYY-MM-DD>.json` to silence future false positives.

This was tightened on 2026-04-28 after both `cardiopro_append.json` and `essen_append.json` were flagged as 5-day pending writes when they had actually been PATCHed to Notion on 2026-04-23 — the absence of a `status` field is not evidence of an unwritten payload. See `feedback_context_cleanup.md` in memory.

If `.context/` doesn't exist, skip silently — not all sessions stage writes.

### Sync-sweep DLQ depth (post-MVE, added with /sync-sweep)

Read `${STATE}/sync-sweep-retry-queue.yaml`. This is the dead-letter queue for
`/sync-sweep` PATCH failures (5xx, 429, network) that have exhausted in-run
retries and need a fresh run to drain. Surfacing depth here gives Aaron a
single-glance view of how stuck the sweeper is.

**Procedure:**

1. If the file does not exist → **no flag emitted**. Skip silently. The file
   is created on first failure, not on first run.
2. Parse the file as YAML. Expected schema:
   ```yaml
   queue:
     - entity_name: str
       notion_page_id: str
       payload: object
       attempts: int            # 1..3
       last_status: str         # 5xx | 429 | network | other
       first_failed: str        # ISO timestamp of first failure
   ```
3. **Malformed YAML graceful skip:** if the parse fails (truncated file, bad
   indentation, non-string keys), append a one-line warning to
   `${LOGS_DIR}/{TODAY}.md` of the form
   `sync-sweep DLQ: state/sync-sweep-retry-queue.yaml malformed — skipped`,
   then continue with no flag. Do NOT crash, do NOT block the briefing.
4. If `queue` is empty (missing key, `null`, or empty list `[]`) → **no flag
   emitted**.
5. If `queue` is non-empty:
   - `N = len(queue)`
   - `M = max(today - first_failed) in days` across all entries (oldest entry wins; round down)
   - If `M >= 3` (any entry has been stuck 3+ days):
     emit flag `⚠️ sync-sweep DLQ: N items, oldest M days`
   - Else: emit flag `sync-sweep DLQ: N items, oldest M days`

**Where this renders in Step 7:**

Render the flag in the briefing under the existing **"⚠️ Pending writes from
prior session"** umbrella as its own sub-line. If no pending writes were
detected but the DLQ has entries, render under a new top-level
`## ⚠️ System flags` section (one line per flag). When ≥3 days old, the marker
implies the API is persistently flaky for those IDs — not a transient burst —
and Aaron should consider draining manually or pruning the payload.

This check was added 2026-05-19 with the `/sync-sweep` MVE; the retry queue
file is the load-bearing artifact for the OBSERVED discipline on that skill.

## Step 1c: Yesterday Catch-up Sync (bidirectional reconcile)

Aaron's checkboxes and the source systems (Google Tasks, Notion) drift apart
in both directions. The dominant pattern (per `feedback_nightly_gtask_batch_close.md`)
is that Aaron closes tasks in the Google Tasks UI nightly and never ticks the
daily-note `[ ]`. The inverse — daily-note `[x]` with the source still open —
happens too but is rarer. Step 1c reconciles both directions, with **gtasks /
Notion treated as the authoritative source**.

This direction matters for resilience: when the gtasks API has an intermittent
500 burst (see the 2026-05-13 → 2026-05-15 incident), the dominant pull path
(API → daily note) is a local file edit, which never fails. Only the rare
push path (daily note → API) is exposed to API failures.

**Procedure:**

1. Compute `YESTERDAY` = today minus 1 day (YYYY-MM-DD).
2. Read `${VAULT}/daily/{YESTERDAY}.md`. If it doesn't exist, skip this step.
3. Scan every line in the file matching `^- \[[ xX]\] ` (BOTH unchecked and
   checked). For each match, extract:
   - The visible task text
   - The checkbox state (`checked` or `unchecked`)
   - Any trailing HTML comment of the form `<!-- gtask:<ID> -->` or
     `<!-- notion:<ID> -->` — these are durable source IDs written by Step 9
     when the daily note was created.
   Build a map: `{source_id → {state, line_number, line_text}}`.
4. Read today's log file `${LOGS_DIR}/{TODAY}.md` if it already exists — if a
   `### Catch-up Sync` section is present from an earlier run, skip this step
   (don't double-prompt).
5. **Pull authoritative state once per source system:**
   - **gtask:** one call `gws tasks tasks list --params '{"tasklist":"MDE5NTgyMDkwMjMxNjkwNzQyMTk6MDow","showCompleted":true,"showHidden":true,"updatedMin":"<YESTERDAY-1d>T00:00:00.000Z","maxResults":100}' --format json`. The `updatedMin` lower-bound (yesterday minus one day) catches overnight closures while keeping the response small. Cache by ID.
   - **notion:** GET `https://api.notion.com/v1/pages/<ID>` per ID (no batch endpoint).
6. **Reconcile each pair into one of four buckets:**
   - **`pull_completions`** — source is `completed` / `Done` AND daily-note is `[ ]`. Action: mirror to `[x]` in YESTERDAY's daily note (local file edit, no API write). **This is the dominant case** when Aaron closes nightly in the gtasks UI.
   - **`push_completions`** — source is open AND daily-note is `[x]`. Action: PATCH source to completed. **Rare and the only path exposed to API failures.**
   - **`both_match`** — no-op.
   - **`unverifiable`** — source unreachable (5xx, 401, timeout). List for the briefing, no action.
7. For `[x]` items WITHOUT an embedded ID (legacy notes or manual additions):
   record as `manual_completions_no_source` — informational only.
8. If both `pull_completions` and `push_completions` are empty → skip silently.
   Otherwise surface separately in Step 7 under **"⚠️ Catch-up sync from yesterday"**
   and gate writes at Step 8b.

**Failure handling:** If Google Tasks or Notion is unreachable for the Step 5
pull, mark every ID from that system as `unverifiable` and continue. Never
block the briefing on a sync check.

**Why this direction:** Daily-note → API is the failure-prone path (intermittent
500s, auth quirks). API → daily-note is a file edit. By making the API
authoritative and the file the mirror, we eliminate ~80% of the sync write
surface area. The push path still exists for the rare case where Aaron ticks
`[x]` in Obsidian first.

History:
- The 2026-04-29 → 2026-04-30 gap (5 unsynced `[x]` items) drove the original
  push-only Step 1c. See `feedback_obsidian_tasks_sync.md`.
- The 2026-05-13 → 2026-05-15 `gtasks_500_burst_recurring` incident exposed
  that the push direction was over-relied on AND the curl-with-bearer call
  was returning 401, not 500 — some "500s" were auth misclassification. See
  `feedback_reversed_gtask_sync.md`.

## Step 1d: Build the Suppression Set (deprioritized / back-burner / snoozed)

Aaron's deprioritization decisions live in `state/priorities.yaml` and as
free-text annotations inside the previous daily-note. They are **NOT**
reflected in the source-system Status fields — a dropped Notion subtask is
usually still `Status: "Not started"`, a back-burnered gtask is still
`status: "needsAction"`. Without an explicit suppression step, the Step 3
Notion query and the Step 5 gtask pull will resurface them as actionable
items, contradicting yesterday's decision.

This step was added 2026-05-20 after AFFA's 6 subtasks resurfaced as a
Lincoln Lab actionable bundle the morning after Aaron explicitly wrote
"affas out of the picute fo now" and "take AFFA off main sttaus for now"
in the 5/19 daily note AND logged `dropped_20260519: AFFA 6-subtask bundle`
to priorities.yaml. Three of four signals were ignored by the filter chain;
this step makes them load-bearing.

**Build a single `SUPPRESSED_IDS` set with the union of:**

1. **`priorities.yaml :: dropped_<recent-dates>`** — read every key matching
   `dropped_YYYYMMDD` whose date is within the last 14 days. Each list entry
   is free text but typically contains a page_id or task title; extract any
   bare UUID (regex `[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}`)
   AND any embedded `gtask:` / `notion:` markers. Add all extracted IDs to
   `SUPPRESSED_IDS` with reason `dropped_<date>` and the original line as
   evidence.

2. **`priorities.yaml :: back_burner[]`** — each entry has a `source` and
   `source_id`. If `source_id` is non-null, add it with reason
   `back_burner since <moved_at>`.

3. **`priorities.yaml :: dormant_snooze[]`** — each entry has a `page_id`
   and `until`. If `today <= until`, add `page_id` with reason
   `dormant_snooze until <until>`. If `today > until`, skip (snooze expired —
   item should resurface naturally).

4. **Yesterday's daily-note free-text annotations** (the prose, not the
   `[ ]` / `[x]` state). Read `${VAULT}/daily/{YESTERDAY}.md` line-by-line.
   For each line containing a `<!-- gtask:ID -->` or `<!-- notion:ID -->`
   comment, scan the same line (and the 2 lines above + below) for any of
   these case-insensitive phrases:
   - `off main status`
   - `back burner` / `backburned` / `backburn` / `back-burner`
   - `deprioritized` / `depriortized` / `deprio`
   - `out of the picture` / `out of picute` (Aaron's spelling)
   - `dropped` / `drop` (whole-word — careful, "dropoff" should NOT match)
   - `snooze` / `snoozed`
   - `track-only` / `track only` / `backbone tracking only`
   - `not focusing on` / `not a focus`
   - `parked` / `park it`
   - `kill it` / `formally kill`
   If matched, add the embedded ID to `SUPPRESSED_IDS` with reason
   `daily-note annotation "<matched phrase>"` and the line number.

5. **Parent-task implication**: if a Notion page_id is suppressed AND the
   live Master Tasks query returns subtasks whose `Parent task` relation
   points to that page_id, those subtask page_ids are ALSO suppressed
   transitively. Without this, parents land in `dropped_*` but their
   children resurface as orphaned items (the AFFA case — parent flipped
   Done, 6 subtasks left as Not started).

**How `SUPPRESSED_IDS` is used downstream:**

- **Step 3 (Notion query)**: after fetching Master Tasks, filter out any
  page whose `id` is in `SUPPRESSED_IDS`. Same for Provider CRM.
- **Step 5 (Google Tasks)**: filter out any task whose `id` is in
  `SUPPRESSED_IDS`.
- **Step 6 (Top 3 scoring)**: suppressed items are excluded from the score
  pool entirely. They never become Top 3 candidates.
- **Step 7 (briefing)**: render a footer **"🔇 Suppressed N items
  (deprioritized/back-burner/snoozed)"** with a one-line-per-bucket
  summary so the audit trail stays visible. Format:
  ```
  🔇 Suppressed 7 items (audit trail preserved):
    - AFFA bundle (6 subtasks)         — dropped_20260519
    - Cardio Pro Rollout                — dormant_snooze until 2026-06-30
    - Sheila                            — back_burner since 2026-05-11
  ```
  Aaron can verify the right things were filtered. If something was
  wrongly suppressed, removing it from the priorities.yaml bucket
  brings it back tomorrow.

**Failure modes:**

- Suppression should never throw. If `priorities.yaml` is malformed or a
  `dropped_*` key is unreadable, log a one-line warning to today's log and
  proceed with whatever IDs were successfully extracted. Don't block.
- Phrase-matching is conservative on purpose. False negatives (an item that
  *should* be suppressed but wasn't) are recoverable — Aaron sees it in the
  briefing and can drop it explicitly. False positives (suppressing
  something that should be actionable) are the worse failure mode because
  the item silently disappears. When in doubt, do NOT suppress.

## Step 2: Pull Google Calendar

Use the `gws` CLI to fetch calendar events via Bash tool.

**Commands:**

```bash
# Today's events (JSON for structured parsing)
gws calendar +agenda --today --format json

# Tomorrow's events (for meeting prep section)
gws calendar +agenda --tomorrow --format json
```

**Response shape:**
```json
{
  "count": N,
  "events": [
    {
      "calendar": "email@gmail.com",
      "start": "2026-04-14T11:00:00-04:00",
      "end": "2026-04-14T12:00:00-04:00",
      "summary": "Event title",
      "location": "optional address"
    }
  ]
}
```

**Processing:**
- Tag each event with a stream using `config/streams.yaml`:
  - For each event, walk `streams[]` in declaration order and case-insensitively
    substring-match the event `summary` against each stream's `keywords` list.
    First-match-wins (order matters when a keyword appears in multiple streams).
  - Events matching no keyword fall through to the stream with `is_default: true`
    (or are tagged "untagged" if no default is set).
- Detect conflicts: overlapping timed events on the same day (compare start/end times)
- Note event times, titles, and locations
- All-day events have date-only start/end (no time component)

**If gws calendar fails:** Skip this section. Add "Google Calendar" to the skipped sources list. Continue with other sources.

## Step 3: Pull Notion Databases

Use the Notion REST API via `curl` (Bash tool). The `notion-api` skill is installed
with full reference docs at `.agents/skills/notion-api/`.

**Authentication:** The token is in `$NOTION_API_TOKEN` env var. All requests need:
```bash
-H "Authorization: Bearer $NOTION_API_TOKEN" \
-H "Notion-Version: 2025-09-03" \
-H "Content-Type: application/json"
```

**After every Notion database query in this step:** filter out any result page
whose `id` appears in `SUPPRESSED_IDS` (built in Step 1d). Track the suppressed
count per database for the Step 7 footer. The 5/19→5/20 AFFA resurfacing was
caused by skipping this filter — do not omit it.

**If `$NOTION_API_TOKEN` is empty or unset:** Skip all Notion sections. Add "Notion"
to the skipped sources list with message: "NOTION_API_TOKEN not set. Add it to
.claude/settings.local.json under env." Continue with other sources.

**For each database in `notion_databases`:**

### Master Tasks (primary)

Query the database using POST:
```bash
curl -s -X POST "https://api.notion.com/v1/data_sources/528d24b8-e1e6-4ca0-a7ee-87f70a4f7980/query" \
  -H "Authorization: Bearer $NOTION_API_TOKEN" \
  -H "Notion-Version: 2025-09-03" \
  -H "Content-Type: application/json" \
  -d '{
    "filter": {
      "and": [
        {"property": "Status", "status": {"does_not_equal": "Done"}}
      ]
    },
    "sorts": [{"property": "Due", "direction": "ascending"}],
    "page_size": 50
  }'
```

From the response `results` array, parse each page's `properties`:
- **Status:** `properties.Status.status.name` — values: "Not started", "In progress", "Waiting", "Done"
- **Due date:** `properties.Due.date.start` — ISO date string
- **Workspace:** `properties.Workspace.select.name` — business tag
- **Assignee:** `properties.Assignee.people[].name`
- **Task (Title):** `properties.Task.title[0].plain_text` — the title property is called "Task", not "Name"
- **Updated:** `properties.Updated.last_edited_time` or `last_edited_time` on the page object

Identify items by status:
- **In progress:** Status = "In progress"
- **Not started:** Status = "Not started"
- **Waiting:** Status = "Waiting"
- **Overdue:** Due date is in the past AND Status is NOT "Done"
- **Stale:** page's `last_edited_time` is older than `staleness_days` (7 days) AND Status is NOT "Done"

Tag each item by stream using the Workspace field value matched against
`streams[].workspace_values` in `config/streams.yaml`. A page's `Workspace`
string belongs to stream S if it appears in `S.workspace_values`. Walk streams
in declaration order; first match wins. Unmatched / null Workspace falls
through to the stream with `is_default: true`.

**IMPORTANT:** Do NOT inherit a stream assignment from a Notion parent task
name. Check the actual Workspace field on each item. If Workspace is null,
infer from item context against `streams[].keywords` the same way calendar
tagging does (first-match-wins in declaration order). Historical example:
"DOCPRO clients" parent does NOT mean subtasks are Dock Pro — checked each
individually (learned 2026-04-15 when AFC Urgent Care + Dr Remzy Meny were
misrouted as Dock Pro instead of Nestmate).

### Provider CRM (secondary)

```bash
curl -s -X POST "https://api.notion.com/v1/data_sources/ae0a3158-59b4-8235-b7ca-0758daa2322a/query" \
  -H "Authorization: Bearer $NOTION_API_TOKEN" \
  -H "Notion-Version: 2025-09-03" \
  -H "Content-Type: application/json" \
  -d '{"page_size": 50}'
```

- Check for providers needing follow-up: Last Contact > `provider_followup_days` (14 days)
- Check pipeline items by stage field

### Activity Log (secondary)

```bash
curl -s -X POST "https://api.notion.com/v1/data_sources/3db174bf-c997-4a41-93ee-36f280e511db/query" \
  -H "Authorization: Bearer $NOTION_API_TOKEN" \
  -H "Notion-Version: 2025-09-03" \
  -H "Content-Type: application/json" \
  -d '{
    "filter": {
      "property": "Date",
      "date": {"on_or_after": "<3 days ago in YYYY-MM-DD>"}
    },
    "page_size": 20
  }'
```

- Check for recent activities (last 3 days) for context
- Note any items with a non-empty "Next Action" field

### Meeting Notes — Granola sync target (secondary)

```bash
curl -s -X POST "https://api.notion.com/v1/data_sources/22ba3158-59b4-804d-9c1c-000b9fad40ae/query" \
  -H "Authorization: Bearer $NOTION_API_TOKEN" \
  -H "Notion-Version: 2025-09-03" \
  -H "Content-Type: application/json" \
  -d '{
    "filter": {
      "timestamp": "last_edited_time",
      "last_edited_time": {"on_or_after": "<yesterday in YYYY-MM-DD>"}
    },
    "sorts": [{"property": "Date", "direction": "descending"}],
    "page_size": 20
  }'
```

For each result:
- **Meeting name:** `properties["Meeting name"].title[0].plain_text`
- **Date:** `properties.Date.date.start`
- **Summary:** `properties.Summary.rich_text[0].plain_text` (Granola's auto-recap, may be long — preview first 200 chars)
- **Workspace:** `properties.Workspace.select.name` — null = needs triage
- **Related Tasks:** `properties["Related Tasks"].relation[]` — count of linked Master Tasks (0 = no actions extracted yet)

Surface in the briefing under a new "Recent Meeting Recaps (24h)" section,
grouped by Workspace. Any meeting with `Workspace = null` goes under
**"⚠️ Untagged — needs triage"** with the suggestion to run `/capture-meeting`
on it (which will route action items + tag the workspace).

**Triage hint:** infer likely Workspace from attendee names + title keywords
(see `legacy_category_field` notes in config/sources.yaml). Do NOT auto-tag in
read mode — only suggest. Tagging happens via the trust gate or via
`/capture-meeting`.

**Confidence requirement (AAC BOUNDED + GROUNDED, added 2026-05-18):** Every triage
suggestion includes a 0.0–1.0 confidence score based on:
- 1.0 if a single workspace keyword matches title AND attendee list is single-business
- 0.8 if attendee list strongly implies one workspace (e.g. "Roman, Tim, Damian" → Dock Pro)
- 0.5 if title keyword weak match OR attendees span 2 workspaces
- < 0.5 → render as "⚠️ low confidence — verify manually" with NO suggested workspace

Display format: `suggested: **{workspace}** (conf {0.85}) — based on {evidence summary}`.
Aaron then sees the reasoning, not just the guess.

**Action-item extraction status (per meeting):**

For each Meeting Notes row, check `Related Tasks` relation count and the
titles of the linked tasks:

- `Related Tasks` count = 0 → **untreated**: Aaron has the Granola recap in
  Notion but no Master Tasks have been wrapped from it yet. Surface in the
  briefing under **"📋 Meetings needing action-item extraction"** with a
  `→ /capture-meeting <page-id>` hint.
- `Related Tasks` count > 0 but no linked task title starts with `[Meeting]`
  → **partially treated**: action items exist but were created before the
  parent-task wrapper convention. Show as `partially treated — N orphan
  subtasks, no parent`. Hint: `→ /capture-meeting <page-id>` will create the
  parent and re-link.
- `Related Tasks` includes a `[Meeting] …` row → **wrapped**: parent task +
  subtasks already created. Show subtask completion progress like
  `5/8 subtasks done` so Aaron can see meeting follow-through at a glance.

The "📋 Meetings needing action-item extraction" list should also expand to
recurring topic-page appends (Cardio Pro Rollout, Essen Healthcare 4/21,
etc.) if their last `## YYYY-MM-DD —` block is newer than the most recent
`[Meeting]` parent task that links to them. Same `/capture-meeting` hint
applies — it accepts the topic page_id and treats the latest dated section
as the source meeting.

**Coverage check (workspace-wide, not just Meeting Notes DB):**

Aaron pushes Granola meetings to Notion in two patterns:
1. **As new Meeting Notes DB entries** (one meeting → one DB row). Detected by the query above.
2. **As appended sections inside existing topic pages** (e.g. `Cardio Pro Rollout`, `Essen Healthcare 4/21 Meeting notes`). The Granola URL appears as block content inside the topic page, not as a Meeting Notes row. This pattern is intentional — it keeps long-running threads coherent. See `feedback_granola_routing.md` in memory.

For each Granola URL referenced in `state/priorities.yaml` (or in the prior day's log) that is NOT already represented in the Meeting Notes DB query above, run a workspace-wide search before declaring a sync gap:

```bash
# Extract the unique fragment from the Granola URL (e.g. "19221ac9" from notes.granola.ai/t/19221ac9-...)
# Then query Notion search for that fragment.
curl -s -X POST "https://api.notion.com/v1/search" \
  -H "Authorization: Bearer $NOTION_API_TOKEN" \
  -H "Notion-Version: 2025-09-03" \
  -H "Content-Type: application/json" \
  -d '{"query":"<8-char-fragment>","page_size":10}'
```

If the search returns 0 results AND the Meeting Notes DB also has no match → declare **"⚠️ Granola → Notion sync gap"** and suggest pushing from the Granola app.

If the search returns ≥1 result → the meeting IS in Notion as an appended section. Note its parent page in the briefing under "Recent Meeting Recaps (24h)" so Aaron sees where it landed; do NOT flag a sync gap.

This was added 2026-04-28 after the 4/23 Nestmate/Docpro and Lab meetings were falsely reported as missing for 5 consecutive days while actually living inside Cardio Pro Rollout and Essen Healthcare 4/21 pages.

**If a specific database returns an error (404 object_not_found):** The database
likely isn't shared with the integration. Warn: "Database {name} not accessible —
share it with the 'Daily Automation' integration in Notion." Continue with others.

**Handle pagination:** If `has_more` is true in the response, make additional
requests with `start_cursor` from `next_cursor`. Limit to 3 pages max per database.

## Step 4: Scan Obsidian Vault

Read the local vault at `${VAULT}` using the Read and Glob tools.

**Inbox items:**
- Use Glob to find all files in `${VAULT}/inbox/`
- List each file as an unprocessed capture needing review

**Notes tagged #review:**
- Use Grep to search for `#review` across `${VAULT}/notes/` and `${VAULT}/` (frontmatter `tags:` or inline `#review`)
- List matches as notes needing attention

**Recent notes:**
- Use Glob to find files in `${VAULT}/notes/` modified in the last 3 days
- Mention these as recent activity for context

**If the vault path doesn't exist or folders are missing:** Report what was expected vs. found. Add "Obsidian" to skipped sources if vault is completely inaccessible.

## Step 5: Pull Google Tasks

Run the gws CLI to fetch tasks. The CLI is at the system PATH.

**Commands to run via Bash tool:**

```bash
# List all task lists
gws tasks tasklists list

# For each task list, fetch incomplete tasks
gws tasks tasks list --params '{"tasklist":"<TASKLIST_ID>"}'
```

The known default tasklist ID is: `MDE5NTgyMDkwMjMxNjkwNzQyMTk6MDow`

**Processing:**
- Filter to tasks with `status: "needsAction"` (incomplete)
- **Filter out any task whose `id` appears in `SUPPRESSED_IDS`** (built in Step 1d).
  Track suppressed count for the Step 7 footer.
- Flag tasks with a `due` date that is today or in the past as overdue
- Note parent-child relationships (subtasks have a `parent` field)
- Sort by: overdue first, then by position

**If gws CLI fails or is not found:** Skip this section. Add "Google Tasks" to skipped sources. Display: "Google Tasks: not connected. Install gws CLI or paste tasks manually."

## Step 6: Score and Rank Top 3 Outcomes

Collect all actionable items from Steps 2-5 and score each:

| Signal | Points |
|--------|--------|
| Has due date today or is overdue | +3 |
| Marked high-priority (if priority_field exists in config) | +2 |
| Has a related calendar event today (title keyword match) | +2 |
| Stale: not updated in 7+ days | +1 |
| Blocks someone else (has a non-Aaron assignee) | +2 |

**Ranking rules:**
- Sort by score descending
- Pick top 3
- Break ties by rotating through `streams[].key` (in declaration order from
  `config/streams.yaml`) to prevent one stream from dominating
- Include the score breakdown for each item so Aaron can see the reasoning

**Stream starvation guard (added 2026-04-27, formalized 2026-05-18 per AAC):**

Deterministic formula (no Claude judgment). `STREAM_KEYS` is the list of
`streams[].key` values read from `config/streams.yaml` in declaration order:

```
1. raw_top3 = first 3 items after sort-by-score-desc
2. raw_top3_streams = set of stream keys in raw_top3
3. for each stream key S in STREAM_KEYS:
     oldest_stale[S] = max(item.days_stale for item in all_items where item.stream == S and item.days_stale >= 7)
4. starved = streams where oldest_stale[S] is defined AND S not in raw_top3_streams
5. if starved is non-empty:
     pick S_starved = argmax(oldest_stale[S] for S in starved)   # most-starved wins
     candidate = highest-score item in all_items where stream == S_starved
     final_top3 = [raw_top3[0], raw_top3[1], candidate]          # replace slot #3 only
   else:
     final_top3 = raw_top3
6. include reason in Step 7 display: "Slot #3 promoted from {S_starved} (stale {N}d)"
```

This is AAC-D (deterministic code) work, not AAC-C (LLM judgment). Reading the
formula above, generate the swap mechanically. Do NOT improvise.

This exists because logs 2026-04-14 → 2026-04-27 showed Lab consistently starved (Accu panels stale 8+ days, Cytology→IHC 262 days) while Nestmate/IPA dominated. Score-only ranking was the cause: Lab tasks have no due dates, so they never won on the +3 due-date signal. The starvation guard injects them on age alone.

**Items that can be scored:**
- Notion Master Tasks items (have due dates, statuses, assignees)
- Google Tasks items (have due dates)
- Provider CRM follow-ups (stale contact = overdue signal)
- Calendar prep items (upcoming meeting = urgency signal)

## Step 6b: Notion 24-Hour Change Audit

Before composing the briefing, query all three Notion databases for pages edited
in the last 24 hours (use `last_edited_time` timestamp filter with `on_or_after`
set to yesterday's date). Also run a workspace-wide search sorted by
`last_edited_time` descending (page_size 20) to catch changes in databases not
explicitly configured.

Categorize changes as:
- **Completed:** items whose Status changed to Done
- **Created:** new pages (created_time within last 24 hours)
- **Edited:** existing pages that were modified

Extract actionable items from these changes: missing next steps, new tasks without
due dates, completed work that triggers follow-up actions.

## Step 7: Compose and Display Briefing

Output the briefing to the terminal in this format:

```markdown
# Daily Briefing — {TODAY} ({day of week})

_Run: {RUN_ID} · Mode: {MODE}_

{If catchup_sync is non-empty:}
## ⚠️ Catch-up sync from yesterday
{Items Aaron checked off in yesterday's daily note that are still open in their source system. Will be closed at the trust gate (Step 8).}
- {task text} — {Google Tasks | Notion} still open. Will close on approval.
{If manual_completions_no_source is non-empty, list under "Manual completions (no source ID — informational only)".}

{If memory_calendar_gaps is non-empty:}
## ⚠️ Memory ↔ Calendar Gaps
- {item} — promised meeting not on calendar in {window}. Schedule it or close the memory item.

{If pending_writes is non-empty:}
## ⚠️ Pending writes from prior session

{Group by category. Confirmed entries (status=pending/awaiting_approval/denied) are real. Unverified entries lack a status field — they may already be applied; verify before acting.}

**Confirmed pending:**
- {file path} — {intent summary}. Re-confirm or discard before continuing.

**Unverified (status field absent — may already be applied):**
- {file path} — {payload summary, e.g. "appends to Notion page X"}. Search Notion for matching content; if found, move to `.context/applied/`.

## Awaiting Others
{Items from priorities.yaml `awaiting:` section — blocked on someone else}
- {title} — waiting on {person} since {first_carried} ({N} days). Last nudge: {date or "—"}
{If awaiting_until has passed: prefix with **"⏰ deadline passed — re-engage"**}
{If `awaiting:` is empty or absent: omit section}

## Calendar
{List today's events with times, business tags, and conflict flags}
{If no events: "No events scheduled today."}

## Top 3 Outcomes
1. {item} — score: {N} ({breakdown}) [{business}] {source_marker}
   {↳ past: {path} — "{snippet excerpt, 80 chars}"}     ← optional, only if a vault_search hit ≥ 1.5 exists
2. {item} — score: {N} ({breakdown}) [{business}] {source_marker}
   {↳ past: {path} — "{snippet excerpt, 80 chars}"}
3. {item} — score: {N} ({breakdown}) [{business}] {source_marker}
   {↳ past: {path} — "{snippet excerpt, 80 chars}"}

{If slot #3 was promoted by the starvation guard, append a one-line reason:}
   _Slot #3 promoted from {starved_dept} (stale {N}d) — see config/starvation rule._

{Past-context citations are computed by running `scripts/vault_search.py` against
each Top 3 item's text BEFORE rendering the briefing. The skill should:

  1. For each Top 3 item, extract 3-5 keyword terms (entity names, business
     terms, action verbs). Strip stopwords and check items.
  2. Run `python scripts/vault_search.py "<terms joined by space>" --top-n 1
     --min-score 1.5 --json`
  3. If a result comes back, render the `↳ past: ...` line beneath the item
     with the relative path and the first 80 chars of the snippet.
  4. If no result meets the threshold, omit the line entirely (don't render
     "no context found" — it's noise).

Skip vault_search for items whose source_marker is [cal] (calendar prep items
rarely have past context worth surfacing). Always run for [notion:…] and
[gtask:…] items. The whole pass should add < 2 seconds to total wall time.}

{source_marker format (AAC GROUNDED — every fact must trace to a source):
  - Notion item: render as `[notion:ABCD…]` where ABCD is the first 4 chars of the page_id
  - Google Task: render as `[gtask:XYZW…]`
  - Calendar prep: `[cal]`
  - Derived/manual: `[derived]`
  The full ID is also embedded as an HTML comment for /end-day Step 4b parsing:
  `<!-- notion:abc-123-def -->` etc.}

## Actionable Items by Stream

{Iterate `streams[]` from `config/streams.yaml` in declaration order. For each
stream, render a `### {stream.display_name}` header followed by the items
tagged with that stream's key. If a stream has no items, omit its section
entirely. To resolve stream membership for an item, use the same routing
already computed in Step 3 (Workspace field → `workspace_values`) and Step 2
(calendar `summary` → `keywords`). Items with no stream assignment fall to
the `is_default: true` stream.}

### {streams[].display_name}
- [ ] {each actionable item with context}
{If none: omit section}

## Recent Meeting Recaps (24h)
{Meetings synced from Granola → Notion in the last 24 hours, grouped by Workspace.
Each entry shows: meeting name, date, 1-line preview from Summary, and Related Tasks count.
If Workspace is null, file under "⚠️ Untagged — needs triage" with a suggested
workspace inferred from attendees/title and a hint to run /capture-meeting.}

### {Workspace}
- {Meeting name} ({Date}) — {Summary preview...} | {N} linked tasks | [page](url)

### ⚠️ Untagged — needs triage
- {Meeting name} ({Date}) — suggested: **{inferred workspace}** — run `/capture-meeting <page-id>` to route action items + tag

### 📋 Meetings needing action-item extraction
{Meeting Notes DB rows where Related Tasks count = 0, OR where related tasks
exist but none start with `[Meeting]` (no parent wrapper). Also include
topic-page appends whose latest `## YYYY-MM-DD` block is newer than any
linked `[Meeting]` parent task.}
- {Meeting name} ({Date}) — **untreated, no Master Tasks linked** — `/capture-meeting <page-id>` will create `[Meeting] {name} {date}` parent + subtasks
- {Meeting name} ({Date}) — partially treated: {N} orphan subtasks, no parent — `/capture-meeting <page-id>` will wrap them under a parent

### ✅ Meetings already wrapped (subtask progress)
{Meeting Notes DB rows where a `[Meeting] …` parent task exists. Show
completion at a glance.}
- {Meeting name} ({Date}) — `[Meeting] {parent title}` — {completed}/{total} subtasks done

{If no meetings synced into the Meeting Notes DB in last 24h AND no recent topic-page appends found: "No recent Granola → Notion syncs."}

{If a Granola URL in state/priorities.yaml or prior-day log was found via workspace-wide search inside an existing topic page (not the Meeting Notes DB), surface as:
"📎 Topic-page append: {meeting} from {date} → landed in **{parent page title}**. Not in Meeting Notes DB by design."}

{Only declare a sync gap when BOTH the Meeting Notes DB query AND the workspace-wide URL search return no match:
"⚠️ Sync gap: {meeting} from {date} referenced in priorities but not found anywhere in Notion — push from Granola app."}

## Notion Changes (Last 24 hrs)
**Completed:** {items marked Done}
**Created:** {new pages}
**Edited:** {modified pages}
{If no changes: "No Notion changes in last 24 hours."}

## Provider Follow-ups Needed
{Providers not contacted in 14+ days from CRM}
{If none or CRM unavailable: omit this section}

## Skipped Sources
{List any sources that were unavailable with reason}
{If all sources connected: omit this section}

## 🔇 Suppressed (audit trail — Step 1d)
{Render only if SUPPRESSED_IDS is non-empty. Group by reason bucket. Shows
Aaron what was hidden from the actionable list so he can verify nothing was
wrongly filtered. Omit section entirely if SUPPRESSED_IDS is empty.}

- {item title} — {reason, e.g. "dropped_20260519" | "back_burner since 2026-05-11" | "dormant_snooze until 2026-06-30" | "daily-note annotation 'off main status'"}
- ...
```

**Actionable items rules:**
- Every item gets a markdown checkbox `- [ ]` so Aaron can track completion in Obsidian
- Group ALL actionable items by stream (read `config/streams.yaml`): Notion tasks,
  Google Tasks, calendar prep, provider follow-ups, stale items — everything goes
  into its stream section
- Tag items with source in parentheses when helpful: (Notion), (Tasks), (CRM)
- **Embed durable source IDs as HTML comments at end of each line** — Obsidian
  hides them, but `/end-day` and the next day's `/start-day` catch-up sync use
  them for exact-ID matching back to the source system. Format:
  - Google Tasks: `- [ ] Visit Dr Tin (Tasks, due today) <!-- gtask:62ViTSu0nQnqrwPl -->`
  - Notion (Master Tasks / Provider CRM): `- [ ] Peptide purity RJ (Notion) <!-- notion:abc-123-def -->`
  - Items derived (calendar prep, manual additions, stale items without a single
    source): no comment. They sync as `manual_completions` only.
  - One ID per checkbox. If the line aggregates multiple source items, list each
    on its own sub-checkbox with its own ID.
- Include sub-checkboxes for grouped items (e.g., outreach lists) — each subitem
  carries its own ID comment if it has one.
- Items with no clear stream tag go under the `is_default: true` stream from `streams.yaml`
- Overdue and stale items go into their stream section, not a separate section

**Formatting rules:**
- Keep it scannable. Use bullet points, not paragraphs.
- Bold the stream tag on each item using the stream's `key` from `streams.yaml` (e.g. **[lab]**, **[ipa]**, **[nestmate]**)
- Use relative dates: "2 days overdue", "stale 12 days"
- Calendar conflicts get a warning marker

## Step 8: Trust Gate

After displaying the briefing, use AskUserQuestion to present options:

**Question:** "What would you like to do with this briefing?"

**Options:**
- **A) Create Obsidian daily note** ��� Write today's briefing to `${VAULT}/daily/{TODAY}.md`
- **B) Just the briefing** — No writes, you're done
- **C) Both daily note + mark items in progress** — Write daily note AND ask which Top 3 items to mark "In progress" in Notion

Each option is individually selectable. Default recommendation: Option A.

### Step 8b: Catch-up sync confirmation (only if Step 1c produced reconcile work)

Two trust gates can fire here, presented separately and in order.

**Gate 1 — Pull mirror (file edit only, no API risk):**

If `pull_completions` is non-empty:

**Question:** "{M} items closed in gtasks/Notion are still `[ ]` in yesterday's daily note. Mirror to `[x]`?"

Options:
- **Yes, mirror all** — in-place edit YESTERDAY's daily note: replace `- [ ]` with `- [x]` on each matching line. No API call.
- **Pick which** — checkbox list, mirror only confirmed.
- **Skip** — leave the daily note as-is.

Mirroring is a pure local file edit and cannot fail on API issues. Always
preferred over the push path when both are available.

**Gate 2 — Push completions (API writes, fallible):**

If `push_completions` is non-empty, prompt AFTER Gate 1 completes:

**Question:** "Yesterday's daily note has {N} `[x]`'d items still open in their source. Push completions now?"

Options:
- **Yes, sync all** — execute writes
- **Pick which to sync** — checkbox list, sync only confirmed
- **Skip** — leave them; they'll resurface in today's briefing

Execute approved syncs **before** Step 9's daily-note write so today's briefing
doesn't double-list them as still-open.

For each Google Tasks item (use `gws tasks tasks patch` — NOT curl with
`Bearer $(gws auth token)`, which returns 401 on this machine per
`reference_gtasks_writes.md`):

```bash
gws tasks tasks patch \
  --params '{"tasklist":"MDE5NTgyMDkwMjMxNjkwNzQyMTk6MDow","task":"<gtask_id>"}' \
  --json '{"status":"completed"}' \
  --format json
```

For each Notion page:
```bash
curl -s -X PATCH "https://api.notion.com/v1/pages/<notion_id>" \
  -H "Authorization: Bearer $NOTION_API_TOKEN" \
  -H "Notion-Version: 2025-09-03" \
  -H "Content-Type: application/json" \
  --max-time 60 \
  -d '{"properties": {"Status": {"status": {"name": "Done"}}}}'
```

Log every sync attempt (pull mirrors and push patches) in today's log under
`### Catch-up Sync` so re-runs are idempotent.

**Failure handling on push path (gtasks 500):**
1. First attempt fails with HTTP 500 / `backendError` → wait 15 seconds, retry once.
2. Second attempt also 500 → record the gtask ID in `state/gtask-retry-queue.yaml`
   under `pending_retries:` with timestamp + last-status + original task title.
   Surface in today's actionable section as "⚠️ gtask close deferred to next /start-day".
3. Next /start-day's Step 1c drains the queue at the start of Step 5 (read
   `state/gtask-retry-queue.yaml`, attempt each ID with the same single-retry
   pattern, remove on success, leave with incremented `attempts` count on
   failure).
4. Other failures (404, 401, non-500 4xx, timeout): report once, do not retry,
   surface in actionable section. These are not transient.

The 15s/single-retry budget is intentionally small — start-day must not block
on a flaky API. If 500s persist for a single ID across 3+ days, surface as a
system flag.

## Step 9: Execute Approved Actions

### If creating Obsidian daily note (Option A or C):
Write to `${VAULT}/daily/{TODAY}.md` using this template:

```markdown
---
date: {TODAY}
day: {day of week}
tags: [daily, briefing]
---

# Daily Briefing — {TODAY} ({day of week})

## Calendar
{events}

## Top 3 Outcomes
{scored items}

---

## Actionable Items by Stream

### {streams[].display_name}
- [ ] {item with context} <!-- gtask:<task_id> -->
- [ ] {item with context} <!-- notion:<page_id> -->
- [ ] {derived/manual item with no source ID — no comment}
{Iterate `streams[]` from `config/streams.yaml` in declaration order, rendering
a `### {display_name}` header for each stream that has items. Omit streams
with no items. Include the trailing `<!-- gtask:ID -->` or `<!-- notion:ID -->`
comment whenever the item came directly from Google Tasks or a Notion database
row. These comments are the ID anchors that tomorrow's `/start-day` Step 1c
uses to detect Aaron's `[x]` checks and push them back to source.}

---

## Recent Meeting Recaps (24h)
{Granola → Notion synced meetings, grouped by Workspace, with action-item link counts.
Untagged meetings flagged with a suggested workspace + `/capture-meeting <page-id>` hint.}

---

## Notion Changes (Last 24 hrs)
**Completed:** {items}
**Created:** {items}
**Edited:** {items}

---

## End of Day Review

_Fill in at EOD — what got done, what carries forward._

**Completed:**
- [ ] _(move completed items here)_

**Carries forward to tomorrow:**
- [ ] _(move incomplete items here)_

**Notes / Decisions made today:**
-
```

If the file already exists and has content, **append** a new timestamped section:
```markdown

---

## Afternoon Briefing ({current time})
{new briefing content}
```

### If marking items in progress (Option C):
For each Top 3 item that came from Notion, update its Status via the Notion API:
```bash
curl -s -X PATCH "https://api.notion.com/v1/pages/{page_id}" \
  -H "Authorization: Bearer $NOTION_API_TOKEN" \
  -H "Notion-Version: 2025-09-03" \
  -H "Content-Type: application/json" \
  -d '{"properties": {"Status": {"status": {"name": "In progress"}}}}'
```
Confirm each update with the user before executing.

### Always: Mirror daily note to Notion mobile page

This gives Aaron a phone-readable copy of today's briefing via the Notion
mobile app, since Cowork can't write to his local Obsidian vault and Telegram
delivery is still being scaffolded. Page is overwritten wholesale on every
run — last writer wins. `/end-day`'s evening pass also runs this same
mirror so the page reflects end-of-day state by 20:00.

1. Read `mobile_briefing_page_id` from `${CONFIG}` (config/sources.yaml).
   If unset, **skip silently** — this mirror is opt-in.
2. Read the just-written `${VAULT}/daily/{TODAY}.md`.
3. Strip the YAML frontmatter block (`---\n...\n---\n` at the top).
4. Replace the page's content using the Notion MCP:
   ```
   mcp__claude_ai_Notion__notion-update-page
     page_id: <mobile_briefing_page_id>
     command: "replace_content"
     new_str: <stripped markdown body>
     properties: {}
     content_updates: []
   ```
5. If the Notion call fails (5xx / 401 / timeout) → append a one-line
   `### Mobile Mirror` entry to `${LOGS_DIR}/{TODAY}.md` noting the failure
   reason. **Do not retry. Do not block.** The next scheduled run will
   overwrite with fresh content.

If the Notion MCP is not loaded in the current session (e.g. a stripped-down
runner): also skip silently and note "MCP unavailable" in the day's log.
The page only needs to be current for *one* of the day's runs to be useful
on the phone.

### Always: Save to logs
Write the briefing to `${LOGS_DIR}/{TODAY}.md` using this format:

```markdown
---
date: {TODAY}
sources_available: [{list of sources that responded}]
sources_skipped: [{list of sources that failed or were unavailable}]
---

## Morning Briefing ({current time})

{full briefing content from Step 7}
```

If the log file already exists (re-run), append a new timestamped section
instead of overwriting.

## Step 10: Emit Telemetry (AAC OBSERVED)

After all writes complete (or after display in observe/draft modes that skipped writes),
emit one JSONL row to `logs/_telemetry.jsonl` via the shared helper:

```bash
DURATION_MS=$(( $(date +%s%3N 2>/dev/null || python -c "import time; print(int(time.time()*1000))") - RUN_START_MS ))

scripts/telemetry.sh start-day "${RUN_ID}" "${DURATION_MS}" "${STATUS}" "$(python -c "
import json
print(json.dumps({
    'mode': '${MODE}',
    'sources_ok': ${SOURCES_OK_JSON},          # e.g. ['calendar','notion','tasks','obsidian']
    'sources_skipped': ${SOURCES_SKIPPED_JSON},
    'top3_scores': ${TOP3_SCORES_JSON},        # e.g. [8, 7, 5]
    'starvation_swap': ${STARVATION_SWAP_FLAG}, # true/false
    'pending_writes_count': ${PENDING_WRITES_COUNT},
    'pull_completions': ${PULL_COMPLETIONS_COUNT},
    'push_completions': ${PUSH_COMPLETIONS_COUNT},
    'meetings_needing_extraction': ${MEETINGS_UNTREATED_COUNT},
    'note_written': ${NOTE_WRITTEN_BOOL},        # true if Option A/C ran in Step 9
})
")"
```

`STATUS` is `ok` (all sources responded), `partial` (≥1 source skipped), or
`failed` (no briefing rendered).

This row enables `/weekly-review` and future health dashboards. Never edit or
delete telemetry rows — append-only.

## Error Handling

- **scripts/check_mode.sh exits 1 (locked):** Refuse to run. Do NOT emit telemetry — locked mode is "this skill never ran today."
- **scripts/check_mode.sh exits 2 (unreadable):** Fail closed — treat as locked.
- **gws CLI not found or auth expired:** Skip Calendar and/or Tasks gracefully. Suggest `gws auth login --scopes calendar,tasks`. Telemetry: `sources_skipped` includes the failed source.
- **gws API not enabled (403):** Warn user to enable the API in Google Cloud Console, skip source.
- **Notion API timeout:** If a curl call hangs, use `--max-time 60` to timeout after 60 seconds, skip that source.
- **Notion API auth failure (401):** Warn user to check NOTION_API_TOKEN in settings.local.json, skip source.
- **Empty database response:** Not an error — display "No items found in {database name}".
- **Bad database ID:** Warn "Database {name} not found — check database_id in config/sources.yaml".
- **Never retry automatically.** Report clearly and continue with available sources.
- **Never crash on a missing source.** The briefing runs with whatever is available. Telemetry status = `partial`.
