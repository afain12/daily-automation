# COO Twin — Daily Automation System

Personal Chief of Staff system that unifies Notion, Obsidian, Google Calendar,
and Google Tasks into a single terminal workflow. Aaron manages multiple businesses
(lab, IPA, Nestmate, Dock Pro / Cardio Pro) and this system imposes structure on
the daily chaos across all of them.

**Mirror of `AGENTS.md` for Claude Code.** OpenAI Codex reads `AGENTS.md` as its
canonical project-memory file; Claude Code reads this one. The two files share an
identical project body — **when a project fact changes, update both.** Tooling deltas
(Claude Code vs Codex) live in separate sections at the bottom of each:
Claude Code → `docs/claude-code-setup.md` + `docs/anthropic-best-practices.md`;
Codex → "Codex Operating Notes" section in `AGENTS.md`.

## Skills

| Skill | Phase | Status | Description |
|-------|-------|--------|-------------|
| `/start-day` | 1 | Active | Morning briefing + daily plan |
| `/capture-meeting` | 2 | Active | Meeting note splitter (Notion + Obsidian + Calendar) |
| `/end-day` | 3 | Active | Day close retro, planned vs actual, carry-forwards |
| `/start-day-team` | 1 | Experimental | Parallel fan-out variant of /start-day (4 worker subagents) |
| `/end-day-team` | 3 | Experimental | Parallel variant of /end-day + braindump-extractor for Activity Log mining |
| `/capture-meeting-team` | 2 | Experimental | Parse-then-fan-out variant; 5 parallel write workers after trust gate |
| `/notion-probe` | 0 | Active | Read-only Notion workspace scanner; scores DBs against canonical roles (genericization foundation) |
| `/notion-map` | 0 | Active | Property-role mapper; consumes /notion-probe output, writes draft sources.yaml stub |
| `/notion-template-install` | 0 | Active | Installs 4 canonical Notion DBs from version-controlled JSON templates (empty-workspace path) |
| `/setup` | 0 | Active | User-facing onboarding questionnaire — Step A (source presence) + Step B (stream definitions); writes streams.yaml |
| `/automation` | 4 | Active | Cron-style saved prompts; reads state/automations.yaml; weekly-review + provider-followup-nudge now run through this |
| `/vault-health` | 4 | Active | Read-only vault audit: orphan notes, broken wikilinks, untagged notes, stale inbox. Trust-gated batch fixes. |
| `/meeting-prep` | 2 | Active | Pre-meeting context dossier: attendees → CRM/Activity Log/Meeting Notes/vault. Read-only. |
| `/weekly-review` | 4 | Superseded | Now an automation entry in state/automations.yaml — invoke via `/automation` when due |

The `*-team` skills are experimental siblings that re-implement their baseline using
parallel sub-agent fan-out. Same input/output contract, same trust gate. See
`state/experiments/start-day-team.md` for the A/B methodology. Promote a team variant
to default only after 5+ runs at `quality_delta == 0` and demonstrated wall-time win.

## Project Structure

