---
name: end-day
description: >-
  End-of-day retro: compares the morning plan against what actually happened.
  Pulls current state from Calendar, Notion, Obsidian, and Google Tasks. Asks
  about unplanned work. Logs planned vs actual, carry-forwards, and observations.
  Updates state/priorities.yaml for tomorrow's /start-day.
coo_twin:
  category: briefing
  mode_required: any
  writes_external: true
  preflight: required
  experimental: false
---

# /end-day — Day Close Retro

You are acting as Aaron's Chief of Staff. Your job is to close the loop on today:
compare the morning plan against reality, capture what drifted and why, and set up
tomorrow by carrying forward unfinished work.

**Read-first, write-on-approval.** Show the retro summary before writing anything.

## Constants

```
REPO_DIR = "C:/Users/aaron/daily-automation"
CONFIG   = "${REPO_DIR}/config/sources.yaml"
LOGS_DIR = "${REPO_DIR}/logs"
VAULT    = "${REPO_DIR}/vault"
STATE    = "${REPO_DIR}/state"
TODAY    = <current date in YYYY-MM-DD format>
RUN_ID   = "ed-${TODAY//-/}-$(date +%H%M)"
```

## Step 0: Mode Check (AAC GOVERNED)

```bash
MODE=$(scripts/check_mode.sh) || {
  echo "🛑 Agent is locked. /end-day refuses to run."
  exit 0
}
```

- `locked` → refuse.
- `observe` → set `SKIP_WRITES=1`; build retro, display, do NOT update priorities.yaml or push completions.
- `draft` (default) → standard trust gate.
- `approved` → /end-day's writes (state file edits, sync pushes, dead-task resolutions) check action_id prefixes per `state/coo_mode.yaml`. Defaults still gate.

Capture `RUN_START_MS` for telemetry at Step 10.

## Step 1: Load Morning Plan

Read today's log file at `${LOGS_DIR}/{TODAY}.md`.

Extract from the morning briefing:
- **Top 3 Outcomes** — the scored priorities from this morning
- **Calendar events** — what was scheduled
- **Actionable items by department** — the full checklist
- **Sources available/skipped** — what data we had this morning

If no morning log exists: warn "No morning briefing found for today. Running
/end-day without a morning plan — I'll still capture what happened today."
Continue with Steps 2-4 to build the retro from current state alone.

Also read `${STATE}/priorities.yaml` for any carry-forward items from yesterday.

## Step 2: Pull Current State

### 2a: Google Calendar — What Actually Happened

Use gws CLI:
```bash
gws calendar +agenda --today --format json
```

Compare against the morning calendar:
- Events that were added after the morning briefing
- Events that were cancelled or moved
- Events that happened as planned

**If gws fails:** Skip. Note in retro.

### 2b: Notion — Changes Since Morning

Query all three databases for pages edited today.

**Master Tasks:**
```bash
curl -s -X POST "https://api.notion.com/v1/data_sources/528d24b8-e1e6-4ca0-a7ee-87f70a4f7980/query" \
  -H "Authorization: Bearer $NOTION_API_TOKEN" \
  -H "Notion-Version: 2025-09-03" \
  -H "Content-Type: application/json" \
  --max-time 60 \
  -d '{
    "filter": {
      "timestamp": "last_edited_time",
      "last_edited_time": {"on_or_after": "<TODAY>T00:00:00Z"}
    },
    "page_size": 50
  }'
```

Categorize each page:
- **Completed today:** Status changed to "Done" (check status field)
- **Moved to In Progress:** Status is now "In progress" and wasn't this morning
- **New items created:** `created_time` is today
- **Edited:** Any other page modified today

**Provider CRM:**
```bash
curl -s -X POST "https://api.notion.com/v1/data_sources/ae0a3158-59b4-8235-b7ca-0758daa2322a/query" \
  -H "Authorization: Bearer $NOTION_API_TOKEN" \
  -H "Notion-Version: 2025-09-03" \
  -H "Content-Type: application/json" \
  --max-time 60 \
  -d '{
    "filter": {
      "timestamp": "last_edited_time",
      "last_edited_time": {"on_or_after": "<TODAY>T00:00:00Z"}
    },
    "page_size": 50
  }'
```

**Activity Log:**
```bash
curl -s -X POST "https://api.notion.com/v1/data_sources/3db174bf-c997-4a41-93ee-36f280e511db/query" \
  -H "Authorization: Bearer $NOTION_API_TOKEN" \
  -H "Notion-Version: 2025-09-03" \
  -H "Content-Type: application/json" \
  --max-time 60 \
  -d '{
    "filter": {
      "property": "Date",
      "date": {"equals": "<TODAY>"}
    },
    "page_size": 20
  }'
```

