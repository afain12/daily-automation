# Manus v2 vs. Hermes PRD — Audit + Real-World Execution

**Date:** 2026-05-18
**Inputs:** `manus_suggestions_v_2_ops_agent_cleaned (1).md` (Downloads), `state/prd-alphaclaw-migration.md` v0.6, `logs/MVE-bypass.md`, memory `project_cowork_scheduling.md`.
**Status:** Audit complete. Execution plan is sequenced against the live MVE (day 0 = today) and the Cowork cron that is already firing.

---

## 0. Verdict in one paragraph

Manus v2 and the Hermes PRD are mostly **complementary, not competing**. The PRD is a *platform* doc (host, orchestrator, capture surface, trust gate, undo, circuit breaker). Manus v2 is a *dispatch-discipline* doc (audit-log format, cost attribution, operating modes, recipient whitelist, accession handling). The two collide in only one place — **outbound dispatch Gmail**, which Manus assumes is core and the PRD doesn't mention at all. That gap is real but **out of scope for the MVE** and the answer is "defer dispatch until after the MVE verdict, then merge Manus §3–§4 into Phase 4+ of the PRD." Below: line-by-line mapping, the dispatch gap, and a 2-week execution plan that respects the MVE gate.

---

## 1. Manus → PRD mapping (what's already covered, what to add, what to reject)

| Manus v2 recommendation | PRD coverage | Verdict |
|---|---|---|
| **Loguru structured JSON audit log** (§3.1) | PRD has `.context/applied/` + `logs/` but no library choice or schema. | **ADD.** Adopt Loguru + the Manus JSON schema verbatim. Land in Phase 0 (before Hermes/alphaclaw deploy). |
| **tokencost per-interaction cost tracking** (§3.2) | PRD §8.9 has tiered circuit breaker but no per-skill attribution. | **ADD.** tokencost is the *input* the circuit breaker needs — without it, the breaker is theater. Land in Phase 0. |
| **Bitwarden CLI first, Infisical later** (§3.3) | PRD uses `.secrets/*.env` + mirror to `settings.local.json`. | **AGREE with Manus.** Current `.secrets/` pattern is the "minimal locked-down secret approach." Defer Infisical until ≥5 secrets cross machines. Keep as-is. |
| **EZGmail prototype only; official Gmail API for production** (§3.4) | PRD doesn't mention outbound Gmail. | **DEFER (see §2 below).** Out of MVE scope. Revisit at Phase 4. |
| **APScheduler — defer unless Hermes is insufficient** (§3.5) | PRD §19.2 picks Hermes native cron. Today Cowork is the runner. | **AGREE.** Skip APScheduler. Cowork covers MVE; Hermes covers post-MVE. |
| **python-telegram-bot — defer** (§3.6) | PRD §19.2: Hermes native Telegram gateway. MVE uses Bot API directly via PowerShell. | **AGREE.** No third lib. |
| **Notion MCP — boring + append-only + 🤖 tag + action ID** (§3.7) | PRD has trust gate but no "🤖 tag every agent-created row" convention. | **ADOPT THE TAG.** Cheap, makes bulk rollback trivial alongside undo payloads. Add to AGENTS.md when Hermes/alphaclaw deploys. |
| **Accession numbers = sensitive identifier; LLM gets placeholder, local code injects ID** (§4.1) | PRD has no PHI/identifier handling. Lab dispatch isn't scoped. | **ADD when dispatch lands** (Phase 4+). Document the pattern now in `config/dispatch-rules.yaml` (placeholder file). |
| **Operating modes 0–4 (Observe / Draft / Approved / Trusted / Locked)** (§4.2) | PRD has implicit "draft-approve" default but no formal mode taxonomy. | **ADD.** Worth the 30 LOC. Default `MODE 1 — Draft Only` matches PRD's "async approval as trust gate." `MODE 4 — Locked` is the same as Manus's LOCK AGENT (§4.5). |
| **Idempotency `action_id` before send** (§4.3) | PRD §3.2 has `q-NNN` queue IDs for *inbox*; nothing for outbound. | **ADOPT for any future write.** Pattern: `{skill}:{target}:{date}:{hash(payload)}`. Cheap, prevents duplicate Notion rows even today. |
| **Recipient whitelist** (§4.4) | Not in PRD (no dispatch). | **DEFER** — only meaningful when outbound exists. |
| **LOCK AGENT emergency stop** (§4.5) | PRD §8.9 monthly breaker forces manual re-enable. Manus's command form is cleaner. | **ADD.** Implement as Telegram command + Hermes hook (or PowerShell flag during MVE). Tiny scope, high safety value. |
| **Skill priorities: supplies-order, courier-pickup, it-ticket** (§5) | PRD skills: start-day, capture-meeting, end-day, weekly-review. **Different universe.** | **HOLD.** Manus's skills are Lincoln Lab dispatch automation; PRD skills are COO Twin orchestration. Not either/or — the Manus skills become a *second skill pack* once dispatch is wired. |
| **Build philosophy: read → draft → log → approve → send narrowly → plan → optimize** (§9) | PRD §7.4 has similar earn-trust progression. | **AGREE — already aligned.** |

