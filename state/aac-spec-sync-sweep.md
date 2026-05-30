# /sync-sweep — AAC 16-section spec (v0.2 DRAFT)

**Date:** 2026-05-19 (v0.1 initial draft same day; v0.2 same-session revision after Aaron's design picks + scope expansion).
**Author:** Claude (Chief of Staff drafting on Aaron's brief).
**Status:** DRAFT — design picks locked, scope expanded. Not yet approved to build. Decision doc captured at `[[project-sync-sweep-skill]]` in memory.
**Framework:** AAC v1.1, per `state/aac-framework-extraction.md`.
**Sibling reference:** `state/aac-audit-of-current-skills.md` §6 (worked-example format this doc mirrors).

> **Why this skill exists.** Aaron's words: *"Data is equivalent to thousands of dollars being left on the line."* Today, when Aaron drops "Alex Acosta finally called back — push the Roosevelt cardio meeting to Friday" into the daily-note braindump, nothing finds the Alex Acosta CRM page and writes that update there. The information lives in one place (Obsidian braindump) and dies there. Same gap exists for newly-created Notion pages with no follow-through, for new Meeting Notes DB entries synced from Granola without a manual `/capture-meeting` invocation, and for context buried in the broader Obsidian vault that never reaches the right Notion compartment. `/sync-sweep` closes all four gaps with one resolution+routing engine.

## Scope (v0.2 — expanded from v0.1)

**Four input classes, one resolution engine:**

| Input class | What it sees | Action |
|---|---|---|
| **A. Braindump** | `vault/daily/YYYY-MM-DD.md` `## Braindump` section | Entity-resolve mentions → append `## Latest:` section to matching Notion page body |
| **B. Obsidian vault** | Files in `vault/CardioPro/`, `Labaide/`, `Nestmate/`, `United IPA/`, `Notes to self/`, `notes/`, `inbox/` edited in last 24h | Entity-resolve + LLM-route content into matching Notion compartment (CRM page body, Activity Log row, or new Master Task) |
| **C. New Meeting Notes DB pages** | `/v1/data_sources/22ba3158.../query` for pages created in last 24h | If page has no `Related Tasks` populated, run /capture-meeting's parse-and-route pipeline auto: parent `[Meeting]` task + subtasks per action item + back-link to recap |
| **D. New Notion pages workspace-wide** | `/v1/search` filtered to `last_edited_time ≥ 24h ago`, excluding A/C above | If page is empty / stub, prompt Aaron inline for one-line context (per his Q4 answer — actively apply learned context, not read-only surface) |

All four classes converge into the same Step 8 trust gate. Aaron sees one consolidated list of "things /sync-sweep wants to write" per run, organized by source class.

**Why not split into four skills?** Aaron explicitly said: "I don't want to have to keep adding new skills." All four share the same entity resolution + Notion-search + trust-gate + idempotency machinery. Splitting would duplicate ~70% of the code. The risk is mega-node anti-pattern (AAC §1), so the process map (§3) keeps each input class as its own clearly-bounded node, not a soup.

**v1 hard out-of-scope (defer to future):**
- Obsidian annotations next to existing checkboxes (the "Alex Acosta scenario from /start-day") — needs a diff against morning briefing. Defer to v2.
- Bidirectional Notion-page-edits → Obsidian. One direction only in v1: outside → Notion.
- Real-time triggers. v1 is batch (on-demand + `/end-day` final step + post-MVE schedule).

---

## 1. Work object

**Four input classes (see Scope section above), one output unit type.**

**Output unit:** one of these, per resolved item:
- `## Latest: <one-line summary>` section prepended (under a fixed `## Latest:` divider) inside an existing Notion page body, with prior dated sections below it in reverse-chronological order.
- New Master Tasks row (when input is class C — new meeting) following `/capture-meeting`'s `[Meeting]` parent + subtask pattern.
- Activity Log row (when source phrase contains a decision verb: `decided | agreed | approved | finalized | going with | confirmed`).

**Cardinality (per run, typical day):**
- Class A (braindump): 0–8 mentions → 0–6 successful appends
- Class B (obsidian recent edits): 0–4 files → 0–4 routed updates (each file may produce multiple)
- Class C (new meeting notes): 0–3 new meetings/day → 0–3 parent+subtask trees
- Class D (new notion pages no context): 0–2/day → 0–2 inline prompts

Worst-case ~20 staged items per run. Trust gate paginates if >10.

**Idempotency unit:** `action_id` per item per source line. Re-running on the same braindump / same Obsidian file / same meeting page is a no-op for already-applied items.

---

## 2. Mode

**AAC mode: Replace.**

Replaces Aaron's manual process of: "scroll Notion → search for Alex Acosta → open the page → scroll to bottom → type the update → date it → save." That manual process happens 0 times per day today, because it never happens — the update gets lost. So Replace here is replacing "the gap" rather than "an existing workflow."

Not Augment (no parallel human process to preserve). Not Extend (not adding a new capability on top of an existing skill — though `/end-day` calls it).

---

## 3. Process map

```
                                ┌─────────────────────────────┐
                                │  Trigger                    │
                                │  - /end-day Step 9 (final)  │
                                │  - standalone /sync-sweep   │
                                │  - scheduled (post-MVE)     │
                                └──────────────┬──────────────┘
                                               ▼
                                ┌─────────────────────────────┐
                          ┌─────│  Step 0: Mode check         │── locked ──▶ refuse
                          │     └──────────────┬──────────────┘
                          │                    ▼
                          │     ┌─────────────────────────────┐
                          │     │  Step 1: Pull source        │
                          │     │  material (braindump +      │
                          │     │  Notion 24h new pages)      │
                          │     └──────────────┬──────────────┘
                          │                    ▼
                          │     ┌─────────────────────────────┐
                          │     │  Step 2: PHI input gate     │── PHI ────▶ refuse + log
                          │     │  (scripts/phi_scan.sh)      │
                          │     └──────────────┬──────────────┘
                          │                    ▼
                          │     ┌─────────────────────────────┐
                          │     │  Step 3: Entity extraction  │
                          │     │  (C-element — LLM)          │
                          │     │  output: list of mentions   │
                          │     │  with confidence + source   │
                          │     │  line cite                  │
                          │     └──────────────┬──────────────┘
                          │                    ▼
                          │     ┌─────────────────────────────┐
                          │     │  Step 4: Workspace-wide     │
                          │     │  /v1/search per entity      │
                          │     │  (D-element — Notion API)   │
                          │     └──────────────┬──────────────┘
                          │                    ▼
                          │     ┌─────────────────────────────┐
                          │     │  Step 5: Match scoring +    │
                          │     │  disambiguation queue       │
                          │     │  - high conf single match → │
                          │     │    auto-stage               │
                          │     │  - multi-match or low conf  │
                          │     │    → A-element (Aaron picks)│
                          │     │  - no match → Uncategorized │
                          │     └──────────────┬──────────────┘
                          │                    ▼
                          │     ┌─────────────────────────────┐
                          │     │  Step 6: Idempotency check  │
                          │     │  (action_id.sh check)       │── already ──▶ skip
                          │     └──────────────┬──────────────┘  applied
                          │                    ▼
                          │     ┌─────────────────────────────┐
                          │     │  Step 7: Stage payloads in  │
                          │     │  .context/sync-sweep-*.json │
                          │     └──────────────┬──────────────┘
                          │                    ▼
                          │     ┌─────────────────────────────┐
                          │     │  Step 8: Trust gate         │── Aaron ──▶ no writes
                          │     │  (display ALL proposed      │   declines
                          │     │  appends, per-item approve) │
                          │     └──────────────┬──────────────┘
                          │                    ▼
                          │     ┌─────────────────────────────┐
                          │     │  Step 9: Apply PATCHes      │
                          │     │  /v1/blocks/{id}/children   │── 5xx ────▶ DLQ
                          │     │  one per approved item      │           (sync-sweep-
                          │     └──────────────┬──────────────┘            retry-queue.yaml)
                          │                    ▼
                          │     ┌─────────────────────────────┐
                          │     │  Step 10: Archive + stamp   │
                          │     │  mv .context/X.json →       │
                          │     │  .context/applied/X-DATE    │
                          │     │  + action_id stamp          │
                          │     └──────────────┬──────────────┘
                          │                    ▼
                          │     ┌─────────────────────────────┐
                          └────▶│  Step 11: Telemetry +       │
                                │  summary                    │
                                └─────────────────────────────┘
```

**Hidden queue (drawn, not implicit):** `state/sync-sweep-retry-queue.yaml` — per the `feedback_reversed_gtask_sync.md` pattern. Each entry: `entity_name`, `notion_page_id`, `payload`, `attempts`, `last_status`, `first_failed`. `/start-day` surfaces this queue's depth in its system flags.

**Implicit decisions made explicit:**
- "When is a match strong enough to auto-stage?" → confidence floor in §8.
- "When does an update get an Activity Log row in addition to the page-body append?" → see §11 state machine (only when the braindump phrase contains a decision verb: "decided/agreed/approved/finalized").
- "What counts as a Notion page in scope?" → §6 input schema (Master Tasks, Provider CRM, Activity Log, Meeting Notes, AND topic pages anywhere in the workspace — same scope as Granola sync-gap workspace search per `[[feedback-granola-routing]]`).

---

## 4. Nodes + runtimes

| Step | Node | Runtime | Why |
|---|---|---|---|
| 0 | Mode check | D | Read `state/coo_mode.yaml`. Same pattern as all other skills. |
| 1 | Pull source material | D | File read + Notion list query, both unambiguous. |
| 2 | PHI input gate | D | `scripts/phi_scan.sh` is regex-based. AAC GATED input gate. |
| 3 | Entity extraction | **C** | Natural-language input, ambiguous (need to disambiguate "Alex" → which Alex), reversible (we stage before writing). This is the only AI-runtime node in the skill. |
| 4 | Workspace-wide search | D | `/v1/search` is deterministic; pagination, hit collection. |
| 5 | Match scoring + disambiguation | D for scoring, **A** for low-conf | Scoring formula is deterministic (title similarity + workspace match + recency + content-type weighting). Disambiguation when multiple matches or confidence < floor → Aaron picks. AAC: ambiguous decision → downgrade to A or D. |
| 6 | Idempotency check | D | `scripts/action_id.sh check`. Pure file lookup. |
| 7 | Stage payloads | D | Write JSON to `.context/`. Pure I/O. |
| 8 | Trust gate | H | Aaron approves. AAC GOVERNED. |
| 9 | Apply PATCHes | D | `curl -X PATCH /v1/blocks/{id}/children` with the pre-staged payload. |
| 10 | Archive + stamp | D | `mv` + `action_id.sh stamp`. |
| 11 | Telemetry | D | `scripts/telemetry.sh` append. |

**The only C element is Step 3.** Same shape as `/start-day` Step 7 per the existing audit — most of the skill is D dressed as a Claude conversation. The 5 disciplines apply to Step 3 only.

**No H element beyond the trust gate.** v1 doesn't do judgment-level synthesis — it does mechanical "find entity, append dated section, stop." Decisions stay with Aaron at the trust gate.

---

## 5. Edges

| Edge | Trigger | Latency budget | Volume estimate | Contract |
|---|---|---|---|---|
| Trigger → Step 0 | cron / /end-day Step 9 / manual | <1s | 1–3/day (one /end-day call + 1–2 ad-hoc) | none |
| Step 1 → Step 2 | always | <2s | 1:1 | raw braindump text + new-page list |
| Step 2 → Step 3 | clean | <100ms | 1:1 | same text |
| Step 2 → REFUSE | PHI detected | <100ms | rare | append to `logs/_phi_refusals.jsonl` |
| Step 3 → Step 4 | extraction returns ≥1 entity | <8s (LLM call) | 1 call per run, 0–8 entities | entity list with conf + source line |
| Step 4 → Step 5 | per entity | <2s per /v1/search call | 0–8 search calls per run | candidate matches list |
| Step 5 → Step 6 (auto-stage) | conf ≥ 0.85 AND single match | <50ms | majority of entities | stage decision |
| Step 5 → Step 5b (disambig) | conf < 0.85 OR multi-match | wait on Aaron | minority of entities | trust-gate question |
| Step 6 → SKIP | action_id already stamped | <50ms | re-runs only | log "idempotent skip" |
| Step 6 → Step 7 | fresh | <50ms | typical | stage payload |
| Step 7 → Step 8 | always | <50ms | 1:1 | `.context/sync-sweep-*.json` files |
| Step 8 → Step 9 (approve) | Aaron picks A or per-item Y | wait on Aaron | 1 per run | approved item list |
| Step 8 → terminal (decline) | Aaron picks C | wait on Aaron | rare | no writes; archive payloads to `.context/applied/<name>-declined-<date>.json` for audit |
| Step 9 → DLQ | PATCH 5xx | <60s timeout | rare; bursty (Notion outage) | retry-queue entry |
| Step 9 → Step 10 | 200 OK | <100ms | typical | success record |
| Step 10 → Step 11 | always | <50ms | 1:1 | run summary |

**SLA budget for full run:** ~30s in the common case (3 entities, all auto-stage, all approved as batch). Worst case with disambiguation + 8 entities + 1 retry: ~3 minutes.

---

## 6. Input schema

```yaml
trigger:
  source: "end-day-final-step" | "standalone-invocation" | "scheduled"
  run_id: "ss-YYYYMMDD-HHMM"   # ss prefix = sync-sweep
  mode: "observe" | "draft" | "approved" | "auto" | "locked"   # from state/coo_mode.yaml

inputs:
  braindump:
    file_path: "vault/daily/YYYY-MM-DD.md"
    extracted_section: "## Braindump → next ##"   # if section missing, run is a no-op
    raw_text: <string>

  notion_recent_pages:
    # New OR last_edited Notion pages in the last 24h, across in-scope databases.
    # Listed as candidates to also receive an update IF braindump mentions them.
    sources_queried:
      - master_tasks      # data_source 528d24b8-...
      - provider_crm      # data_source ae0a3158-...
      - activity_log      # data_source 3db174bf-...
      - meeting_notes     # data_source 22ba3158-...
      - workspace_search  # /v1/search, no DB filter — catches topic pages, account pages, etc.
    items: <list of {page_id, title, parent, last_edited_time, workspace}>

  config:
    file: "config/sources.yaml"
    notion_api_version: "2025-09-03"

  state:
    retry_queue: "state/sync-sweep-retry-queue.yaml"   # may be empty
    applied_index: ".context/applied/"                  # for idempotency
```

**Input gate (AAC GATED):** Step 2 PHI scan rejects raw braindump before LLM extraction. Same `scripts/phi_scan.sh` already used in `/capture-meeting` — no new code.

---

## 7. Output schema

```yaml
per_entity_mention:
  source_line: <int>             # line number in vault/daily/YYYY-MM-DD.md
  source_text: <string>          # exact braindump phrase that triggered this
  entity_canonical: <string>     # "Alex Acosta" (the resolved name)
  entity_aliases_tried: [<str>]  # ["Alex", "Acosta", "Alex Acosta"]
  confidence: <float 0.0-1.0>    # entity-extraction confidence
  input_class: "A" | "B" | "C" | "D"  # which input class triggered this (gates the per-class floor)
  section_context: <string|null> # E1 — nearest preceding section header (e.g. "Nestmate") or null
  line_business_signal: <string|null>  # E1 — business keyword found in current line (e.g. "lab") or null
  override_applied: <bool>       # E1 — true when line_business_signal overrode section_context
  context_window: [<str>]        # E1 — 2-3 surrounding lines used for ambiguous mentions
  matches:
    - page_id: <uuid>
      page_title: <string>
      parent_db: <string>        # "Provider CRM" | "Master Tasks" | "topic-page" | …
      workspace: <string>        # "Nestmate" | "Lincoln Lab" | …
      match_score: <float>       # title_similarity * 0.5 + workspace_match * 0.3 + recency * 0.2
      url: <string>
  resolution: "auto-stage" | "disambiguation-needed" | "no-match"
  payload:                       # only if resolution == "auto-stage" or post-disambig
    page_id: <uuid>
    append_section_heading: "## YYYY-MM-DD — <one-line summary>"
    append_body: <markdown string, ≤500 chars>
    activity_log_row: <null | {decision_summary, workspace, date}>   # only if decision verb detected
  action_id: "sync-sweep:<page_id_short>:YYYY-MM-DD:<8-char-hash>"

per_run_summary:
  entities_extracted: <int>
  auto_staged: <int>
  disambiguated: <int>
  no_match: <int>
  skipped_idempotent: <int>
  approved: <int>
  written: <int>
  failed: <int>
  status: "ok" | "partial" | "refused" | "failed"
  duration_ms: <int>
```

**Output gate (AAC GATED):** Step 5 enforces a confidence floor AND a match-score floor — items below either floor cannot auto-stage; they must route to disambiguation. Output schema rejects any `resolution: "auto-stage"` without a populated `payload`.

---

## 8. C-element specs (Step 3 — Entity extraction)

**Model:** Claude (already in-process). No separate API call required when /sync-sweep is invoked from inside Claude Code; the extraction is a structured prompt to "self".

**Prompt skeleton:**

```
You are extracting entity mentions from Aaron's daily-note braindump.

In-scope entities (anything Aaron tracks in Notion):
- people (providers, reps, business contacts) — e.g. "Alex Acosta", "Dr Gordin", "Ahmed"
- accounts / clinics — e.g. "AFC Urgent Care", "Sovereign Phoenix", "Essen Healthcare"
- deals / programs — e.g. "the Roosevelt cardio meeting", "AHBD/LDX integration"
- meetings (recurring topics) — e.g. "Cardio Pro Rollout", "SP weekly"

Out of scope:
- generic verbs ("called", "emailed", "scheduled")
- Aaron himself
- vague references ("the doctor", "they")

For each entity, return:
{
  "entity_canonical": <string>,
  "aliases": [<short forms used in this line>],
  "source_line": <int>,
  "source_text": <verbatim line>,
  "confidence": <0.0-1.0>,
  "update_summary": <one-line synthesis of what to append, e.g. "called back; pushing Roosevelt cardio meeting to Friday">
}

Confidence rubric:
- 0.95+: full name + business context match ("Alex Acosta finally called back")
- 0.85:  partial name but unambiguous in context ("Acosta pushing Friday")
- 0.70:  first name + business context ("Alex from Roosevelt cardio")
- < 0.70: ambiguous — return anyway with low conf; Step 5 routes to disambig
```

**Confidence floor (per AAC §2.3 v1.1, refined 2026-05-19 eng review D2):**
- **Class A (braindump append) — reversible-bounded**: floor = **0.85** to auto-stage. Cleanup is one Notion UI block-delete (~5s).
- **Class B (Obsidian → existing Notion compartment) — reversible-bounded**: floor = **0.85** to auto-stage. Same cleanup.
- **Class C (Meeting Notes auto-processing — creates new Master Tasks + Google Tasks mirror) — irreversible-bounded**: floor = **0.92** to auto-stage. Cleanup requires Notion delete + subtask sweep + Google Tasks mirror delete = 30s+ manual work. AAC v1.1 §2.3 table maps this consequence class to 0.92.
- **Class D (new Notion page active write) — reversible-bounded**: floor = **0.85** to auto-stage. Cleanup is one block-delete.
- Below floor: disambiguation gate (A-element).

This per-class threshold is load-bearing for safety. Class C in particular: a wrong-meeting auto-process could create 3-5 phantom tasks across Notion + Google Tasks that Aaron would have to hunt down. The 0.92 floor sends borderline meetings to the trust gate where Aaron taps approve/reject; the cost of a tap is much smaller than the cost of cleanup.

**Source citation requirement (AAC GROUNDED):** every entity in extraction output MUST include `source_line` + `source_text`. The trust gate displays both. Aaron sees: *"Alex Acosta → Provider CRM page X (conf 0.92, line 47: '...')"*.

**Hard refuse classes (AAC BOUNDED):**
- Entity name contains PHI patterns leaked through (DOB-like, SSN-like) → fail closed, log to `logs/_phi_refusals.jsonl`.
- `update_summary` contains a payment instruction (amount + send/wire/transfer) → refuse; surface to Aaron as "this looked like a payment instruction; routing to Activity Log only, not to a CRM page."

---

## 9. H-element specs (Step 8 trust gate + Step 5 disambiguation)

### Step 5 disambiguation (per-entity gate)

**Judgment question:** *"Which Notion page is this braindump line about?"*

**Triggered when:** Step 5 found ≥2 candidate matches OR top match's `match_score` < 0.65.

**Display per entity:**

```
Line 47: "Alex Acosta finally called back — pushing Roosevelt cardio to Friday"
Extracted: entity="Alex Acosta", confidence=0.78

Candidate Notion pages:
  [A] Alex Acosta — Provider CRM (Nestmate)    last edited 2026-05-12   match: 0.81
      url: https://notion.so/...
  [B] Alex Acosta meeting — Meeting Notes      last edited 2026-04-30   match: 0.62
      url: https://notion.so/...
  [C] Roosevelt Cardio + Acosta — topic page   last edited 2026-05-15   match: 0.71
      url: https://notion.so/...

Pick one, or [N] none / skip this mention.
```

**Metrics tracked:** disambiguation choice + match score per choice. Telemetry over time tells us "Aaron picks the topic-page version 80% of the time when CRM-vs-topic-page tie" → in v2, weight that into the scoring formula.

### Step 8 trust gate (per-run, batched)

**Judgment question:** *"Apply these updates to Notion?"*

**Options (matches /capture-meeting Step 5 + /end-day Step 7 conventions):**
- **A) Apply all** — PATCH every staged update.
- **B) Select specific items** — numbered list, Aaron enters "1,3,5".
- **C) Just save the summary** — no Notion writes; payloads still get archived to `.context/applied/<name>-declined-<date>.json` for audit.
- **D) Edit first** — Aaron rewrites a specific `append_body` before approval.