**If Notion fails:** Skip. Note in retro.

### 2c: Google Tasks — Completed and New

```bash
gws tasks tasks list --params '{"tasklist":"MDE5NTgyMDkwMjMxNjkwNzQyMTk6MDow","showCompleted":true,"completedMin":"<TODAY>T00:00:00Z"}'
```

Also fetch current incomplete tasks to compare against morning state:
```bash
gws tasks tasks list --params '{"tasklist":"MDE5NTgyMDkwMjMxNjkwNzQyMTk6MDow"}'
```

Identify:
- Tasks completed today (`status: "completed"`, `completed` date is today)
- New tasks added today (`updated` date is today and not in morning list)
- Tasks still incomplete that were in the morning's list

**If gws fails:** Skip. Note in retro.

### 2d: Obsidian — New Notes Today

Use Glob and file modification times to find notes created or modified today:

```
${VAULT}/notes/*.md    — new permanent notes
${VAULT}/meetings/*.md — meeting notes captured today
${VAULT}/inbox/*.md    — new inbox captures
```

Check each vault folder (including business folders like CardioPro/, Labaide/,
Nestmate/, United IPA/, Notes to self/) for any files modified today.

## Step 3: Ask About Unplanned Work

Use AskUserQuestion:

**"Anything major happened today that isn't in your calendar or Notion?"**
**"(e.g., fires, long calls, unexpected work, ad-hoc meetings)"**

Options:
- **Nothing major** — Proceed with tool-tracked data only
- **Yes, let me add context** — User types unplanned work

Store the response as `unplanned_work` for the retro.

## Step 4: Compare Planned vs Actual

### 4a: Top 3 Outcomes Assessment

For each of the morning's Top 3 Outcomes, determine status:

- **Completed:** Found in completed Notion tasks or Google Tasks
- **In Progress:** Status is "In progress" in Notion, or partially done
- **Not Started:** No change detected
- **Blocked:** Status is "Waiting" or user mentioned a blocker

Use AskUserQuestion to confirm the status of each Top 3 item:

**"How did your Top 3 go today?"**

Display each item and ask the user to confirm or correct:
```
1. {item 1} — I see {detected status}. Correct?
2. {item 2} — I see {detected status}. Correct?
3. {item 3} — I see {detected status}. Correct?
```

Options:
- **Looks right** — Accept auto-detected statuses
- **Let me correct** — User provides corrections

### 4b: Department Checklist Reconciliation + Sync Loop

Read today's daily note at `${VAULT}/daily/{TODAY}.md` and extract every checkbox line:
- `- [x]` → Aaron marked it complete during the day
- `- [ ]` → still open

Build a `checkbox_completions` list of every `[x]` item. For each completed item,
**parse the line for an embedded source-ID HTML comment** written by `/start-day`
(Step 9, daily-note template):

- `<!-- gtask:<ID> -->` → Google Tasks task ID. Queue an exact-ID complete in 8e.
- `<!-- notion:<ID> -->` → Notion page ID. Queue an exact-ID Status=Done flip in 8e.

Use a regex like `<!--\s*(gtask|notion):([A-Za-z0-9_\-]+)\s*-->` to extract.
Exact-ID matching is durable; do NOT fall back to fuzzy title matching when an
ID is present.

For checked items with **no embedded ID** (legacy daily notes from before the
2026-04-30 format change, or manual additions Aaron typed in himself):

1. **Best-effort title match against this morning's actionable items** in the
   briefing (`${LOGS_DIR}/{TODAY}.md`). Source tags like `(Notion)`, `(Tasks)`,
   `(CRM)` indicate which system to query.
2. If a Google Tasks title match is found, look up the task ID by searching the
   morning's `gws tasks tasks list` output. Queue completion in 8e.
3. If a Notion title match is found via the morning's Master Tasks query, queue
   the Status=Done PATCH in 8e.
4. **No match found** → record as `manual_completions` (logged only, no write).

Conversely, items completed in Notion/Tasks but NOT checked in the daily note
remain a reconciliation gap — surface them in the retro under "Sync gaps" so
Aaron can verify the daily note matches reality.

**Bidirectional Notion → Google Tasks sync (added 2026-04-30):**

For every Notion Master Task whose Status changed to "Done" today (detected
in Step 2b), read its `Last Activity` rich_text property. If it contains
`gtask:<ID>`, queue a Google Tasks completion in Step 8e for that task ID.
This closes the reverse loop: when Aaron (or a teammate) flips a Notion
subtask to Done in the Notion UI, the mirrored Google Task auto-completes
on /end-day.

The `Last Activity` back-pointer is written by `/capture-meeting` Step 6a-3
when the Google Tasks mirror is created. See `feedback_meeting_parent_subtask.md`
in memory.

