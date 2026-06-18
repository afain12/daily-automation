# Review Gates & Execution Methodology — high-output-start-day_20260617

Every phase (A–E) runs the SAME execute → verify → codex → quality loop below.
No phase advances until its gate is green. This operationalizes
`.claude/rules/codex-review-discipline.md` and `.claude/rules/worktree-discipline.md`
for this track.

## The standard per-stage loop (MANDATORY at each phase)

```
1. EXECUTE   → /dispatch  (single-domain phases: B, C)
               subagent-driven-development  (multi-task phases: A, D)
               TDD red→green→refactor, atomic commits in the worktree
2. SELF-VERIFY → unit + e2e green AND 4 regression guards green
                 (/verification-before-completion)
3. CODEX     → /codex review against the phase diff/PR URL.
               Iterate per codex-review-discipline: re-run after each fix.
               Stop only when 0×[P1] and remaining [P2]s are consciously deferred.
4. QUALITY   → spawn the phase's review agent(s) READ-ONLY on the diff (below).
               Resolve every production-risk / convention finding or defer with reason.
5. GATE      → advance only when steps 3 and 4 are clean. Record the codex round
               count + agent verdict in the phase's commit/PR notes.
```

### Step 1 — execution tool by phase shape
- **`/dispatch`** for single-domain, well-scoped phases (B wrapper, C skill edits):
  it injects project context, auto-selects domain skills (e.g.
  `python-testing-patterns`, `bash-defensive-patterns`), picks inline-vs-delegated,
  and auto-verifies.
- **`subagent-driven-development`** for multi-task phases (A: dataclasses +
  render contract + fixtures + suites; D: orchestrator parser + scorecard +
  skill edits): a coordinator decomposes the phase into worker subagents with
  strict return contracts, then integrates. Workers implement against the tests;
  the coordinator owns the trust/merge.

### Step 3 — codex scope per phase
Pass the phase diff (PR URL form preferred; invoke from the worktree CWD per
codex-discipline so findings aren't attributed to the wrong branch):
```bash
cd .worktrees/high-output-start-day
codex review https://github.com/<owner>/<repo>/pull/<N> -c 'model_reasoning_effort="high"' --enable web_search_cached
# or pre-merge, against the local diff:  /codex review
```
Iterate until convergence. Escalate to human deep review if the same finding
class appears in 2+ consecutive rounds (codex saturating) or 4+ rounds without
convergence (split the phase).

### Step 4 — quality agents per phase (read-only, from `.claude/agents/`)

| Phase | Primary agent | Focus |
|-------|---------------|-------|
| A — pure module | `code-reviewer` | dataclass design, scoring/grouping correctness, marker preservation, test completeness |
| B — wrapper | `code-reviewer` | arg parsing, graceful degradation, subprocess/e2e seams, no gws/curl leak |
| C — runtime skill edits | `quality-reviewer` | **parser-contract regression**, drift-check completeness, anchor preservation, dual-copy convergence (load-bearing) |
| D — orchestrator | `quality-reviewer` + `code-reviewer` | `end_day_orchestrator.py` sync contract, additive-telemetry only, dedup/override correctness (load-bearing) |
| E — calendar adapter | `quality-reviewer` | idempotency, overlap/DST, action_id stamp-after-success, auth handling |

Spawn pattern (parallel when independent, single message):
```
Agent(subagent_type="quality-reviewer", prompt="Review the Phase C diff in
.worktrees/high-output-start-day against base. Focus: does the new render break
extract_checked_source_actions? Are gws/curl fully purged from both skill copies?
READ-ONLY, return prioritized findings.")
```

## Phase gate definitions (codex + quality, on top of tests.md DoD)

- **A gate:** unit + e2e green · `code-reviewer` clean · codex 0×[P1].
- **B gate:** wrapper e2e green · `code-reviewer` clean · codex 0×[P1].
- **C gate (load-bearing):** Phase-A/B e2e + `skill_drift_check.sh` + `skill_lint.sh`
  green · `quality-reviewer` confirms parser contract intact · codex 0×[P1],
  iterated to convergence (required per discipline: touches runtime + the sync path).
- **D gate (load-bearing):** orchestrator tests green · previews isolated ·
  `quality-reviewer` + `code-reviewer` clean · codex 0×[P1] iterated (required:
  function signatures + telemetry plumbing on the load-bearing
  `end_day_orchestrator.py`).
- **E gate:** fake-adapter tests green · `quality-reviewer` clean · codex 0×[P1] ·
  one human-approved live block verified.

## Pre-implementation review (already done for this track)

3× Sonnet reviews (strategy/build/compat) + 1× Codex consult
(`019ed83f-f2cc-73b0-b2fd-bbd85301f5ae`) reshaped the plan before code. That is
the EARLIER half of the iterative pattern; the per-phase gates above are the
post-code half.