**Net:** 6 things to add (Loguru, tokencost, 🤖 tag, operating modes, action_id, LOCK AGENT), 3 to defer (Gmail wrapper, whitelist, accession pattern), 1 to reject (Infisical now), rest already aligned.

---

## 2. The dispatch gap (the one real divergence)

Manus assumes the agent's primary value is **outbound email** (supplies orders, courier pickup, IT tickets, AR nudges). The PRD assumes the agent's primary value is **inbound orchestration** (briefings, captures, routing across Notion/Calendar/Tasks).

These are different products. Aaron has to pick a priority order. Two honest framings:

1. **Inbound-first (current PRD).** Dispatch is Phase 4+. Manus §3–§4 sits as a design doc until then. Pro: MVE answers a question we already started measuring. Con: doesn't address the Lincoln Lab operational load Manus is targeting.
2. **Dispatch-first (Manus).** Pivot the MVE to test "I will text the agent to draft a supplies order at 5am from the car." Pro: higher leverage if it works (each dispatch saves 5–10 min). Con: throws away the existing MVE setup, adds Gmail OAuth + recipient whitelist before any baseline.

**Recommendation:** Stay inbound-first through MVE verdict (≤ 2026-05-25). If MVE returns BRIEFINGS-ONLY or KILL, **then** reconsider dispatch-first because the inbound premise died. If MVE returns PROCEED, fold Manus dispatch in at Phase 4 of the existing PRD plan.

---

## 3. Real-world execution plan — next 2 weeks

Anchored to today (2026-05-18, MVE day 0) and the fact that Cowork is already running `/start-day` (morning + 6:09pm) on the same repo.

### Week 1 — MVE measurement (no infra changes)

**Cowork is the MVE runner**, with phone-delivery via a **Notion mobile-briefing page** (mirrored each run; opened in the Notion mobile app). This deviates from PRD §9.-1, which assumed Windows Task Scheduler + Telegram. The deviation is fine for inbound-read measurement: Notion mobile covers "does Aaron read briefings on his phone." Telegram capture (outbound from phone → inbox) is *not* live in Week 1 unless Aaron completes BotFather setup; the capture-bypass metric will be partially blind until then.

**Revised plan (2026-05-18 evening):** Telegram bot wasn't live as of MVE start. 2026-05-18 becomes **Day 0 (setup, not measured)**; Day 1 shifts to 2026-05-19; verdict shifts to 2026-05-26.

| Day | Action | Owner | Source of truth |
|---|---|---|---|
| 2026-05-18 (Day 0, today) | Wire phone delivery. ✅ Notion mobile page `365a3158-59b4-8100-a1ae-c6a8ad53eec5` created. ✅ `/start-day` + `/end-day` skills updated with mirror step. ⏳ BotFather + `.secrets/telegram.env` (Aaron). ⏳ Confirm next scheduled Cowork run renders the mirror correctly (Aaron checks Notion mobile). | Claude + Aaron | `config/sources.yaml`, `scripts/README-MVE.md` |
| 2026-05-19 (Day 1) | First measured day. Fill `logs/MVE-bypass.md` Day 1 row after each meeting. Set 3 phone reminders. | Aaron | `logs/MVE-bypass.md` |
| 2026-05-19 → 05-25 | Daily: log meetings, briefing-read, briefing-useful. No code changes. If Telegram comes online mid-week, note the day it switched on. | Aaron | `logs/MVE-bypass.md` |
| 2026-05-26 | Fill in Week Summary. Verdict: PROCEED / BRIEFINGS-ONLY / KILL. | Aaron | `logs/MVE-bypass.md` Week Summary |

