# High Output Start-Day / End-Day Overhaul Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task after Aaron approves the spec. This plan is intentionally written as a spec first, not an implementation, and must survive a `/codex` spec review before any code/skill changes land.

**Goal:** Overhaul Aaron's COO Twin `/start-day` and `/end-day` workflow from task-list production into an Andy Grove / High Output Management operating system: daily outputs, leverage, delegation, calendar execution, and measurable end-of-day throughput.

**Architecture:** Preserve the existing COO Twin data plumbing and safety model (preflight, AAC, source markers, trust gates, idempotent writes, Notion/Google/Obsidian routing). Add a new deterministic planning layer that converts sourced tasks/events into `DailyOutput` objects, groups lower-level tasks into production lanes, proposes calendar blocks, and gives `/end-day` a matching output scorecard. Roll out as additive sections first, then promote once validated.

**Tech Stack:** Markdown skills under `.claude/skills/` and `.agents/skills/`, Python helper modules/scripts under `scripts/`, YAML config under `config/` and `state/`, Obsidian daily notes under `vault/daily/`, Google Calendar/Tasks via `python3 scripts/google_api.py`, Notion via Python `urllib.request` reading `.secrets/notion.env` directly.

> [CODEX REVIEW] Good architectural direction, but this line conflicts with current authoritative `.claude/skills/start-day/SKILL.md` and `.claude/skills/end-day/SKILL.md`, which still specify `gws` and shell `curl` in many steps. If this overhaul standardizes on `google_api.py` and Python `urllib`, add an explicit migration task and acceptance criterion that the active skill docs no longer instruct implementers to use `gws`/curl for the touched paths. Otherwise Hermes implementers may follow the old skill text and violate this plan.

---

## 0. Operating Context / Non-Negotiables

### Existing system to preserve

- Project root: `/Users/afain/daily-automation`.
- Active skills:
  - `.claude/skills/start-day/SKILL.md`
  - `.claude/skills/end-day/SKILL.md`
  - `.claude/skills/start-day-team/SKILL.md`
  - `.claude/skills/end-day-team/SKILL.md`
  - vendored mirror `.agents/skills/start-day/SKILL.md`
- Existing script:
  - `scripts/end_day_orchestrator.py`
  - `tests/test_end_day_orchestrator.py`
- Existing configs:
  - `config/sources.yaml`
  - `config/streams.yaml`
  - `state/priorities.yaml`
  - `state/coo_mode.yaml`
- Existing daily note and log examples:
  - `vault/daily/2026-06-17.md`
  - `logs/2026-06-17.md`
  - older logs show repeated Top 3 vs actual-output mismatch.

> [CODEX REVIEW] This inventory is missing several active integration surfaces from `CLAUDE.md`: `/automation`, `/vault-health`, `/meeting-prep`, `scripts/vault_search.py`, `scripts/automation_due.py`, and the newer `/end-day` integrated preview path around `scripts/end_day_orchestrator.py`, `note_harvest`, and `sync-sweep`. They may not all need implementation changes, but the spec should explicitly classify them as "no change expected" or add regression checks. The current end-day orchestrator stages preview JSON under `.context/preview/` specifically so `/start-day` will not flag it as pending; new output scorecard code must preserve that behavior.

### Safety / AAC constraints

This overhaul must not weaken existing safety:

1. **BOUNDED:** all workflows still begin with preflight/mode check and refuse on `locked`.
2. **GROUNDED:** every output must cite its source marker: `[notion:abcd]`, `[gtask:abcd]`, `[cal]`, `[derived]`; calendar block proposals must cite the output they execute.
3. **GATED:** no Google Calendar creation, Google Task creation/patch, Notion patch, or daily note rewrite without trust gate approval.
4. **OBSERVED:** telemetry gains output metrics but existing telemetry remains append-only.
5. **GOVERNED:** external writes use `action_id` and stamp only after confirmed 2xx / verified file write.

> [CODEX REVIEW] Add the project-specific pending-write lifecycle here: top-level `.context/*.json` means pending/unverified and `.context/preview/` is intentionally ignored by `/start-day`. Calendar block previews and output-scorecard previews should not be staged in top-level `.context/` unless they are truly awaiting approval; otherwise the existing pending-write audit will create daily false positives.

### Critical implementation constraints

- `gws` is not installed. Use `python3 scripts/google_api.py` for Calendar/Tasks.
- Do **not** use shell `curl -H "Authorization: Bearer $NOTION_API_TOKEN"`; Hermes token masking breaks it. Use Python `urllib.request`, reading `.secrets/notion.env` directly.
- Do not delegate heavy COO Twin data pulls to subagents; they time out. Direct parent-session scripts only.
- Do not inherit stream from a Notion parent task. Check `Workspace` directly and fall back to `config/streams.yaml` keyword matching.
- Keep local state as source of truth for workflow evolution. Do not encode stable workflow rules only in model memory.

> [CODEX REVIEW] This is correct for Codex/Hermes, but it is currently not true inside the active Claude skill bodies. Treat this as a blocking consistency gap before implementation: update the plan to include "replace touched `gws`/curl instructions in the active skill docs" or scope the implementation so helper scripts encapsulate all Calendar/Notion access and the skill docs call only those scripts.

---

## 1. Management Model: Andy Grove / High Output Management

