# Notion Workspace Reorganization Plan

**Status:** Plan v5 — parallel execution strategy added, LabAide handling relaxed. Phase 0 execution authorized 2026-05-29. Phase 5 deferred. Phase 6 parked.
**Drafted:** 2026-05-29 · revised v4: same day
**Authorization granted:** none yet for execution. Aaron has confirmed scope: do 1–4, hold 5.
**Top constraint (Aaron 2026-05-29):** zero data loss. Every mutating operation has a pre-write check and a snapshot. Hard stops on any condition the plan didn't anticipate. See §10.
**Canonical lab name decided:** `Lincoln Reference Laboratory` (fixes the legacy "Link & Reference Laboratory" typo while keeping the formal name).
**Mode at execution time:** must be `draft` so trust gate fires on every write.

---

## 1. Findings (what's actually wrong today)

### 1.1 `Workspace` select values have drifted across all four canonical DBs

The same business has different option names in different DBs. This silently breaks any filter that joins on Workspace and causes `/start-day` Workspace-aware queries to undercount.

| DB | Workspace options today |
|---|---|
| **Master Tasks** (`ece9b123…`) | `Link & Reference Laboratory`, `United IPA`, `Nestmate`, `Dock Pro`, `Other` |
| **Provider CRM** (`df3a3158…`) | `Lincoln Lab`, `United IPA`, `Nestmate`, `Dock Pro` *(no `Other`)* |
| **Activity Log** (`ec64cb70…`) | `Lincoln Lab`, `United IPA`, `Nestmate`, `Dock Pro`, **`LabAide`**, `Other`, **`Link & Reference Laboratory`** |
| **Meeting Notes** (`1dea3158…`) | `Link & Reference Laboratory`, `United IPA`, `Nestmate`, `Dock Pro`, `Other` |

**Target state (all 4 DBs identical):**
`Lincoln Reference Laboratory` · `United IPA` · `Nestmate` · `Dock Pro` · `Other`

### 1.2 Phantom duplicate Provider CRM

Two collections claim to be Provider CRM:
- `collection://ae0a3158-59b4-8235-b7ca-0758daa2322a` — the one `sources.yaml` reads. **Real one.**
- `collection://062feecb-7cea-4522-9283-64ba07f0c109` — orphan with identical schema.

**Activity Log's `Provider` relation field points to the orphan (`062feecb…`)**, not the real CRM. Every Activity Log → Provider link is therefore disconnected from the live data.

### 1.3 "Nestmate Account" relation is mislabeled

Master Tasks has a relation property called **`Nestmate Account`** pointing at `collection://32ca3158-59b4-81d0-9877-000b8bcd5639`. That collection's actual name is **`Speciality Pharmacy Account Tracking`** and its schema is a generic Notion product-tracker template (`Task name`, `Effort level`, `🐞 Bug`, `💬 Feature request`, `🦾Self`, `🏫Learn`, etc.) — clearly an unused template Aaron loaded and never repurposed.

### 1.4 HQ teamspace top level is a graveyard of loose provider pages

Pages floating at root of `Aaron Fainshtein's Workspace HQ` instead of being CRM rows:
- Dr Amy Goldberg
- Dr Mihammed Ali
- Dr. Adrianova
- Dr Rybstein (LocalMD Sunset Park)
- Dr Alex (LocalMD Sunset Park)
- Dr Tim ENG
- Dr Kiranpreet

Same pattern inside teamspace hubs — e.g. CardioPro page has `Eileen Endocrinologist`, `FM Medical Care`, `CY Medical Care` as child pages instead of CRM rows.

### 1.5 Meeting Notes DB hidden under one teamspace

Meeting Notes is parented under the `Lincoln Reference Laboratory` teamspace page even though Workspace can be any business. From any other teamspace it's invisible without searching.

### 1.6 Dead schema cruft

- Meeting Notes `Category` multi_select (`Planning`/`Standup`/`Presentation`/`Retro`/`Customer call`) — never populated; confirmed in `CLAUDE.md` and `sources.yaml` comments. Safe to delete.
- 2 trashed teamspaces still owned: `Reps`, `Dr Hussain's Clinical Research Trials`. Permanent delete.
- Master Tasks `Due soon` view has hard-coded end date `2026-04-10` (already in the past). Should be a relative range (`today` → `today + 7 days`).
- Master Tasks has 10 views, several redundant once Workspace-grouped Morning Report covers per-business filtering.

### 1.7 Row counts (sampled 2026-05-29)

| DB | Total rows | Lab-variant breakdown | Notes |
|---|---|---|---|
| Activity Log | 27 | 7 × `Link & Reference Laboratory`, 0 × `Lincoln Lab`, 0 × `LabAide` | 1 row has null Type → flag for Phase 2.7 backfill |
| Master Tasks | 41 | 11 × `Link & Reference Laboratory`, 0 × `Lincoln Lab`, 0 × `LabAide` | 7 rows have null Workspace (Inbox candidates — leave as-is) |
| Provider CRM (real) | 9 | 0 across all lab variants | 3 rows have null Workspace; 1 row totally blank (`336a3158…`) |
| Provider CRM (orphan) | **0** | n/a | **Empty! Phase 3 row migration unnecessary.** Schema repoint + archive only. |
| Meeting Notes | 6 | 0 across all lab variants | All 6 rows have null Workspace AND null Category. Phase 1.2 trivially safe. |
| SP Account Tracking | 13 | n/a (no Workspace field) | Active. Parented under Nestmate teamspace per Aaron 2026-05-29. Out of scope rebuild later. |

