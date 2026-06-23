#!/usr/bin/env python3
"""Morning /refine-calendar runner.

Reads today's daily note + current Google Calendar anchors, stages an Execution
Plan preview under `.context/preview/`, and optionally applies it through the
separately-gated `output_calendar.py` adapter.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re
import subprocess
import sys
from typing import Any, Dict, List, Optional

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None

import calendar_planning as cp
import output_calendar
import output_planning as op

REPO_DIR = pathlib.Path(__file__).resolve().parents[1]


def _parse_source_ref(line: str) -> op.SourceRef:
    m = re.search(r"<!--\s*(gtask|notion):([^\s>]+)\s*-->", line)
    if m:
        return op.SourceRef(m.group(1), m.group(2))
    if "Calendar" in line or "calendar" in line:
        return op.SourceRef("cal", "")
    return op.SourceRef("derived", "")


def extract_top_outputs(note_text: str) -> List[op.DailyOutput]:
    lines = note_text.splitlines()
    outputs: List[op.DailyOutput] = []
    in_top = False
    for i, line in enumerate(lines):
        if line.startswith("## Today — Ship These 3"):
            in_top = True
            continue
        if in_top and line.startswith("## ") and not line.startswith("## Today"):
            break
        if in_top and line.startswith("- [ ] "):
            title = re.sub(r"^- \[ \]\s*", "", line).split("<!--")[0].strip()
            detail = lines[i + 1].strip() if i + 1 < len(lines) else ""
            owner = detail.split("·")[0].strip() if "·" in detail else "Other"
            done_when = detail.split("done when:", 1)[1].strip() if "done when:" in detail else title
            outputs.append(op.DailyOutput(
                title=title,
                owner=owner,
                source_refs=[_parse_source_ref(line + " " + detail)],
                done_when=done_when,
            ))
    return outputs[:3]


def extract_day_type(note_text: str) -> str:
    patterns = [r"_Day type:\s*([a-zA-Z-]+)", r"Day type:\s*([a-zA-Z-]+)"]
    for pat in patterns:
        m = re.search(pat, note_text)
        if m:
            return m.group(1).strip().lower()
    return "deep-work"


def _source_refs_from_candidate(raw: dict) -> List[op.SourceRef]:
    refs: List[op.SourceRef] = []
    for r in raw.get("source_refs", []) or []:
        if isinstance(r, dict):
            refs.append(op.SourceRef(str(r.get("system") or "derived"), str(r.get("id") or "")))
    if refs:
        return refs
    if raw.get("notion_id"):
        return [op.SourceRef("notion", str(raw["notion_id"]))]
    if raw.get("gtask_id"):
        return [op.SourceRef("gtask", str(raw["gtask_id"]))]
    return [op.SourceRef("derived", "")]


def extract_attention_candidates(data: dict, *, limit: int = 12) -> List[op.DailyOutput]:
    """Turn scored task-candidate JSON into DailyOutput rows."""
    tasks = data.get("tasks", []) if isinstance(data, dict) else []
    usable = [t for t in tasks if isinstance(t, dict) and (t.get("title") or "").strip()]
    usable.sort(key=lambda t: (float(t.get("attention_pct") or 0), float(t.get("value_score") or 0)),
                reverse=True)
    outputs: List[op.DailyOutput] = []
    for t in usable[:limit]:
        title = str(t.get("title") or "").strip()
        workspace = str(t.get("workspace") or t.get("owner") or "Other")
        subset = str(t.get("subset") or "").strip()
        attention = t.get("attention_pct")
        done_when = str(t.get("done_when") or "next concrete action completed").strip()
        if attention is not None:
            done_when = f"{done_when} (attention {attention}%)"
        owner = f"{workspace} · {subset}" if subset else workspace
        outputs.append(op.DailyOutput(title=title, owner=owner,
                                      source_refs=_source_refs_from_candidate(t),
                                      done_when=done_when))
    return outputs


def merge_outputs_with_candidates(outputs: List[op.DailyOutput],
                                  candidates: List[op.DailyOutput],
                                  *, max_total: int = 12) -> List[op.DailyOutput]:
    """Keep Top-3 first, then add attention-ranked candidates without duplicates."""
    merged: List[op.DailyOutput] = []
    seen = set()
    for o in list(outputs) + list(candidates):
        key = re.sub(r"\s+", " ", o.title.lower()).strip()
        if not key or key in seen:
            continue
        seen.add(key)
        merged.append(o)
        if len(merged) >= max_total:
            break
    return merged


def load_config(root: pathlib.Path) -> dict:
    path = root / "config" / "calendar.yaml"
    if yaml is None:
        raise RuntimeError("PyYAML is required to read config/calendar.yaml")
    return yaml.safe_load(path.read_text())


def fetch_calendar(root: pathlib.Path, date: str) -> dict:
    proc = subprocess.run(["python3", "scripts/google_api.py", "calendar", date],
                          cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          check=False)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "calendar fetch failed")
    return json.loads(proc.stdout)


def _block_dict(block: cp.CalendarBlockProposal) -> dict:
    return {
        "output_id": block.output_id,
        "block_type": block.block_type,
        "summary": block.summary,
        "start": block.start,
        "end": block.end,
        "stream": block.stream,
        "source_markers": block.source_markers,
        "write_eligible": block.write_eligible,
        "dedupe_key": block.dedupe_key,
        "action_id": block.action_id,
        "flags": block.flags,
    }


def generate_preview(*, root: pathlib.Path, date: str, day_type: Optional[str],
                     calendar_data: Optional[dict] = None,
                     task_candidates: Optional[dict] = None) -> Dict[str, Any]:
    note_path = root / "vault" / "daily" / f"{date}.md"
    note_text = note_path.read_text()
    cfg = load_config(root)
    outputs = extract_top_outputs(note_text)
    if task_candidates:
        outputs = merge_outputs_with_candidates(outputs, extract_attention_candidates(task_candidates))
    resolved_day_type = day_type or extract_day_type(note_text)
    data = calendar_data if calendar_data is not None else fetch_calendar(root, date)
    anchors = data.get("events", []) if isinstance(data, dict) else []
    plan = cp.propose_calendar_blocks(outputs, anchors, config=cfg,
                                      day_type=resolved_day_type, date=date)
    markdown = cp.render_execution_plan_markdown(plan)

    preview_dir = root / ".context" / "preview"
    preview_dir.mkdir(parents=True, exist_ok=True)
    json_path = preview_dir / f"exec-plan-{date}.json"
    md_path = preview_dir / f"exec-plan-{date}.md"
    payload = {
        "intent": "refine-calendar",
        "status": "preview_only_no_external_writes",
        "date": date,
        "day_type": resolved_day_type,
        "source_daily_note": str(note_path),
        "outputs": [
            {
                "title": o.title,
                "owner": o.owner,
                "done_when": o.done_when,
                "source_refs": [r.__dict__ for r in o.source_refs],
            }
            for o in outputs
        ],
        "plan": {
            "open_minutes": plan.open_minutes,
            "proposed_minutes": plan.proposed_minutes,
            "unplaced": plan.unplaced,
            "flags": plan.flags,
            "blocks": [_block_dict(b) for b in plan.blocks],
        },
        "markdown": markdown,
    }
    json_path.write_text(json.dumps(payload, indent=2))
    md_path.write_text("\n".join([
        f"# Execution Plan Preview — {date}",
        "",
        f"Source: `{note_path.relative_to(root)}`",
        "Mode: preview-first. Apply requires approved/auto mode + explicit --apply --yes.",
        "",
        markdown.rstrip(),
        "",
        f"JSON payload: `{json_path.relative_to(root)}`",
    ]) + "\n")
    return {"json_path": json_path, "markdown_path": md_path, "markdown": markdown, "payload": payload}


def main() -> int:
    today = dt.date.today().isoformat()
    p = argparse.ArgumentParser(description="Stage/apply today's refine-calendar execution plan.")
    p.add_argument("--date", default=today)
    p.add_argument("--day-type", default=None)
    p.add_argument("--mode", default="draft", choices=["observe", "draft", "approved", "auto", "locked"])
    p.add_argument("--apply", action="store_true", help="Insert staged blocks into Google Calendar")
    p.add_argument("--yes", action="store_true", help="Required with --apply after user approval")
    p.add_argument("--calendar-json", type=pathlib.Path, help="Test fixture for calendar data; skips Google API read")
    p.add_argument("--task-candidates-json", type=pathlib.Path,
                   help="Optional scored task candidate file for high-value gap filling")
    args = p.parse_args()

    if args.mode == "locked":
        print(json.dumps({"status": "refused", "reason": "mode_locked"}, indent=2))
        return 0
    calendar_data = json.loads(args.calendar_json.read_text()) if args.calendar_json else None
    task_candidates = json.loads(args.task_candidates_json.read_text()) if args.task_candidates_json else None
    preview = generate_preview(root=REPO_DIR, date=args.date, day_type=args.day_type,
                               calendar_data=calendar_data, task_candidates=task_candidates)
    print(preview["markdown"].rstrip())
    print(f"\nPreview staged: {preview['json_path']}")
    if args.apply:
        if not args.yes:
            raise output_calendar.CalendarApplyError("--apply requires --yes after approval")
        result = output_calendar.apply_blocks(preview["payload"]["plan"]["blocks"],
                                              apply=True, mode=args.mode)
        print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, indent=2), file=sys.stderr)
        raise SystemExit(1)