### 1.1 Replace “tasks” as the top unit with “outputs”

A task is an action. An output is a finished business result.

Example conversion:

| Current item | New output framing |
|---|---|
| `Starling IPA / Luis — confirm 2pm meeting` | `Starling IPA meeting loop closed: confirmed, rescheduled, or deliberately dropped` |
| `GI Medical lunch` | `GI Medical lunch converted into next action and owner` |
| `Ilene + Jonathan task grid` | `1-week provider follow-up grid exists with owner/date for each provider` |

### 1.2 Every output gets a done-state

Each top item must answer:

- What finished artifact/result exists?
- Who is unblocked?
- Which business stream moves?
- What proof indicates completion?
- What calendar block will produce it?

> [CODEX REVIEW] This is the strongest High Output Management part of the plan. To make it operational, define "proof" as a concrete evidence type: checked daily-note source line, Notion Status=Done, Google Task completed, calendar event attended/captured, explicit Aaron correction, or created artifact path/URL. Without this, `/end-day` will fall back to subjective scoring and the output scorecard will not be auditable.

### 1.3 Use Grove leverage categories

Each candidate item receives an `output_type` and leverage classification:

| output_type | Grove meaning | Examples | Calendar priority |
|---|---|---|---|
| `decision_unlock` | decision that unblocks work | approve grid, choose vendor, resolve calendar gap | prime morning |
| `delegation_unlock` | one instruction multiplies team output | assign Ilene/Jonathan/Kader/Ryan | early delegation pass |
| `relationship_revenue` | provider/account movement | GI Medical, Starling, Piris | field/meeting window |
| `operational_system` | process/SOP/integration asset | LabAide SOP, eCW flow, API docs | deep work |
| `followup_batch` | maintenance loop closure | stale CRM follow-ups | batch window |
| `admin_personal` | low-leverage but necessary | tickets, reimbursements | low-energy block |

> [CODEX REVIEW] The categories map well to Grove-style leverage, but the plan should add a meeting loop category or rule. Grove's operating cadence depends heavily on meetings becoming decisions, delegated work, or captured follow-ups. Current `/start-day` already surfaces Meeting Notes and extraction gaps; the new output layer should require every important meeting today to have prep/capture/follow-up handling, even if it is not a Top 3 output.

### 1.4 Output score replaces raw task score at the top

Existing item scoring remains useful, but top-level selection should score *outputs*:

| Signal | Points | Notes |
|---|---:|---|
| Due today / overdue / promised today | +3 | Same as current |
| Unblocks another person/team | +3 | Grove leverage boost |
| Revenue/account/provider relationship movement | +3 | Field-business bias |
| Converts a meeting into a next action | +2 | Meeting capture discipline |
| Creates a reusable system/SOP | +2 | Operational leverage |
| Calendar gap risk | +2 | Prevents silent drift |
| Stale 7+ days | +1 | Existing starvation signal |
| Delegatable with clear owner | +1 | Encourage leverage over doing everything |
| Personal/admin | cap at 3 | Prevents low-leverage items crowding top outputs |

### 1.5 Protect stream starvation, but at output level

Keep existing starvation guard, but apply after output grouping:

1. Build candidate outputs.
2. Select raw top 3–5 by score.
3. If a stream has stale actionable items 7+ days and no selected output, promote its best output into slot #5 or replace the lowest non-critical slot.
4. Never promote suppressed/back-burnered items.
5. Calendar events already scheduled today always surface even if related task is suppressed.

> [CODEX REVIEW] The existing starvation guard deterministically replaces slot #3 only. This plan changes selection to 3 primary + 2 flex and promotes into slot #5 or replaces a non-critical slot. That is probably better, but it is a behavioral change and needs its own tests against `config/streams.yaml` order, stale-days selection, and suppression. Also define what "non-critical" means deterministically so the helper cannot make an opaque model judgment.

---

## 2. New Data Model

### 2.1 Add `DailyOutput` internal object

Implement as a plain Python dataclass or documented dict shape.

Suggested file:

- Create: `scripts/output_planning.py`
- Test: `tests/test_output_planning.py`

```python
@dataclass
class SourceRef:
    source: Literal["notion", "gtask", "calendar", "derived", "crm", "vault"]
    id: str | None
    marker: str
    title: str
    stream: str
    due: str | None = None
    stale_days: int | None = None
    raw: dict[str, Any] = field(default_factory=dict)

@dataclass
class DailyOutput:
    id: str
    title: str
    stream: str
    output_type: str
    done_state: str
    owner: str
    score: int
    score_breakdown: list[str]
    source_refs: list[SourceRef]
    calendar_strategy: str
    recommended_block_minutes: int
    earliest_start_hint: str | None = None
    dependencies: list[str] = field(default_factory=list)
    delegation: list[dict[str, str]] = field(default_factory=list)
    risk_flags: list[str] = field(default_factory=list)
```

> [CODEX REVIEW] Add a stable `source_line_ids` or `completion_refs` concept, not just display `source_refs`. `/end-day` needs to know which exact checkbox/comment, Notion page, Google Task, or calendar capture proves an output moved. Aggregated outputs like "Ilene + Jonathan task grid" may contain several child tasks; the model must represent whether completing one child, all children, or an explicit user correction marks the output shipped.

