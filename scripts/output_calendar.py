#!/usr/bin/env python3
"""Gated Google Calendar write adapter for refine-calendar.

This is intentionally small and boring: it consumes a staged preview JSON from
`.context/preview/`, inserts only COO-managed execution blocks through the
canonical `scripts/google_api.py calendar insert` wrapper, and stamps each
`action_id` only after a confirmed successful insert.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
from typing import Any, Callable, Dict, List

REPO_DIR = pathlib.Path(__file__).resolve().parents[1]
APPLIED_DIR = REPO_DIR / ".context" / "applied"


class CalendarApplyError(RuntimeError):
    pass


def load_preview_blocks(path: pathlib.Path) -> List[dict]:
    data = json.loads(path.read_text())
    if isinstance(data, dict) and isinstance(data.get("blocks"), list):
        return data["blocks"]
    if isinstance(data, dict) and isinstance(data.get("plan"), dict):
        blocks = data["plan"].get("blocks", [])
        if isinstance(blocks, list):
            return blocks
    raise CalendarApplyError(f"No blocks found in preview: {path}")


def build_calendar_insert_command(block: dict) -> List[str]:
    action_id = block["action_id"]
    markers = " ".join(block.get("source_markers") or [])
    description = "\n".join([
        "COO Twin refine-calendar execution block",
        f"action_id: {action_id}",
        f"dedupe_key: {block.get('dedupe_key', '')}",
        f"block_type: {block.get('block_type', '')}",
        f"source_markers: {markers}",
        "Managed by /refine-calendar. Do not hand-edit the coo-block marker.",
    ])
    cmd = [
        "python3", "scripts/google_api.py", "calendar", "insert",
        "--summary", block["summary"],
        "--start", block["start"],
        "--end", block["end"],
        "--description", description,
    ]
    if block.get("location"):
        cmd.extend(["--location", block["location"]])
    return cmd


def default_already_applied(action_id: str) -> bool:
    return (APPLIED_DIR / f"{action_id.replace(':', '_')}.json").exists()


def default_stamp(action_id: str, meta: dict) -> None:
    payload = json.dumps(meta, separators=(",", ":"))
    subprocess.run(["scripts/action_id.sh", "stamp", action_id, payload], cwd=REPO_DIR, check=True)


def default_runner(cmd: List[str]) -> dict:
    proc = subprocess.run(cmd, cwd=REPO_DIR, check=False, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        raise CalendarApplyError(proc.stderr.strip() or proc.stdout.strip() or f"command failed: {cmd}")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise CalendarApplyError(f"Could not parse google_api.py response: {proc.stdout[:500]}") from exc


def apply_blocks(blocks: List[dict], *, apply: bool, mode: str,
                 already_applied: Callable[[str], bool] = default_already_applied,
                 stamp: Callable[[str, dict], None] = default_stamp,
                 runner: Callable[[List[str]], dict] = default_runner) -> Dict[str, Any]:
    if not apply:
        return {"status": "preview", "created": [], "skipped": [], "blocks": blocks}
    if mode not in ("approved", "auto"):
        raise CalendarApplyError("Calendar apply requires mode approved/auto and explicit --apply")

    created: List[dict] = []
    skipped: List[dict] = []
    for block in blocks:
        action_id = block["action_id"]
        if already_applied(action_id):
            skipped.append({"action_id": action_id, "reason": "already_applied"})
            continue
        result = runner(build_calendar_insert_command(block))
        if result.get("status") != "ok" or not result.get("id"):
            raise CalendarApplyError(f"Calendar insert did not confirm success for {action_id}: {result}")
        meta = {
            "calendar_event_id": result["id"],
            "calendar_link": result.get("link", ""),
            "summary": block.get("summary", ""),
            "start": block.get("start", ""),
            "end": block.get("end", ""),
            "target": "google_calendar",
        }
        stamp(action_id, meta)
        created.append({"action_id": action_id, "event_id": result["id"], "link": result.get("link", "")})
    return {"status": "applied", "created": created, "skipped": skipped}


def main() -> int:
    p = argparse.ArgumentParser(description="Apply a refine-calendar preview to Google Calendar after approval.")
    p.add_argument("--preview", required=True, type=pathlib.Path)
    p.add_argument("--mode", default="draft", choices=["observe", "draft", "approved", "auto", "locked"])
    p.add_argument("--apply", action="store_true", help="Actually insert events. Omit for preview/no-write.")
    args = p.parse_args()

    if args.mode == "locked":
        raise CalendarApplyError("mode locked: refusing calendar writes")
    blocks = load_preview_blocks(args.preview)
    result = apply_blocks(blocks, apply=args.apply, mode=args.mode)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CalendarApplyError as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, indent=2), file=sys.stderr)
        raise SystemExit(1)
