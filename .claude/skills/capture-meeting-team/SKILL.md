---
name: capture-meeting-team
description: >-
  EXPERIMENTAL team-orchestrated /capture-meeting. Parsing + trust gate stay
  in the coordinator (single-context judgment). Step 6 writes fan out across
  5 parallel workers (notion-tasks, notion-decisions, notion-crm, calendar,
  obsidian) AFTER approval. Safe to run concurrently with /end-day-team.
  Invoke explicitly; not auto-triggered.
coo_twin:
  category: capture
  mode_required: any
  writes_external: true
  preflight: required
  phi_gate: true
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

# /capture-meeting-team — Meeting Note Splitter (parallel writes)

Experimental sibling of `/capture-meeting`. Same input contract, same output
contract, same trust gate UX. Steps 0–5 are sequential in the coordinator
(parse + categorize + present trust gate — single-LLM-judgment work that
doesn't parallelize cleanly). Step 6 (execute approved routing) fans out
across 5 worker agents.

**Baseline reference:** `.claude/skills/capture-meeting/SKILL.md`. If output
diverges, baseline wins.

**Why fan out the writes and not the parse:** the parse is one model
applying confidence + categorization across the whole note. Splitting it
across workers would re-encode the routing rules N times and risk
disagreement on borderline items. The writes are independent destinations
(Notion Master Tasks vs Notion Activity Log vs CRM vs Calendar vs Obsidian)
with no inter-dependency *after* trust gate — natural fan-out boundary.

**Realistic speedup:** baseline Step 6 is ~20–25s on a typical meeting
(5 actions, 1–2 decisions, 1–2 CRM updates, 1 follow-up, 2 obsidian notes).
With fan-out, max worker (`notion-tasks-worker` due to parent→subtask→gtask
chain) runs ~16s. So ~5s saved per meeting. Smaller than `/start-day-team`,
but two other wins matter more: (a) error isolation — if CRM 401s, tasks
still land; (b) it's the same architecture as `/sp-sweep` and `/sync-sweep`,
so we learn it here cheaply.

## Constants

```
REPO_DIR = "C:/Users/aaron/daily-automation"
CONFIG   = "${REPO_DIR}/config/sources.yaml"
ROUTING  = "${REPO_DIR}/config/routing-rules.yaml"
LOGS_DIR = "${REPO_DIR}/logs"
VAULT    = "${REPO_DIR}/vault"
TODAY    = <current date in YYYY-MM-DD format>
RUN_ID   = "cmt-${TODAY//-/}-$(date +%H%M%S)"   # cmt = capture-meeting-team
TEAM     = "capture-meeting-${TODAY//-/}-$(date +%H%M%S)"
```

`TEAM` is RUN_ID-keyed (includes seconds — multiple meetings per day) so
concurrent invocations (back-to-back meetings, or /end-day-team running
alongside) never collide. See "Parallel safety" at the bottom.

Capture `RUN_START_MS` for telemetry.

## Steps 0–5: Sequential (coordinator)

**Identical to baseline `/capture-meeting` Steps 0 through 5.** No
parallelism, no team yet. The coordinator does:

- Step 0: Mode check
- Step 1: Load config + routing rules
- Step 2: Collect meeting notes (paste / file / meetings folder / Granola
  recap page)
- Step 2.5: PHI input gate (`scripts/phi_scan.sh`)
- Step 3: Collect meeting context (business tag, attendees)
- Step 4: Parse + categorize with confidence scores
- Step 4.5: Idempotency cache check (`scripts/action_id.sh check`)
- Step 5: Present trust gate; Aaron selects which items to route

The team isn't created until AFTER trust gate approval. This keeps team
overhead off the path for runs that get rejected at the trust gate (which
happens routinely — Aaron edits categorizations and re-displays).

## Step 5.5: Create Team (only if Step 5 approved ≥1 item)

```
TeamCreate(team_name: "${TEAM}",
           agent_type: "coordinator",
           description: "Parallel writes for /capture-meeting on ${TODAY}")
```

If Step 5 approved zero items (Aaron picked "None — just save the notes"),
skip team creation. Run Step 6e (meeting note file) inline in coordinator,
emit telemetry, exit.

## Step 6: Fan-out Approved Writes (5 parallel workers)

Spawn five workers in **one Agent-tool-call message** so they run
concurrently. All use `subagent_type: "Explore"` (read-only filesystem,
Bash for curl + gws — enough to PATCH Notion, create gtasks, create
calendar events; for Obsidian local file writes, see worker 5 caveat).

Each worker receives the approved subset of items for its category as a
self-contained prompt, plus the meeting context (business tag, attendees,
TODAY, recap_page_id_if_any, run_id). Each returns a structured JSON
final message describing what landed and what failed.

### Worker 1 — `notion-tasks-worker`

**Owns Step 6a (parent + subtasks + gtask mirrors + Last Activity back-patch).**

> You write Notion Master Tasks for this meeting. Steps in order (the
> dependency chain matters):
>
> 1. Create the parent task: `[Meeting] <name> <YYYY-MM-DD>`, Workspace =
>    primary business, Status = "In progress", Assignee = Aaron, link
>    `Related to Meeting Notes (Related Tasks)` to `<recap_page_id>` if
>    Option D was used. Use the exact curl request shape in
>    `.claude/skills/capture-meeting/SKILL.md` Step 6a-1. Capture the
>    response `id` as `PARENT_TASK_ID`.
>
> 2. For each approved action item: create as a child of `PARENT_TASK_ID`
>    (`Parent Task` relation). Carry Workspace, Due, Assignee from the
>    parsed item. Use Step 6a-2 request shape. Capture each response
>    `id` as `SUBTASK_IDS[]`.
>
> 3. For each Aaron-owned subtask: create a Google Task mirror via
>    `gws tasks tasks insert` (Step 6a-3 shape). Capture each response
>    `id` as `GTASK_ID`. Then PATCH the corresponding Notion subtask's
>    `Last Activity` rich_text to contain `gtask:<GTASK_ID>` so /end-day
>    can do exact-ID bidirectional sync.
>
> 4. If the source was Option D (Granola recap page), PATCH the recap page
>    `Workspace` (if it was untagged) AND `Related Tasks` (relation array
>    = parent + all subtask IDs). Merge with existing relations — never
>    clobber. Use Step 6a-bonus shape.
>
> Re-run safety: before step 1, query Master Tasks where
> `Related to Meeting Notes` contains `<recap_page_id>` AND title starts
> with `[Meeting]`. If a parent already exists, reuse its ID and only add
> missing subtasks. NEVER duplicate the parent.
>
> Stamp action_id on every successful write. If a write fails, do NOT
> stamp — the next run retries.
>
> Return JSON:
> `{status, parent_task_id, subtask_ids: [...], gtask_ids: [...],
>   failures: [{step, item, reason}]}`

### Worker 2 — `notion-decisions-worker`

**Owns Step 6b (Activity Log entries).**

> For each approved DECISION item, POST a new Activity Log page per
> `/capture-meeting` Step 6b request shape. Type = "Decision", Date =
> TODAY, Workspace = the item's resolved business tag.
>
> These writes are independent of each other and of the task chain —
> run them in sequence within your turn (curl after curl) but you're
> free to start as soon as you receive the prompt.
>
> Stamp action_id on each success.
>
> Return JSON:
> `{status, activity_log_ids: [...], failures: [...]}`

### Worker 3 — `notion-crm-worker`

**Owns Step 6c (Provider CRM upsert).**

> For each approved PROVIDER item:
>
> 1. Search Provider CRM by title contains `<provider name>`
>    (data_source `ae0a3158-59b4-8235-b7ca-0758daa2322a`).
> 2. If found, PATCH the existing page with `Last Contact` = TODAY and
>    `Next Step` rich_text = `<next step text>`.
> 3. If NOT found, POST a new CRM page with Stage = "New Lead", Workspace
>    = item's business tag.
>
> Use `--max-time 60` on every curl. Stamp action_id on each success.
>
> Return JSON:
> `{status, updated_page_ids: [...], created_page_ids: [...],
>   failures: [...]}`

### Worker 4 — `calendar-worker`

**Owns Step 6d (follow-up Calendar drafts).**

> For each approved FOLLOW-UP item, create a Calendar event via
> `gws calendar +quickadd "<topic> with <attendees>" --calendar primary`.
> Use the reference timeframe field as `--start`/`--end` if specific.
>
> If `gws calendar` is unavailable, fall back to the Google Calendar MCP
> tool `mcp__claude_ai_Google_Calendar__create_event` with summary,
> description, attendees. If neither works, return the event details as
> text in the failure list so the coordinator can surface them at the end.
>
> Stamp action_id on each success.
>
> Return JSON:
> `{status, calendar_event_ids: [...], failures: [...]}`

### Worker 5 — `obsidian-stager`

**Owns Step 6e (Insight notes + Meeting note file).**

Caveat: Explore agents cannot Write local files directly (they have Bash +
Read + Glob/Grep but no Edit/Write). Two implementation paths:

**Path A (recommended):** This worker is `general-purpose` instead of
`Explore`, so it can use the Write tool directly. Tradeoff: slightly
broader tool surface in the worker. Acceptable because the trust gate
already passed and the write targets are known-safe paths under
`${VAULT}/notes/` and `${VAULT}/meetings/`.

**Path B (fallback):** This worker is Explore; it stages the content +
target path in its JSON return; the coordinator does the actual Write
inline after all 5 workers report. Adds one round-trip but keeps every
worker read-only.

Default to **A**. Prompt:

> Write the following files to disk:
>
> 1. For each approved INSIGHT, create `${VAULT}/notes/{TODAY}-<slug>.md`
>    with frontmatter `date, tags: [meeting, <business>], source: meeting
>    with <attendees>` and a body containing the original text. Use the
>    template in `/capture-meeting` Step 6e §Insights.
>
> 2. Always write the meeting note file
>    `${VAULT}/meetings/{TODAY}-<meeting-slug>.md` with frontmatter
>    `date, meeting, attendees, tags`, then `## Raw Notes` (original
>    text), `## Routed Items` (bulleted list of every item written by
>    workers 1–4 — coordinator passes this to you), `## Decision Links`
>    (wikilinks for each Activity Log entry).
>
> Return JSON:
> `{status, notes_files: [path, ...], meeting_file: path, failures: [...]}`

### Spawning pattern

One Agent-tool message, five Agent calls. All five workers receive the
common context block (meeting metadata, business_tag, attendees, recap_page_id,
TODAY, run_id) plus their category's approved items.

After all five return, the coordinator:

1. Aggregates failures across workers
2. Logs any failed Notion writes to
   `${VAULT}/meetings/{TODAY}-pending-notion.md` for manual entry (matches
   baseline error handling)
3. Renders the routing-complete summary (Step 7 of baseline)

## Step 7: Summary

Same as baseline Step 7. Add team line:

```
_Run: {RUN_ID} · Mode: {MODE} · Team: ${TEAM} · workers: tasks={ms} decisions={ms} crm={ms} cal={ms} obs={ms}_
```

## Step 8: Stamp action_ids + Telemetry

Workers stamp their own successful writes (each worker is closest to its
write outcome — least likely to mis-stamp a failed call as applied). The
coordinator does NOT re-stamp.

Telemetry emitted under skill name `capture-meeting-team` with extra fields:

```json
{
  "team_run": true,
  "team_name": "${TEAM}",
  "worker_durations_ms": {"tasks": N, "decisions": N, "crm": N, "calendar": N, "obsidian": N},
  "worker_statuses": {...},
  "coordinator_overhead_ms": N,
  "baseline_skill_for_comparison": "capture-meeting",
  "writes_succeeded": {...},
  "writes_failed": [...]
}
```

## Step 9: Teardown

```
TeamDelete()
```

## Failure Modes

- **Single worker fails entirely** (e.g., notion-crm-worker 401s on every
  CRM call) → other workers' results still land. Report at the end.
- **Single write within a worker fails** → worker stamps successes only,
  returns failure in JSON; the action_id will retry on next run.
- **Worker 1 (notion-tasks) parent creation fails** → subtasks cannot be
  created. Worker returns `status: "blocked"` with reason; other workers'
  results still land. Aaron re-runs after fixing the parent issue (often
  auth) and re-run safety (Step 6a-3 §re-run) avoids dupes.
- **PHI gate fires** in Steps 2.5 → no team is ever created. Refuse and log
  per baseline.
- **TeamDelete fails** → not fatal; the team dir is local-only state and
  doesn't affect Notion/Calendar/Tasks. Surface as a warning.

## Parallel safety with /end-day-team

This skill is safe to run concurrently with `/end-day-team`. Guarantees:

1. **TEAM name** is RUN_ID-keyed with second-precision
   (`cmt-{date}-{HHMMSS}`). Two back-to-back /capture-meeting-team
   invocations and a concurrent /end-day-team (`edt-…`) all get distinct
   directories under `~/.claude/teams/`.
2. **No shared mutable file targets.** This skill writes
   `${VAULT}/notes/{TODAY}-<slug>.md` (new files, slug-unique),
   `${VAULT}/meetings/{TODAY}-<meeting-slug>.md` (new files, meeting-slug-
   unique), `.context/applied/{aid}.json` (per-action_id unique), and the
   shared append-only `logs/_telemetry.jsonl` (line-oriented, atomic
   under POSIX). /end-day-team writes
   `${VAULT}/daily/{TODAY}.md` (Edit), `${STATE}/priorities.yaml` (Write),
   `${LOGS_DIR}/{TODAY}.md` (append), `${STATE}/gtask-retry-queue.yaml`.
   No file-level conflict.
3. **Action IDs are skill-prefixed.** Workers stamp
   `capture-meeting:meeting-key:date:hash`; /end-day-team stamps
   `end-day:...`. No collision in `.context/applied/`.
4. **Notion writes** target different surfaces. This skill CREATES
   Master Tasks, Activity Log entries, CRM pages. /end-day-team PATCHES
   existing Master Tasks (Status flips) and creates Activity Log entries
   too. There's a theoretical race if /end-day-team PATCHes a Master Task
   *while* this skill is creating it under the same parent, but the
   create→PATCH ordering is sequential within each team's own coordinator,
   so the only cross-team risk is /end-day-team flipping a task to Done
   that this skill is still in the middle of creating subtasks under.
   Mitigation: extremely unlikely in practice (Aaron isn't running EOD
   retro on a meeting he's still capturing), and if it happens, Notion's
   eventual consistency makes the worst case a stale read on either side.
5. **Trust gates** are interactive — Aaron is in one or the other, never
   both simultaneously. They serialize naturally from the user's POV.
6. **Telemetry JSONL appends** are concurrent-safe under POSIX for writes
   under PIPE_BUF (4096 bytes — our rows are ~500 bytes).

The same `gtask-retry-queue.yaml` race noted in `/end-day-team`'s parallel-
safety section applies in reverse if this skill ever queues a failed gtask
write to that file. Today it doesn't — write failures here are logged to
`${VAULT}/meetings/{TODAY}-pending-notion.md`, not to the retry queue. If
that changes, add a flock wrapper.

## Experiment Log

Append to `state/experiments/capture-meeting-team.md` (create on first
run, mirror schema from `start-day-team.md`). Track total_ms,
max_worker_ms, coord_overhead_ms, writes_succeeded counts per worker,
writes_failed counts, quality_delta_vs_baseline.

Exit criteria: same as siblings — 5+ runs at `quality_delta == 0` AND
real wall-time savings → promote. Any unfixable regression → abandon.
