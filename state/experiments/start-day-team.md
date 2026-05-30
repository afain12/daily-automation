# Experiment: /start-day-team (parallel fan-out)

**Started:** 2026-05-19
**Status:** scaffolded, no runs yet
**Owner:** Aaron + Claude
**Baseline:** `/start-day` (`.claude/skills/start-day/SKILL.md`)
**Variant:** `/start-day-team` (`.claude/skills/start-day-team/SKILL.md`)

## Hypothesis

Steps 2–5 of /start-day (Calendar pull, Notion 4-DB pull, Obsidian scan,
Google Tasks pull) are independent network/file I/O. Running them sequentially
costs roughly `sum(latencies)`. Running them as four Agent-tool workers in
one fan-out costs roughly `max(latencies) + coordinator overhead`.

Expected savings: 50–70% of total wall time on a typical morning, assuming
Notion is the long pole (4 DB queries + workspace search) and the others
finish well inside that envelope.

## What we measure

Per run, append one row to the log below:

```
date       | run_id              | total_ms | max_worker_ms | coord_overhead_ms | quality_delta | notes
```

- **total_ms** — coordinator wall time from Step 0 to Step 9 end.
- **max_worker_ms** — slowest worker's duration (the parallel floor).
- **coord_overhead_ms** — `total_ms - max_worker_ms`. Should stay small; if
  it grows, the coordinator is doing too much serial work and the
  architecture isn't paying off.
- **quality_delta** — manual eyeball score after the run, comparing this
  briefing against what /start-day would have produced:
  - `0` = same Top 3, same sections, same routing
  - `-1` = something missing or misclassified vs baseline
  - `+1` = somehow strictly better (unlikely — same logic)
- **notes** — anything notable: worker that skipped, surprising latency,
  trust-gate friction, etc.

## Exit criteria

- **Promote:** 5+ runs with `quality_delta == 0` AND median total_ms < 60% of
  a recent /start-day baseline. Then rename `start-day-team` → `start-day`
  and archive the sequential version under `.claude/skills/_archive/`.
- **Abandon:** any `quality_delta < 0` whose root cause isn't fixable in the
  team architecture (e.g., a step genuinely requires sequential context).
  Document the failure mode and revert.

## Baseline reference latencies

Before running the team variant, capture a few /start-day baseline durations
from `logs/_telemetry.jsonl` to compare against. (TODO on first run.)

## Run log

| date | run_id | total_ms | max_worker_ms | coord_overhead_ms | quality_delta | notes |
|------|--------|----------|---------------|-------------------|---------------|-------|
| 2026-05-19 13:46 | sdt-20260519-1346 | ~90000 (est) | ~75000 (notion) | ~15000 | 0 | First validation. All 4 workers parallel, all returned `status:ok`, JSON contracts honored. **3 prompt issues found + fixed same session:** (1) calendar keywords too literal — AHBD/LDX/Telcor/Gary biller/Visit Dr X all untagged; expanded `config/sources.yaml` + added fallback inference. (2) notion-worker dropped due dates as `""` instead of null/ISO — clarified prompt with example shape. (3) Activity Log empty; added 30-day sanity count. Trust gate skipped (afternoon validation run, not real morning). No telemetry row (didn't reach Step 10). Bonus: obsidian-worker's memory_meetings extraction was richer than baseline /start-day. |
| 2026-05-19 14:07 | sdt-20260519-1407 | ~80000 (est) | ~70000 (notion) | ~10000 | +1 | Fix-verification run. **All 3 fixes verified working:** (1) Calendar 12/12 tagged vs 1/12 before — keyword expansion + inference both fire. `tag_source` field clean. (2) Notion `due:null` consistently — revealed real finding that all 29 open Master Tasks have no Due date set (root cause of Lab starvation in scoring). (3) Silence-check returned `total_30d:1, most_recent_date:2026-05-14` — only 1 Activity Log entry in 30 days. Confirms `feedback_top3_vs_actual.md` failure mode at scale; validates /end-day-team braindump-extractor design. **2 new prompt issues found + fixed same session:** (A) CRM followup over-flagging (returned 7d items despite 14d threshold) — added strict threshold rule. (B) gtasks-worker incomplete enumeration (3/27 tasks) — added completeness requirement + `open_tasks_total` self-check field. quality_delta=+1 because Run #2 surfaced strictly more actionable signal than baseline /start-day would (silence-check + tag_source audit). |

## Known risks going in

1. **Worker fork overhead.** Spawning four agents has its own startup cost
   (model fork, system prompt load). If it's >5s × 4, the parallelism gain
   erodes. Watch the first few runs.
2. **Worker prompt drift.** Each worker prompt re-encodes a slice of
   /start-day's spec. If the baseline spec evolves (e.g., a new Notion DB),
   the team skill must be updated in lockstep or it'll silently fall behind.
   `.claude/skills/start-day-team/SKILL.md` calls out this dependency.
3. **Trust-gate UX.** The coordinator still owns the trust gate — workers
   never write. This is intentional. If a worker-side write ever feels
   tempting, that's the architecture telling us to keep it coordinator-side.
4. **Notion rate limiting.** Four DB queries from the notion-worker land
   serially inside that worker (it's one agent doing curl in sequence).
   Fan-out happens between worker types, not within. Acceptable for now.
