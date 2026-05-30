# AAC Framework Extraction (reference doc)

**Source:** <https://github.com/AnkitClassicVision/agent-automation-creator> v1.1, locked 2026-05-14.
**Extracted:** 2026-05-18.
**Purpose:** Aaron's learning reference. Not a quick summary — the full mental model so future-Aaron and future-Claude can apply it to any new agent skill before shipping.

---

## 0. The inversion in one sentence

> Most AI projects design the AI first and fit a process around it. AAC reverses this: map the process, assign the cheapest runtime that satisfies all constraints, and apply AI discipline only where AI is the runtime.

If you internalize nothing else, internalize that. Every other rule below derives from it.

---

## 1. The three unbreakable layers

### Layer 1 — Process Map (must exist before Layer 2)

Three granularities:
- **Work elements** — atomic, one verb. ("query Notion for overdue tasks", not "do the briefing".)
- **Nodes** — transactional groupings with a single named owner.
- **Process** — full DAG with trigger, nodes, edges, queues, decisions, sinks.

**Mandatory map content:**
- A DAG (no cycles).
- Every edge declares: latency budget, volume estimate, contract (input/output schema), trigger type (push/pull/cron).
- Sinks include: happy path, refuse, hard-refuse.
- Hidden queues (DLQs, retry buffers) are drawn, not implied.
- Implicit decisions are made explicit. "If urgent" buried in prose = anti-pattern.

**Anti-patterns:**
- **Mega-node** — 10+ things in one node. Can't isolate failures, can't roll back partway.
- **Implicit decisions** — buried in prose. Not reproducible, testable, auditable.
- **Hidden queues** — DLQs that exist in code but not on the map. Operators can't recover.

### Layer 2 — Runtime Assignment (reads off work attributes, not preferences)

Four runtimes, cheapest-that-fits wins:

| Runtime | Wins when | Relative cost |
|---|---|---|
| **D — Deterministic Code** | Inputs well-formed, decision unambiguous, outcome reversible, stakes low | Baseline |
| **C — Closed-Loop AI** | Medium stakes, natural-language input, reversible (or guarded irreversible), medium volume | ~100–1000× D |
| **A — Assisted AI** | High stakes, complex judgment, human approval required | ~2–10× C |
| **H — Human Only** | Regulatory / novel / value-laden / irreversible-unbounded | ~10–100× A |

**8 constraint dimensions (v1.1 adds 4):**
1. Decision class (unambiguous / natural-language / novel / value-laden)
2. Action consequence (reversible / reversible-costly / irreversible-bounded / irreversible-unbounded)
3. Input type (well-formed / natural-language / ambiguous)
4. Volume × stakes
5. **[v1.1]** Data classification (public / internal / confidential / PHI / PII)
6. **[v1.1]** Provider contract (permitted uses, BAA, DPA)
7. **[v1.1]** Data residency (region / country / third-party)
8. **[v1.1]** Retention + deletion (how long, audit log requirements)

**Hard stops (no C-runtime):**
- C + irreversible-unbounded → downgrade to A or H. *No exceptions.*
- C + ambiguous input → downgrade to D (clarify deterministically) or A.
- C + novel or value-laden decision → downgrade to A or H.
- Any tool in stack fails constraint → STOP, downgrade or swap.

### Layer 3 — Closed-Loop AI Framework (applies only to C; all 5 required or downgrade to A)

The five disciplines. Each is mandatory for any C element. Missing any one = the element is not C-eligible; downgrade until it's fixed.

---

## 2. The 5 disciplines in detail

### 2.1 BOUNDED — stays in its lane

**Definition:** AI picks *parameters*, never *action class*. Vocabulary is finite and enumerated in code.

**Patterns:**
- Actions enumerated in code: `actions = ["send_sms", "send_email", "route_to_human"]`; AI classifies which one.
- OOD detector with explicit threshold; weird input → human.
- Explicit refuse path with logged reason.
- Hard-refuse policy classes enumerated for the domain ("don't send if opted out", "don't send if moved").
- Schema validator at action boundary rejects unapproved actions.

**Anti-patterns:**
- AI selects both action class and parameters ("respond however you think best").
- Action vocabulary implicit in the prompt, not explicit in code.
- Hidden action classes in prompts ("also try X if…" as side-comment).
- No OOD detector — system improvises on weird input.

**Failure consequence:** "What did we just text to all our patients?"

**Rubric items 21–25.**

### 2.2 GROUNDED — checks its facts

**Definition:** Every factual claim has a retrievable source ID. Not guessing. Looking it up, every time.

**Patterns:**
- RAG with explicit citation: `{"fact": "hours 9–5", "source_id": "clinic_config_20260516_v2"}`.
- Output schema *requires* source IDs for all factual fields.
- Validator rejects ungrounded outputs before action.
- Audit trail links every claim to its source.
- Confidence tied to source recency.

