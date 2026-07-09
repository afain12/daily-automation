#!/usr/bin/env python3
"""
scripts/automation_due.py — Companion to /automation skill.

Reads state/automations.yaml, computes which automations are due to run RIGHT
NOW, prints them as JSON. Also handles last_run stamping after a successful
execution and history-append bookkeeping.

Why a helper script: YAML parsing + cadence math + atomic writes are awkward
in bash. The skill body stays focused on trust gate + prompt execution; this
script handles the mechanical bookkeeping.

Subcommands:
  due                 List automations due to run now (JSON).
  due --include-all   Also include enabled-but-not-due automations.
  list                List ALL automations (enabled + disabled), with status.
  stamp <id>          Update last_run to NOW for the given automation id.
                      Also appends an entry to the history section.
  reset <id>          Set last_run to null (forces next run to fire).

Usage from the skill:
  python scripts/automation_due.py due
  python scripts/automation_due.py stamp weekly-review
"""

from __future__ import annotations
import argparse
import json
import re
import sys
from datetime import datetime, timedelta, time as dtime
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
AUTOMATIONS_FILE = REPO_DIR / "state" / "automations.yaml"

DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


# We avoid PyYAML to keep zero external deps (check_mode.sh's regex pattern).
# automations.yaml has a stable simple shape: a top-level `automations:` list
# of mappings with scalar values, plus a `history:` list. Parser is intentionally
# minimal — if the file shape drifts, add PyYAML rather than growing this regex.

def parse_yaml(text: str) -> dict:
    """Minimal YAML parser for the automations.yaml shape. Handles:
    - top-level keys with list values
    - list items as `- ` followed by indented key/value pairs
    - scalar values (string, int, bool, null)
    - multiline string blocks `|` at end of key
    Anything else: bail and tell the caller to install PyYAML.
    """
    try:
        import yaml  # type: ignore
        return yaml.safe_load(text) or {}
    except ImportError:
        pass

    # Fallback: hand-rolled. Good enough for this file's shape.
    lines = text.splitlines()
    i = 0
    result: dict = {}

    def parse_scalar(s: str):
        s = s.strip()
        if s == "null" or s == "":
            return None
        if s in ("true", "True"):
            return True
        if s in ("false", "False"):
            return False
        if s.startswith('"') and s.endswith('"'):
            return s[1:-1]
        if s.startswith("'") and s.endswith("'"):
            return s[1:-1]
        try:
            return int(s)
        except ValueError:
            pass
        return s

    while i < len(lines):
        line = lines[i]
        stripped = line.rstrip()
        if not stripped or stripped.lstrip().startswith("#"):
            i += 1
            continue
        # top-level key
        m = re.match(r"^([a-z_][a-z0-9_]*):\s*(.*)$", stripped)
        if not m:
            i += 1
            continue
        key, rest = m.group(1), m.group(2).strip()

        if rest == "" or rest == "[]":
            # Look ahead to see whether the next non-blank line starts with "- "
            # (list) or "  key:" (mapping). Empty list if `[]` or nothing follows.
            if rest == "[]":
                result[key] = []
                i += 1
                continue
            j = i + 1
            while j < len(lines) and (not lines[j].strip() or lines[j].lstrip().startswith("#")):
                j += 1
            if j < len(lines) and lines[j].lstrip().startswith("- "):
                items, i_next = parse_list(lines, j)
                result[key] = items
                i = i_next
                continue
            else:
                result[key] = None
                i += 1
                continue
        else:
            result[key] = parse_scalar(rest)
            i += 1
    return result


