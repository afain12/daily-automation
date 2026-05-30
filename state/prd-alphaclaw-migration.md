# PRD — COO Twin Migration to alphaclaw on Render

**Author:** Aaron Fainshtein (drafted by Claude)
**Date:** 2026-05-12
**Status:** Draft v0.3 — surgical fixes for v0.2 doc-integrity bugs (changelog in §16; v0.2→v0.3 deltas in §17)
**Owner:** Aaron (sole user, sole operator)
**Related docs:**
- `CLAUDE.md` (current system architecture)
- `~/.gstack/projects/daily-automation/aaron-master-design-20260414-103924.md` (original design)
- `state/research-integration-plan.md` (deferred /research skill stack)
- Memory: `project_routing_redesign_pending.md` (BLOCKS migration start date — see §9.0)

---

## 0. Reader's Guide

This PRD describes migrating the **daily-automation** project (a personal Chief-of-Staff system built on Claude Code skills) from local-laptop execution to an always-on, multi-channel agent deployed on Render via the `garrytan/alphaclaw` harness, with `garrytan/gbrain` as the knowledge layer and a private GitHub repo as the agent's version-controlled workspace.

**v0.2 incorporates 7 blocker-level fixes from codex review:**
1. **Instant-inbox + deferred-routing split** (resolves async latency vs. 30s capture threshold)
2. **Single repo, not split** (resolves §6/§8 contradiction in v0.1)
3. **Migration day 0 ≥ 2026-05-20** OR restart 14-day routing-redesign dataset (resolves contamination of in-flight evidence collection)
4. **Hard cost circuit breakers** (per-run, daily, monthly caps that disable cron, not just alerts)
5. **gbrain retrieval eval gate** (pass before promoting to load-bearing)
6. **8GB load profile dry-run before Phase 1** (auto-upsize on observed OOM)
7. **Undo-payload protocol for every external write** (rollback for Notion/Calendar/Tasks isn't theater)

Plus minor fixes: `gws` CLI → direct Google REST migration documented, ~~voice capture pulled into MVP~~ (REMOVED 2026-05-12), timeline recalibrated to **8–11 weeks calendar** (was: 3–4 weeks in v0.1).

Sections marked **[ASSUMPTION]** are working hypotheses pending Aaron's confirmation. **[TBD]** marks genuine open questions.

---

## 1. Executive Summary

### 1.1 Problem Statement

Unchanged from v0.1. Current daily-automation delivers value but is constrained by:

1. **Synchronous-only execution** tied to a single Windows laptop.
2. **Single surface** — no phone-first capture for in-clinic / on-the-go moments where bypass rate is highest.
3. **No watchdog / observability** — silent failures discovered hours later.

### 1.2 Proposed Solution

Deploy `alphaclaw` to Render as a 24/7 hosted personal agent. Treat the existing daily-automation repo as the agent's GitHub-backed workspace.

**Key v0.2 architectural change: capture and routing are decoupled.** Aaron sends ≤1-line messages or forwarded URLs to Telegram (text-only — no voice); the agent acknowledges in ≤5 seconds with a queue ID and a one-tap "skip routing" escape. **Routing proposals arrive asynchronously** (2–10 min later). This solves the latency contradiction in v0.1 where the 30s capture threshold was incompatible with full proposal review.

`gbrain` is the **candidate primary** searchable memory layer — promoted to primary **only on retrieval eval pass** (§7.6); falls back to read-optional with grep-based log scan if eval fails. Notion remains business system-of-record; Google Tasks remains capture; Obsidian vault remains the human-edited reflection surface (with gbrain mirror once promoted).

### 1.3 Success Criteria (measurable, 90 days post-migration)

| KPI | Target | Measurement |
|---|---|---|
| Skill availability uptime | ≥ 99% of scheduled cron firings complete | alphaclaw Watchdog + SQLite event store |
| Daily briefing delivery latency | ≤ 5 min from cron fire to Telegram delivery | Cron timestamp vs Telegram message timestamp |
| **NEW: Capture-to-instant-ack latency** | **P50 ≤ 5s, P95 ≤ 10s** | **Telegram message timestamp diff** |
| Capture-to-routed-and-approved latency | P50 ≤ 5 min, P95 ≤ 20 min | Telegram timestamp diff (Aaron's response is in the loop) |
| **NEW: Capture bypass rate** | **≤ 10% of meetings/clinic visits skip the system** | **Weekly retro count vs Calendar event count** |
| Manual-laptop dependency | ≤ 1 skill run/week requires laptop | Local Claude Code session count |
| Routing accuracy | ≥ 95% of department assignments correct | Weekly retro: correction count in /end-day |
| Cost ceiling (enforced, not observed) | ≤ $150/month total | Hard circuit breaker, §8.9 |
| **NEW: External-write reversibility** | **100% of agent-initiated writes have an undo payload** | **`.context/applied/` audit + undo log** |

**Non-target:** Hands-free fully autonomous. Trust gate stays. Only the *surface* changes from terminal to Telegram.

---

## 2. Users & Personas

Unchanged from v0.1. Primary: Operator Aaron. Single-tenant, single-user. Latency-sensitive (>30s capture friction = bypass).

---

## 3. User Stories & Acceptance Criteria

### Story 3.1 — Morning briefing arrives without action

Unchanged from v0.1. Briefing posts to Telegram by 7:05am ET Mon–Fri, department-grouped, graceful degradation per data source.

### Story 3.2 — Meeting capture from phone — **REDESIGNED in v0.2**

**As** Aaron, **I want** to fire-and-forget a meeting capture in ≤5 seconds **so that** the system never costs me more time than capturing in my head would.

This is the load-bearing UX of the entire migration. v0.1's version (90s synchronous proposal) violated Aaron's observed 30s threshold. v0.2 splits the flow:

#### Phase A — Instant inbox (≤5s, no review)

**Acceptance Criteria:**
- Aaron sends to Telegram: a Granola URL or pasted notes (text only — no voice, no photos in MVP).
- Agent replies within 5 seconds: `📥 Queued #q-447 — routing in progress. Reply "skip 447" to drop.`
- Payload lands in `inbox/q-NNN.json` in workspace, durable. Aaron can stop here and the day continues.
- If Aaron sends 10 captures in a row across 10 minutes, all 10 get acks within 5s each. No throttling.

#### Phase B — Deferred routing (2–10 min, async approval)

**Acceptance Criteria:**
- Within 10 min of queueing, agent posts proposal: N Notion tasks, M Obsidian paths, K Calendar events.
- Proposal includes the original queue ID and a one-tap menu: `[Approve all] [Approve 1,3] [Skip] [Edit]`.
- If Aaron doesn't respond within 6 hours, proposal expires and payload is preserved under `inbox/expired/`. Telegram message edits to `⏰ Expired — payload preserved at inbox/expired/q-447.json`.
- Workspace-wide Notion search runs BEFORE declaring sync gap (existing `feedback_granola_routing.md` rule).
- On approval, writes execute, undo payload writes to `.context/undo/`, audit moves to `.context/applied/`.

#### Phase C — Manual fallback always available

**Acceptance Criteria:**
- `inbox/` directory is human-readable JSON. Aaron can edit, batch-route, or drop items manually.
- Local Claude Code on laptop can drain the inbox via existing `/capture-meeting` skill (no behavioral fork — same code path).

### Story 3.3 — Day-close retro

Unchanged from v0.1. Cron 00:00 UTC. Honest "real movement off Top 3" per `feedback_top3_vs_actual.md`. Writes `state/priorities.yaml`.

### Story 3.4 — Self-healing watchdog

Unchanged from v0.1.

### Story 3.5 — Audit & rollback — **STRENGTHENED in v0.2**

**As** Aaron, **I want** every external write to be individually reversible **so that** a misroute is recoverable in under 5 minutes without manual Notion archaeology.

**Acceptance Criteria:**
- Every Notion PATCH, Calendar event creation, Tasks insert generates a paired **undo payload** at `.context/undo/<write-id>.json`.
- Undo payloads contain: write target ID, original state (if PATCH/update), inverse operation (DELETE for inserts, restore-from-snapshot for updates).
- `/undo <write-id>` Telegram command executes the inverse.
- `/undo last` reverses the most recent agent write.
- `/undo last 5` reverses the last 5 writes in reverse order.
- Notion's own version history is the secondary safety net; undo payloads are primary because Calendar and Tasks have no useful version history.
- Workspace git rollback is the tertiary safety net for state/config files only — does NOT touch external systems.

### Story 3.6 — Weekly review

Unchanged from v0.1. Gated on 2+ weeks of post-migration logs.

### Story 3.7 — **REMOVED in v0.4-draft** — Voice capture

**Decision (2026-05-12):** Voice capture dropped entirely. Aaron chose type-only after the /autoplan review surfaced that voice required Whisper as a mandatory dependency (Claude Opus 4.7 does NOT support audio input). Phone-first typing into Telegram is the only capture surface.

**Implications cascading from this decision:**
- No Whisper API dependency.
- No voice transcription budget line item.
- No transcription confidence-threshold review path.
- The "in-clinic hands-free" use case is **not addressed by this system**. Aaron captures by typing on phone in the moment, or by reconstruction post-hoc.
- **This sharpens the MVE question (§9.-1):** the entire phone-first capture premise now stands or falls on whether Aaron actually types into Telegram on his phone vs. using existing alternatives (Notes app, Notion mobile). The MVE measures exactly this.

---

## 4. Non-Goals

Updated from v0.1:

1. No skill *behavioral* rewrites. Skills get a porting pass (gws CLI → REST, AskUserQuestion → Telegram approval), not new logic. Existing routing rules, dept tagging, trust gate semantics are preserved bit-for-bit.
2. No multi-provider routing. Anthropic only.
3. No iMessage/WhatsApp/Slack in MVP. Telegram only.
4. No public API.
5. No multi-user features.
6. No /weekly-review until 2+ weeks of post-migration logs exist.
7. No automatic Notion writes without async approval.
8. No migration of OneDrive-mirrored business folders into workspace repo — they stay on OneDrive + get gbrain-ingested.
9. No retirement of local Claude Code on laptop — permanent redundant surface.
10. **NEW: No Render IP allowlist relaxation.** SETUP_PASSWORD alone is insufficient for write capability (see §8.5).
11. **NEW (v0.4): No voice capture.** Type-only Telegram input. Dropped after Whisper-mandatory finding + Aaron's preference (2026-05-12).

---

## 5. Current State

Unchanged from v0.1. See v0.1 §5 — still accurate, including known brittleness (laptop-bound, no watchdog, silent OAuth failures, routing-redesign in progress).

**v0.2 amendment:** §5.3 "gbrain status" is now blocking — see §9.0 prerequisite gates.

---

## 6. Target Architecture

### 6.1 High-level diagram — **CORRECTED in v0.2**

The v0.1 diagram showed `.claude/skills/` inside the workspace path, contradicting §8.2's claim of repo split. v0.2 resolves: **single repo, single source of truth**. Code + state + logs + workspace are all one repo.

```
                              ┌──────────────────────────────────────┐
                              │     Render — Standard 16GB (revised)  │
                              │                                       │
                              │   ┌─────────────────────────────┐    │
                              │   │  alphaclaw (Node 24)         │    │
                              │   │  ├─ Setup UI (password+IP)   │    │
                              │   │  ├─ Watchdog                 │    │
                              │   │  ├─ Webhook handler          │    │
                              │   │  ├─ Cost circuit breaker     │    │
                              │   │  └─ Spawns:                   │    │
                              │   │     OpenClaw Gateway          │    │
                              │   │     127.0.0.1:18789           │    │
                              │   │     ├─ Skills runner          │    │
                              │   │     ├─ Inbox processor (NEW)  │    │
                              │   │     ├─ Channel: Telegram      │    │
                              │   │     └─ Cron + catch-up replay │    │
                              │   └─────────────────────────────┘    │
                              │                                       │
                              │   ALPHACLAW_ROOT_DIR/                 │
                              │   └─ workspace/   ← coo-twin repo    │
                              │      ├─ .claude/skills/               │
                              │      ├─ AGENTS.md                     │
                              │      ├─ TOOLS.md                      │
                              │      ├─ config/sources.yaml           │
                              │      ├─ state/                        │
                              │      ├─ logs/                         │
                              │      ├─ inbox/        (NEW — durable) │
                              │      ├─ inbox/expired/                │
                              │      ├─ .context/applied/             │
                              │      └─ .context/undo/ (NEW)          │
                              │   .env (secrets, not in repo)         │
                              │   sqlite.db (events + cron + costs)   │
                              └──────────┬─────────────────────┬──────┘
                                         │ hourly sync         │ outbound
                                         ▼                     ▼
                            ┌────────────────────┐  ┌──────────────────────┐
                            │ GitHub (private)    │  │ - Notion REST        │
                            │ afain1/coo-twin     │  │ - Google REST        │
                            │ (single repo)       │  │   (NOT gws CLI)      │
                            └────────────────────┘  │ - gbrain MCP         │
                                                    │ - Anthropic API      │
                                                    │ - Granola URL fetch  │
                                                    └──────────────────────┘
                                         ▲
                                         │ chat (text only)
                                         ▼
                                ┌────────────────────┐
                                │ Telegram bot       │
                                │ @aaron_coo_twin    │
                                │ user-ID locked     │
                                └────────────────────┘
```

### 6.2 Component responsibilities

Unchanged from v0.1, plus:

| Component | Owns (additions) |
|---|---|
| **alphaclaw** | Cost circuit breaker, IP allowlist enforcement, catch-up replay scheduler |
| **OpenClaw Gateway** | Inbox queue processor (FIFO with priority for time-sensitive skills) |
| **Workspace repo (single)** | All code, config, state, logs, inbox, undo payloads, audit trail. One source of truth. |

### 6.3 Data flow — **REDESIGNED for instant-ack + deferred-routing**

```
INSTANT INBOX (≤5s SLA, fire-and-forget)
────────────────────────────────────────
Aaron → Telegram: "<URL | text>"
  → alphaclaw webhook receives
  → minimal validation (size, source)
  → write inbox/q-NNN.json (durable)
  → reply "📥 Queued #q-NNN — routing in progress"
  → DONE for Aaron's foreground attention


ASYNC ROUTING (2–10 min, in-loop approval)
───────────────────────────────────────────
Inbox processor (every 60s OR triggered by new inbox entry)
  → pick oldest q-NNN.json
  → invoke /capture-meeting skill against payload
  → skill produces draft writes → .context/<run-id>.json
  → skill posts Telegram proposal w/ menu
  → wait for Aaron's reply (max 6h before expire)
  → on approve: execute writes, generate undo payloads,
                move .context/<run-id>.json to .context/applied/
                write to .context/undo/<write-id>.json per write
  → on skip: archive inbox entry, no writes
  → on expire: move to inbox/expired/


UNDO (operator-initiated)
─────────────────────────
Aaron → Telegram: "/undo q-447" or "/undo last"
  → lookup .context/undo/<write-id>.json
  → execute inverse operation
  → confirm in Telegram + move undo file to .context/undo/applied/


CRON SKILLS (start-day, end-day, weekly-review)
────────────────────────────────────────────────
Same flow but triggered by alphaclaw cron, not inbox.
Briefings are read-only → post to Telegram directly.
EOD prompts use the same Phase A inbox semantics for
Aaron's unplanned-work responses.
```

The key invariant: **Phase A (instant inbox) is ALWAYS available regardless of model/Notion/Calendar availability.** If everything downstream is broken, captures still durably land.

---

## 7. AI System Requirements

### 7.1 Model & runtime

- Primary: Claude Opus 4.7 (1M context).
- Fallback: Sonnet 4.6 for cron-fired skills (cost optimization).
- **Prompt caching MUST be enabled** for stable system prompts.
- Per-skill-invocation budget: 200k tokens warm; >200k triggers review.
- **NEW: Hard per-run cost cap** — abort skill execution at $5 single-invocation spend (configurable). See §8.9.

### 7.2 Tool requirements

| Tool | Today | v0.2 target |
|---|---|---|
| Notion REST | ✓ | ✓ (unchanged) |
| Google Calendar | `gws calendar` CLI | **Direct Google Calendar REST API** (gws unavailable in Render container) |
| Google Tasks | `gws tasks` CLI | **Direct Google Tasks REST API** (same reason) |
| gbrain MCP | Loaded | **Populated + eval-gated per §7.6** |
| Telegram Bot API | N/A | New (OpenClaw native) |
| Granola URL fetch | N/A | New — assume HTML scrape, monitor for API surface |
| ~~Voice transcription~~ | ~~N/A~~ | **REMOVED — no voice in MVP per Aaron's 2026-05-12 decision.** |

### 7.3 Skills inventory & migration status

| Skill | Today | MVP target | Porting risk |
|---|---|---|---|
| `/start-day` | Active (terminal) | Cron 11:00 UTC → Telegram | Low (mostly reads) — gws→REST swap is the only behavioral change |
| `/capture-meeting` | Active (terminal) | Inbox-triggered async approval | Medium — splits into Phase A + Phase B handlers |
| `/end-day` | Active (terminal) | Cron 00:00 UTC + Telegram inbox prompts | Medium — interactive prompt becomes inbox round-trip |
| `/weekly-review` | Planned | Cron Sun 22:00 UTC → PR | Low |

**Porting work breakdown (per codex #13 challenge):**
- `gws calendar` → Google Calendar REST: ~150 LOC per skill
- `gws tasks` → Google Tasks REST: ~80 LOC per skill
- AskUserQuestion → inbox/proposal/approval: ~100 LOC shared library (write once)
- Total: ~1,000 LOC of porting across 3 skills. Not trivial. Estimated 3–4 days focused work.

### 7.4 Evaluation strategy

Updated from v0.1:

| Skill | Eval method | Pass threshold |
|---|---|---|
| `/start-day` | 5 weekdays of parallel local-laptop + Render runs; diff briefing content | ≥ 95% same items surfaced; 0 false omissions of overdue tasks |
| `/capture-meeting` | Replay against 20 historical Granola meetings (10 known-good ground truth + 10 edge cases including topic-page appends) | ≥ 90% routing accuracy; 100% no false-sync-gap; ≥ 95% department correct |
| `/end-day` | 7 consecutive days of parallel runs | Identical carry-forward set 7/7 |
| Phase A instant-ack | 50 synthetic captures across burst patterns | P95 ≤ 10s, P50 ≤ 5s |
| Async approval flow | 20 test captures with realistic Aaron-response timing | P95 ≤ 20min total, error rate ≤ 5% |
| Trust gate enforcement | 5 synthetic unauthorized PATCH attempts (wrong user ID, expired token, replay) | 0 successes |
| **NEW: Undo correctness** | 10 random recent writes per skill | 100% successful inverse; 0 corruption |

### 7.5 AGENTS.md bootstrap

Unchanged from v0.1 §7.5. **Plus added rules:**

```
8. NEVER write without a corresponding undo payload. If you cannot
   generate an inverse operation for a write, REFUSE the write and
   surface the issue in Telegram.
9. Inbox is sacred. Phase A acks MUST happen in ≤5s. Skip Notion
   search, gbrain lookup, and any other I/O. Just queue and ack.
10. Per-run cost cap: abort if accumulated token cost in a single
    skill invocation exceeds $5 (configurable in Envars).
```

### 7.6 **NEW: gbrain readiness gate**

Per codex #6, gbrain promotion to load-bearing requires passing a fixed retrieval eval:

**Eval set construction (Phase 0 work, ~1 day):**
- 30 retrieval queries representing real /weekly-review and /capture-meeting cross-reference needs.
- Examples: "what did I decide about Beacon providers last month?", "which clinics did I meet about HEDIS in April?", "find all decisions about Cardio Pro postponement".
- Each query has 1–3 known-correct documents/pages as ground truth.

**Pass threshold:**
- Recall@5 ≥ 0.85 (correct doc in top 5 results for 85%+ of queries).
- Latency P95 ≤ 2s per query.
- Index freshness: documents added in last 24h are searchable.

**Failure mode:**
- gbrain stays read-optional. /weekly-review reverts to grep-based log scan. Migration proceeds without gbrain as load-bearing.
- Reattempt eval monthly. Promote when passing.

### 7.7 **NEW: `gws` CLI replacement (porting work)**

Current skills depend on `gws` (Google Workspace CLI), which is a local binary on Aaron's laptop. Render containers don't have it.

**Migration plan:**
- Replace with direct Google Calendar API v3 + Google Tasks API v1 REST calls.
- OAuth2 refresh token stored in Render env vars; refresh handled by a shared `scripts/google-auth.sh` helper.
- New scripts: `scripts/calendar.sh` (replaces `gws calendar`), `scripts/tasks.sh` (replaces `gws tasks`).
- Local laptop continues using `gws` for backward compat — both code paths supported via env var `GOOGLE_INTEGRATION_MODE={gws|rest}`.

---

## 8. Technical Specifications

### 8.1 Hosting

- **Provider:** Render.
- **Plan: Standard 16GB ($25/mo) — revised from Hobby 8GB per codex #7.** 8GB was wishful; OpenClaw + browser tool + Opus + skill concurrency needs headroom. Start at 16GB; downsize only after 2 weeks of <50% memory utilization.
- **Region:** US-East.
- **Persistent disk:** 20GB.
- **Restart policy:** Auto-restart + alphaclaw watchdog.

### 8.2 Repository structure — **SIMPLIFIED in v0.2**

**Decision: single private repo `afain1/coo-twin`.** v0.1's split was internally inconsistent (per codex #4) and added coordination overhead for a single-user system.

```
afain1/coo-twin (private)
├── .claude/skills/
├── scripts/
│   ├── notion.sh
│   ├── calendar.sh        # NEW (replaces gws calendar)
│   ├── tasks.sh           # NEW (replaces gws tasks)
│   └── google-auth.sh     # NEW (OAuth refresh)
├── config/
│   ├── sources.yaml       # IDs as ${ENV_VAR} references
│   └── routing-rules.yaml
├── AGENTS.md
├── TOOLS.md
├── CLAUDE.md
├── README.md
├── render.yaml
├── state/
│   └── priorities.yaml
├── inbox/                 # NEW — durable Phase A queue
├── inbox/expired/
├── logs/                  # 90-day retention
├── .context/
│   ├── applied/           # audit trail of executed writes
│   └── undo/              # undo payloads (NEW)
└── vault/                 # daily/, meetings/, notes/, reviews/
                           # (NOT business-folder mirrors — those stay OneDrive)
```

**Alphaclaw hourly auto-commit conflict (codex #11):** Resolved by convention — Aaron edits the laptop's local clone, never the Render container's working copy directly. The Render workspace IS the authoritative copy; laptop pushes via PR for any manual changes. Alphaclaw commits to `agent/` branch hourly; Aaron's PRs go to `main`; weekly merge.

### 8.3 Secrets management

Unchanged from v0.1 §8.3.

### 8.4 Channel: Telegram bot

Unchanged from v0.1 §8.4. Text and URLs only — voice and photos out of MVP scope.

### 8.5 Access control — **STRENGTHENED in v0.2**

Per codex #2 and #3, single-factor SETUP_PASSWORD is insufficient for external-write capability. v0.2 layers defenses:

| Layer | What it gates | Implementation |
|---|---|---|
| 1. Render IP allowlist | Setup UI access | If Aaron has static home IP: narrow allowlist (home + phone tether). If not: ISP regional range. **If neither feasible: layer 1 removed; residual risk shifts to layers 2–6 and must be explicitly accepted in writing.** Decision required pre-Phase 1 (see G6 in §9.0). |
| 2. SETUP_PASSWORD | Setup UI auth | 32+ char random, password manager only |
| 3. Telegram user-ID lock | Message handler | AGENTS.md rule + alphaclaw config: only accept messages from `TELEGRAM_USER_ID=<aaron>`. Reject + log + alert all others. |
| 4. Scoped tokens | API surface | Notion integration with capability limits (only the 3 in-use databases shared, no workspace-wide write). Google OAuth minimum scopes (calendar.events + tasks). |
| 5. Per-run cost cap | Runaway protection | §8.9 |
| 6. Async approval | Every external write | §6.3 |

**Step-up auth (codex #2 recommendation) NOT adopted** because TOTP per approval would obliterate latency budget. The 6 layers above are the trade. If an incident proves them insufficient, revisit.

### 8.6 Cron schedule — **with catch-up replay**

Per codex #12, missed cron firings need defined catch-up semantics.

| Cron (UTC) | Local (ET) | Skill | Catch-up policy |
|---|---|---|---|
| `0 11 * * 1-5` | 7am Mon–Fri | `/start-day` | If missed and current time < 12:00 ET same day, run on resume. Else skip with Telegram alert. |
| `0 0 * * *` | 8pm daily | `/end-day` | If missed and current time < 06:00 UTC next day, run on resume. Else skip. |
| `0 22 * * 0` | 6pm Sun | `/weekly-review` | If missed, run within 24h on resume. |
| `*/15 * * * *` | every 15min | inbox processor | Process backlog FIFO on resume. |
| `0 * * * *` | hourly | workspace → GitHub commit | Skip; next hour catches up. |

Max staleness per skill is encoded; beyond that, skip + alert rather than fire late.

### 8.7 Observability

Same as v0.1 plus:

| Metric | Surface |
|---|---|
| Phase A ack latency P50/P95 | alphaclaw SQLite + weekly dashboard |
| Inbox depth + age | Setup UI → Inbox tab (custom) |
| Per-skill cost (last 24h, 7d, 30d) | alphaclaw Usage + circuit-breaker state |
| Undo invocations + outcomes | `.context/undo/applied/` count + weekly retro |
| Capture bypass rate (estimated) | /end-day asks; logged weekly |

### 8.8 **NEW: Undo payload protocol**

Every agent-initiated external write generates a paired undo payload BEFORE the write executes. If undo generation fails, the write is aborted.

**Undo payload format (`.context/undo/<write-id>.json`):**
```json
{
  "write_id": "w-20260512-1442-001",
  "system": "notion",
  "operation": "patch_blocks_children",
  "target": "block_id_xyz",
  "original_state": { ... full pre-write snapshot of mutated fields ... },
  "inverse_operation": {
    "type": "patch",
    "target": "block_id_xyz",
    "payload": { ... restore-original-state PATCH ... }
  },
  "created_at": "2026-05-12T14:42:13Z",
  "linked_inbox_id": "q-447",
  "linked_applied": ".context/applied/cap-20260512-1422.json"
}
```

**Per-system specifics:**
- **Notion:** Original-state snapshot of the page/block before PATCH. Inverse = restoring PATCH. New page creation → inverse = archive page.
- **Google Calendar:** Event creation → inverse = delete by event ID. Event update → inverse = restore prior event JSON.
- **Google Tasks:** Same pattern — insert → delete, update → restore.
- **gbrain:** put_page → revert_version (gbrain natively supports). Tag add → tag remove.

**Retention:** Undo payloads kept 30 days, then auto-archived to `.context/undo/archived/<year-month>/`. Beyond 30 days, restore requires manual ops.

**Limitations (honest):**
- If Aaron manually edits a Notion task between agent write and undo, the undo will overwrite his edit. Telegram surfaces a warning: `⚠️ Target modified since write; undo will overwrite manual edits. Confirm?`
- Calendar/Tasks have no native version history — undo is best-effort from snapshot only.

### 8.9 **NEW: Cost circuit breaker**

Per codex #8. Three layers, all enforced (not just alerted):

| Layer | Threshold | Action |
|---|---|---|
| Per-skill-invocation | $5 Anthropic token cost | Abort skill mid-run, log, alert Telegram |
| Per-day cumulative | $15 | Disable proposal generation + async writes + weekly-review. **Tier-0 preserved: Phase A inbox acks, daily briefings, and EOD prompts ALWAYS continue.** Captures queue durably; routing resumes at UTC midnight when breaker resets. |
| Per-month cumulative | $150 | Disable all writes and non-critical crons. **Tier-0 preserved: Phase A inbox acks + daily briefings continue (read-only mode).** Aaron must explicitly re-enable writes in Setup UI. |

**Tier-0 rationale:** Phase A inbox is the migration's load-bearing UX (Story 3.2). A breaker that disables capture defeats the purpose. Token cost of Tier-0 operations is bounded and predictable (~$0.01 per ack; ~$0.30 per briefing × 30/mo = $9/mo worst case). Tier-0 fits inside even the monthly cap with margin.

State persisted in alphaclaw SQLite. Reset at UTC midnight (daily) and 1st of month (monthly).

Implementation: tally token usage via Anthropic API response headers; convert to USD at posted rates; compare against breaker state.

**Anthropic console budget alert at $100/mo** is the secondary safety net (catches breaker bugs).

---

## 9. Migration Plan (Phased)

### 9.-1 **NEW (v0.4 candidate): Phase -1 — 1-week Minimum Viable Experiment (MVE)**

Per /autoplan cross-model consensus (Claude subagent + Codex both flagged), the load-bearing premise of this PRD — "phone-first capture is the bottleneck; async Telegram delivery cuts bypass rate" — is **stated but not measured**. Before committing to 8–11 weeks of infrastructure, run a 1-week MVE.

**MVE scope (1 evening of work + 7 days observation):**
- Windows Task Scheduler entry firing `/start-day` daily at 7am ET.
- 30-line PowerShell script pipes briefing output to Telegram via Bot API.
- A second Telegram thread: Aaron forwards Granola URLs / pastes notes → script appends to `inbox/q-NNN.json` in OneDrive-synced folder.
- Laptop drains the inbox via existing `/capture-meeting` on next Aaron-initiated session.
- NO alphaclaw, NO Render, NO gbrain, NO undo payloads, NO circuit breakers.

**Measurement (week-long bypass log):**
- Each day, Aaron logs in `logs/MVE-bypass.md`: meetings/clinic visits + whether captured + why-not-if-not.
- Compare week 1 vs current baseline (the 4 weeks of existing logs).

**Decision criteria post-MVE:**
- If bypass rate drops ≥30% AND Aaron reads briefing daily on phone → **full migration GREEN** (proceed to G1 gate).
- If bypass rate flat but briefings read → **scope reduction**: ship briefings-as-permanent + skip capture migration. Saves 6–8 weeks.
- If bypass rate flat AND briefings ignored → **migration KILLED**. The premise was wrong. Different problem to solve (probably post-hoc reconstruction support).

**Why this matters:** Both /autoplan voices (Claude subagent + Codex) independently concluded that the premise has never been measured. The current PRD optimizes a number that doesn't exist. The MVE costs 1 evening and yields a real data point before 8–11 weeks of work.

---

### 9.0 **NEW: Prerequisite gates (blocking — must pass before Phase 1)**

Per codex #5, #6, #10, the v0.1 timeline was wrong because it assumed parallel work. Real timeline gates are sequential.

| Gate | Owner | Estimated time | Blocks |
|---|---|---|---|
| **G1 — Routing-redesign data window complete** | Aaron's existing memory rule (`project_routing_redesign_pending.md`) | Migration day 0 must be ≥ 2026-05-20 (14 days post-pause-lift on 2026-05-06) | Phase 1 |
| G2 — gbrain initialized + populated + eval passing | Phase 0 work | 2–4 days | Phase 4 (skills referencing gbrain) |
| G3 — gws → REST porting completed locally + tested | Phase 0 work | 3–4 days | Phase 1 |
| G4 — 8GB vs 16GB load profile dry-run (1-day soak on Render) | Phase 1 prep | 1 day | Phase 2 cron enablement |
| G5 — Inbox/undo/circuit-breaker libraries written + unit-tested | Phase 0 work | **7–10 days** (revised from 3 days per /autoplan dual-voice — production-grade undo across Notion/Calendar/Tasks/gbrain with edge-case coverage and integration tests is 2–3x more work than initially scoped) | Phase 4 |
| **G6 — Network posture decision (static IP / ISP-range / password-only)** | Aaron + Phase 1 prep | ½ day | Phase 1 |

**Earliest migration start date: 2026-05-20 (G1).** Even with parallelized G2–G5, realistic Phase 1 start is ~2026-05-24.

### 9.1 Phase 0 — Pre-flight & data hygiene (5–7 days)

- [ ] G2 work: Run `/setup-gbrain` locally. Ingest existing `vault/`. Build the 30-query eval set (§7.6). Run eval — must pass before promoting.
- [ ] G3 work: Port `gws calendar` and `gws tasks` to direct REST. Write `scripts/calendar.sh`, `scripts/tasks.sh`, `scripts/google-auth.sh`. Test locally with `GOOGLE_INTEGRATION_MODE=rest`. Confirm parity with `gws` outputs.
- [ ] G5 work: Build inbox processor library, undo payload generator, cost circuit-breaker. Unit tests for each.
- [ ] Resolve all open `.context/*.json` top-level files (CLAUDE.md hygiene).
- [ ] Document a known-good `/start-day` output for 2026-05-20 (post-migration eval baseline).
- [ ] Confirm G1 satisfied: routing-redesign 14-day window complete on or before 2026-05-20.

**Exit:** All G gates green. `.context/` empty at top-level. Eval baselines captured.

### 9.2 Phase 1 — Deploy alphaclaw + infrastructure (2 days)

- [ ] G4 work: 1-day load profile dry-run on Render with synthetic skill burst. Confirm 16GB plan stays <70% memory. If fail → 32GB.
- [ ] Generate SETUP_PASSWORD, configure Render IP allowlist.
- [ ] Create private `afain1/coo-twin` repo, push current state.
- [ ] Render → New Web Service → alphaclaw template. Set all env vars.
- [ ] First boot: confirm Watchdog green, Providers green, Browse tab shows workspace.
- [ ] Test no-op skill via Setup UI.

**Exit:** alphaclaw live, no writes attempted yet, all 6 access-control layers verified.

### 9.3 Phase 2 — Wire Telegram + first read-only skill (`/start-day`) (5 weekdays soak)

- [ ] Create Telegram bot. Pair to agent. Lock user ID.
- [ ] Configure cron `0 11 * * 1-5` for `/start-day`.
- [ ] Manual test fire. Verify briefing posts.
- [ ] 5 weekdays of automated runs with laptop running parallel.
- [ ] Diff briefings daily; pass threshold ≥ 95% match.

**Exit:** 5 consecutive clean weekdays.

### 9.4 Phase 3 — Inbox + Phase A instant-ack (3 days build + 3 days soak)

- [ ] Build inbox webhook handler.
- [ ] Build Phase A: receive → write → ack ≤5s.
- [ ] Test with 50 synthetic captures across burst patterns. P95 ≤ 10s.
- [ ] First live test: Aaron sends 5 real captures across a day. No routing yet — verify they queue durably.
- [ ] 3 days of inbox-only usage. No routing, no writes. Just confirm captures survive.

**Exit:** Phase A solid. 50/50 captures durable. Latency P95 met.

### 9.5 Phase 4 — Async routing for `/capture-meeting` (1 week build + 1 week soak)

- [ ] Build Phase B: inbox processor → proposal → approval → write → undo payload.
- [ ] Replay 20 historical Granola meetings against ground truth. ≥90% routing accuracy.
- [ ] First live live test: one real meeting end-to-end. Iterate on message format.
- [ ] 1 week of live usage with laptop fallback available.
- [ ] Measure: P50 capture-to-routed, bypass rate (compare to baseline).

**Exit:** 10 consecutive `/capture-meeting` runs no manual correction. Bypass rate ≤15% week-1 (target ≤10% by week 4).

### 9.6 Phase 5 — Port `/end-day` (3 days build + 1 week soak)

Unchanged from v0.1 §9.5.

### 9.7 Phase 6 — Stabilize + tune (2 weeks)

- [ ] Daily Watchdog check.
- [ ] Weekly cost/usage review.
- [ ] Bypass rate trending.
- [ ] AGENTS.md drift tuning.

### 9.8 Phase 7 — Build `/weekly-review` (1 day build + 2 Sundays soak)

Gated on Phase 6 stable + 2+ weeks of post-migration logs.

### 9.9 Total timeline (recalibrated)

| Phase | Build | Soak | Cumulative |
|---|---|---|---|
| 0 (prereqs) | 5–7d | — | week 1 |
| 1 (deploy) | 2d | — | week 2 |
| 2 (start-day) | 1d | 5 weekdays | week 3 |
| 3 (inbox) | 3d | 3d | week 4 |
| 4 (capture-meeting) | 7d | 7d | week 6 |
| 5 (end-day) | 3d | 7d | week 7 |
| 6 (stabilize) | — | 14d | week 9 |
| 7 (weekly-review) | 1d | 14d | week 11 |

**Realistic total: 8–11 weeks from 2026-05-20 start ≈ live by mid-July to early August 2026.** v0.1's 3–4 weeks was wrong.

---

## 10. Risks & Mitigations — **UPDATED for v0.2**

| # | Risk | L | I | Mitigation |
|---|---|---|---|---|
| R1 | Async routing latency exceeds 30s capture threshold | ~~High~~ **Low** | High | **RESOLVED in v0.2 via instant-ack split.** Phase A is ≤5s. Aaron's foreground capture cost is now lower than typing into Notion. |
| R2 | Render OOM at 8GB | ~~Medium~~ **Low** | Medium | **Default plan upgraded to 16GB ($25/mo).** G4 load profile validates pre-Phase-2. |
| R3 | Notion API rate limits | Low | Low | Existing patterns + exponential backoff at HTTP layer. |
| R4 | Google OAuth refresh expires silently | Medium | High | Hourly health-check ping; Telegram alert on 401. NEW: `scripts/google-auth.sh` exposes `--check` mode. |
| R5 | Telegram bot token leaked | Low | Critical | User-ID lock (layer 3 of §8.5). Bot can't approve writes from non-Aaron sender. |
| R6 | SETUP_PASSWORD brute-forced | Low | Critical | Render IP allowlist (layer 1) + 32-char password + rate limit. |
| R7 | Anthropic spending spike | ~~Medium~~ **Low** | High | **§8.9 hard circuit breaker enforces, doesn't just alert.** |
| R8 | Workspace repo accidentally public | Low | Critical | Private at creation; GitHub secret scanning enabled; CODEOWNERS = afain1. |
| R9 | Rollback theater for external writes | ~~High~~ **Low** | High | **§8.8 undo payload protocol resolves.** Every write reversible. |
| R10 | Granola format change | Medium | Medium | Graceful degradation + Telegram alert; manual paste path always works. |
| R11 | Routing accuracy drift | Medium | Medium | Weekly eval (5 random meetings). Alert if <90%. |
| R12 | OneDrive vault sync breaks on cloud | ~~Certain~~ **Mitigated** | Medium | OneDrive stays laptop-only. gbrain ingests from OneDrive via daily local script that pushes to workspace repo. Vault folders in coo-twin are agent-generated only. |
| R13 | alphaclaw upstream breaking change / governance instability | ~~Low~~ **Medium** (raised v0.6 — OpenClaw founder joined OpenAI Feb 2026; OpenClaw moved to independent foundation; market migrating to Hermes per §19 research) | Medium | Pin version in render.yaml; quarterly restore-to-local drill (codex #14). **NEW:** Hermes-on-Railway is now the post-MVE default (§19) which de-risks this entirely if G7 selects Hermes. |
| R14 | Render multi-hour outage | Low | Low | During outage, Aaron sends captures to Telegram normally; messages stack in Telegram's own server-side queue (~24h retention) and process on Render resume. For >24h outages, Aaron fires skills manually on laptop (permanent redundant surface, §4 #9). **Laptop-fallback webhook deferred to v1.1 — accepted residual risk.** |
| R15 | Aaron stops trusting after 1 misroute | Medium | Existential | "Why?" command per write; visible undo path; ≤95% routing accuracy gate per skill. |
| **R16 NEW** | Migration corrupts routing-redesign 14-day evidence | High (if started before 2026-05-20) | High | **G1 gate enforces 2026-05-20 minimum start.** |
| **R17 NEW** | gbrain ingest produces low retrieval quality | Medium | Medium | §7.6 eval gate — gbrain stays read-optional if eval fails. |
| **R18 NEW** | Cost circuit breaker false-trip kills critical cron | Low | Medium | Per-skill thresholds tuned; manual override in Setup UI; weekly review of breaker firings. |
| ~~R19~~ | ~~Voice transcription quality~~ | — | — | **REMOVED — no voice in MVP (2026-05-12 decision).** |
| **R20 NEW** | Auto-commit creates noisy git history | Low | Low | `agent/` branch isolation per §8.2; weekly merge to `main`. |

---

## 11. Budget — **REVISED in v0.2**

### 11.1 One-time setup

| Item | Cost |
|---|---|
| Domain (optional) | $0–15/yr |
| Aaron time | ~30 hrs across 8–11 weeks (was: 12 hrs, revised per realistic scope) |
| Claude API dev/eval | $50–100 |

### 11.2 Monthly recurring

| Line | Low / Expected / High |
|---|---|
| Render Standard 16GB | $25 / $25 / $25 |
| Render upsize to 32GB (if G4 fails) | $0 / $0 / $50 |
| Anthropic API | $30 / $80 / $150 (HARD CAP per §8.9) |
| gbrain hosting | $0 / $5 / $20 [TBD] |
| ~~Voice transcription (Whisper)~~ | ~~$0 / $5 / $15~~ — **REMOVED, no voice in MVP** |
| GitHub Pro (already paid) | $0 |
| Telegram | $0 |
| Domain | $0–1 |
| **Total** | **$55 / $115 / $260** |

**Hard ceiling: $150/mo (enforced by §8.9).** Monthly cumulative breaker kills writes at $150. Expected steady-state: ~$115/mo.

### 11.3 ROI sanity check

Migration costs ~$115/mo in exchange for: phone-first capture (eliminates ~50% of bypass), watchdog (eliminates ~1 incident/mo at ~1hr each), weekly-review (unlocks pattern detection). Conservative time savings: 4 hrs/mo. At Aaron's effective rate, ROI is positive even at the $150 cap.

---

## 12. Open Questions / TBDs

Updated from v0.1:

1. **[TBD-1] gbrain populated and passing eval?** Now gates Phase 4 via G2 (was floating).
2. **[TBD-2] Granola URL stability** — still unresolved. Assume scrape; monitor.
3. **[TBD-3] OneDrive vault** — RESOLVED: laptop syncer pushes vault to repo daily; gbrain mirror.
4. **[TBD-4] Voice in MVP** — RESOLVED 2026-05-12: REMOVED entirely. Type-only.
5. **[TBD-5] Render IP allowlist** — confirm Aaron has static home IP. If not, accept higher SETUP_PASSWORD reliance + IP-range allowlist for ISP.
6. **[TBD-6] Cron DST** — alphaclaw cron uses UTC. ET shifts twice/yr. Confirm cron expressions handle this (UTC doesn't shift, but ET-anchored intent does).
7. **[TBD-7] Phase abort criterion** — RESOLVED: if Phase 4 capture bypass rate >25% after 2 weeks, revert capture-meeting to laptop-only; treat as failed surface migration but keep cron skills.
8. **[TBD-8] Audit backup beyond GitHub** — quarterly snapshot of `.context/applied/` + `.context/undo/` to S3 or Backblaze? Open.
9. **[TBD-9] Multi-device Telegram** — confirmed per-user-ID is enough.
10. **[TBD-10] Decommission local laptop** — NEVER. Permanent redundant surface.
11. **[TBD-11 NEW]** — What's the laptop-fallback inbox handler scope when Render is down? Webhook from Telegram to laptop? Local cron polling Telegram updates? Open.
12. **[TBD-12]** — ~~Anthropic audio input vs Whisper~~ **RESOLVED: no voice in MVP (2026-05-12).**

---

## 13. Strategic Notes

Same as v0.1 §13. The trust gate is load-bearing; "eject anytime" is real; gbrain compounds with use.

---

## 14. Appendix

### 14.1 Glossary

Same as v0.1 plus:
- **Phase A / Phase B** — Instant inbox capture (Phase A, ≤5s) vs deferred routing approval (Phase B, 2–10min).
- **Undo payload** — Pre-computed inverse operation stored alongside every external write.
- **Circuit breaker** — Hard cost threshold that disables operations, not an alert.

### 14.2 References

Same as v0.1.

### 14.3 Decision log

| Date | Decision | Rationale |
|---|---|---|
| 2026-05-12 | Telegram single channel for MVP | Existing personal comms. |
| 2026-05-12 | Single repo (revised from split) | Codex #4 — split was inconsistent for single-user. |
| 2026-05-12 | 16GB Render plan default | Codex #7 — 8GB was wishful. |
| 2026-05-12 | Keep laptop permanently | Redundant surface. |
| 2026-05-12 | Anthropic-only | Skill tuning. |
| 2026-05-12 | gbrain primary memory (gated) | Codex #6 — eval gate before promotion. |
| 2026-05-12 | **Instant-ack + deferred-routing split** | Codex #1 — solves 30s threshold contradiction. |
| 2026-05-12 | **Hard cost circuit breaker** | Codex #8 — enforcement, not alerts. |
| 2026-05-12 | **Undo payload protocol** | Codex #9 — rollback for external writes. |
| 2026-05-12 | **Migration day 0 ≥ 2026-05-20** | Codex #10 — preserve routing-redesign evidence. |
| 2026-05-12 | **Voice capture in MVP** | Aaron's bypass concentrates in clinics. |
| 2026-05-12 | **6 access control layers, no TOTP** | Codex #2 — TOTP kills latency budget. |
| 2026-05-12 | **gws CLI → direct Google REST** | Render container lacks gws binary. |
| 2026-05-12 | **Timeline: 8–11 weeks, not 3–4** | Codex #5 — soak gates accumulate. |

---

## 15. **NEW** — Open implementation questions for Phase 0

Concrete items requiring decision before Phase 0 begins:

1. ~~**Voice transcription provider:**~~ **REMOVED — no voice in MVP (2026-05-12).**
2. **Inbox storage format:** Flat JSON files in `inbox/` (simple, git-trackable, slow at scale) vs SQLite (faster, harder to manually edit). Default: flat JSON. Single-user volume <100/day = JSON is fine.
3. **Undo retention:** 30 days hot + archive vs longer hot retention. Default: 30 hot, indefinite archived.
4. **Render IP allowlist scope:** Aaron's home static IP + phone tether ranges vs broader ISP range. Default: narrowest possible; expand on observed false-blocks.
5. **Laptop-fallback for Render outage:** Defer to v1.1 or build in MVP. Default: defer; document the outage runbook as "wait it out or fire skills manually on laptop."

---

## 16. **NEW** — Changelog v0.1 → v0.2

**Critical fixes (per /codex review 2026-05-12):**
- §3.2 capture-meeting story redesigned: instant-ack + deferred-routing (codex #1).
- §6.1 architecture diagram corrected — single repo, no split (codex #4).
- §8.2 repo structure consolidated (codex #4).
- §9.0 prerequisite gate G1 added: migration start date ≥ 2026-05-20 (codex #10).
- §8.8 undo payload protocol added (codex #9).
- §8.9 cost circuit breaker added (codex #8).
- §7.6 gbrain retrieval eval gate added (codex #6).
- §8.1 default plan upgraded to 16GB + G4 load profile gate added (codex #7).
- §9.9 timeline recalibrated to 8–11 weeks (codex #5).

**Supporting fixes:**
- §7.7 documented `gws` → REST porting requirement (Claude's addition; codex missed).
- Story 3.7 voice capture pulled into MVP (Claude's addition). **[REVERSED in v0.4 — see §18.8.]**
- §8.5 access control: explicit 6-layer model documented (codex #2 partially).
- §8.6 cron catch-up replay policy (codex #12).
- §7.3 skill rewrite scope explicit ~1,000 LOC porting (codex #13).
- R16–R20 added to risk register.

**Deferred (not v0.2):**
- TOTP step-up auth (codex #2 — kills latency budget; mitigated by 6-layer alternative).
- Multi-channel redundancy beyond laptop fallback (codex #3 — accepted single-channel risk for personal tool).

---

---

## 17. **NEW** — Changelog v0.2 → v0.3

Surgical fixes from /codex confirmation review on v0.2:

- **Timeline contradiction killed.** §0 Reader's Guide said "6–8 weeks"; §9.9 said "8–11 weeks". §0 corrected to 8–11.
- **Outage plan contradiction resolved.** R14 previously implied a built laptop-fallback webhook; §15 #5 said defer. Committed to defer; R14 rewritten to use Telegram's native server-side queue (~24h) as the actual outage buffer + manual laptop firing for longer outages.
- **Cost breaker carve-out.** v0.2's $15/day breaker disabled the inbox processor, which would have killed Phase A capture on busy days. v0.3 introduces **Tier-0**: Phase A inbox acks + daily briefings + EOD prompts always survive breaker firings. Only proposal generation and writes get gated.
- **IP allowlist conditional clarified.** v0.2 layer 1 was silently TBD on static IP availability. v0.3 makes it explicit: 3 modes (static IP / ISP-range / none) with documented residual-risk acceptance. New gate G6 forces decision pre-Phase 1.
- **gbrain "primary" framing softened.** §1.2 now says "candidate primary, promoted on eval pass" — matches §7.6 eval gate semantics instead of overstating readiness.

**Items intentionally NOT changed despite codex flagging:**
- Telegram SPOF (codex #3): accepted — laptop is the redundancy for single-user tool.
- Scope contradiction (codex #13): "no behavioral rewrites" is correct in spirit (routing logic preserved); flow rewiring is documented ~1,000 LOC porting work.
- Dependency concentration (codex #14): quarterly restore-to-laptop drill (R13) is the mitigation.

---

**END OF PRD v0.3 — /autoplan multi-discipline review completed (see §18)**

---

## 18. **NEW** — /autoplan Multi-Discipline Review Results (2026-05-12)

### 18.1 Pipeline executed

- **Phase 1 (CEO/Strategy):** Claude subagent + Codex via /autoplan
- **Phase 2 (Design):** SKIPPED — no UI scope (backend agent system)
- **Phase 3 (Eng):** Covered in Codex integration challenge
- **Phase 3.5 (DX):** Covered in Claude subagent multi-angle review

### 18.2 Dual-voice consensus

| Dimension | Claude subagent | Codex | Consensus |
|---|---|---|---|
| 1. Right problem? (phone-first capture as bottleneck) | DISAGREE — likely wrong | AGREE — premise unproven | **CONFIRMED: premise unmeasured** |
| 2. MVE alternative seriously evaluated? | NO | NO | **CONFIRMED: not evaluated** |
| 3. Voice transcription claim (Opus 4.7 audio) | LIKELY WRONG | **DENY — Whisper mandatory** | **CONFIRMED: claim was wrong, fixed in this revision** |
| 4. Soak gates assume operator attention? | YES — Aaron empirically overwhelmed | AGREE | **CONFIRMED: needs automated diff infra** |
| 5. Infra-before-routing-stability concern | CRITICAL | DISAGREE — parallelizable | DISAGREE — codex wins on sequencing |
| 6. G5 (3 days) underestimated? | YES — 7-10 days | AGREE | **CONFIRMED: revised to 7–10 days** |
| 7. alphaclaw pin/patch strategy | MISSING | Partially addressed | DISAGREE — codex wins |
| 8. AGENTS.md drift loop owner | MISSING | AGREE | **CONFIRMED: needs explicit owner + cadence** |

**6 of 8 dimensions: CONFIRMED gap.** This is high-signal — both models reached the same conclusion independently on the load-bearing concerns.

### 18.3 User Challenge surfaced (per /autoplan protocol)

> **Both models recommend the user's stated direction should change.**
>
> **You said:** Execute the 8–11 week migration to alphaclaw on Render, starting after the G1 routing-redesign window (2026-05-20).
>
> **Both models recommend:** Run a 1-week MVE (laptop cron + Telegram briefing bot, no alphaclaw/Render/gbrain) FIRST. Measure bypass rate. Then decide whether to proceed with full migration, ship briefings-only as the end state, or kill the migration.
>
> **Why:** The PRD's load-bearing premise ("phone-first capture is the bottleneck") has never been measured. You have anecdotes (`feedback_top3_vs_actual.md`) but no week-long timestamped log. The MVE costs 1 evening and produces a real data point.
>
> **What we might be missing:** You may already have private knowledge that bypass rate is high — anecdotally, the in-clinic moments are real. The models can't see that internal evidence.
>
> **If we're wrong, the cost is:** Delay 7 days before starting the real work. Worst case for following the recommendation is a 1-week timeline slip. Worst case for ignoring it is 8–11 weeks of infrastructure that solves the wrong problem.
>
> **The default is your original direction.** This challenge is surfaced; it is not auto-decided.

### 18.4 Taste decisions surfaced for final approval

1. **Async approval as the trust gate.** v0.3 commits to async-by-default. Claude subagent argues a solo operator might be better served by *synchronous* approval (laptop terminal session, done in 90s) because capture latency and approval latency are different problems. Decision: are we building Slack-for-myself when a faster terminal would do?
2. **gbrain as candidate primary vs permanent read-optional.** Eval set is constructed by the same person building the system = grading your own homework. Alternative: keep gbrain read-optional indefinitely; Notion + Obsidian grep is enough for <5,000 notes.
3. **Whisper budget impact.** Voice transcription was assumed Claude-native. Whisper API is now a mandatory line item (~$5–15/mo) plus added latency + separate auth/error surface. Worth Story 3.7 staying in MVP? Or defer voice to v1.1?

### 18.5 Cross-cutting themes (appearing in 2+ angles independently)

1. **Solo-operator soak-period unreality.** Every phase gate assumes a level of focused operator attention that existing logs contradict.
2. **Premise verification missing.** Phone-first bottleneck + audio support both stated as facts, both unverified. PRDs that ship with unverified load-bearing premises stall at Phase 4.
3. **Infrastructure on unstable foundations.** Routing logic still in flight; circuit breakers and undo payloads being designed around it.

### 18.6 Auto-decided items (per /autoplan 6 principles — no user review needed)

- Voice transcription claim corrected to Whisper (P1 completeness, P5 explicit).
- G5 estimate revised 3d → 7–10d (P5 explicit honesty).
- Phase -1 MVE added as candidate v0.4 fix (P2 boil-lakes — small scope, high info value).

### 18.7 Final verdict

**Cross-model consensus: RUN-MVE-FIRST**

Both /autoplan voices independently arrived at the same conclusion. The migration is structurally sound but premised on assumptions that should be measured for 1 week before the 8–11 week commitment. The recommended path:

1. **Decide on the User Challenge (§18.3) first.** Aaron's call — your private context on bypass rate may justify skipping the MVE.
2. **If MVE proceeds:** Phase -1 (§9.-1) is the next step. Defer all other Phase 0 work until MVE results land.
3. **If MVE is skipped:** Update §1.1 to be explicit that "phone-first as bottleneck" is an assumption Aaron is committing to without measurement, and proceed to G1 gate per v0.3 plan.

**This is the end of /autoplan. No further automated review cycles recommended — the marginal value of a 4th codex pass is below the friction cost. Next step is human decision.**

---

---

## 18.8 — Post-/autoplan decisions (v0.4 deltas, 2026-05-12)

After /autoplan completed, Aaron made two decisions that affect scope:

1. **Voice capture DROPPED entirely.** Type-only Telegram input. Story 3.7 removed; Whisper budget removed; R19 removed; voice transcription line in §7.2 removed; TBD-4 and TBD-12 resolved; §15 #1 nuked. **Side effect: the entire phone-first capture premise now rests on whether Aaron actually types into Telegram on phone vs using Apple Notes or Notion mobile. The MVE (§9.-1) tests exactly this.**
2. **Phase -1 MVE accepted as the next gate.** Both /autoplan voices recommended it; Aaron is going forward. Before any G1–G6 work or Render deployment, the 1-week MVE runs locally.

These changes constitute v0.4 in spirit. Full v0.4 changelog deferred — the surgical edits are inline above with strikethroughs marking the deltas from v0.3.

**Net effect on scope:** MVP shrinks. No voice means no Whisper, no transcription confidence logic, no audio storage, no audio API auth surface. Saves ~3–5 days of porting/integration work and ~$5–15/mo recurring. Reduces complexity of inbox payload (text only). Telegram bot config simpler (no audio MIME handling).

**Net effect on premise:** Sharpens it. The migration's value prop is now exclusively "I will type into Telegram on my phone instead of opening the laptop." The MVE proves or kills this in 1 week.

---

**END OF PRD v0.3 + /autoplan review + v0.4 voice-removal delta**

---

## 19. **REWRITTEN v0.6** — Host + Orchestrator (Hermes on Railway is the new post-MVE default)

Added 2026-05-13, rewritten 2026-05-13 after deep research. v0.5 framed Railway + Hermes as "research-pending alternatives, OpenClaw + Render is the default." Research flipped that conclusion. **v0.6 makes Hermes on Railway the post-MVE default** unless a focused porting spike (G7) finds a blocker.

This section still does NOT change the MVE (§9.-1). MVE is laptop-only and orchestrator-agnostic. Everything below applies post-MVE.

### 19.1 What the research found (citations in commit message)

Five findings drove the default flip:

**Finding 1 — gbrain officially supports Hermes as a first-class peer to OpenClaw.** Garry Tan's `garrytan/gbrain` README lists two installation paths side-by-side: AlphaClaw on Render (one-click, 8GB+ RAM) and Hermes Agent on Railway (one-click template `praveen-ks-2001/hermes-agent-template`). Same bootstrap method, same skill packs, same operational protocol. Aaron's original question — "does gbrain work better with Hermes?" — has a clean answer: **gbrain is platform-agnostic. Neither is privileged.**

**Finding 2 — Hermes ships native primitives that this PRD planned to build on alphaclaw.**

| PRD requirement | alphaclaw (PRD §) | Hermes native |
|---|---|---|
| Setup UI | §8.5, custom password+IP API | Built-in web dashboard, Keys tab, no terminal |
| Watchdog / auto-repair | §8.7, `openclaw doctor --fix --yes` | Self-healing native, restart-on-crash baked in |
| Cron + catch-up | §8.6, custom API + replay layer | `hermes cron create "0 11 * * 1-5" "<prompt>" --deliver telegram --name "start-day"` — natural language or cron syntax, one-shot supported |
| Telegram | §8.4, custom handler | Native gateway: `TELEGRAM_ALLOWED_USERS`, group allowlist, webhook or polling, proxy, slash command ACLs |
| MCP / gbrain | §7.2, OpenClaw runtime loads MCP | `hermes mcp <subcommand>` native, MCP server + client |
| Webhooks (Phase A ≤5s ack) | §6.3, custom in-process | Native webhook adapter with HMAC-SHA256, `deliver_only: true` returns without invoking LLM = the Phase A ≤5s ack pattern, free |
| Cost / token analytics | §8.9, we build the breaker | Built-in token/cost analytics dashboard |
| Hooks (circuit-breaker style) | not in alphaclaw | `~/.hermes/hooks/<name>/HOOK.yaml` listens for `agent:step` etc — circuit-breaker behavior without writing it |
| Persistence | Render persistent disk 20GB | Railway Volume mounted at `/opt/data` |

The only major PRD requirement neither ships natively is the §8.8 undo payload protocol. That's a build on either platform.

**Finding 3 — Cost delta is material.**

| Path | Monthly | Year 1 actual |
|---|---|---|
| Render Standard 16GB (PRD as drafted) | $25 | $300 |
| Hermes on Railway Hobby ($5–$10 typical per Railway template docs) | $5–$10 | $0 (Aaron pre-paid the Hobby year) |

Hermes is also provider-agnostic, so PRD §4 #2 ("Anthropic only") becomes a policy choice not a forced constraint. Useful for the $150/mo circuit breaker: fallback to a cheaper Sonnet/Gemini call keeps Tier-0 alive longer.

**Finding 4 — OpenClaw governance shifted against us in Q1 2026.** OpenClaw founder Peter Steinberger joined OpenAI in February 2026; OpenClaw moved to an independent foundation. Hermes (Nous Research) hit #1 on OpenRouter at 224B daily tokens. Industry coverage flags "50% Abandon OpenClaw for Hermes" and similar momentum signals. R13 reclassified Low → Medium.

**Finding 5 — Honest gaps that argue against switching.**
- Aaron's four skills are Claude Code markdown format. Hermes uses `~/.hermes/skills/` with its own lifecycle. Porting cost: ½–5 days, unmeasured.
- Hermes' self-improving-skill feature is a footgun for a trust-gated system (Story 3.5 needs deterministic skills for audit). Either disable self-improvement or accept a different audit model. See R24.
- The alphaclaw-based PRD design cost is already paid (3 review cycles, §1–§19). Switching means re-running review against new primitives.
- Hermes is younger (Feb 2026 launch) than alphaclaw. Less battle-tested at single-user scale specifically.

### 19.2 New default: Hermes on Railway Hobby (post-MVE)

**Unless G7 (§19.3) turns up a blocker, the post-MVE production default flips to:**
- Host: **Railway Hobby** (pre-paid through ~2027), with $10/mo overage cap
- Orchestrator: **Hermes Agent** (`nousresearch/hermes-agent`)
- Memory: gbrain (unchanged from §7.6 — eval gate still applies)
- Workspace: single repo `afain1/coo-twin` (unchanged)
- Telegram: native Hermes gateway (no custom handler needed)
- Cron: `hermes cron create ...` per skill (replaces alphaclaw cron API)
- Inbox / Phase A: Hermes webhook adapter with `deliver_only: true` for ≤5s ack
- Phase B routing: Hermes skill execution triggered from inbox processor
- Undo payloads: still custom, ~same LOC on either platform
- Cost circuit breaker: implemented via Hermes hooks (`agent:step` event) — likely less custom code than the alphaclaw path

**Conditional fallback to alphaclaw + Render Standard 16GB:** if G7 spike finds blocker. Documented below.

### 19.3 G7 — Porting spike (replaces prior research spike)

v0.5 G7 was "½–2 day research spike to figure out if Hermes is viable." v0.6 G7 is narrower and produces real evidence:

**Scope:**
1. Deploy Hermes on Railway via the one-click template (~30 min).
2. Port `/start-day` only — the simplest, mostly-read skill — to Hermes skill format.
3. Wire Telegram, Notion REST, Google REST. Run for 3 consecutive mornings against laptop baseline.
4. Compare briefings: ≥95% same items surfaced (same threshold as PRD §7.4 eval).
5. Measure: token cost per run, webhook ack latency, gbrain retrieval through Hermes MCP.

**Time budget:** 1–2 days focused work. **G7 passes** if Hermes-`/start-day` matches the laptop baseline at ≥95% and webhook ack stays under the §3.2 Phase A SLA (≤5s P95).

**G7 fails** → fall back to PRD v0.3 default (alphaclaw + Render Standard 16GB). Cost: 1–2 days lost, no other damage. Soak gates have not started.

**G7 cannot fire before MVE result is in (§9.-1).** If MVE kills migration, G7 is moot.

### 19.4 Risks (revised + added)

| # | Risk | L | I | Mitigation |
|---|---|---|---|---|
| R21 (revised) | Railway Hobby usage-credit overage during traffic spike | Low | Low | Hermes is lightweight (target ~$5–$10/mo per template docs). Hard $10/mo overage cap configured; alerts at $8. Burst absorption sufficient for single-user. |
| R22 (revised) | Hermes skill format port reveals hidden LOC | Medium | Medium | G7 porting spike tests the simplest skill first and produces real estimate. If `/start-day` port takes >2 days, fall back to alphaclaw default. |
| R23 (revised) | Switching orchestrator post-Phase-1 = restart of soak gates | Low (gated by G7) | High | G7 forces decision before Phase 1. Soak gates do not start until orchestrator is locked. |
| **R24 NEW** | Hermes self-improving-skill behavior breaks deterministic audit trail (Story 3.5) | Medium (default-on in Hermes) | High (trust gate is load-bearing) | Disable skill self-improvement during config; lock skill versions to git-committed states; explicitly accept "skills are deterministic, no runtime mutation" as a deployment invariant. Surface in AGENTS.md equivalent. |
| **R25 NEW** | Hermes is young (Feb 2026 GA) — undocumented edge cases at single-user soak scale | Medium | Low–Medium | 14-day Phase 2 soak is the same canary as alphaclaw path. Laptop redundant surface (§4 #9) covers Hermes-down outages identically. |

### 19.5 What this section does NOT change

- MVE (§9.-1) still next. Laptop + Telegram only. Orchestrator-agnostic.
- gbrain readiness gate G2 (§7.6) unchanged — same Recall@5 ≥ 0.85 threshold, same 30-query eval.
- Trust gate semantics (Story 3.5) unchanged. Undo payloads (§8.8) still required.
- Cost circuit breaker thresholds (§8.9) unchanged — implementation surface differs.
- Single repo `afain1/coo-twin` unchanged.
- gws→REST porting (§7.7, gate G3) still required regardless of host/orchestrator.
- Phase ordering 0→1→2→...→7 unchanged.

### 19.6 Sections superseded by v0.6 (read these with v0.6 lens)

- §6.1 deployment diagram — assumes alphaclaw on Render. If G7 passes, this diagram is replaced. Drafting deferred until G7 result.
- §6.2 component responsibilities — assumes alphaclaw owns Setup UI / Watchdog / etc. Hermes owns most of these natively.
- §6.3 data flow — Phase A/B flow structure stays; specific code paths change.
- §7.2 tool requirements — "Telegram Bot API (new)" → Hermes ships this. "Granola URL fetch (new)" → still required, separate concern.
- §7.5 AGENTS.md — Hermes uses an equivalent format under `~/.hermes/`. Port required as part of G7 if Hermes wins.
- §8.1 hosting — current text picks Render Standard. Becomes conditional: "Render Standard 16GB if G7 selects alphaclaw, else Railway Hobby with $10/mo overage cap."
- §9.0 prereq gates — G7 inserted between G1 (date) and G2–G6 (Phase 0 work). All Phase 0 work happens after G7 lock-in.
- §11.2 budget — recurring drops from $55/$115/$260 to roughly **$15/$25/$50** if Hermes wins G7. Anthropic budget unchanged ($30/$80/$150 hard cap).
- §10 R13 — already updated above.

A full §6/§7/§8 rewrite is deferred until after G7 outcome to avoid double-rewriting the PRD if G7 fails and we fall back to alphaclaw defaults.

### 19.7 Backlog option: Anthropic Managed Agents (added 2026-05-19, demoted same day)

Added after a `/managed-agents/multi-agent` + `/managed-agents/webhooks` doc fetch on 2026-05-19. A first draft proposed Managed Agents as a parallel third orchestrator with a G7-MA spike. The draft was **demoted to a backlog note the same day** after self-review against the logs and a `/codex review` independent pass:

- **MVE Phase -1 is still running.** Day 1 was 2026-05-19; verdict 2026-05-26. §9.-1 blocks Phase 0+ orchestrator work until verdict — no parallel-with-Hermes-G7 spike was startable.
- **The `*-team` experimental skills already validate the coordinator+worker pattern locally** via Claude Code subagents (`state/experiments/start-day-team.md`). Hosted Managed Agents proposes to migrate a pattern that hasn't passed local A/B promotion yet (5+ runs at `quality_delta == 0` + wall-time win).
- **The first-draft implementation artifacts were not API-valid.** Codex review flagged 9 P1 findings: wrong tool types (`bash_20250124`/`file_editor_20250124` are Messages API, not Managed Agents), underspecified `mcp_servers` (missing `type`/`url`/`mcp_toolset`/`vault_ids`), webhook dedup race that drops retries permanently, missing GET hydration on webhook events, and a 5xx-on-route-error loop that would auto-disable the endpoint. Findings recorded in `state/experiments/managed-agents/README.md`.

**Honest capability summary preserved for revival.** Managed Agents ships native coordinator+roster, native HMAC-signed webhooks with retry-stable `event.id`, and per-agent context isolation. It does **not** ship native cron, native Telegram gateway, or provider-agnostic fallback — those would still need to be built and would re-lock PRD §4 #2 that v0.6 explicitly unlocked.

**Revival conditions (all required):**
1. MVE Phase -1 passes (§9.-1).
2. `*-team` A/B reaches promotion decision (pass or reject).
3. `/sync-sweep` ships.
4. Hermes G7 (§19.3) runs **and fails**, OR a new audit-grade requirement emerges that Hermes can't satisfy.
5. Routing-redesign analysis is complete.

If all five hold, fix the P1 findings in `state/experiments/managed-agents/README.md` before any `POST /v1/agents` call.

**Decision matrix unchanged from v0.6.** Hermes-on-Railway remains the post-MVE default. alphaclaw on Render is the v0.3 fallback. Managed Agents is the **third** fallback, not a parallel option.

---

**END OF PRD v0.3 + /autoplan review + v0.4 voice-removal delta + v0.6 Hermes-on-Railway flip + v0.7 Managed-Agents demoted-to-backlog (2026-05-19)**
