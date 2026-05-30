# Routing Redesign — Log Analysis Plan

**Status:** Deferred. Analysis scheduled for **on or after 2026-05-06** (2 full weeks of logs).
**Purpose:** Before committing to the Codex-revised routing design, mine 2 weeks of real logs/daily-notes/priorities-state so every threshold, bucket, and UX choice is calibrated to Aaron's actual workflow instead of guesses.
**Evidence base (at execution time):** all `logs/*.md` and `vault/daily/*.md` between 2026-04-14 and the execution date, plus `state/priorities.yaml` daily snapshots.

## Pending input: New department promotion (Specialty Pharmacy)

**Captured 2026-04-27** during workflow refinement pass. Do not act before 2026-05-06.

Evidence:
- 2026-04-20 log: created "Specialty Pharmacy" note under Nestmate Health.
- 2026-04-22 log: 13 subtasks created overnight at 03:13 (auto-generated, not from a /capture-meeting run).
- 2026-04-23 log: GI NotebookLM episode produced under Specialty Pharmacy umbrella; "Shapsis via Sorkin — 45/pp proposal" carried forward as Specialty Pharmacy work but currently filed under Nestmate.

Decision to make on 2026-05-06: promote `specialty_pharmacy` to a top-level Workspace in `config/sources.yaml` with its own keyword list, OR keep it as a sub-tag under Nestmate. If promoted, update CLAUDE.md department table, all skill briefing templates, and routing rules accordingly.

Why deferred: this is a routing change. Adding it now contaminates the 14-day evidence base.

---

## Deferral rationale (decided 2026-04-22)
Aaron chose to wait until two weeks of data accumulate before running the analysis. Reasons and implications:
- **More data = better-calibrated thresholds.** 6 days of logs would let us over-fit to the current week (which is Specialty-Pharmacy-heavy). 14 days smooths that.
- **Cost of waiting:** ~1 misroute/day will continue until the redesign ships. Aaron accepts this; corrections will keep being surfaced inline in each daily note.
- **Critical constraint during the wait:** do NOT modify routing logic in `start-day`, `end-day`, or `capture-meeting` between now and the analysis run. Changing the routing while collecting evidence contaminates the dataset. Bug fixes unrelated to routing are fine.
- **During the wait, DO:** keep capturing inline corrections in daily notes, let /end-day continue carrying forward, let priorities.yaml grow naturally. The evidence base depends on unmodified behavior.

## Trigger
Re-open this plan and run Phases 1–7 on the first `/start-day` session on or after **2026-05-06** (assuming ≥10 daily-note files exist between 2026-04-14 and that date). If daily notes fall below that count by then, push the trigger date out until we have ≥10.

---

## Design decisions this plan will answer

The open questions from the Codex-revised design:

| # | Decision | Options | What we need from data |
|---|---|---|---|
| D1 | Confidence threshold for auto-routing | 0.6 / 0.7 / 0.8 | Misroute rate observed per confidence level |
| D2 | Force-claim friction tolerance | 3–5 claims/day / 6–10 / unlimited | Actual volume of ambiguous items per day |
| D3 | Parked store rendering | Hidden / collapsed / inline | How many parked items per dept at steady state |
| D4 | Which people need disambiguation | Start narrow vs broad | People appearing in ≥2 depts across logs |
| D5 | Single-dept alias map (seed list) | — | Names that always route to one dept |
| D6 | Google Tasks parent → dept mapping | Curated list vs free inference | Parent titles and their true depts |
| D7 | Dedup signal precedence | ID-first vs hybrid | How often IDs are present in carry-forwards |
| D8 | Learned-rule decay window | 14d / 30d / 60d | Rule half-life observed |

---

## Analysis phases

### Phase 1 — Inventory & normalize (30 min)
**Goal:** Get every actionable item from the 6 days into a single structured dataset.

1. Parse each `logs/YYYY-MM-DD.md` and `vault/daily/YYYY-MM-DD.md`
2. Extract per-item fields:
   - `date`, `title`, `claimed_dept` (what briefing assigned), `true_dept` (from inline corrections OR from end-day log), `source` (notion/tasks/calendar/carry-forward), `source_id` (if present), `parent_title`, `status` (active/completed/parked/carried), `days_carried` (from priorities.yaml if applicable)
3. Write to `state/tmp/routing-analysis.jsonl` — one JSON per item
4. Sanity: spot-check 10 items by eye vs their file

**Deliverable:** `state/tmp/routing-analysis.jsonl` with estimated 200–400 items across 6 days.

---

### Phase 2 — Misroute audit (20 min)
**Goal:** Answer D1 + D5 — how bad is current routing, which names are safe overrides.