def parse_list(lines: list[str], i: int) -> tuple[list[dict], int]:
    """Parse a YAML list starting at line i (which begins with `- `).
    Returns (items, next_line_index)."""
    items = []
    while i < len(lines):
        line = lines[i]
        stripped_left = line.lstrip()
        # End of list: blank or comment we accept, but a top-level key ends the list.
        if not stripped_left:
            i += 1
            continue
        if stripped_left.startswith("#"):
            i += 1
            continue
        # A top-level non-indented `key:` ends the list.
        if re.match(r"^[a-z_]", line) and not line.startswith(" "):
            break
        if not stripped_left.startswith("- "):
            # Next line must be either a continuation of the current item (indented)
            # or end of list. The `- ` prefix is mandatory for new items.
            i += 1
            continue

        # New item.
        item: dict = {}
        # First key of the item is on the same line as `- ` (or it's `-` alone — then
        # the first key is on the next line).
        first = line.lstrip()[2:]  # strip "- "
        m = re.match(r"^([a-z_][a-z0-9_]*):\s*(.*)$", first.strip())
        if m:
            k, v = m.group(1), m.group(2)
            if v.strip() in ("|", "|+", "|-"):
                # multiline block scalar
                block_indent = None
                block_lines = []
                j = i + 1
                while j < len(lines):
                    ln = lines[j]
                    if ln.strip() == "":
                        block_lines.append("")
                        j += 1
                        continue
                    spaces = len(ln) - len(ln.lstrip())
                    if block_indent is None:
                        block_indent = spaces
                    if spaces < block_indent:
                        break
                    block_lines.append(ln[block_indent:])
                    j += 1
                item[k] = "\n".join(block_lines).rstrip("\n")
                i = j
            else:
                item[k] = _scalar(v)
                i += 1
        else:
            i += 1

        # Subsequent keys of this item are indented more than the `- `.
        while i < len(lines):
            ln = lines[i]
            stripped = ln.lstrip()
            if not stripped or stripped.startswith("#"):
                i += 1
                continue
            if stripped.startswith("- "):
                break  # next item
            if re.match(r"^[a-z_]", ln):
                break  # top-level key
            m = re.match(r"^([a-z_][a-z0-9_]*):\s*(.*)$", stripped)
            if not m:
                i += 1
                continue
            k, v = m.group(1), m.group(2)
            if v.strip() in ("|", "|+", "|-"):
                block_indent = None
                block_lines = []
                j = i + 1
                while j < len(lines):
                    bln = lines[j]
                    if bln.strip() == "":
                        block_lines.append("")
                        j += 1
                        continue
                    spaces = len(bln) - len(bln.lstrip())
                    if block_indent is None:
                        block_indent = spaces
                    if spaces < block_indent:
                        break
                    block_lines.append(bln[block_indent:])
                    j += 1
                item[k] = "\n".join(block_lines).rstrip("\n")
                i = j
            else:
                item[k] = _scalar(v)
                i += 1

        items.append(item)
    return items, i


def _scalar(s: str):
    s = s.strip()
    if s == "" or s == "null":
        return None
    if s in ("true", "True"):
        return True
    if s in ("false", "False"):
        return False
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        return s[1:-1]
    try:
        return int(s)
    except ValueError:
        pass
    return s


def load_automations() -> dict:
    if not AUTOMATIONS_FILE.exists():
        return {"automations": [], "history": []}
    return parse_yaml(AUTOMATIONS_FILE.read_text(encoding="utf-8"))


