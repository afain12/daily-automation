# Test Strategy — high-output-start-day_20260617

Stdlib `unittest` only (repo convention — no pytest). Tests import modules via
`sys.path.insert(0, .../scripts)` like `tests/test_end_day_orchestrator.py`.
Run all: `python -m unittest discover -s tests`.

## Two test tiers

| Tier | Definition | Mocks? | Network? | Files |
|------|-----------|--------|----------|-------|
| **Unit** | One pure function, one assertion theme | none | none | `test_output_planning.py` |
| **E2E** | Full render → write files → real parse loop | NONE (real orchestrator) | none (fixtures) | `test_render_parse_roundtrip.py`, `test_start_day_wrapper_e2e.py` |
| Live-API e2e | One approved calendar block | n/a | yes (Phase E only) | manual, never CI |

The e2e tier is the alignment guarantee: it imports the **real**
`end_day_orchestrator` and feeds it the renderer's actual output. No stubbed
parser — if start-day and end-day drift, these fail.

## Coverage matrix (test ↔ folded change)

| Folded change | Guarded by |
|---|---|
| #1 Phase-C gate (identical sync actions old vs mixed) | `test_render_parse_roundtrip` parametrized over both fixtures |
| #2 Golden render-pair fixture | the fixtures + both e2e suites consume them |
| #3 Minimal DelegationAsk schema | `test_delegation_ask_roundtrip`, scorecard `delegated` test |
| #4 gws/curl purge + drift grep + stable next-block | `scripts/skill_drift_check.sh` (CI step) + `test_next_block_label_is_display_only` |
| Codex: completion_policy → child markers | `test_resolve_completion_any_all_manual` |
| Codex: aaron_confirmed override, no double-count | `test_scorecard_dedup_aaron_confirmed` |
| Contract: markers on non-indented `- [x]` | `test_markers_on_toplevel_checkbox_lines` |
| Contract: previews isolated to `.context/preview/` | Phase D validation assertion |

## Regression guards (must stay green untouched)

- `tests/test_end_day_orchestrator.py` — 4 existing tests.
- `python scripts/capture_meeting_parse.py --self-test`
- `bash scripts/skill_lint.sh`
- `python scripts/streams_check.py`

## Definition of done per phase

A phase is done only when: its unit tests pass, its e2e tests pass, the 4 existing
regression guards pass, and (Phase C+) `skill_drift_check.sh` passes. Red→green
commits are atomic; no phase merges with a skipped or `xfail` test lacking a
written "remove after" condition.
