# Hermes Compatibility Review — Start Day Revamp

Review date: 2026-06-18
Reviewed folder: `/Users/afain/daily-automation/start day revamp`

## Files reviewed

- `README.md`
- `00-retrieved-telegram-context.md`
- `01-high-output-start-day-overhaul-plan.md`
- `02-10x-management-audit.md`
- `03-gary-tan-level-owner-review.md`

## Verification performed

Commands run from `/Users/afain/daily-automation`:

```bash
bash scripts/preflight.sh
scripts/skill_lint.sh
python3 -m unittest tests/test_end_day_orchestrator.py
```

Observed results:

```text
preflight: MODE=draft, NOTION_OK=1, GWS_OK=1, VAULT_OK=1, PREFLIGHT_OK=1
preflight warning: gws_cli_missing_using_google_api_py
skill_lint: 34 total, 15 COO Twin, 0 failures
end_day_orchestrator tests: Ran 4 tests — OK
```

## Executive verdict

The restructuring is directionally strong, but it is not implementation-safe yet.

The biggest Hermes risk is not the management theory. The biggest risk is that the plan currently spans multiple agent surfaces with different sources of truth:

- Hermes active skills under `~/.hermes/skills/coo-twin/`
- Claude Code project skills under `.claude/skills/`
- vendored external skills under `.agents/skills/`
- Codex project context under `AGENTS.md`
- Claude project context under `CLAUDE.md`

If only one layer is updated, Hermes may keep operating with the old `/start-day` and `/end-day` instructions.

## Critical compatibility issues

### 1. Active Hermes skills are not the same as `.claude/skills`

The plan mostly discusses modifying:

- `.claude/skills/start-day/SKILL.md`
- `.claude/skills/end-day/SKILL.md`

But this Hermes session loads skills from:

- `/Users/afain/.hermes/skills/coo-twin/start-day/SKILL.md`
- `/Users/afain/.hermes/skills/coo-twin/end-day/SKILL.md`

Observed command-reference counts:

```text
/Users/afain/.hermes/skills/coo-twin/start-day/SKILL.md: gws=23, curl=21, DailyOutput=0
/Users/afain/.hermes/skills/coo-twin/end-day/SKILL.md:   gws=18, curl=9,  DailyOutput=0
.claude/skills/start-day/SKILL.md:                     gws=17, curl=11, DailyOutput=0
.claude/skills/end-day/SKILL.md:                       gws=19, curl=7,  DailyOutput=0
```

Risk:

Hermes may continue following old instructions even if `.claude/skills` is updated.

Required fix:

Before implementation, define the actual deployment target:

1. Hermes runtime skills: `~/.hermes/skills/coo-twin/start-day` and `~/.hermes/skills/coo-twin/end-day`
2. Claude Code project skills: `.claude/skills/start-day` and `.claude/skills/end-day`
3. Project docs: `AGENTS.md` and `CLAUDE.md`

Do not modify only `.claude/skills` and assume Telegram/Hermes will change.

### 2. Existing active skill docs still contain old `gws` and shell `curl` paths

The plan correctly says:

- `gws` is not installed
- use `python3 scripts/google_api.py`
- do not use shell curl with Notion token because Hermes redaction breaks it

But active skill files still contain many old `gws` / `curl` references.

Risk:

Hermes may select an old instruction from the same skill body and call the wrong command.

Required fix:

Do not rely on prose warnings alone. Add wrapper scripts and make the skill call those scripts only.

Recommended pattern:

```text
scripts/start_day_collect.py --date YYYY-MM-DD --json
scripts/start_day_output_plan.py --date YYYY-MM-DD --shadow --json
scripts/start_day_render.py --date YYYY-MM-DD --shadow
```

Then skill docs should call scripts, not repeat raw Calendar/Notion API recipes.

### 3. `.agents/skills` is vendored and should not be edited directly

The plan mentions modifying `.agents/skills/start-day/SKILL.md` if it remains active.

Risk:

`.agents/skills/` is described in project context as external dependency / fetched skills. Editing it can be overwritten or violate repo conventions.

Required fix:

Treat `.agents/skills` as read-only unless there is an explicit sync/update mechanism. Update local active skills and project-owned `.claude/skills`; do not patch vendored files as the primary implementation target.

### 4. Output aggregation can break source-marker sync

Current `/end-day` sync depends on exact checkbox markers:

```markdown
<!-- gtask:ID -->
<!-- notion:ID -->
```

Current orchestrator test verifies checked lines become `gtask_complete`, `notion_done`, or manual completions.

Risk:

If `DailyOutput` aggregates several child tasks into one pretty output, Hermes may lose the individual source IDs needed to sync back to Google Tasks / Notion.

Required fix:

Every output needs machine-readable completion refs:

```python
completion_refs: list[CompletionRef]
completion_policy: "any" | "all" | "manual"
```

Rendered markdown must preserve child checkboxes with original markers below the output.

### 5. Tables in the first viewport are a Telegram/mobile problem

