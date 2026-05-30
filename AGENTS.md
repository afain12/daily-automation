# COO Twin — Daily Automation System (Codex view)

**Mirror of `CLAUDE.md` for OpenAI Codex CLI.** OpenAI Codex reads this file as the
canonical project-memory file (per the AGENTS.md spec). Claude Code reads `CLAUDE.md`.
The two files share an identical project body — **when a project fact changes,
update both.** Tooling deltas (Claude Code vs Codex) live in separate "Operating Notes"
sections at the bottom of each.

Personal Chief of Staff system that unifies Notion, Obsidian, Google Calendar,
and Google Tasks into a single terminal workflow. Aaron manages multiple businesses
(lab, IPA, Nestmate, Dock Pro / Cardio Pro) and this system imposes structure on
the daily chaos across all of them.

## Skills

| Skill | Phase | Status | Description |
|-------|-------|--------|-------------|
| `/start-day` | 1 | Active | Morning briefing + daily plan |
| `/capture-meeting` | 2 | Active | Meeting note splitter (Notion + Obsidian + Calendar) |
| `/end-day` | 3 | Active | Day close retro, planned vs actual, carry-forwards |
| `/start-day-team` | 1 | Experimental | Parallel fan-out variant of /start-day (4 worker subagents) |
| `/end-day-team` | 3 | Experimental | Parallel variant of /end-day + braindump-extractor |
| `/capture-meeting-team` | 2 | Experimental | Parse-then-fan-out variant; 5 parallel write workers after trust gate |
| `/notion-probe` | 0 | Active | Read-only Notion workspace scanner; scores DBs against canonical roles (genericization foundation) |
| `/notion-map` | 0 | Active | Property-role mapper; consumes /notion-probe output, writes draft sources.yaml stub |
| `/notion-template-install` | 0 | Active | Installs 4 canonical Notion DBs from version-controlled JSON templates (empty-workspace path) |
| `/setup` | 0 | Active | User-facing onboarding questionnaire — Step A (source presence) + Step B (stream definitions); writes streams.yaml |
| `/weekly-review` | 4 | Planned | Weekly patterns + insights (needs 2+ weeks of logs) |

Skills are defined for Claude Code under `.claude/skills/<name>/SKILL.md`. Codex
does not yet have an equivalent skills directory in this repo — Codex sessions
follow the same workflow conventions but invoke them through prompts rather than
slash-commands. If/when a Codex skills folder is created, document the path here.

## Project Structure

```
.claude/skills/                   — Claude Code project skills (authoritative)
.claude/agents/                   — Custom subagent definitions (Claude Code)
.codex/config.toml                — Codex CLI config (this tool's settings live here)
.agents/skills/                   — External dependency skills (fetched via skills-lock.json, don't edit)
config/
  sources.yaml               — Notion DB IDs, data source IDs, field mappings, business keywords
  routing-rules.yaml         — Meeting note routing rules (/capture-meeting)
scripts/
  preflight.sh               — Unified Step 0: mode check + NOTION/GWS/VAULT availability (`eval $(scripts/preflight.sh)`)
  check_mode.sh              — Reads state/coo_mode.yaml; called by preflight.sh and legacy callers
  skill_lint.sh              — Validates COO Twin SKILL.md files (frontmatter + AAC discipline)
  telemetry.sh               — Appends a row to logs/_telemetry.jsonl
  action_id.sh               — Idempotency: generate / check / stamp action_ids
  phi_scan.sh                — PHI input gate for /capture-meeting
state/
  coo_mode.yaml              — System-wide write-mode (observe | draft | approved | auto | locked)
  profile.yaml               — Aaron-specific profile: businesses, ambiguous persons, operating gates, preferences
  priorities.yaml            — Carry-forward items between days
  roadmap.md                 — Future enhancements (speculative, not current state)
  tmp/                        — Scratch JSON (don't commit)
.context/                    — Staged Notion block-children payloads (PATCH bodies)
  *.json                      — Top-level: still pending. /start-day flags these.
  applied/                    — After PATCH succeeds, MOVE the file here.
logs/
  YYYY-MM-DD.md              — Daily briefing + EOD retro logs (retained 90 days)
  _telemetry.jsonl           — Append-only one-row-per-run skill telemetry
docs/
  claude-code-setup.md       — Claude Code permission modes / settings (not Codex)
  anthropic-best-practices.md — Canonical Anthropic guidance (not Codex)
vault/                        — Obsidian vault root
  inbox/, daily/, meetings/, notes/, CardioPro/, Labaide/, Nestmate/, United IPA/, Notes to self/, AI Engineering/
```

