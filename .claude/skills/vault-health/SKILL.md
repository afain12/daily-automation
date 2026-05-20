---
name: vault-health
description: >-
  Read-only audit of the Obsidian vault. Finds orphan notes (no incoming
  [[wikilinks]]), broken wikilinks (target missing), untagged notes in
  vault/notes/, and stale inbox notes (>30 days old). Reports a summary;
  offers trust-gated batch fixes for the easy wins (delete-or-link orphans,
  fix-or-remove broken wikilinks). Never auto-fixes — Aaron decides.
coo_twin:
  category: admin
  mode_required: any
  writes_external: false
  preflight: required
  experimental: false
---

# /vault-health — Obsidian Vault Audit

You are auditing the Obsidian vault for hygiene issues. **Read-only at the
scan layer.** Any fixes go through individual trust gates. The audit itself
never writes.

## Constants

```
REPO_DIR  = "C:/Users/aaron/daily-automation"
VAULT     = "${REPO_DIR}/vault"
TODAY     = <current date in YYYY-MM-DD format>
RUN_ID    = "vh-${TODAY//-/}-$(date +%H%M%S)"
```

## Step 0: Preflight

```bash
eval "$(scripts/preflight.sh --require vault)"
[ "$MODE" = "locked" ] && { echo "🛑 Locked"; exit 0; }
```

`locked` → refuse. `observe` → run scan + display; refuse all fix prompts.
`draft` → standard trust gates. `approved`/`auto` → not honored here (this
skill prompts on every fix because vault hygiene decisions are taste calls,
not rule-based — auto-approving them would mean deleting Aaron's notes).

Capture `RUN_START_MS`.

## Step 1: Run the Audit

```bash
REPORT=$(python scripts/vault_health.py)
N_ISSUES=$(echo "$REPORT" | python -c "import sys,json; print(json.load(sys.stdin)['issue_count'])")
```

If `N_ISSUES == 0`:
- Print: `✓ Vault clean. {N} notes scanned. No issues.`
- Emit telemetry, exit.

## Step 2: Display Report

Format the JSON report as a structured summary:

```
# Vault Health — {TODAY}

Scanned: {total} notes ({notes}/{meetings}/{daily}/{inbox})

## Orphan Notes ({count})
Notes in vault/notes/ and vault/meetings/ with zero incoming [[wikilinks]].
Top 10 by oldest mtime:
1. {path} — last modified {N}d ago
2. ...

## Broken Wikilinks ({count})
[[Target]] references whose target file doesn't exist.
1. {source} → [[{missing target}]]
2. ...

## Untagged Notes in notes/ ({count})
Permanent notes lacking any #tag in body or frontmatter.
1. {path}
2. ...

## Stale Inbox (>30d, {count})
Fleeting notes that have aged out of "inbox" status.
1. {path} — {N}d old
2. ...
```

Cap lists at 20 visible entries with an "... and N more" line. Aaron triages
the visible ones; the rest accumulate in JSON for follow-up.

## Step 3: Triage Trust Gate

For each category with issues, use `AskUserQuestion` to ask Aaron how to
proceed. Don't ask per-item — that's hundreds of questions. Ask per-category:

### Orphans
> "Orphan notes ({N}). Many are intentional (one-off thoughts that never got
> linked). Action?"
> - **Skip** — leave them. (default)
> - **Tag for review** — append `#review` tag to all orphans so they surface
>   in future briefings.
> - **List the first 10 verbosely** — show fuller previews so Aaron can pick
>   per-item.

### Broken wikilinks
> "Broken wikilinks ({N}). Each is a `[[Target]]` whose target file doesn't
> exist. Action?"
> - **Show each + propose** — for each broken link, run `scripts/vault_search.py`
>   against the missing target name; if there's a high-confidence match (score
>   >2.0), propose renaming the wikilink to the real file. Aaron approves
>   per-link.
> - **List only** — print the full table, no fixes.
> - **Skip** — defer.

### Untagged
> "Untagged notes in notes/ ({N}). Action?"
> - **Skip** — many evergreen notes don't need tags.
> - **Suggest tags** — for each untagged note, propose tag(s) based on
>   filename + body keywords; Aaron approves per-note.

### Stale inbox
> "Inbox notes older than 30 days ({N}). Action?"
> - **Move to notes/** — escalate them to permanent status (still untagged
>   unless tagged manually).
> - **Move to archive/** — create vault/archive/ if missing and move them out
>   of inbox.
> - **Skip** — leave them.

## Step 4: Apply Approved Fixes

For each approved action, execute the file ops. **All fixes are local file
moves/edits — no external system writes.** Track per-fix outcome:

```bash
FIXES_APPLIED=()
FIXES_FAILED=()
# Example: append #review tag to orphans
for f in $ORPHAN_PATHS; do
  if grep -q "^#review" "$f" 2>/dev/null; then
    FIXES_APPLIED+=("$f (already tagged)")
    continue
  fi
  echo "" >> "$f"
  echo "#review" >> "$f"
  FIXES_APPLIED+=("$f")
done
```

Print a per-fix line as you apply it: `✓ {path}` or `✗ {path} — {reason}`.

## Step 5: Telemetry

```bash
DURATION_MS=$(( $(date +%s%3N 2>/dev/null || python -c "import time; print(int(time.time()*1000))") - RUN_START_MS ))
EXTRA=$(python -c "import json; print(json.dumps({
  'mode': '$MODE',
  'orphans': $N_ORPHANS,
  'broken_links': $N_BROKEN,
  'untagged': $N_UNTAGGED,
  'stale_inbox': $N_STALE,
  'fixes_applied': $N_FIXES_APPLIED,
  'fixes_failed': $N_FIXES_FAILED
}))")
scripts/telemetry.sh vault-health "$RUN_ID" "$DURATION_MS" ok "$EXTRA"
```

## Notes

- This skill pairs with the `vault-orphan-scan` automation in
  `state/automations.yaml`. Weekly cadence: the automation prints the audit
  summary; `/vault-health` is the interactive triage on top of it.
- Daily notes (`vault/daily/*.md`) are NEVER classified as orphans — they're
  intentional entry points for date-based recall. They CAN have broken
  outgoing wikilinks though, and those are reported.
- Untagged-note detection looks at both `#inline-tags` and frontmatter
  `tags: [...]`. Notes with either pass.
- This is the only `/admin` skill that has `mode_required: any` AND
  `writes_external: false`. The "writes" it does are vault file edits, which
  are inside the repo — they don't count as external for AAC purposes, but
  they do still require trust gate approval per the per-category prompts.
