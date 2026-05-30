# /sync-sweep — Implementation Task List
**Date:** 2026-05-19  
**Based on:** `state/aac-spec-sync-sweep.md` v0.2  
**Explore worker output integrated:** 2026-05-19 (two-script extraction plan)  
**Fixtures worker output integrated:** 2026-05-19 (45 labeled eval fixtures + E1 spec correction)  
**Eng review gaps integrated:** 2026-05-19 (G1–G7 acceptance criteria + schema propagation)  
**Status:** Draft — awaiting Aaron's go-ahead to build

---

## Build order rationale

Phase 1 is split into 1A (parse extraction) and 1B (write extraction). The Explore worker confirmed that extraction must be two-pass: `capture_meeting_parse.py` first, validated against `/capture-meeting` parity, then `capture_meeting_write.py`. Both are Python, not bash — date resolution, confidence scoring, and JSON I/O are all cleaner in Python. Phase 2 builds the class A (braindump → Notion append) end-to-end loop first, then layers in classes B/C/D and extras. Phase 3 wires into `/end-day`. Phase 4 validates against the 45 fixture file now available at `state/sync-sweep-eval-fixtures.yaml`.

The critical path is: **T1 → T3a → T4 → T5 → T6 → T7 → T8 → T9 → T16 → T17**. T3b (write extraction) is a parallel dependency for T12 (class C) but does not block class A. Fixtures worker also surfaced a required E1 spec correction (T21) that must land before T7 is implemented.

```
T1 (config schema)
  └─▶ T2 (state files)
  └─▶ T21 (E1 spec correction)
        └─▶ T3a (capture_meeting_parse.py)
              └─▶ T3b (capture_meeting_write.py)
              └─▶ T4 (Step 0–2: mode + PHI gate)
                    └─▶ T5 (Step 3: entity extract + E1 soft prior)
                          └─▶ T6 (Step 4: Notion search)
                                └─▶ T7 (Step 5: scoring + E1 + E2 read)
                                      └─▶ T8 (Steps 6–7: idempotency + stage)
                                            ├─▶ T9 (Steps 8–9: trust gate + PATCH)
                                            │     └─▶ T11 (E2 disambiguation memory)
                                            ├─▶ T10 (class B: Obsidian vault scan)
                                            ├─▶ T12 (class C: meeting auto-process) ←── T3b
                                            │     └─▶ T13 (E3 priorities.yaml integration)
                                            ├─▶ T14 (class D: stub page enrichment)
                                            └─▶ T15 (E4 Granola URL + E5 dup-append guard)
                                                  └─▶ T16 (Steps 10–11: archive + telemetry)
                                                        └─▶ T17 (/end-day Step 9 wiring)
                                                              └─▶ T18 (/start-day DLQ surfacing)
                                                                    └─▶ T19 (observe-mode dry run)
                                                                          └─▶ T20 (fixture eval run)
                                                                          └─▶ T23 (PHI gate integration test) ←── T5
                                                                                └─▶ T22 (regression tracking task)
```

---

## Phase 1A — Parse extraction (hard dependency for class C)

