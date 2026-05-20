---
name: end-day-team
description: >-
  EXPERIMENTAL team-orchestrated /end-day. Coordinator + 5 parallel workers
  (calendar-eod, notion-eod, gtasks-eod, obsidian-eod, braindump-extractor).
  Adds a "Real movement off Top 3" section that auto-mines decision verbs
  from the daily-note braindump — the failure mode in
  feedback_top3_vs_actual.md. Safe to run concurrently with
  /capture-meeting-team. Invoke explicitly; not auto-triggered.
coo_twin:
  category: briefing
  mode_required: any
  writes_external: true
  preflight: required
  experimental: true
  parallel_workers: 5
disable-model-invocation: true
allowed-tools:
  - Bash(curl https://api.notion.com/*)
  - Bash(gws *)
  - Bash(scripts/*)
  - Bash(date *)
  - Read
  - Write
  - Edit
  - Glob
  - Grep
---

# /end-day-team — Day Close Retro (parallel fan-out)

Experimental sibling of `/end-day`. Same input contract, same output contract,
same trust gates. Steps 2–4 (source pulls + comparison data prep) fan out
across 5 worker agents. Everything that touches state — reconcile, carry-
forward composition, trust gate, all writes — stays in the coordinator.

**Baseline reference:** `.claude/skills/end-day/SKILL.md`. If this skill ever
diverges in *what* it produces, baseline wins and this skill is wrong. The
only legal difference is *how* the source pulls happen.

**New capability vs baseline:** a 5th worker (`braindump-extractor`) reads
today's daily-note braindump section, identifies decision verbs + entity
mentions, and returns candidate Activity Log entries. The coordinator
surfaces these in the **"Real movement off Top 3"** section and offers them
at the trust gate as opt-in Activity Log writes. This closes the gap from
`feedback_top3_vs_actual.md` (in-person Nestmate days score 0/3 because work
bypasses Notion/Tasks).

## Constants

```
REPO_DIR = "C:/Users/aaron/daily-automation"
CONFIG   = "${REPO_DIR}/config/sources.yaml"
LOGS_DIR = "${REPO_DIR}/logs"
VAULT    = "${REPO_DIR}/vault"
STATE    = "${REPO_DIR}/state"
TODAY    = <current date in YYYY-MM-DD format>
RUN_ID   = "edt-${TODAY//-/}-$(date +%H%M)"   # edt = end-day-team
TEAM     = "end-day-${TODAY//-/}-$(date +%H%M)"
```

`TEAM` is RUN_ID-keyed so concurrent invocations (e.g. /capture-meeting-team
mid-retro) never collide on `~/.claude/teams/${TEAM}/`. See
"Parallel safety" at the bottom.

Capture `RUN_START_MS` for telemetry.

## Step 0: Mode Check

Identical to `/end-day` Step 0. Locked → refuse. Observe → set
`SKIP_WRITES=1` (build retro, display, no state mutation). Draft/Approved →
proceed.

## Step 1: Load Morning Plan (coordinator)

Read `${LOGS_DIR}/{TODAY}.md` for this morning's briefing — Top 3,
calendar, departmental checklist, sources available/skipped. Read
`${STATE}/priorities.yaml` for yesterday's carry-forwards. The coordinator
owns this — workers don't re-parse the morning log.

If no morning log exists, warn and continue with current state only
(workers still run; reconcile section becomes "no plan to compare").

## Step 1.5: Create Team

```
TeamCreate(team_name: "${TEAM}",
           agent_type: "coordinator",
           description: "Parallel fan-out for /end-day on ${TODAY}")
```

## Step 2: Fan-out (parallel workers)

Spawn five workers in **one Agent-tool-call message** so they run
concurrently. All are read-only (`subagent_type: "Explore"`). Each returns
one structured JSON final message.

### Worker 1 — `calendar-eod-worker`

> Pull today's actual calendar via Bash:
> `gws calendar +agenda --today --format json`
>
> Return JSON:
> `{status, today_events: [...], skipped_reason?}`
>
> The coordinator handles the diff against this morning (event additions,
> cancellations, moves). You just deliver the current state.
>
> If `gws calendar` fails, return `status: "skipped"` with reason.

### Worker 2 — `notion-eod-worker`

> Query the three Notion data sources for pages edited today
> (`last_edited_time` on_or_after `<TODAY>T00:00:00Z`), per the exact request
> shapes in `.claude/skills/end-day/SKILL.md` Step 2b:
>
> - Master Tasks `528d24b8-e1e6-4ca0-a7ee-87f70a4f7980`
> - Provider CRM  `ae0a3158-59b4-8235-b7ca-0758daa2322a`
> - Activity Log  `3db174bf-c997-4a41-93ee-36f280e511db`
>
> Also run a **dead-task scan** on Master Tasks: Status = "In progress" AND
> `last_edited_time` older than 5 days. Return their IDs, titles, days
> dormant, and workspace. The coordinator decides what to do with them at
> the trust gate (`/end-day` Step 4c + 7b).
>
> For Master Tasks edited today: classify each as completed
> (Status → Done), moved-to-in-progress, newly created, or just edited.
>
> For Master Tasks flipped to Done today, read `Last Activity` rich_text —
> if it contains `gtask:<ID>`, include that gtask ID in the return so the
> coordinator can queue the reverse Google Tasks completion (baseline 4b
> bidirectional sync).
>
> Use `--max-time 60` on every curl. If `$NOTION_API_TOKEN` is empty,
> return `status: "skipped"` immediately.
>
> Return JSON:
> `{status, master_tasks: {completed, moved_in_progress, created, edited},
>   crm: {edited_today}, activity_log: {created_today},
>   dead_tasks: [{id, title, days_dormant, workspace}],
>   reverse_gtask_completions: [...]}`

### Worker 3 — `gtasks-eod-worker`

> Pull two task views via Bash:
>
> 1. Completed today:
>    `gws tasks tasks list --params '{"tasklist":"MDE5NTgyMDkwMjMxNjkwNzQyMTk6MDow","showCompleted":true,"completedMin":"<TODAY>T00:00:00Z"}' --format json`
> 2. Currently open:
>    `gws tasks tasks list --params '{"tasklist":"MDE5NTgyMDkwMjMxNjkwNzQyMTk6MDow"}' --format json`
>
> Also drain the DLQ check: read `state/gtask-retry-queue.yaml` if it
> exists; return `pending_retries` (count, oldest_days, sample 3 items).
>
> Return JSON:
> `{status, completed_today: [...], open: [...], dlq: {depth, oldest_days, items}}`
>
> If `gws tasks` fails, return `status: "skipped"` with reason.

### Worker 4 — `obsidian-eod-worker`

> Read today's daily note `${VAULT}/daily/{TODAY}.md` and extract:
>
> 1. **Every checkbox line** (`- [x] …` or `- [ ] …`). For each, capture
>    state + embedded source-ID HTML comment (`<!-- gtask:ID -->`,
>    `<!-- notion:ID -->`) per `/end-day` Step 4b regex. Return as
>    `checkbox_completions: [{state, source, source_id, line_text, line_number}]`.
> 2. **Today's braindump text** — the part of the daily note Aaron has typed
>    free-form during the day. It's typically below the "Actionable Items"
>    block or under any `## Braindump` / `## Notes` section. Return as
>    `braindump_raw_text: "..."` — pass-through; you don't parse it. The
>    braindump-extractor worker handles that.
>
> Also glob for new/modified-today files in:
> - `${VAULT}/notes/**/*.md`
> - `${VAULT}/meetings/**/*.md`
> - `${VAULT}/inbox/**/*.md`
> - business folders `${VAULT}/CardioPro/`, `Labaide/`, `Nestmate/`,
>   `United IPA/`, `Notes to self/`
>
> Return JSON:
> `{status, checkbox_completions: [...], braindump_raw_text: "...",
>   new_notes: [...], new_meetings: [...], new_inbox: [...],
>   business_folder_changes: [...]}`

### Worker 5 — `braindump-extractor` (new vs baseline)

> Input (from coordinator): the `braindump_raw_text` string captured by
> obsidian-eod-worker, plus today's calendar events list (for entity
> context) and the day's primary business tags. Coordinator passes these
> verbatim in your prompt.
>
> Your job: scan the braindump for **decision verbs** and **entity
> mentions** that should become Activity Log entries. This addresses
> `feedback_top3_vs_actual.md` — in-person work bypasses Notion/Tasks; the
> daily-note braindump is the only catch.
>
> Decision verbs to surface:
> - "decided", "agreed", "approved", "going with", "confirmed", "finalized",
>   "settled on", "moving forward with", "killed", "dropped", "paused"
> - Also: implicit decisions — "Dr Rookwood will reschedule to Tuesday"
>   (decision: rescheduling), "Guerchon needs BAA before referral flow"
>   (decision: gating)
>
> Entity mentions to extract:
> - Provider names (Dr / clinic / urgent care / "spoke with X")
> - Business names (Sovereign Phoenix, Healthfirst, Essen, Lincoln Lab, etc.)
> - Key teammate names (Adam, Valentyna, Morshed, Julie, Gary, Luis, Ahmed,
>   Guerchon, Cyrus, Ilene, Roman)
>
> For each candidate Activity Log entry, return:
> `{decision_or_observation: "...",
>   workspace: "<inferred from business keywords>",
>   confidence: 0.0-1.0,
>   source_line: N,
>   source_text: "<exact quote>",
>   entities: [...]}`
>
> Confidence rules (mirror `/capture-meeting` Step 4 §Parsing Rules):
> - 0.90+ : explicit decision verb + clear subject + clear workspace
> - 0.75  : explicit verb, ambiguous workspace OR weak subject
> - 0.60  : implicit decision, requires Aaron's call
> - < 0.60 → DO NOT include in the return; would just be noise.
>
> Return JSON:
> `{status, candidate_activity_log_entries: [...]}`
>
> If braindump_raw_text is empty / under 50 chars, return
> `status: "skipped", reason: "no braindump content"`. Never block.

### Spawning pattern

One message, five Agent calls. Workers 1–4 are independent; worker 5
depends on worker 4's `braindump_raw_text`. Two options for ordering:

**Option A (simpler):** spawn workers 1–4 in one message; once worker 4
returns, spawn worker 5 with the braindump text as input. Adds one
round-trip but the prompt is clean.

**Option B (faster):** spawn all 5 in one message. Worker 5 reads the
daily note itself via Glob/Read. Adds redundant file read but parallelizes.
Pick B when the daily note is small (<10 KB), which it always is.

Default to **B**. Worker 5's prompt becomes "read `${VAULT}/daily/{TODAY}.md`
yourself, scan its braindump section."

## Step 3: Reconcile (coordinator)

The coordinator does this — it touches files, and synthesis is where the
single-context view matters.

### 3a: Top 3 status detection

For each morning Top 3 item, cross-reference against
`notion-eod.master_tasks.completed`, `notion-eod.master_tasks.moved_in_progress`,
`gtasks-eod.completed_today`, and `obsidian-eod.checkbox_completions` to
infer status (Completed / In Progress / Not Started / Blocked).

### 3b: Checkbox ↔ source reconciliation

Same as baseline `/end-day` Step 4b: for each `[x]` in
`obsidian-eod.checkbox_completions` with an embedded `gtask:` or
`notion:` ID, queue the corresponding completion. For `[x]` without an
embedded ID, best-effort title match against this morning's actionable
items. Items completed in source but not checked in daily note → log to
"Sync gaps" section.

### 3c: Bidirectional reverse sync queue

Add `notion-eod.reverse_gtask_completions` to the gtask completion queue
(Notion → Done implies gtask close).

### 3d: Calendar drift

Diff `calendar-eod.today_events` against the morning's events from
`logs/{TODAY}.md`. Build `calendar_drift: {added, removed, moved}`.

### 3e: Real movement candidates

`braindump-extractor.candidate_activity_log_entries` is the pre-baked list.
Threshold cleanup: drop any entry where `workspace` is null AND
`confidence < 0.80`. The remaining list goes into Step 4's retro display
under "Real movement off Top 3" and Step 5 trust gate as an opt-in
write-batch.

### 3f: Carry-forward build

Same as baseline Step 5. Auto-include unfinished Top 3, high-priority
unchecked items, new items needing follow-up, and yesterday's
carry-forwards whose `days_carried` should increment.

## Step 4: Compose Retro

Render the baseline `/end-day` Step 6 template exactly, plus the new
"Real movement off Top 3" subsection populated from Step 3e candidates:

```markdown
## Real Movement off Top 3 (from today's braindump)

System-tracked Top 3: {N}/3
Braindump-derived candidates ({M} found, all conf ≥ 0.80):
- [{workspace}] {decision_or_observation} (conf {0.92})
  Source: "{source_text}" (line {N})
- ...

→ Trust gate will offer: log all M to Activity Log? Pick subset? Skip?
```

Also include a one-line team header so A/B vs baseline is visible:

```
_Run: {RUN_ID} · Mode: {MODE} · Team: ${TEAM} · workers: cal={ms} notion={ms} gtask={ms} obs={ms} brain={ms}_
```

## Step 5: Trust Gate

Baseline `/end-day` Step 7 trust gate (Option A / B / C) PLUS a new
sub-gate for braindump-derived Activity Log entries.

### 5a: Main retro gate

Baseline Options A / B / C unchanged.

### 5b: Braindump Activity Log gate (only if Step 3e found ≥ 1 entry)

**Question:** "Braindump scan found {M} candidate Activity Log entries.
Log them?"

Options:
- **All** — write all M as Activity Log entries
- **Pick which** — show each, accept/reject one by one
- **Skip** — don't log; they'll resurface tomorrow if the braindump still
  mentions them (no automatic carry — Activity Log entries are point-in-time)

### 5c: Dead-task gate (baseline 7b)

Per baseline Step 7b — for each item in `notion-eod.dead_tasks`, force a
decision (Mark Done / Set hard due / Park to back-burner / Snooze 5 days).

## Step 6: Execute Approved Actions (coordinator)

Same as baseline Step 8 (a–g). All writes execute coordinator-side after
gates pass — workers are already done and the team will be torn down in
Step 8.

Addition: **Step 6a-braindump** — for each approved braindump candidate,
POST a new Activity Log entry (per `/capture-meeting` Step 6b shape):

```bash
curl -s -X POST "https://api.notion.com/v1/pages" \
  -H "Authorization: Bearer $NOTION_API_TOKEN" \
  -H "Notion-Version: 2025-09-03" \
  -H "Content-Type: application/json" \
  --max-time 60 \
  -d '{
    "parent": {"data_source_id": "3db174bf-c997-4a41-93ee-36f280e511db"},
    "properties": {
      "Task": {"title": [{"text": {"content": "<decision_or_observation>"}}]},
      "Type": {"select": {"name": "Decision"}},
      "Date": {"date": {"start": "<TODAY>"}},
      "Workspace": {"select": {"name": "<workspace>"}}
    }
  }'
```

Stamp each with an `action_id` of shape
`end-day:activity-log:{TODAY}:<hash-of-source-text>` so re-runs of
/end-day-team on the same day no-op (baseline action_id pattern).

## Step 7: Summary + Telemetry

Baseline Step 9 summary unchanged. Telemetry (Step 10) emitted under skill
name `end-day-team`, with extra fields:

```json
{
  "team_run": true,
  "team_name": "${TEAM}",
  "worker_durations_ms": {"calendar": N, "notion": N, "gtasks": N, "obsidian": N, "braindump": N},
  "worker_statuses": {...},
  "coordinator_overhead_ms": N,
  "braindump_candidates_found": N,
  "braindump_candidates_approved": N,
  "braindump_skipped_low_conf": N,
  "baseline_skill_for_comparison": "end-day"
}
```

## Step 8: Teardown

```
TeamDelete()
```

## Failure Modes

- **Any worker skipped** → its source goes into "Skipped Sources" in the
  retro. Continue.
- **Worker 5 (braindump) skipped or empty** → render the "Real Movement
  off Top 3" section with `M = 0` and a note "No braindump content
  detected." Don't treat as failure; some days Aaron just doesn't braindump.
- **All workers skipped** → render retro from morning log + priorities.yaml
  only (graceful degradation matches baseline behavior).
- **Coordinator-side failures** — identical to baseline.

## Experiment Log

Append a row to `state/experiments/end-day-team.md` after each run
(create that file on first run, mirror schema from `start-day-team.md`).
Track: total_ms, max_worker_ms, coord_overhead_ms, braindump_candidates_found,
braindump_approved_rate, quality_delta_vs_baseline.

Exit criteria same as start-day-team: 5+ runs with `quality_delta == 0`
AND meaningful wall-time savings → promote. Any unfixable regression →
abandon.

## Parallel safety with /capture-meeting-team

This skill is safe to run concurrently with `/capture-meeting-team`. The
guarantees:

1. **TEAM name** is RUN_ID-keyed (`edt-{date}-{HHMM}`); /capture-meeting-team
   uses `cmt-…`. No directory collision under `~/.claude/teams/`.
2. **No shared mutable file targets.** This skill writes
   `${VAULT}/daily/{TODAY}.md` (Edit), `${LOGS_DIR}/{TODAY}.md` (append),
   `${STATE}/priorities.yaml` (Write), `${STATE}/gtask-retry-queue.yaml`
   (read/write). /capture-meeting-team writes
   `${VAULT}/meetings/{TODAY}-…md`, `${VAULT}/notes/{TODAY}-…md`, plus
   Notion + Google APIs. The only overlap surface is the appended
   `${LOGS_DIR}/_telemetry.jsonl`, which is line-oriented and append-safe
   (POSIX guarantees atomic writes of small lines).
3. **Action IDs are skill-prefixed** (`end-day:...` vs `capture-meeting:...`)
   so `.context/applied/{aid}.json` files never collide.
4. **Notion writes** target different pages (this skill PATCHes status flips
   + creates Activity Log entries; /capture-meeting-team creates Master
   Tasks + CRM updates). No write-write conflict on any single page.
5. **Trust gates** are interactive (AskUserQuestion). Aaron can only be in
   one at a time — they serialize naturally from the user's POV.

If both skills happen to PATCH `state/gtask-retry-queue.yaml` (e.g.,
/end-day-team adds a retry, /capture-meeting-team logs a write failure),
the second writer's read-modify-write could lose the first's update. This
is the one true race. Mitigation: keep retry-queue writes coordinator-side
in both skills, and serialize within each skill so the window is small.
If we ever see queue corruption, switch to a flock-based wrapper.