---

## 10. Memory

**Reads:**
- `state/coo_mode.yaml` — current mode (Step 0).
- `state/priorities.yaml` — to enrich entity matching ("Alex Acosta" appearing in `awaiting:` confirms the Provider CRM page is the right target).
- `state/sync-sweep-retry-queue.yaml` — past failures, retry before staging new.
- `.context/applied/sync-sweep-*` — idempotency check.
- `config/sources.yaml` — data-source IDs, workspace_values, business keywords.
- `vault/daily/YYYY-MM-DD.md` — input.

**Writes:**
- `.context/sync-sweep-<run_id>.json` — staged payload (Step 7).
- `.context/applied/sync-sweep-<run_id>-<date>.json` — archived after PATCH (Step 10). Per `[[feedback-context-cleanup]]`, the date suffix is when the write landed.
- `state/sync-sweep-retry-queue.yaml` — append on failure.
- `logs/_telemetry.jsonl` — one row per run (Step 11).
- `logs/_phi_refusals.jsonl` — append on PHI gate trip.
- `logs/YYYY-MM-DD.md` — one-line audit per applied update.

**No new memory file types.** All persistence reuses existing AAC infrastructure (the `.context/applied/` pattern, the retry-queue yaml shape, the telemetry jsonl).

---

## 11. State machine