### Task 1: Extend `config/sources.yaml` with `entity_aliases` and single-dept person list
- **File(s):** `C:/Users/aaron/daily-automation/config/sources.yaml`
- **Phase:** 1A
- **Depends on:** none
- **Estimated time:** 20m
- **Description:** Add two new top-level sections to `sources.yaml`: `entity_aliases` (a map of canonical name → Notion page_id for authoritative, graduated resolutions per §E2) and `single_dept_persons` (the safe first-name override list per §locked decision #3 — names like `MDland`, `Alam`, `Sheila`, `EMU` that map unambiguously to a single workspace). These sections are read-only at this stage; the skill code in Phase 2 will consume them.
- **Acceptance criteria:**
  - `config/sources.yaml` parses without error after edits
  - `entity_aliases:` section exists as a top-level key (may be empty `{}` initially)
  - `single_dept_persons:` section exists with at least the known safe names from `feedback_person_routing.md` (MDland/Alam → Lincoln Lab, Sheila/EMU → Nestmate) with their workspace values
  - No existing keys broken; `staleness_days`, `workspace_values`, all DB entries still parse
- **Notes:** §locked decision #3. The `entity_aliases` section is the graduation target for E2 resolutions that reach 3 confirmations. Start it empty — it gets populated by the skill at runtime.

---

### Task 2: Create `state/sync-sweep-retry-queue.yaml` and `state/sync-sweep-resolutions.yaml` scaffolds
- **File(s):** `C:/Users/aaron/daily-automation/state/sync-sweep-retry-queue.yaml`, `C:/Users/aaron/daily-automation/state/sync-sweep-resolutions.yaml`
- **Phase:** 1A
- **Depends on:** none
- **Estimated time:** 15m
- **Description:** Create both state files with their documented YAML schema and empty initial content. `sync-sweep-retry-queue.yaml` holds the DLQ per §15. `sync-sweep-resolutions.yaml` holds E2 disambiguation memory per §E2. Both are written to at runtime; creating them now prevents first-run file-not-found errors and makes the schema explicit for implementers.
- **Acceptance criteria:**
  - Both files exist and parse as valid YAML
  - `sync-sweep-retry-queue.yaml` has a `queue: []` root key and a comment block documenting entry shape: `entity_name`, `notion_page_id`, `payload`, `attempts`, `last_status`, `first_failed`
  - `sync-sweep-resolutions.yaml` has a `resolutions: []` root key and a comment block documenting entry shape: `mention_text`, `resolved_page_id`, `resolved_page_title`, `workspace`, `confirmed_at`, `confirmation_count`
  - `/start-day` and `/end-day` do not break when these files are present
- **Notes:** §10 Memory, §E2. The retry queue shape mirrors `state/gtask-retry-queue.yaml` — keep naming consistent.

---

### Task 21: Correct E1 (section-header prior) in `state/aac-spec-sync-sweep.md`
- **File(s):** `C:/Users/aaron/daily-automation/state/aac-spec-sync-sweep.md`
- **Phase:** 1A
- **Depends on:** none
- **Estimated time:** 20m
- **Description:** The fixtures worker identified that the E1 "section header beats contact name" rule is wrong in the v0.2 spec. Three fixtures prove the line-level signal must be able to override the section header (Dr Tim ENG case: Nestmate section, but "lab" keyword in line → Lincoln Lab routing). Update the E1 section of the spec with the corrected rule: (1) section header sets a default business prior, (2) line-level business-keyword match from `config/sources.yaml` `calendar_business_keywords` overrides the prior, (3) multiple business keywords on one line → disambig, (4) confidence reflects section+line agreement (high) vs. disagreement (line wins, conf drops to ~0.70). Also update the reference to `feedback_brainstorm_to_execution.md` to note the absolute form of the rule has been superseded.
- **Acceptance criteria:**
  - `state/aac-spec-sync-sweep.md` §E1 section contains the corrected four-rule description
  - The old "section header beats contact name" absolute statement is removed or marked superseded
  - The spec change is clearly dated (2026-05-19) with "fixtures worker finding" as rationale
  - The Ahmed (multi-dept), Dr Rookwood (context-window), and Dr Tim ENG (line-override) counter-examples are referenced in the spec as the motivating cases
- **Notes:** Fixtures worker finding. Source rule in `feedback_brainstorm_to_execution.md` described section header as authoritative — the fixtures disprove the absolute form. The soft-prior form is the correct implementation target.

---

### Task 3a: Implement `scripts/capture_meeting_parse.py`
- **File(s):** `C:/Users/aaron/daily-automation/scripts/capture_meeting_parse.py`
- **Phase:** 1A
- **Depends on:** T1, T21
- **Estimated time:** 90m
- **Description:** Create a Python script encapsulating `/capture-meeting` Steps 4 + 4.5 (parse-and-categorize + idempotency check). Takes meeting notes on stdin or via `--notes-file`, outputs a JSON array of categorized items to stdout. Business tag, attendees, meeting key, and date are passed via CLI flags. The script reads routing indicators from `config/routing-rules.yaml` and workspace values from `config/sources.yaml`. Implements the confidence rubric from §8, the < 0.70 → Uncategorized threshold, and source-line citation on every item. Action_id generation shells out to `scripts/action_id.sh` (not reimplemented) per Explore worker risk #4.
- **Acceptance criteria:**
  - `scripts/capture_meeting_parse.py --help` runs without error
  - Given a sample meeting notes body, outputs valid JSON array with fields: `category`, `confidence`, `source_line`, `source_text`, `owner`, `owner_resolved_from`, `due`, `due_resolved_from`, `secondary_hint`, `action_id`, `skip_idempotent`
  - `--date` flag is required; relative-date parsing ("next Tuesday") resolves against this explicit date — not `datetime.today()` — per Explore worker risk #1
  - `--business-tag` empty/absent: falls back to attendee-keyword inference using `calendar_business_keywords` from sources.yaml, then to "other" — per Explore worker risk #2
  - Confidence threshold (< 0.70 → Uncategorized) is enforced inside the script
  - Items already stamped in `.context/applied/` (idempotency check via `action_id.sh check`) have `skip_idempotent: true` in output
  - Exit codes: 0 = success, 1 = config error, 2 = empty input
  - Running `/capture-meeting` on a known meeting produces identical categorization output before and after this extraction (parity test)
  - **G7**: Unit test: mock `gws tasks tasks insert` output that includes the `"Using keyring backend: keyring\n"` banner prefix. Verify the script strips that banner before attempting JSON parse. Fail = `json.JSONDecodeError` raised on banner-prefixed output.
- **Notes:** Explore worker signature spec. Risk #1 (explicit --date), risk #2 (headless business-tag path), risk #4 (shell out to action_id.sh). The parity test is critical — do NOT ship this until confirmed `/capture-meeting` Step 4 behavior is unchanged. G7 added from eng review (Explore worker flagged gws banner as fragile/untested).

---

## Phase 1B — Write extraction (dependency for class C only)

### Task 3b: Implement `scripts/capture_meeting_write.py`
- **File(s):** `C:/Users/aaron/daily-automation/scripts/capture_meeting_write.py`
- **Phase:** 1B
- **Depends on:** T3a
- **Estimated time:** 90m
- **Description:** Create a Python script encapsulating `/capture-meeting` Steps 6a-1/2/3 + 6a-bonus (create Notion parent task, create subtasks, create Google Tasks mirrors for Aaron-owned items, PATCH Granola back-link). Takes the JSON array from `capture_meeting_parse.py` on stdin or `--parsed-items` file. Outputs `{parent_task_id, subtasks: [{notion_id, gtask_id, action_id}], back_link_patched}` as JSON. Supports `--dry-run` flag that logs all writes without executing. Action_id stamping is done inside this script via `action_id.sh stamp` (not in the caller).
- **Acceptance criteria:**
  - `scripts/capture_meeting_write.py --dry-run` with a known parsed-items payload logs the expected Notion API calls without executing them
  - Creates `[Meeting]` parent task in Master Tasks using the correct data_source ID from `config/sources.yaml`
  - Creates subtasks with `Parent Task` relation set to the parent's ID (captured from the POST response — not guessed)
  - Google Tasks mirror created for Aaron-owned subtasks using `gws tasks tasks insert`; gws banner (`Using keyring...`) is stripped before JSON parse — and a unit test inside the script verifies this strip with a mock banner per Explore worker risk #3
  - Back-link PATCH to the recap page (6a-bonus) uses accumulated subtask IDs from the structured JSON handoff — not shell variable accumulation — per Explore worker risk #5
  - Exit codes: 0 = all writes ok, 1 = partial failures (some subtasks failed), 2 = auth error (401)
  - Action_ids are stamped via `action_id.sh stamp` after each successful write (not in a batch at the end — to preserve partial progress on failure)
- **Notes:** Explore worker signature spec, risks #3, #4, #5. The two-pass approach means this script ONLY handles the write side; parsing state is passed in as JSON. The structured JSON handoff for the Granola back-link (risk #5) avoids the bash variable accumulation bug that was latent in the original inline skill.

---

## Phase 2 — Core skill implementation (class A first, then B/C/D)

### Task 4: Create `skill.md` skeleton with Step 0 (mode check) and Step 1 (input pull — class A only)
- **File(s):** `C:/Users/aaron/daily-automation/.claude/skills/sync-sweep/skill.md`
- **Phase:** 2
- **Depends on:** T1, T2
- **Estimated time:** 45m
- **Description:** Create the `skill.md` file with YAML frontmatter, constants block, and Steps 0–1 fully implemented. Step 0 reuses `scripts/check_mode.sh` exactly as in `/capture-meeting`. Step 1 reads the braindump section from today's daily note and strips already-synced lines via `<!-- synced to notion:... -->` regex. Sets `RUN_ID` with `ss-` prefix per §6 input schema.
- **Acceptance criteria:**
  - File exists at `.claude/skills/sync-sweep/skill.md` with valid YAML frontmatter (`name: sync-sweep`, `description:`)
  - Step 0: refuses when mode is `locked`; sets `SKIP_WRITES=1` when `observe`
  - Step 1: reads `vault/daily/YYYY-MM-DD.md`, extracts the `## Braindump` section, exits as no-op (with a logged message) when the section is absent
  - Step 1: strips already-synced lines (matching `<!-- synced to notion:[a-f0-9]+ -->`) before returning text to subsequent steps
  - `RUN_START_MS` is captured for telemetry
- **Notes:** §3 process map Steps 0–1, §15 failure mode (braindump missing → no-op), §locked decision #2.

---

### Task 5: Implement Step 2 (PHI gate) and Step 3 (entity extraction with corrected E1 soft prior)
- **File(s):** `C:/Users/aaron/daily-automation/.claude/skills/sync-sweep/skill.md`
- **Phase:** 2
- **Depends on:** T4, T21
- **Estimated time:** 60m
- **Description:** Step 2 pipes braindump text through `scripts/phi_scan.sh` (existing, no new code). Step 3 implements entity extraction: deterministic regex pass first — extract nearest preceding `##`/`###` heading as `section_context`, AND scan the current line for business-keyword matches from `config/sources.yaml` `calendar_business_keywords`. Apply the corrected E1 rule (T21): line-level keyword overrides section prior; multiple keywords on one line → flag for disambig. Also look at ±2 surrounding lines for context per Dr Rookwood fixture finding. Then pass `section_context`, `line_keyword_signal`, and `surrounding_context` into the LLM extraction prompt from §8.
- **Acceptance criteria:**
  - PHI-containing text triggers refusal and logs to `logs/_phi_refusals.jsonl`
  - Step 3 output JSON includes all fields from the updated §7 `per_entity_mention` schema: `entity_canonical`, `aliases`, `source_line`, `source_text`, `confidence`, `update_summary`, `section_context`, `line_business_signal`, `input_class`, `override_applied`, `context_window` — field names must match exactly (note: `line_business_signal`, not `line_keyword_signal`, per the v0.2 schema update)
  - `line_business_signal` correctly overrides `section_context` when present — verified with a test case matching the Dr Tim ENG fixture (Nestmate section, "lab" keyword in line → Lincoln Lab)
  - Surrounding ±2 lines are included in the extraction prompt context (not just the current line) — verified with Dr Rookwood-style fixture where routing depends on adjacent lines
  - Payment-instruction refuse class: item routes to Activity Log suggestion, does not crash
  - Regex fallback on 20s LLM timeout: extracts nouns matching workspace keywords from `config/sources.yaml`
- **Notes:** §8 C-element, corrected §E1 (T21), §14 timeout fallback, §7 per_entity_mention schema (updated with `input_class`, `section_context`, `line_business_signal`, `override_applied`, `context_window` fields — schema gap propagated from eng review). Fixtures worker finding: three counter-examples (Ahmed, Dr Rookwood, Dr Tim ENG) are now in `state/sync-sweep-eval-fixtures.yaml` and serve as acceptance test cases.

---

### Task 6: Implement Step 4 (workspace-wide Notion search per entity)
- **File(s):** `C:/Users/aaron/daily-automation/.claude/skills/sync-sweep/skill.md`
- **Phase:** 2
- **Depends on:** T5
- **Estimated time:** 45m
- **Description:** For each extracted entity, issue a `/v1/search` call using the canonical name and aliases. Collect up to 5 candidate matches per entity including topic-page hits. Each match includes `page_id`, `page_title`, `parent_db`, `workspace`, `last_edited_time`, and URL. Handle 5xx per §15 (skip entity, mark no-match, status=partial).
- **Acceptance criteria:**
  - For a known entity name present in Provider CRM, the search returns that page as a candidate
  - Topic-page hits are included alongside DB hits (not filtered out)
  - Each candidate carries all required fields: `page_id`, `page_title`, `parent_db`, `workspace`, `last_edited_time`, `url`
  - 5xx on a search call marks that entity as `no-match` and sets run status to `partial` — does not crash
  - `--max-time 60` on every curl call; `Notion-Version: 2025-09-03` header on all calls
- **Notes:** §3 Step 4, §5 Edges. Uses `/v1/search`, not `/v1/data_sources/.../query`.

---

### Task 7: Implement Step 5 (match scoring with corrected E1 prior weighting and E2 resolution read)
- **File(s):** `C:/Users/aaron/daily-automation/.claude/skills/sync-sweep/skill.md`
- **Phase:** 2
- **Depends on:** T1, T6, T21
- **Estimated time:** 60m
- **Description:** Implement the scoring formula: `match_score = title_similarity * 0.5 + workspace_match * 0.3 + recency * 0.2`. Apply corrected E1 prior: if `line_keyword_signal` is present, it takes precedence over `section_context` for workspace-match scoring. If `line_keyword_signal` is absent, `section_context` serves as the soft prior (boost). Read `state/sync-sweep-resolutions.yaml` for E2 +0.2 boost. Read `single_dept_persons` from `config/sources.yaml` for first-name overrides. Auto-stage threshold: conf ≥ 0.85 AND match_score ≥ 0.65 AND single match.
- **Acceptance criteria:**
  - A known full-name entity with a single clear Notion match resolves to `auto-stage`
  - An ambiguous first name (e.g., "Alex") with multiple matches triggers disambiguation display per §9 format
  - `single_dept_persons` list: a bare first name in that list resolves to `conf 0.85` auto-stage
  - E2 prior boost of +0.2 is applied to the correct candidate when `sync-sweep-resolutions.yaml` has an entry
  - **E1 corrected behavior**: entity in a Nestmate section but with "lab" in the line → workspace_match scores against Lincoln Lab, not Nestmate — verified against the Dr Tim ENG fixture in `state/sync-sweep-eval-fixtures.yaml`
  - Ahmed (multi-dept, no line keyword) → conf ~0.65 → disambiguation, not auto-stage — verified against the Ahmed fixtures
- **Notes:** §5 edges (thresholds), §7 output schema (match_score formula), corrected §E1 (T21), §E2, §locked decisions #3. The fixtures from `state/sync-sweep-eval-fixtures.yaml` are the canonical acceptance test oracle for all three tricky cases.

---

### Task 8: Implement Step 6 (idempotency check) and Step 7 (stage payloads to `.context/`)
- **File(s):** `C:/Users/aaron/daily-automation/.claude/skills/sync-sweep/skill.md`
- **Phase:** 2
- **Depends on:** T7
- **Estimated time:** 40m
- **Description:** Step 6 calls `scripts/action_id.sh check` for each entity's action_id (format: `sync-sweep:<page_id_short>:YYYY-MM-DD:<8-char-hash>`). Step 7 writes fresh items to `.context/sync-sweep-<run_id>.json`. Decision-verb detection (`decided | agreed | approved | finalized | going with | confirmed`) sets `activity_log_row` in the payload.
- **Acceptance criteria:**
  - Re-running sync-sweep on the same braindump after prior stamps results in zero new staged items
  - `.context/sync-sweep-<run_id>.json` is created with valid JSON
  - Decision-verb detection correctly sets `activity_log_row` when present
  - Items declined at prior trust gate (archived as `*-declined-*`) are NOT blocked by idempotency check
  - Action_id filename format on Windows uses `_` separator (`:` → `_`) per existing `action_id.sh` behavior
- **Notes:** §3 Steps 6–7, §6 idempotency unit, §11 decision-verb side branch. Hash input: `entity_canonical + page_id + source_text[:80]`.

---

### Task 9: Implement Step 8 (trust gate) and Step 9 (PATCH apply with `## Latest:` prepend)
- **File(s):** `C:/Users/aaron/daily-automation/.claude/skills/sync-sweep/skill.md`
- **Phase:** 2
- **Depends on:** T8
- **Estimated time:** 90m
- **Description:** Step 8 displays all staged payloads with options A/B/C/D per §9 H-element trust gate spec. Step 9 executes approved PATCHes using the §locked decision #1 `## Latest:` prepend pattern: read existing children, locate or create `## Latest:` heading, demote prior content to dated section below, insert new content. On success, edit daily note to wrap source line with strikethrough + `<!-- synced to notion:<id> -->`. On 5xx, append to retry queue; on 401, stop all writes and surface token-rotation message.
- **Acceptance criteria:**
  - Trust gate displays `[class-A conf:X.XX]` prefix, source line citation, and proposed append body per §9 format
  - Options A/B/C/D all work correctly: A approves all, B takes comma-separated numbers, C archives to `.context/applied/<run_id>-declined-<date>.json` with no Notion writes, D lets Aaron rewrite append_body
  - Successful PATCH to a page with existing `## Latest:` correctly demotes prior content to dated section — verified by re-reading `/v1/blocks/{id}/children`
  - Successful PATCH to a page with no `## Latest:` creates the heading correctly
  - Source line in daily note is wrapped with strikethrough and sync comment after success
  - 5xx → retry-queue entry; action_id NOT stamped
  - 401 → stops all writes, surfaces token-rotation message
  - 404 (page deleted between search and write) → skip item, mark `stale-target`, log only
  - **G1**: Test: target page has 150 children blocks. Verify the pagination walk (via `next_cursor`) finds an existing `## Latest:` heading located past block 100. Fail = duplicate `## Latest:` heading created because the first GET page returned only 100 blocks.
  - **G2**: Test: manually insert a duplicate `## Latest:` heading into a page before running. Verify the auto-repair logic promotes the older heading to a dated section (e.g., `## 2026-05-18 — Prior`) and retains only the newly written `## Latest:`. Fail = two `## Latest:` headings coexist after the run. (New from D1.)
- **Notes:** §3 Steps 8–9, §9 H-element trust gate, §locked decisions #1 and #2, §15 failure modes. G1/G2 added from eng review (pagination edge case + D1 auto-repair verification).

---

### Task 10: Implement class B (Obsidian vault recent-edit scan)
- **File(s):** `C:/Users/aaron/daily-automation/.claude/skills/sync-sweep/skill.md`
- **Phase:** 2
- **Depends on:** T9
- **Estimated time:** 60m
- **Description:** Add class B input to Step 1: scan `vault/CardioPro/`, `vault/Labaide/`, `vault/Nestmate/`, `vault/United IPA/`, `vault/Notes to self/`, `vault/notes/`, `vault/inbox/` for files with mtime within the last 24h. Extract entity mentions using the same Step 3 extraction (reuse, don't duplicate). Class B items enter the same Steps 4–9 pipeline tagged `[class-B]` in the trust gate.
- **Acceptance criteria:**
  - A vault file edited in the last 24h with a known entity name produces a class-B staged item
  - Files older than 24h are skipped
  - Business vault folders (`CardioPro/`, etc.) are scanned read-only — no writes to these folders
  - Class B items display `[class-B]` prefix in the trust gate
  - Non-existent vault folders (vault sync hasn't run) are skipped gracefully
- **Notes:** §1 work object class B, §locked decision #4.

---

### Task 11: Implement E2 (disambiguation memory — persist and graduate resolutions)
- **File(s):** `C:/Users/aaron/daily-automation/.claude/skills/sync-sweep/skill.md`, `C:/Users/aaron/daily-automation/state/sync-sweep-resolutions.yaml`
- **Phase:** 2
- **Depends on:** T7, T2
- **Estimated time:** 45m
- **Description:** After Aaron picks a candidate at the Step 5 disambiguation gate, write or update the resolution in `state/sync-sweep-resolutions.yaml` (increment `confirmation_count`). On the next scoring pass, apply the +0.2 boost. When `confirmation_count` reaches 3, graduate the entry to `entity_aliases` in `config/sources.yaml` and remove from resolutions.
- **Acceptance criteria:**
  - First disambiguation pick for "Alex Acosta" creates entry with `confirmation_count: 1`
  - Third pick graduates to `entity_aliases` in `config/sources.yaml` and removes from `sync-sweep-resolutions.yaml`
  - Subsequent runs with a graduated alias auto-stage without disambiguation (conf = 0.85)
  - `sync-sweep-resolutions.yaml` remains valid YAML after every write
- **Notes:** §E2. Graduation threshold of 3 is hardcoded per spec.

---

### Task 12: Implement class C (Meeting Notes DB auto-processing)
- **File(s):** `C:/Users/aaron/daily-automation/.claude/skills/sync-sweep/skill.md`
- **Phase:** 2
- **Depends on:** T3a, T3b, T9
- **Estimated time:** 90m
- **Description:** Query Meeting Notes data_source (`22ba3158-59b4-804d-9c1c-000b9fad40ae`) for pages created/edited in the last 24h. Skip those with `Related Tasks` populated. For fresh meetings, fetch page body blocks (same GET as `/capture-meeting` Step 2 Option D), pass to `scripts/capture_meeting_parse.py` with explicit `--date` flag and inferred `--business-tag`, then pass parse output to `scripts/capture_meeting_write.py --dry-run` for staging. Trust gate shows `[MEETING: <name>]` prefix with confidence floor 0.92.
- **Acceptance criteria:**
  - Meeting Notes page with `Related Tasks` populated is skipped
  - Fresh meeting page produces `[MEETING: <name>]` trust gate entry
  - Business context inferred from `Workspace` field first, then keyword matching, then Uncategorized
  - On approval, creates `[Meeting]` parent + subtasks via `capture_meeting_write.py` (not inline code)
  - Aaron-owned subtasks get Google Tasks mirror
  - Confidence floor 0.92 enforced — items below threshold go to Uncategorized bucket
  - `scripts/capture_meeting_parse.py` and `scripts/capture_meeting_write.py` are invoked as subprocesses, not duplicated inline
  - **G3**: Test: meeting note where `capture_meeting_parse.py` produces action items at confidence 0.88 (below the 0.92 class-C floor). Verify those items are routed to the trust gate for manual review and NOT auto-staged. Fail = 0.88-confidence items written without trust gate prompt. (New from D2.)
- **Notes:** §New scope (class C), §scope implications (0.92 confidence floor). Blocked on T3a + T3b. G3 added from eng review (D2 confidence floor enforcement).

---

### Task 13: Implement E3 (priorities.yaml integration for class C tasks)
- **File(s):** `C:/Users/aaron/daily-automation/.claude/skills/sync-sweep/skill.md`
- **Phase:** 2
- **Depends on:** T12
- **Estimated time:** 30m
- **Description:** After class C writes succeed, write corresponding entries to `state/priorities.yaml` per §E3 routing rules: Aaron-owned tasks with due dates → `carry_forward`, blocking-someone-else tasks → `awaiting`, teammate-owned → skip, decision-verb tasks → skip.
- **Acceptance criteria:**
  - Aaron-owned class-C subtask with due date → new `carry_forward` entry with `source: notion` and page_id
  - Aaron-owned subtask with awaiting signal → `awaiting` entry
  - Teammate-owned subtask → no `priorities.yaml` entry
  - Decision-verb subtask → no `priorities.yaml` entry
  - `priorities.yaml` remains valid YAML; existing entries are preserved
- **Notes:** §E3. Decision-verb list: `decided | agreed | approved | finalized | going with | confirmed`.

---

### Task 14: Implement class D (new Notion stub page enrichment)
- **File(s):** `C:/Users/aaron/daily-automation/.claude/skills/sync-sweep/skill.md`
- **Phase:** 2
- **Depends on:** T10, T9
- **Estimated time:** 60m
- **Description:** Use `/v1/search` for pages with `last_edited_time ≥ 24h ago`, excluding class A/C-covered pages. For stub pages (no/minimal body content): search vault for a matching recent file — if found and substantive (>50 chars), stage update. If no vault match, prompt Aaron inline for one-line context with `[class-D]` prefix.
- **Acceptance criteria:**
  - Stub page with matching recent vault file → staged class-D update
  - Stub page with no vault match → inline prompt to Aaron for one-line context
  - Pages already covered by class A or C are excluded from class D
  - Pages with substantive existing content are skipped silently
  - 50-char threshold is in a named constant (not magic number) for future tuning
  - **G4**: Test: braindump mentions "Alex Acosta" AND a new empty Notion page titled "Alex Acosta" exists created <24h ago. Verify class A wins: the append goes to the existing entity page, and the empty stub surfaces in the trust gate flagged as a duplicate stub (not written to). Fail = append goes to the stub page, or the collision is not surfaced. (New from D3.)
- **Notes:** §1 work object class D, §locked decision #4, §locked decision D3 (class A wins collision). G4 added from eng review.

---

### Task 15: Implement E4 (Granola URL detection) and E5 (duplicate-append guard)
- **File(s):** `C:/Users/aaron/daily-automation/.claude/skills/sync-sweep/skill.md`
- **Phase:** 2
- **Depends on:** T12, T8
- **Estimated time:** 50m
- **Description:** E4: Scan braindump before entity extraction for Granola URL patterns (`https?://(notes\.granola\.ai|notion\.so/[a-f0-9-]{32,36})`). Matching lines route to class C pipeline; the URL line gets strikethrough on success. E5: Before staging any append in Step 7, query target page children for `## YYYY-MM-DD — *` headings in the last 7 days. Compute bag-of-words cosine similarity between staged body and existing section. Similarity > 0.75 → flag as `[DUPLICATE conf:X.XX]` in trust gate.
- **Acceptance criteria:**
  - Granola URL in braindump is detected by E4 regex and routes to class C pipeline
  - Granola URL line gets strikethrough+sync-comment on successful class C processing
  - E5: staged append body >75% similar to existing dated section → flagged `[DUPLICATE]` in trust gate
  - Aaron can still approve a `[DUPLICATE]` item to write
  - E5: similarity computed with Python `collections.Counter` bag-of-words (no embedding model)
  - Novel append (<75% overlap) is not flagged
- **Notes:** §E4, §E5. Cosine: `dot(a, b) / (|a| * |b|)` over term-frequency vectors.

---

## Phase 3 — Integration with `/end-day` and `/start-day`

### Task 16: Implement Step 10 (archive + stamp) and Step 11 (telemetry)
- **File(s):** `C:/Users/aaron/daily-automation/.claude/skills/sync-sweep/skill.md`
- **Phase:** 3
- **Depends on:** T9
- **Estimated time:** 30m
- **Description:** Step 10: stamp action_ids via `scripts/action_id.sh stamp` with metadata (skill, run_id, notion_page_id, source_class, input_tokens, output_tokens). Move `.context/sync-sweep-<run_id>.json` to `.context/applied/sync-sweep-<run_id>-<YYYY-MM-DD>.json`. Step 11: call `scripts/telemetry.sh` with all `per_run_summary` fields plus cost tracking (`input_tokens`, `output_tokens`, `model_id`, `estimated_cost_usd`) per §13.
- **Acceptance criteria:**
  - After a successful run, no `.context/sync-sweep-*.json` files exist at top level
  - `.context/applied/sync-sweep-<run_id>-<YYYY-MM-DD>.json` exists
  - `logs/_telemetry.jsonl` gains exactly one new row per skill run with all required fields
  - Declined runs (Option C) also get archive + telemetry (status=`ok`, written=0, declined=N)
  - Partial runs (some 5xx) have status=`partial` in telemetry
  - `/start-day` pre-flight finds no orphaned sync-sweep payloads after a completed run
- **Notes:** §3 Steps 10–11, §10 Memory, CLAUDE.md `.context/` lifecycle, §13.

---

### Task 17: Wire `/end-day` Step 9 to call `/sync-sweep`
- **File(s):** `C:/Users/aaron/daily-automation/.claude/skills/end-day/skill.md`
- **Phase:** 3
- **Depends on:** T16
- **Estimated time:** 30m
- **Description:** Add a final step to `/end-day/skill.md` (after existing Step 9 Summary, before Step 10 Telemetry) that invokes `/sync-sweep` with `trigger: end-day-final-step`. If `/sync-sweep` produces no staged items, skip silently with one-line log. If `/sync-sweep` fails (locked, PHI), log the failure and let end-day complete normally.
- **Acceptance criteria:**
  - Running `/end-day` through to completion triggers `/sync-sweep` as the final step
  - Empty braindump / no staged items → no empty trust gate displayed; one-line "sync-sweep: nothing to route today"
  - Trigger source `end-day-final-step` appears in sync-sweep telemetry row
  - `/end-day`'s existing steps 1–10 still execute correctly
  - `/sync-sweep` failure does not propagate as `/end-day` failure
- **Notes:** §3 process map trigger sources, §file layout invocation paths.

---

### Task 18: Add DLQ surfacing to `/start-day` pre-flight
- **File(s):** `C:/Users/aaron/daily-automation/.claude/skills/start-day/skill.md`
- **Phase:** 3
- **Depends on:** T2
- **Estimated time:** 20m
- **Description:** Add a check in `/start-day`'s system-flags section that reads `state/sync-sweep-retry-queue.yaml` and surfaces queue depth as a system flag when non-empty. Format: "sync-sweep DLQ: N items, oldest M days." Entries ≥3 days old get a distinct warning marker.
- **Acceptance criteria:**
  - Non-empty retry queue → system flag with depth and oldest-entry age in `/start-day` output
  - Empty queue or missing file → no flag
  - Entries ≥3 days old → "⚠️ oldest N days" marker
  - Malformed YAML → parse warning, skip, no crash
- **Notes:** §15 retry queue surfacing failure mode.

---

## Phase 4 — Validation

### Task 19: Dry-run validation in `observe` mode against real braindumps
- **File(s):** No new files — runs against existing `vault/daily/` entries
- **Phase:** 4
- **Depends on:** T16, T17
- **Estimated time:** 60m (run time + review)
- **Description:** With `state/coo_mode.yaml` set to `observe`, run `/sync-sweep` against the last 5 real braindump entries in `vault/daily/`. Verify entity extraction, Notion search, scoring, and trust gate display work correctly end-to-end with zero external writes.
- **Acceptance criteria:**
  - All 5 dry runs complete without crashing
  - Entity extraction produces ≥1 entity for braindumps known to contain provider/account names
  - Trust gate displays correct format per §9
  - No Notion PATCHes executed (`SKIP_WRITES=1` respected)
  - No `.context/` top-level files remain after each run
  - Telemetry row per run with `status: ok`, `written: 0`
  - PHI scan does not false-positive on normal business content (ISO dates, provider names)
  - **G6**: Test: simulate 3 consecutive PATCH 5xx responses for the same item (mock the curl call to return 503 three times). Verify the item enters the retry queue, exhausts 3 attempts across retries, graduates to DLQ status, and `/start-day` surfaces it in the system-flags section. Fail = item silently dropped after 3 failures, or never reaches DLQ. (Tested here as an end-to-end flow; unit-level retry logic is owned by T9.)
- **Notes:** §15 observe-mode behavior, §16 change management (7-day observe trial before promoting to draft). G6 added from eng review (retry-queue graduation + /start-day surfacing path).

---

### Task 20: Run entity extraction against `state/sync-sweep-eval-fixtures.yaml` and measure precision/recall
- **File(s):** `C:/Users/aaron/daily-automation/state/sync-sweep-eval-fixtures.yaml` (pre-existing, 45 fixtures)
- **Phase:** 4
- **Depends on:** T5, T7, T19
- **Estimated time:** 60m (run + scoring)
- **Description:** The fixtures file is already available (45 labeled examples across 8 days of braindumps, distribution: Nestmate 18, Lincoln Lab 12, United IPA 9, Dock Pro 4, Other 2). Run the Step 3 entity extraction + Step 5 scoring against each fixture sentence. Compute precision and recall segmented by confidence bucket (high/medium/low) and by business. Pass thresholds: ≥85% agreement on high+medium fixtures, ≥70% on low-confidence fixtures. Failures are investigation items, not ship-blockers (low-conf fixtures are inherently judgment calls).
- **Acceptance criteria:**
  - Extraction run on all 45 fixtures completes without error
  - ≥85% agreement on the 40 high+medium-confidence fixtures
  - ≥70% agreement on the 5 low-confidence fixtures
  - Ahmed (multi-dept) fixtures: entity extracted with conf ~0.65 → routes to disambig, NOT auto-staged
  - Dr Rookwood fixture: entity extracted correctly when surrounding context lines are included
  - Dr Tim ENG fixture: Lincoln Lab routing despite Nestmate section header (E1 line-override)
  - Per-business breakdown logged to `logs/<TODAY>.md` for trend tracking
  - Any fixture failure is documented with root cause (extraction miss, scoring error, or correct behavior that conflicts with label)
- **Notes:** Fixtures worker output. 45 fixtures covering 2026-05-02 through 2026-05-19. Fixtures file is the oracle for any future prompt changes — always re-run before promoting.

---

### Task 23: Write PHI gate integration test for `/sync-sweep` input path
- **File(s):** `C:/Users/aaron/daily-automation/.claude/skills/sync-sweep/skill.md`, `C:/Users/aaron/daily-automation/scripts/phi_scan.sh`
- **Phase:** 4
- **Depends on:** T5
- **Estimated time:** 30m
- **Description:** Implement a test that exercises the full PHI gate path specific to `/sync-sweep` input. Construct a synthetic braindump string containing an SSN-pattern string (e.g., `"SSN: 123-45-6789"`), run it through Step 2 of the skill, and assert the three required outcomes: (1) `phi_scan.sh` triggers a refusal, (2) the refusal is logged to `logs/_phi_refusals.jsonl` with `skill: sync-sweep` and a timestamp, (3) no LLM call is made (Step 3 entity extraction is never invoked). **(G5 from eng review.)**
- **Acceptance criteria:**
  - Test input: synthetic braindump with `"SSN: 123-45-6789"` in the body
  - `phi_scan.sh` exits non-zero for that input
  - `logs/_phi_refusals.jsonl` gains exactly one new entry with `skill: sync-sweep`, `pattern: SSN`, and a valid ISO timestamp
  - No entity extraction output produced — Step 3 is not reached
  - Test input without SSN-pattern passes Step 2 cleanly (no false positive)
  - Test is runnable as a standalone script (e.g., `bash scripts/test_phi_gate.sh`) that exits 0 on pass, 1 on fail
- **Notes:** G5 from eng review. `phi_scan.sh` already exists and handles SSN/DOB/MRN patterns for `/capture-meeting`. This task verifies it is correctly wired into `/sync-sweep` Step 2 and that the `_phi_refusals.jsonl` log entry includes the correct `skill` field.

---

### Task 22: Add regression-tracking gate for entity extraction prompt changes
- **File(s):** `C:/Users/aaron/daily-automation/state/sync-sweep-eval-fixtures.yaml`, `C:/Users/aaron/daily-automation/state/aac-spec-sync-sweep.md`
- **Phase:** 4
- **Depends on:** T20
- **Estimated time:** 20m
- **Description:** Add a comment header to `state/sync-sweep-eval-fixtures.yaml` documenting the regression protocol: any change to the entity extraction prompt (§8 C-element) must be benchmarked against these 45 fixtures before promotion, and results appended to a `## Eval History` section in the fixtures file. Add a corresponding note in `state/aac-spec-sync-sweep.md` §16 change management section referencing the fixtures file as the mandatory benchmark gate. Also add a reminder note for monthly fixture refresh (30 days from 2026-05-19 → 2026-06-19).
- **Acceptance criteria:**
  - `state/sync-sweep-eval-fixtures.yaml` has a header comment block documenting the regression protocol and monthly refresh reminder
  - An `## Eval History` section exists in the fixtures file with the T20 baseline run result recorded
  - `state/aac-spec-sync-sweep.md` §16 Change management section references fixtures file as mandatory benchmark for prompt changes
  - The monthly refresh date (2026-06-19) is noted in the spec and in the fixtures header
- **Notes:** §16 monthly eval refresh. This is the implementation of the "≥90% extraction agreement before promoting prompt changes" change management rule. Fixtures worker noted that Aaron's vocabulary evolves (new provider names, new shorthand) — 30-day refresh cycle keeps the eval grounded.

---

## Summary table

| Task | Phase | Est. time | Blocked? |
|------|-------|-----------|----------|
| T1: config schema extension | 1A | 20m | — |
| T2: state file scaffolds | 1A | 15m | — |
| T21: E1 spec correction | 1A | 20m | — |
| T3a: `capture_meeting_parse.py` | 1A | 90m | — |
| T3b: `capture_meeting_write.py` | 1B | 90m | T3a |
| T4: skill.md scaffold + Steps 0–1 | 2 | 45m | — |
| T5: Steps 2–3 (PHI + entity extract + E1) | 2 | 60m | T21 |
| T6: Step 4 (Notion search) | 2 | 45m | — |
| T7: Step 5 (scoring + E1 + E2 read) | 2 | 60m | T21 |
| T8: Steps 6–7 (idempotency + stage) | 2 | 40m | — |
| T9: Steps 8–9 (trust gate + PATCH) *(+G1, G2)* | 2 | 90m | — |
| T10: class B (Obsidian vault scan) | 2 | 60m | — |
| T11: E2 (disambiguation memory) | 2 | 45m | — |
| T12: class C (meeting auto-process) *(+G3)* | 2 | 90m | T3a, T3b |
| T13: E3 (priorities.yaml integration) | 2 | 30m | — |
| T14: class D (stub page enrichment) *(+G4)* | 2 | 60m | — |
| T15: E4 (Granola URL) + E5 (dup guard) | 2 | 50m | — |
| T16: Steps 10–11 (archive + telemetry) | 3 | 30m | — |
| T17: /end-day Step 9 wiring | 3 | 30m | — |
| T18: /start-day DLQ surfacing | 3 | 20m | — |
| T19: observe-mode dry run *(+G6)* | 4 | 60m | — |
| T20: fixture eval run (precision/recall) | 4 | 60m | — |
| T23: PHI gate integration test *(G5 new)* | 4 | 30m | T5 |
| T22: regression-tracking gate | 4 | 20m | T20 |

**Total: 23 tasks — Phase 1A: 4, Phase 1B: 1, Phase 2: 12, Phase 3: 3, Phase 4: 4** *(+1 task: T23)*  
**Total estimated build time: ~17h** *(+30m)*  
**Class A only (MVE): T1 + T2 + T4 + T5 + T6 + T7 + T8 + T9 + T16 ≈ 7h**  
**Full v0.2 (all classes + extras + integration + validation): ~17h**

### Eng review changes (2026-05-19)
- T3a: added G7 acceptance criterion (gws keyring banner strip unit test)
- T5: schema gap propagated — output must match updated §7 `per_entity_mention` schema (`input_class`, `section_context`, `line_business_signal`, `override_applied`, `context_window`); field name `line_business_signal` replaces `line_keyword_signal`
- T9: added G1 (pagination >100 blocks) and G2 (auto-repair duplicate `## Latest:` heading) acceptance criteria
- T12: added G3 (conf 0.88 below 0.92 floor → trust gate, not auto-staged)
- T14: added G4 (class A vs D collision: class A wins, stub surfaces as duplicate flag)
- T19: added G6 (3× PATCH 5xx → retry-queue → DLQ graduation → /start-day surfacing)
- T23: new task — PHI gate integration test for sync-sweep input path (G5)
