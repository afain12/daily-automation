#!/usr/bin/env python3
"""Unified /end-day orchestrator.

Preview mode runs end-day core, note-harvest preview, and sync-sweep preview as
read-only workers, merges them into one run plan, and stages that plan in
.context/end-day-{run_id}.json. Execution is intentionally conservative in this
first integration: it renders the unified gate and records safe/local facts; the
legacy skills remain the executors for external writes until the write adapters
are hardened.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import dataclasses
import datetime as dt
import json
import os
import pathlib
import re
import subprocess
import sys
import time
from typing import Any

# Derive the repo root from this file's location (scripts/<this>.py) so a run from
# a worktree or any clone operates on ITS OWN checkout — not a hard-coded production
# path. Env override stays available for unusual layouts (e.g. Hermes deploy).
REPO_DIR = pathlib.Path(
    os.environ.get("COO_REPO_DIR") or pathlib.Path(__file__).resolve().parent.parent
)
CONTEXT = REPO_DIR / ".context"
LOGS = REPO_DIR / "logs"


@dataclasses.dataclass
class RunContext:
    date: str
    mode: str = "draft"
    run_id: str = ""
    repo_dir: pathlib.Path = REPO_DIR
    trigger: str = "standalone"

    @property
    def daily_note_path(self) -> pathlib.Path:
        return self.repo_dir / "vault" / "daily" / f"{self.date}.md"

    @property
    def log_path(self) -> pathlib.Path:
        return self.repo_dir / "logs" / f"{self.date}.md"


@dataclasses.dataclass
class WriteAction:
    owner: str
    type: str
    title: str
    source_line: int | None = None
    source_text: str = ""
    source_id: str | None = None
    confidence: float = 1.0
    payload: dict[str, Any] = dataclasses.field(default_factory=dict)
    risk: str = "safe"
    selected_by_default: bool = True

    def action_key(self) -> str:
        normalized = re.sub(r"\s+", " ", (self.source_text or self.title).strip().lower())
        return f"{self.type}:{self.source_id or ''}:{self.source_line or ''}:{normalized[:120]}"

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclasses.dataclass
class SkillPreview:
    skill: str
    summary: str = ""
    actions: list[WriteAction] = dataclasses.field(default_factory=list)
    noops: list[str] = dataclasses.field(default_factory=list)
    warnings: list[str] = dataclasses.field(default_factory=list)
    raw: dict[str, Any] = dataclasses.field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = dataclasses.asdict(self)
        d["actions"] = [a.to_dict() for a in self.actions]
        return d


@dataclasses.dataclass
class EndDayRunPlan:
    context: RunContext
    previews: list[SkillPreview]
    proposed_writes: list[WriteAction]
    noops: list[str]
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.context.run_id,
            "date": self.context.date,
            "mode": self.context.mode,
            "trigger": self.context.trigger,
            "previews": [p.to_dict() for p in self.previews],
            "proposed_writes": [w.to_dict() for w in self.proposed_writes],
            "noops": self.noops,
            "warnings": self.warnings,
        }


BRAINDUMP_ANCHORS = [
    re.compile(r"^##\s+Braindump\b", re.I),
    re.compile(r"^\*\*Braindump.*\*\*\s*$", re.I),
    re.compile(r"^Braindump:\s*$", re.I),
]


def extract_braindump(note_text: str) -> str:
    """Extract a daily-note Braindump section across known heading variants."""
    lines = note_text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if any(p.match(line.strip()) for p in BRAINDUMP_ANCHORS):
            start = i + 1
            break
    if start is None:
        return ""
    end = len(lines)
    for j in range(start, len(lines)):
        stripped = lines[j].strip()
        if re.match(r"^##\s+", stripped) or re.match(r"^\*\*[A-Z]", stripped):
            end = j
            break
    return "\n".join(lines[start:end]).strip()


def _clean_title(line: str) -> str:
    text = re.sub(r"<!--.*?-->", "", line)
    text = re.sub(r"^- \[[ xX]\]\s*", "", text).strip()
    text = re.sub(r"\*\*", "", text)
    return text.strip(" -·")


def extract_checked_source_actions(note_text: str) -> list[dict[str, Any]]:
    """Return source-sync actions implied by checked daily-note lines."""
    out: list[dict[str, Any]] = []
    for lineno, line in enumerate(note_text.splitlines(), start=1):
        # Match the RAW line (not line.strip()) so only column-0 checkboxes are
        # syncable — an indented `  - [x] ... <!-- gtask:id -->` sub-bullet must
        # NOT trigger a sync write (contract #1 made self-enforcing, not assumed).
        if not re.match(r"^- \[[xX]\]\s+", line):
            continue
        marker = re.search(r"<!--\s*(gtask|notion|derived):([^>]+?)\s*-->", line)
        title = _clean_title(line)
        if not marker or marker.group(1) == "derived":
            out.append({"type": "manual_completion", "title": title, "source_line": lineno, "source_text": line})
        elif marker.group(1) == "gtask":
            out.append({"type": "gtask_complete", "title": title, "source_id": marker.group(2).strip(), "source_line": lineno, "source_text": line})
        elif marker.group(1) == "notion":
            out.append({"type": "notion_done", "title": title, "source_id": marker.group(2).strip(), "source_line": lineno, "source_text": line})
    return out


def preview_end_day_core(ctx: RunContext) -> SkillPreview:
    if not ctx.daily_note_path.exists():
        return SkillPreview(skill="end_day", summary=f"No daily note at {ctx.daily_note_path}", warnings=["daily note missing"])
    text = ctx.daily_note_path.read_text(encoding="utf-8", errors="replace")
    checked = extract_checked_source_actions(text)
    actions: list[WriteAction] = []
    for item in checked:
        risk = "safe" if item["type"] in {"gtask_complete", "notion_done"} else "local"
        actions.append(WriteAction(owner="end_day", type=item["type"], title=item["title"], source_line=item.get("source_line"), source_text=item.get("source_text", ""), source_id=item.get("source_id"), risk=risk))
    summary = f"{len(checked)} checked completion(s) found in daily note"
    return SkillPreview(skill="end_day", summary=summary, actions=actions)


def preview_sync_sweep(ctx: RunContext) -> SkillPreview:
    if not ctx.daily_note_path.exists():
        return SkillPreview(skill="sync_sweep", summary="No daily note; sync-sweep no-op", noops=["daily note missing"])
    text = ctx.daily_note_path.read_text(encoding="utf-8", errors="replace")
    braindump = extract_braindump(text)
    if not braindump.strip():
        return SkillPreview(skill="sync_sweep", summary="sync-sweep no-op: no Braindump section or section empty", noops=["no Braindump section"])

    # MVP preview: deterministic entity-like lines only. Full Notion resolution remains in the skill.
    actions: list[WriteAction] = []
    for idx, line in enumerate(braindump.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or "<!-- synced to notion:" in stripped or "<!-- nh-harvested:" in stripped:
            continue
        # Conservative: stage as review-only if it contains a capitalized person/org-like token.
        if re.search(r"\b(?:Dr\.?\s+)?[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3}\b", stripped):
            actions.append(WriteAction(owner="sync_sweep", type="notion_append_review", title=stripped[:90], source_line=idx, source_text=stripped, confidence=0.65, risk="review", selected_by_default=False))
    return SkillPreview(skill="sync_sweep", summary=f"Braindump present; {len(actions)} review candidate(s) staged", actions=actions, raw={"braindump_chars": len(braindump)})


def _latest_preview_file(ctx: RunContext, before_ts: float) -> pathlib.Path | None:
    preview_dir = ctx.repo_dir / ".context" / "preview"
    if not preview_dir.exists():
        return None
    candidates = sorted(preview_dir.glob(f"note-harvest-nh-{ctx.date.replace('-', '')}-*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for p in candidates:
        if p.stat().st_mtime >= before_ts - 2:
            return p
    return candidates[0] if candidates else None


def preview_note_harvest(ctx: RunContext, timeout: int = 90) -> SkillPreview:
    before = time.time()
    cmd = [sys.executable, str(ctx.repo_dir / "scripts" / "note_harvest.py"), "--date", ctx.date, "--trigger", "end-day", "--observe"]
    try:
        result = subprocess.run(cmd, cwd=str(ctx.repo_dir), capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return SkillPreview(skill="note_harvest", summary="note-harvest preview timed out", warnings=["timeout"])
    if result.returncode not in (0,):
        return SkillPreview(skill="note_harvest", summary="note-harvest preview failed", warnings=[result.stderr[:500] or result.stdout[:500]], raw={"returncode": result.returncode})
    path = _latest_preview_file(ctx, before)
    if not path:
        return SkillPreview(skill="note_harvest", summary="note-harvest no preview payload", noops=["no payload"])
    try:
        payload = json.loads(path.read_text())
    except Exception as e:
        return SkillPreview(skill="note_harvest", summary="note-harvest payload unreadable", warnings=[repr(e)])

    actions: list[WriteAction] = []
    for a in payload.get("actions", []):
        if a.get("resolution") == "uncategorized" or float(a.get("confidence") or 0) < 0.70:
            continue
        actions.append(WriteAction(owner="note_harvest", type=a.get("dispatch_type", "unknown"), title=a.get("title") or a.get("clause") or "note-harvest action", source_line=a.get("source_line"), source_text=a.get("source_text") or a.get("clause", ""), confidence=float(a.get("confidence") or 0), payload=a, risk="review", selected_by_default=False))
    uncategorized = sum(1 for a in payload.get("actions", []) if a.get("resolution") == "uncategorized" or float(a.get("confidence") or 0) < 0.70)
    summary = f"{len(actions)} staged action(s), {uncategorized} uncategorized; payload {path.name}"
    return SkillPreview(skill="note_harvest", summary=summary, actions=actions, raw={"payload_path": str(path), "candidates_found": payload.get("candidates_found")})



def preview_event_reconcile(ctx: RunContext, timeout: int = 30) -> SkillPreview:
    """Preview business-progress reconciliations from Hermes/Telegram + Obsidian.

    This worker is intentionally read-only. It calls scripts/event_reconcile.py,
    which produces source-grounded CRM/Rolodex candidates but never writes to
    Notion, Google, or the vault. /end-day remains the single approval surface.
    """
    cmd = [sys.executable, str(ctx.repo_dir / "scripts" / "event_reconcile.py"), "--date", ctx.date, "--json", "--repo-dir", str(ctx.repo_dir)]
    try:
        result = subprocess.run(cmd, cwd=str(ctx.repo_dir), capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return SkillPreview(skill="event_reconcile", summary="event-reconcile preview timed out", warnings=["timeout"])
    if result.returncode != 0:
        return SkillPreview(skill="event_reconcile", summary="event-reconcile preview failed", warnings=[result.stderr[:500] or result.stdout[:500]], raw={"returncode": result.returncode})
    try:
        payload = json.loads(result.stdout)
    except Exception as e:
        return SkillPreview(skill="event_reconcile", summary="event-reconcile JSON unreadable", warnings=[repr(e), result.stdout[:500]])

    actions: list[WriteAction] = []
    for item in payload.get("proposed_reconciliations", []):
        evidence = item.get("evidence", {}) or {}
        actions.append(WriteAction(
            owner="event_reconcile",
            type=item.get("event_type", "business_progress_candidate"),
            title=item.get("title") or evidence.get("excerpt") or "business-progress candidate",
            source_line=evidence.get("line"),
            source_text=evidence.get("excerpt", ""),
            source_id=item.get("action_id") or evidence.get("event_id"),
            confidence=float(item.get("confidence") or 0),
            payload=item,
            risk="review",
            selected_by_default=False,
        ))
    summary = payload.get("summary") or f"{len(actions)} business-progress candidate(s)"
    return SkillPreview(skill="event_reconcile", summary=summary, actions=actions, noops=payload.get("noops", []), warnings=payload.get("warnings", []), raw=payload)


def merge_previews(ctx: RunContext, previews: list[SkillPreview]) -> EndDayRunPlan:
    proposed: list[WriteAction] = []
    noops: list[str] = []
    warnings: list[str] = []

    # Priority gives source-line ownership to action-dispatch before context append,
    # but source syncs from end-day are safe and listed first.
    owner_rank = {"end_day": 0, "note_harvest": 1, "sync_sweep": 2, "event_reconcile": 3}
    all_actions = [a for p in previews for a in p.actions]
    all_actions.sort(key=lambda a: (owner_rank.get(a.owner, 9), a.source_line or 999999, a.type))

    owned_lines: dict[tuple[int | None, str], WriteAction] = {}
    exact_keys: set[str] = set()
    for action in all_actions:
        key = action.action_key()
        if key in exact_keys:
            warnings.append(f"duplicate skipped: {action.owner} {action.type} {action.title[:60]}")
            continue
        exact_keys.add(key)

        norm_source = re.sub(r"\s+", " ", action.source_text.strip().lower())[:160]
        line_key = (action.source_line, norm_source)
        existing = owned_lines.get(line_key)
        if existing and existing.owner != action.owner:
            # note-harvest claims lines before sync-sweep; end_day source sync can coexist.
            if {existing.owner, action.owner} == {"note_harvest", "sync_sweep"}:
                warnings.append(f"sync_sweep skipped line {action.source_line}: note_harvest already owns source line")
                continue
        if action.owner in {"note_harvest", "sync_sweep"}:
            owned_lines[line_key] = action
        proposed.append(action)

    proposed.sort(key=lambda a: (owner_rank.get(a.owner, 9), a.source_line or 999999))
    for p in previews:
        noops.extend([f"{p.skill}: {n}" for n in p.noops])
        warnings.extend([f"{p.skill}: {w}" for w in p.warnings])
    return EndDayRunPlan(ctx, previews, proposed, noops, warnings)


def render_plan(plan: EndDayRunPlan) -> str:
    lines = [
        f"# /end-day Unified Preview — {plan.context.date}",
        "",
        f"Run: `{plan.context.run_id}` · Mode: `{plan.context.mode}` · Trigger: `{plan.context.trigger}`",
        "",
        "## Module summaries",
    ]
    for p in plan.previews:
        lines.append(f"- **{p.skill}** — {p.summary}")
    if plan.noops:
        lines.append("\n## No-ops")
        lines.extend(f"- {n}" for n in plan.noops)
    if plan.warnings:
        lines.append("\n## Warnings / dedupe")
        lines.extend(f"- {w}" for w in plan.warnings)

    groups: dict[str, list[WriteAction]] = {}
    for a in plan.proposed_writes:
        groups.setdefault(a.owner, []).append(a)
    lines.append("\n## Proposed writes / approvals")
    if not plan.proposed_writes:
        lines.append("No proposed writes.")
    for owner, actions in groups.items():
        lines.append(f"\n### {owner} ({len(actions)})")
        for i, a in enumerate(actions, start=1):
            default = "preselected" if a.selected_by_default else "review"
            src = f" L{a.source_line}" if a.source_line else ""
            sid = f" `{a.source_id}`" if a.source_id else ""
            lines.append(f"- [{default}] **{a.type}**{src}{sid}: {a.title[:140]}")
    lines.append("\nApproval execution is intentionally staged: use this preview as the single gate, then run approved legacy executors or the upcoming `--approve` adapter.")
    return "\n".join(lines)


def get_mode(repo_dir: pathlib.Path) -> str:
    mode_file = repo_dir / "state" / "coo_mode.yaml"
    if not mode_file.exists():
        return "draft"
    try:
        import yaml  # type: ignore
        return (yaml.safe_load(mode_file.read_text()) or {}).get("mode", "draft")
    except Exception:
        return "draft"


def build_preview(ctx: RunContext) -> EndDayRunPlan:
    workers = [preview_end_day_core, preview_sync_sweep, preview_note_harvest, preview_event_reconcile]
    previews: list[SkillPreview] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(workers)) as ex:
        future_map = {ex.submit(w, ctx): w.__name__ for w in workers}
        for fut in concurrent.futures.as_completed(future_map):
            try:
                previews.append(fut.result())
            except Exception as e:
                previews.append(SkillPreview(skill=future_map[fut], summary="worker failed", warnings=[repr(e)]))
    previews.sort(key=lambda p: {"end_day": 0, "note_harvest": 1, "sync_sweep": 2, "event_reconcile": 3}.get(p.skill, 9))
    return merge_previews(ctx, previews)


def stage_plan(plan: EndDayRunPlan) -> pathlib.Path:
    # Preview payloads live under .context/preview/ so /start-day does not flag
    # them as prior-session pending writes. Approved/executing runs can promote
    # selected actions into top-level .context/ or .context/applied/ later.
    context = plan.context.repo_dir / ".context" / "preview"
    context.mkdir(parents=True, exist_ok=True)
    data = plan.to_dict()
    data["status"] = "preview"
    path = context / f"end-day-{plan.context.run_id}.json"
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def append_telemetry(plan: EndDayRunPlan, status: str = "ok") -> None:
    extra = {
        "mode": plan.context.mode,
        "date": plan.context.date,
        "trigger": plan.context.trigger,
        "integrated": True,
        "module_summaries": {p.skill: p.summary for p in plan.previews},
        "proposed_writes": len(plan.proposed_writes),
        "warnings": len(plan.warnings),
        "noops": len(plan.noops),
    }
    cmd = [str(plan.context.repo_dir / "scripts" / "telemetry.sh"), "end-day-orchestrator", plan.context.run_id, "0", status, json.dumps(extra)]
    subprocess.run(cmd, cwd=str(plan.context.repo_dir), check=False, capture_output=True, text=True, timeout=10)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Integrated /end-day preview orchestrator")
    parser.add_argument("--date", default=dt.date.today().isoformat())
    parser.add_argument("--trigger", default="standalone")
    parser.add_argument("--preview", action="store_true", help="Build unified preview and stage .context payload")
    parser.add_argument("--json", action="store_true", help="Print JSON plan instead of markdown")
    args = parser.parse_args(argv)

    repo = REPO_DIR
    run_id = f"ed-{args.date.replace('-', '')}-{dt.datetime.now().strftime('%H%M%S')}"
    ctx = RunContext(date=args.date, mode=get_mode(repo), run_id=run_id, repo_dir=repo, trigger=args.trigger)
    plan = build_preview(ctx)
    path = stage_plan(plan)
    append_telemetry(plan)

    if args.json:
        print(json.dumps({**plan.to_dict(), "stage_path": str(path)}, indent=2))
    else:
        print(render_plan(plan))
        print(f"\nStaged: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