```
[idle]
   │
   ├─trigger──▶ [reading-inputs]
   │              │
   │              ├─braindump missing──▶ [no-op exit]    (logs "no braindump section today")
   │              │
   │              └─braindump present──▶ [phi-scan]
   │                                       │
   │                                       ├─PHI──▶ [refuse + log]──▶ [terminal]
   │                                       │
   │                                       └─clean──▶ [extracting]
   │                                                    │
   │                                                    └──▶ [searching]
   │                                                            │
   │                                                            └──▶ [scoring]
   │                                                                   │
   │                                                                   ├─all auto──▶ [staging]
   │                                                                   │
   │                                                                   └─some need disambig──▶ [waiting-on-aaron-disambig]
   │                                                                                            │
   │                                                                                            └──▶ [staging]
   │                                                                                                    │
   │                                                                                                    └──▶ [waiting-on-aaron-trust-gate]
   │                                                                                                            │
   │                                                                                                            ├─decline──▶ [archive-declined]──▶ [telemetry]──▶ [terminal]
   │                                                                                                            │
   │                                                                                                            └─approve──▶ [writing]
   │                                                                                                                          │
   │                                                                                                                          ├─all OK──▶ [archive + stamp]──▶ [telemetry]──▶ [terminal]
   │                                                                                                                          │
   │                                                                                                                          └─some 5xx──▶ [retry-queue append]──▶ [partial telemetry]──▶ [terminal]
```