**Vault sync:** Business folders are copied from `C:/Users/aaron/OneDrive/Documents/Obsidian Vault/`
into `vault/` via `cp -ru`. These are read-only mirrors — Obsidian edits happen in OneDrive,
daily notes and meeting notes are written directly to vault/.

## Data Sources

### Notion (REST API via curl)

Authentication: `$NOTION_API_TOKEN` env var (in `.secrets/notion.env`; see Codex Operating Notes below for how Codex picks it up)
API Version: `2025-09-03`

**IMPORTANT:** Use the `/v1/data_sources/{id}/query` endpoint, NOT `/v1/databases/{id}/query`.
The data_source IDs are different from database IDs. **All IDs live in `config/sources.yaml`** —
that's the single source of truth. Read from there rather than hard-coding.

Primary databases queried: **Master Tasks**, **Provider CRM**, **Activity Log**, **Meeting Notes**.

Key fields on Master Tasks:
- **Status** (status): "Not started", "In progress", "Waiting", "Done"
- **Workspace** (select): "Lincoln Reference Laboratory", "United IPA", "Nestmate", "Dock Pro", "Other"
- **Due** (date): ISO date
- **Assignee** (people): array of users
- **Task** (title): task name (NOT "Name" — the title property is called "Task")

Overdue = Due date in the past AND Status != "Done"
Stale = `last_edited_time` older than 7 days AND Status != "Done"

### Google Calendar (gws CLI)

```bash
gws calendar +agenda --today --format json     # Today's events
gws calendar +agenda --tomorrow --format json   # Tomorrow's for prep
gws calendar +insert --summary "..." --start ... --end ...   # Create event (NOT events insert --params)
```

### Google Tasks (gws CLI)

```bash
gws tasks tasklists list                         # List all task lists
gws tasks tasks list --params '{"tasklist":"MDE5NTgyMDkwMjMxNjkwNzQyMTk6MDow"}'  # Default list
gws tasks tasks patch ...                        # Use this for writes — curl + `gws auth token` doesn't work
```

Default tasklist ID: `MDE5NTgyMDkwMjMxNjkwNzQyMTk6MDow`

### Obsidian (direct file read/write)

Vault path: `C:/Users/aaron/daily-automation/vault`
Tag conventions: `#review`, `#lab`, `#ipa`, `#nestmate`

## Department Routing Rules

Every item must be assigned to a department:

| Department | Workspace Value | Description |
|------------|----------------|-------------|
| **Nestmate** | "Nestmate" | Urgent care accounts, provider outreach, supply chain |
| **Dock Pro / Cardio Pro** | "Dock Pro" | Cardiac monitoring device rollout — reps, cardiologists, internists |
| **United IPA** | "United IPA" | Provider network, credentialing, claims, sign-up docs |
| **Lincoln Lab** | "Lincoln Reference Laboratory" | Testing panels, pathology, specimens |
| **Other / Personal** | "Other" | Everything else |

### Workspace value conventions (canonical — do not drift)

As of 2026-05-29 Notion reorg, the `Workspace` select on all 4 canonical DBs (Master Tasks, Provider CRM, Activity Log, Meeting Notes) uses the SAME option set:

- `Lincoln Reference Laboratory`
- `United IPA`
- `Nestmate`
- `Dock Pro`
- `Other`

Activity Log additionally preserves `LabAide` as a separate value (Aaron 2026-05-29 — distinct product, not the lab business).

**Rules for any new DB added to this workspace:**
- Use this exact option set verbatim. No abbreviations, no synonyms.
- Never re-introduce `Lincoln Lab` or `Link & Reference Laboratory` as Workspace values (those were the drift the reorg fixed).
- For human-friendly display in CLI briefings, the short name "Lincoln Lab" is still fine — see `state/profile.yaml` `display` field. That's a display-layer translation, not a data-layer drift.
- `sources.yaml` `workspace_values.lab` is the single source of truth for the API value.