### 4c: Dead-Task EOL Scan

Scan all Notion Master Tasks where Status = "In progress" and
`last_edited_time` is more than 5 days old. For each, build a `dead_tasks` list:
- Title
- `page_id`
- Days since last edit
- Workspace (department)

These are zombie tasks — listed as active but with no movement. They must be
explicitly resolved on each `/end-day`, not silently re-surfaced. Show them in
the retro (Step 6) and require an action via the trust gate (Step 7).

### 4d: Calendar Drift

Compare morning calendar vs actual:
- List events that were added, removed, or moved
- Note any meetings that ran over their scheduled time (if user mentioned)

### 4e: Calendar Drift (legacy alias)

(Now handled in Step 4d. This anchor preserved for older log references.)

### 4f: Inline Annotation Extraction (NEW 2026-05-29)

Aaron types imperative scheduling directives into the daily note as checkbox
tails or braindump prose — `"Bill for trish ... handle 9am tomm set on calender"`,
`"create cal event 10am"`, `"set for 4pm tomm"`, `"create 11am task on calender"`.
These are instructions to **create a calendar event / Google Task**, not passive
notes, and were being silently dropped (a week's worth lost; caught 2026-05-29).
See memory `feedback_daily_note_annotations_are_actions`.

This step reuses the daily-note lines already read in 4b — no extra file read.

**Procedure:**

1. Run the deterministic extractor (pure regex; **no LLM, no PHI gate needed**):
   ```bash
   python scripts/capture_meeting_parse.py --mode annotations \
     --date {TODAY} --notes-file "${VAULT}/daily/{TODAY}.md"
   ```
   It emits a JSON array of intents:
   ```json
   {"verb":"create_event|create_task|reschedule",
    "suggested_summary":"...","source_line":172,"original_text":"...",
    "date_iso":"2026-05-29","date_resolved_from":"relative_phrase",
    "start_iso":"2026-05-29T09:00:00","end_iso":"2026-05-29T10:00:00",
    "meridiem_guessed":false,"time_resolved_from":"single_meridiem",
    "confidence":0.95,"flags":[]}
   ```
   The extractor already skips struck-through lines, `<!-- synced -->` /
   `<!-- sched-done -->` lines, markdown headers/tables/blockquotes, and
   `(already in tasks/on calendar)` markers.

2. **MVP scope:** act only on `create_event` and `create_task`. `reschedule` and
   any `recurring`/low-confidence items are **surfaced only** (Step 6), never
   auto-staged. (Reschedule execution + recurrence land in the fuller version.)

3. **Idempotency check (BEFORE proposing):** for each create intent, build
   ```bash
   AID=$(scripts/action_id.sh generate end-day \
        "cal" "{TODAY}" "<verb>|<start_iso>|<suggested_summary>")
   scripts/action_id.sh check "$AID" && mark intent already_created
   ```
   Use target `cal` for create_event, `gtask` for create_task. The hash includes
   the resolved start + summary, so a re-run of `/end-day` (or tomorrow's
   `/start-day` reading this same note) produces the identical AID and no-ops.
   Carry `$AID` on the intent for stamping in 8h.

4. **Dedupe against live state (read-only):**
   - `create_event`: pull `gws calendar +agenda --date {target-day} --format json`
     (or `--today`/`--week` and filter). Skip (mark `dup_skipped`) if an event
     with start within ±15 min AND a fuzzy-matching summary already exists.
     This is the programmatic version of the manual "verified, not duplicated"
     check from the 2026-05-29 note.
   - `create_task`: compare against the incomplete-tasks list already pulled in
     2c. Skip if an open task with a matching title exists.

5. **Conflict + ambiguity flags** (carry to Step 6, do NOT auto-resolve):
   - `meridiem_guessed` → "assumed {9 AM} — confirm".
   - Proposed event start within ±30 min of a *different* existing event →
     `⚠ overlaps "{other}"`. Two new intents colliding → flag together.
   - `verb_ambiguous` (matched both event + task signals) → surface as
     "event or task?" — never create both.
   - `confidence < 0.70` OR any flag → surfaced but NOT pre-selected at the gate.

Build `annotation_intents` (create_event/create_task, with per-item status:
`proposed | already_created | dup_skipped | needs_confirm`) and
`annotation_reschedules` (surface-only) for Step 6.

## Step 5: Build Carry-Forward List

Items that carry forward to tomorrow:
1. **Unfinished Top 3 items** — auto-carry unless user explicitly drops them
2. **Items from morning checklist not completed** — only high-priority ones
3. **New items created today that need follow-up** — from Notion/Tasks changes
4. **Yesterday's carry-forwards that weren't addressed** — increment days_carried

For each carry-forward candidate, the user should confirm at the trust gate
(Step 6). Items carried for 3+ days get a special flag.

## Step 6: Compose and Display Retro

Output the retro to the terminal:

```markdown
# End of Day — {TODAY} ({day of week})

## Top 3 Outcomes: How'd It Go?
1. {item} — {status} {context}
2. {item} — {status} {context}
3. {item} — {status} {context}

**Score: {completed}/{total}**

## What Got Done Today

### Completed
- {completed items from Notion, Tasks, and Calendar — grouped by business}

### New Items Created
- {new Notion pages, new Tasks, new Obsidian notes}

### Provider Activity
- {CRM updates, activity log entries}

## What Drifted

### Calendar Changes
- {events added/removed/moved since morning}

### Unplanned Work
- {user-reported unplanned items, or "None reported"}

### Items Not Touched
- {items from morning plan that had no activity}

## Sync Loop (Obsidian ↔ Tasks/Notion)

### Checkboxes you ticked off in today's daily note
- {N items} — {list with their source: Notion / Tasks / Manual}

### Sync gaps (completed in source but not checked in daily note)
- {item completed in Notion/Tasks but `[ ]` in daily note} — verify before close

### Pending writes (will execute on approval at trust gate)
- Mark {N} Google Tasks as completed (one curl/gws call each)
- Set {N} Notion Master Tasks to "Done" (PATCH /v1/pages/{id})
- Manual completions logged only: {N}

## Inline Annotations Detected (Step 4f — NEW)

{Render only if annotation_intents or annotation_reschedules is non-empty.
Omit entirely otherwise. Per-item, modeled on /capture-meeting Step 5 display.}

### Will create on approval (pre-selected)
{create_event / create_task intents with status=proposed AND confidence ≥ 0.70
AND no blocking flag.}
- 📅 **{suggested_summary}** → Calendar {date} {start}–{end}  _(line {N}, conf {0.95})_
- ✅ **{suggested_summary}** → Google Task{, due {date}}  _(line {N}, conf {0.80})_

### Needs your confirmation (NOT pre-selected)
{Items with a flag: meridiem_guessed, overlap, verb_ambiguous, or conf < 0.70.}
- 📅 **{summary}** → {date} {start} — ⚠ {assumed 9 AM / overlaps "Huang" 12:00 / event-or-task?}  _(line {N}, conf {0.60})_

### Already handled (no-op)
- {summary} — already created (action_id stamped) / already on calendar (dup) — skipped

### Reschedule mentions (surface-only in MVP — not auto-applied)
{annotation_reschedules — e.g. "push to next week", "move to 3pm".}
- {original_text} — reschedule intent; {has <!-- gtask/notion:ID --> anchor → "can retarget" | "no source anchor — handle manually"}

## Dead Tasks (In Progress > 5 days, no edits)

For each dead task, require explicit action at the trust gate:
- {Title} — {N} days dormant [{department}]

## Carry Forward to Tomorrow

{Each item with days_carried count}
- {item} — carried {N} day(s) [{business}]
- {item} — NEW carry-forward [{business}]

{Items carried 3+ days get a warning:}
> Carried 3+ days: {item}. Still a priority, or should it be dropped/delegated?

## Real Movement off Top 3 (AAC OBSERVED — first-class metric)

{Per memory `feedback_top3_vs_actual.md`: ask explicitly about Top 3 movement
even when system data shows 0/3. In-person work bypasses Notion/Tasks. A 0/3
score on a 5/12-style "all clinic visits" day is wrong.}

- Top 3 system-tracked completions: {N}/3
- Real movement (Aaron's self-report): {M}/3
- If divergence > 0: log to telemetry as `real_vs_tracked_delta` for trend.

## DLQ Status (AAC OBSERVED — surface hidden queues)

Read `${STATE}/gtask-retry-queue.yaml` if present. Report:

- **Pending retries:** {N} items, oldest {M} days
- {For each item carrying ≥3 days: show title + attempts + last_status}

If N > 0 AND the oldest is ≥3 days, surface this as a system flag for Aaron —
the API is persistently flaky for that ID, not just a transient burst.

## Today's Observations

{Single-day observations only — cross-day patterns are for /weekly-review}
- {e.g., "4 of 5 meetings were IPA-related but top outcomes were lab tasks"}
- {e.g., "3 new tasks created today, only 1 completed — inflow exceeding output"}
- {e.g., "No Obsidian notes created — consider capturing one key insight"}

## Skipped Sources
{List any sources that were unavailable}
```

## Step 7: Trust Gate

Use AskUserQuestion:

**"What would you like to do with this retro?"**

Options:
- **A) Save everything + sync loop** — Update daily note, log, carry-forwards,
  push all queued sync writes (close Google Tasks, flip Notion to Done) for items
  Aaron checked off in the daily note, resolve dead tasks per Step 7b, AND create
  the pre-selected inline-annotation events/tasks from Step 4f (Step 8h).