> [CODEX REVIEW] Consider making `owner` nullable or structured (`owner_type`, `owner_name`). If the owner is Aaron, a teammate, or an external party, end-day handling differs: Aaron-owned work can be scheduled; teammate-owned work becomes delegation/awaiting; external-owned work becomes awaiting/follow-up. A single string will make the leverage/delegation logic brittle.

### 2.2 Add `CalendarBlockProposal`

```python
@dataclass
class CalendarBlockProposal:
    output_id: str
    summary: str
    start: str
    end: str
    block_type: Literal["focus", "prep", "meeting", "capture", "followup", "delegation", "batch", "admin", "buffer", "eod"]
    stream: str
    write_eligible: bool
    confidence: float
    source_markers: list[str]
    flags: list[str]
```

> [CODEX REVIEW] Require timezone-aware RFC3339 datetimes here. Current Calendar/Tasks notes repeatedly warn about local naive times and EDT/EST offsets. Tests should cover America/New_York DST behavior and all-day/fixed-meeting events so proposed blocks do not drift or overlap silently.

### 2.3 Add `DelegationAsk`

```python
@dataclass
class DelegationAsk:
    output_id: str
    person: str
    ask: str
    needed_by: str | None
    channel: str | None
    source_markers: list[str]
    write_eligible: bool = False  # communication drafting remains gated separately
```

### 2.4 Add `OutputScorecard`

```python
@dataclass
class OutputScorecard:
    date: str
    outputs_planned: int
    outputs_shipped: int
    outputs_partially_moved: int
    delegation_asks_sent: int
    people_unblocked: int
    meetings_captured: int
    calendar_blocks_created: int
    real_vs_tracked_delta: int
```

> [CODEX REVIEW] Add `outputs_dropped`, `outputs_delegated`, and `outputs_blocked_waiting` or clarify where those decisions live. Grove-style output control is not just shipped/partial; deliberately dropping, delegating, or parking a low-leverage output is a real management decision and should not look like failure.

---

## 3. New `/start-day` Output Shape

### 3.1 Preserve existing sections, but reorder around outputs

Current `/start-day` renders:

1. flags
2. calendar
3. Top 3 Outcomes
4. actionable items by stream
5. meetings
6. Notion changes
7. follow-ups
8. suppressed

New preferred order:

```markdown
# Daily Output Plan — {TODAY} ({day})

_Run: {RUN_ID} · Mode: {MODE}_

## ⚠️ System Flags / Calendar Gaps / Pending Writes
...

## 1. Today's Outputs
| # | Output | Stream | Done-state | Owner | Leverage | Score | Source |
|---|---|---|---|---|---|---:|---|

## 2. Calendar Execution Plan
| Time | Block | Output | Type | Write? |
|---|---|---|---|---|

## 3. Delegation Queue
| Person | Ask | Output unlocked | Needed by | Source |
|---|---|---|---|---|

## 4. Meeting Prep + Capture Discipline
| Meeting | Prep block | Capture block | Follow-up block |
|---|---|---|---|

## 5. Production Lanes
### Lane A — Must Ship Today
### Lane B — Delegation Unlocks
### Lane C — Revenue / Relationship Follow-ups
### Lane D — Operational Systems
### Lane E — Admin / Personal Batch

## 6. Stream Backlog by Business
### Lincoln Lab
### United IPA
### Nestmate
### Dock Pro / Cardio Pro
### Other / Personal

## 7. Recent Meeting Recaps / Extraction Needs
...

## 8. Notion Changes / Provider Follow-ups / Vault
...

## 9. End-of-Day Scorecard Template
- Outputs shipped:
- People unblocked:
- Meetings captured:
- Revenue/account movement:
- Decisions made:
- Carry-forward:

## 🔇 Suppressed
...
```

> [CODEX REVIEW] This is comprehensive but likely too heavy for the phone briefing. The first viewport should probably be: system flags, today's 3 primary outputs, next calendar block/delegation action. Production lanes, backlog, recaps, and scorecard template can remain below. Add an acceptance criterion that the top daily-note section is readable on mobile without horizontal table overflow; Markdown tables are especially fragile on phones.

### 3.2 Keep backwards-compatible anchors

Because `/end-day` currently extracts Top 3, calendar, checkboxes, and source markers, the new daily note must keep recognizable anchors during transition:

- Include an alias heading:
  - `## Top 3 Outcomes` can remain, but render as a compatibility subset of `## 1. Today's Outputs`.
- Keep checkbox lines with `<!-- gtask:ID -->` and `<!-- notion:ID -->` comments.
- Keep `## Actionable Items by Stream` for at least one release, even if moved below Production Lanes.
- Keep `## End of Day Review` exactly enough for `/end-day` to patch.

> [CODEX REVIEW] Strengthen this from headings to exact shape. Current `/end-day` and tests parse checkbox lines with `<!-- gtask:ID -->` / `<!-- notion:ID -->`, `## Actionable Items by Stream`, and `## End of Day Review`. Add fixture tests using `vault/daily/2026-06-17.md` or a copied fixture to prove old parsers still extract checked completions after the new sections are inserted.

> [CODEX REVIEW] Do not "replace Top 3 with compatibility alias" until `/end-day` has been promoted and tested. For the shadow period, keep an actual `## Top 3 Outcomes` numbered list in the same visible format, even if generated from the top `DailyOutput` objects. The prose skill currently extracts "Top 3 Outcomes", not arbitrary aliases.