**CRITICAL ROUTING RULE:** Do NOT inherit department from a Notion parent task name.
Check the actual Workspace field on each item. If null, infer from context:
- Provider names, clinics, urgent cares, medical practices = typically **Nestmate**
- Cardiac monitoring, reps for cardiac panels, cardiologists = **Dock Pro / Cardio Pro**
- "DOCPRO clients" parent does NOT mean subtasks are Dock Pro — check each individually

This was learned on 2026-04-15 when outreach tasks (Dr Remzy Meny, Dr Rookwood, AFC Urgent Care, etc.)
were incorrectly placed under Dock Pro because they lived under a "DOCPRO clients" parent in Notion.
They were actually Nestmate provider outreach.

## Daily Note Format

Daily notes in `vault/daily/YYYY-MM-DD.md` use department-grouped checkboxes:

```markdown
## Actionable Items by Department

### Nestmate
- [ ] Task with context

### Dock Pro / Cardio Pro
- [ ] Task with context

### United IPA
- [ ] Task with context

### Lincoln Lab
- [ ] Task with context

### Other / Personal
- [ ] Task with context
```

**Rules:**
- Every actionable item gets `- [ ]` checkbox (Aaron checks these off throughout the day)
- Group by department, NEVER by data source (not "Notion section" + "Tasks section")
- Overdue and stale items go into their department section, not a separate section
- Include a "Notion Changes (Last 24 hrs)" section: completed, created, edited
- Include an "End of Day Review" section: completed, carries forward, notes/decisions
- Include a "Backlog - Needs Triage" section for low-priority items not for today

## Information Routing Philosophy

Aaron's three brains:
- **Notion** = Business brain. Tasks, CRM, activity logs, accounts. Operational system of record.
- **Google Tasks** = Quick capture brain. Day-to-day actions, quick to-dos with due dates.
- **Obsidian** = Reflection brain. Daily tracking, learnings, process improvements.

When routing information:
- Action items with business context → Notion
- Quick to-dos, follow-ups, reminders → Google Tasks (with due dates)
- Reflections, learnings, process improvements → Obsidian notes
- Meeting outcomes get SPLIT: actions → Notion, learnings → Obsidian, follow-ups → Tasks
- Decisions → Notion Activity Log (single source of truth), Obsidian gets a link not a copy

### Granola → Notion routing (two patterns, both legitimate)

Granola meeting notes land in Notion via one of two patterns. Tooling must
recognize both before declaring a "sync gap":

1. **New Meeting Notes DB entry** — one meeting → one row. Detected by querying the Meeting Notes data source.
2. **Appended section inside an existing topic page** — for recurring threads
   (e.g. `Cardio Pro Rollout`, `Essen Healthcare 4/21`, `Nestmate weekly`),
   the Granola URL + bullets get pasted as a dated `## YYYY-MM-DD — <title>`
   section inside the topic page. Does NOT appear in the Meeting Notes DB.

**Coverage check rule:** before flagging a Granola URL as missing, run a
workspace-wide `/v1/search` for an 8-char fragment of the URL. Only declare
"⚠️ Sync gap — push from Granola app" when BOTH the Meeting Notes DB query
AND the workspace search return zero matches. Topic-page hits should be
surfaced as `📎 Topic-page append: ... → landed in {parent page}`, not as a sync gap.

### Staged Notion writes (`.context/` lifecycle)

When a skill prepares a Notion `PATCH /v1/blocks/{id}/children` payload that
needs a trust gate or human review, it lands as a JSON file in `.context/`.
The lifecycle is mandatory:

1. **Stage** — write the `{"children":[...]}` payload to `.context/<name>.json`.
   Optionally include a top-level `status: "pending"` field; absence of a
   status field does NOT mean unwritten.
2. **Apply** — PATCH the payload to Notion.
3. **Cleanup** — immediately `mv .context/<name>.json
   .context/applied/<name>-<YYYY-MM-DD>.json`. The date is when the write
   landed, not when the file was created. **Never leave applied payloads in
   `.context/` top-level** — /start-day's pre-flight will keep flagging them
   as pending writes (the 2026-04-23 → 2026-04-28 false-positive incident).

