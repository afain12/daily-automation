---
name: setup
description: >-
  First-run onboarding for a new user. Walks through two early-funnel question
  clusters — which data sources you use, and what streams of work you want to
  track separately — then writes config/streams.yaml + state/setup-answers.yaml.
  Local-file only; no API calls. Token collection, Notion probing, role mapping,
  and trust-mode selection come in later steps of /setup (not implemented here).
coo_twin:
  category: setup
  mode_required: any
  writes_external: false
  preflight: optional      # bootstrap path; coo_mode.yaml may not exist yet
  experimental: false
---

# /setup — Onboarding Steps A + B (Source Presence + Streams)

You are running the very front of the onboarding funnel for a new user of this
COO Twin system. **Scope is deliberately narrow.** Two question clusters only:

- **Step A** — which external sources does the user actively use? (~30s)
- **Step B** — what streams of work should the system track separately? (~2–3 min)

**Not in scope here** (handled by later steps of /setup that already exist or
are planned): API token collection, /notion-probe, /notion-map role mapping,
mobile mirror config, trust-mode selection (`state/coo_mode.yaml`). Do not
collect those here. If the user asks about them, point them at the next steps
and finish this skill cleanly.

This skill **writes to local files only** — no Notion, no Google, no network.

## Constants

```
REPO_DIR        = "C:/Users/aaron/daily-automation"
CONFIG_DIR      = "${REPO_DIR}/config"
STATE_DIR       = "${REPO_DIR}/state"
STREAMS_FILE    = "${CONFIG_DIR}/streams.yaml"
ANSWERS_FILE    = "${STATE_DIR}/setup-answers.yaml"
VALIDATOR       = "${REPO_DIR}/scripts/streams_check.py"
TODAY           = <current date in YYYY-MM-DD format>
RUN_ID          = "su-${TODAY//-/}-$(date +%H%M%S)"
BACKUP_FILE     = "${CONFIG_DIR}/streams.backup-${TODAY}.yaml"
ANSWERS_VERSION = 1
```

All file I/O must use UTF-8. The project runs on Windows + Git Bash and
Python's default cp1252 will mangle em-dashes / unicode. Use
`PYTHONIOENCODING=utf-8` for inline python blocks and `encoding="utf-8"` on
every `open()` call.

## Step 0: Mode Check (AAC GOVERNED)

```bash
export PYTHONIOENCODING=utf-8

MODE=$(scripts/check_mode.sh) || {
  echo "🛑 Agent is locked. /setup refuses to run."
  exit 0
}
```