```
.claude/skills/
  start-day/SKILL.md             — Morning briefing skill (authoritative)
  capture-meeting/SKILL.md       — Meeting note routing skill
  end-day/SKILL.md               — Day close retro skill
  start-day-team/SKILL.md        — Experimental fan-out variant
  end-day-team/SKILL.md          — Experimental fan-out variant
  capture-meeting-team/SKILL.md  — Experimental fan-out variant
.claude/agents/                   — Custom subagent definitions (read-only workers reused across team skills)
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
  vault_search.py            — BM25-lite search over vault/ + logs/ (no embeddings; called from /start-day Top-3 context)
  vault_health.py            — Vault audit: orphans, broken wikilinks, untagged notes, stale inbox (companion to /vault-health)
  automation_due.py          — Companion to /automation: due-check, last_run stamping, history bookkeeping
state/
  coo_mode.yaml              — System-wide write-mode (observe | draft | approved | auto | locked)
  profile.yaml               — Aaron-specific profile: businesses, ambiguous persons, operating gates, preferences
  automations.yaml           — Saved prompts + cadence + delivery channel; consumed by /automation
  priorities.yaml            — Carry-forward items between days (/end-day writes, /start-day reads)
  roadmap.md                 — Future enhancements (speculative, not current state)
  tmp/                        — Scratch JSON for curl payloads / response parsing (don't commit)
.context/                    — Staged Notion block-children payloads (PATCH bodies)
  *.json                      — Top-level: still pending. /start-day flags these.
  applied/                    — After PATCH succeeds, MOVE the file here (named `<base>-<YYYY-MM-DD>.json`)
                                so /start-day stops flagging it. Never delete — keeps an audit trail.
logs/
  YYYY-MM-DD.md              — Daily briefing + EOD retro logs (retained 90 days)
  _telemetry.jsonl           — Append-only one-row-per-run skill telemetry
docs/
  claude-code-setup.md       — Permission modes, settings.json layout, auto-mode tuning
  anthropic-best-practices.md — Canonical Anthropic Claude Code guidance applied to this repo
vault/                        — Obsidian vault root
  inbox/                     — Fleeting notes, quick captures (surfaced by /start-day)
  daily/                     — Daily notes (YYYY-MM-DD.md format)
  meetings/                  — Meeting notes (created by /capture-meeting)
  notes/                     — Permanent/evergreen notes
  CardioPro/                 — Synced from OneDrive: Dock Pro / Cardio Pro notes
  Labaide/                   — Synced from OneDrive: Lincoln Lab notes
  Nestmate/                  — Synced from OneDrive: Nestmate notes
  United IPA/                — Synced from OneDrive: IPA notes
  Notes to self/             — Synced from OneDrive: personal reflections
  AI Engineering/            — Synced from OneDrive: research/reference notes
```

**Vault sync:** Business folders are copied from `C:/Users/aaron/OneDrive/Documents/Obsidian Vault/`
into `vault/` via `cp -ru`. These are read-only mirrors — Obsidian edits happen in OneDrive,
daily notes and meeting notes are written directly to vault/.

## Data Sources

### Notion (REST API via curl)

Authentication: `$NOTION_API_TOKEN` env var in `.claude/settings.local.json`
API Version: `2025-09-03`

**IMPORTANT:** Use the `/v1/data_sources/{id}/query` endpoint, NOT `/v1/databases/{id}/query`.
The data_source IDs are different from database IDs. **All IDs live in `config/sources.yaml`** — that's
the single source of truth. Read from there rather than hard-coding.

Primary databases queried: **Master Tasks**, **Provider CRM**, **Activity Log**, **Meeting Notes**.

Key fields on Master Tasks:
- **Status** (status): "Not started", "In progress", "Waiting", "Done"
- **Workspace** (select): "Lincoln Lab", "United IPA", "Nestmate", "Dock Pro", "Other"
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
| **Lincoln Lab** | "Lincoln Lab" | Testing panels, pathology, specimens |
| **Other / Personal** | "Other" | Everything else |

**CRITICAL ROUTING RULE:** Do NOT inherit department from a Notion parent task name.
Check the actual Workspace field on each item. If null, infer from context:
- Provider names, clinics, urgent cares, medical practices = typically **Nestmate**
- Cardiac monitoring, reps for cardiac panels, cardiologists = **Dock Pro / Cardio Pro**
- "DOCPRO clients" parent does NOT mean subtasks are Dock Pro — check each individually (learned 2026-04-15 when AFC Urgent Care + Dr Remzy Meny were misrouted as Dock Pro instead of Nestmate)

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

## Information Routing

Three brains, three roles:
- **Notion** → business system of record (tasks, CRM, activity logs, accounts)
- **Google Tasks** → quick-capture to-dos with due dates
- **Obsidian** → reflections, learnings, process improvements

Routing: action items with business context → Notion. Quick reminders → Tasks.
Reflections/learnings → Obsidian. Meeting outcomes SPLIT (actions → Notion,
learnings → Obsidian, follow-ups → Tasks). Decisions → Notion Activity Log
(single source of truth); Obsidian gets a link, not a copy.

### Granola → Notion routing

Two legitimate landing patterns: (1) a new Meeting Notes DB row, or (2) a dated
`## YYYY-MM-DD — <title>` section appended to an existing topic page (e.g.
`Cardio Pro Rollout`, `Essen Healthcare 4/21`, `Nestmate weekly`). Topic-page
appends do NOT appear in the Meeting Notes DB.