### 3.3 New Top Outputs selection rules

- Produce **3 primary outputs + 2 optional flex outputs**.
- Primary outputs should fit available calendar capacity.
- If existing calendar is overloaded, reduce outputs rather than pretending all can ship.
- Explicitly identify output failure modes:
  - `blocked_by_external_person`
  - `calendar_gap`
  - `needs_decision`
  - `needs_delegation`
  - `needs_capture_after_meeting`
  - `too_large_for_today`

### 3.4 Calendar blocks are proposals, not writes

`/start-day` should propose blocks in the briefing but only write after approval.

Default proposed blocks:

| Block | Duration | Rule |
|---|---:|---|
| Command Review | 15–20m | after routine/gym |
| Deep Work 1 | 45–60m | highest leverage output |
| Delegation Pass | 10–15m | before 11am |
| Deep Work 2 | 45–60m | second output or operational system |
| Meeting Prep | 15–30m | before important meeting |
| Capture Block | 15–20m | immediately after meeting |
| Follow-up Send Block | 15–30m | after capture if needed |
| Stream Batch | 30–45m | followups grouped by business |
| Admin Batch | 20–30m | late-day |
| EOD Scorecard | 15–20m | late-day |

> [CODEX REVIEW] Add capacity rules before proposal rendering: do not propose more block minutes than open working time, include travel/meeting buffers, and degrade to fewer outputs if fixed meetings dominate the day. The plan states this in 3.3, but `propose_calendar_blocks` needs a deterministic test for overloaded days.

### 3.5 Calendar write gate options

At trust gate, add choices:

- **A) Write daily note only**
- **B) Write daily note + create calendar execution blocks**
- **C) Write daily note + create blocks + mark selected Notion outputs In Progress**
- **D) Preview only**

Calendar create rules:

- Dedupe live calendar: skip if event with same summary and start ±15 minutes already exists.
- Never create blocks overlapping fixed meetings unless labeled `buffer` or user explicitly confirms.
- Add `source_markers` in calendar description.
- Use action IDs: `start-day:cal:{date}:{hash}`.
- Do not create outbound communication events or send messages.

> [CODEX REVIEW] Option C ("mark selected Notion outputs In Progress") is risky for aggregated outputs. Require the trust gate to show the exact Notion page IDs and skip outputs sourced from Google Tasks, CRM rows, calendar events, or derived/manual items unless there is a one-to-one Master Tasks page. This avoids mutating the wrong Notion object from a high-level output title.

---

## 4. New `/end-day` Output Shape

### 4.1 End-day should score output, not just task completion

New retro order:

```markdown
# End of Day Output Scorecard — {TODAY}

## 1. Planned Outputs: Result
| Output | Morning done-state | Detected result | Aaron correction | Status |
|---|---|---|---|---|

## 2. Grove Leverage Review
| Category | Count | Notes |
|---|---:|---|
| Decisions made | N | ... |
| People unblocked | N | ... |
| Delegation asks sent | N | ... |
| Meetings converted to next actions | N | ... |
| Reusable systems created | N | ... |

## 3. Calendar Execution Reality
| Proposed block | Happened? | Evidence | Drift reason |
|---|---|---|---|

## 4. Real Movement Off-Plan
...

## 5. Carry Forward / Drop / Delegate Decisions
...

## 6. Tomorrow Setup
...
```

### 4.2 Preserve current `/end-day` sync loop

Do not remove:

- checkbox extraction
- Notion/gtask completion sync
- inline annotation detection
- dead-task resolution
- priority carry-forward writing
- telemetry

> [CODEX REVIEW] Also preserve the newer integrated preview contract in `scripts/end_day_orchestrator.py`: preview workers, de-duping by source line, staging under `.context/preview/`, and telemetry skill name `end-day-orchestrator`. Phase 5 should say whether output scorecard parsing lives in the orchestrator preview, the prose skill, or both. Right now it only lists generic parser helpers, which could bypass the actual run-plan flow.

### 4.3 New scorecard fields in telemetry

Add fields without breaking old consumers:

```json
{
  "outputs_planned": 5,
  "outputs_shipped": 2,
  "outputs_partial": 2,
  "people_unblocked": 3,
  "delegation_asks": 4,
  "meetings_captured": 1,
  "calendar_blocks_proposed": 8,
  "calendar_blocks_created": 6,
  "calendar_blocks_completed_estimate": 4,
  "real_vs_tracked_delta": 1
}
```

> [CODEX REVIEW] Specify these as extra JSON fields appended through `scripts/telemetry.sh`, not changes to the base telemetry row shape. Existing telemetry is append-only and consumers may assume `ts`, `skill`, `run_id`, `duration_ms`, `status`; the acceptance test should confirm old rows and new rows coexist.

### 4.4 End-day prompts should be fewer but more executive

Instead of asking for many task statuses, ask:

1. “Which planned outputs actually shipped?”
2. “Who got unblocked today?”
3. “Any major work that happened outside the plan?”
4. “Which carry-forwards should be dropped/delegated instead of carried again?”

---

## 5. Implementation Phases

## Phase 1 — Spec + Plan Review Only