**Decision-verb side branch (Step 5b, inside [scoring]):** if `update_summary` contains a decision verb (`decided | agreed | approved | finalized | going with | confirmed`), the staged payload includes an additional Activity Log row (using the same shape as `/capture-meeting` Step 6b). This routes decisions to the canonical Activity Log per "Route, don't dump" key principle #5 — the page-body append still happens, but the decision also gets indexed.

---

## 12. Data contract (all 8 constraint dimensions)

| Dimension | Value | Implication |
|---|---|---|
| 1. Decision class | Natural-language input (braindump), unambiguous-after-disambig action (append block) | Step 3 = C; Step 5 disambig = A; Step 9 write = D |
| 2. Action consequence | **Reversible-bounded** — appending a block to a Notion page is undoable in the Notion UI in ~5 seconds. Worst case: an extra section in a page Aaron deletes. | C-eligible. Confidence floor 0.85 per AAC §2.3 v1.1. |
| 3. Input type | Natural-language (braindump prose) | Step 2 PHI scan + Step 3 entity extraction with confidence scoring |
| 4. Volume × stakes | 0–8 entities/day × low-medium stakes (data-loss prevention, not patient safety) | Per-run cost ceiling: ~$0.05 in tokens (one LLM call, ~3k input + ~1k output). Daily cap: ~$0.50 across all triggers. |
| 5. Data classification | **Internal + business confidential.** Braindump contains provider names, account names, internal pricing discussions. No PHI by policy (PHI scan enforces). | Cannot ship raw braindump to third-party LLMs without BAA. In-process Claude is acceptable per Anthropic's data use policy. |
| 6. Provider contract | Anthropic (Claude Code in-process). Existing trust posture covers this skill. | No new vendor onboarding required. |
| 7. Data residency | Local (laptop). Pre-MVE: no cloud. Post-MVE: Hermes/Railway per `[[project-hermes-railway-default]]`. Both US-resident. | OK for v1. |
| 8. Retention + deletion | `.context/applied/sync-sweep-*` kept indefinitely (audit trail). `logs/_telemetry.jsonl` rolled at 90 days same as logs. PHI refusal log kept forever. | No new retention infra. |

