#!/usr/bin/env python3
"""
scripts/vault_health.py — Read-only audit of vault/ for orphan notes,
broken wikilinks, and untagged notes. Companion to /vault-health skill.

What it scans:
  - vault/notes/         — primary scope (evergreen notes)
  - vault/meetings/      — meeting notes
  - vault/daily/         — daily notes (audited differently: never "orphan",
                           but check for broken outgoing wikilinks)
  - vault/inbox/         — fleeting notes; warn if any are >30 days old

What it reports:
  - orphan: file has no incoming [[wikilinks]] from anywhere in the vault.
    Daily notes are excluded from orphan check (they're index entry points).
  - broken_link: a [[Target]] in some file points to no existing note.
  - untagged: a note in vault/notes/ has no #tag in frontmatter or body.
  - stale_inbox: a vault/inbox/ note older than 30 days.

Output: JSON to stdout (default) or human text (--text).
Exit codes: 0 (clean), 1 (issues found — useful for CI gate), 2 (scan error).
"""

from __future__ import annotations
import argparse
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
VAULT = REPO_DIR / "vault"

WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:\|[^\]]+)?(?:#[^\]]+)?\]\]")
TAG_RE = re.compile(r"(?:^|\s)#([a-zA-Z][a-zA-Z0-9_/-]*)")
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)


def list_md(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(p for p in root.rglob("*.md") if p.is_file())


def note_id(p: Path) -> str:
    """The wikilink target form: filename without .md, no path."""
    return p.stem


def extract_wikilinks(text: str) -> list[str]:
    """Return list of normalized target stems (case-preserved as written)."""
    return [m.strip() for m in WIKILINK_RE.findall(text)]


def has_tags(text: str) -> bool:
    """Check for #tags in body OR frontmatter `tags:` list."""
    if TAG_RE.search(text):
        return True
    m = FRONTMATTER_RE.match(text)
    if m and re.search(r"^\s*tags\s*:", m.group(1), re.MULTILINE):
        return True
    return False


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    ap = argparse.ArgumentParser(description="Vault health audit.")
    ap.add_argument("--text", action="store_true", help="Human text output (default JSON).")
    ap.add_argument("--inbox-stale-days", type=int, default=30)
    ap.add_argument("--quiet", action="store_true", help="JSON output only (no progress).")
    args = ap.parse_args(argv)

    if not VAULT.exists():
        print(json.dumps({"error": f"vault not found at {VAULT}"}), file=sys.stderr)
        return 2

    notes = list_md(VAULT / "notes")
    meetings = list_md(VAULT / "meetings")
    daily = list_md(VAULT / "daily")
    inbox = list_md(VAULT / "inbox")
    all_md = notes + meetings + daily + inbox

    # Index by stem (case-insensitive) for wikilink target resolution. Obsidian
    # is case-insensitive for [[Foo]] vs file `foo.md`.
    by_stem: dict[str, Path] = {}
    for p in all_md:
        by_stem.setdefault(p.stem.lower(), p)

    # Build the incoming-link graph: target stem → list of source paths.
    incoming: dict[str, list[Path]] = {}
    broken: list[tuple[Path, str]] = []  # (source, broken target)

    for src in all_md:
        try:
            text = src.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for target in extract_wikilinks(text):
            key = target.lower()
            incoming.setdefault(key, []).append(src)
            if key not in by_stem:
                broken.append((src, target))

    # Orphans: notes/ and meetings/ files with zero incoming links.
    # daily/ and inbox/ are excluded (entry points / fleeting).
    orphans: list[Path] = []
    for p in notes + meetings:
        if not incoming.get(p.stem.lower()):
            orphans.append(p)

    # Untagged: notes/ files with no #tag anywhere.
    untagged: list[Path] = []
    for p in notes:
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not has_tags(text):
            untagged.append(p)

    # Stale inbox: fleeting notes older than the threshold.
    stale_inbox: list[tuple[Path, int]] = []
    cutoff = datetime.now() - timedelta(days=args.inbox_stale_days)
    for p in inbox:
        try:
            mtime = datetime.fromtimestamp(p.stat().st_mtime)
            if mtime < cutoff:
                stale_inbox.append((p, (datetime.now() - mtime).days))
        except OSError:
            continue

    report = {
        "scanned": {
            "notes": len(notes),
            "meetings": len(meetings),
            "daily": len(daily),
            "inbox": len(inbox),
            "total": len(all_md),
        },
        "orphans": [str(p.relative_to(REPO_DIR).as_posix()) for p in orphans],
        "broken_links": [
            {"source": str(s.relative_to(REPO_DIR).as_posix()), "target": t}
            for s, t in broken
        ],
        "untagged_notes": [str(p.relative_to(REPO_DIR).as_posix()) for p in untagged],
        "stale_inbox": [
            {"path": str(p.relative_to(REPO_DIR).as_posix()), "days_old": d}
            for p, d in stale_inbox
        ],
    }
    report["issue_count"] = (
        len(report["orphans"])
        + len(report["broken_links"])
        + len(report["untagged_notes"])
        + len(report["stale_inbox"])
    )

    if args.text:
        print(f"Vault Health — scanned {report['scanned']['total']} notes")
        print(f"  notes: {report['scanned']['notes']}  meetings: {report['scanned']['meetings']}  "
              f"daily: {report['scanned']['daily']}  inbox: {report['scanned']['inbox']}")
        print()
        if not report["issue_count"]:
            print("✓ No issues found.")
        else:
            if report["orphans"]:
                print(f"Orphan notes ({len(report['orphans'])}):")
                for o in report["orphans"][:20]:
                    print(f"  - {o}")
                if len(report["orphans"]) > 20:
                    print(f"  ... and {len(report['orphans']) - 20} more")
                print()
            if report["broken_links"]:
                print(f"Broken wikilinks ({len(report['broken_links'])}):")
                for b in report["broken_links"][:20]:
                    print(f"  - {b['source']} → [[{b['target']}]]")
                if len(report["broken_links"]) > 20:
                    print(f"  ... and {len(report['broken_links']) - 20} more")
                print()
            if report["untagged_notes"]:
                print(f"Untagged notes in notes/ ({len(report['untagged_notes'])}):")
                for u in report["untagged_notes"][:10]:
                    print(f"  - {u}")
                if len(report["untagged_notes"]) > 10:
                    print(f"  ... and {len(report['untagged_notes']) - 10} more")
                print()
            if report["stale_inbox"]:
                print(f"Stale inbox notes (>{args.inbox_stale_days}d):")
                for s in report["stale_inbox"]:
                    print(f"  - {s['path']} ({s['days_old']}d old)")
                print()
    else:
        print(json.dumps(report, indent=2))

    return 1 if report["issue_count"] else 0


if __name__ == "__main__":
    sys.exit(main())