**Objective:** Produce and review this plan before changing runtime behavior.

**Files:**
- Create: `.hermes/plans/2026-06-17_160051-high-output-start-day-overhaul.md`

**Steps:**
1. Write this plan.
2. Run `/codex` spec review against this plan.
3. Read review comments.
4. Revise plan if Codex flags blockers.
5. Ask Aaron for go/no-go before implementation.

**Validation:**
- Plan exists.
- Codex review summary appended.
- No runtime files changed.

---

## Phase 2 — Add Pure Planning Helpers

**Objective:** Create deterministic helper functions without altering existing skill output.

**Files:**
- Create: `scripts/output_planning.py`
- Create: `tests/test_output_planning.py`

**Core functions:**

```python
def classify_output_type(item: dict) -> str: ...
def score_daily_output(output: DailyOutput) -> tuple[int, list[str]]: ...
def group_items_into_outputs(items: list[dict], calendar_events: list[dict], streams: dict) -> list[DailyOutput]: ...
def apply_output_starvation_guard(outputs: list[DailyOutput], stream_order: list[str]) -> list[DailyOutput]: ...
def propose_calendar_blocks(outputs: list[DailyOutput], existing_events: list[dict], day_start: str, day_end: str) -> list[CalendarBlockProposal]: ...
def render_output_plan_markdown(outputs: list[DailyOutput], blocks: list[CalendarBlockProposal], delegations: list[DelegationAsk]) -> str: ...
```

> [CODEX REVIEW] Add explicit input adapters or fixtures. The hard part is not only scoring dataclasses; it is converting current Notion pages, Google Tasks JSON, calendar events, Provider CRM rows, suppressed IDs, and stream metadata into a normalized item list without losing source markers. A pure helper phase should include `normalize_*` functions or a fixture-driven contract for the shape expected from existing skill pulls.

**Tests:**

1. `test_classifies_delegation_unlock_when_owner_non_aaron`
2. `test_relationship_revenue_scores_above_admin_when_due_equal`
3. `test_admin_personal_score_is_capped`
4. `test_calendar_gap_adds_risk_and_score`
5. `test_starvation_guard_promotes_missing_stream_output`
6. `test_suppressed_items_never_become_outputs`
7. `test_calendar_blocks_do_not_overlap_existing_meetings`
8. `test_capture_block_follows_meeting`
9. `test_source_markers_preserved_in_rendered_markdown`

> [CODEX REVIEW] Add tests for: output IDs are stable across reruns, aggregate outputs retain all child source refs, suppressed items are excluded before grouping, stream fallback uses `is_default`, first-match-wins keyword order is honored, no output is selected without at least one source ref unless explicitly `[derived]`, and rendered Markdown avoids table-only mobile-critical information.

**Validation command:**

```bash
python3 -m unittest tests/test_output_planning.py
```

Expected: all tests pass.

---

## Phase 3 — Add Start-Day Additive Section

**Objective:** Add the new `Daily Output Plan` section while preserving existing sections and parsers.

**Files:**
- Modify: `.claude/skills/start-day/SKILL.md`
- Modify: `.agents/skills/start-day/SKILL.md` if it remains the vendored/active mirror
- Optional modify: `AGENTS.md` / `CLAUDE.md` if workflow contract changes are finalized

> [CODEX REVIEW] Do not modify `.agents/skills/start-day/SKILL.md` if it is still vendored from `skills-lock.json`; both AGENTS and CLAUDE describe `.agents/skills/` as external dependency skills that should not be edited. If there is an active mirror requirement, define the sync mechanism; otherwise keep implementation to `.claude/skills/start-day/SKILL.md` and local scripts.

**Steps:**
1. Add `Step 6c: Build Daily Outputs` after existing score and Notion audit.
2. Keep existing `Top 3 Outcomes` scoring in place for compatibility.
3. Add output model fields to skill docs.
4. Add new render section before `Top 3 Outcomes` or replace Top 3 with compatibility alias.
5. Add trust gate option for calendar block creation, gated and idempotent.
6. Add telemetry fields.

> [CODEX REVIEW] Add "write `logs/YYYY-MM-DD.md` and `vault/daily/YYYY-MM-DD.md` with compatible sections" explicitly. The current daily note and log are both used by downstream flows, but this phase only names the skill doc. If the output plan renders to one but not the other, `/end-day` may read stale or missing planned outputs.

**Important compatibility requirements:**

- `## Top 3 Outcomes` still appears.
- `## Actionable Items by Stream` still appears.
- Checkbox source markers still appear.
- Daily note still has `## End of Day Review`.
- Existing `/end-day` works if it ignores new sections.

**Validation:**

- Run skill lint:

```bash
scripts/skill_lint.sh
```

- Run existing tests:

```bash
python3 -m unittest tests/test_end_day_orchestrator.py
python3 -m unittest tests/test_output_planning.py
```

- Dry-run by manually applying helper functions to `vault/daily/2026-06-17.md` shape and verifying rendered markdown.

> [CODEX REVIEW] Make this an automated fixture test, not manual only. Copy the 2026-06-17 note shape into `tests/fixtures/` or embed a minimal representative fixture, render the additive section, and assert `end_day_orchestrator.extract_checked_source_actions` still returns the same source-sync actions.

---

## Phase 4 — Calendar Block Creation Adapter