**Do NOT this week:**
- Do not deploy Hermes/alphaclaw. PRD §9.-1 says wait for MVE.
- Do not start the Manus dispatch work. Same gate.
- Do not edit routing logic — `project_routing_redesign_pending.md` blocks until 2026-05-20 minimum.

### Week 2 — Verdict-conditional

**If verdict = PROCEED** (bypass ↓ ≥30% AND briefings read daily):

| Day | Action |
|---|---|
| 2026-05-26 | Add `scripts/audit_log.py` with Loguru + Manus JSON schema (§3.1). Wire to existing `/start-day`, `/end-day` on local. Costs $0, no infra change. |
| 2026-05-27 | Add `scripts/cost_tracker.py` with tokencost. Append cost line to each log entry. |
| 2026-05-28 | Add operating-mode env var (`COO_MODE=draft`) + LOCK toggle via a Telegram command handler in the existing PowerShell capture script. |
| 2026-05-29 | G3 work: port `gws calendar` and `gws tasks` to direct REST. Required for *both* Hermes and alphaclaw. |
| 2026-05-30 | G7 spike: deploy Hermes on Railway via one-click template. Port `/start-day` only. (PRD §19.3.) |
| 2026-05-31 → 06-02 | 3-morning Hermes vs Cowork baseline diff. Pass = ≥95% match. |
| 2026-06-03 | G7 verdict → either commit to Hermes/Railway or fall back to alphaclaw/Render. Lock orchestrator. |

**If verdict = BRIEFINGS-ONLY** (briefings read, bypass flat):

| Day | Action |
|---|---|
| 2026-05-26 | Promote the Cowork morning+evening setup + Notion mobile mirror to permanent. Document in `CLAUDE.md`. |
| 2026-05-27 | Skip Hermes/Render entirely. Add Loguru + tokencost (still useful) to local skills. |
| 2026-05-28+ | Pivot to dispatch-first per Manus §5: scope `supplies-order.md` as the next skill. New 1-week MVE for dispatch. |

**If verdict = KILL** (briefings ignored, bypass flat):

| Day | Action |
|---|---|
| 2026-05-26 | Stop Cowork tasks. Archive PRD as "premise rejected." Update memory. |
| 2026-05-27+ | Reset and ask the harder question: "what *would* actually reduce the daily operating load?" Manus §1 framing ("simplicity is a safety feature") is the right lens for that re-scoping. |

---

## 4. Things to do today (revised 2026-05-18 evening — Day 0 wiring)

**Done (auto):**
1. ✅ `logs/MVE-bypass.md` re-sequenced: Day 0 = 2026-05-18 (setup), Day 1 = 2026-05-19, …, Day 7 = 2026-05-25, verdict = 2026-05-26.
2. ✅ Notion mobile-briefing page created (`365a3158-59b4-8100-a1ae-c6a8ad53eec5`), captured into `config/sources.yaml` as `mobile_briefing_page_id`.
3. ✅ `/start-day` skill gets a "mirror to Notion mobile page" step after writing the daily note.
4. ✅ `/end-day` skill gets the same mirror step at the end of Step 8.

**Pending (Aaron):**
5. Open the Notion mobile app on your phone. Find "📱 Daily Briefing — Mobile" under Command Center. Pin/star it. It'll populate at the next scheduled Cowork run (tomorrow morning).
6. **BotFather** (~10 min): create the bot, save `.secrets/telegram.env` per `scripts/README-MVE.md` §1-3.
7. **Smoke test Telegram** (~30 sec after step 6): `. .\.secrets\telegram.env; "MVE Day 0 smoke test" | .\scripts\mve-telegram-send.ps1`. Confirm DM arrives on phone.
8. **(Optional, post-BotFather)** Set up Windows Task Scheduler entry to fire a laptop-side morning send. See `scripts/README-MVE.md` §6. Cowork's Notion mirror is sufficient even without this — Telegram is the nicer-to-have.
9. Audit file + skill changes are still untracked. Tell Claude when to `git add`.