The plan's `## 1. Today's Outputs` table is too wide for phone use.

Risk:

Aaron reads this on Telegram; wide Markdown tables degrade scanability and may wrap badly.

Required fix:

Use bullet-first phone view above tables:

```markdown
## Today — Ship These 3
1. Output — done when: ... — proof: ... — next block: ...
2. Output — done when: ... — proof: ... — next block: ...
3. Output — done when: ... — proof: ... — next block: ...
```

Put detailed tables below the fold only.

### 6. `.context/preview/` must remain separate from pending writes

The plan mentions preview artifacts and `.context/preview/`, which is correct.

Risk:

If output-plan previews are written to top-level `.context/*.json`, `/start-day` will flag them as pending writes every morning.

Required fix:

All shadow-mode artifacts go under:

```text
.context/preview/
```

Only true approval-pending write payloads go top-level `.context/*.json`.

### 7. Calendar write phase is still underspecified for `google_api.py`

The docs defer calendar writes, which is correct. But when that phase starts, `google_api.py` command shape must be respected.

Known constraint from current COO Twin skills:

- Calendar insert uses naive local datetimes, not timezone-offset strings.
- Example working shape:

```bash
python3 scripts/google_api.py calendar insert --summary "Title" --start 2026-06-10T15:30:00 --end 2026-06-10T16:00:00
```

Risk:

If `CalendarBlockProposal` stores timezone-aware RFC3339 and passes it directly to `google_api.py`, calendar insert can fail or drift depending on script behavior.

Required fix:

Keep internal datetimes timezone-aware for planning tests, but create a dedicated adapter that converts to the exact `google_api.py` insert format. Test DST and local date behavior before any live event.

### 8. End-day orchestrator integration is the real contract

The current `/end-day` skill now routes through `scripts/end_day_orchestrator.py --preview`.

Risk:

If output-scorecard parsing is added only to prose skill docs and not to `end_day_orchestrator.py`, the actual EOD run may ignore the new output plan.

Required fix:

Implement output parsing in `end_day_orchestrator.py` or explicitly stage it through the orchestrator preview payload.

Add tests for:

- old notes only,
- mixed old/new notes,
- no output section but valid checkboxes,
- `.context/preview/` staging remains ignored by `/start-day` pending-write scan.

### 9. `PortfolioPulse` needs deterministic data, not model vibes

The Gary Tan owner review adds `Portfolio Pulse`, which is good. But if implemented as pure LLM judgment, it will be unstable.

Risk:

Daily business allocation may become inconsistent or overly persuasive without evidence.

Required fix:

Make `PortfolioPulse` deterministic from source signals first:

- today's calendar density per stream,
- overdue/stale task counts per stream,
- recent meeting extraction gaps,
- carry-forward age,
- explicit high-priority / current focus state,
- Aaron override.

Then allow LLM prose only to explain the deterministic result.

### 10. README is stale

`README.md` lists only files 00–02. It does not list:

- `03-gary-tan-level-owner-review.md`
- this compatibility review

Risk:

Human review misses the newest docs.

Required fix:

Update README whenever new review artifacts are added.

## Recommended safe implementation contract

Before any behavior change, write a small implementation contract file:

`start day revamp/05-implementation-contract.md`

It should specify:

1. Which skill surfaces are updated:
   - Hermes runtime skill path
   - `.claude/skills` path
   - AGENTS/CLAUDE docs if needed
2. Which paths are read-only:
   - `.agents/skills`
3. Which scripts are source of truth:
   - `scripts/output_planning.py`
   - `scripts/start_day_*` wrappers if created
4. Which section headings are compatibility anchors:
   - `## Top 3 Outcomes`
   - `## Actionable Items by Stream`
   - `## End of Day Review`
5. Which write paths are banned in Phase 1:
   - Calendar event creation
   - Notion status mutation from aggregate output
   - top-level `.context/*.json` preview writes
6. Which tests must pass before rollout.

## Recommended first build slice — revised

Do this first:

1. Create `scripts/output_planning.py` with pure deterministic objects:
   - `PortfolioPulse`
   - `SourceRef`
   - `CompletionRef`
   - `DailyOutput`
2. Create `tests/test_output_planning.py`.
3. Add fixture-driven normalization tests for:
   - Google Tasks JSON
   - Notion Master Tasks rows
   - Calendar events
   - stream config
   - suppressed IDs
4. Render shadow-only markdown.
5. Preserve old `## Top 3 Outcomes` exactly.
6. Add no calendar writes.
7. Run:

```bash
python3 -m unittest tests/test_output_planning.py
python3 -m unittest tests/test_end_day_orchestrator.py
scripts/skill_lint.sh
bash scripts/preflight.sh
```

## Go / no-go guidance

Current state: **GO for Phase 1 helper/test design. NO-GO for modifying live `/start-day` behavior yet.**

Reasons:

- Active Hermes skill docs still contain old command paths.
- Multiple skill surfaces are not reconciled.
- Output aggregation could break completion sync.
- Calendar writes are correctly deferred but not adapter-safe yet.
- README/archive docs need small cleanup.

Once the implementation contract exists and tests cover compatibility anchors, this can move safely into shadow-mode implementation.