**Objective:** Safely create Google Calendar execution blocks after approval.

**Files:**
- Modify: `scripts/google_api.py` only if existing `calendar insert/create` lacks needed description support.
- Create or modify: `scripts/output_calendar.py`
- Tests: `tests/test_output_calendar.py`

> [CODEX REVIEW] Good to isolate writes. Also add a no-network fake adapter interface so tests never call live Google APIs. The acceptance criteria should require a dry-run JSON plan that shows exactly which events would be created, their action_ids, source markers, and overlap decisions before any live test block.

**Rules:**

1. Read existing calendar before creating blocks.
2. Dedupe event if same summary and start ±15m.
3. Refuse overlapping fixed meetings unless explicitly marked approved.
4. Include source markers and output done-state in description.
5. Generate action ID before write, stamp after confirmed create response.
6. Calendar block writes must be individually visible at trust gate.

**Test cases:**

- `test_dedupes_existing_block_same_start`
- `test_refuses_overlap_with_fixed_meeting`
- `test_allows_buffer_overlap_only_when_flagged`
- `test_description_contains_source_markers`
- `test_action_id_stamped_only_after_success`

**Validation:**

Use a fake calendar JSON fixture first. Do not create live calendar events until Aaron approves a single test block.

---

## Phase 5 — End-Day Output Scorecard

**Objective:** Make `/end-day` evaluate planned outputs and actual leverage.

**Files:**
- Modify: `.claude/skills/end-day/SKILL.md`
- Modify: `scripts/end_day_orchestrator.py`
- Modify: `tests/test_end_day_orchestrator.py`

> [CODEX REVIEW] This phase needs to preserve current orchestrator behavior: `main --preview` should still stage `.context/preview/end-day-*.json`, `render_plan` should still show proposed writes/approvals, and `append_telemetry` should still emit `end-day-orchestrator`. Add tests around `build_preview`/`stage_plan` so output-scorecard parsing does not accidentally promote preview data to top-level pending writes.

**Add parser helpers:**

```python
def extract_daily_outputs(note_text: str) -> list[dict]: ...
def extract_calendar_execution_plan(note_text: str) -> list[dict]: ...
def build_output_scorecard(outputs: list[dict], checked_actions: list[dict], notion_changes: list[dict], gtask_changes: list[dict], user_corrections: dict) -> dict: ...
```

**Tests:**

1. Parses `## 1. Today's Outputs` table.
2. Falls back to `## Top 3 Outcomes` if new table missing.
3. Detects output completion from a checked source line.
4. Allows partial/real movement correction even if no source completion exists.
5. Produces telemetry-compatible scorecard fields.
6. Does not break existing checkbox sync tests.

> [CODEX REVIEW] Add tests for old-note fallback and mixed-note compatibility: a note with only `## Top 3 Outcomes`, a note with both `## 1. Today's Outputs` and `## Top 3 Outcomes`, and a note with no output section but valid checkboxes. `/end-day` must still run when `/start-day` was skipped or came from the old format.

**Validation command:**

```bash
python3 -m unittest tests/test_end_day_orchestrator.py
```

---

## Phase 6 — Rollout Plan

### 6.1 Shadow mode for 3 days

For 3 `/start-day` runs:

- Render both old Top 3 and new Daily Outputs.
- Do not auto-create calendar blocks.
- Compare `/end-day` results:
  - old Top 3 score
  - new output score
  - real movement delta
  - Aaron subjective usefulness

> [CODEX REVIEW] Add a hard rollback criterion for shadow mode: if output planning obscures a source marker, changes selected Top 3 in a way Aaron rejects, increases briefing length beyond an agreed threshold, or causes `/end-day` fallback parsing, keep it shadow-only. This makes the rollout testable instead of subjective.

### 6.2 Single calendar block test

After shadow mode, create exactly one approved calendar block:

- `EOD — Output Scorecard` or `CAPTURE — [meeting] next actions`
- Verify it appears once, no duplicate, correct description/source markers.

### 6.3 Gradual promotion

If shadow + test pass:

1. Daily Outputs becomes primary section.
2. Top 3 remains as compatibility alias for 2 weeks.
3. Calendar block creation offered daily but remains gated.
4. After 2 weeks, consider updating `/end-day` to treat outputs as primary.

---

## 7. Risks / Tradeoffs

| Risk | Impact | Mitigation |
|---|---|---|
| New structure too verbose | Aaron ignores briefing | Primary section must fit phone screen; detail stays lower |
| Calendar over-blocking | Field day becomes rigid | Blocks are proposals; include buffer; cap outputs to capacity |
| Existing parsers break | `/end-day` fails | Keep compatibility headings and tests |
| More scoring complexity | Harder to trust output | Show score breakdown plainly |
| Calendar writes duplicate | Annoying calendar clutter | Dedupe + action_id + single-test rollout |
| Delegation queue becomes unsent wish list | No leverage realized | End-day asks which delegation asks were sent |
| Personal/admin disappears | Life admin piles up | Keep late-day admin batch, cap priority not visibility |
| Stream starvation too aggressive | Wrong stream promoted | Promote only one slot and never suppressed items |

> [CODEX REVIEW] Add risks for "aggregated output hides individual syncable tasks", "tables render poorly on Telegram/mobile", "derived output cannot be proven at end-day", and "calendar proposals create planning debt if never approved." These are the most likely day-to-day workflow failures from the current spec.

