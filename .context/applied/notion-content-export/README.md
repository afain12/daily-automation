# Notion Content Export — full workspace backup

**Created:** 2026-05-29 · **Purpose:** zero-data-loss backup of the *page bodies* across all
live teamspaces, before any structural reorg (Phase 5) touches page locations.

This complements the row-level Phase 0 snapshots (`../notion-reorg-phase-0-*-pre.json`),
which captured DB rows + property values but **not** page bodies, topic pages, meeting-note
bodies, or the teamspace folder trees. This export fills that gap.

## What's here

- `pages/<pageid>.md` — one file per Notion page. Filename = page ID (dashes stripped).
  Each file = YAML frontmatter (`page_id`, `title`, `notion_url`, `ancestor_path`,
  `exported_at`) followed by the **full verbatim page body** in Notion-flavored markdown.
  No truncation. Folder hierarchy is reconstructable from each file's `ancestor_path`.
- `_manifests/index.tsv` — catalog: `page_id  <tab>  title  <tab>  bytes`. 273 pages.

## Coverage (273 unique pages, 1.1 MB)

Captured by 5 parallel export workers, deduped globally by page ID:

| Source | Captured |
|---|---|
| Meeting Notes DB (6 rows) + meeting/topic pages | ✅ |
| Provider CRM DB (9 rows) + loose provider pages | ✅ |
| SAIPA Providers DB | ✅ 102 rows |
| Master Tasks DB (42 rows) + Activity Log DB (28 rows) | ✅ |
| Teamspace hub pages (Lincoln / United IPA / Nestmate / CardioPro / Docpro) | ✅ |
| HQ structural pages (Command Center, Daily Briefing Mobile, Notion↔Obsidian Bridge) | ✅ |
| Specialty Pharmacy Account Tracking DB (14 rows) | ✅ |
| "Documentation for Specialty Pharmacy" folder + 10 referral-flyer child pages | ✅ |
| Recursed child pages (depth ≤ 4) | ✅ |

## Known limits (NOT in this backup)

- **File attachments** (xlsx / pdf / pptx) embedded in pages are referenced but not
  downloaded — the API returns links, not file bytes.
- **Granola/meeting transcripts** are not retrievable via the page-fetch API.
- **Trashed teamspaces** (`Reps`, `Dr Hussain's Clinical Research Trials`) are excluded
  per Aaron 2026-05-29 (lower priority; API returns 404 for trashed teamspace content anyway).
- **`Laboratory Accounts`** and **`SAIPA`** are databases — their schema/views are captured;
  Laboratory-Accounts individual rows were out of the row-export scope.

## Restore

Each file is plain markdown. To re-create a page, paste the body back into a new Notion page,
or re-import via `notion-create-pages`. `ancestor_path` in the frontmatter tells you where it
lived in the teamspace tree.
