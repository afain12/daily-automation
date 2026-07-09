---
name: refine-calendar
description: >-
  Calendar refinement after /start-day. Converts today's 3 outputs + must-convert
  meetings into proposed Google Calendar execution blocks using
  scripts/calendar_planning.py, stages a preview in .context/preview/, and can
  apply the blocks to Google Calendar only after explicit approval via the gated
  scripts/output_calendar.py adapter.
coo_twin:
  category: briefing
  mode_required: any
  writes_external: true
  preflight: required
  experimental: true
---

# /refine-calendar — Calendar Refinement

You run this after `/start-day` to turn the day's Top 3 outputs and calendar
anchors into a small set of protected execution blocks.

The calendar is a **commitment layer, not a task mirror**. Tasks stay in Notion /
Google Tasks / Obsidian. Calendar blocks are only for protected time that produces
an output or unblocks someone.

## Safety model

- Default run is preview-only.
- Live Google Calendar writes require BOTH:
  1. COO mode `approved` or `auto`.
  2. Explicit user approval, represented in CLI by `--apply --yes`.
- Never auto-delete, move, or update existing events. Insert-only.
- Every created block carries a deterministic `action_id` and is stamped in
  `.context/applied/` only after `google_api.py calendar insert` returns `status: ok`.
- Re-running skips any already-stamped action_id.
- Execution Plan lines use `▹`, never `- [ ]`, so `/end-day` checkbox parsing is safe.

## Constants

```bash
REPO_DIR="/Users/user/daily-automation"
CONFIG="${REPO_DIR}/config/calendar.yaml"
PREVIEW="${REPO_DIR}/.context/preview"
TODAY="$(date +%F)"
```

## Step 0: Mode Check (AAC BOUNDED / GOVERNED)

```bash
cd /Users/user/daily-automation
eval "$(scripts/preflight.sh)"   # MODE / NOTION_OK / GWS_OK / VAULT_OK / SKIP_WRITES
```

If `MODE=locked`, refuse and exit. If `GWS_OK=0`, run preview only from any
available daily-note data and state that Calendar live read/write is unavailable.

## Step 1: Preview after /start-day

Run the morning preview:

```bash
python3 scripts/refine_calendar.py --date "${TODAY}" --mode "${MODE}"
```

Optional high-value gap-fill input:

```bash
python3 scripts/refine_calendar.py \
  --date "${TODAY}" \
  --mode "${MODE}" \
  --task-candidates-json ".context/preview/task-candidates-${TODAY}.json"
```

Candidate file format is documented at `references/task-candidate-format.md`. Use it for smaller high-value Notion/Google Tasks subsets scored by `attention_pct` and `value_score`; the runner keeps `Ship These 3` first, then appends the highest-attention candidate tasks for large open gaps.

This script:
1. Reads `vault/daily/${TODAY}.md` from `/start-day` output.
2. Extracts `## Today — Ship These 3` into `DailyOutput` objects.
3. Reads day type from `_Day type: ..._` unless `--day-type` is provided.
4. Reads current Google Calendar anchors via:
   `python3 scripts/google_api.py calendar ${TODAY}`.
5. Loads `config/calendar.yaml`.
6. Calls the pure helper:

```python
plan = calendar_planning.propose_calendar_blocks(outputs, anchors, config=cfg,
                                                 day_type=day_type, date=TODAY)
md = calendar_planning.render_execution_plan_markdown(plan)
```

7. Stages:
   - `.context/preview/exec-plan-${TODAY}.json`
   - `.context/preview/exec-plan-${TODAY}.md`

The `.context/preview/` path is intentional: `/start-day` pending-write audits
ignore this directory, so preview files do not create false pending-write alarms.

## Step 2: Review the gate

Show the operator the rendered `## Execution Plan` and summarize:

- number of blocks
- proposed minutes
- flags (`over_capacity`, `prep_no_preroom`, `all_day_anchor`,
  `field_day_dropped_focus`)
- exact file staged under `.context/preview/`

Ask whether to apply. Do not apply unless the operator says “apply”, “add them”,
“write to calendar”, “go ahead”, or equivalent.

## Step 3: Apply to Google Calendar (approved only)

Only after approval, run:

```bash
python3 scripts/refine_calendar.py --date "${TODAY}" --mode approved --apply --yes
```

or, if applying an already-staged preview directly:

```bash
python3 scripts/output_calendar.py \
  --preview ".context/preview/exec-plan-${TODAY}.json" \
  --mode approved \
  --apply
```

`output_calendar.py` is the only live-write adapter. It wraps the canonical Google
API route:

```bash
python3 scripts/google_api.py calendar insert \
  --summary "▹ PREP — Visit Jumpstart Medical" \
  --start "2026-06-22T10:00:00-04:00" \
  --end "2026-06-22T10:30:00-04:00" \
  --description "COO Twin refine-calendar execution block ... action_id: ..."
```

It then stamps:

```bash
scripts/action_id.sh stamp "$ACTION_ID" '{"calendar_event_id":"...","target":"google_calendar"}'
```

Stamp only after confirmed 2xx / `status: ok`. Never stamp on failure.

## Config rules currently enabled

From `config/calendar.yaml`:

- `all_day_busy_default: false`
  - All-day business calendar items are informational by default and do not zero
    out the workday.
  - Per-anchor `busy: true` can still consume the day later if the adapter supplies it.
- `field_day_bounds.end: "19:00"`
  - Field days can schedule evening CAPTURE/EOD blocks after relationship meetings.
- `important_meeting_keywords: ["lunch", "dinner", "breakfast", "important", "pitch"]`
  - Important relationship meetings override routine filtering and require a full 30-minute PREP block when space exists.
  - If a full 30 minutes cannot fit, surface `important_prep_no_30min` instead of silently squeezing weak prep.
- `field_focus_min_window_min: 120`
  - Field days still avoid task spam, but a huge gap between fixed commitments becomes a FOCUS block for the highest-value Top 3 output instead of downtime.
- Normal days remain `09:00–17:30`.

## Telemetry (AAC OBSERVED)

Append one row per run through the shared helper after preview/apply completes:

```bash
scripts/telemetry.sh refine-calendar "rc-${TODAY//-/}-$(date +%H%M)" "$DURATION_MS" "$STATUS" "$JSON_PAYLOAD"
```

Telemetry payload must include: `mode`, `day_type`, `blocks_proposed`,
`open_minutes`, `proposed_minutes`, `unplaced`, `preview_staged`,
`apply_requested`, `created_count`, `skipped_count`, and `wrote_calendar`.
For preview-only runs, `wrote_calendar=false`. For apply runs, set it true only
when at least one insert returned `status: ok` and was stamped.

## Error handling

- `locked` → refuse.
- `observe` / `draft` → preview only; do not apply.
- Calendar read fails → render from daily note with `anchors=[]`, mark partial.
- Calendar insert fails → stop immediately, do not stamp the failed block, report the error.
- Already-stamped action_id → skip; do not duplicate events.
- Never retry automatically. The user should decide whether to rerun.

## Verification commands

```bash
python3 -m unittest tests.test_calendar_planning tests.test_output_calendar tests.test_refine_calendar tests.test_end_day_orchestrator
bash scripts/skill_lint.sh .claude/skills/refine-calendar/SKILL.md
```

## Telegram / Gateway usage

This skill is installed in the default Hermes profile and enabled for gateway use.
From Telegram, the operator can say any of:

```text
/skill refine-calendar
run refine calendar preview
run refine calendar for today after start day
```

Telegram sessions must use terminal commands, not `execute_code`. The command to
run is:

```bash
cd /Users/user/daily-automation
eval "$(scripts/preflight.sh)"
python3 scripts/refine_calendar.py --date "$(date +%F)" --mode "$MODE"
```

If the operator approves the preview from Telegram with “apply”, “add them”, “write to
calendar”, or “go ahead”, run exactly:

```bash
cd /Users/user/daily-automation
eval "$(scripts/preflight.sh)"
python3 scripts/refine_calendar.py --date "$(date +%F)" --mode approved --apply --yes
```

Do not ask him to open a terminal. Do not emit `MEDIA:` tags. Return the concise
phone-first summary directly in chat.

## Phone-first output shape

Keep the final output short:

```text
Execution Plan staged: .context/preview/exec-plan-YYYY-MM-DD.json
Blocks: 5 · Proposed: 2h · Mode: draft preview-only

▹ 10:00–10:30 PREP · Visit Jumpstart Medical
▹ 11:30–11:50 CAPTURE · Visit Jumpstart Medical
...

Say “apply” to write these to Google Calendar.
```