---

## 8. Open Questions for Aaron

1. Should calendar execution blocks be created on your primary calendar only, or should we create a separate “COO Twin Execution” calendar?
2. What is your real default workday boundary after gym: 9:00–5:30, or do you want an evening block too?
3. Should personal/admin tasks be visible in the daily output plan, or only in the late-day batch?
4. Who are the canonical delegation people and channels?
   - Ilene
   - Jonathan
   - Kader
   - Ryan
   - Steven
   - Abid
   - others?
5. Should `/start-day` create tentative calendar holds for uncertain meetings like Starling/Luis, or only flag them?
6. Do you want 3 outputs/day or 5 outputs/day as the default target?

> [CODEX REVIEW] Add one owner question: "What counts as shipped for relationship/revenue outputs when the result is a conversation rather than a completed source task?" Without Aaron's answer, the scorecard may undercount field work, which is already a known Top 3 vs actual-output gap.

---

## 9. Implementation Acceptance Criteria

The overhaul is successful only if all are true:

- `/start-day` still runs with Calendar, Tasks, Notion, vault, and graceful degradation.
- `/end-day` still syncs checked boxes to Google Tasks/Notion after approval.
- Existing tests pass.
- New output planning tests pass.
- Daily note remains readable on Telegram/mobile.
- Every top output has a clear done-state.
- Every proposed calendar block cites the output it executes.
- Calendar writes are gated, deduped, and idempotent.
- Telemetry tracks output throughput without breaking existing rows.
- Aaron can look at the top of the daily note and know exactly what must ship today.

> [CODEX REVIEW] Add acceptance criteria that old daily notes remain parseable, `.context/preview/` remains ignored by `/start-day`, source-ID comments survive unchanged, and no new external write path exists without action_id check/stamp coverage. These are the integration invariants most likely to regress.

---

## 10. Recommended First Build Slice

Build only this first:

1. `scripts/output_planning.py` pure helpers.
2. `tests/test_output_planning.py`.
3. Render additive `## Daily Output Plan — Shadow Mode` in `/start-day` docs.
4. No calendar writes yet.
5. Run 3 days manually/shadow before any write adapters.

This follows Aaron's 90/10 rule: plan and validate first, single safe test, then expand.

> [CODEX REVIEW] This is the right first slice. I would narrow it further by excluding calendar writes entirely from Phase 3 and allowing only rendered proposals until after at least one successful `/end-day` parse of a shadow output plan.

## Codex Review — Summary

1. Overall flow verdict: concerns, but directionally strong. The plan is meaningfully Grove/HOM-aligned because it moves from raw task lists to outputs, done-states, leverage, delegation, calendar execution, and end-day throughput. The major concern is integration specificity: the plan describes the right operating model but does not yet fully pin it to the current parser/write contracts.

2. Critical gaps or blockers: reconcile the `google_api.py`/Python `urllib` plan with active skill docs that still instruct `gws` and curl; define concrete proof/evidence types for output completion; specify exact compatibility shape for `## Top 3 Outcomes`, `## Actionable Items by Stream`, source-ID comments, and `## End of Day Review`; account for current `end_day_orchestrator.py` preview staging under `.context/preview/`.

3. Integration risks with existing components: output aggregation can hide individual Notion/Google Task sync anchors; Markdown tables can degrade the phone briefing; top-level `.context/` misuse can trigger false pending-write flags; modifying vendored `.agents/skills/` would violate repo conventions; Option C can mutate the wrong Notion page if an output is not one-to-one with a Master Tasks item.

4. Recommendations before implementation: add fixture tests based on the 2026-06-17 daily-note shape; add normalization/helper contracts for current source JSON, suppression, and streams; keep Daily Outputs shadow-only and preserve the old Top 3 list verbatim for the first release; add no-network calendar adapter tests; make telemetry additions extra fields only; add rollback criteria after the 3-day shadow.

5. Questions for Aaron / owner: What counts as "shipped" for relationship-heavy work? Should the phone view optimize for 3 primary outputs with optional flex hidden lower down? Which calendar should receive execution blocks? Which delegation people/channels are canonical? Should "delegated" and "dropped deliberately" count as successful management outcomes in the end-day scorecard?

---

## Post-Codex Revision Lock — Required Before Implementation

Codex review found the plan directionally strong but not yet implementation-safe. These revisions are now part of the plan and must be completed before any runtime behavior changes.

### A. Active skill-doc consistency is a blocking task

Before implementing helper logic, update the implementation plan/task list to reconcile active skill instructions:

- `.claude/skills/start-day/SKILL.md` still contains old `gws` and shell `curl` instructions in multiple sections.
- `.claude/skills/end-day/SKILL.md` still contains old `gws` and shell `curl` instructions in multiple sections.
- The implementation must either:
  1. replace touched instructions with `python3 scripts/google_api.py` and Python `urllib.request`, or
  2. encapsulate all source pulls/writes behind helper scripts and make skills call only those helpers.

**Acceptance criterion:** no newly touched path tells an implementer to use unavailable `gws` or masked shell `curl` for Calendar/Tasks/Notion.

### B. Exact backward-compatibility shapes are mandatory

