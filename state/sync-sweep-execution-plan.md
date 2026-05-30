# /sync-sweep — Execution Plan

**Date locked:** 2026-05-19
**Status:** READY TO BUILD (Eng Review CLEARED)
**Estimated build:** Class A MVE ~7h · Full v0.2 ~17h
**Build model:** Subagent-driven development, hybrid agent team (persistent lead + one-shot workers)

This document is the **single source of truth for executing the build.** It does not duplicate the spec — it points to artifacts, defines the team, and sequences the launches.

---

## 1. Artifacts (read these before any launch)

| Artifact | Path | Role |
|---|---|---|
| **Spec v0.2 (eng-cleared)** | `state/aac-spec-sync-sweep.md` | Architecture source of truth. 16 AAC sections, 4 input classes, 5 extras (E1-E5), 3 locked eng-review decisions (D1/D2/D3), `## GSTACK REVIEW REPORT` at end |
| **Task list** | `state/sync-sweep-tasks.md` | 23 atomic tasks, 5 phases, ~17h total. Each task has file paths + acceptance criteria + dependencies |
| **Eval fixtures** | `state/sync-sweep-eval-fixtures.yaml` | 45 hand-labeled entity extractions across 8 days of braindumps. **Pass gate for Phase 4** |
| **Test plan** | `~/.gstack/projects/daily-automation/afain1-master-eng-review-test-plan-20260519-1400.md` | Affected pages, key interactions, edge cases, critical paths, eval fixture validation gate |
| **AAC framework** | `state/aac-framework-extraction.md` | Discipline reference (BOUNDED, GROUNDED, GATED, OBSERVED, GOVERNED) |
| **Skills audit** | `state/aac-audit-of-current-skills.md` | Patterns from /start-day, /capture-meeting, /end-day — reuse, don't reinvent |

---

## 2. Team composition

**Model:** Hybrid (persistent team-lead, one-shot specialist workers).
**Coordination protocol:** Lead reviews specialist output before integration. Specialists never write to each other. All cross-specialist handoffs go through lead via `SendMessage`.

| Role | Agent type | Persistence | Job |
|---|---|---|---|
| **Team lead** | `kiro-plan` named `sync-sweep-lead-v2` | Persistent across sessions | Maintains task list, assigns work to specialists, integrates specialist outputs, surfaces blockers to Aaron |
| **Phase 1A/1B builder** | `python-backend-expert` | One-shot per task | Builds `capture_meeting_parse.py`, `capture_meeting_write.py`, validates parity against existing /capture-meeting |
| **Phase 2 builder** | `python-backend-expert` | One-shot per task | Builds `sync_sweep_notion_latest.py`, `sync_sweep_entity_extract.py`, helper scripts |
| **Skill markdown author** | `claude` (main session) | Inline | Writes `.claude/skills/sync-sweep/skill.md` orchestration layer (trust gate, mode check, top-level flow) |
| **Code reviewer** | `code-reviewer` | One-shot at phase boundaries | Reviews each completed phase for security, AAC discipline, test coverage |
| **Eval runner** | `general-purpose` | One-shot at Phase 4 | Runs /sync-sweep in `mode: observe` against fixtures, computes precision/recall, gates promotion |

**Anti-patterns to avoid:**
- Specialist agents writing to each other directly. Always route through `sync-sweep-lead-v2`.
- Launching builders before lead has confirmed task is ready.
- Skipping the code-reviewer gate between phases.
- Building Phase 2 before Phase 1A's parity gate passes.

---

## 3. Phase sequence with gates

### Phase 1A — Extract `capture_meeting_parse.py`

**Tasks:** T1, T2, T3, T3a (4 tasks, ~3h)

