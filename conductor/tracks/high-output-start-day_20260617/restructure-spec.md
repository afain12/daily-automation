# Restructure spec — /start-day as a High Output operating system (primary, not shadow)

Decision (2026-06-17): skip shadow mode. Make the High Output Management model the
PRIMARY briefing. The contract gate (test_render_parse_roundtrip) is the safety net that
makes a direct replace safe — it proves new rendering never drops what /end-day reads.

## Principle (re-anchor)
Grove: a manager's output = output of their org + neighboring orgs under their influence.
start-day stops being a department to-do aggregator and becomes a **leverage allocator**:
lead with where the leverage is, commit to 3 outputs, count delegation as output, triage the rest.

## Target briefing order (Step 7 rewrite) — leverage at the top, plumbing below
1. Header — date, day, `Mode:`.
2. **## Portfolio Pulse** — one line per business: which is the binding constraint today + why.
   The single highest-leverage framing; it decides what the 3 outputs should be.
3. **## Kill / Defer / Delegate** — daily triage of stale / low-leverage items (the "what NOT to do
   today") — comes BEFORE the outputs (decide what you're not doing before committing capacity). See synthesis #2.
4. **## Today — Ship These 3** — the 3 outputs (render via `output_planning.render_output_plan_markdown`).
   Phone-first compact bullets, markers on column-0 checkboxes. THE headline.
5. **## Meetings That Must Convert** — today's meetings that must produce a decision / owner / next action.
6. Operational alerts (catch-up sync, memory↔calendar gaps, pending writes) — KEEP, compacted, below the fold.
7. Demoted supporting detail: Calendar, **Actionable Items by Stream** (now a reference backlog, NOT the headline),
   Meeting Recaps, Notion Changes, Provider Follow-ups, Suppressed audit. All retained, just demoted.
8. `## End of Day Review` placeholder — UNCHANGED heading (contract #3).

## Selection rework (Step 6 rewrite) — per context/selection-algorithm.md
Replace the current scoring with: Portfolio Pulse (which business is the constraint) →
leverage score (constraint-removal > revenue/relationship > delegation-counts-as-shipped >
meeting-conversion > admin) → day-type filter (field day = no deep-work blocks) →
starvation guard → output exactly 3.

## Day-type classification (new, was missing)
Classify today from the calendar: field day / deep-work / firefight / admin. Drives whether
calendar blocks are proposed and how aggressive the 3 outputs are.

## CONTRACTS — preserve verbatim (see CONTRACTS.md, all 8). The restructure must NOT break:
- `## Top 3 Outcomes` STILL written to `logs/{DATE}.md` via `render_log_top3` (contract #2) — the
  daily-note headline may be "Today — Ship These 3", but the LOG keeps the exact `## Top 3 Outcomes`.
- Source markers stay on non-indented `- [ ]` lines (contract #1).
- `## End of Day Review` heading unchanged (contract #3).
- `state/priorities.yaml` keys additive-only; suppression set still consumed (contract #4).
- `.context/preview/` isolation, telemetry append-only, action_id format (contracts 5-7).
- Both skill copies (.claude + ~/.hermes) edited together (contract #8).

## Must-NOT-drop (regression guard — the current skill does a lot)
Every existing load-bearing step stays functional: Step 1b pre-flight, Step 1c catch-up sync,
Step 1d suppression, Step 3 Granola/topic-page sync-gap detection, Step 5 Tasks, Step 8 trust
gate, Step 9 execute. The restructure REORDERS and REFRAMES the OUTPUT; it does not delete plumbing.

## Out of scope (defer)
Calendar block writes (still gated), the typed scorecard engine, weekly pattern-learning loop.

## 4-LENS REVIEW SYNTHESIS (2026-06-17 — binding, overrides anything above that conflicts)

**1. SURGICAL, NOT REWRITE.** The 1,107-line skill is mostly load-bearing plumbing. Touch ONLY
Step 6 (selection scoring) and Step 7 (briefing order + new sections). Leave Steps 0–5, 1b/1c/1d,
8/8b, 9 plumbing, and 10 BYTE-FOR-BYTE. See `DO-NOT-DROP.md` — it is the implementer's bible.
You cannot silently drop what you do not touch.

**2. REORDER (10x).** Step 7 order: Portfolio Pulse → **Kill/Defer/Delegate** → Today: Ship These 3
→ Meetings That Must Convert → (operational alerts + demoted stream list below). Kill/Defer/Delegate
comes BEFORE the 3 outputs — decide what you're NOT doing before committing capacity.

**3. done_when (10x — the single highest-value change).** `DailyOutput` gets a `done_when` field.
`render_output_plan_markdown` REFUSES to render an output whose `done_when` is null or matches
`work on X / make progress on X / follow up on X`. This forces real outputs, not a reordered task dump.

**4. DETERMINISTIC RENDERER, NOT LLM FREEHAND (contract).** The marker-bearing checkbox lines MUST
come from `output_planning` (verbatim), never LLM-composed prose. The SKILL.md instructs the model to
call the renderer and paste output exactly; never reindent/ paraphrase a checkbox line.

**5. PORTFOLIO PULSE MUST BITE (10x).** Each line names the SPECIFIC constraint (not category) and
emits a capital-allocation % (e.g. "60% IPA"). The selector enforces it: absent strong override, ≥2 of
3 outputs come from the highest-allocation business. EOD-verifiable.

**6. DEMOTE = POSITION-ONLY.** The stream task-list keeps full `- [ ]` + `<!-- system:id -->` column-0
format and stream grouping. Demotion is reading-order only, NOT content/ID reduction (catch-up sync depends on it).

**7. SELECTION HEURISTICS (10x — make leverage detectable).** constraint-removal = 0 assignees + Status
"Waiting", or "credentialing/approval/sign-off" in title. Starvation N = 7 (inherit existing). Delegation
counts only with a named delegatee from `state/profile.yaml` + a next-step they can do without Aaron.

**8. TEST EXTENSIONS.** Add to test_render_parse_roundtrip / test_output_planning: bidirectional heading
check (`render_log_top3` ⊄ "Ship These 3"; `render_output_plan_markdown` ⊄ "Top 3 Outcomes"); done_when
guard test; EOD-heading-position assertion. Build `deploy_hermes_skills.sh` BEFORE editing the Hermes copy.

## Done =
Step 6 + Step 7 surgically restructured (both copies), output_planning has done_when + Pulse allocation,
contract gate + new tests green, ZERO plumbing step touched (DO-NOT-DROP verified), reviewed (codex + quality).
