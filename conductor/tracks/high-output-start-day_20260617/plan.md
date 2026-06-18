# Plan: High-Output Start-Day / End-Day Restructure

Execution plan for track `high-output-start-day_20260617`. TDD throughout
(red → green → refactor). Every phase lists its unit tests and e2e tests; a phase
is not "done" until both pass plus the repo validation gate.

> Worktree discipline: all implementation happens in `.worktrees/high-output-start-day`
> on branch `feat/high-output-start-day`. Never on master. Squash-merge via PR.

## Testing model for this track

- **Unit tests** — pure functions in `scripts/output_planning.py`, no I/O, no
  network. Scoring, classification, suppression, stable IDs, marker preservation,
  delegation schema, completion-policy resolution.
- **E2E tests** — exercise the *full render → file → parse loop* with NO mocks of
  the parser and NO live APIs. The golden render-pair fixture (change #2) is the
  backbone: render real `DailyOutput`s to a real log + daily-note pair on a temp
  dir, then run the **actual** `end_day_orchestrator` functions against them and
  assert the sync actions + scorecard are correct. Subprocess-invoke
  `scripts/start_day.py` so the wrapper itself is covered.
- **Live-API e2e** is explicitly deferred to Phase E (one human-approved calendar
  block), never run in CI.

CI wiring (Phase A task A6): add `python -m unittest discover -s tests` and
`bash scripts/skill_drift_check.sh` as steps in `.github/workflows/validate.yml`
and the local pre-push hook, alongside the existing 3 self-checks.

## Execution & review loop (MANDATORY every phase) — see `review-gates.md`

Each phase runs the same loop: **execute** (`/dispatch` for single-domain phases B/C;
`subagent-driven-development` for multi-task phases A/D) → **self-verify** (unit + e2e
+ regression guards) → **`/codex review`** iterated to 0×[P1] → **quality agent**
(`code-reviewer` for A/B; `quality-reviewer` for the load-bearing C/D/E, read-only) →
**gate**. A phase does not advance until codex and the quality agent are clean. Each
phase below ends with a `Stage gate:` line; the full per-phase agent/codex matrix is
in `review-gates.md`.

---

## Phase A — Planning module, render contract, golden fixtures, delegation schema

**Objective:** deterministic planner + the exact markdown render contract + the
render-pair fixtures. No skill edits, no external writes.

### Tasks
- **A1** `scripts/output_planning.py` dataclasses: `SourceRef`, `CompletionRef`,
  `DailyOutput`, `OutputScorecard`, and **`DelegationAsk`** (change #3:
  `delegatee`, `ask`, `date`, `source_ref`, `confirmation_state`). Skip
  `PortfolioPulse`. `DailyOutput` carries `completion_refs`, `completion_policy ∈
  {any,all,manual}`, `owner_type ∈ {aaron,teammate,external,system}`,
  `next_block_label` (display-only stable string — change #4).
- **A2** Pure functions: `normalize_gtask/notion/calendar/vault_line`,
  `classify_output_type`, `score_daily_output`, `stable_output_id` (hash of
  date+sorted source_ids), conservative **1:1** `group_items_into_outputs`,
  `apply_output_starvation_guard`, `resolve_completion(output, checked_actions)`
  implementing the any/all/manual → child-marker-state mapping.
- **A3** `render_output_plan_markdown(...)` — emits, in one daily-note body:
  phone-first `## Today — Ship These 3` bullets, a real `## Top 3 Outcomes`
  compat list, `## Actionable Items by Department` with child `- [x]/[ ] … <!--
  gtask|notion|derived:ID -->` lines (non-indented), and a `## End of Day Review`
  placeholder. Plus `render_log_top3(...)` for the LOG file (split-file fact).
- **A4** Golden render-pair fixtures (change #2) under `tests/fixtures/`:
  `daily_old_format.md`, `daily_mixed_output_plan.md`, and paired
  `logs_old_format.md`, `logs_mixed_output_plan.md`.
- **A5** Module docstring carries the implementation contract (replaces the
  separate `06-implementation-contract.md`).
- **A6** Wire `unittest discover` + `skill_drift_check.sh` into `validate.yml`
  and the pre-push hook.

### Unit tests — `tests/test_output_planning.py`
1. relationship/revenue scores above admin when due is equal; admin capped.
2. suppressed items never become outputs.
3. stable output IDs across reruns for same source refs.
4. aggregated output retains ALL child source refs.
5. no output selected without a source ref unless `derived`/`manual`.
6. starvation guard promotes one stream only, never suppressed.
7. `next_block_label` renders as stable display text (no calendar write).
8. `DelegationAsk` round-trips delegatee/ask/date/source_ref/confirmation_state.
9. `resolve_completion`: policy `any` ships on 1 child marker; `all` needs every
   child; `manual` requires `aaron_confirmed`.
10. rendered markdown keeps markers on non-indented `- [ ]` lines.

### E2E test — `tests/test_render_parse_roundtrip.py` (the alignment backbone)
- Render a known `DailyOutput` set to a temp `vault/daily/{D}.md` + `logs/{D}.md`.
- Run the **real** `end_day_orchestrator.extract_checked_source_actions` on the
  daily note → assert exact `gtask_complete` / `notion_done` / `manual_completion`
  set matches the children's markers.
- Assert the log exposes `## Top 3 Outcomes` and the daily note has `## End of
  Day Review`.
- Parametrize over both fixtures (old + mixed) and assert the action set is
  IDENTICAL across formats (this is change #1's gate, authored here).

### Validation
```bash
python -m unittest tests.test_output_planning tests.test_render_parse_roundtrip
python -m unittest tests.test_end_day_orchestrator     # unchanged, still green
```

**Stage gate:** execute via `subagent-driven-development` (multi-task: dataclasses +
render contract + fixtures + suites). Then `/codex review` (iterate to 0×[P1]) +
`code-reviewer` agent on the module. Advance only when both clean.

---

## Phase B — Wrapper script

**Objective:** one entry point so both skill copies become identical one-liners.

### Tasks
- **B1** `scripts/start_day.py` with `render --shadow [--fixture PATH] [--date D]`,
  calling Phase A functions. Reads Calendar/Tasks via `python3
  scripts/google_api.py` and Notion via Python `urllib` + `.secrets/notion.env`
  (NO gws, NO shell curl). Degrades gracefully + emits `warnings[]`.
- **B2** JSON output shape: `{date, mode, daily_outputs[], delegation_asks[],
  warnings[], source_counts{}}`.

### Unit tests — extend `tests/test_output_planning.py`
- arg parsing; `--fixture` path bypasses live pulls; missing source → warning not crash.

### E2E test — `tests/test_start_day_wrapper_e2e.py`
- `subprocess` invoke `python3 scripts/start_day.py render --shadow --fixture
  tests/fixtures/daily_mixed_output_plan.md`; assert stdout contains the four
  anchors + markers; pipe the rendered daily note into the real orchestrator and
  assert the same action set as Phase A.

### Validation
```bash
python3 scripts/start_day.py render --shadow --fixture tests/fixtures/daily_mixed_output_plan.md
python -m unittest discover -s tests
```

**Stage gate:** execute via `/dispatch` (single-domain wrapper). Then `/codex review`
(iterate to 0×[P1]) + `code-reviewer` agent on arg parsing / graceful degradation /
no gws-curl leak. Advance only when both clean.

---

## Phase C — Runtime shadow integration (GATED)

**Objective:** `/start-day` shows the shadow section in the live Hermes runtime.
First user-visible value.

> **GATE (change #1):** do NOT start Phase C until the Phase A/B e2e roundtrip is
> green AND `skill_drift_check.sh` passes. The minimum gating test:
> `test_render_parse_roundtrip` proves identical sync actions on old vs mixed
> notes, the log keeps `## Top 3 Outcomes`, and the daily note keeps `## End of
> Day Review`.

### Tasks
- **C1** Edit `~/.hermes/skills/coo-twin/start-day/SKILL.md`: call
  `python3 scripts/start_day.py render --shadow`; insert the section below system
  flags, above old `## Top 3 Outcomes`; preserve all anchors.
- **C2** Mirror the identical change to `.claude/skills/start-day/SKILL.md`
  (diff between the two should be ~frontmatter only).
- **C3** Change #4: delete `gws` + raw Notion `curl` recipes from **both**
  `start-day` copies entirely (not just touched steps); same for the two
  `end-day` copies in Phase D.
- **C4** Add `scripts/skill_drift_check.sh`: grep-fail if `\bgws\b` or
  `curl .*api\.notion\.com` appears in any active skill body; assert both copies
  call the wrapper.
- **C5** Add a deploy helper `scripts/deploy_hermes_skills.sh` (repo → `~/.hermes`
  copy) since `~/.hermes/` is not under git — makes Phase C reproducible/rollback-able.

### E2E / validation
```bash
bash scripts/skill_drift_check.sh
bash scripts/skill_lint.sh
python -m unittest discover -s tests
```
Manual: run `/start-day` in the runtime, eyeball mobile viewport, confirm no
top-level `.context/*.json` was created.

**Stage gate (load-bearing):** execute via `/dispatch`. Then `/codex review`
iterated to convergence (required — touches the Hermes runtime + sync path) +
`quality-reviewer` agent confirming the parser contract is intact and gws/curl are
purged from BOTH copies. Advance only when codex 0×[P1] and quality findings resolved.

---

## Phase D — End-day output scorecard (preview-only)

**Objective:** `/end-day` scores planned outputs; additive, no new external writes.

### Tasks
- **D1** Add to `scripts/end_day_orchestrator.py`: `extract_daily_outputs(note)`,
  `build_output_scorecard(outputs, checked_actions, user_corrections)`.
- **D2** Scorecard status is one enum `{shipped,partial,delegated,dropped,blocked}`;
  `aaron_confirmed` overrides status (not additive); dedupe evidence by
  `output_id+proof_type+source_id` (adopted Codex Q4).
- **D3** Stage scorecard under `.context/preview/` only; telemetry fields additive.
- **D4** Edit both `end-day` skill copies: summarize outputs, keep
  `end_day_orchestrator --preview` as the sync path; purge gws/curl (change #4).

### Unit tests — extend `tests/test_end_day_orchestrator.py`
1. old note (Top 3 only) → scorecard builds, checkbox sync unchanged.
2. mixed note → outputs extracted AND checkboxes still sync.
3. no-output-section note with valid checkboxes → still syncs.
4. `completion_policy=any/all` resolution.
5. `aaron_confirmed` overrides, no double-count (dedup key).
6. `delegated`/`blocked`/`dropped` are not scored as failures.

### E2E test — extend `tests/test_render_parse_roundtrip.py`
- Full loop: render (Phase A) → write pair → `build_output_scorecard` → assert
  per-output status matches the children's marker states end to end.

### Validation
```bash
python -m unittest discover -s tests
ls .context/*.json 2>/dev/null && echo "FAIL: top-level pending write" || echo "ok: previews isolated"
```

**Stage gate (load-bearing):** execute via `subagent-driven-development` (parser +
scorecard + dual skill edits). Then `/codex review` iterated to convergence (required
— function signatures + telemetry plumbing on `end_day_orchestrator.py`) +
`quality-reviewer` AND `code-reviewer` agents (sync contract, additive-telemetry-only,
dedup/override correctness). Advance only when codex 0×[P1] and both agents clean.

---

## Phase E — Calendar adapter + promotion (after 3-day shadow)

Deferred. Only after shadow passes: `scripts/output_calendar.py` with fake-adapter
unit tests (dedupe, overlap refusal, TZ/DST, action_id stamp-after-success), then
ONE human-approved live block on `aaronfainshtein1@gmail.com` as the only live-API
e2e. Promote shadow → primary with `## Top 3 Outcomes` as a 2-week compat alias.

---

## Lifecycle checklist

Each phase gate = tests green + `/codex review` 0×[P1] + quality agent clean
(see `review-gates.md`).

- [ ] `EnterWorktree(high-output-start-day)`
- [ ] Phase A (unit + e2e green · codex · code-reviewer)
- [ ] Phase B (wrapper e2e green · codex · code-reviewer)
- [ ] **Phase C gate check** → Phase C (drift + lint green · codex iterated · quality-reviewer)
- [ ] Phase D (orchestrator tests green, previews isolated · codex iterated · quality-reviewer + code-reviewer)
- [ ] 3-day shadow observation (rollback criteria active)
- [ ] Phase E (separate follow-up track · codex · quality-reviewer)
- [ ] `/verification-before-completion` → `ExitWorktree` → PR → squash-merge