**Before flagging a sync gap:** run `/v1/search` workspace-wide for an 8-char
URL fragment. Only declare "⚠️ Sync gap — push from Granola app" when BOTH the
DB query AND search return zero matches. Topic-page hits get surfaced as
`📎 Topic-page append: ... → landed in {parent page}`, not as a gap.

### Staged Notion writes (`.context/` lifecycle)

When a skill prepares a Notion `PATCH /v1/blocks/{id}/children` payload that
needs a trust gate or human review, it lands as a JSON file in `.context/`.
The lifecycle is mandatory:

1. **Stage** — write the `{"children":[...]}` payload to `.context/<name>.json`.
   Optionally include a top-level `status: "pending"` field if explicit pending
   semantics are needed; absence of a status field does NOT mean unwritten.
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
MUST honor these patterns or be downgraded from C (LLM judgment) to A (human-gated).

### Operating mode — `state/coo_mode.yaml`

System-wide mode controls write behavior across all skills:

| Mode | Behavior |
|------|----------|
| `observe` | Read-only. No writes to any external system. Briefings still render. |
| `draft` | **Default.** Every write goes through a trust gate. |
| `approved` | Trust gate auto-approves action_ids whose prefix matches `approved_action_prefixes`. Others still gated. |
| `auto` | Full auto for skills listed in `auto_skills` (empty by default). |
| `locked` | Emergency stop. Every skill refuses at Step 0. |

Every skill begins with `MODE=$(scripts/check_mode.sh) || exit` at Step 0. New skills
should use the unified `eval "$(scripts/preflight.sh)"` form, which sets `MODE`,
`NOTION_OK`, `GWS_OK`, `VAULT_OK`, `SKIP_WRITES`, and `PREFLIGHT_WARNINGS` in one call.
Edit `state/coo_mode.yaml` directly to change mode (post-MVE: Telegram `LOCK AGENT` / `UNLOCK AGENT` commands).

### Telemetry — `logs/_telemetry.jsonl`

Append-only JSONL. One row per skill run. Written via `scripts/telemetry.sh`.
Required fields per row: `ts`, `skill`, `run_id`, `duration_ms`, `status`. Each
skill adds its own context (sources_ok, confidence buckets, write counts, mode, …).

The file is the OBSERVED discipline's load-bearing artifact. Never edit rows
in place. `/weekly-review` will read this file to detect drift.

### Idempotency — `scripts/action_id.sh` + `.context/applied/`

Every external write (Notion PATCH, gtask insert, Gmail send, calendar event)
carries an `action_id` of the form `{skill}:{target}:{date}:{8-char-hash}`.
Before executing, skills call:

```bash
AID=$(scripts/action_id.sh generate <skill> <target> <date> <payload>)
scripts/action_id.sh check "$AID" && skip || run_write
# ... after success ...
scripts/action_id.sh stamp "$AID" '{"notion_page_id":"..."}'
```

Stamped action_ids live as JSON files in `.context/applied/{aid}.json`. Re-runs
no-op. Failed writes are NOT stamped — they retry on next run. Per-write
idempotency stamps share the directory with per-payload archives (see
`.context/` lifecycle above); the structure is unchanged.

### PHI input gate — `scripts/phi_scan.sh`

`/capture-meeting` Step 2.5 scans raw notes for SSN / DOB / MRN patterns BEFORE
LLM parsing. PHI detection refuses the run and logs to `logs/_phi_refusals.jsonl`.
This is the AAC GATED input gate. It does NOT make the system HIPAA-compliant —
it prevents the dumbest leakage (accidentally pasted patient identifier).

### Confidence + source citation on routed items

`/capture-meeting` Step 5 trust gate shows per item: `[CATEGORY conf:0.92]`,
`Source line N: "<original text>"`, and `action_id: capture-meeting:meeting-key:date:hash`.
Items with `conf < 0.70` auto-route to Uncategorized regardless of indicator
strength — keeps Aaron classifying a few hard ones, not yes/no'ing many easy ones.

### Daily briefing source markers

`/start-day` Step 7 renders `[notion:abcd…]`, `[gtask:xyzw…]`, `[cal]`, or
`[derived]` next to every Top 3 item — 4-char ID stub for visibility, full
HTML comment for /end-day's exact-ID sync. (AAC GROUNDED.)

### When building a new skill

Fill in all 16 AAC spec sections before building. Blank sections = spec not
ready. Full list at `state/aac-framework-extraction.md` §4; worked example
(proposed `/provider-followup-nudge`) at `state/aac-audit-of-current-skills.md` §6.