**Anti-patterns:**
- AI generates factual claims with no retrieval ("your hours are X" with no lookup).
- Retrieval happens but source IDs aren't logged.
- Training data is the fallback ("I was trained on 2025 hours, so I'll say 9-5").
- Source latency hidden; AI doesn't know data is stale and ships anyway.

**Failure consequence:** Patient texted old hours. Shows up to closed clinic.

**Rubric items 26–28.**

### 2.3 GATED — checks before doing

**Definition:** Multiple checkpoints validate before any real action. Four gates, in order.

**The 4-gate architecture:**
1. **Input gate** — schema validation, value ranges, content policy, OOD test. Rejects malformed input *before* AI call.
2. **Output gate** — schema validation, policy, grounding verification, confidence ≥ floor. Rejects low-quality output *before* action.
3. **Cross-check gate** — conditional second-opinion (cheaper call or rule-based). Conditional on action consequence.
4. **Action gate** — idempotency, rate limits, blast radius, sanity checks. Last gate before irreversible.

**Confidence floors by action consequence (v1.1):**
- Reversible-cheap: **0.6**
- Reversible-costly: **0.8**
- Irreversible-bounded: **0.92**
- Irreversible-unbounded: **not C-eligible** — use A or H.

**Cross-check conditionality:**
- Irreversible-bounded: *unconditional* (always run).
- Others: conditional on confidence/risk (skippable only via *rule*, never vibes).

**Patterns:**
- Hard-refuse runs *before* any other gate.
- Input gate in code before any AI call.
- Confidence scores stored per run; output gate enforces the floor.
- Cross-check is a separate, cheaper call.
- Action gate has idempotency, rate limit, blast radius, sanity checks.
- All four gates visible on the process map with explicit pass/fail paths.

**Anti-patterns:**
- AI output → action with no validation.
- Confidence tracked but not enforced.
- Only the output gate exists; malformed input reaches AI.
- Cross-check has loopholes ("skip if previous 10 were good").
- Hard-refuse runs *after* other gates.

**Failure consequence:** Sent message to someone not opted in, already sent 3x, has no phone, with garbled content.

**Rubric items 29–33.**

### 2.4 OBSERVED — nothing is hidden

**Definition:** Every run is fully visible. Telemetry is continuous, structured, and monitored — not just logged.

**Patterns:**
- Per-run telemetry: input hash, output, model version, latency, cost, confidence, validator pass/fail per gate.
- Control charts on every key metric (not just event logs).
- Input drift, output drift, confidence drift monitored *independently*.
- Champion-challenger on every model/prompt change (shadow run, ≥95% agreement before promotion).
- Cost per run / day / month tracked and alarmed.
- Latency p50/p95/p99 computed; SLA violations logged.

**Anti-patterns:**
- Logs exist but unstructured (incident reconstruction takes hours).
- Telemetry event-based only; no control charts.
- Drift metrics combined (signals cancel out).
- Model changes deployed without shadow testing.
- Cost tracked by cloud provider, not by skill/decision.

**Failure consequence:** Accuracy drifts 95% → 87% over 3 months silently. Discovered via customer complaint. 500 bad outputs already shipped.

**Rubric items 34–37.**

### 2.5 GOVERNED — has a stop button

**Definition:** Human is in control. One-click shutdown. Refusals cheap and logged. Kill switches per action class.

**Patterns:**
- Refuse always available; cheap (button/flag, not a second model call); logged.
- Hard-refuse events audit-logged *separately* from graceful refuse ("human said no" ≠ "AI was unsure").
- Ambiguous input routes to *deterministic* fallback — never AI improvisation.
- Kill switch per action class (disable "send SMS" without disabling "send email").
- Confidence thresholds explicit and version-controlled (in code + runbook).
- Incident runbook with SEV-1/2/3/4 thresholds and response times.

**Anti-patterns:**
- Refusal requires re-intervention every escalation.
- Refuse path expensive (second model call).
- Ambiguous input sent to AI with "guess if you can".
- No kill switch — restart whole process or field calls manually.
- Confidence thresholds soft ("usually aim for 0.8").
- Incident runbook is a Word doc on someone's desktop.

**Failure consequence:** Agent sent a message you didn't intend. Can't shut it down fast enough. Scrambling during incident.

**Rubric items 38–42.**

---

## 3. The 57-item rubric (grouped)

| Section | Items | Audits |
|---|---|---|
| A. Process-level | 1–8 | Is the process graphable and well-defined? |
| B. Work element type | 9–12 | Are elements typed and scoped? |
| C. Runtime assignment | 13–20 | Was the runtime chosen by attributes, not preference? |
| D. Closed-loop properties | 21–42 | Do C elements satisfy all 5 disciplines? |
| E. Spec document | 43 | Are all 16 required sections complete? |
| F. Cost discipline | 44–50 | Will this hemorrhage money? |
| G. Operations | 51–57 | Can this be operated without silent decay? |