Shadow-mode output must preserve these exact parseable anchors:

```markdown
## Top 3 Outcomes
1. **Title** — score: N (...) **[stream]** `[source:abcd]` <!-- optional full source comment -->

## Actionable Items by Stream
### Lincoln Lab
- [ ] **[lab]** Task text <!-- gtask:ID -->
- [ ] **[lab]** Task text <!-- notion:ID -->

## End of Day Review
```

**Acceptance criterion:** fixtures prove old-format notes, mixed old/new notes, and no-output-section notes still parse in `/end-day`.

### C. Output proof/evidence types are required

Every `DailyOutput` must include machine-readable completion evidence, not just prose.

Allowed proof types:

- `daily_checkbox_checked` — line with source comment checked in Obsidian.
- `gtask_completed` — Google Task status completed.
- `notion_done` — Notion Master Task Status=Done.
- `calendar_capture_done` — capture/follow-up block created or checked.
- `artifact_created` — file/path/URL exists.
- `aaron_confirmed` — explicit end-day correction.
- `delegated` — owner assigned with clear ask and follow-up date.
- `dropped_deliberately` — explicit management decision, not failure.
- `blocked_waiting` — moved to awaiting with owner/date.

`DailyOutput` must gain:

```python
completion_refs: list[CompletionRef]
completion_policy: Literal["any", "all", "manual"]
owner_type: Literal["aaron", "teammate", "external", "system"]
owner_name: str | None
```

### D. `.context/` lifecycle must not regress

- Rendered shadow previews should not write top-level `.context/*.json` unless truly awaiting approval.
- Use `.context/preview/` for preview artifacts.
- `/start-day` must continue ignoring `.context/preview/`.

**Acceptance criterion:** test or manual validation confirms no new false pending-write flags appear from output-plan previews.

### E. Phone-first rendering requirement

The first mobile viewport should avoid wide tables. Use compact bullets above detailed tables:

```markdown
## Today — Ship These 3
1. **Output** — done when: ... — next block: 9:20
2. **Output** — done when: ... — next block: 10:30
3. **Output** — done when: ... — next block: 12:00/capture

**Next action:** 9:20–10:00 FOCUS — Starling IPA loop closed
```

Detailed tables can remain below for desktop/log review.

### F. Calendar writes deferred beyond first implementation slice

The first build slice is narrowed:

1. Pure helper module.
2. Tests.
3. Shadow-mode rendered output plan.
4. Existing Top 3 preserved verbatim.
5. `/end-day` parser compatibility verified.
6. No calendar writes.

Only after at least one successful `/end-day` parse of a shadow output plan may calendar write adapters be implemented.

### G. Deterministic capacity and starvation rules

Before building calendar proposals:

- Define working-day bounds from config/profile or default `09:00–17:30 America/New_York`.
- Proposed blocks must not exceed open working minutes.
- Overloaded days reduce output count.
- Starvation replacement must define “non-critical” mechanically, e.g. lowest score among non-due-today, non-calendar-event outputs.

### H. Rollback criteria for 3-day shadow

Keep Daily Outputs shadow-only if any of these happen:

- Source markers are hidden or lost.
- `/end-day` fails to parse checkboxes or Top 3.
- Aaron rejects the selected outputs as worse than old Top 3 on any 2 of 3 days.
- Top mobile section becomes too long to scan quickly.
- New preview artifacts trigger pending-write warnings.
- Output grouping hides individual Google Task / Notion anchors needed for sync.

### I. Extra regression surfaces to classify as no-change or tested

Before implementation starts, explicitly mark these as no-change or add regression checks:

- `/meeting-prep`
- `/automation`
- `/vault-health`
- `/note-harvest`
- `/sync-sweep`
- `scripts/vault_search.py`
- `scripts/automation_due.py`
- `scripts/end_day_orchestrator.py` preview merge behavior

### J. Owner answers from Telegram context — locked 2026-06-17

Retrieved from Telegram session `20260617_164714_ef45c8`, messages 7278–7282.

1. **Relationship/revenue shipped definition:** shipped means a successful meaningful interaction between the two parties where an agreement is made to start using us, proceed, or operate under terms both sides accept. For field/relationship work, the proof may be a conversation outcome rather than a completed task row.
2. **Successful delegated management outcome:** delegated and runner-driven outcomes count as successful management when they move the client timeline. Example: if Ilene/Eileen or another runner/associate visits an office directly and gets an outcome from the meeting, that is a valid delegated success.
3. **Calendar target:** execution blocks should go only on Aaron's established primary Google Calendar, `aaronfainshtein1@gmail.com`. Do not create a separate COO Twin Execution calendar unless Aaron explicitly changes this later.
4. **Phone view:** optimize for exactly **3 primary outputs** in the first mobile viewport. Flex/secondary outputs may live below the fold.
5. **Delegation channel model:** the default write channel is task creation for Aaron and/or the delegated runner/associate. Outbound communication still follows the existing approval gate.

### K. Remaining owner questions before calendar-write phase

1. What are the canonical runner/associate names and preferred task destinations beyond Ilene/Eileen?
2. Should `dropped_deliberately` count as a successful management outcome only when it frees capacity, or always when explicitly decided?
3. What default workday bounds should the block proposer use after gym: `09:00–17:30 America/New_York`, or include an evening block?