- **B) Edit carry-forwards/syncs/annotations first** — Let me add/remove/modify
  carry-forward items, opt out of any queued sync writes, toggle which Step-4f
  annotation events/tasks to create (and confirm any flagged ones), or override
  dead-task resolutions before saving.
- **C) Just the summary** — Don't write anything, review only.

If B: ask which items to add, remove, or modify. For the "needs confirmation"
annotation items (meridiem guesses, overlaps, ambiguous verb), this is where Aaron
picks the time / resolves the overlap / chooses event-vs-task. Then save.

**Auto-mode note:** in `approved` mode, the auto-mode classifier cannot see
AskUserQuestion selections (memory `feedback_automode_trust_gate`). Annotation
creates are calendar/Tasks commitments — they always require plain-text approval
in chat, never silent auto-create, even at high confidence. `approved_action_prefixes`
does NOT include `end-day:cal:` / `end-day:gtask:` for the MVP.

### Step 7b: Dead-task resolution (only if Step 4c found any)

For each item in `dead_tasks`, use AskUserQuestion to force a decision:

**"{title} — In Progress for {N} days with no edits. What's the call?"**

Options (per task):
- **Mark Done** — flip Notion status to Done (will execute in 8f)
- **Set hard due date** — prompt for a date, update Notion `Due` (executes in 8f)
- **Park to back-burner** — prepend `[BACK-BURNER]` and rotate to priorities.yaml
  back-burner section