`/start-day` only scans top-level `.context/*.json`, never `.context/applied/`.
Files with no status field are surfaced as "unverified — verify push status,"
not as "unwritten."

**Search workspace-wide before declaring missing.** Notion content can live in
databases OR as block content inside topic pages. Before saying anything is
"not in Notion," run `/v1/search` against a unique fragment (URL, person name,
title keyword). Aaron's append-to-topic-page workflow is intentional.

## Cross-cutting Agent Discipline (AAC v1.1 applied)

Adopted 2026-05-18 after auditing the three active skills against the Agent
Automation Creator framework. Full audit at `state/aac-audit-of-current-skills.md`;
framework reference at `state/aac-framework-extraction.md`.

The five disciplines (BOUNDED, GROUNDED, GATED, OBSERVED, GOVERNED) are wired
through every skill via four shared helpers and one state file. Every new skill
MUST honor these patterns.

### Operating mode — `state/coo_mode.yaml`

System-wide mode controls write behavior across all skills:

| Mode | Behavior |
|------|----------|
| `observe` | Read-only. No writes to any external system. Briefings still render. |
| `draft` | **Default.** Every write goes through a trust gate. |
| `approved` | Trust gate auto-approves action_ids whose prefix matches `approved_action_prefixes`. |
| `auto` | Full auto for skills listed in `auto_skills` (empty by default). |
| `locked` | Emergency stop. Every skill refuses at Step 0. |

Every skill begins with `MODE=$(scripts/check_mode.sh) || exit` at Step 0. New skills
should use `eval "$(scripts/preflight.sh)"`, which sets `MODE`, `NOTION_OK`,
`GWS_OK`, `VAULT_OK`, `SKIP_WRITES`, and `PREFLIGHT_WARNINGS` in one call.

### Telemetry — `logs/_telemetry.jsonl`

Append-only JSONL. One row per skill run via `scripts/telemetry.sh`. Required
fields per row: `ts`, `skill`, `run_id`, `duration_ms`, `status`. Never edit
rows in place.

### Idempotency — `scripts/action_id.sh` + `.context/applied/`

Every external write carries an `action_id` of the form
`{skill}:{target}:{date}:{8-char-hash}`. Before executing, skills call:

```bash
AID=$(scripts/action_id.sh generate <skill> <target> <date> <payload>)
scripts/action_id.sh check "$AID" && skip || run_write
# ... after success ...
scripts/action_id.sh stamp "$AID" '{"notion_page_id":"..."}'
```

Stamped action_ids live as JSON files in `.context/applied/{aid}.json`. Re-runs
no-op. Failed writes are NOT stamped — they retry on next run.

### PHI input gate — `scripts/phi_scan.sh`

`/capture-meeting` Step 2.5 scans raw notes for SSN / DOB / MRN patterns BEFORE
LLM parsing. PHI detection refuses the run and logs to `logs/_phi_refusals.jsonl`.
This is the AAC GATED input gate. It does NOT make the system HIPAA-compliant.

### Confidence + source citation on routed items

`/capture-meeting` Step 5 trust gate displays:
- `[CATEGORY conf:0.92]` per item — confidence 0.0–1.0
- `Source line N: "<original text>"` — every claim cites its origin
- `action_id: capture-meeting:meeting-key:date:hash` — for audit + idempotency

Items with `conf < 0.70` auto-route to Uncategorized.

### Daily briefing source markers

`/start-day` Step 7 renders `[notion:abcd…]`, `[gtask:xyzw…]`, `[cal]`, or
`[derived]` next to every Top 3 item.

### When building a new skill

Fill in all 16 AAC spec sections (see `state/aac-framework-extraction.md` §4)
before building. A worked example for `/provider-followup-nudge` is in
`state/aac-audit-of-current-skills.md` §6.

Every COO Twin SKILL.md MUST include a `coo_twin:` block in its YAML frontmatter
(see CLAUDE.md for the full schema and `scripts/skill_lint.sh` for enforcement).
The block has six required fields: `category`, `mode_required`, `writes_external`,
`preflight`, `experimental`, and optionally `phi_gate` + `parallel_workers`.
Vendored external skills lack this block and are auto-skipped by the linter.

## Calendar Business Tagging Keywords

(defined in `config/sources.yaml`):

