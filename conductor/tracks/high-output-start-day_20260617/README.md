# high-output-start-day — dispatch track

Reworks `/start-day` with High Output Management framing (Portfolio Pulse + 3 outputs,
delegation-counts-as-shipped, day-type, meetings-that-convert). Reviewed 4 lenses 2026-06-17.

## Dispatch reading order
1. **`CONTRACTS.md`** — must-not-break handshake with /end-day + Hermes. READ FIRST.
2. **`TASKS.md`** — the fixed, lean-first execution list. This is what the loop iterates.
3. **`spec.md`** — data/behavior contract for the engine (Phase 2).
4. **`review-gates.md`** — the spec-review → quality/code-review gate per task.
5. **`tests.md`** — test list. `context/` holds the 44KB overhaul plan + owner + Hermes-compat reviews.

## Run it
`/dispatch` → `/subagent-driven-development`, starting at **Phase 1 / T1** in TASKS.md.
Phase 1 ships a shadow doc change only (no engine) and exits on Aaron's keep/kill after 3 mornings.
Phase 2 (the typed engine) is DEFERRED — build only if Phase 1 proves out.

`plan.md` is the original Conductor plan, preserved for reference; **TASKS.md supersedes its ordering.**