**Verdict logic:**
- All 57 pass → production-ready.
- Any A/B/C fail → redesign before build.
- Any D fail on C element → downgrade to A or fix.
- E fail → spec incomplete; builder not ready.
- F fail → will hemorrhage cost; refactor.
- G fail → will silently decay; add operations.

**Grade (A/B/C/D/F):**
- A = all 5 properties healthy.
- B = 4 healthy, 1 needs-work, 0 broken.
- C = ≥1 broken or ≥2 needs-work.
- D = 2+ broken.
- F = 3+ broken or any A/B/C kill.

---

## 4. The 16 required spec sections (before handing to a builder)

A spec is incomplete and not ready to build until ALL of these exist:
1. Work object
2. Mode (Replace / Augment / Extend)
3. Process map
4. Nodes + runtimes
5. Edges
6. Input schema
7. Output schema
8. C-element specs (models, prompts, thresholds)
9. H-element specs (judgment question, metrics)
10. Memory
11. State machine
12. Data contract (all 8 constraint dimensions)
13. Cost model
14. Latency SLAs
15. Failure modes + recovery
16. Ownership + operations

If you can't fill in section 8 because the AI part isn't designed yet, you're still in Layer 2, not Layer 3. Don't build.

---

## 5. AgentTwin (the diagnostic tool)

A Claude Code skill that audits any agent against the 57-item rubric and outputs a self-contained HTML report.

**Fires when:** user asks to diagnose / audit / score / map / visualize / "is this ready?" / "should we ship?" / shares a spec or workflow diagram.

**Output:** single HTML file, two tabs:
1. **Summary** — letter grade, 5 plain-English property cards (Stays in its lane / Checks its facts / Checks before doing / Nothing is hidden / Has a stop button), before/after toggle, 3-item action plan for non-technical reader.
2. **Process Map** — flow overview, ranked recommendations (Critical / High / Medium / Optimization), memory + state machine cards, per-node detail (model info if C, judgment info if H), edge detail, full fix list.

**5-step audit process:**
1. Identify workflow (read everything; don't invent gaps).
2. Extract AAC elements (nodes, edges, cross-cutting).
3. Score 57-item rubric; assign per-property status; derive grade.
4. Build JSON per data-schema.md.
5. Render HTML, save, present.

**Status calibration:**
- **Healthy** — implemented, documented, monitored, no fails in 30 days.
- **Needs work** — partial / has gaps / 1–3 fails in 30 days.
- **Broken** — missing / undocumented / 4+ fails or incident in 90 days.

**Cardinal rule:** when between levels, downgrade. Surface problems clearly.

---

## 6. AAC's named anti-patterns (the things it warns NOT to do)

1. **Mega-node** — 10+ things in one node; can't isolate failures.
2. **Implicit decisions** — buried in prose; not reproducible.
3. **AI-selects-action-class** — AI chooses entire action class; unbounded.
4. **No-refuse-path** — no graceful decline; acts even when unsure.
5. **Missing-DLQ** — failure queues exist in code but not on map.
6. **Ungrounded-claims** — facts generated without lookup.
7. **Model-change-without-shadow** — deploy without A/B; discover divergence weeks later.
8. **No-control-charts** — telemetry collected but not monitored.
9. **Cost-creep** — no alarms; cheap model never re-benchmarked.
10. **Silent-decay** — no weekly trace review, monthly eval, quarterly re-bake.
11. **Regulatory-pretense** — "human approval required" but humans auto-approve. Audit trail appearance without actual safety.

---

## 7. Operating discipline (Section G: items 51–57)

Workflows without operators silently decay. Every production agent requires:
- **Named owner** doing weekly trace reviews (10–20 traces).
- **Monthly eval set refresh** defined.
- **Quarterly model re-bake** defined.
- **Incident runbook** with SEV-1/2/3/4 thresholds + response times.
- **Change management path** — Propose → Eval → Canary → Rollout, with approvals.
- **[v1.1] Every H element declared terminal or migration-eligible** with reason class.
- **[v1.1] Per-error cost band declared**; graduation threshold matches band.

---

## 8. The author's worldview

- **Inversion principle:** process first, runtime second, AI discipline only where AI runs.
- **Safety by design:** the 5 disciplines are structural bones, not nice-to-haves.
- **Right-size the problem:** cheapest runtime that satisfies all constraints, not preference.
- **Jidoka (stop the line):** if a workflow fails the rubric, it's not production-ready. Period.
- **Operator-in-the-loop is mandatory:** weekly trace reviews, monthly eval refreshes, incident runbook. No exceptions.
- **Regulatory/contractual constraints are structural:** data class, BAA, residency, retention determine runtime, not compliance overlay.

Battle-tested on two healthcare workflows: optometry after-hours intake (~80 calls/day, $0.012/contact) and Rx fax entry (~5 faxes/day, $0.048/contact). The 8 v1.0→v1.1 changes came from the Rx workflow exposing gaps.

---

**End of extraction.** See sibling doc `aac-audit-of-current-skills.md` for how to apply this to /start-day, /capture-meeting, /end-day, and to scope new workload-killer skills.
