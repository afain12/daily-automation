# AAC Audit of Daily-Automation Skills

**Date:** 2026-05-18.
**Auditor:** Claude.
**Framework:** AAC v1.1 (see `aac-framework-extraction.md`).
**Subjects:** `/start-day`, `/capture-meeting`, `/end-day`.
**Aaron's stated goal:** reduce workload on sending emails and BS tasks.

This is a learning audit, not a redesign. The point is to see *where each skill silently violates AAC discipline* — because each violation is either a workload cost (manual fallback) or a future incident risk.

---

## 0. Headline verdict

| Skill | Letter grade | Worst property | One-line summary |
|---|---|---|---|
| `/start-day` | **B** | OBSERVED | Strong on BOUNDED + GATED (trust gate is real). Weak on telemetry/cost tracking. No grounding source-IDs on facts. |
| `/capture-meeting` | **C** | GROUNDED + GATED | Routes by indicator keyword match — no source-ID for "this is an action item". Confidence floor is implicit ("be generous, let trust gate decide"). |
| `/end-day` | **B** | OBSERVED | Best designed of the three (dead-task scan, dormant_snooze, bidirectional sync). Lacks per-run telemetry + cost. |

**System-level finding:** the three skills are unusually disciplined on BOUNDED and GOVERNED (every write goes through a trust gate), and unusually weak on OBSERVED (no per-run telemetry, no drift monitoring, no cost attribution). That asymmetry is *exactly* the Manus v2 + AAC overlap we flagged in `manus-v2-audit-and-execution.md` §1.

The system is safer than it is legible. Good news: that's the easier failure mode to fix.

---

## 1. /start-day — full audit

### Process map (Layer 1) — present but not drawn

The skill has **9 explicit steps** with 3 sub-steps (1b, 1c, 6b, 8b). That's good. But several AAC violations:

- **Mega-node risk in Step 3 ("Pull Notion Databases").** It bundles Master Tasks + Provider CRM + Activity Log + Meeting Notes + workspace-wide search + sync-gap detection. By AAC's definition (≥10 things in one node), this is a mega-node. Fix: split into 4 nodes — one per data source — and a 5th node "coverage check".
- **Implicit decisions.** Step 6 ranking rules contain "Break ties by alternating business" — this is a decision but not surfaced as a node. Step 6 starvation guard is another implicit decision. Both should be explicit nodes on the map.
- **Hidden queue.** `state/gtask-retry-queue.yaml` (Step 8b failure handling) is a DLQ. It exists. It's not drawn on any map. AAC anti-pattern #5.

### Runtime assignment (Layer 2)

Reading the skill: most "AI" work is actually deterministic.

| Step | Today's runtime (effectively) | AAC says should be | Why |
|---|---|---|---|
| 1, 1b | D (read files, validate) | D | ✓ |
| 1c (sync reconcile) | D (deterministic comparison) | D | ✓ |
| 2–5 (pull sources) | D (curl + JSON parse) | D | ✓ |
| 6 (scoring) | D (formula in markdown) | D | ✓ |
| 6b (24h changes) | D | D | ✓ |
| 6 starvation guard | A (Claude infers oldest stale dept) | D — write the formula in code | Currently a "use your judgment" instruction to Claude. AAC: ambiguous → downgrade to D. |
| 7 (compose briefing) | C (Claude prose-generates) | C with grounded sources | ✓ runtime; grounding is the gap |
| 3 Granola triage hints | C (Claude infers workspace from attendees) | A — Aaron approves | Currently auto-included in briefing without explicit confidence floor. |
| 8 trust gate | H (Aaron approves) | H | ✓ |
| 9 writes | D (execute approved curl) | D | ✓ |

**Real finding:** Step 7 is the only true C element. Most of the skill is D dressed as a Claude conversation. That's fine — but it means the 5 disciplines really only apply to Step 7.