1. For every item, compute `was_misrouted = (claimed_dept != true_dept)`. Count by day and overall.
2. Group misroutes by *why it went wrong*:
   - Notion Workspace field was null → bucket A
   - Workspace was present but ignored → bucket B (shouldn't happen, but flag it)
   - Google Tasks parent pointed to wrong dept → bucket C
   - Person name ambiguous (multi-dept person) → bucket D
   - No disambiguating signal at all → bucket E
3. For items NOT misrouted, record which signal got them right. This builds the auto-routing-works baseline.

**Deliverable:** `state/tmp/misroute-audit.md` — 1-page summary:
- Overall misroute rate (today's number was 4/~75 = ~5%; want 6-day average)
- Breakdown by bucket A–E
- Top 10 recurring names that were routed correctly every time → **seed for single-dept alias map (D5)**

---

### Phase 3 — Multi-department people census (15 min)
**Goal:** Answer D4 — which names genuinely need disambiguators, which ones are single-dept.

1. Extract every person mentioned across all 6 days (capitalized first names + "Dr. X" patterns)
2. For each name, list the set of departments it appeared under across the 6 days
3. Rank:
   - **Single-dept** (appeared in exactly 1 dept) → goes to alias map
   - **Multi-dept with clear contexts** (e.g., Cyrus: IPA when task mentions "account", Nestmate when "Bay Parkway") → goes to `person_routing.yaml` with disambiguators
   - **Multi-dept with no discriminator** → always force-claim

**Deliverable:** `state/tmp/person-census.md`:
- `single_dept`: [name → dept] list (target: ~15–25 names)
- `multi_dept_with_context`: [name → {dept: [keywords]}] list (target: Cyrus, Ilene, Ahmed, Ryan, maybe 2–3 others)
- `multi_dept_ambiguous`: [names that always need claim] (target: ≤5)

---

### Phase 4 — Force-claim volume estimate (10 min)
**Goal:** Answer D2 — how many claims per morning is this actually going to cost?

1. Re-run the revised pipeline (mentally or scripted) against the 6-day dataset at three thresholds: 0.6, 0.7, 0.8
2. Count items that would have gone to "Needs Routing" under each threshold
3. Average per morning; tail (worst day) also matters

**Deliverable:** 3-row table — (threshold, avg claims/day, worst-day claims/day). Aaron picks the threshold he can live with.

---

### Phase 5 — Carry-forward dedup & parked analysis (15 min)
**Goal:** Answer D3, D7, D8.

1. **Dedup (D7):** For every carry-forward entry in the 6-day priorities.yaml snapshots, check whether it has a `source_id`. Compute the ID-fill rate. If >70% have IDs, ID-first dedup is viable. If lower, need to force the carry-forward writer (/end-day) to always capture IDs going forward.
2. **Parked volume (D3):** Count items currently "carried ≥7 days" in priorities.yaml (7 items today per my earlier parse — Rookwood, Good Health Psych, Main Street Radiology, Vamos, Adrianova, Ling CUI, Peptide purity, YubiKey, Shake/braces). Project forward — if 7+ parked items already after 1 week, inline rendering is clutter.
3. **Decay window (D8):** Look at carry-forward entries that eventually got closed. Median time from first carry to close = natural rule-relevance window. Use 2× that as the learned-rule decay threshold.

**Deliverable:** `state/tmp/dedup-parked-analysis.md` — 1-page with:
- ID-fill rate on carry-forwards today
- Current parked-item count by dept (Nestmate/Dock Pro/IPA/Lab/Other)
- Recommended decay window in days

---

### Phase 6 — Parent-title mapping (10 min)
**Goal:** Answer D6 — can we trust Google Tasks parent inheritance?

1. Extract every Google Tasks parent title from the 6 days
2. For each parent, assign the correct dept manually based on the subtasks it contains
3. If parent→dept is 1:1 for ≥90% of parents, inheritance is safe. If multi-mapped, inheritance is a liability.

**Deliverable:** `config/tasks-parent-routing.yaml` draft — curated parent title → dept map.

Examples from today's data:
- "Accureference brainstorm" → Lab
- "Specialty Pharmacy" → Nestmate
- "Send email to reps" → Lab
- "Followup on United Ipa sign up docs" → IPA
- "Accounts to train for swab" → Lab
- "Rippling for Valentyna" → Other/HR
- "For house" → Other/Personal
- "Ai papers to read" → Other
- "For dr rookwood" → Nestmate

---

### Phase 7 — Synthesis & revised-design commitment (15 min)
**Goal:** Turn analysis into concrete config files + updated `.claude/skills/start-day/skill.md`.

1. Write `config/person_routing.yaml` seeded from Phase 2 + Phase 3 output
2. Write `config/tasks-parent-routing.yaml` from Phase 6
3. Write `state/parked.yaml` schema + migrate current parked items from priorities.yaml
4. Draft updates to `/start-day` and `/end-day` skill files to apply the new pipeline (do NOT implement yet — draft only for review)
5. Write `state/routing-metrics.jsonl` schema (append target)

**Deliverable:** Set of 4 draft config files + 2 skill-file patch previews. Presented for approval before any skill file is actually edited.

---

## Total estimate
~1.5–2 hours of focused analysis. Phases 1-6 produce evidence artifacts; Phase 7 turns evidence into config drafts. **No skill code changes until Phase 7 artifacts are approved.**

## What this plan explicitly does NOT do
- ❌ Does not modify `.claude/skills/start-day/skill.md` or any skill file
- ❌ Does not touch Notion or Google APIs (purely local file analysis)
- ❌ Does not implement the parked store, the learned-rules file, or the metrics pipeline — it only produces drafts
- ❌ Does not answer "should we build /weekly-review yet" — that's a separate question, the metrics schema just sets it up

## Open questions for you before we run this
1. **Scope:** is 6 days enough evidence, or should we wait until we have 2 weeks and then run the analysis once with more data? (More data = better thresholds, but delays the fix for another week of misroutes.)
2. **Execution mode:** should I run Phases 1–6 in one shot and present all findings together, or gate after each phase for your input? Gating adds 5–10 min per gate in elapsed time but surfaces disagreements early.
3. **Phase 7 deliverable format:** do you want the draft configs in-line in chat for review, or written to disk at their final paths so you can edit them directly in your editor?