- **lab:** lab, lincoln, testing, sample, specimen, pathology, phlebotomy, draw, panel
- **ipa:** ipa, united, provider, network, credentialing, claims, saipa, sovereign, phoenix
- **nestmate:** nestmate, account, nest
- **dock_pro:** dock, cardio
- Events matching no keyword → "untagged"

## Key Principles

1. **Read-first, write-on-approval.** Never auto-write without trust gate confirmation.
2. **Graceful degradation.** If any source is unavailable, run with what's available. Never crash.
3. **Local state is primary.** Config, logs, and state live in this repo, not agent memory.
4. **Business tagging.** Every item tagged by department using Workspace field or keyword matching.
5. **Route, don't dump.** Parse streams of info into the right tool — don't pile everything in one place.
6. **Close the loop.** /end-day scans all Notion DBs for today's changes, routes next steps.
7. **Time-blocking.** A task is a suggestion; a calendar block is a commitment.
8. **System evolves.** Capture workflow improvements. Surface patterns proactively.

## Error Handling Patterns

All skills follow these patterns:
- **Notion timeout:** `--max-time 60` on all curl calls
- **Auth failure (401):** Warn user to check NOTION_API_TOKEN, skip source
- **Database not found (404):** Warn to share DB with integration, skip source
- **gws CLI failure:** Skip Calendar/Tasks gracefully, suggest `gws auth login --scopes calendar,tasks`
- **gws API not enabled (403):** Warn to enable API in Google Cloud Console
- **Empty response:** Not an error — display "No items found in {database name}"
- **Never retry automatically.** Report clearly and continue with available sources.

## Team-skill pattern

The `*-team` skills implement parallel fan-out locally via Claude Code's Agent tool.
Each is a **coordinator** that spawns N sub-agents in parallel via a single message
with multiple Agent calls, then synthesizes their structured JSON returns.

Discipline locked in across all team skills:
- **Workers read; coordinator writes.** Trust gate stays in the coordinator. Workers
  use read-only `Explore` subagent type (no Edit/Write).
- **One Agent message, N parallel calls.**
- **Each worker has a strict JSON return contract** declared in its prompt.
- **Telemetry under the team skill name** (e.g. `start-day-team`).
- **TEAM name is RUN_ID-keyed** for concurrent-safety.

Codex does not currently expose the same `Agent` tool primitive, so team-skill variants
are Claude-Code-only today. Equivalent fan-out from Codex would need to be re-implemented
against Codex's sub-process model — not done.

## Codex Operating Notes

Codex CLI specifics (delta from Claude Code):

- **Config file:** `.codex/config.toml`. There is no `.codex/skills/` directory in this repo;
  Codex-launched workflows run from this AGENTS.md file and direct prompts.
- **Secrets:** `NOTION_API_TOKEN` lives in `.secrets/notion.env` (the canonical store).
  Source it before running Codex sessions that hit Notion:
  `source .secrets/notion.env && codex ...`
- **No permission-modes equivalent.** Codex does not have Claude Code's `auto` / `acceptEdits` /
  `plan` modes or `autoMode.environment` rules. Trust gates in this project are enforced
  by the skill logic itself (the AAC GATED discipline + `state/coo_mode.yaml`), not by the agent tooling.
- **No sub-agent / parallel-fan-out primitive** in Codex today — see "Team-skill pattern" above.
- **Telemetry still applies.** Codex sessions should still call `scripts/telemetry.sh` at end
  of run so `/weekly-review` sees them.

For the Claude Code equivalents of these notes see `docs/claude-code-setup.md` and
`docs/anthropic-best-practices.md`. Both are read-relevant to Codex too as background — Codex
doesn't enforce them, but the underlying skill discipline (telemetry, idempotency, PHI gate, mode file)
applies regardless of which agent is driving.

## Pointers

- **Project source of truth (data_source IDs etc.):** `config/sources.yaml`
- **AAC framework reference:** `state/aac-framework-extraction.md`
- **AAC audit of current skills:** `state/aac-audit-of-current-skills.md`
- **Roadmap / future enhancements:** `state/roadmap.md`
- **Full approved design:** `~/.gstack/projects/daily-automation/aaron-master-design-20260414-103924.md`
- **Claude Code's view of the same project:** `CLAUDE.md` (update together)