**Phase 0 completed 2026-05-29.** Snapshots written to `.context/applied/notion-reorg-phase-0-*-pre.json`, manifest with SHA-256 hashes at `state/notion-reorg-snapshot-manifest.yaml`.

**Phase 2 batch size measured:** 18 rows total need Workspace value PATCH (7 Activity Log + 11 Master Tasks). All `Link & Reference Laboratory` → `Lincoln Reference Laboratory`. No `Lincoln Lab` or `LabAide` rows exist anywhere — option-deletion assertions in Phase 2.4 will pass trivially for those.

**Phase 3 batch size measured:** 0 rows. The orphan CRM is empty and the Activity Log `Provider` column was observed empty in every sampled row. Phase 3 reduces to schema repoint + archive of the empty orphan DB.

---

## 1.8 Why this cleanup is the observability foundation

A late realization (per Notion's own startup-OS guide and the YC Startup-in-a-Box patterns surveyed 2026-05-29): the cleanup in Phases 1–4 isn't decoration. It's the prerequisite layer for "Gary Tan-level observability" — a single-pane-of-glass Company OS Home that surfaces per-business KPIs, blockers, and decisions across all 4 businesses.

The observability layer (designed in §8, scheduled as Phase 6) is only possible if:

| Phase 6 requirement | Provided by |
|---|---|
| Per-business linked views filter cleanly | Phase 2 — unified Workspace select |
| Decision panel shows provider context | Phase 3 — repointed Activity Log → real Provider CRM relation |
| Decision panel sees all decisions | Phase 2.7 — backfilled `Type` field on Activity Log |
| Linked views in skill code don't drift | Phase 4 — `sources.yaml` canonical convention + CLAUDE.md guardrail |
| KPI DB and Goals DB use the same Workspace vocabulary | Phase 4.6 — documented convention |

That's why Phases 1–4 are worth shipping even if Phase 6 never happens. They fix real bugs today (drift, broken relations, dead schema) **and** lay the rails for the founder-grade upgrade later.

---

## 2. Naming convention (decided)

| Concept | Canonical value | Notes |
|---|---|---|
| Lab business | `Lincoln Reference Laboratory` | Replaces both `Link & Reference Laboratory` (typo) and `Lincoln Lab` (informal). |
| IPA business | `United IPA` | Already consistent. |
| Nestmate | `Nestmate` | Already consistent. |
| Dock/Cardio Pro business | `Dock Pro` | Workspace-field value. Teamspace will be renamed from `Docpro` → `Dock Pro` to match. CardioPro stays as a sub-hub *inside* Dock Pro. |
| Fallback | `Other` | Add to Provider CRM (currently missing). |

**`sources.yaml` impact:** the `workspace_values.lab` entry must change from `"Lincoln Lab"` → `"Lincoln Reference Laboratory"`. Any skill code that pattern-matches on the literal `"Lincoln Lab"` string needs an audit — see Phase 4 checklist.

---

## 3. Target structure

```
HQ teamspace  (system layer — DBs and nothing else)
├── ✅ Master Tasks
├── 👥 Provider CRM
├── 📒 Activity Log
└── 🗓 Meeting Notes

Lincoln Reference Laboratory  (business teamspace)
└── 🏥 Lab Hub page
    ├── 1. Mission / overview
    ├── 2. Linked views (filtered to this Workspace)
    │   ├── Active tasks (Master Tasks · Workspace = Lincoln Reference Laboratory · Status ≠ Done)
    │   ├── Active accounts (Provider CRM · Workspace = … · Stage ≠ Inactive)
    │   ├── Recent activity (Activity Log · Workspace = … · last 30 days)
    │   └── Recent meetings (Meeting Notes · Workspace = … · last 60 days)
    ├── 3. Reference docs (flyers, templates, SOPs as child pages)
    └── 4. Dated topic pages (Granola append targets stay as they are)

United IPA   ← same hub template
Nestmate     ← same hub template
Dock Pro     ← same hub template, with CardioPro sub-hub
```

**Per-DB view set (collapse to 3–4 max):**

| DB | Keep | Delete |
|---|---|---|
| Master Tasks | `Morning Report` (grouped by Workspace), `By status` (board), `Due this week` (fixed filter), `Inbox (no workspace)`, `All tasks` (default) | `Lincoln Lab`, `United IPA`, `Nestmate`, `Dock Pro`, `Top-level tasks` — replaced by linked views on each teamspace hub |
| Provider CRM | `Pipeline Board`, `Needs Follow-Up`, `Default view` | `IPA Providers` (use Workspace filter on default) |
| Activity Log | `By Workspace`, `Calendar`, add `Last 7 Days` table | `Default view` (rename to "All") |
| Meeting Notes | `All Meetings`, add `By Workspace` | `My Notes` |

---

## 4. Execution plan (5 phases, ~17 atomic steps)

**Mode:** `draft` throughout. Every write hits the trust gate.
**Telemetry:** each phase emits one `notion-reorg` telemetry row to `logs/_telemetry.jsonl`.
**Rollback:** each phase exports a snapshot of affected rows to `.context/applied/notion-reorg-phase-N-YYYYMMDD.json` BEFORE mutating. If a phase needs to be reverted, the snapshot is the input to a restoration script.

### Phase 0 — Measure + FULL snapshot (read-only, no writes)

**Reinforced for zero-data-loss:** Phase 0 now exports the *complete* row state of every DB before any mutation begins, not just headers. These are the canonical rollback artifacts.

- 0.1 Query each canonical DB, paginating until `has_more: false`. Store totals + per-Workspace-value counts in §1.7.
- 0.2 **Full row dump** of orphan Provider CRM `062feecb…` → `.context/notion-reorg-orphan-crm-rows.json`. Every column, every row. Aaron's "full replace" decision means we won't read it again — but we keep the JSON forever as the audit trail.
- 0.3 **Full row dump** of Activity Log → `.context/applied/notion-reorg-phase-0-activity-log-pre.json`. Every column including `Provider`, `Task`, `Workspace`, `Type`, `Outcome`, `Next Action`, raw page IDs.
- 0.4 **Full row dump** of Master Tasks → `.context/applied/notion-reorg-phase-0-master-tasks-pre.json`. Same — every column including `Workspace`, `Status`, `Due`, `Assignee`, `Last Activity`, `Nestmate Account` relation values, `Parent Task` / `Subtasks` relation chains.
- 0.5 **Full row dump** of Provider CRM (real `ae0a3158…`) → `.context/applied/notion-reorg-phase-0-provider-crm-pre.json`. Every column including `Workspace`, `Stage`, `Notes`, `Related Task` relation values.
- 0.6 **Full row dump** of Meeting Notes → `.context/applied/notion-reorg-phase-0-meeting-notes-pre.json`. Every column including `Workspace`, `Category`, `Related Tasks`, `Attendees`.
- 0.7 **Full row dump** of `Speciality Pharmacy Account Tracking` (`32ca3158…`) → `.context/applied/notion-reorg-phase-0-sp-tracking-pre.json`. Per Aaron's decision this DB stays, but snapshot anyway in case Phase 2 needs to touch it.
- 0.8 Hash each snapshot file (SHA-256), store hashes in `state/notion-reorg-snapshot-manifest.yaml`. Tamper detection for rollback.
- 0.9 **Pre-flight assertions** (hard stop if any fail):
  - Mode is `draft`
  - All 4 canonical DBs return data successfully
  - `.context/applied/` is writable
  - Snapshot file count = expected (6 files)
  - At least one snapshot row is non-empty (catches accidentally empty exports)
- **Output:** updated row-count table in §1.7, snapshots staged, manifest checked in.

**Rollback artifact:** the 6 JSON files above are the canonical state of the Notion workspace at 2026-05-29 pre-cleanup. Any Phase 1–4 mutation can be reversed by reading the relevant snapshot and PATCHing rows back to their pre-state.

### Phase 1 — Low-risk cleanups (no schema change, no row rewrites)

**Reinforced for zero-data-loss:** even "low risk" steps now have pre-write content audits.

- 1.1 Permanently delete trashed teamspaces (`Reps`, `Dr Hussain's Clinical Research Trials`).
  - **Pre-write audit:** fetch each trashed teamspace, list ALL child pages and DBs. If any non-empty content exists, **HARD STOP** and ask Aaron page-by-page whether to keep. Export contents to `.context/applied/notion-reorg-phase-1-trashed-teamspace-<name>.json` regardless.
  - **Irreversible** once deleted. Trash → permanent purge.
  - Approval gate fires twice: once on audit results, once on the actual delete call.

- 1.2 Delete `Category` field on Meeting Notes.
  - **Pre-write audit:** query Meeting Notes for any row where `Category` is non-null. CLAUDE.md and `sources.yaml` say "never populated" but verify before dropping.
  - **Hard stop** if any row has `Category` set: list rows + values, ask Aaron whether to migrate to a different field (e.g., `Workspace`) or drop with confirmation.
  - If verified zero: drop column.

- 1.3 Fix `Due soon` view filter on Master Tasks: change end date from exact `2026-04-10` → relative `today + 7 days`.
  - View config change only. No row data touched.

- 1.4 Rename Master Tasks `Default view` → `All tasks` (cosmetic).
  - View metadata only. No row data touched.

**Risk:** Low for 1.2–1.4; the audit on 1.1 dictates whether 1.1 ships at all. **Approval gates:** 1.1 (twice), 1.2 (once, after audit result).

### Phase 2 — Workspace value unification + observability foundation

This phase isn't just data hygiene. The Workspace select is the **pivot** that makes the Company OS Home single-pane-of-glass possible (per Notion's startup-OS guide: "embed Goals/Tasks/Meetings databases in your wiki filtered by department"). A clean Workspace value across all 4 DBs is the prerequisite for per-business linked views, KPI roll-ups, and any future cross-DB rollup formulas.

