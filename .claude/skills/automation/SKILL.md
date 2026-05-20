---
name: automation
description: >-
  Runs saved prompts on a cadence. Reads state/automations.yaml, lists which
  automations are due to fire now, presents a trust gate, then executes
  approved prompts in-session and delivers output to the configured channel
  (Obsidian note, daily-note append, or stdout). Scheduling lives in external
  cron — this skill answers "what should run right now?" and "execute it."
coo_twin:
  category: admin
  mode_required: any
  writes_external: true
  preflight: required
  experimental: false
---

# /automation — Cron-style saved prompts

You are running due automations from `state/automations.yaml`. Each automation
is a saved prompt + cadence + delivery target. This skill answers two
questions: **what is due right now?** and **execute approved ones, then
update bookkeeping.**

**Read-first, write-on-approval.** Each automation passes through an
individual trust gate before its prompt is executed.

## Constants

```
REPO_DIR     = "C:/Users/aaron/daily-automation"
AUTOMATIONS  = "${REPO_DIR}/state/automations.yaml"
TODAY        = <current date in YYYY-MM-DD format>
RUN_ID       = "auto-${TODAY//-/}-$(date +%H%M%S)"
```

## Step 0: Preflight (AAC GOVERNED)

```bash
eval "$(scripts/preflight.sh)"
if [ "$MODE" = "locked" ]; then
  echo "🛑 Agent is locked (state/coo_mode.yaml). /automation refuses to run."
  exit 0
fi
```

- `locked` → refuse.
- `observe` → list due automations but execute nothing (SKIP_WRITES=1).
- `draft`   → standard: each automation gates individually.
- `approved`/`auto` → execute without gate if every due automation's id has a
  prefix in `state/coo_mode.yaml :: approved_action_prefixes`.

Capture `RUN_START_MS` for telemetry.

## Step 1: Compute Due Automations

```bash
DUE_JSON=$(python scripts/automation_due.py due)
N_DUE=$(echo "$DUE_JSON" | python -c "import sys,json; print(len(json.load(sys.stdin)['due']))")
```

If `N_DUE == 0`:
- Print "✓ No automations due. Next eligible check at next cron tick."
- Emit telemetry with `status=ok`, `n_due=0`, `n_executed=0`.
- Exit cleanly.

## Step 2: Present Trust Gate

For each due automation, display:

```
[N/total] {id} — {description}
  cadence: {cadence}  last_run: {last_run or "never"}
  delivery: {delivery} → {delivery_target}
  prompt (excerpt): "{first 200 chars of prompt}..."
```

If invoked interactively (Aaron at the terminal), use `AskUserQuestion` with one
question per due automation: **"Run {id}?"** Options: **Yes / Skip / Skip and disable**.

If invoked non-interactively (Cowork scheduler, `--unattended` flag), apply
mode-based default:
- `draft`    → skip everything (require human approval).
- `approved` → execute everything whose id-prefix is allow-listed; skip rest.
- `auto`     → execute all due automations.

## Step 3: Execute Approved Automations

For each approved automation, execute its `prompt` field in the current
Claude session context. Treat the prompt as if Aaron had pasted it directly —
read the files it references, run the queries it asks for, produce the output
it specifies.

**Important constraints:**
- The prompt MAY reference any repo file, run any read-only command, query
  Notion/Calendar/Tasks via the configured tooling. It MAY NOT escalate beyond
  the current `MODE`'s write permissions.
- If the prompt requests an external write that would normally require its
  own trust gate (Notion PATCH, calendar event creation), pause and ask Aaron
  before proceeding — the `/automation` outer gate approves the automation as
  a whole; individual external writes inside it still gate per their normal
  skill rules.
- Delivery targets get the {date} placeholder expanded to today (YYYY-MM-DD).

### Delivery channels

| delivery              | Action |
|-----------------------|--------|
| `obsidian`            | Write the result to a new file at `delivery_target` (e.g. `vault/notes/Weekly-Review-2026-05-20.md`). Overwrite if it already exists for today. |
| `daily_note_append`   | Append a section to today's daily note (`vault/daily/{date}.md`). `delivery_target` is the section header (e.g. `## Provider Nudges`). Skip if the section already exists in the file (idempotent). |
| `stdout`              | Print to terminal only — Aaron triages manually. No file write. |
| `notion`              | (reserved — not yet implemented) Would PATCH a Notion page. Refuse until implemented. |
| `telegram`            | (reserved — not yet implemented) Would push to Telegram bot. Refuse until implemented. |

## Step 4: Update Bookkeeping

For each successfully executed automation:

```bash
python scripts/automation_due.py stamp <id> --status ok
```

For failures (output couldn't be produced, delivery target inaccessible, etc.):

```bash
python scripts/automation_due.py stamp <id> --status failed
```

A `stamp` updates `last_run` to NOW and appends one entry to `automations.yaml`'s
`history:` list. Future `/automation` invocations use `last_run` to compute due-ness.

**Do NOT stamp** if the automation was approved by Aaron but the actual execution
errored before producing output — leave `last_run` unchanged so the next run
retries. Stamp only when delivery actually landed.

## Step 5: Telemetry

```bash
DURATION_MS=$(( $(date +%s%3N 2>/dev/null || python -c "import time; print(int(time.time()*1000))") - RUN_START_MS ))
EXTRA=$(python -c "import json; print(json.dumps({
  'mode': '$MODE',
  'n_due': $N_DUE,
  'n_executed': $N_EXECUTED,
  'n_skipped': $N_SKIPPED,
  'n_failed': $N_FAILED,
  'executed_ids': $EXECUTED_IDS_JSON
}))")
scripts/telemetry.sh automation "$RUN_ID" "$DURATION_MS" ok "$EXTRA"
```

## Step 6: Summary

Print a one-line summary:

```
/automation: 2 executed, 0 skipped, 0 failed (3 due of 3 enabled, mode: draft)
```

## Scheduling

`/automation` does NOT schedule itself. External cron triggers it:

- **Cowork scheduled run** — add `/automation` to the existing morning + evening
  scheduler entries alongside `/start-day` and `/end-day`. The skill no-ops cleanly
  when nothing is due, so frequent invocation is cheap.
- **Windows Task Scheduler** — local laptop fallback. Same pattern: run on whatever
  cadence covers your shortest-period automation (probably daily).

The cadence in `state/automations.yaml` is the source of truth for **what** runs;
the external scheduler just decides **when to check**.

## Adding a new automation

1. Append an entry to `state/automations.yaml` with `enabled: false`, `last_run: null`.
2. Test the prompt by invoking `python scripts/automation_due.py due --include-all`
   to verify parsing, then `/automation` with the entry temporarily forced.
3. Once it produces clean output, flip `enabled: true`.

Anti-pattern: do NOT inline tasks that already have their own skill. If `/start-day`
already covers what you want, schedule `/start-day` directly via cron — don't
wrap it in an automation.

## Failure modes & recovery

| Failure                     | Behavior |
|-----------------------------|----------|
| `automations.yaml` missing  | Print warning, exit 0 (no automations to run). |
| `automations.yaml` malformed | Print error with line context, exit 1. Don't stamp anything. |
| Prompt execution errored    | Skip stamp (so retries on next run), surface error in summary, telemetry status=`partial`. |
| Delivery target unreachable | Print prompt output to stdout as fallback, mark `partial`, do NOT stamp. |
| Two automations want the same daily-note section | Run them sequentially; second one sees the section already exists and skips (idempotent guard). |