**Hard stop check:** none of the 8 dimensions push this out of C-eligibility for Step 3. The reversible-bounded action consequence is the load-bearing dimension — if appending a Notion block were irreversible-unbounded (e.g. sending an email to Alex Acosta), Step 3 would have to downgrade to A.

---

## 13. Cost model

**Per run:**
- Entity extraction (Step 3): ~3k input tokens (braindump + prompt) + ~1k output tokens. At Opus rates ≈ $0.05/run. At Sonnet rates ≈ $0.012/run. **Recommendation: Sonnet for v1.** The extraction task is structured-output, low-judgment; Opus is overkill.
- Notion API calls: free (within rate limits). ~8 search calls + 0–6 PATCH calls per run.
- gws CLI calls: free.

**Per day (worst case):** 3 runs × $0.05 = $0.15/day → ~$4.50/month.
**Per day (typical):** 1 run × $0.012 (Sonnet) = $0.012/day → ~$0.36/month.

**Cost alarm threshold:** if monthly sync-sweep cost exceeds $10, something is wrong (probably extraction prompt looped or braindump exploded in size). `/weekly-review` (planned) will read `logs/_telemetry.jsonl` and flag this.

**Token attribution:** every telemetry row records `input_tokens`, `output_tokens`, `model_id`, `estimated_cost_usd`. This is the OBSERVED discipline applied to cost.

---

## 14. Latency SLAs

| Percentile | Budget | Why this matters |
|---|---|---|
| p50 | <30s | When called from `/end-day` Step 9, Aaron is still at the terminal. <30s = no perceived delay. |
| p95 | <90s | One full disambiguation interaction. Acceptable as a one-off. |
| p99 | <3 min | Multi-entity disambiguation + 1 Notion retry. Past this, something is wrong. |

**SLA violation logging:** every run records `duration_ms`. Telemetry analysis flags p95 > 90s for two consecutive days.

**Hard timeout:** Notion `curl --max-time 60` per call (matches existing skills). LLM extraction has a soft 20s timeout; on timeout, fall back to "extract only nouns matching `config/sources.yaml` workspace keywords" — a deterministic regex pass that gets the high-value cases (clinic names, recurring meeting names) even if Claude is slow.

---

## 15. Failure modes + recovery

| Failure | Detection | Recovery | Telemetry status |
|---|---|---|---|
| Mode = locked | Step 0 exits | Refuse silently | not logged |
| Mode = observe | Step 0 sets SKIP_WRITES=1 | Run all of Steps 1–8 display, skip Step 9 writes | status=`ok`, write_count=0 |
| Braindump section missing | Step 1 | No-op exit. Don't error. Append "no braindump today" to log. | status=`ok`, entities=0 |
| PHI detected | Step 2 | Refuse parsing. Append to `logs/_phi_refusals.jsonl`. | status=`refused` |
| Entity extraction returns 0 | Step 3 | No-op exit. Log "extracted 0 entities". | status=`ok`, entities=0 |
| `/v1/search` 5xx | Step 4 | Skip this entity, mark as `no-match`. Surface in summary. | status=`partial` |
| All entities `no-match` | Step 5 | Display summary, no trust gate needed, exit. | status=`ok`, written=0 |
| Aaron declines (Option C) | Step 8 | Archive payloads to `.context/applied/<run_id>-declined-<date>.json`. No retry queue. | status=`ok`, declined=N |
| PATCH 5xx during write | Step 9 | Append entry to `state/sync-sweep-retry-queue.yaml`. Continue with remaining writes. | status=`partial`, failed=N |
| PATCH 401 (token expired) | Step 9 | STOP all writes. Surface to Aaron: "NOTION_API_TOKEN expired — rotate per .secrets/notion.env". | status=`failed` |
| PATCH 404 (page deleted between Step 4 and Step 9) | Step 9 | Skip this item, mark as `stale-target`. Log only. | status=`partial`, stale=N |
| Idempotency check matches | Step 6 | Skip this entity, log "idempotent skip". | status=`ok`, skipped_idempotent=N |
| Retry queue depth ≥ 3 days old | Surfaced by `/start-day` | `/start-day` system flag: "sync-sweep DLQ has N items, oldest M days — Notion API persistently flaky for these IDs" | n/a (read-only surfacing) |