- **Keep as-is, ignore for 5 more days** — log a snooze; don't surface again until
  10 days dormant

Record each decision; do not act until trust gate (Step 7) is approved.

## Step 8: Execute Approved Actions

### 8a: Update Obsidian Daily Note

Read `${VAULT}/daily/{TODAY}.md`. Find the "End of Day Review" section
(it's part of the /start-day template) and fill it in:

```markdown
## End of Day Review

**Completed:**
- [x] {each completed item}

**Carries forward to tomorrow:**
- [ ] {each carry-forward item with context}

**Notes / Decisions made today:**
- {observations and decisions from the retro}
```

Use the Edit tool to replace the placeholder content in the existing daily note.
If the daily note doesn't exist, create it with just the EOD content.

### 8b: Append to Log File

Append the retro to `${LOGS_DIR}/{TODAY}.md`:

```markdown

---

## End of Day ({current time})

### Top 3 Results
{status of each Top 3 item}

### Completed Today
{list of completed items with sources}

### New Items Created
{list}

### Unplanned Work
{user input or "None"}

### Calendar Drift
{changes}

### Carry Forward
{list with days_carried}

### Observations
{observations}
```

### 8c: Update State File

Write carry-forward items to `${STATE}/priorities.yaml`:

```yaml
carry_forward:
  - title: "Task description"
    source: notion
    source_id: "page-id-if-available"
    business: ipa
    first_carried: "2026-04-15"
    days_carried: 1
    original_due: "2026-04-14"
    notes: "context from today"
  - title: "Another task"
    source: tasks
    source_id: null
    business: lab
    first_carried: "2026-04-13"
    days_carried: 3
    original_due: null
    notes: "carried 3 days — flagged for review"

last_updated: "2026-04-15"
```

Rules for updating priorities.yaml:
- **New carry-forwards:** `first_carried` = today, `days_carried` = 1
- **Existing carry-forwards still unfinished:** increment `days_carried` by 1
- **Completed carry-forwards:** remove from the list
- **Items the user explicitly drops:** remove from the list
- **Items carried 5+ days:** add a note suggesting archival or delegation

In addition to `carry_forward`, priorities.yaml has three more top-level sections
(added 2026-04-27):

```yaml
awaiting:
  - title: "Piris Health insurances — Raymond response"
    blocked_on: "Raymond"        # who/what we're waiting on
    nudged_at: "2026-04-22"      # last time we contacted them
    waiting_since: "2026-04-22"
    awaiting_until: "2026-04-30" # if absent, no auto-rotation; if past, /start-day flags as expired
    business: dock_pro
    source: tasks
    source_id: null
    notes: "Email sent 4/22. Granola: ..."

dormant_snooze:
  # Used by Step 8f's "Keep as-is, snooze 5 days" path. /end-day Step 4c
  # skips dead-task surfacing for any page_id with `until` still in the future.
  - page_id: "23aa3158-59b4-80ad-94ba-c3381d1a9fcd"
    title: "Panels for Drs"
    until: "2026-05-02"

back_burner:
  # Items moved here by Step 8f or by manual user direction. Renamed inline in
  # Notion with [BACK-BURNER] prefix; rotated out of carry_forward.
```

When `/end-day` builds carry-forwards, route items by signal:
- Notes/title contain "await", "awaiting", "blocked on", "from him/her" + a person name
  → `awaiting:` bucket
- User explicitly snoozed dead task → `dormant_snooze:`
- User explicitly parked → `back_burner:`
- Everything else still active → `carry_forward:`

When `awaiting_until` passes without resolution, `/start-day`'s "Awaiting Others"
section flags the item with **"⏰ deadline passed — re-engage"**.

### 8d: Check for Notion Status Updates (Optional)

If any Top 3 items were completed but their Notion status is still "In progress",
offer to update them to "Done":

```bash
curl -s -X PATCH "https://api.notion.com/v1/pages/{page_id}" \
  -H "Authorization: Bearer $NOTION_API_TOKEN" \
  -H "Notion-Version: 2025-09-03" \
  -H "Content-Type: application/json" \
  --max-time 60 \
  -d '{"properties": {"Status": {"status": {"name": "Done"}}}}'
```

Only offer this, don't auto-execute. Present as a trust gate option:
"These items appear completed but are still marked In Progress in Notion.
Update them to Done? {list}"

### 8e: Sync Completed Checkboxes Back to Source

For every item in `checkbox_completions` from Step 4b that traces back to a source,
push the completion. Approved as a batch via Option A in Step 7.

**Google Tasks completions:**

CRITICAL: gws splits URL/query params from the request body across two flags. Nesting
`body` inside `--params` is a silent failure mode — the API returns 200 OK with an
empty/unchanged task. Hit 2026-05-20 during /end-day when 6 newly-created tasks all
landed blank. Use `--params` for `tasklist` + `task` only, and `--json` for the body:

```bash
gws tasks tasks patch \
  --params '{"tasklist":"MDE5NTgyMDkwMjMxNjkwNzQyMTk6MDow","task":"<TASK_ID>"}' \
  --json '{"status":"completed"}'
```

The same rule applies to `gws tasks tasks insert` (creating new tasks during /end-day
braindump capture or /capture-meeting Step 6a-3): `--json '{"title":"...","notes":"..."}'`,
NEVER `--params '{...,"body":{"title":"..."}}'`. See `reference_gws_tasks_insert.md`.

Always verify the response `title` or `status` field is populated — there is no error
on the broken form.

If `gws tasks tasks patch` is unavailable in the installed gws version, fall back to
a direct curl against the Google Tasks REST API:
```bash
curl -s -X PATCH "https://tasks.googleapis.com/tasks/v1/lists/MDE5NTgyMDkwMjMxNjkwNzQyMTk6MDow/tasks/<TASK_ID>" \
  -H "Authorization: Bearer $(gws auth token)" \
  -H "Content-Type: application/json" \
  --max-time 60 \
  -d '{"status":"completed"}'
```

**Notion task completions:**
Use the same PATCH /v1/pages/{page_id} call as Step 8d, with the page_id from the
matched Notion source. One call per task; no batching.

**Manual completions (no source match):** log only — no external write. They appear in
Step 8b's "Completed Today" section so the daily log captures them.

**Failure handling:** If a single sync write fails (404, 401, 5xx), report which item
failed, continue with the remaining writes. Do not retry. The next morning's
/start-day will resurface any item that didn't sync — Aaron can re-tick it then.

### 8f: Execute Dead-Task Resolutions

For each decision recorded in Step 7b:

- **Mark Done:** PATCH the Notion page Status → "Done" (same call shape as 8d).
- **Set hard due date:** PATCH the Notion page with `{"properties":{"Due":{"date":{"start":"YYYY-MM-DD"}}}}`.
- **Park to back-burner:** Update the page title to prepend `[BACK-BURNER]` (PATCH
  the title property), AND add an entry to the `back_burner` section of
  `priorities.yaml` so it doesn't drop out of view entirely.
- **Keep as-is, snooze 5 days:** Write a `dormant_snooze` entry to
  `priorities.yaml` with `until: <today + 5d>`. Step 4c next time should skip any
  task whose `page_id` appears in `dormant_snooze` with `until` still in the future,
  and remove the entry once the date passes.

All four operations follow the same trust-gate batching as 8e — they execute only
under Option A or under a confirmed B selection.

### 8g: Mirror daily note to Notion mobile page

By this point the daily note's "End of Day Review" section is filled in (8a)
and any source-system writes (8d/8e/8f) have landed. Push the final state to
the Notion mobile page so Aaron can read tonight's closeout on his phone.

1. Read `mobile_briefing_page_id` from `${CONFIG}` (config/sources.yaml).
   If unset, **skip silently** — opt-in.
2. Read the just-updated `${VAULT}/daily/{TODAY}.md`.
3. Strip the YAML frontmatter (`---\n...\n---\n` at the top).
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
   reason. **Do not retry. Do not block.** Tomorrow's `/start-day` mirror
   will overwrite anyway.

If the Notion MCP is not loaded in the current session: skip silently and
note "MCP unavailable" in the day's log. Mirror runs from both `/start-day`
and `/end-day`, so a miss on one doesn't lose the phone view for long.

### 8h: Execute Inline Annotations (NEW 2026-05-29)

Runs only under Option A, or the subset Aaron confirmed under Option B. Skips in
`observe`/`SKIP_WRITES`. Execute BEFORE Step 9.5 (sync-sweep) so a `reschedule`
phrase isn't re-routed as braindump prose. Process only `create_event` /
`create_task` intents whose status is `proposed` (or `needs_confirm` and the user
approved it); never the `already_created` / `dup_skipped` ones.

For each approved intent:

1. **Re-check idempotency** (the `$AID` from Step 4f):
   ```bash
   scripts/action_id.sh check "$AID" && continue   # already applied → no-op
   ```

2. **create_event** — use the canonical insert (memory `reference_gws_calendar_insert`):
   ```bash
   gws calendar +insert --summary "<suggested_summary>" \
     --start "<start_iso e.g. 2026-05-29T16:00:00-04:00>" \
     --end   "<end_iso>" --format json
   ```
   Append a `-04:00` (EDT) / `-05:00` (EST) offset to the ISO datetimes the
   extractor emits (they are naive local). Default 60-min end is already in
   `end_iso`. Optionally tag the summary's stream from
   `calendar_business_keywords`.

3. **create_task** — gws Tasks insert. CRITICAL: body goes in `--json`, NEVER
   nested in `--params` (silent blank-task failure — memory
   `reference_gws_tasks_insert`):
   ```bash
   gws tasks tasks insert \
     --params '{"tasklist":"MDE5NTgyMDkwMjMxNjkwNzQyMTk6MDow"}' \
     --json '{"title":"<suggested_summary>","due":"<date_iso>T00:00:00.000Z"}'
   ```
   Verify the response `title` is populated (blank = the broken-form failure).

4. **On success:**
   ```bash
   scripts/action_id.sh stamp "$AID" '{"cal_event_id":"<id>"}'   # or {"gtask_id":"..."}
   ```
   Then append a single-line handled sentinel to **that one source line** in the
   daily note so it isn't re-created next run. Grep the exact line text first to
   confirm a UNIQUE match; never `replace_all`. Append, do not rewrite:
   `... set on calender <!-- sched-done:cal:<8hex> {TODAY} -->`
   **If the source line is inside the actively-typed `## Braindump` block**
   (clobber risk — memory `feedback_endday_braindump_append`), skip the in-note
   sentinel and rely on the `$AID` stamp alone; log the creation under
   `### Annotation Execution` in `${LOGS_DIR}/{TODAY}.md` instead.

5. **On failure** (4xx/5xx/timeout): report which intent failed, continue with
   the rest, do NOT retry, do NOT stamp (so a later run can re-attempt). Same
   non-blocking discipline as 8e.

Record counts (`annotations_created_event`, `annotations_created_task`,
`annotations_skipped_idempotent`, `annotations_dup_skipped`, `annotations_failed`)
for Step 10 telemetry.

## Step 9: Summary

```markdown
# Day Closed

**Top 3 Score:** {completed}/{total}
**Items completed today:** {count}
**Carry-forwards for tomorrow:** {count} ({N} new, {M} continued)
**Daily note updated:** {yes/no}
**Log saved:** {yes/no}
**Priorities state updated:** {yes/no}

{If any carry-forwards are 3+ days old:}
> Consider reviewing long-standing items during your next /weekly-review.

Good night, Aaron.
```

## Step 9.5: Sync Sweep Final Pass (braindump → Notion topic pages)

After the day-close summary renders but BEFORE telemetry, invoke `/sync-sweep` as
the final substantive step of `/end-day`. This drains today's `## Braindump`
section in the daily note into matching Notion topic pages (one `## Latest:`
append per resolved entity), so casual mentions Aaron typed during the day
("Talked to Pak today about Q3 supply", "Cyrus updated me on Essen") don't get
buried in the daily note alone.

`/sync-sweep` enforces its own mode check, PHI gate, and trust gate; this step
just routes Aaron into it with a known trigger source.

**Invocation:**

Set `TRIGGER_SOURCE=end-day-final-step` before invoking so the downstream
telemetry row (Step 11 of `/sync-sweep`) records the originating skill.
Concretely, when the agent launches `/sync-sweep` here, do so with that
trigger marker carried inline (env var or explicit prompt note — whichever
the runtime supports). `/sync-sweep`'s Step 11 emits a `trigger_source` field
that `/weekly-review` will later filter on.

```bash
# Conceptual — the agent runs /sync-sweep with this trigger set.
TRIGGER_SOURCE=end-day-final-step
# Then invoke the /sync-sweep skill.
```

**No-op path (clean exit, no UI noise):**

If today's daily note has no `## Braindump` section, or the section is empty,
or every extracted entity is idempotently already applied, `/sync-sweep` exits
at Step 1 / Step 6 with `entities_extracted: 0` (or `entities_staged: 0`) and
emits its own telemetry. `/end-day` MUST NOT display an empty trust gate in
that case — surface a single inline line in the day's log instead:

```
sync-sweep: nothing to route today
```

This keeps the EOD UX clean on quiet days.

**Failure path (do not propagate):**

If `/sync-sweep` refuses (mode locked, PHI detected, missing daily note) or
fails partway (Notion 5xx during search, retry-queue writes), `/end-day` MUST
NOT propagate the failure as its own. Log a one-line note in
`${LOGS_DIR}/{TODAY}.md`:

```
sync-sweep: <refused|failed|partial> — <reason>. /end-day completing normally.
```

Then continue to Step 10. The next morning's `/start-day` pre-flight surfaces
the DLQ depth if anything landed in `state/sync-sweep-retry-queue.yaml`.

**What this does NOT replace:**

This is route-by-mention behavior — short phrases tied to known Notion topic
pages. The structured retro writes (Steps 8a–8g above) — daily note EOD section,
state file updates, sync loop pushes, dead-task resolutions, mobile mirror —
all execute BEFORE this step and stand on their own.

## Step 10: Emit Telemetry (AAC OBSERVED)

```bash
DURATION_MS=$(( $(date +%s%3N 2>/dev/null || python -c "import time; print(int(time.time()*1000))") - RUN_START_MS ))

scripts/telemetry.sh end-day "${RUN_ID}" "${DURATION_MS}" "${STATUS}" "$(python -c "
import json
print(json.dumps({
    'mode': '${MODE}',
    'top3_tracked': ${TOP3_TRACKED_COUNT},          # what Notion/Tasks closed today
    'top3_real': ${TOP3_REAL_COUNT},                # Aaron's self-reported real movement
    'real_vs_tracked_delta': ${TOP3_REAL_COUNT} - ${TOP3_TRACKED_COUNT},
    'completed_today': ${COMPLETED_COUNT},
    'new_items_today': ${NEW_ITEMS_COUNT},
    'unplanned_work_reported': ${UNPLANNED_BOOL},
    'carry_forward_new': ${CARRY_NEW},
    'carry_forward_continued': ${CARRY_CONTINUED},
    'carry_forward_3plus_days': ${CARRY_3PLUS},
    'dead_tasks_resolved': ${DEAD_RESOLVED_COUNT},
    'gtask_retry_queue_depth': ${DLQ_DEPTH},
    'gtask_retry_queue_oldest_days': ${DLQ_OLDEST_DAYS},
    'sync_pull_completions': ${PULL_COUNT},
    'sync_push_completions': ${PUSH_COUNT},
    'sync_push_failures': ${PUSH_FAIL_COUNT},
    'annotations_detected': ${ANNO_DETECTED},            # Step 4f total (create_event+create_task)
    'annotations_created_event': ${ANNO_CREATED_EVENT},
    'annotations_created_task': ${ANNO_CREATED_TASK},
    'annotations_needs_confirm': ${ANNO_NEEDS_CONFIRM},  # surfaced, flagged
    'annotations_skipped_idempotent': ${ANNO_SKIP_IDEM},
    'annotations_dup_skipped': ${ANNO_DUP_SKIP},
    'annotations_failed': ${ANNO_FAILED},
    'annotation_reschedules_surfaced': ${ANNO_RESCHED}   # surface-only in MVP
})
")"
```

`STATUS` is `ok` (retro built + writes succeeded), `partial` (≥1 source down or ≥1 write failed), or `failed` (couldn't build retro).

## Error Handling

- **scripts/check_mode.sh exits 1 (locked):** Refuse. No telemetry.
- **No morning log:** Run retro based on current state alone. Warn but don't fail.
- **Notion API failure:** Report which databases were unreachable. Use whatever data
  is available from other sources. Note in retro. Telemetry status = `partial`.
- **gws CLI failure:** Skip calendar/tasks comparison. Note in retro.
- **Obsidian daily note doesn't exist:** Create a minimal one with just the EOD section.
- **State file corrupted:** Regenerate `priorities.yaml` from today's retro data.
  Warn user that previous carry-forward history may be lost.
- **Never retry automatically.** Report clearly and continue.
- **Never crash on a missing source.** The retro runs with whatever is available.