Every COO Twin SKILL.md MUST include a `coo_twin:` block in its YAML frontmatter.
Run `scripts/skill_lint.sh` to validate. The block identifies the file as a
first-party skill (vendored external skills lack it and are auto-skipped):

```yaml
---
name: my-skill
description: >-
  One-paragraph what + when.
coo_twin:
  category: briefing | capture | admin | setup
  mode_required: any | draft+ | approved+
  writes_external: true | false       # touches Notion/Calendar/Tasks/anything off-disk
  preflight: required | optional | none
  experimental: false                  # true for *-team variants
  phi_gate: true                       # only if skill ingests free-text user notes
  parallel_workers: 5                  # team skills only
---
```

The lint also enforces:
- A Step 0 mode check (`scripts/preflight.sh` or `scripts/check_mode.sh` or `Step 0` heading)
- Telemetry emission (`scripts/telemetry.sh` or direct `logs/_telemetry.jsonl` append)
- Trust gate language when `writes_external: true`
- `scripts/phi_scan.sh` when `phi_gate: true`

## Calendar Business Tagging

Events are auto-tagged from summary text using keyword lists in `config/sources.yaml`
(buckets: lab, ipa, nestmate, dock_pro; no match → untagged).

## Key Principles

1. **Read-first, write-on-approval.** Never auto-write without trust gate confirmation.
2. **Graceful degradation.** If any source is unavailable, run with what's available. Never crash.
3. **Local state is primary.** Config, logs, and state live in this repo, not Claude memory.
4. **Business tagging.** Every item tagged by department using Workspace field or keyword matching.
5. **Route, don't dump.** Parse streams of info into the right tool — don't pile everything in one place.
6. **Close the loop.** /end-day scans all Notion DBs for today's changes, extracts next steps,
   routes to Tasks/Calendar. Nothing falls through the cracks overnight.
7. **Time-blocking.** Don't just list tasks — offer to block calendar time for high-priority items.
   A task is a suggestion; a calendar block is a commitment.
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

## Team-skill pattern (this repo's fan-out discipline)

The `*-team` skills implement Anthropic's parallelization pattern locally via the
Agent tool. Each `*-team` SKILL.md is a **coordinator** that spawns N sub-agents
in parallel via a single message with multiple Agent calls, then synthesizes
their structured JSON returns.

Discipline locked in across all team skills:
- **Workers read; coordinator writes.** Trust gate stays in the coordinator. Workers
  use `subagent_type: "Explore"` (read-only Bash + Read/Glob/Grep, no Edit/Write).
- **One Agent message, N parallel calls.** Multiple Agent tool uses in a single
  assistant message run concurrently.
- **Each worker has a strict JSON return contract** declared in its prompt — the
  coordinator merges by field, not by free-text parsing.
- **Telemetry under the team skill name** (e.g. `start-day-team`, not `start-day`)
  so `/weekly-review` can A/B the variants from `logs/_telemetry.jsonl`.
- **TEAM name is RUN_ID-keyed** to make concurrent invocations safe. See each
  team skill's §"Parallel safety" for the file-by-file collision analysis.

**Custom subagents — when to extract.** If two `*-team` skills both inline the
same worker (calendar pull, notion pull, etc.), promote the worker to
`.claude/agents/<name>.md` and have both skills reference it. Today the only
extracted one is `.claude/agents/notion-puller.md`; the rest are still inline
in `start-day-team` and `end-day-team`. Repeat extraction as inline prompts drift apart.

## Pointers

- **Claude Code setup (permission modes, settings.json, auto-mode):** `docs/claude-code-setup.md`
- **Anthropic best practices applied to this repo:** `docs/anthropic-best-practices.md`
- **Roadmap / future enhancements:** `state/roadmap.md`
- **Full approved design:** `~/.gstack/projects/daily-automation/aaron-master-design-20260414-103924.md`

## GBrain Configuration (configured by /setup-gbrain)
- Mode: local-stdio
- Engine: pglite
- Config file: ~/.gbrain/config.json (mode 0600)
- Setup date: 2026-05-18
- MCP registered: yes (user scope, gbrain serve)
- Artifacts sync: full (federated source: gstack-brain-aaron)
- Current repo policy: unset (no origin remote)