**Cardinal rule:** never retry automatically inside a single run. Failures go to the queue; next `/sync-sweep` invocation retries with bounded attempts (max 3 attempts per entry, then surface to Aaron).

---

## 16. Ownership + operations

**Named owner:** Aaron.

**Weekly trace review (per AAC §7):**
- Read last 7 days of `logs/_telemetry.jsonl` filtered to `skill: sync-sweep`.
- Check: entity extraction false-positive rate (entities extracted but no Notion match — could be Aaron's new names or could be extraction over-firing), disambiguation rate (high = scoring formula needs tuning), DLQ depth.
- Time required: ~10 min/week, folded into `/weekly-review` skill when built.

**Monthly eval refresh:**
- Take the 10 most recent braindumps. Aaron manually labels entities → ground truth. Compare to extraction output. Track precision + recall over time.
- Catches drift: e.g. if Aaron starts using "Yili" as shorthand for "Dr Yili Huang" and extraction stops catching it.

**Quarterly model re-bake:**
- Re-evaluate Sonnet vs. Opus vs. Haiku for entity extraction. Cost may have shifted; capability may have shifted. Lock the choice for the next quarter.

**Incident runbook:**
- **SEV-1 (data corruption):** wrong-page append landed. Response: identify via `.context/applied/sync-sweep-*` audit; revert in Notion UI; add the misidentified entity to a `state/sync-sweep-aliases.yaml` block-list so it routes to disambig forever.
- **SEV-2 (partial outage):** Notion API down, DLQ filling. Response: run `/sync-sweep --retry-only` mode (post-v1) once API recovers.
- **SEV-3 (cost spike):** monthly cost > $10. Response: read `logs/_telemetry.jsonl`, find the run with anomalous token use, root-cause (probably a braindump pasted with a 10-page transcript).
- **SEV-4 (latency drift):** p95 > 90s for 2 consecutive days. Response: check if Notion API latency is the cause; if so, accept; if not, profile the LLM call.

**Change management path:**
- Spec changes → update this file → review by Aaron → commit.
- Prompt changes → shadow run against last 7 days of braindumps → require ≥90% extraction agreement → promote.
- Confidence-floor changes → trial for 7 days in `mode: observe` → review delta in disambig rate → promote.

**Migration eligibility (v1.1):** this skill is **NOT terminal** — every C-element decision could in principle be migrated to D if Aaron's entity vocabulary stabilizes enough to be regex-matched. Reason class: "judgment that may stabilize." Re-evaluate quarterly.

---

## Locked design decisions (Aaron's picks, 2026-05-19)

1. **Append position: TOP with `## Latest:` divider (hybrid).** Latest update lives under a fixed `## Latest:` heading at the page top. Prior dated sections sit below it in reverse-chronological order (newest at top of the "history" stack). Implementation: every PATCH first reads existing children, locates the `## Latest:` heading block (creating it if absent), demotes the prior "Latest" payload to a dated `## YYYY-MM-DD — <summary>` section beneath it, and inserts the new content under the `## Latest:` heading. More code than bottom-append, but matches Aaron's read pattern: open page → see freshest context immediately.

**Pagination edge case (flagged by sync-sweep-lead Phase 1 review):** Notion's `/v1/blocks/{id}/children` paginates at 100 blocks. A long-running CRM page (Aaron's high-activity accounts) may exceed this. The `## Latest:` helper MUST walk all pages via `next_cursor` when reading children — partial reads risk creating a duplicate `## Latest:` heading because the helper would miss the existing one past block 100. Implementation requirement: full-walk read before any write decision. Cost is one extra GET per ~100 block boundary; affordable.

**Race condition mitigation (D1, locked 2026-05-19 eng review):** Read-then-write is a TOCTOU race. Two concurrent writes (e.g., Aaron editing the page in Notion app + scheduled /sync-sweep run) can both observe "no `## Latest:` heading" and both insert one. Mitigation: **verify-after-PATCH + auto-repair**. After every PATCH, do a follow-up GET of the page's first ~20 children. If two `## Latest:` headings exist, promote the older to a dated section (`## YYYY-MM-DD — auto-merged on race detect`) and keep the new one as Latest. Cost: one extra GET (~150ms) per write, well below Notion's 3 req/s sustained rate limit. Acceptable trade for eliminating user-visible duplicates.

2. **Daily-note marker: strikethrough + sync comment.** After a successful PATCH, /sync-sweep edits `vault/daily/YYYY-MM-DD.md` to wrap the source line: `~~Alex Acosta finally called back...~~ <!-- synced to notion:abcd1234 -->`. Two benefits: visible scan ("what already landed?"), and future `/sync-sweep` runs skip already-synced lines via the `<!-- synced -->` comment regex before even calling LLM extraction. Idempotency stamp at `.context/applied/` is the durable check; daily-note marker is the human-legible one.

3. **First-name extraction: hybrid using single-dept person list.** Per memory `feedback_person_routing.md`: names like `MDland`, `Alam` (Lab); `Sheila`, `EMU` (Nestmate); etc. are safe single-dept overrides. Apply that list to first-name extraction — if the bare first name maps to a known single-dept person, score conf 0.85 and auto-stage. Everyone else (Cyrus, Ilene, Ahmed, Alex — names spanning departments) stays conservative at conf ~0.65 and routes to disambig. The override list lives in `config/sources.yaml` under a new `entity_aliases:` section so Aaron can edit it.

4. **New Notion pages (no braindump mention): ACTIVE write, not read-only.** *Aaron's quote:* "You should take what you have learned from it and apply it into the necessary compartment." When /sync-sweep finds a new Notion page in the last 24h with no braindump context, it consults the Obsidian vault (class B input) for any recent file matching the page's entity name. If a match exists with substantive content, /sync-sweep stages a routed update into the new Notion page using that Obsidian content. If no Obsidian match exists, /sync-sweep prompts Aaron inline for a one-line context. This is a scope expansion from v0.1's "read-only surface" — Aaron explicitly upgraded it.

