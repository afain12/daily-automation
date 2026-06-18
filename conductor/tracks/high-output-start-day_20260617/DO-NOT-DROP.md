# DO-NOT-DROP — the restructure must touch ONLY Step 6 + Step 7

Source: regression/completeness review 2026-06-17. The restructure is a SURGICAL edit. Every item
below is load-bearing plumbing that MUST survive byte-for-byte. The safe way to guarantee that is to
leave its SKILL.md region unedited. If you must touch a region, this is the checklist it has to still pass.

## Leave these regions byte-for-byte (do NOT edit)
- Step 0 mode check (`check_mode.sh`, `SKIP_WRITES`, `RUN_START_MS`)
- Step 1 config load + streams_check
- Step 1b pre-flight: `.context/*.json` audit (excludes `.context/applied/` AND `.context/preview/`; absent `status` ≠ unwritten); sync-sweep DLQ depth; memory↔calendar gap check
- Step 1c catch-up sync: bidirectional reconcile, `pull_completions` (file edit) vs `push_completions` (API), `gws tasks tasks patch` (NOT curl — 401s here), `gtask-retry-queue.yaml` drain, once-per-day guard
- Step 1d suppression: ALL 5 sources (`dropped_*`, `back_burner`, `dormant_snooze`, yesterday daily-note phrase-match w/ typo list, parent→subtask transitive); conservative false-negative bias
- Step 2 calendar pull + stream tagging
- Step 3 Notion pulls (`/v1/data_sources/{id}/query`, suppress per-DB) + Granola TWO-PATH detection (DB row vs topic-page append; `/v1/search` 8-char fragment before declaring a sync gap)
- Step 4 vault scan; Step 5 Tasks pull (+ suppression)
- Step 6b 24h Notion change audit
- Step 8 trust gate (A/B/C; observe=informational); Step 8b TWO gates (Gate 1 file edit, Gate 2 API)
- Step 9 plumbing: daily-note APPEND-if-exists, mobile mirror (`mobile_briefing_page_id`, fail silent), log write
- Step 10 telemetry (append-only, frozen field names)

## Contracts that MUST hold in the edited Step 6/7 output
- [ ] `## Top 3 Outcomes` numbered list → `logs/{DATE}.md` (the LOG, via `render_log_top3`). Daily-note headline may be "Today — Ship These 3". NEVER put "Today — Ship These 3" in the log or "Top 3 Outcomes" in the daily-note headline.
- [ ] Every `- [ ]` in the demoted stream list keeps its `<!-- gtask:ID -->` / `<!-- notion:ID -->` at COLUMN 0; one ID per checkbox; never indented.
- [ ] `## End of Day Review` heading verbatim in the daily note; keep it last or with a `## ` after it (Hermes regex lookahead).
- [ ] `🔇 Suppressed N items` audit footer still rendered (Aaron catches false positives).
- [ ] `## Awaiting Others`, `## Provider Follow-ups Needed` (feeds provider_followup_nudge automation), `## Skipped Sources` (feeds telemetry `sources_skipped`), `## Memory ↔ Calendar Gaps` — all still rendered when non-empty.

## Top-3 silent-drop risks (most likely to be forgotten)
1. Step 1c catch-up sync loop — don't let "purge gws/curl" delete the bidirectional reconcile.
2. Markers aggregated onto indented sub-bullets → parser silently returns 0 actions.
3. Suppression collapsed to a naive `dropped_*` id-lookup, losing phrase-match + transitive paths.

## Verify (per edit)
`bash scripts/skill_lint.sh` · contract-anchor greps · `python3 -m unittest discover -s tests` ·
dual-copy diff of the new sections · manual eyeball of one rendered briefing.
