# CONTRACTS — must-not-break (READ FIRST, every implementer subagent)

Source: 4-lens review 2026-06-17 (compat / blast-radius pass). These are the hard
contracts between `/start-day`, `/end-day`, and the Hermes runtime. Breaking any of
them silently corrupts the morning↔evening handshake. **Preserve all 8. No exceptions
without an explicit gate.**

| # | Contract | Writer | Reader | Rule |
|---|----------|--------|--------|------|
| 1 | **Source markers on NON-indented `- [ ]` lines** | start-day Step 9 (daily note) | end-day `extract_checked_source_actions` regex `^- \[[xX]\]\s+` + `<!--\s*(gtask\|notion\|derived):...-->` | CRITICAL. Markers MUST stay at column 0. A `DailyOutput` parent bullet may exist but must NOT absorb child markers into indented sub-bullets, or all sync writes silently drop. |
| 2 | **`## Top 3 Outcomes` lives in `logs/{DATE}.md`** (the log, not the daily note) | start-day Step 9 (`render_log_top3`) | end-day Step 1 + `end_day_orchestrator.py` | HIGH. Heading exact-match. Write it to the LOG file. Get this wrong → end-day reports 0/3 every evening. |
| 3 | **`## End of Day Review` heading unchanged** in `vault/daily/{DATE}.md` | start-day Step 9 (placeholder) | Hermes end-day hardcoded `re.search(r'## End of Day Review\n(.*?)(?=\n## \|\Z)')` | HIGH. Rename = empty EOD narrative on Hermes. Any rename requires editing that regex AND deploying both Hermes copies atomically. |
| 4 | **`state/priorities.yaml` top-level keys additive-only** | end-day Step 8c | start-day Steps 1b/1d (suppression, awaiting) | HIGH. Keep `carry_forward`, `awaiting`, `dormant_snooze`, `back_burner`, `last_updated`. Add keys, never rename. New `DelegationAsk` state goes in a SEPARATE file (`state/delegation_asks.yaml` or `.context/preview/`), not inside priorities.yaml. |
| 5 | **`logs/_telemetry.jsonl` append-only, existing fields frozen** | both skills via `scripts/telemetry.sh` | weekly-review, A/B | LOW. New fields OK; never rename/remove `ts, skill, run_id, duration_ms, status, mode, sources_ok, top3_scores, …`. |
| 6 | **`action_id` format `{skill}:{target}:{date}:{8hash}`** | any writing skill | start-day Step 8b drain, end-day idempotency | LOW. Format frozen so re-runs no-op. |
| 7 | **Shadow artifacts ONLY under `.context/preview/`** | start-day shadow renders | start-day Step 1b pending-write scan (top-level only) | MEDIUM. Never write shadow JSON to `.context/*.json` top-level or every future run flags it as a pending write. |
| 8 | **Both skill copies edited together** | — | Hermes runtime vs Claude Code runtime | HIGH. `~/.hermes/skills/coo-twin/{start-day,end-day}/SKILL.md` and `.claude/skills/{start-day,end-day}/SKILL.md` diverge by ~170 lines already. Every behavior edit touches BOTH, via `scripts/deploy_hermes_skills.sh`. `~/.hermes/` is outside git — see TASKS guardrail. |

## The gate that enforces this
**NO live skill edit (Phase C / Phase 2) until `tests/test_render_parse_roundtrip.py` proves
`extract_checked_source_actions` returns an IDENTICAL action set on an old-format note and a
new-format (mixed) note.** That E2E roundtrip is the contract-preservation proof, not a nice-to-have.

## Why the lean path is safe
A shadow-mode `SKILL.md` change that **only appends a new section BELOW the untouched existing
Top 3 / Actionable Items / End of Day Review sections** preserves contracts 1–4 by construction —
it changes nothing the parsers read. That is why Phase 1 ships as a doc change, not an engine.