def parse_ts(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def is_due(a: dict, now: datetime) -> bool:
    """Compute due-ness for one automation given current datetime."""
    if not a.get("enabled"):
        return False
    cadence = (a.get("cadence") or "").lower()
    last = parse_ts(a.get("last_run"))

    if cadence == "manual":
        return False  # only fires via --force-run
    if cadence == "daily":
        # Due if never run, OR run was on a prior calendar day.
        return last is None or last.date() < now.date()
    if cadence == "weekdays":
        if now.weekday() >= 5:  # sat/sun
            return False
        return last is None or last.date() < now.date()
    if cadence == "weekly":
        anchor = (a.get("cadence_anchor") or "").lower()
        target_dow = DAYS.index(anchor) if anchor in DAYS else 0  # default monday
        # Due on the anchor day if not already run this week.
        if now.weekday() != target_dow:
            return False
        if last is None:
            return True
        # Same calendar week (Mon-anchored): due if last run was more than 6 days ago.
        return (now.date() - last.date()) >= timedelta(days=6)
    if cadence == "monthly":
        anchor = a.get("cadence_anchor") or "1"
        try:
            target_dom = int(anchor)
        except (TypeError, ValueError):
            target_dom = 1
        if now.day != target_dom:
            return False
        if last is None:
            return True
        # Different (year, month) → due.
        return (last.year, last.month) != (now.year, now.month)
    return False


def cmd_due(args):
    doc = load_automations()
    now = datetime.now()
    items = []
    for a in doc.get("automations") or []:
        due = is_due(a, now)
        if not (due or (args.include_all and a.get("enabled"))):
            continue
        items.append({
            "id": a.get("id"),
            "description": a.get("description"),
            "cadence": a.get("cadence"),
            "delivery": a.get("delivery"),
            "delivery_target": a.get("delivery_target"),
            "prompt": a.get("prompt"),
            "last_run": a.get("last_run"),
            "due_now": due,
        })
    print(json.dumps({"now": now.isoformat(timespec="seconds"), "due": items}, indent=2))


def cmd_list(args):
    doc = load_automations()
    now = datetime.now()
    items = []
    for a in doc.get("automations") or []:
        items.append({
            "id": a.get("id"),
            "description": a.get("description"),
            "cadence": a.get("cadence"),
            "enabled": bool(a.get("enabled")),
            "last_run": a.get("last_run"),
            "due_now": is_due(a, now),
        })
    print(json.dumps({"now": now.isoformat(timespec="seconds"), "automations": items}, indent=2))


def cmd_stamp(args):
    doc = load_automations()
    now_iso = datetime.now().isoformat(timespec="seconds")
    found = False
    text = AUTOMATIONS_FILE.read_text(encoding="utf-8")
    # Surgical edit: find the automation block for this id and replace last_run line.
    # Pattern: an entry starting with `  - id: <name>` runs until the next `  - id:`
    # or end-of-list (next top-level key).
    pattern = re.compile(
        r"(  - id:\s*" + re.escape(args.id) + r"\b[\s\S]*?)\n(    last_run:.*?)(\n)",
        re.MULTILINE,
    )
    def repl(m):
        nonlocal found
        found = True
        head = m.group(1)
        return f"{head}\n    last_run: {now_iso}{m.group(3)}"
    new_text, n = pattern.subn(repl, text, count=1)
    if n == 0:
        print(json.dumps({"ok": False, "error": f"no automation with id={args.id}"}))
        sys.exit(2)
    AUTOMATIONS_FILE.write_text(new_text, encoding="utf-8")

    # Append history entry — non-critical, best-effort.
    hist_line = f"\n  - {{ ts: {now_iso}, id: {args.id}, status: {args.status} }}"
    # If "history: []" exists, replace with list. Otherwise append.
    if re.search(r"^history:\s*\[\]\s*$", new_text, re.MULTILINE):
        new_text2 = re.sub(r"^history:\s*\[\]\s*$",
                           f"history:{hist_line}", new_text, count=1, flags=re.MULTILINE)
        AUTOMATIONS_FILE.write_text(new_text2, encoding="utf-8")
    elif re.search(r"^history:\s*$", new_text, re.MULTILINE):
        new_text2 = re.sub(r"^history:\s*$",
                           f"history:{hist_line}", new_text, count=1, flags=re.MULTILINE)
        AUTOMATIONS_FILE.write_text(new_text2, encoding="utf-8")

    print(json.dumps({"ok": True, "id": args.id, "last_run": now_iso}))


def cmd_reset(args):
    text = AUTOMATIONS_FILE.read_text(encoding="utf-8")
    pattern = re.compile(
        r"(  - id:\s*" + re.escape(args.id) + r"\b[\s\S]*?)\n(    last_run:.*?)(\n)",
        re.MULTILINE,
    )
    found = [False]
    def repl(m):
        found[0] = True
        return f"{m.group(1)}\n    last_run: null{m.group(3)}"
    new_text, n = pattern.subn(repl, text, count=1)
    if n == 0:
        print(json.dumps({"ok": False, "error": f"no automation with id={args.id}"}))
        sys.exit(2)
    AUTOMATIONS_FILE.write_text(new_text, encoding="utf-8")
    print(json.dumps({"ok": True, "id": args.id, "last_run": None}))


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    ap = argparse.ArgumentParser(description="automations.yaml due-check + bookkeeping")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_due = sub.add_parser("due", help="List automations due to run now")
    p_due.add_argument("--include-all", action="store_true",
                       help="Also include enabled-but-not-due automations")
    p_due.set_defaults(func=cmd_due)

    p_list = sub.add_parser("list", help="List all automations with status")
    p_list.set_defaults(func=cmd_list)

    p_stamp = sub.add_parser("stamp", help="Mark an automation as run NOW")
    p_stamp.add_argument("id")
    p_stamp.add_argument("--status", default="ok",
                         choices=["ok", "partial", "failed"],
                         help="Status to record in history")
    p_stamp.set_defaults(func=cmd_stamp)

    p_reset = sub.add_parser("reset", help="Clear last_run to force next run")
    p_reset.add_argument("id")
    p_reset.set_defaults(func=cmd_reset)

    args = ap.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