---

## 5. What was NOT decided here (deliberately)

- **Dispatch-first vs inbound-first pivot.** Defer to 2026-05-25 verdict.
- **Loguru vs OpenTelemetry.** Loguru chosen because Manus chose it and the schema is the load-bearing part, not the lib.
- **Gmail dispatch surface (separate Gmail account, OAuth scopes, label conventions).** Out of scope until Phase 4.
- **PHI / accession boundary review.** Needs compliance attorney input before Manus §4.1 ships. Note this in TBD-13 if PRD revs.
- **Whether to write Manus's dispatch skills into Hermes skill format or Claude Code markdown format.** Depends on G7 outcome.

---

## 6. Third reference: AnkitClassicVision/agent-automation-creator (AAC) + AgentTwin

Added 2026-05-18 at user's request. Repo: <https://github.com/AnkitClassicVision/agent-automation-creator>.

**What it is:** A *process-first design framework* for AI-augmented workflows — not a deployable agent, not a skill pack, not a runtime. v1.1 shipped 2026-05-14 (3 days old; 15 stars; 100% HTML+Markdown, no executable code). Ships with **AgentTwin**, an installable Claude Code skill that audits an agent design against a 57-item rubric and outputs a self-contained HTML wellness report (letter grades A–F across BOUNDED / GROUNDED / GATED / OBSERVED / GOVERNED).

**Overlap with the current build:**

| Capability | AAC has it? | We need it from elsewhere |
|---|---|---|
| Skill format (Claude Code SKILL.md) | ✓ exact match | — |
| Telegram, Notion, Calendar, Gmail integrations | ✗ | Hermes / our scripts |
| Cron / scheduling | ✗ | Cowork → Hermes |
| Audit log lib | ✗ (discipline only) | Manus §3.1 Loguru |
| Undo / rollback | ✗ | PRD §8.8 |
| Cost circuit breaker | ✗ | PRD §8.9 |

**Verdict: REFERENCE-ONLY, not adopted.** AgentTwin is a *pre-deploy governance audit tool*, not infra. The current build has already passed the "should we build this" gate (PRD exists, MVE running). AAC adds zero acceleration to the next 14 days. It becomes useful **after** G7 / orchestrator lock-in, as a pre-ship sign-off pass on the Hermes (or alphaclaw) deployment spec.

**Three things worth stealing now (cheap, high clarity):**

1. **The BOUNDED / GROUNDED / GATED / OBSERVED / GOVERNED taxonomy** — formalize these as section headers in a new `AGENTS.md` (Hermes-equivalent of CLAUDE.md). PRD §3.5 (gates), §8.8 (undo), §8.9 (breaker) all map cleanly. Names make the discipline legible to future-Aaron + future-Claude. *Estimated cost: 30 min when AGENTS.md is first authored, scheduled for G7 spike.*
2. **The 5-property card layout** from AgentTwin's HTML report (Stays in lane / Checks facts / Checks before doing / Nothing is hidden / Has a stop button) — borrow as a weekly digest format for `/end-day` retros or a future `/health` skill. *Estimated cost: 1 hr once /end-day stabilizes post-MVE.*
3. **The "process-first, runtime-second" framing** — before porting any skill into Hermes format, write a one-paragraph runtime map (which steps are deterministic code, which are LLM, which are human-gated). Forces clarity. *Estimated cost: 10 min per skill during G7 / Phase 4 ports.*

**When to actually install AgentTwin:**
- Earliest: after MVE verdict = PROCEED (2026-05-25+).
- Run it once against the final orchestrator spec (Hermes or alphaclaw) before any production deploy.
- Treat its A–F grade as a sign-off gate, not a build dependency.

**When NOT to install:**
- This week (MVE measurement phase — no spec to audit yet).
- If MVE returns BRIEFINGS-ONLY or KILL (no agent build to audit).

---

**End of audit.** Next action: fill in Day 1 of the bypass log and let MVE run.
