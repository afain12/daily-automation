---
name: start-day-team
description: >-
  EXPERIMENTAL team-orchestrated /start-day. Spawns a coordinator plus four
  parallel workers (calendar, notion, obsidian, gtasks) instead of running
  source pulls sequentially. Goal: ~3x wall-time reduction vs baseline
  /start-day. Production /start-day is untouched — use this for A/B work only.
  Invoke explicitly with /start-day-team; not auto-triggered.
coo_twin:
  category: briefing
  mode_required: any
  writes_external: true
  preflight: required
  experimental: true
  parallel_workers: 4
disable-model-invocation: true
allowed-tools:
  - Bash(curl https://api.notion.com/*)
  - Bash(gws *)
  - Bash(scripts/*)
  - Bash(date *)
  - Bash(mkdir *)
  - Read
  - Write
  - Edit
  - Glob
  - Grep
---

# /start-day-team — Daily Briefing (parallel fan-out)

Experimental sibling of `/start-day`. Same input contract, same output
contract, same trust gates. The only difference is **how** Steps 2–5 run:
in baseline they're sequential bash + curl + glob calls; here a coordinator
spawns four worker agents in parallel and merges their structured returns.

**Comparison target:** the authoritative spec is
`.claude/skills/start-day/SKILL.md`. This skill MUST produce a briefing that
is semantically equivalent to the baseline — same sections, same scoring,
same Top 3, same trust gate options. If the team version diverges, the
baseline wins and this skill is wrong.

**When to run:** mornings when you want to test the team flow, or
deliberately when comparing latency / quality against baseline. Default
remains `/start-day`.

## Constants

Same as `/start-day`:

```
REPO_DIR = "/path/to/daily-automation"
CONFIG   = "${REPO_DIR}/config/sources.yaml"
LOGS_DIR = "${REPO_DIR}/logs"
VAULT    = "${REPO_DIR}/vault"
STATE    = "${REPO_DIR}/state"
TODAY    = <current date in YYYY-MM-DD format>
RUN_ID   = "sdt-${TODAY//-/}-$(date +%H%M)"   # sdt = start-day-team
TEAM     = "start-day-${TODAY//-/}-$(date +%H%M)"
```

Capture `RUN_START_MS` for telemetry, same as baseline.

## Step 0: Mode Check

Identical to `/start-day` Step 0. Run `scripts/check_mode.sh`. Locked → refuse.
Observe → set `SKIP_WRITES=1`. Draft/Approved → proceed.

Record mode in the briefing header.

## Step 1: Load Configuration (coordinator only)

Read `${CONFIG}` (config/sources.yaml). The coordinator owns the config —
workers receive only the slice each needs (calendar keywords for the calendar
worker, data source IDs for the notion worker, etc.). This keeps each worker
fork small and avoids re-parsing YAML four times.

## Step 1.5: Create Team

```
TeamCreate(team_name: "${TEAM}",
           agent_type: "coordinator",
           description: "Parallel fan-out for /start-day on ${TODAY}")
```

The coordinator is the current session. Workers are spawned via the Agent
tool with `team_name: "${TEAM}"` and `name: <role>`.

## Step 2: Fan-out (parallel workers)

Spawn all four workers in a **single message** (multiple Agent tool calls in
one block — that's what makes them run in parallel). Each worker:

- Receives a self-contained prompt with explicit return contract.
- Reads only the sources it owns.
- Returns a structured summary as its final message. Never writes to any
  external system — read-only.
- Uses `subagent_type: "Explore"` (read-only, can run Bash for `gws` and
  `curl`, can Read/Glob/Grep, can't Edit/Write).

### Worker 1 — `calendar-worker`

**Prompt skeleton:**

> You are the calendar worker for the operator's COO Twin /start-day fan-out. Run
> two commands via Bash:
>
> 1. `gws calendar +agenda --today --format json`
> 2. `gws calendar +agenda --tomorrow --format json`
>
> **Tagging — two passes, in order. First match wins.**
>
> **Pass 1: keyword match** (case-insensitive, against `summary` + `location`).
> Read the full keyword lists from `config/sources.yaml` — they include both
> generic terms (lab, operations, sales, product, product) AND specific proper
> nouns the operator uses (LDX, AHBD, Vendor A, Gary biller, AFC, Person O, Example Account,
> Person H, Rybstein, Sorkin, Person S, Person R, Person Q, etc.). The lists are
> non-exhaustive — they were expanded 2026-05-19 to fix the validation-run
> issue where real contact visits landed `untagged`.
>
> **Pass 2: fallback inference** for events Pass 1 left `untagged`:
> - Summary starts with `Visit Contact ` or `Visit <Office>` → **product**
>   (the operator's default route for unmatched contact visits)
> - Summary contains `Meditate`, `Tea`, `GYM`, `Lunch`, `Workout` → **personal**
> - Summary contains `Workshop`, `Maven`, `Webinar`, `Live`, `Course` → **personal**
> - Otherwise → **untagged** (genuinely)
>
> Detect overlapping timed events on the same day (conflicts). Adjacent
> events (one ends where the next starts) are NOT conflicts.
>
> Return ONE final JSON message — no markdown, no surrounding prose:
> ```
> {"status":"ok|partial|skipped",
>  "today":[{"summary","start","end","business","location","tag_source"}],
>  "tomorrow":[...],
>  "conflicts":[{"a","b","window"}],
>  "skipped_reason":null}
> ```
> `tag_source` is `"keyword"`, `"inference"`, or `"untagged"` so the
> coordinator can audit tagging quality.
>
> If `gws calendar` fails (missing CLI, auth expired, 403), return
> `{"status":"skipped","skipped_reason":"..."}` with empty arrays. Never block.

### Worker 2 — `notion-worker`

**Prompt skeleton:**

> You are the notion worker for the operator's COO Twin /start-day fan-out. Query
> these four data sources via the Notion REST API (curl + `$NOTION_API_TOKEN`),
> following the exact request shapes in
> `.claude/skills/start-day/SKILL.md` Step 3:
>
> - Master Tasks: `528d24b8-e1e6-4ca0-a7ee-87f70a4f7980` (open tasks only)
> - Contact CRM: `ae0a3158-59b4-8235-b7ca-0758daa2322a`
> - Activity Log: `3db174bf-c997-4a41-93ee-36f280e511db` (last 3 days)
> - Meeting Notes: `22ba3158-59b4-804d-9c1c-000b9fad40ae` (last 24h)
>
> Also run the **24-hour change audit** (baseline Step 6b): for each of
> Master Tasks / Contact CRM / Activity Log, filter `last_edited_time`
> on_or_after yesterday's date. Also run one workspace-wide
> `/v1/search` sorted by `last_edited_time` desc, `page_size: 20`, to catch
> changes in DBs not explicitly configured.
>
> For Meeting Notes results, compute the action-item extraction status per
> baseline Step 3 (untreated / partially treated / wrapped) and the workspace
> triage confidence score for null-Workspace meetings.
>
> **Activity Log silence sanity-check (added 2026-05-19 after validation
> run #1):** if the 3-day Activity Log query returns 0 results, run a
> follow-up query with `Date on_or_after <TODAY - 30 days>` and return the
> 30-day count as `activity_log.silence_check.total_30d`. This disambiguates
> "real silence" from "filter is wrong" — a true 4d silence on a busy
> workspace is itself a strong briefing signal, not a bug.
>
> **Due-date extraction (mandatory format, added 2026-05-19):** for every
> Master Tasks item, the `due` field in your return MUST be either:
> - an ISO date string (e.g. `"2026-05-22"`) when `properties.Due.date.start` is set, OR
> - the JSON literal `null` when the Due property is unset.
>
> Do NOT return `""` (empty string) — that's neither and the coordinator
> can't distinguish "no due date set" from "extraction failed." Same rule
> for `last_activity` (`gtask:<ID>` string or `null`).
>
> **CRM follow-up threshold (added 2026-05-19 after validation run #2):**
> The `crm.followups_needed` list MUST be filtered by
> `days_since_last_contact > 14` (the `contact_followup_days` value in
> config/sources.yaml). Do NOT include contacts contacted 7–14 days ago as
> followups_needed — they're still inside the threshold. Run #2 incorrectly
> flagged 7-day-old contacts and inflated the briefing.
>
> Use `--max-time 60` on every curl. If `$NOTION_API_TOKEN` is empty, return
> `{"status":"skipped","errors":[{"reason":"NOTION_API_TOKEN missing"}]}`
> immediately. If a specific DB returns 404, skip just that DB and add it
> to `errors`.
>
> Return ONE final JSON message — no markdown, no prose. Example shape
> (truncated; cap each list at 20 entries):
> ```
> {"status":"ok|partial|skipped",
>  "master_tasks":{
>    "open_count":29,
>    "in_progress":[{"id":"abc","title":"...","due":null,"workspace":"Product","last_edited_time":"...","last_activity":"gtask:XYZ"}],
>    "not_started":[...],
>    "waiting":[...],
>    "overdue":[...],
>    "stale":[...]
>  },
>  "crm":{"followups_needed":[{"id","title","stage","last_contact","days_since","workspace"}]},
>  "activity_log":{
>    "recent_with_next_action":[...],
>    "recent_all":[...],
>    "silence_check":{"queried_window_days":3,"results":0,"total_30d":N}
>  },
>  "meeting_notes":{"recaps_24h":[...],"untreated":[...],"partially_treated":[...],"wrapped":[...]},
>  "changes_24h":{"master_tasks":{"completed":[],"created":[],"edited":[]},"crm":{...},"activity_log":{...},"workspace_search_top":[...]},
>  "errors":[]}
> ```

### Worker 3 — `obsidian-worker`

**Prompt skeleton:**

> You are the obsidian worker for the operator's COO Twin /start-day fan-out. Vault
> path: `${VAULT}`. Do this:
>
> 1. Glob `${VAULT}/inbox/**/*.md` — list each as an unprocessed capture.
> 2. Grep for `#review` across `${VAULT}/notes/` and `${VAULT}/` (frontmatter
>    `tags:` or inline `#review`).
> 3. Glob `${VAULT}/notes/**/*.md` modified in the last 3 days.
> 4. Read `${STATE}/priorities.yaml` and extract any items whose notes mention
>    an explicit upcoming meeting time, day, or phrase like "potentially
>    Friday", "tomorrow", "this week". Return these as `memory_meetings` so
>    the coordinator can run the calendar-gap check (baseline Step 1b).
>
> Also glob `${REPO_DIR}/.context/*.json` (top-level only — skip
> `${REPO_DIR}/.context/applied/`). For each file, read the top-level
> `intent`/`pending`/`status` field and classify per baseline Step 1b:
> confirmed pending / unverified / applied-ignore.
>
> Return one final JSON:
> `{inbox: [...], review_tagged: [...], recent_notes: [...],
>   memory_meetings: [...], pending_writes: {confirmed, unverified}}`
>
> If the vault path doesn't exist, return `status: "skipped"` with reason.

### Worker 4 — `gtasks-worker`

**Prompt skeleton:**

> You are the gtasks worker for the operator's COO Twin /start-day fan-out. Run via
> Bash:
>
> 1. Open tasks today:
>    `gws tasks tasks list --params '{"tasklist":"MDE5NTgyMDkwMjMxNjkwNzQyMTk6MDow","showHidden":true,"maxResults":100}' --format json`
>    Filter to `status: "needsAction"`. Flag `due` ≤ today as overdue. Note
>    parent/child via `parent` field. Sort: overdue first, then by `position`.
>
> 2. Yesterday catch-up pull (for baseline Step 1c reconcile):
>    `gws tasks tasks list --params '{"tasklist":"MDE5NTgyMDkwMjMxNjkwNzQyMTk6MDow","showCompleted":true,"showHidden":true,"updatedMin":"<YESTERDAY-1d>T00:00:00.000Z","maxResults":100}' --format json`
>    Return every task with its current `status` and `id` — the coordinator
>    does the reconcile against yesterday's daily note.
>
> **Completeness requirement (added 2026-05-19 after validation run #2):**
> You MUST enumerate **every** task with `status: "needsAction"` in the
> response. Do NOT summarize, sample, or stop after the first few. the operator
> typically has 20–40 open tasks. If your `open_tasks` array has fewer than
> 10 entries, **re-read the bash output completely** before returning —
> partial parsing is the #1 failure mode. After enumerating, set the
> response's `open_tasks_total` field to the count and self-check that it
> matches the array length.
>
> **Due-date format:** `due` must be an ISO date string OR JSON `null` —
> never `""`.
>
> If `gws tasks` fails, return `status: "skipped"` with reason — never block.
>
> Return ONE final JSON:
> `{status, open_tasks: [...], open_tasks_total: N, overdue_count: N, catchup_pull: [...], skipped_reason?}`

### Spawning pattern

In one message, call:

```
Agent({subagent_type: "Explore", team_name: "${TEAM}", name: "calendar-worker", description: "calendar pull", prompt: <calendar prompt>})
Agent({subagent_type: "Explore", team_name: "${TEAM}", name: "notion-worker",   description: "notion pull",   prompt: <notion prompt>})
Agent({subagent_type: "Explore", team_name: "${TEAM}", name: "obsidian-worker", description: "obsidian scan", prompt: <obsidian prompt>})
Agent({subagent_type: "Explore", team_name: "${TEAM}", name: "gtasks-worker",   description: "gtasks pull",   prompt: <gtasks prompt>})
```

All four return their final JSON message into your conversation. Capture
their wall-clock durations for telemetry.

## Step 3: Yesterday Catch-up Reconcile (coordinator)

The coordinator owns this step because it touches files (Edit on yesterday's
daily note) and workers are Explore (read-only). Inputs:

- `gtasks_worker.catchup_pull` — gtask IDs + current state
- For Notion daily-note IDs, the coordinator does the per-ID GETs inline
  (small N — usually 0–5 IDs)

Then reconcile per baseline Step 1c into:
`pull_completions`, `push_completions`, `both_match`, `unverifiable`,
`manual_completions_no_source`.

## Step 4: Memory ↔ Calendar Gap Check (coordinator)

Cross-check `obsidian_worker.memory_meetings` against
`calendar_worker.today + tomorrow + (optional) gws calendar +agenda --week`.
Build `memory_calendar_gaps`. Same logic as baseline Step 1b.

## Step 5: Score and Rank Top 3 (coordinator)

Apply the baseline Step 6 scoring formula deterministically. Apply the
department-starvation guard (baseline Step 6 §"Department starvation guard").
No deviation — this skill is testing the **runtime architecture**, not the
scoring logic.

## Step 6: Compose Briefing

Render exactly the baseline Step 7 template. Add one line at the very top of
the briefing header so the A/B is visible:

```
_Run: {RUN_ID} · Mode: {MODE} · Team: ${TEAM} · workers: cal={ms} notion={ms} obs={ms} gtask={ms}_
```

Otherwise the output is identical to baseline.

## Step 7: Trust Gate

Identical to baseline Step 8 + 8b. Coordinator runs `AskUserQuestion`.

## Step 8: Execute Approved Actions

Identical to baseline Step 9 (write daily note, optional Notion status
patches, mobile mirror, save to logs). Coordinator runs these — workers are
already idle/done.

## Step 9: Telemetry

Emit ONE row to `logs/_telemetry.jsonl` via `scripts/telemetry.sh`, with skill
name `start-day-team` (NOT `start-day` — so /weekly-review can tell them
apart). Extra fields beyond baseline:

```json
{
  "team_run": true,
  "team_name": "${TEAM}",
  "worker_durations_ms": {"calendar": N, "notion": N, "obsidian": N, "gtasks": N},
  "worker_statuses":     {"calendar": "ok|skipped", ...},
  "coordinator_overhead_ms": N,    # total wall - max(worker_durations)
  "baseline_skill_for_comparison": "start-day"
}
```

## Step 10: Teardown

```
TeamDelete()
```

The team has done its work. Cleanup removes `~/.claude/teams/${TEAM}/` and
the matching task list.

## Failure Modes (worker-specific)

- **Any single worker returns `status: skipped`:** add its source to the
  briefing's "Skipped Sources" section, continue with the other three. This
  is the same graceful-degradation contract as baseline.
- **A worker crashes / times out / never returns its JSON:** treat as
  skipped. Surface in the briefing footer as `⚠️ Worker {role} failed — see
  experiment notes` so the A/B run is honest about coverage.
- **All four workers skipped:** render a minimal briefing from `state/priorities.yaml`
  + yesterday's log only, mark telemetry status `failed`.
- **Coordinator-side failures (mode check, config parse, trust gate):**
  identical to baseline — refuse / surface clearly.

## Experiment Log

Append a row to `state/experiments/start-day-team.md` after each run:
`date | RUN_ID | total_ms | max_worker_ms | coord_overhead_ms | quality_delta_vs_baseline (-1|0|+1) | notes`.

Manually score `quality_delta` after eyeballing: did this briefing match what
baseline would have produced? `-1` if worse, `0` if equivalent, `+1` if
somehow better (likely never — same logic).

The experiment ends when:
- 5+ runs show `quality_delta == 0` AND wall-time savings are real → promote
  this skill to default (`/start-day`) and archive the sequential baseline.
- ≥1 run shows `quality_delta < 0` with no clear fix → abandon and document
  why in the same file.
