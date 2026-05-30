---
name: notion-ui-ops
description: >-
  Drives Notion operations the REST/MCP API CANNOT do: delete/rename database
  views, create linked-database views, rename teamspaces, drag-reparent pages/DBs,
  download file attachments, configure buttons/automations. Two mechanisms — the
  unofficial private Notion API (web client's own endpoints; robust, scriptable)
  preferred for structural ops, with browser DOM automation (gstack `browse`
  headless + visible `connect-chrome`) as fallback and for visual verification.
  Screenshot-before+after on every mutating step. Trust gate before any write.
  Companion to the API-based reorg work in state/notion-reorg-plan.md.
coo_twin:
  category: admin
  mode_required: draft+
  writes_external: true
  preflight: required
  experimental: true
---

# /notion-ui-ops — Notion UI / private-API operations

You execute Notion changes that the official API (REST + Notion MCP) cannot reach.
**Everything here mutates a production, multi-business workspace.** The full content
backup at `.context/applied/notion-content-export/` (273 pages, 2026-05-29) is the
rollback net, but you still treat every step as irreversible-until-verified.

## Why this skill exists (the API ceiling)

Confirmed unreachable by REST/MCP as of 2026-05-29:

| Operation | API | This skill |
|---|---|---|
| Delete / rename a database **view** | ❌ | ✅ |
| Create a **linked-database view** (Company OS Home) | ❌ | ✅ |
| Rename a **teamspace** (e.g. `Docpro` → `Dock Pro`) | ❌ | ✅ |
| Drag-**reparent** a page/DB in the sidebar | ❌ | ✅ |
| Download a **file attachment** (xlsx/pdf/pptx bytes) | ❌ | ✅ |
| Buttons / DB automations | ❌ | ✅ |

Anything the official API *can* do (row PATCH, schema DDL, page bodies, archive,
create pages/DBs) stays on the API — do NOT use this skill for it.

## Two mechanisms — prefer the private API

1. **Private Notion API (preferred).** The endpoints the Notion web client itself
   calls (e.g. `POST /api/v3/saveTransactions`, `queryCollection`). Structured,
   no DOM fragility. Auth = the logged-in browser session's `token_v2` cookie +
   `x-notion-space-id`. This handles view CRUD, linked views, and reparent far more
   reliably than clicking. **Unofficial** — can change without notice; treat as
   best-effort and always verify the result via the official API or a screenshot.
2. **Browser DOM (fallback + verification).** Use when the private API path is
   unknown/blocked, or to *see* a result:
   - **`browse`** (headless, ~100 ms/cmd) for scripted, repeatable click-paths.
   - **`connect-chrome`** (visible) for **every irreversible step** — Aaron watches
     it happen. Mandatory for: teamspace rename, page/DB delete, reparent.

Decision rule per op: *private API if a known endpoint exists → else `browse` →
escalate to visible `connect-chrome` for anything irreversible.*

## Step 0: Preflight + mode

```bash
eval "$(scripts/preflight.sh --require notion)"
[ "$MODE" = "locked" ]  && { echo "🛑 Locked"; exit 0; }
[ "$MODE" = "observe" ] && echo "👁 observe — will navigate + screenshot only, NO mutations"
RUN_ID="nuiops-$(date +%Y%m%d-%H%M%S)"
RUN_START_MS=$(date +%s%3N)
```

`locked` → refuse. `observe` → navigate + screenshot to report current UI state, but
refuse all mutations. `draft` → trust gate on every mutating op. `approved`/`auto` →
NOT honored here: UI ops are structural and hard to undo, so this skill prompts on
**every** mutating action regardless of mode (like `/vault-health`).

## Step 1: Establish + verify the browser session

1. Confirm a logged-in Notion session. Preferred: `connect-chrome` (uses Aaron's real
   Chrome profile, already authed). Headless `browse` path: run `setup-browser-cookies`
   first to import the Notion cookie domains.
2. Navigate to a known page (Command Center `335a3158-59b4-815b-863d-c585bf957dc8`).
   **Screenshot.** If it shows a login wall, STOP — ask Aaron to log in (`! ` command)
   and retry. Never attempt to type credentials.
3. If using the private API: extract `token_v2` + space id from the session, do ONE
   read-only probe (e.g. `getSpaces`) and confirm a 200 before any write.

## Step 2: Per-operation loop (the discipline)

For each requested operation:

1. **Resolve target** — page/DB/view ID from `config/sources.yaml` (single source of
   truth) or the content-export index. Never guess IDs from page titles.
2. **Pre-state snapshot** — screenshot (DOM path) AND/OR fetch current state via the
   official API (e.g. list the DB's views via `notion-fetch`). Save under
   `.context/applied/notion-ui-ops/<RUN_ID>/<op>-pre.{png,json}`.
3. **Idempotency check** — is the change already in place? (view already gone, linked
   view already exists). If yes → skip, log `noop`.
4. **TRUST GATE** — show Aaron: the op, the target (id + human name), the mechanism
   (private-API vs browse vs visible-chrome), and the pre-state screenshot. Wait for
   explicit plain-text approval. (AskUserQuestion answers are NOT sufficient for
   external writes — see memory `feedback_automode_trust_gate`.)
5. **Execute** — private API call OR scripted clicks. Irreversible ops run in visible
   `connect-chrome`.
6. **Post-state verify** — screenshot AND re-read via official API. Save `-post.*`.
   Assert the change landed (view count dropped by 1, linked view present, etc.).
   On mismatch → STOP, report, do not proceed to the next op.
7. **Stamp** — `scripts/action_id.sh` stamp (`notion-ui-ops:<target>:<date>:<hash>`).

## Step 3: Telemetry

Append one row per run to `logs/_telemetry.jsonl` via `scripts/telemetry.sh`:
`skill=notion-ui-ops`, `run_id`, `duration_ms`, `status`, plus `ops_attempted`,
`ops_done`, `ops_noop`, `ops_failed`, `mechanism` per op, `mode`.

## Operation catalog

Each op documents: mechanism, target-resolution, pre/post assertion. Selectors and
private-API request shapes are **discovered on first run with screenshots, then
recorded back into this file** (don't hard-code unverified DOM paths).

- **delete_view(db, view_id)** — remove a redundant/broken view. Assert: view absent
  from `notion-fetch` `<views>` after.
- **rename_view(db, view_id, new_name)**.
- **create_linked_view(parent_page, source_db, filter, groupBy)** — the Company OS
  Home / hub-page building block.
- **rename_teamspace(team_id, new_name)** — visible chrome only.
- **reparent(page_or_db_id, new_parent_id)** — visible chrome only.
- **download_attachments(page_id, dest_dir)** — pull xlsx/pdf/pptx bytes the export
  could only link.

## Current backlog (clean-up-first scope — Aaron 2026-05-29)

Do the low-risk wins now; defer hub-page / Company OS Home structure until the cleaned
baseline settles.

1. **Fix or delete the broken Master Tasks "Lincoln Lab" view** (`view://335a3158-59b4-8116-af5a-000cc458de8c`)
   — its filter still references the deleted `Link & Reference Laboratory` option, so
   it returns nothing. Either repoint the filter to `Lincoln Reference Laboratory` or
   delete it (redundant with Workspace-grouped Morning Report).
2. **Delete redundant Master Tasks views**: `United IPA`, `Nestmate`, `Dock Pro`,
   `Top-level tasks` — replaced by the Workspace-grouped Morning Report + per-hub
   linked views.
3. **Delete `IPA Providers` view** (Provider CRM) and **`My Notes` view** (Meeting Notes).

Deferred (design-after): rename `Docpro` → `Dock Pro`, reparent the 4 DBs under HQ,
build per-business hub pages with linked views, Company OS Home. See
`state/notion-reorg-plan.md` §3 (target structure), §5 (Phase 5), §8 (observability).

## Field-tested findings (2026-05-29 — hybrid MCP+Playwright run)

**MCP-first capability map (verified live):**
- ✅ MCP `notion-create-view` (linked views via `parent_page_id`+`data_source_id`),
  `notion-create-pages`, `notion-update-view` (rename/filter/sort), `notion-update-data-source`
  (`in_trash` archive), `notion-move-pages`. Build the whole Company OS additively via MCP.
- ❌ MCP **cannot delete a view** (no delete in update-view; no delete-view tool) → Playwright.
- ❌ MCP **cannot filter status-type properties** — `FILTER "Status" = "Waiting"` (and `IN`)
  silently produce an EMPTY filter. Select-type (`Workspace`, `Type`) filters work fine.
  Workaround: set the status filter in the UI (2 clicks) or via Playwright; or use a board GROUP BY Status.
- ❌ MCP `move-pages` **cannot target a teamspace root** (only page/database/data_source/workspace).
  So "DBs at HQ teamspace top level" isn't MCP-doable; nesting under an HQ page or UI drag only.
  Linked-view hubs make DB physical location irrelevant anyway — usually skip reparenting.

**Playwright backup (what reliably works):**
- Auth: persistent profile + **real Chrome** (`channel: 'chrome'`) + strip automation flags
  (`ignoreDefaultArgs: ['--enable-automation']`, `--disable-blink-features=AutomationControlled`)
  — otherwise Google SSO blocks with "browser may not be secure". gstack's throwaway profile loses
  login on restart; Playwright persistent profile holds it. Kill stray chrome on the profile before relaunch.
- **Delete a view:** open the `N more…` overflow → type the name in the "Search for a view" box →
  click the `•••` at `(searchBox.right − 14, searchBox.bottom + 21)` (the first filtered row,
  targeted GEOMETRICALLY — `getByText(name)` matches background table cells and misclicks) →
  click "Delete view" menu item → click the confirm dialog's "Delete view" button.
- **One view per browser session.** Batching multiple deletes in one session bleeds popover state
  and flakes; single-view runs are reliable. Verify each via `notion-fetch` DB `<views>`.
- Multi-step UI (setting a filter, scrolling to a linked view, sidebar drag) is flaky — prefer MCP
  or hand a 2-click to the user.

## Safety invariants

- Production workspace. The 273-page export is the rollback net, not a license to move fast.
- Screenshot before AND after every mutating step — the evidence trail.
- Never type credentials; if logged out, hand back to Aaron.
- Private API is unofficial — verify every result via the official API or a screenshot.
- One op at a time through the trust gate; a failed/mismatched op halts the run.
- HIPAA-adjacent: never screenshot or download pages containing patient identifiers
  without flagging; route any free-text capture through `scripts/phi_scan.sh` first.
