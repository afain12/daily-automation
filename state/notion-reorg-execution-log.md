# Notion Reorg + Company OS — Execution Log

**Date:** 2026-05-29 · **Mode:** draft · **Operator:** Claude Code (hybrid MCP + Playwright)
**Design doc:** `state/notion-reorg-plan.md` · **Rollback net:** `.context/applied/notion-content-export/` (273 pages)

This log records what actually changed in the live Notion workspace this session. Every
mutation is reversible (see Rollback column).

---

## 0. Correction to prior belief

The reorg plan (`notion-reorg-plan.md`) assumed Phases 1–4 were unstarted. **Live verification
on 2026-05-29 showed they were already executed** (done directly via the Notion MCP, so no
`logs/_telemetry.jsonl` rows or `.context/applied/` action_id stamps existed — that absence
misled the first status read). Confirmed already-done in the workspace before this session:

- Workspace `select` unified across all 4 canonical DBs → `Lincoln Reference Laboratory`,
  `United IPA`, `Nestmate`, `Dock Pro`, `Other` (+ `LabAide` preserved on Activity Log).
  The 19 rows formerly tagged `Link & Reference Laboratory` migrated cleanly (no data loss).
- `Category` field dropped from Meeting Notes.
- `Due soon` view date fixed to relative `today`.
- `Default view` renamed `All tasks`.
- Activity Log `Provider` relation already repointed to the real CRM (`ae0a3158…`).
- `config/sources.yaml` `workspace_values.lab` already = `Lincoln Reference Laboratory`.

---

## 1. Content backup (read-only, data preservation)

Full page-body export of all live teamspaces, since the Phase-0 snapshots only held DB rows.

- **273 unique pages, 1.1 MB** → `.context/applied/notion-content-export/pages/<pageid>.md`
  (frontmatter + verbatim body; `ancestor_path` preserves folder tree).
- Index: `_manifests/index.tsv` · self-doc: `README.md`.
- Built by 5 parallel export workers. Covers Meeting Notes, Provider CRM, SAIPA Providers (102),
  Master Tasks (42), Activity Log (28), SP Account Tracking (14), all hub pages, the SP
  referral-flyer folder (10 children), recursed children.
- **Not captured:** file-attachment bytes (xlsx/pdf/pptx — API links only), Granola transcripts,
  the two trashed teamspaces (Reps, Dr Hussain's — excluded per Aaron, low priority).

---

## 2. Company OS layer (additive, via MCP)

### New page
| Item | ID / URL | Parent |
|---|---|---|
| 🛰️ **Company OS Home** | `36fa3158-59b4-814e-ab92-dd7f5c885ab0` | Command Center (`335a3158-59b4-815b-863d-c585bf957dc8`) |

### Linked views ON Company OS Home (3)
| View | Source DB | Filter / config | View ID |
|---|---|---|---|
| Active blockers | Master Tasks | `Status = Waiting` (set via Playwright) | `36fa3158-59b4-8105-83ee-000c49666f3b` |
| Recent decisions | Activity Log | `Type = Decision`, sort Date desc | `36fa3158-59b4-8109-9a79-000cb8613483` |
| Open pipeline | Provider CRM | board, group by Stage | `36fa3158-59b4-818b-b644-000cb5e24038` |

### Business hub pages — 4 linked views each (Active tasks · Accounts · Recent activity · Recent meetings), filtered to that Workspace
| Hub page | Page ID | Workspace value |
|---|---|---|
| 🔬 Lincoln Reference Laboratory | `335a3158-59b4-814e-aa87-df56b4c3bb73` | Lincoln Reference Laboratory |
| 🏥 United IPA | `335a3158-59b4-81eb-93ff-dd678a357924` | United IPA |
| 🐝 Nestmate | `335a3158-59b4-8125-bf09-de765977e77f` | Nestmate |
| ⚓ Dock Pro (on CardioPro page) | `335a3158-59b4-81b6-9908-cce7eea0e120` | Dock Pro |

Total added: **1 page + 20 linked views.** All reversible (delete the page / views).

---

## 3. Cleanup / destructive changes

| Change | Target | Tool | Rollback |
|---|---|---|---|
| Fixed broken view filter | Master Tasks `Lincoln Lab` view (`335a3158-59b4-8116…`): `Link & Reference Laboratory` → `Lincoln Reference Laboratory` | MCP `update-view` | re-set filter |
| Trashed empty orphan CRM | `062feecb-7cea-4522-9283-64ba07f0c109` (0 rows, nothing referenced it) | MCP `update-data-source in_trash` | un-trash within 30 days |
| Deleted 4 redundant views | Master Tasks: `Top-level tasks`, `United IPA`, `Nestmate`, `Dock Pro` | Playwright | recreate from `.context/applied/notion-ui-ops/views-rollback.json` |

**Master Tasks views remaining (clean):** All tasks · By status · Inbox (no workspace) ·
Due soon · Lincoln Lab (fixed) · Morning Report.

---

## 4. NOT done (deliberate)

- **Reparent the 4 canonical DBs under the HQ teamspace root** — `move-pages` cannot target a
  teamspace root (only page / database / data_source / workspace), and the linked-view hubs make
  each DB's physical location irrelevant. Skipped rather than risk a flaky sidebar drag.
- Permadelete / restore of the two trashed teamspaces — left as-is per Aaron.
- Loose provider pages → CRM rows migration — out of scope (separate session, per plan §5).

---

## 5. New tooling built

- **`/notion-ui-ops` skill** (`.claude/skills/notion-ui-ops/SKILL.md`) — hybrid model: MCP-first,
  Playwright backup for the gaps. Passes `scripts/skill_lint.sh`. Documents the verified MCP↔
  Playwright capability split + auth recipe + techniques.
- **Playwright harness** (`scripts/notion-ui-ops/`): persistent profile + real Chrome channel
  (`channel: 'chrome'` + automation flags stripped so Google SSO doesn't block). Scripts:
  `login.mjs`, `delete-view.mjs`, `filter-apply.mjs`, `config.mjs`. `profile/`, `node_modules/`,
  `storageState.json` are gitignored.

### Verified MCP capability map (for future work)
- ✅ MCP can: create pages, create linked views, rename/refilter views (select-type), archive
  data sources (`in_trash`), move pages (to a page/workspace).
- ❌ MCP cannot: **delete a view**, **filter status-type properties** (`FILTER "Status" = …`
  silently drops — use Playwright Filter toolbar → Status, or a board grouped by Status),
  **move to a teamspace root**, rename a teamspace. → Playwright for these.

---

## 6. Evidence trail

- View configs (pre-delete): `.context/applied/notion-ui-ops/views-rollback.json`
- Screenshots per op: `.context/applied/notion-ui-ops/del-*`, `fapply-*`, etc.
- Content backup: `.context/applied/notion-content-export/`
- This session did NOT emit `notion-reorg` telemetry rows (work ran via MCP/Playwright, not the
  skill helper scripts). The artifacts above are the canonical record.