## Extras locked for v0.2 (Aaron's picks 2026-05-19)

All five additional behaviors fold into v0.2. Order below matches build sequence:

### E1. Section-header business prior (SOFT prior with line-level override)

**E1 — Section-header soft prior + line-level override (corrected 2026-05-19 from fixtures-worker finding)**

1. The nearest preceding `##` / `###` section heading sets a default business prior for items in that section.
2. A line-level business-keyword match (against `config/sources.yaml` `calendar_business_keywords`) **overrides** the section prior for that line.
3. Multiple business keywords on a single line → flag the item for disambiguation rather than auto-routing.
4. Confidence reflects section+line agreement (high when both point the same way; drops to ~0.70 when line overrides section).

Motivating fixtures (see `state/sync-sweep-eval-fixtures.yaml`):
- **Dr Tim ENG** — line carries "lab" keyword inside a Nestmate section → routes to Lincoln Lab, conf ~0.72.
- **Dr Rookwood** — extracted correctly only when ±2 surrounding lines feed the LLM extraction context.
- **Ahmed** — multi-dept person with no line keyword → routes to disambig, conf ~0.65.

Supersedes the absolute "section header beats contact name" form previously cited from `feedback_brainstorm_to_execution.md`.

---

**Superseded form (kept for traceability):** Originally specced as "section header beats contact name" per `[[feedback-brainstorm-to-execution]]`, but the Dr Tim ENG fixture (2026-05-13 line 142) shows the absolute form is wrong: he appeared in a Nestmate section, but the line read "successfully closed for lab" — correct routing is Lincoln Lab. Line-level signal MUST be able to override the section prior. The absolute "section header beats contact name" rule is no longer authoritative; rules 1–4 above replace it.

**Context window:** extraction also reads the previous 2-3 lines for context. The Dr Rookwood fixture (2026-05-18) has no business keyword in its own line — the Nestmate signal lives in surrounding phrasing ("her book away from Quest/LabCorp split"). Line-isolated extraction misses these.

Implementation: deterministic regex pass on raw braindump for section headers + line-keyword scan BEFORE the LLM call. Output schema gains `section_context`, `line_business_signal`, and `override_applied` per entity.

### E2. Disambiguation memory

After Aaron picks a candidate at the disambig gate (Step 5), persist the resolution:

```yaml
# state/sync-sweep-resolutions.yaml
resolutions:
  - mention_text: "Alex Acosta"
    resolved_page_id: "23ba3158-..."
    resolved_page_title: "Alex Acosta — Provider CRM"
    workspace: "Nestmate"
    confirmed_at: "2026-05-19"
    confirmation_count: 3
```

Step 5 scoring reads this file first. Match in resolutions → boost match_score by +0.2. After 3 confirmations of the same mention→page mapping, promote to `entity_aliases:` in `config/sources.yaml` and remove from resolutions (graduates from learned to authoritative).

### E3. priorities.yaml integration

When class C (meeting notes auto-processing) creates a new Master Task, ALSO write a corresponding entry to `state/priorities.yaml`:

- If task title contains decision-verb signal → no priorities entry (decision is closed)
- If task is owned by Aaron with a due date → `carry_forward:` entry with `source: notion`, `source_id: <task_page_id>`
- If task is owned by Aaron with no due date but blocking someone else → `awaiting:` entry
- If task is owned by a teammate → no priorities entry (it's on their plate, not Aaron's)

Closes the seam where /capture-meeting creates tasks but /start-day doesn't know about them until they age into stale.

### E4. Granola URL in braindump

If the braindump contains a Granola URL pattern (`https://notes.granola.ai/...` or `https://notion.so/...` matching a Meeting Notes DB page), treat the URL as a class C trigger. Extract the Meeting Notes page_id, fetch it, run the same auto-processing pipeline as class C above.

Detection regex: `https?://(notes\.granola\.ai|notion\.so/[a-f0-9-]{32,36})` per line. The URL line itself in the braindump gets strikethrough'd on success same as any other synced line.

### E4b. Class A vs Class D collision rule (locked 2026-05-19 eng review D3)

When a braindump mention (class A) AND a new empty Notion page in the last 24h (class D) both resolve to the same canonical entity (e.g., both about "Alex Acosta"), the conflict is resolved by **class A wins**: append braindump content to the existing entity page (the one with history). The new empty page surfaces in the trust gate as:

```
⚠️ Duplicate stub detected: "Alex Acosta" — Notion page <id> created <when> by you, empty body.
   Class A is appending to <existing-page-title> instead.
   Action: [keep stub] [delete stub] [open in Notion]
```

Rationale: existing-page-with-history is the durable record; the new empty page is almost certainly a stub Aaron created and forgot. Routing both to the same page prevents history fragmentation. The trust-gate flag lets Aaron clean up the duplicate stub in one tap.

### E5. Duplicate-append guard

Before staging a `## Latest:` append, query the target Notion page's children blocks for any `## YYYY-MM-DD — *` heading in the last 7 days. For each, compute a cosine-similarity-like signal between the staged append body and the existing section's body. If similarity > 0.75 → flag as duplicate, route to trust gate as `[DUPLICATE conf:0.X]` instead of `[APPEND]`.

Aaron can still approve to write anyway (sometimes a repeat update is intentional — "called Alex again, still no answer"), but the default action is "skip — covered by existing section dated YYYY-MM-DD."

Implementation note: deterministic cosine over bag-of-words is fine for v0.2 (no embedding model needed). If precision is poor, upgrade to embedding similarity in a later version.

---

## New scope: Meeting Notes auto-processing (added 2026-05-19)

*Aaron's quote:* "We will start using the meeting notes inside of Notion to dictate and pretty much write up actionable next steps for meetings themselves. Make sure also that if there are new meetings that occur, we are reading through them, updating the Notion workspaces with necessary information, and creating to-do items."

This is the class C input. Behavior:

1. Query `/v1/data_sources/22ba3158-59b4-804d-9c1c-000b9fad40ae/query` (Meeting Notes DB) for pages created or last-edited in the last 24h.
2. For each such page, check `Related Tasks` relation property:
   - **Populated** → already processed (by `/capture-meeting` or a prior `/sync-sweep` run). Skip.
   - **Empty** → fresh meeting; needs auto-processing.