### The 5 disciplines applied to Step 7 (compose briefing)

| Discipline | Status | Evidence + fix |
|---|---|---|
| **BOUNDED** | ✅ Healthy | Output schema is a fixed markdown template. Claude doesn't get to invent sections. |
| **GROUNDED** | ⚠️ Needs work | Briefing text says "AFC Urgent Care, 2 days overdue" — but the briefing doesn't include a `source_id` link to the Notion page. If Aaron disputes a claim, you can't 1-click verify. **Fix:** include the `<!-- notion:<ID> -->` comment in the displayed briefing (it's already in the daily note template). Cost: 0 LOC, just format change. |
| **GATED** | ✅ Healthy | Output gate is the trust-gate (Step 8). Input gate is Step 1b pre-flight. Cross-check is the Step 1c reconcile. Action gate is the per-curl `--max-time 60`. |
| **OBSERVED** | ❌ Broken | No per-run telemetry. No "how many briefings have been generated this month", "what's the p95 latency", "what's the average token cost". This is the **single biggest gap.** Cost: 1–2 hr to add a `logs/_telemetry.jsonl` append at end of every run. |
| **GOVERNED** | ✅ Healthy | Trust gate. Aaron can refuse any option. No auto-send. |

**Verdict: B.** OBSERVED is the only broken property. Grounding source-IDs is the only "needs work". Both cheap to fix.

### Concrete fixes for /start-day (ranked by load reduction)

1. **Add `logs/_telemetry.jsonl` append.** Each run writes: timestamp, sources_available, sources_skipped, top3 score breakdown, latency per step, total runtime. Unblocks weekly trend review without you opening logs. *~1 hr.*
2. **Embed source-ID in displayed briefing**, not just the daily note. Currently you have to open the daily note to click through to Notion. Embed `<!-- notion:abc-123 -->` (or render as `[→]` markdown link if briefing is delivered to Telegram). *~30 min.*
3. **Replace "starvation guard" prose with a deterministic formula.** Today Claude infers "oldest stale dept not in top 3". Make it a sort comparator. AAC: ambiguous → D. *~30 min.*
4. **Add a `confidence` field to Granola workspace-triage suggestions** (Step 3 untagged section). When Claude infers workspace from attendees, attach a 0–1 confidence; if < 0.7, mark as "low confidence — verify manually". *~1 hr.*

---

## 2. /capture-meeting — full audit

This is the highest-load, highest-risk skill (it *writes* to Notion + Google Tasks + Calendar + Obsidian).

### Process map (Layer 1) — present, but anti-patterns visible

- **Mega-node in Step 6.** Steps 6a (parent task + subtasks + gtasks mirror + back-pointer PATCH), 6a-bonus (recap PATCH), 6b (Activity Log), 6c (CRM update), 6d (calendar draft), 6e (Obsidian notes + meeting file). That's 12+ distinct write actions in one node. Classic AAC mega-node.
- **Implicit decisions.** Step 4 says "Be generous in matching — over-categorize, let Aaron trim at trust gate." That's an explicit *anti-pattern* per AAC §2.2: "AI generates factual claims with no retrieval / confidence". The right pattern is: classify with confidence, surface low-confidence as "uncategorized" with reason.
- **Hidden queue.** Failed Notion writes go to `${VAULT}/meetings/{TODAY}-pending-notion.md`. That's a DLQ. Not drawn. Anti-pattern #5.

### Runtime assignment (Layer 2)

This is where /capture-meeting silently violates AAC the most. Look at the **action consequence** column:

| Step | Action | Consequence | Today's runtime | AAC says should be |
|---|---|---|---|---|
| 6a-1 | Create parent Notion task | Reversible (archive page) | C → trust gate → D | ✓ |
| 6a-2 | Create subtask | Reversible | C → trust gate → D | ✓ |
| 6a-3 | Create Google Task | Reversible (delete) | C → trust gate → D | ✓ |
| 6a-bonus | PATCH recap page Workspace+Relations | **Irreversible-bounded** (overwrites prior Workspace if present, *merges* relations but original Workspace value is lost without an undo payload) | C → trust gate → D | ✓ runtime, but confidence floor should be **0.92** per AAC GATED, not Aaron's eyeball at trust gate |
| 6b | Log decision to Activity Log | Reversible | C → trust gate → D | ✓ |
| 6c | Update existing CRM record OR create new | **Irreversible-bounded if update** (Last Contact / Next Step overwrite) | C → trust gate → D | Needs undo payload (Manus §4.3 + PRD §8.8). |
| 6d | Calendar quickadd | Reversible (delete event) | C → trust gate → D | ✓ |
| 6e | Write Obsidian files | Reversible (rm) | D | ✓ |

**Real finding:** Steps 6a-bonus and 6c are *irreversible-bounded* writes (the prior value is lost when you PATCH). AAC says these need **confidence ≥ 0.92** and **unconditional cross-check**. Today's trust gate is binary (approve/skip) — there's no confidence to enforce, and Aaron is the cross-check. That's fine for single-user tooling, but it's why /capture-meeting can quietly clobber a hand-entered CRM "Next Step" if Claude's parsed update is sloppy.

### The 5 disciplines applied to /capture-meeting

| Discipline | Status | Evidence + fix |
|---|---|---|
| **BOUNDED** | ⚠️ Needs work | Action vocab is enumerated (5 categories), but Step 4 says "match multiple categories when ambiguous — let trust gate decide". That's AI selecting *both* parameters and (multiple) action classes. AAC anti-pattern #3. **Fix:** pick one primary category with confidence; surface secondary categories only as "consider also" hints below the trust gate. |
| **GROUNDED** | ❌ Broken | The big one. When Claude extracts "Tell Abos to follow up with Dr Remzy by Friday" → routes to Master Tasks with Owner=Abos, Due=Friday — **none of this is grounded.** "Abos" is matched to a user_id via `GET /v1/users` (good), but "Friday" is parsed by Claude with no source citation, and the action-class assignment ("this is an action item") has no `source_id` pointing to the originating bullet. **Fix:** every routed item carries `{"source_text": "<original line>", "source_offset": 412, "extraction_confidence": 0.85}`. Surface confidence at the trust gate. |
| **GATED** | ⚠️ Needs work | Output gate (trust gate) ✓. Input gate ⚠️ — accepts any pasted text without OOD detection (what if Aaron pastes a wall of medical reports? what if he pastes patient names?). Cross-check ❌ — none. Action gate ⚠️ — no idempotency check (re-running on the same meeting *does* dedupe per Step 6a-3 edge case "Re-running on the same meeting", but only by querying Master Tasks after the fact; AAC wants an idempotency *key* per write). **Fix:** input gate scans for PHI markers (patient names patterns, DOBs, MRNs) and refuses. Idempotency = `action_id = capture-meeting:{recap_page_id_or_hash}:{action_index}`. |
| **OBSERVED** | ❌ Broken | Same as /start-day — no per-run telemetry. Worse: no record of *how many items each meeting produced*, *which categories*, *which were rejected at trust gate*. You can't see drift if Claude starts over-extracting. |
| **GOVERNED** | ⚠️ Needs work | Trust gate ✓. Kill switch ❌ — no per-action-class disable ("don't touch CRM today"). Refuse path: "None — just save the notes" ✓ but it's a single-meeting refuse, not a standing refuse. **Fix:** add a `COO_MODE=draft` env var (Manus §4.2) that forces all routing to dry-run regardless of trust gate approval. |

**Verdict: C.** GROUNDED is broken (no source citation on any routed item), GATED has missing input gate + no idempotency, OBSERVED has no telemetry. Three of five properties need work.

### Concrete fixes for /capture-meeting (ranked by load reduction)

1. **Idempotency key per write.** Re-running /capture-meeting on the same Granola URL today silently relies on a post-hoc dedupe query. Make it explicit: `action_id = capture-meeting:{recap_page_id}:{hash(action_text)}`. Cache `.context/applied/{action_id}.json`. Re-runs no-op fast. *~2 hr.*
2. **Source citation on every routed item.** Each entry in the trust gate displays `[from line 14: "Tell Abos to follow up with Dr Remzy by Friday"]`. Lets you spot misparses before approving. *~3 hr.*
3. **Confidence score per categorization.** Display "ACTION (0.92)" / "INSIGHT (0.61)" at the trust gate. Anything < 0.7 auto-routes to "Uncategorized" instead of polluting the routed list. *~2 hr.*
4. **Input gate for PHI markers.** Regex scan for SSN / DOB / MRN patterns; refuse with "PHI detected — paste cleaned notes". Doesn't make HIPAA compliant but stops the dumbest leakage. *~1 hr.*
5. **Undo payload generator.** For 6a-bonus and 6c (the irreversible-bounded writes), snapshot prior state to `.context/undo/{action_id}.json` *before* PATCH. PRD §8.8 already designs this. *~4–6 hr.*

---

## 3. /end-day — full audit

The most disciplined skill of the three. Already has dead-task scan, dormant_snooze, bidirectional sync, gtask retry queue, 4-way reconcile buckets. It reads like it was *built* with AAC in mind even though it wasn't.

### The 5 disciplines

| Discipline | Status | Evidence |
|---|---|---|
| **BOUNDED** | ✅ Healthy | Step 7b dead-task options are 4 enumerated actions (Done / set date / back-burner / snooze). Step 7 is 3 enumerated options. No improvisation. |
| **GROUNDED** | ✅ Healthy | Step 4b parses source-ID from HTML comments. Step 4c reads `last_edited_time` from Notion. Every claim traces to a source. **The model for the other two skills.** |
| **GATED** | ✅ Healthy | Step 7 trust gate, Step 7b dead-task gate. Both Aaron-approved. Idempotency in Step 8e/8f via batched approval. |
| **OBSERVED** | ❌ Broken | Same gap as the other two — no telemetry. No "carry-forward trend over 30 days", no "average sync gap count". `state/priorities.yaml` is state, not telemetry. |
| **GOVERNED** | ✅ Healthy | Trust gate. Dead-task forced decision (no silent re-surface). Dormant-snooze 5-day timeout enforced. |

**Verdict: B.** Only OBSERVED is broken. Everything else is healthy.

### Concrete fixes for /end-day

1. **Append per-run row to `logs/_telemetry.jsonl`.** Same fix as /start-day. *~30 min after start-day version exists.*
2. **Track "real movement off Top 3" as a first-class metric** (per existing memory `feedback_top3_vs_actual.md`). Already manually surfaced — make it telemetry too. *~30 min.*
3. **Promote the gtask retry queue to a visible DLQ.** Today it's `state/gtask-retry-queue.yaml`. Add a section to the EOD retro: "DLQ status: N items, oldest M days". *~15 min.*

---

## 4. What's MISSING entirely (the BS-task killer skills you don't have yet)

This is the part of the audit aimed directly at Aaron's stated goal: "reduce workload on sending emails or doing BS tasks."

The three existing skills are *read-and-organize* skills. None of them *dispatch outbound work*. That's the whole reason Manus v2 felt different — it's a dispatch-first framing.

Applying AAC's runtime-assignment logic, here are the skills that would actually reduce email/BS load. Each row maps to AAC's 4 runtimes:

| Skill | What it does | AAC runtime | Why it's the right runtime |
|---|---|---|---|
| `/supplies-order` | Aaron texts "order panels for Lincoln Lab"; agent drafts email to `supplies@lincolnreference.com` with last-week's order as template. | C → trust gate → D | Template-driven, recipient whitelisted, reversible (Aaron sees draft before send). |
| `/provider-followup-nudge` | Cron-fired daily: any Provider CRM row with `Last Contact > 14 days` AND `Stage != "Lost"` → drafts a 3-line follow-up email per provider. Aaron approves batch in Telegram. | C → trust gate → D | Reversible, low-stakes, idempotency key = `followup:{provider_id}:{date}`. |
| `/courier-pickup-request` | Aaron texts "courier 5pm" → drafts pickup email to logistics with today's specimen count from a Notion DB. | C → trust gate → D | Template + 1 lookup. Idempotent. |
| `/AR-aging-nudge` | Weekly: scan a (future) AR aging Notion DB; draft polite-but-firm follow-up emails per overdue invoice. | A — Aaron tones each one | High-stakes (relationship), value-laden. AAC: A, not C. |
| `/meeting-prep-brief` | 30 min before each Tier-1 calendar event, agent posts to Telegram: attendees, last 3 Activity Log entries with them, open tasks involving them. | C — read-only, no writes | Pure GROUNDED retrieval. AAC: fine at C with source citations. |
| `/dead-relationship-scan` | Weekly: providers contacted 3+ months ago, no decline reason logged → suggest re-engage or mark Lost. | A | Value-laden (which to drop). |
| `/it-ticket-by-accession` | Aaron texts "IT issue with accession A12345" → drafts ticket. **AAC v1.1 lens:** accession is the operational identifier; PHI lookup is the linked work. AAC §2.4 GROUNDED + Manus §4.1 (placeholder-then-render) pattern fits. | A — compliance-gated | Manus correctly downgraded this from C to A pending compliance review. |

**The single highest-leverage new skill: `/provider-followup-nudge`.** Reason: your Provider CRM already has `Last Contact` and `Stage`. The work to draft is template-driven. The work that takes you time today is *opening Notion, scanning, picking up the phone*. AAC runtime-eligible at **C with trust gate**. Estimated build: 1 day. Estimated load reduction: 30–60 min/day of "I should reach out to so-and-so".

---

## 5. Cross-cutting fixes (apply to all skills + future skills)

These are the AAC patterns that would reset the floor for every skill simultaneously:

### 5.1 Per-run telemetry (OBSERVED, all skills)

Single file: `logs/_telemetry.jsonl`. Append-only. One line per skill run:

```json
{"ts":"2026-05-18T07:03:14-04:00","skill":"start-day","run_id":"sd-20260518-0703","duration_ms":18420,"sources_ok":["calendar","notion","tasks","obsidian"],"sources_skipped":[],"top3_scores":[8,7,5],"writes":0,"cost_usd":null}
```

Unblocks: weekly retro, drift detection, cost trends. *~2 hr once across all 3 skills.*

### 5.2 Source-ID propagation (GROUNDED, all skills)

Every piece of data that flows through the system carries its `source_id` as metadata. /start-day already does this in daily-note HTML comments — extend to: briefing display, /capture-meeting routed items, /end-day retro lines.

*~3 hr once.*

### 5.3 Idempotency keys on every external write (GATED, all skills)

`action_id = {skill}:{target_id}:{date}:{hash(payload)}`. Stored in `.context/applied/{action_id}.json`. Re-runs check existence and no-op.

PRD §8.8 already designs the undo payload schema. This is the *idempotency* side of the same pattern.

*~2 hr per skill.*

### 5.4 Operating modes (GOVERNED, system-wide)

Single env var: `COO_MODE` ∈ {`observe`, `draft`, `approved`, `auto`, `locked`}. Default `draft`. Skills check at the top:
- `observe` — no writes ever.
- `draft` — trust gate required (today's default).
- `approved` — trust gate auto-approves whitelisted action_ids.
- `auto` — full auto for `whitelisted_skills` only (none today).
- `locked` — no skills run at all.

Manus §4.2 + AAC GOVERNED converge here. *~1 hr.*

### 5.5 LOCK AGENT Telegram command (GOVERNED, post-MVE)

Telegram message `LOCK AGENT` flips `COO_MODE=locked` in a state file the cron tasks read on next fire. Confirmation: `🛑 Agent locked. All skills will refuse until /UNLOCK AGENT.`

*~1 hr once Telegram bot exists (MVE step 1–6).*

---

## 6. Spec discipline for any new skill (AAC §4 applied)

Before building `/provider-followup-nudge` or any future skill, fill in all 16 spec sections. Concrete template:

1. **Work object** — "draft a follow-up email to a provider who hasn't been contacted in 14+ days"
2. **Mode** — Replace (Aaron's current manual scanning of CRM)
3. **Process map** — cron trigger → query CRM (D) → filter stale (D) → for each: draft email body (C) → trust gate (H) → send via Gmail API (D) → log to Activity Log (D)
4. **Nodes + runtimes** — listed above
5. **Edges** — cron: 1x/day 08:00 ET; CRM query → filter: ≤2s p95; filter → draft: 1 call per provider, max 20 providers/run; draft → gate: Telegram batch message; gate → send: ≤30s after approval
6. **Input schema** — `{provider_id, name, last_contact, stage, prior_email_history}`
7. **Output schema** — `{draft_subject, draft_body, source_ids: [{provider_id, last_email_id}], extraction_confidence: 0–1}`
8. **C-element specs** — model: Sonnet 4.6; prompt: cached system prompt with template; confidence floor: 0.8 (reversible-costly per AAC)
9. **H-element specs** — Aaron approves batch in Telegram; metric tracked: approve rate per run
10. **Memory** — gbrain prior emails to same provider (post-MVE)
11. **State machine** — provider state: never_contacted | active | stale | re-engage_drafted | sent_recently
12. **Data contract** — internal data class; no PHI in email bodies; provider names = internal classified; recipient whitelist required
13. **Cost model** — ~$0.02 per draft × 20/day max = $0.40/day = $12/month
14. **Latency SLAs** — cron-fire to Telegram batch ≤ 3 min; approval to all-sends-complete ≤ 60s
15. **Failure modes + recovery** — Notion CRM down → skip run; Gmail API 4xx → log + retry next day; Gmail API 5xx → retry once, then DLQ
16. **Ownership + operations** — Aaron; weekly trace review of approve rate + draft quality; monthly: re-bake prompt if approve rate < 70%

If any of those 16 are blank when you start building, AAC says STOP — you're not ready.

---

## 7. The learning, in one paragraph

The single most useful thing AAC teaches that we're not yet doing: **make confidence and source citation first-class fields on every routed item**. Today, /capture-meeting hands you a list ("8 actions, 3 decisions, 2 insights") and you approve or reject. AAC says: it should hand you a list where each item shows ("ACTION 0.94 [from line 14]"), and items below 0.7 confidence don't make the list at all — they go to a "couldn't categorize, please decide" bucket. That single change collapses the trust-gate cognitive load. You stop being a yes/no on 13 items and start being a yes/no on 9 items + a triage on 4. It's the same number of decisions you have today, but the easy ones are gone. Multiply across every skill that writes externally, and the daily friction drops by 30–50% without changing what the agent *does* — only how it *presents what it's about to do*.

The second most useful thing: **dispatch skills are runtime-eligible at C with a trust gate.** You don't need PHI clearance, you don't need 8 weeks of Hermes work, you don't need an undo system for *reversible* emails. You need a recipient whitelist, an idempotency key, and the same trust-gate pattern you've already mastered in /capture-meeting. `/provider-followup-nudge` is the first one to build — and it could ship in a week, well within the MVE evaluation window if the MVE comes back PROCEED.

---

**End of audit.** See `aac-framework-extraction.md` for the full reference.
