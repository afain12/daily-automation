# TASKS — dispatch execution list (fixed after 4-lens review, 2026-06-17)

Execute with `/dispatch` → `/subagent-driven-development`: one fresh implementer subagent
per task, then spec-review then code-review gate (see `review-gates.md`). **Every implementer
reads `CONTRACTS.md` first.** Tasks run in order; do not parallelize within a phase (each phase
touches one file).

## Review verdict (why this list differs from plan.md)
- Plan soundness: **GO-WITH-FIXES** — split read path (contract #2) under-documented in plan.
- Executability: **YES-WITH-FIXES** — task ordering + granularity fixes applied below.
- Compat: **GO for Phase 1 shadow; NO-GO for live engine edits until E2E roundtrip green.**
- 10x management: **MIXED** — value is the instruction, not the engine. Hence lean-first.

---

## PHASE 1 — Lean shadow ship (DEFAULT — start here)
Goal: get the better *briefing* in front of Aaron and validate the judgment before building any engine.
Ships as a doc change only. Preserves all contracts by appending below untouched sections.

- **T1 — Author the selection algorithm (one page).** The highest-leverage artifact and it does
  not exist yet: given Calendar+Notion+Tasks+vault, how to pick exactly 3 outputs. Order:
  Portfolio Pulse (which business has the best leverage constraint today) → score by leverage
  type (constraint-removal > revenue/relationship > delegation-counts-as-shipped > meeting-conversion
  > admin) → day-type filter (field day = no deep-work blocks) → starvation guard → output 3.
  Deliverable: `conductor/tracks/.../context/selection-algorithm.md`.
- **T2 — Edit `~/.hermes/.../start-day/SKILL.md` to APPEND a shadow section** below the existing
  (untouched) Top 3 / Actionable Items: `## Today — Ship These 3` (phone-first compact bullets,
  NO wide tables), a 1-line Portfolio Pulse, a `Day type:` line, and a `## Meetings That Must
  Convert` lane (decision / owner / next action). Existing sections and all headings unchanged.
- **T3 — Mirror T2 into `.claude/skills/start-day/SKILL.md`** (contract #8). Keep the two runtimes'
  existing deltas intact; only add the same appended section.
- **T4 — Run 3 mornings in shadow, eyeball on phone.** Human checkpoint. Keep or kill based on
  whether the briefing is actually sharper. If kill → revert two files, done, no engine built.

**Phase 1 exit:** Aaron confirms the briefing is better. Only then consider Phase 2.

---

## PHASE 2 — Engine (DEFERRED — build only if Phase 1 judgment proves out)
The original Conductor track, with executability fixes applied. Do NOT start until T4 says "keep"
AND a deterministic scorer is actually needed (e.g. for end-day scorecard sync).

- **E1 — Build `scripts/output_planning.py` whole** (merges old A1+A2+A3+A5): dataclasses
  (`SourceRef, CompletionRef, DailyOutput, DelegationAsk, OutputScorecard`), pure scoring/grouping
  functions, and BOTH renderers `render_output_plan_markdown()` + `render_log_top3()`. Module
  docstring = the contract. **Grouping defaults to 1:1 (one source → one output); `max_children=1`
  guard in shadow mode** so markers never aggregate (contract #1).
- **E2 — Golden render-pair fixtures** under `tests/fixtures/` (old-format note + mixed-format
  note). Author AFTER E1's render signatures are locked.
- **E3 — `tests/test_render_parse_roundtrip.py`** — THE gate (contract proof): asserts
  `extract_checked_source_actions` returns identical actions on both fixtures.
- **E4 — `scripts/skill_drift_check.sh`** (grep-fail on `\bgws\b` / `curl.*api\.notion\.com`).
  **Built BEFORE any purge** so the purge has an automated check (review fixed the C4-after-C3 order).
- **E5 — `scripts/start_day.py render --shadow [--fixture] [--date]`** (merges old B1+B2): Python
  urllib only, no gws/curl. Defines + tests the JSON output shape `{date, mode, daily_outputs[],
  delegation_asks[], warnings[], source_counts{}}`. **PRECONDITION: confirm `scripts/google_api.py`
  exists; if absent it is an E5 sub-deliverable, not an ad-hoc invention.**
- **E6 — GATE: E3 must be green.** No live skill edit before this passes.
- **E7 — Purge `gws` + raw Notion `curl` from all 4 skill copies**, wire the new wrapper in.
  Edit `~/.hermes/...` first, mirror to `.claude/...` (contract #8). One atomic commit per skill pair.
- **E8 — `scripts/deploy_hermes_skills.sh`** (because `~/.hermes/` is outside git — rollback safety).
- **E9 — end-day scorecard:** add `extract_daily_outputs()` + `build_output_scorecard()` to
  `scripts/end_day_orchestrator.py`; stage under `.context/preview/` ONLY (contract #7); additive
  telemetry only (contract #5); edit both end-day skill copies. Read the existing orchestrator
  before editing — extend, never overwrite.

---

## Phase-2 carry-forward (Codex review 2026-06-17, pre-existing in end_day_orchestrator.py)
These were flagged reviewing the vendored orchestrator; NOT exercised by the Phase-1
gate (which only imports `extract_checked_source_actions`). Address in E9.
- **[P1] FIXED in this branch** — `REPO_DIR` hard-coded to `/Users/afain/daily-automation`;
  now derived from `__file__` (+ `COO_REPO_DIR` override). Propagate to main + ~/.hermes copies.
- **[P1] note_harvest worker** — `preview_note_harvest` shells out to `scripts/note_harvest.py`,
  untracked here, so a worktree `main()` run degrades that worker to "failed" and the unified
  gate silently omits note-harvest actions. Vendor the note_harvest chain or make the omission loud. (E9)
- **[P2] sync-sweep line numbers** — `idx` is Braindump-relative while the gate uses daily-note
  `source_line`; `merge_previews` line-ownership check can miss conflicts. (E9)
- **[P2] dedupe key** — collapse external completions by `(type, source_id)` before the
  line-sensitive key, so the same marker checked in both Today and Actionable sections doesn't double-stage. (E9)

## Guardrails for the dispatch loop
- `~/.hermes/` may be absent on a given machine. If so, the Hermes-copy edits (T2, E7) **skip with a
  logged WARNING and a staged patch under `.context/preview/`**, they do not fail the task. The
  Claude Code copy edit still runs.
- Custom review agents `quality-reviewer` / `code-reviewer` must exist in `.claude/agents/` for
  Phase 2 gates. Phase C/D-equivalent tasks (E7, E9) use `quality-reviewer`, not just code review.
- Cut from scope (over-engineering, per soundness review): `real_vs_tracked_delta`,
  `day_mode` capacity-throttling, `earliest_start_hint` on `DailyOutput`, `CalendarBlockProposal`
  in the engine (calendar writes are out for the whole rollout), `meetings_captured` telemetry.