- `locked` → refuse (exit 0, no telemetry; locked runs don't happen).
- `observe` → run all prompts and validation, but **do not write** to
  `${STREAMS_FILE}` or `${ANSWERS_FILE}`. Print what would have been written.
  Telemetry status = `ok` with `dry_run: true` in extra.
- `draft` / `approved` / `auto` → normal behavior. /setup is human-driven by
  definition; the only "write" is to local config, so we don't gate per-write.

Capture `RUN_START_MS=$(date +%s%3N 2>/dev/null || python -c "import time; print(int(time.time()*1000))")` for telemetry.

## Step 1: Pre-flight — Existing config check

If `${STREAMS_FILE}` already exists and is non-empty:

1. Read it. If it parses as YAML and contains a `streams:` key with ≥1 entry,
   treat it as the **incumbent config** (this is the case for Aaron's repo —
   `streams.yaml` is already populated).
2. Use AskUserQuestion to ask:

   **"`config/streams.yaml` already has {N} streams configured ({comma-separated key list}). What do you want to do?"**

   Options:
   - **Back up and replace** — Copy the current file to
     `config/streams.backup-{TODAY}.yaml`, then proceed with Step A.
   - **Show me the current config first** — Print the streams section, then
     re-ask this question. (Don't fall through into a write path until the user
     explicitly picks replace or abort.)
   - **Abort** — Exit without writing. Telemetry status = `aborted`.

3. If the user picks "Back up and replace":
   ```bash
   cp "${STREAMS_FILE}" "${BACKUP_FILE}"
   ```
   Confirm with: `Backed up existing config to config/streams.backup-{TODAY}.yaml. Proceeding.`

   If `${BACKUP_FILE}` already exists (user ran /setup twice today), append a
   counter: `streams.backup-{TODAY}-2.yaml`, `-3.yaml`, etc. Never overwrite a
   backup silently — the whole point of the backup is recoverability.

If `${STREAMS_FILE}` does not exist or is empty → no backup needed, skip to
Step A.

Also check whether `${ANSWERS_FILE}` exists. If yes, offer to **re-use prior
answers** as defaults in the prompts below (still confirm each one — don't skip
the prompts entirely). This is how the success-criterion re-run produces a
byte-identical output.

## Step A: Source Presence (1–3 questions, ~30 seconds)

### A.1 — Which sources do you use?

Use AskUserQuestion (multi-select) to ask:

**"Which of these do you actively use? (Multi-select)"**

Options (header: "Sources"):
- **Notion** — Business databases (tasks, CRM, activity log, meeting notes)
- **Google Calendar** — Meetings and time-blocking
- **Google Tasks** — Quick-capture to-dos with due dates
- **Obsidian** — Local-file notes, daily journal, reflections
- **Gmail** — Email triage and follow-up

Record each as a boolean. Empty selection is allowed but warn the user that
most skills depend on at least one of these and the system will produce
minimal value without any.

### A.2 — Obsidian vault path (only if Obsidian was selected)

Use AskUserQuestion (single text/select):

**"Where is your Obsidian vault?"**

Options:
- **Use the default (`./vault` inside this repo)** — Recommended; matches the
  project's existing vault layout.
- **Custom path** — User types an absolute or relative path. Validate that
  the directory exists; if not, ask whether to create it now (`mkdir -p`) or
  re-enter the path.

Store as `obsidian.vault_path`. If the user picks the default, store
`"./vault"` as the literal value (don't resolve to an absolute path — keeping
it relative makes the answers file portable).

### A.3 — Defer everything else

Do **not** ask for: Notion API token, Google OAuth status, Gmail credentials,
calendar IDs, tasklist IDs, or any role-mapping. State this once in chat:

> Tokens and role mapping are collected in a later step of /setup. For now I'm
> just recording which sources you use so downstream steps know what to wire.

## Step B: Streams (~2–3 minutes)

### B.1 — How many streams?

Use AskUserQuestion (single-select):

**"What separate streams of work do you want this system to track separately?"**

Brief explanatory blurb in chat first:

> Streams are the top-level buckets used to group tasks, meetings, and notes.
> Most users have 2–5. Each stream gets its own section in your daily briefing.
> Examples: a business unit ("Acme Sales"), a side project ("Open source X"),
> a life area ("Personal / Family"), a client account.

Options:
- **1** (single bucket — rare; mostly useful for personal-only workflows)
- **2**
- **3**
- **4**
- **5**
- **6**
- **7**
- **8** (maximum supported; more becomes unmanageable)

Store the integer N. **Validate 1 ≤ N ≤ 8.** If a user types a number outside
the range, re-prompt.

### B.2 — Per-stream details

For each stream i in 1..N, ask THREE questions in a row (one AskUserQuestion call
per question, sequentially). Don't batch — the user needs to see each stream
build up. Total prompts: A.1 + (maybe A.2) + B.1 + N×3 ≤ 3 + N×3. For N=8 that's
27 prompts, well under the 60-prompt warning.

#### B.2.a — Display name
**"Stream {i} of {N}: What's the display name?"**

Free text. This is what shows up as `### {display_name}` in daily-note department
headers. Examples: "Acme Sales", "Personal", "Open Source / Side Projects".
Trim whitespace. Reject empty string and re-prompt.

#### B.2.b — Short key
**"Stream {i} ({display_name}): What's a short key for this stream?"**

Free text, but normalize aggressively:
- lowercase
- replace spaces and underscores with `-`
- strip every character that isn't `[a-z0-9-]`
- collapse repeated `-` into one
- strip leading/trailing `-`

Examples:
- "Acme Sales" → `acme-sales`
- "Open Source" → `open-source`
- "United IPA" → `united-ipa`

Show the normalized version to the user before accepting:

> I'll use `acme-sales` as the key. OK?

Validate:
- Must match `^[a-z][a-z0-9-]{0,30}$` (must start with a letter, ≤31 chars).
- Must not already be used by an earlier stream in this run (re-prompt).
- Reserved: `default`, `none`, `null` — re-prompt if user lands on one of these.

#### B.2.c — Keywords (optional)
**"Stream {i} ({display_name}): Any keywords that route to this stream? (3–10 recommended, or skip)"**

Free text — user enters a comma-separated list. Parse, lowercase, trim each, dedupe.
Skip / empty input is allowed (the stream simply won't auto-match against calendar
event titles or attendee names — that's fine for explicit-only routing).

Show the parsed list before accepting:

> Keywords: `acme, sales-call, demo, pricing`. OK?

### B.3 — Default / catch-all stream

After all N streams are collected, use AskUserQuestion (single-select):

**"Which stream is the catch-all for items that don't match any other?"**

Options: each `display_name` collected, one per option, plus a synthetic
"Other / Personal" option if the user hasn't already named one. (Don't force
this synthetic option — if the user explicitly named a stream like "Misc" or
"Personal", that's what they want.)

The selected stream gets `is_default: true`. Exactly one stream must have this
flag (validated by `streams_check.py` — see §default_stream_count rule).

## Step 2: Render `state/setup-answers.yaml`

Write the raw answers FIRST (before streams.yaml) so the file is available
even if streams generation fails. Schema:

```yaml
# state/setup-answers.yaml — raw answers from /setup Steps A+B.
# Re-running /setup with this file present allows deterministic re-generation
# of config/streams.yaml. Bump `version` when the schema changes incompatibly.

version: 1
run_id: "{RUN_ID}"
captured_at: "{ISO8601 timestamp}"

# Step A: source presence
sources:
  notion: true            # bool
  google_calendar: true
  google_tasks: false
  obsidian: true
  gmail: false

obsidian:
  vault_path: "./vault"   # only present if sources.obsidian == true

# Step B: streams (in declaration order — order is load-bearing for routing)
streams:
  - key: "acme-sales"
    display_name: "Acme Sales"
    keywords: ["acme", "sales-call", "demo", "pricing"]
    is_default: false
  - key: "personal"
    display_name: "Personal"
    keywords: []
    is_default: true

# Reserved for later /setup steps. Always written, even when empty, so future
# /setup invocations can layer on without schema migration. Do not populate
# from this skill — those steps come later.
tokens: {}              # notion_api_token, google_oauth_status, etc.
notion_role_mapping: {} # master_tasks_data_source_id, provider_crm_data_source_id, etc.
trust_mode: null        # coo_mode value (observe | draft | approved | auto | locked)
```

Write via python heredoc with `encoding="utf-8"`:

```bash
mkdir -p "${STATE_DIR}"
PYTHONIOENCODING=utf-8 python - <<'PY'
import yaml, datetime, os
answers = {
    "version": 1,
    "run_id": os.environ["RUN_ID"],
    "captured_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
    "sources": { ... },              # from Step A.1
    "obsidian": { ... } or None,     # only if obsidian selected; omit key entirely otherwise
    "streams": [ ... ],              # from Step B
    "tokens": {},
    "notion_role_mapping": {},
    "trust_mode": None,
}
# Drop None-valued top-level keys so the file is minimal.
answers = {k: v for k, v in answers.items() if v is not None}
with open(os.environ["ANSWERS_FILE"], "w", encoding="utf-8") as f:
    yaml.safe_dump(answers, f, sort_keys=False, allow_unicode=True, default_flow_style=False)
PY
```

**Determinism note:** `sort_keys=False` plus iterating streams in user-input
order keeps the file byte-identical on re-runs sourced from the same answers.
The success criterion depends on this.

## Step 3: Render `config/streams.yaml`

Build the streams config from the Step B answers. Emit the same header comment
block the Aaron-version uses (paraphrased — don't hardcode "Lincoln Lab" etc.):

```yaml
# Streams — the generic equivalent of "departments" or "business units".
#
# Every skill that currently hardcodes department names should iterate this
# file instead. The migration is incremental — a skill can keep its hardcoded
# list while it's being refactored, as long as the list stays consistent with
# this file (run scripts/streams_check.py to verify).
#
# Generated by /setup on {TODAY} from state/setup-answers.yaml.
# Re-run /setup to regenerate; edit by hand only if you understand the
# iteration-order + is_default contract documented at the bottom of this file.

streams:
  - key: acme-sales
    display_name: "Acme Sales"
    is_default: false
    # Notion Workspace-select option values that route to this stream.
    # Initially seeded with the display_name; tune later as your Notion
    # Workspace select options stabilize.
    workspace_values:
      - "Acme Sales"
    keywords:
      - acme
      - sales-call
      - demo
      - pricing

  - key: personal
    display_name: "Personal"
    is_default: true
    # Catch-all stream; receives anything that doesn't match another stream's
    # workspace_values or keywords.
    workspace_values:
      - "Personal"
    keywords: []

# ============================================================
# Inheritance contract
# ============================================================
# - Daily-note department headers are rendered from `display_name` in stream order.
# - Calendar tagging walks streams in order and picks the first whose keywords
#   match the event summary. Order matters when a keyword could match multiple
#   streams — declare the more-specific stream first.
# - Routing inference (e.g. /capture-meeting attendee → stream) uses keywords
#   the same way: first-match-wins, in declaration order.
# - The `is_default: true` stream is the fallback when no match. Exactly one
#   stream must have it (validated by scripts/streams_check.py).
```

**Rules for the generator:**

- `workspace_values` is seeded with a single entry equal to `display_name`.
  The user can refine these later once they run /notion-probe + /notion-map.
  Initial seed beats empty list (streams_check.py's reverse-direction check
  treats unused workspace_values as `info`, not blocking — see line 96–102 of
  the validator).
- `keywords` carries the user's input verbatim (lowercased, deduped).
- Emit streams in user-declared order (do NOT alphabetize). Order is
  load-bearing for first-match-wins routing.
- Use 2-space indentation, `allow_unicode=True`, `default_flow_style=False`,
  `sort_keys=False`.
- Quote `display_name` and `workspace_values` entries (they may contain
  spaces / special chars); leave `key` and `keywords` unquoted when possible.
- Don't write the file directly — render to a string, then `open(..., "w", encoding="utf-8")`.

If `MODE == "observe"`, print the would-be content to stdout with a banner
`# [dry-run] would write to config/streams.yaml:` and skip the actual write.

## Step 4: Validate

```bash
PYTHONIOENCODING=utf-8 python "${VALIDATOR}" --json > "${STATE_DIR}/tmp/setup-validate-${RUN_ID}.json"
VALIDATE_EXIT=$?
```

Parse the JSON output. Three outcomes:

- **`VALIDATE_EXIT == 0`** (consistent, or only `info`-severity issues) →
  Success. Print a summary:

  > config/streams.yaml validated. N streams configured.
  > {info-severity issues if any, prefixed with "ℹ️"}

- **`VALIDATE_EXIT == 1`** (blocking issues detected) →
  - Restore the backup over the freshly-written `${STREAMS_FILE}`:
    ```bash
    if [ -f "${BACKUP_FILE}" ]; then
      cp "${BACKUP_FILE}" "${STREAMS_FILE}"
    else
      rm -f "${STREAMS_FILE}"   # no prior, so remove the bad file
    fi
    ```
  - Display the blocking issues with their `code` and `detail` fields.
  - Explain how to fix:
    > Validation failed with {N} blocking issue(s). I restored the prior
    > config (or removed the new file if none existed). The most common
    > causes are:
    > - **default_stream_count**: exactly one stream must be marked default.
    >   Re-run /setup and pick a single catch-all stream in Step B.3.
    > - **workspace_value_unmapped**: an entry in config/sources.yaml
    >   references a workspace value that no stream covers. This usually
    >   means sources.yaml needs updating after /setup, not the other way
    >   around — that's handled by /notion-map later.
    > - **calendar_bucket_orphan**: a bucket in sources.yaml's
    >   calendar_business_keywords has no matching stream key. Either rename
    >   the bucket in sources.yaml or pick a stream key that matches.
  - `state/setup-answers.yaml` is **kept** (so the user can re-run with the
    same answers and only adjust the problematic stream).
  - Telemetry status = `validation_failed`. Exit 0 (skill ran, validation
    refused).

- **`VALIDATE_EXIT == 2`** (malformed YAML) → render error and treat as
  `error` status. Should not happen if Step 3 used PyYAML's safe_dump, but
  defensive cleanup matters.

## Step 5: Summary

After a successful run, display:

```markdown
# /setup Steps A+B complete

**Sources recorded:** {comma-separated list, e.g. "Notion, Google Calendar, Obsidian"}
**Streams configured:** {N}
{for each: "- {key} ({display_name}){' [default]' if is_default else ''}"}

**Files written:**
- config/streams.yaml ({byte count} bytes)
- state/setup-answers.yaml ({byte count} bytes)
{if backup created: "- config/streams.backup-{TODAY}.yaml (your previous config)"}

**Next steps** (not handled by this skill):
1. `/notion-probe` — scan your Notion workspace for canonical databases
2. `/notion-map` — derive field mappings + workspace_values from the probe
3. (later /setup steps) — collect tokens, pick a trust mode, configure mobile mirror

Run `/notion-probe` next.
```

In `observe` mode, replace "Files written" with "Files **would have** been
written (dry-run, mode=observe)" and skip the byte counts.

## Step 6: Telemetry (AAC OBSERVED)

```bash
END_MS=$(date +%s%3N 2>/dev/null || python -c "import time; print(int(time.time()*1000))")
DURATION_MS=$((END_MS - RUN_START_MS))

EXTRA=$(PYTHONIOENCODING=utf-8 python -c "
import json
print(json.dumps({
    'mode': '${MODE}',
    'dry_run': ${DRY_RUN_BOOL_LITERAL},          # 'true' or 'false' (lowercased)
    'sources_selected': ${SOURCES_COUNT},
    'sources': ${SOURCES_LIST_JSON},             # e.g. ['notion','obsidian']
    'streams_count': ${N_STREAMS},
    'backup_created': ${BACKUP_BOOL_LITERAL},
    'validate_exit': ${VALIDATE_EXIT},
    'reused_prior_answers': ${REUSED_ANSWERS_BOOL_LITERAL}
}))
")

scripts/telemetry.sh setup "${RUN_ID}" "${DURATION_MS}" "${STATUS}" "${EXTRA}"
```

Status values:
- `ok` — files written (or would-have-been-written in observe mode), validation passed
- `aborted` — user cancelled at the Step 1 backup-confirm question
- `validation_failed` — files generated but `streams_check.py` returned blocking issues
- `error` — anything else (YAML write error, malformed validator output, etc.)

## Error Handling

- **`scripts/check_mode.sh` exits 1 (locked)** → refuse at Step 0. No telemetry.
- **User aborts at Step 1** → no writes, no backup, telemetry `aborted`.
- **User aborts mid-Step B** → no writes (haven't written anything yet at that
  point — answers file is only written in Step 2 after B is complete).
  Telemetry `aborted`.
- **`PyYAML` missing** → the validator script already errors loudly with
  `ERROR: PyYAML required.` Surface that error and exit with telemetry
  `error`. Do not attempt a shell-out fallback; /setup is a one-time human
  workflow, and "install pyyaml" is a reasonable demand.
- **Permission denied writing config/ or state/** → render the error verbatim,
  do not retry. Telemetry `error`.
- **Backup write fails** → do NOT proceed with the overwrite. Render the
  error, exit with telemetry `error`.
- **Never crash on a malformed Step A.2 vault path** — ask again.
- **Never silently overwrite** an existing backup file — append `-2`, `-3`, …
  counter.

## Success Criterion

Run on a clean tmp directory with no existing `config/streams.yaml`. After
answering questions for ≤5 minutes, the file at `config/streams.yaml` exists,
`scripts/streams_check.py` exits 0 against it, and re-running the skill with
the same answers (sourced from `state/setup-answers.yaml`) produces a
byte-identical output.

If the second-run output differs from the first, the most likely culprits are
(in order of likelihood): non-deterministic key ordering in `yaml.safe_dump`
(fix: `sort_keys=False`), timestamp leakage from Step 2's `captured_at` into
streams.yaml (fix: keep it in answers.yaml only), or stream re-ordering (fix:
preserve user-declared order in both files).