For each of the 4 DBs:
- 2.1 Add new option `Lincoln Reference Laboratory` to the DB's Workspace select (if not present). **Additive only — never removes existing options at this step.**
- 2.2 Query all rows where Workspace is in {`Link & Reference Laboratory`, `Lincoln Lab`, `LabAide`}. **Snapshot every matching row's full state to `.context/applied/notion-reorg-phase-2-<db>-pre-migrate.json` BEFORE 2.3.**
- 2.3 For each matching row, PATCH `Workspace` → `Lincoln Reference Laboratory`. **One row at a time, action_id stamped per row, stamped success to `.context/applied/<aid>.json`.** Migration table (semantic mapping, no data lost):
  - `Link & Reference Laboratory` → `Lincoln Reference Laboratory` (typo fix, same business)
  - `Lincoln Lab` → `Lincoln Reference Laboratory` (informal → formal, same business)
  - `LabAide` → **LEAVE AS-IS.** Per Aaron 2026-05-29: keep LabAide as a separate Workspace value, do not migrate or delete. Any rows tagged `LabAide` stay tagged. The option remains in the Activity Log Workspace select. Treat LabAide as its own thing (a separate product/page space), not as a synonym for the lab business.
- 2.4 **Pre-delete assertion (hard stop on fail):** re-query each old option after 2.3. If row count > 0 for ANY old option, do NOT delete that option. List remaining rows, escalate to Aaron.
- 2.5 Once asserted zero, delete the old options (`Link & Reference Laboratory`, `Lincoln Lab`). **`LabAide` is NOT deleted** — preserved per Aaron 2026-05-29.
- 2.6 On **Provider CRM** only: add `Other` option (currently missing — purely additive, no data risk).
- 2.7 **Observability prep — Activity Log `Type` backfill (writes ONLY to nulls):**
  - Query Activity Log for rows where `Type` is null.
  - **Snapshot affected rows** to `.context/applied/notion-reorg-phase-2-activity-log-type-backfill-pre.json`.
  - Apply heuristic: "DECISION:" prefix or "decided to" → `Decision`; "meeting" → `Meeting`; "called" or " call " → `Call`; "visited" or "visit" → `Site Visit`; "email" → `Email`; else **leave null and flag for manual review** (don't guess).
  - Apply only to rows where heuristic matched with confidence (one of the keywords is unambiguous).
  - Confidence < high → flag to `.context/notion-reorg-type-backfill-uncertain.json` for Aaron to review. Never overwrite existing non-null `Type` values.
- 2.8 Update `config/sources.yaml`:
  - `workspace_values.lab: "Lincoln Reference Laboratory"`
  - `notion_databases[0].workspace_values` mirror new option set across all 4 DBs
  - Add a comment noting Phase 6's KPI DB will reuse these exact values — do not drift again.

**Risk:** Medium. Activity Log alone has 7 rows to rewrite for Workspace + an unknown count for Type backfill. Master Tasks + Meeting Notes counts measured in Phase 0. **Approval gate:** explicit per-DB confirmation before each PATCH batch.

**What Phase 6 inherits from this:** clean Workspace pivot across all 4 DBs + reliable Activity Log Type field. Without this, the Company OS Home page can't be built.

### Phase 3 — Phantom CRM resolution

This phase fixes the broken Activity Log → Provider link. Critical for Phase 6's Company OS Home, where the "Recent decisions" panel needs to show *which provider* the decision was about — currently that link is severed.

**Zero-data-loss rework:** Aaron's "full replace" decision applies to the CRM *table*, NOT to the relation links from Activity Log. Those relation links are real semantic data ("this decision was about Dr X") and must be preserved. Refactored to match-and-migrate the relation values before clearing anything.

- 3.1 Snapshot already done in Phase 0.2.
- 3.2 **Build a name → real-CRM-page-id mapping table.** For each orphan-CRM page (snapshot at Phase 0.2), look up the real Provider CRM (`ae0a3158…`) by `Provider Name` exact match. Output:
  - `state/notion-reorg-provider-id-mapping.yaml` — `<orphan_page_id>: <real_page_id_or_NULL>`
  - **Hard stop if any orphan-CRM row has no name match in the real CRM AND that orphan row is referenced by ≥1 Activity Log row.** That's a row we'd lose context on. Escalate to Aaron with the row list.
  - Aaron's options at the hard stop: (a) create the missing provider in the real CRM and rerun; (b) accept the link will be cleared; (c) abort Phase 3.
- 3.3 **Migrate Activity Log relation values** (one row at a time, snapshot-then-PATCH):
  - For each Activity Log row whose `Provider` references an orphan-CRM page, look up the mapping.
  - If mapped → rewrite the relation value to the real-CRM page-id. The link is preserved.
  - If unmapped (after Aaron's call in 3.2) → clear the relation. Log cleared rows to `.context/notion-reorg-cleared-provider-refs.json` with the orphan page name + page-id so the link can be reconstructed manually if needed.
  - Each PATCH stamped with action_id.
- 3.4 Repoint Activity Log's `Provider` relation property schema target to `collection://ae0a3158-59b4-8235-b7ca-0758daa2322a`. **Schema change on Activity Log.** Snapshot the existing Activity Log schema to `.context/applied/notion-reorg-phase-3-activity-log-schema-pre.json` first.
- 3.5 **Pre-archive assertion** (hard stop on fail): re-query the orphan CRM. Any pages still referenced by Activity Log? If yes, do NOT archive — escalate. The migration in 3.3 should have cleared all incoming relations, but verify.
- 3.6 Archive orphan CRM `062feecb…` to Trash via `notion-update-data-source in_trash=true`. **Trash is undoable for 30 days in Notion** — not a permadelete.
- 3.7 **Observability prep + post-write verification** — verify Activity Log's `Provider` and `Task` relations work after repoint. Pick 3 recent rows, fetch their Provider/Task links, confirm bidirectional traversal works in the Notion UI. Compare against Phase 0.3 snapshot to confirm row counts unchanged.

**Risk:** Medium. Relation migration is now real work but preserves every link with a name match. **Approval gates:** required at 3.2 (mapping table review, any unmatched rows), 3.3 (start migration), 3.4 (schema flip), 3.6 (archive). Four gates.

**What Phase 6 inherits from this:** working Activity Log → Provider → Task relation chain pointing at the only real CRM. No phantom dataset.

**What Phase 6 inherits from this:** working Activity Log → Provider → Task relation chain. The 3-hop traversal (Decision → Provider → outstanding Tasks for that Provider) is what makes the "blockers panel" actually useful.

### Phase 4 — `sources.yaml` + skill code audit + CLAUDE.md sync (no Notion writes)

- 4.1 Update `config/sources.yaml`:
  - `workspace_values.lab` → `"Lincoln Reference Laboratory"`
  - Confirm `notion_databases[0].workspace_values` accurately mirror the new option set
  - Add inline comment block at top documenting "canonical Workspace values — do not drift" so future Phase 6 work and any new DB follows the convention.
- 4.2 `grep` for literal strings `"Lincoln Lab"`, `"Link & Reference Laboratory"`, `"LabAide"` across `.claude/skills/`, `scripts/`, `config/`. List occurrences and patch each. Expect hits in:
  - `start-day` SKILL.md (filter queries)
  - `end-day` SKILL.md (workspace bucketing)
  - `capture-meeting` routing rules
  - `scripts/vault_search.py` if any Workspace string is hardcoded
  - `CLAUDE.md` and `AGENTS.md` (Department Routing Rules table)
- 4.3 Update **CLAUDE.md** and **AGENTS.md** Department Routing Rules table — change `"Lincoln Lab"` Workspace Value column to `"Lincoln Reference Laboratory"`. Both files since AGENTS.md is the Codex mirror.
- 4.4 Run `scripts/skill_lint.sh` to confirm all skills still validate after edits.
- 4.5 Dry-run `/start-day` in observe mode (`state/coo_mode.yaml` mode=observe), confirm Lincoln Reference Laboratory section populates with correct rows.
- 4.6 **Observability prep** — append a `# Workspace conventions` section to `CLAUDE.md` listing the canonical 5 values + the rule that any new DB in this workspace MUST use this exact option set. This is the convention guardrail Phase 6 leans on.

**Risk:** Medium — string-level changes can be missed. Mitigation: comprehensive grep + observe-mode dry run + skill lint.

**What Phase 6 inherits from this:** documented convention that future KPI DB, Company OS Home filters, and any new DB will all key off the same Workspace values. Drift prevention.

### Phase 5 — Structural cleanup (hub pages + view trimming) — **DEFERRED**

**Status:** Held for a later session. Aaron's call 2026-05-29: complete Phases 1–4 first, let the cleaned baseline settle for a week, then revisit. Listed here so the design is captured.

- 5.1 Rename teamspace `Docpro` → `Dock Pro` (cosmetic). Confirm no hardcoded path breakage.
- 5.2 For each business teamspace, build/refresh the standard Hub page template using the existing Lincoln Lab page (`335a3158-59b4-814e-aa87-df56b4c3bb73`) as the model. Add linked views of the 4 canonical DBs filtered to that Workspace.
- 5.3 Move the 4 canonical DBs to live directly under the HQ teamspace (currently Meeting Notes is under Lincoln Reference Laboratory teamspace page). This is a parent-page reparenting.
- 5.4 Delete redundant Master Tasks views (`Lincoln Lab`, `United IPA`, `Nestmate`, `Dock Pro`, `Top-level tasks`) — replaced by per-hub linked views. **Notion API does not expose a delete-view endpoint — this step requires manual UI action.**
- 5.5 Delete `IPA Providers` view from Provider CRM, `My Notes` view from Meeting Notes. **UI action.**
- 5.6 Drop the `Nestmate Account` relation on Master Tasks (mislabeled, never used as designed). Decision: rebuild as a real Nestmate Accounts DB **in a separate dedicated session** — out of scope for this reorg.

**Why deferred:**
- 5.1 requires UI action (no API endpoint for teamspace rename — confirmed by checking the available Notion MCP tool surface).
- 5.4 and 5.5 require UI action for the same reason (no delete-view API).
- 5.2 hub page rebuild is real content work — better done once Phases 1–4 land and you can see the cleaned DBs render correctly.

**Risk when eventually shipped:** Low for view deletions, Medium for DB reparenting (5.3). Mitigation: verify each DB's URL still resolves after parent change — Notion preserves DB IDs through reparenting, but the `parent_id` shown in `sources.yaml` may need a doc update if we track it.

---

## 5. Out of scope (separate sessions)

- **Loose HQ provider pages → CRM rows migration.** Each of the 7 floating provider pages needs manual content reshaping (extract phone/email/notes/stage from freeform page body into CRM properties). Schedule as its own session — call it `/notion-provider-page-migration` (one-off, not a recurring skill).
- **CardioPro sub-page providers** (Eileen Endocrinologist, FM Medical Care, CY Medical Care) — same problem, included in that session. Note: CardioPro stays as a sub-page inside Docpro teamspace (Aaron 2026-05-29), so this migration moves *providers* out, not the CardioPro hub itself.
- **`Speciality Pharmacy Account Tracking` collection rebuild.** Aaron 2026-05-29: keep, owned by Nestmate, treat as the Specialty Pharmacy program's home. Rebuild the schema (replace generic Notion template fields with SP-program fields: doctor, drug class, CDTM status, monthly script volume, etc.) and rename to something like `Specialty Pharmacy Accounts` in a separate dedicated session. Until then, the mislabeled `Nestmate Account` relation on Master Tasks is preserved as-is.
- **Granola sync-gap monitoring (`/sync-sweep`).** Already planned separately in `project_sync_sweep_skill.md`. Reorg doesn't touch it.

---

## 6. Pre-execution checklist

Before starting Phase 0, confirm:

- [ ] `state/coo_mode.yaml` is `draft` (not `auto`)
- [ ] `git status` clean OR current changes committed
- [ ] `.context/` directory empty of pending writes (run `/start-day` pre-flight)
- [ ] Notion API token (`NOTION_API_TOKEN`) valid — `scripts/preflight.sh` returns `NOTION_OK=1`
- [ ] Aaron has explicitly approved the canonical naming decision (✅ — `Lincoln Reference Laboratory`, confirmed 2026-05-29)
- [ ] `.context/applied/` directory exists and is writable (target for snapshot files)
- [ ] `state/notion-reorg-snapshot-manifest.yaml` will be created during Phase 0.8 — file does not need to exist yet
- [ ] Aaron acknowledges the "zero data loss" discipline in §9.5 — every hard stop is honored, no proceeding past escalation without explicit decision (✅ — confirmed 2026-05-29)

---

## 7. Decision log

| Date | Decision | By |
|---|---|---|
| 2026-05-29 | Canonical lab name = `Lincoln Reference Laboratory` | Aaron |
| 2026-05-29 | Build written plan first, no writes | Aaron |
| 2026-05-29 | Out-of-scope: loose provider pages → CRM (separate session) | Claude (proposed) |
| 2026-05-29 | Execute Phases 1–4 now; defer Phase 5; Phase 6 stays parked but informs Phase 2–4 design | Aaron |
| 2026-05-29 | Phase 5.1, 5.4, 5.5 will require manual UI work (no API endpoints) when eventually shipped | Claude (research, confirmed via tool surface check) |
| 2026-05-29 | **Orphan Provider CRM (`062feecb…`):** treat as fully replaced. Archive after repoint, regardless of row count. | Aaron |
| 2026-05-29 | **Meeting Notes parent:** stay neutral / keep current parent — DB serves multiple businesses, don't lock under any single teamspace. Phase 5.3 (reparent to HQ) is NOT planned; leave under Lincoln Reference Laboratory teamspace or move to a neutral HQ root in Phase 5 — decide then. | Aaron |
| 2026-05-29 | **CardioPro hierarchy:** stays as sub-page inside Docpro teamspace. No teamspace promotion. | Aaron |
| 2026-05-29 | **`Speciality Pharmacy Account Tracking` collection:** keep, owned by Nestmate. Rebuild as a real Nestmate-sub-program DB in a separate session (Specialty Pharmacy is the active Nestmate program). The mislabeled `Nestmate Account` relation on Master Tasks is preserved for now; rename to `Specialty Pharmacy` or rebuild in that dedicated session. | Aaron |

---

## 8. Observability layer — "Gary Tan-level" upgrade (additive to the cleanup)

The cleanup above just gets you to a clean, consistent baseline. To get to founder-grade visibility — one pane of glass across all 4 businesses, decisions/blockers surfaced automatically, KPIs tracked weekly — you need to add a thin **company-OS layer on top**. This is the Notion equivalent of what YC's "Startup in a Box" templates and Notion's own "Company Home" guide recommend, adapted for a multi-business operator.

### 8.1 What "Gary Tan-level observability" actually means here

Three things, no more:

1. **One number per business** that tells you if it's healthy this week.
2. **Decisions are searchable** — you can answer "why did we stop X?" in <30 seconds from any device.
3. **Blockers surface themselves** — you don't have to remember to look; the system flags them in your daily briefing.

The current setup already gives you #2 partially (Activity Log with `Type=Decision`) and #3 partially (`/start-day` stale-task surfacing). What's missing is #1, plus the central dashboard that ties all three together.

### 8.2 Proposed additions

**A. New DB: `Company KPIs`** (lives in HQ teamspace)

| Property | Type | Notes |
|---|---|---|
| KPI Name | title | e.g. "Lab samples/month", "IPA MMR", "Nestmate new accounts/month" |
| Workspace | select | Same canonical 5 values |
| Target | number | Annual or quarterly target |
| Current | number | Most recent reading |
| Trend | formula | `if(Current >= Target, "✅", if(Current >= Target*0.7, "⚠️", "🔴"))` |
| Period | select | Weekly / Monthly / Quarterly |
| Updated | last_edited_time | |
| Notes | text | Context for the number |

Start with 2–3 KPIs per business. Don't over-engineer.

**B. New page: `Company OS Home`** (top of HQ teamspace)

Single-pane-of-glass page. Sections:
1. **This week's focus** — 1–3 bullets, hand-edited Monday morning by `/start-day`.
2. **KPI snapshot** — linked view of Company KPIs grouped by Workspace, showing Trend emoji + Current/Target.
3. **Active blockers** — linked view of Master Tasks filtered to `Status=Waiting` AND `last_edited > 7 days`, grouped by Workspace.
4. **Recent decisions (7d)** — linked view of Activity Log filtered to `Type=Decision` AND `Date is on or after relative -7 days`.
5. **Open pipeline** — linked view of Provider CRM grouped by Stage (excluding Active/Inactive).
6. **Quick links** — to each business teamspace hub.

This page becomes Aaron's home screen. Both `/start-day` mobile briefing and the web view read from the same linked views — single source of truth.

**C. Formalize `Decision` discipline**

Activity Log already has `Type=Decision`. Add a soft rule (enforced via `/end-day` braindump extractor): any line starting with "DECISION:" or containing "decided to" or "pivoted to" auto-creates a row with `Type=Decision` and links to relevant Provider/Task. The KPIs and blockers panels in Company OS Home pull from this stream.

**D. Page metadata convention** (per Notion's own startup-OS guide)

Every "important" page (not daily/meeting notes — those are throwaway) gets:
- `Owner` (person)
- `Status` (select: Draft / Active / Archive)
- `Last reviewed` (date, manually bumped quarterly)

Apply to: each teamspace hub page, reference docs (SOPs, templates, flyers), any strategy doc. Skip dated meeting/topic pages and daily notes.

**E. Weekly Ops ritual — formalize via `/automation`**

`/weekly-review` already exists as an automation entry. Add an output template that writes a dated page under HQ → `Weekly Reviews/` with sections:
- **Focus achieved / missed** — what last week's "This week's focus" delivered
- **KPI deltas** — compare Company KPIs vs last week
- **Decisions this week** — pull from Activity Log
- **Blockers cleared / new** — Master Tasks delta
- **Next week's focus** — feeds back into Company OS Home top section

The 30-minute Monday-morning ritual instead of ad-hoc.

### 8.3 Effort vs payoff

| Addition | Build effort | Daily payoff |
|---|---|---|
| Company KPIs DB | 1 hr (DB + 8–12 seed rows) | High — gives you the single number you don't have today |
| Company OS Home | 2 hrs (page + 5 linked views) | High — replaces scrolling through 4 teamspaces |
| Decision discipline | 30 min (rule in `/end-day`) | Medium — better post-hoc lookups |
| Metadata convention | 1 hr (initial backfill on ~20 pages) | Low — quality-of-life |
| Weekly Ops formalized | 1 hr (template + automation update) | Medium — depends on whether you actually do the ritual |

Total: ~5–6 hrs of work. None of it touches the canonical DBs structurally — purely additive.

### 8.4 Where this folds into the execution plan

Add as **Phase 6** (optional, runs after Phase 5):

- 6.1 Create Company KPIs DB. Seed 2–3 rows per business with current best-guess targets.
- 6.2 Create Company OS Home page at HQ root. Embed 5 linked views.
- 6.3 Update `/end-day` SKILL.md to flag DECISION-prefixed lines for Activity Log auto-creation. Keep behind trust gate.
- 6.4 Update `/weekly-review` automation template to output to dated `Weekly Reviews/` page.
- 6.5 One-time pass: stamp `Owner`/`Status`/`Last reviewed` on the ~20 important pages identified in 5.2.

Phase 6 can ship independently — no dependency on Phases 2–5 being complete (though it's prettier on a clean base).

---

## 9.4 Parallel agent execution strategy

Per Aaron's request 2026-05-29: execute via parallel agent fan-out where the COO Twin team-skill discipline applies. This repo already has the pattern (`*-team` skills under `.claude/skills/`): coordinator dispatches read-only workers in parallel, workers return structured JSON, coordinator merges + makes all writes through the trust gate.

### 9.4.1 Parallelization rules

- **Workers read; coordinator writes.** Same as `start-day-team` and `end-day-team`. Workers use parallel tool calls within a single message (functionally equivalent to subagent fan-out for I/O-bound Notion API work, with much less overhead). Heavier subagent fan-out only used when a worker needs to do real synthesis.
- **Single Agent message, N parallel calls** when subagents are warranted. Coordinator never inlines worker logic.
- **Telemetry per worker AND per coordinator action.** Each row in `logs/_telemetry.jsonl` tagged `skill: notion-reorg`, with `phase` + `step` + `worker` fields.
- **Hard stops halt the whole phase, not just one worker.** If any worker returns an assertion failure or unexpected count, the coordinator does not proceed to the next step.

### 9.4.2 Per-phase parallelism map

| Phase | Step | Parallelism strategy |
|---|---|---|
| 0.1–0.7 | Snapshot 6 DBs | **6 parallel `notion-fetch` + `notion-query-database-view` calls** in a single coordinator message. Coordinator writes 6 JSON files sequentially after results return. |
| 0.8 | Hash manifest | Single-threaded (depends on 0.1–0.7 completing) |
| 0.9 | Pre-flight assertions | 4 parallel checks (mode, file count, non-empty, MCP available) |
| 1.1 | Trashed teamspace audit | **2 parallel reads** (one per trashed teamspace). Hard stop on non-empty. Sequential delete after Aaron's per-teamspace gate. |
| 1.2 | Category non-null check | Single query (one DB) |
| 1.3, 1.4 | View config edits | Sequential (small) |
| 2.1 | Add new Workspace option to 4 DBs | **4 parallel `notion-update-data-source` ADD COLUMN-like ops** |
| 2.2 | Snapshot pre-migrate rows per DB | **4 parallel queries** |
| 2.3 | PATCH Workspace value on rows | **Serial within DB** (trust gate per row), **parallel across DBs** (4 concurrent batches) |
| 2.4 | Zero-count re-assert per DB | **4 parallel queries** |
| 2.5 | Delete obsolete options | **4 parallel ops** (independent DBs) |
| 2.6 | Add `Other` to Provider CRM | Single op |
| 2.7 | Activity Log Type backfill | Serial (one DB, trust gate per uncertain row) |
| 2.8 | sources.yaml edit | Single op |
| 3.2 | Build orphan→real CRM mapping | **Parallel name lookups** (one per orphan row) into real CRM |
| 3.3 | Migrate Activity Log Provider relations | **Parallel PATCHes** (each Activity Log row independent), serial trust gate batching |
| 3.4–3.7 | Schema flip + archive + verify | Sequential dependency chain |
| 4.1, 4.2, 4.3 | sources.yaml + grep + CLAUDE.md/AGENTS.md | **3 parallel reads to identify diff sites**, sequential writes (file Edit ordering) |
| 4.4, 4.5, 4.6 | Lint + dry-run + convention append | Sequential |

### 9.4.3 What this saves

Phase 0 alone: 6 sequential Notion fetches at ~2s each = ~12s. Parallelized = ~2.5s. Across Phases 1–4 the wall-time win is ~3-4x because most steps are I/O bound on the Notion API.

The discipline win is bigger: trust-gate batching by DB rather than by row keeps Aaron's approval count manageable while preserving per-row idempotency.

---

## 9.5 Data preservation guarantees

Per Aaron's hard constraint (2026-05-29): **zero data loss across the merge.** Every mutating operation in Phases 1–4 is gated by the following discipline:

### 9.5.1 The four guarantees

1. **Every row that will be mutated is snapshotted BEFORE the PATCH.** The snapshot is a full JSON dump including all columns and relation page-ids, stored under `.context/applied/` with a hash in `state/notion-reorg-snapshot-manifest.yaml`.
2. **Every schema delete (option, property, view) is preceded by a zero-count assertion.** If any row uses the value/property being deleted, the operation HARD STOPS and escalates. No silent data nuking.
3. **Every relation mutation tries to migrate, not clear.** The Phase 3 orphan-CRM cleanup matches by Provider Name first; only clears links that have no match AND are explicitly approved by Aaron for clearing.
4. **Every irreversible action (permadelete teamspace, drop column) has an explicit human approval gate.** Notion's Trash gives us a 30-day undo window for archived DBs and pages, but property drops and teamspace deletes are not in that net — they get the strictest gating.

### 9.5.2 Operations that could lose data (catalogued)

| Phase | Operation | Mitigation |
|---|---|---|
| 1.1 | Permadelete trashed teamspaces | Audit child content first, snapshot, two approval gates. HARD STOP if non-empty. |
| 1.2 | Drop `Category` column on Meeting Notes | Assert zero non-null first. HARD STOP otherwise. |
| 2.3 | PATCH `Workspace` value on rows | Per-row snapshot pre-PATCH. Migration table is semantic (typo fix, formal/informal — same business). |
| 2.5 | Delete old Workspace options | Re-assert zero-count after migration. HARD STOP if any old option still has rows. |
| 2.7 | Backfill `Type` on Activity Log | Writes only to nulls. Existing non-null values never overwritten. Uncertain rows flagged for manual review, never guessed. |
| 3.3 | Rewrite Activity Log `Provider` relations | Migrate-then-clear: try name match first, only clear unmatched after Aaron's call. |
| 3.4 | Repoint Activity Log `Provider` schema target | Schema snapshot before change. |
| 3.6 | Archive orphan CRM | 30-day Notion Trash undo. Not permadelete. |

### 9.5.3 What "zero data loss" explicitly means here

- Every Notion page currently in the workspace is still reachable (in-place, migrated, or trashed-but-recoverable) after Phase 4 completes.
- Every populated property value either survives unchanged, is updated to a semantically equivalent value (e.g., Workspace name normalization), or is captured in a `.context/applied/` snapshot before being changed.
- Every relation link either survives unchanged, is repointed to an equivalent target, or is captured in `notion-reorg-cleared-provider-refs.json` with enough context to manually reconstruct.
- No teamspace, DB, or page is permanently deleted without an explicit audit + Aaron's approval.

If at any point an operation cannot satisfy the above, it stops. The plan does not proceed past a hard stop without an explicit Aaron decision.

---

## 9.6 Rollback procedure

If anything goes wrong during Phases 1–4, the rollback path is:

1. **Stop further mutations.** Set `state/coo_mode.yaml` to `locked`.
2. **Identify the affected phase** from `logs/_telemetry.jsonl` (every action_id is logged with timestamp and the snapshot file it preserved).
3. **For row-level data:** read the per-phase snapshot from `.context/applied/notion-reorg-phase-N-<db>-pre.json` or `notion-reorg-phase-N-<db>-pre-migrate.json`. Diff against current Notion state. For each row whose state diverges from snapshot, PATCH back to snapshot values (action_id stamped as `notion-reorg-rollback:…`).
4. **For schema-level data:** read the schema snapshot from `.context/applied/notion-reorg-phase-N-<db>-schema-pre.json`. Re-add dropped properties via `notion-update-data-source` with the original type/options/relation target.
5. **For deleted options:** re-add the option to the Workspace select, then PATCH-back any rows using the snapshot.
6. **For archived DBs:** un-archive via Notion UI (the orphan CRM at `062feecb…` would be restored this way).
7. **For permadeleted teamspaces:** unrecoverable. This is exactly why Phase 1.1 has the two-gate hard stop on non-empty content.

Snapshot manifest at `state/notion-reorg-snapshot-manifest.yaml` is the index — start there.

---

## 10. Open questions — resolution status

| # | Question | Resolution (2026-05-29) |
|---|---|---|
| 1 | Orphan Provider CRM (`062feecb…`) — keep any rows? | **Resolved.** Full replace. Archive after Activity Log relation repoint, regardless of row count. Phase 0.2 still snapshots rows for rollback safety. |
| 2 | Meeting Notes reparenting (5.3) | **Resolved.** Stay neutral — DB serves all businesses. Don't move it into a single teamspace. Phase 5 (deferred) revisits whether neutral HQ root is even better. |
| 3 | CardioPro vs Dock Pro hierarchy | **Resolved.** CardioPro stays inside Docpro teamspace. |
| 4 | Speciality Pharmacy Account Tracking collection | **Resolved.** Keep, owned by Nestmate. Rebuild as a real Nestmate-sub-program DB in a separate session. Mislabeled `Nestmate Account` relation on Master Tasks stays for now; revisit rename to `Specialty Pharmacy` during that rebuild. |
| 5 | Phase 6 (observability layer) timing | **Resolved.** Park Phase 6. Phases 1–4 ship first; Phase 6 informs their design but doesn't block. |
| 6 | KPI seed list per business | **Open** — only matters if/when Phase 6 ships. Not blocking 1–4. |

**All gates for Phase 0 are now resolved.** Ready to proceed when authorized.