3. For fresh meetings, internally invoke `/capture-meeting`'s Step 4 parse + Step 6a-1/2/3 write pipeline (same code path Aaron uses manually today via "Option D — Granola recap"). Source page is the Meeting Notes recap; output is `[Meeting] <name> <date>` parent task + per-action-item subtasks + Google Tasks mirror for Aaron-owned items.
4. Action items inferred from the meeting note get the same confidence + source-line citations as `/capture-meeting` produces. They appear in the /sync-sweep trust gate alongside braindump/obsidian items.
5. Trust gate displays meeting-derived items with prefix `[MEETING: <meeting name>]` so Aaron can see they came from auto-processing, not from his braindump.

**Why this isn't just /capture-meeting running on a schedule:** /capture-meeting requires Aaron's explicit invocation (chooses the source, sets the business context, picks attendees from a prompt). /sync-sweep auto-detects the meeting AND auto-infers business context from the Notion page's existing `Workspace` field (Granola syncs this) or from attendee-keyword matching per `config/sources.yaml` calendar_business_keywords. If neither resolves, the meeting routes to the trust gate's "Uncategorized" bucket — Aaron tags it once and /sync-sweep remembers.

**Reuses, does not duplicate:** /sync-sweep imports `/capture-meeting`'s parsing logic by calling its `scripts/capture_meeting_parse.sh` (to be extracted from inline during build — currently the parsing is embedded in the skill markdown). One source of truth for "how do we parse a meeting into action items."

## Scope implications — read before building

**v0.2 is meaningfully bigger than v0.1.** Three things changed:
- **Cost:** ~5× the v0.1 token cost. Obsidian vault scan + meeting-note parsing + braindump extraction means ~10–15k input tokens/run typical vs. ~3k. Sonnet still affordable: ~$0.06/run × 3 runs/day = ~$5/mo (vs. v0.1's $0.36/mo). Cost alarm raised from $10 to $25.
- **Implementation time:** ~6–8h vs. v0.1's 3–4h. The Meeting Notes auto-processing is the biggest single chunk because the existing `/capture-meeting` parsing logic needs to be extracted into a reusable script.
- **Risk surface:** writing new Master Tasks (class C) is higher-stakes than appending block sections (class A). Per AAC §2.3 v1.1, the confidence floor for class C action creation = **0.92** (irreversible-bounded — creating a task isn't undoable in <5s; Aaron would have to delete it). The trust gate is the load-bearing mitigation; without explicit Aaron approval, nothing in class C lands.

**Build order recommendation:** ship class A (braindump) first as a working /sync-sweep v0.1, validate for 1 week against real braindumps, then layer in classes B/C/D as v0.2. This matches Aaron's MVE-first discipline per `[[project-mve-decision]]` — ship the smallest end-to-end loop, validate the seam, then expand. If you want one-shot v0.2, that's also viable, just longer to first usable build.

---

## File layout (when built)

```
.claude/skills/sync-sweep/skill.md            — operational skill, ~400 lines
scripts/sync_sweep_entity_extract.sh          — wraps the LLM call (if extracted from inline)
state/sync-sweep-retry-queue.yaml             — DLQ (created on first failure)
.context/sync-sweep-<run_id>.json             — staged payloads (transient)
.context/applied/sync-sweep-<run_id>-<date>.json — archived payloads
config/sources.yaml                            — UNCHANGED (reads existing config)
```

**Invocation paths:**
- `/sync-sweep` (standalone)
- `/end-day` Step 9 (final automatic call — adds a new step to the existing skill)
- `cron / scheduled` (post-MVE — Hermes worker per `[[project-hermes-railway-default]]`)

---

## Verdict on AAC readiness

| Section | Status |
|---|---|
| 1. Work object | ✅ |
| 2. Mode | ✅ Replace |
| 3. Process map | ✅ DAG drawn, no mega-node, hidden queue surfaced |
| 4. Nodes + runtimes | ✅ One C, one A, rest D + H |
| 5. Edges | ✅ All edges declared with latency + volume |
| 6. Input schema | ✅ |
| 7. Output schema | ✅ |
| 8. C-element spec | ✅ Model, prompt, confidence rubric, refuse classes |
| 9. H-element spec | ✅ Disambig question + trust-gate options |
| 10. Memory | ✅ No new file types |
| 11. State machine | ✅ |
| 12. Data contract (8 dims) | ✅ Hard-stop check passes |
| 13. Cost model | ✅ ~$0.36/mo typical, alarm at $10 |
| 14. Latency SLAs | ✅ p50 <30s, p95 <90s |
| 15. Failure modes | ✅ 12 modes mapped to recovery |
| 16. Ownership + operations | ✅ Weekly review, monthly eval, quarterly re-bake, incident runbook |

**Spec is build-ready.** Open design questions §1–5 above need Aaron's call before implementation; recommendations are inlined.

---

**Next step:** Aaron reviews this spec, picks defaults on the 5 open questions, gives go-ahead → Claude implements `.claude/skills/sync-sweep/skill.md` and the supporting scripts in one session. Estimated implementation: 3–4 hours.

---

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | — |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | — | (Explore worker provided outside-voice-equivalent on /capture-meeting extraction) |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | CLEAR | 3 architecture decisions locked (D1/D2/D3), 1 schema gap fixed, 7 test gaps forwarded to lead |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | n/a | Skill is CLI/terminal-only; no UI surface |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | — |

**UNRESOLVED:** 0 — all three architecture decisions answered (D1 verify-after-PATCH, D2 class C floor 0.92, D3 class A wins on collision).

**OUTSIDE VOICE:** Skipped per Aaron's "no ceremony" preference. Explore worker's independent analysis of /capture-meeting extraction served as a partial cross-model check (it surfaced 5 risks the spec hadn't anticipated, all integrated).

**VERDICT:** ENG CLEARED — ready to implement. Spec v0.2 + locked architecture decisions + 7 test gaps integrated into task list = build-ready. MVE-first recommendation stands: ship class A (braindump → page-body append) first as ~7h v0.1, validate against fixtures for one week of real usage, then layer in classes B/C/D as v0.2.
