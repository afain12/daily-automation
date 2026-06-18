# Track: High-Output Start-Day / End-Day Restructure

- **Slug:** `high-output-start-day_20260617`
- **Branch:** `feat/high-output-start-day`
- **Worktree:** `.worktrees/high-output-start-day`
- **Status:** `[ ] Pending`
- **Created:** 2026-06-17
- **Owner:** Aaron (single-user personal COO Twin)

## Goal

Restructure `/start-day` and `/end-day` from a task-list into an Andy-Grove
"outputs" operating system: each morning surfaces exactly **3 business outputs**
with a done-state, owner, proof type, and next block; each evening scores whether
those outputs actually shipped. Roll out **shadow-mode first**, preserve the
existing `/end-day` sync contract exactly, and defer all calendar writes until the
judgment layer is proven.

## Why (review-backed)

Reviewed by three independent Sonnet agents (strategy / build-plan / Hermes-compat)
and one OpenAI Codex consult pass (session `019ed83f-f2cc-73b0-b2fd-bbd85301f5ae`).
All four converge on: cut the gold-plating (Portfolio Pulse, visible scoring rubric,
day-mode), keep the 3-output core, and protect the `/end-day` parser contract above
everything. Source docs: `start day revamp/01`–`05`.

## The four folded changes (this track exists to encode these)

1. **End-day contract test gates Phase C, not Phase D.** `/start-day`'s new render
   does not ship to the Hermes runtime until a test proves the rendered note is
   still consumable by the existing sync parser. (Codex Q3.)
2. **Golden "render-pair" fixture is the central alignment artifact.** One
   `logs/{DATE}.md` + one `vault/daily/{DATE}.md`, produced by the start-day
   renderer and consumed by **both** start-day render tests **and** end-day parser
   tests. This is the e2e backbone that stops the two skills drifting. (Codex Q6.)
3. **Keep a minimal `DelegationAsk` schema now** (delegatee, ask, date, source_ref,
   confirmation_state) — do not fully defer it, because `delegated` is a first-class
   proof type and Aaron's locked answer makes delegation count as shipped. (Codex Q6.)
4. **Purge `gws`/`curl` from BOTH skill copies entirely + add a drift grep**, not
   just touched steps; give `next-block` a stable display-only text format now.
   (Codex Q5/Q6.)

Adopted Codex sharpenings carried through the phases:
- `completion_policy ∈ {any, all, manual}` maps to **child checkbox-marker states**,
  not parent prose.
- `aaron_confirmed` is an **override on output status, not an additive proof event**;
  dedupe scorecard evidence by `output_id + proof_type + source_id`.
- Phase A defines the **exact rendered-markdown contract**, not just dataclasses.
- Conservative **1:1 grouping** is the default; aggregation is opt-in and tested.

## Hard contract facts (must not regress)

- `scripts/end_day_orchestrator.py :: extract_checked_source_actions` parses ONLY
  lines matching `^- \[[xX]\]\s+` and marker regex
  `<!--\s*(gtask|notion|derived):([^>]+?)\s*-->`. Markers must stay on top-level
  (non-indented) checkbox lines.
- **Split read paths:** `/end-day` reads `## Top 3 Outcomes` from `logs/{DATE}.md`
  and the marked checkboxes from `vault/daily/{DATE}.md`; it fills `## End of Day
  Review` in the daily note. The renderer must write all three correctly.
- Preview artifacts stage under `.context/preview/`; top-level `.context/*.json`
  means a real pending write. Never stage shadow previews top-level.
- Telemetry is append-only; new fields are additive only.
- Every external write keeps `action_id` generate/check/stamp.

## Scope

**In:** `scripts/output_planning.py`, `scripts/start_day.py`, the render-pair
fixtures, unit + e2e test suites, `scripts/skill_drift_check.sh`, additive
`extract_daily_outputs` / `build_output_scorecard` in the orchestrator, shadow-mode
edits to the two active `start-day`/`end-day` skill copies.

**Out (non-goals for this track):** live Google Calendar event creation, Notion
status mutation from aggregated outputs, outbound messages, removing old
`## Top 3 Outcomes`, editing `.agents/skills/` (obsolete), Portfolio Pulse,
day-mode classifier, visible scoring rubric.

## Acceptance criteria

- `/start-day` renders a phone-first 3-output shadow section AND preserves
  `## Top 3 Outcomes`, `## Actionable Items by Department` (with markers), and
  `## End of Day Review` exactly.
- `python -m unittest discover -s tests` passes, including the new unit + e2e suites.
- The golden render-pair e2e proves `extract_checked_source_actions` returns the
  identical action set on old-format and mixed-format notes.
- `scripts/skill_drift_check.sh` passes (no `gws` / raw Notion `curl` in active
  skill bodies; both copies converge to the wrapper call).
- No shadow artifact appears as a top-level `.context/*.json` pending write.
- Existing `tests/test_end_day_orchestrator.py` (4 tests) still passes unchanged.

## Rollback criteria (keep shadow-only / revert Phase C)

Source markers lost · `/end-day` fails to parse checkboxes or Top 3 · Aaron rejects
selected outputs on 2 of 3 shadow days · phone top section too long · preview
artifacts trigger pending-write flags · aggregation hides child gtask/notion anchors
· any live write fires without approval.