**Builder:** `python-backend-expert` (one-shot, with full context: Explore worker's extraction plan + the parse-side risks).

**Gate to pass before Phase 1B:**
- New script invocable: `python scripts/capture_meeting_parse.py --notes-file <test> --business-tag nestmate --attendees "X" --meeting-key TEST --date 2026-05-19`
- Output JSON validates against the schema in spec §7 + the per-item structure from Explore's report
- **Parity check:** run the same meeting note through old (inline /capture-meeting) and new (extracted script) paths. Diff categorizations. Pass = identical category assignments + identical confidence within ±0.05
- gws keyring banner strip test passes (G7)
- `scripts/action_id.sh` invoked, not reimplemented

**Code-reviewer pass at gate:** focus on `--date` argument handling (D1 risk), business-tag fallback when empty (Explore risk), action_id consistency.

### Phase 1B — Extract `capture_meeting_write.py`

**Tasks:** T4 (1 task, ~1.5h)

**Builder:** `python-backend-expert` (one-shot).

**Dependency:** Phase 1A gate passed.

**Gate to pass before Phase 2:**
- New script invocable: `python scripts/capture_meeting_write.py --parsed-items <json> --recap-page-id <id> --dry-run`
- Dry-run produces correct PATCH payloads (don't actually write to Notion)
- Live run on a sandbox Notion page creates: parent task → subtasks → Google Tasks mirror → Granola back-link PATCH (in that order)
- Granola back-link PATCH merges existing relations (no clobber test)
- Failure mid-sequence reports partial success cleanly

**Code-reviewer pass at gate:** focus on accumulated-state JSON handoff, recap back-link relation merge.

### Phase 2 — Build `/sync-sweep` skill + helper scripts

**Tasks:** T5-T16 (12 tasks, ~8h)

**Sub-phases (sequential within Phase 2):**

| Sub-phase | Tasks | Builder | Acceptance |
|---|---|---|---|
| 2.1 — Entity extraction script | T5, T6 | python-backend-expert | Schema output matches §7; corrected E1 (soft prior + line override + context window) implemented |
| 2.2 — `## Latest:` prepend helper | T9 | python-backend-expert | Pagination walk (G1) + verify-after-PATCH repair (G2) tests pass |
| 2.3 — Disambig memory + entity_aliases | T7, T8 | python-backend-expert | `state/sync-sweep-resolutions.yaml` shape correct, 3-confirmation graduation rule works |
| 2.4 — Duplicate-append guard | T10 | python-backend-expert | E5 cosine similarity ≥0.75 routes to trust gate as `[DUPLICATE]` |
| 2.5 — Daily-note strikethrough | T11 | python-backend-expert | Strikethrough + `<!-- synced to notion:ID -->` appears; re-runs skip on regex match |
| 2.6 — Class C meeting auto-process | T12, T13 | python-backend-expert | 0.92 floor enforced (G3); empty Workspace fallback works |
| 2.7 — Class A vs D collision | T14 | python-backend-expert | Class A wins on collision (G4); stub flagged in trust gate |
| 2.8 — Retry queue + DLQ | T15, T19 | python-backend-expert | 3-attempt retry → DLQ graduation (G6); `/start-day` flag wiring |
| 2.9 — Skill markdown orchestration | T16 | claude (main) | `.claude/skills/sync-sweep/skill.md` glues everything; trust gate, mode check, telemetry |

**Code-reviewer pass at Phase 2 gate (single review covering all sub-phases):** AAC discipline adherence (BOUNDED/GROUNDED/GATED/OBSERVED/GOVERNED), security (NOTION_API_TOKEN handling, curl payload escaping), no `git add -A`, no broken trust gate.

### Phase 3 — Integration with `/end-day` + docs

**Tasks:** T17, T18, T20 (3 tasks, ~1.5h)

**Builder:** claude (main) — these are skill markdown edits, not new code.

**Acceptance:**
- `/end-day` Step 9 calls `/sync-sweep` as final step (graceful skip if /sync-sweep unavailable)
- `CLAUDE.md` updated with /sync-sweep description in the Skills table + key principles section
- Cron prep documented (post-MVE Hermes/Railway path noted, not yet wired)

### Phase 4 — Validation + regression protocol

**Tasks:** T21, T22, T23, G5 (4 tasks, ~3h)

**Eval runner:** `general-purpose` agent.

**Acceptance — hard gate for "v0.2 done":**
- Run `/sync-sweep` in `mode: observe` against `state/sync-sweep-eval-fixtures.yaml`
- **Pass = ≥85% agreement on high+medium confidence fixtures (33 records), ≥70% on low (5 records)**
- PHI scan integration test (G5) passes: SSN pattern → refusal logged, no LLM call
- Regression protocol documented: any prompt change must re-benchmark against fixtures, ≥85% required before promotion
- Monthly fixture refresh task added to the daily-automation TODOS or cron

**If eval fails:** fix prompt, re-run fixtures. Do NOT promote until threshold met.

---

## 4. MVE-first vs one-shot full v0.2

**Recommended path: MVE-first.**

| Path | Scope | Time | Risk |
|---|---|---|---|
| **MVE-first (recommended)** | Phase 1A + Phase 2.1 + Phase 2.2 + Phase 2.4 + Phase 2.5 + Phase 3 + minimal Phase 4 (class A only) | ~7h | Low. Validates the entity-resolution + page-append flow against your actual braindumps for ~1 week before adding Class B/C/D complexity |
| **One-shot full v0.2** | All 5 phases, all 4 input classes | ~17h | Medium. Class C (meeting auto-process) creates Master Tasks irreversibly; bugs here cost cleanup time |

**MVE = class A only.** Defer class B (Obsidian vault scan), class C (Meeting Notes auto-process), class D (new-page active write) to v0.2 after one week of real-data usage.

After MVE, the v0.2 expansion costs ~10 additional hours (Phase 1B + Phase 2.3 + Phase 2.6 + Phase 2.7 + Phase 2.8).

---

## 5. Launch protocol — exact commands

### Resume from any session

When you sit down to continue, say one of:

- `"go"` or `"start build"` — launches Phase 1A
- `"resume sync-sweep build"` — checks status, launches next pending phase
- `"status"` — sync-sweep-lead-v2 reports current phase, pending tasks, blockers
- `"pause"` — saves state via /context-save, ends session cleanly

### Phase 1A launch (the next concrete action)

I (claude main) will execute this when you say "go":

```
1. SendMessage to sync-sweep-lead-v2: "Begin Phase 1A. Assign T1, T2, T3, T3a to a python-backend-expert worker. Brief the worker with:
   - Explore worker's extraction plan (capture_meeting_parse.py signature + 5 risks)
   - Spec §8 (C-element specs) for confidence rubric
   - state/sync-sweep-tasks.md for atomic acceptance criteria
   - Existing /capture-meeting Steps 4 + 4.5 as the parity reference
   - Sandbox Notion page id (Aaron will provide, or use a test scratch page)
   When worker returns, run parity check, then SendMessage Aaron with pass/fail."

2. sync-sweep-lead-v2 launches the python-backend-expert worker in foreground (we wait on result before continuing).

3. On worker return: lead validates against acceptance criteria, runs the parity diff, reports to Aaron.

4. Aaron decides: proceed to Phase 1B, fix issues, or pause.
```

### Code reviewer launch (between every phase)

```
SendMessage to sync-sweep-lead-v2: "Phase {N} build complete. Spawn code-reviewer on the diff scoped to:
  - new files: <list>
  - modified files: <list>
Focus: AAC discipline, security (token + curl escaping), trust gate completeness, test coverage gaps.
Block phase transition on any P0/P1 findings."
```

### Pause protocol

If you need to stop mid-phase:

```
1. Run /context-save (gstack skill) — captures git state + decisions + remaining work
2. SendMessage to sync-sweep-lead-v2: "Pausing at task {Tn}. Persist current phase state. I'll resume with 'resume sync-sweep build'."
3. Lead writes a checkpoint marker to state/sync-sweep-checkpoint.yaml: {current_phase, last_completed_task, blockers, next_action}
4. Next session: say "resume sync-sweep build" — lead reads checkpoint, briefs the next worker, you pick up.
```

---

## 6. Quality gates checklist

Track build state by checking these off in order. Each row is a hard gate — do not advance until checked.

### Phase 1A gates
- [ ] T1 done: `scripts/capture_meeting_parse.py` exists, executable, `--help` works
- [ ] T2 done: parses canonical test meeting note into JSON matching schema
- [ ] T3 done: confidence scoring rubric implemented per spec §8
- [ ] T3a done: gws keyring banner strip unit test passes (G7)
- [ ] **Parity check pass:** old vs new categorization identical on 5 test meetings
- [ ] Code-reviewer pass: no P0/P1

### Phase 1B gates
- [ ] T4 done: `scripts/capture_meeting_write.py` exists, dry-run works
- [ ] Live sandbox test: parent + subtasks + GTasks + back-link all created correctly
- [ ] Back-link relation merge test (no clobber)
- [ ] Code-reviewer pass

### Phase 2 gates (per sub-phase)
- [ ] 2.1 — entity extraction script works, schema matches §7
- [ ] 2.2 — `## Latest:` pagination + auto-repair tests pass (G1, G2)
- [ ] 2.3 — disambig memory + 3-confirmation graduation works
- [ ] 2.4 — duplicate-append guard (E5) works
- [ ] 2.5 — daily-note strikethrough works, re-runs skip
- [ ] 2.6 — class C 0.92 floor enforced (G3)
- [ ] 2.7 — class A wins on collision (G4)
- [ ] 2.8 — retry → DLQ (G6)
- [ ] 2.9 — skill markdown renders, mode check works, trust gate displays
- [ ] Phase 2 code-reviewer pass

### Phase 3 gates
- [ ] T17 — /end-day Step 9 calls /sync-sweep, graceful skip if unavailable
- [ ] T18 — CLAUDE.md updated
- [ ] T20 — cron prep documented (not wired)

### Phase 4 gates (FINAL — release gate)
- [ ] T21 — eval runner executes /sync-sweep in observe mode against fixtures
- [ ] **≥85% agreement on 33 high+medium fixtures**
- [ ] **≥70% agreement on 5 low fixtures**
- [ ] T22 — regression protocol documented in skill markdown
- [ ] T23 — PHI scan integration test passes (G5)
- [ ] Telemetry verified: one row per /sync-sweep run in `logs/_telemetry.jsonl`
- [ ] Memory updated: `project_sync_sweep_skill.md` flipped from "planned" to "active"

---

## 7. Rollback / pause points

| If this happens | Do this |
|---|---|
| Phase 1A parity check fails | Revert `scripts/capture_meeting_parse.py`, brief python-backend-expert with the specific divergence cases, retry. Do NOT advance to 1B. |
| Phase 2 sub-phase test fails | Fix in place. Other sub-phases can proceed in parallel if their dependencies haven't shifted. |
| Phase 4 eval score <85% on high+medium fixtures | Treat as build-not-done. Fix entity extraction prompt, re-run. Do not flip memory to "active". |
| Notion API token rotated mid-build | Pause all writes, update `.secrets/notion.env` + `.claude/settings.local.json`, resume |
| sync-sweep-lead-v2 becomes unreachable | Spawn fresh kiro-plan named `sync-sweep-lead-v3`, brief with this execution plan + current checkpoint. State is in files, not in agent memory. |
| You change your mind about an extra (E1-E5) | Edit the spec, then SendMessage lead with the diff. Lead updates affected tasks. |

---

## 8. Post-MVE expansion path

After class A MVE ships and survives ~1 week of real braindumps:

1. **Class B (Obsidian vault scan)** — Phase 2.x expansion. Reads `vault/Nestmate/`, `vault/Labaide/`, etc. recent edits, routes content into matching Notion compartments using same entity-resolution engine.
2. **Class C (Meeting Notes auto-process)** — Phase 1B + Phase 2.6. Uses `scripts/capture_meeting_write.py` extracted in Phase 1B. **Higher stakes** (creates new Master Tasks) — 0.92 floor enforced.
3. **Class D (new Notion pages active write)** — Phase 2.7. Reads new Notion pages from last 24h, routes Obsidian context into them.

Each class addition: re-run Phase 4 fixtures eval to ensure no regression on existing classes.

---

## 9. Open items (not blocking build)

- **Scheduling cadence post-MVE** — decided alongside `[[project-hermes-railway-default]]` Hermes/Railway flip. Until then: on-demand + `/end-day` final step only.
- **Monthly fixture refresh** — will be a recurring task once 30 days of usage data exists.
- **v3 ideas (deferred per eng review):** cross-day soft prior, CRM Stage advancement, Gmail integration, gtask reverse-sync consolidation, telemetry-driven prompt tuning loop.

---

## 10. What to type next session

If you're picking this up cold:

```
"resume sync-sweep build"
```

I will:
1. Check `state/sync-sweep-checkpoint.yaml` if present (last known phase + blockers)
2. Verify `sync-sweep-lead-v2` is still addressable; if not, spawn `-v3` with this plan
3. Brief you on current phase + pending action
4. Wait for your "go" or further direction

If you want a status snapshot without resuming:

```
"sync-sweep status"
```

If you want to launch Phase 1A right now:

```
"go" or "start sync-sweep build"
```
