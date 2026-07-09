#!/usr/bin/env python3
"""Calendar refinement — pure scheduling engine (Slice 1).

Converts the day's 3 outputs + must-convert meetings into PROPOSED, time-blocked
calendar commitments. **Pure**: no network, no disk, no subprocess. Config is
argument-injected (the skill reads `config/calendar.yaml` and passes a dict). This
module imports the output dataclasses from `output_planning.py` but owns ALL the
scheduling logic, so the parser-critical `output_planning.py` renderer stays the
"ponytail-minimal cut" its docstring promises.

NON-NEGOTIABLES this module encodes (see start day revamp/02-...-plan.md):
  * INSERT-ONLY world: this module only PROPOSES blocks. Nothing here writes to
    Google Calendar; the write adapter is a later, separately-gated slice.
  * GROUNDED: every block carries `source_markers` citing the output/meeting it
    executes. A block that cannot be placed (e.g. PREP with no pre-room) is
    DROPPED with a visible flag, never silently.
  * DST-correct: emits fully-offset RFC3339 via stdlib `zoneinfo` (the offset is
    computed per-date, so EST/EDT is always right — never a hardcoded -04:00).
  * Parser-safe render: Execution-Plan lines use the `▹` sigil and are NOT
    `- [ ]` checkboxes, so `end_day_orchestrator.extract_checked_source_actions`
    never ingests them as completions (it matches only `^- \\[[xX]\\]`).
  * Deterministic idempotency: `action_id` is hashed over the SAME string as
    `dedupe_key` (`{output_id}|{block_type}|{date}|{start_15m}`), so re-running at
    a different wall-clock minute yields the same id.

v1 block taxonomy (plan T1): FOCUS, PREP, CAPTURE, EOD. The other four
(DELEGATION/BATCH/ADMIN/BUFFER) are deferred until the 4-type version proves
honored.
"""
from __future__ import annotations

import dataclasses
import hashlib
import re
from datetime import datetime, time, timedelta
from typing import Any, List, Optional, Tuple
from zoneinfo import ZoneInfo

# Import the output dataclasses; we never reach back into the renderer logic.
try:  # pragma: no cover - import shim for both `python scripts/x` and package use
    from output_planning import DailyOutput, SourceRef  # type: ignore
except ImportError:  # pragma: no cover
    import pathlib
    import sys

    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    from output_planning import DailyOutput, SourceRef  # type: ignore

V1_BLOCK_TYPES = ("FOCUS", "PREP", "CAPTURE", "EOD")


@dataclasses.dataclass(frozen=True)
class CalendarBlockProposal:
    """One proposed, time-blocked commitment. Display-only until a later slice."""

    output_id: str
    block_type: str           # one of V1_BLOCK_TYPES
    summary: str              # namespaced, e.g. "▹ FOCUS — Vendor A pilot handoff"
    start: str                # fully-offset RFC3339, e.g. "2026-06-22T09:00:00-04:00"
    end: str
    stream: str
    source_markers: List[str]  # ["[cal]"] / ["[notion:abc]"] ...
    write_eligible: bool
    dedupe_key: str
    action_id: str
    flags: List[str] = dataclasses.field(default_factory=list)


@dataclasses.dataclass(frozen=True)
class ExecutionPlan:
    """Result of a proposal pass: the blocks plus plan-level accounting/flags.

    Returning a small result object (rather than a bare list) is what lets the
    render + tests see `over_capacity` / `all_day_anchor` / `field_day_dropped_focus`
    / `prep_no_preroom`, none of which can attach to a block that was never placed.
    """

    blocks: List[CalendarBlockProposal]
    open_minutes: int
    proposed_minutes: int
    unplaced: int
    flags: List[str] = dataclasses.field(default_factory=list)


# ---------------------------------------------------------------------------
# datetime helpers (all tz-aware; DST handled by zoneinfo per-date)
# ---------------------------------------------------------------------------

def _tz(config: dict) -> ZoneInfo:
    return ZoneInfo(config["working_bounds"].get("tz", "America/New_York"))


def _bounds(date: str, config: dict, day_type: Optional[str] = None) -> Tuple[datetime, datetime]:
    tz = _tz(config)
    d = datetime.strptime(date, "%Y-%m-%d").date()
    wb = dict(config["working_bounds"])
    if day_type == "field":
        # Field days often include evening relationship work. Let config extend
        # the bounds (usually just `end`) without changing normal deep-work days.
        wb.update(config.get("field_day_bounds", {}) or {})
    sh, sm = (int(x) for x in wb["start"].split(":"))
    eh, em = (int(x) for x in wb["end"].split(":"))
    return (
        datetime.combine(d, time(sh, sm), tzinfo=tz),
        datetime.combine(d, time(eh, em), tzinfo=tz),
    )


def _parse_dt(raw: str, tz: ZoneInfo) -> Optional[datetime]:
    """Parse an RFC3339/ISO anchor time. Returns None for date-only (all-day)."""
    if not raw or "T" not in raw:
        return None
    s = raw.replace("Z", "+00:00")  # py3.9 fromisoformat can't take a bare Z
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz)
    return dt


def _minutes(a: datetime, b: datetime) -> int:
    return max(0, int((b - a).total_seconds() // 60))


def _hm(dt: datetime) -> str:
    return f"{dt.hour % 12 or 12}:{dt.minute:02d}"


def _hm_dur(mins: int) -> str:
    h, m = divmod(mins, 60)
    if h and m:
        return f"{h}h{m}m"
    if h:
        return f"{h}h"
    return f"{m}m"


def _round15(dt: datetime) -> str:
    return f"{dt.hour:02d}:{(dt.minute // 15) * 15:02d}"


# ---------------------------------------------------------------------------
# interval math
# ---------------------------------------------------------------------------

def _merge(intervals: List[Tuple[datetime, datetime]]) -> List[Tuple[datetime, datetime]]:
    out: List[Tuple[datetime, datetime]] = []
    for s, e in sorted(intervals):
        if out and s <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], e))
        else:
            out.append((s, e))
    return out


def _subtract(b_start: datetime, b_end: datetime,
              busy: List[Tuple[datetime, datetime]]) -> List[Tuple[datetime, datetime]]:
    """Open windows = [b_start, b_end] minus the (merged) busy intervals."""
    open_win: List[Tuple[datetime, datetime]] = []
    cur = b_start
    for s, e in _merge(busy):
        s = max(s, b_start)
        e = min(e, b_end)
        if e <= cur:
            continue
        if s > cur:
            open_win.append((cur, s))
        cur = max(cur, e)
        if cur >= b_end:
            break
    if cur < b_end:
        open_win.append((cur, b_end))
    return open_win


def _all_day_busy(anchor: dict, config: dict) -> bool:
    """Whether a date-only/all-day anchor should consume the whole workday.

    Default is configurable because many business all-day calendar entries are
    reminders/context, not true busy blocks. Per-anchor `busy` overrides the
    default when the live adapter can supply it.
    """
    if "busy" in anchor:
        return bool(anchor.get("busy"))
    return bool(config.get("all_day_busy_default", True))


def compute_open_windows(anchors: List[dict], *, config: dict, date: str,
                         day_type: Optional[str] = None
                         ) -> Tuple[List[Tuple[datetime, datetime]], bool]:
    """Return (open_windows, all_day_anchor_present).

    anchors reuse the Step-2 calendar shape: {start, end, summary, location}.
    All-day anchors (date-only start) are informational by default when
    `all_day_busy_default: false`; set per-anchor `busy: true` to consume the
    workday. An anchor with a missing/blank end is treated as zero-length
    (contributes no busy time) so a malformed event never crashes placement.
    """
    tz = _tz(config)
    b_start, b_end = _bounds(date, config, day_type)
    busy: List[Tuple[datetime, datetime]] = []
    all_day = False
    for a in anchors:
        s_raw = a.get("start", "")
        if not s_raw:
            continue
        if "T" not in s_raw:  # date-only → all-day
            all_day = True
            if _all_day_busy(a, config):
                busy.append((b_start, b_end))
            continue
        s = _parse_dt(s_raw, tz)
        if s is None:
            continue
        e = _parse_dt(a.get("end", ""), tz) or s  # missing end → zero-length
        if e < s:
            e = s
        s, e = max(s, b_start), min(e, b_end)
        if e > s:
            busy.append((s, e))
    return _subtract(b_start, b_end, busy), all_day


# ---------------------------------------------------------------------------
# source markers + ids
# ---------------------------------------------------------------------------

def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "output"


def _output_attr(output: Any, name: str, default: Any = None) -> Any:
    if isinstance(output, dict):
        return output.get(name, default)
    return getattr(output, name, default)


def _display_marker(ref: SourceRef) -> str:
    if ref.system in ("notion", "gtask") and ref.id:
        return f"[{ref.system}:{ref.id}]"
    if ref.system == "cal":
        return "[cal]"
    return "[derived]"


def _output_markers(output: Any) -> List[str]:
    refs = _output_attr(output, "source_refs", []) or []
    markers = [_display_marker(r) for r in refs]
    return markers or ["[derived]"]


def _make_block(output_id: str, block_type: str, title: str, start: datetime,
                end: datetime, stream: str, markers: List[str], date: str,
                config: dict, flags: Optional[List[str]] = None) -> CalendarBlockProposal:
    ns = config.get("block_namespace", "▹")
    dedupe_key = f"{output_id}|{block_type}|{date}|{_round15(start)}"
    digest = hashlib.sha256(dedupe_key.encode()).hexdigest()[:8]
    return CalendarBlockProposal(
        output_id=output_id,
        block_type=block_type,
        summary=f"{ns} {block_type} — {title}",
        start=start.isoformat(),
        end=end.isoformat(),
        stream=stream,
        source_markers=markers,
        write_eligible=False,  # insert-only world; nothing is write-eligible this slice
        dedupe_key=dedupe_key,
        action_id=f"refine-calendar:cal:{date}:{digest}",
        flags=list(flags or []),
    )


# ---------------------------------------------------------------------------
# placement
# ---------------------------------------------------------------------------

def _is_meeting(anchor: dict, config: dict) -> bool:
    """A timed anchor whose summary isn't a routine keyword is a must-convert meeting."""
    if "T" not in anchor.get("start", ""):
        return False  # all-day events aren't treated as convertible meetings in v1
    summ = (anchor.get("summary") or "").lower()
    if _is_important_meeting(anchor, config):
        return True
    return not any(k in summ for k in config.get("routine_keywords", []))


def _is_important_meeting(anchor: dict, config: dict) -> bool:
    """Important relationship meetings always get the strongest prep attempt.

    Lunches/dinners/breakfasts are often the actual high-leverage meetings in
    the operator's field days, so they must not be suppressed by the routine-keyword
    filter and they should get the full PREP max when the window exists.
    """
    summ = (anchor.get("summary") or "").lower()
    return any(k in summ for k in config.get("important_meeting_keywords", []))


def _free_before(t: datetime, occupied: List[Tuple[datetime, datetime]],
                 floor: datetime, max_span: int) -> datetime:
    """Latest free start s.t. [start, t) is unoccupied, bounded by floor/max_span."""
    start = max(floor, t - timedelta(minutes=max_span))
    moved = True
    while moved and start < t:
        moved = False
        for s, e in occupied:
            if s < t and e > start:  # overlaps [start, t)
                start = max(start, e)
                moved = True
    return min(start, t)


def _free_after(t: datetime, occupied: List[Tuple[datetime, datetime]],
                ceil: datetime, max_span: int) -> datetime:
    """Earliest free end s.t. [t, end) is unoccupied, bounded by ceil/max_span."""
    end = min(ceil, t + timedelta(minutes=max_span))
    moved = True
    while moved and end > t:
        moved = False
        for s, e in occupied:
            if s < end and e > t:  # overlaps [t, end)
                end = min(end, s)
                moved = True
    return max(end, t)


def propose_calendar_blocks(outputs: List[Any], anchors: List[dict], *,
                            config: dict, day_type: str, date: str) -> ExecutionPlan:
    """Propose FOCUS/PREP/CAPTURE/EOD blocks. Deterministic, pure, insert-only."""
    tz = _tz(config)
    b_start, b_end = _bounds(date, config, day_type)
    dur = config["durations"]
    min_gap = int(config.get("min_gap_min", 20))

    open_windows, all_day = compute_open_windows(anchors, config=config, date=date,
                                                 day_type=day_type)
    open_minutes = sum(_minutes(s, e) for s, e in open_windows)

    # Seed occupied with the anchor busy set (so blocks never overlap fixed events).
    occupied: List[Tuple[datetime, datetime]] = []
    for a in anchors:
        s_raw = a.get("start", "")
        if not s_raw:
            continue
        if "T" not in s_raw:
            if _all_day_busy(a, config):
                occupied.append((b_start, b_end))
            continue
        s = _parse_dt(s_raw, tz)
        if s is None:
            continue
        e = _parse_dt(a.get("end", ""), tz) or s
        if e < s:
            e = s
        s, e = max(s, b_start), min(e, b_end)
        if e > s:
            occupied.append((s, e))

    blocks: List[CalendarBlockProposal] = []
    plan_flags: List[str] = []
    if all_day:
        plan_flags.append("all_day_anchor")

    # --- PREP / CAPTURE around must-convert meetings -----------------------
    meetings = sorted((a for a in anchors if _is_meeting(a, config)),
                      key=lambda a: a["start"])
    for m in meetings:
        m_start = _parse_dt(m["start"], tz)
        m_end = _parse_dt(m.get("end", ""), tz) or m_start
        if m_start is None:
            continue
        title = (m.get("summary") or "meeting").strip()
        mid = "meeting:" + _slug(title)

        prep_start = _free_before(m_start, occupied, b_start, dur["PREP"]["max"])
        prep_required = dur["PREP"]["max"] if _is_important_meeting(m, config) else dur["PREP"]["min"]
        if _minutes(prep_start, m_start) >= prep_required:
            avail = _minutes(prep_start, m_start)
            block_start = m_start - timedelta(minutes=min(dur["PREP"]["max"], avail))
            blocks.append(_make_block(mid, "PREP", title, block_start, m_start,
                                      "meeting", ["[cal]"], date, config))
            occupied.append((block_start, m_start))
        else:
            plan_flags.append("important_prep_no_30min" if _is_important_meeting(m, config) else "prep_no_preroom")

        cap_end = _free_after(m_end, occupied, b_end, dur["CAPTURE"]["max"])
        if _minutes(m_end, cap_end) >= dur["CAPTURE"]["min"]:
            block_end = m_end + timedelta(minutes=min(dur["CAPTURE"]["max"],
                                                      _minutes(m_end, cap_end)))
            blocks.append(_make_block(mid, "CAPTURE", title, m_end, block_end,
                                      "meeting", ["[cal]"], date, config))
            occupied.append((m_end, block_end))

    # --- FOCUS per output --------------------------------------------------
    # Deep-work days fill normal focus windows. Field days are stricter: they
    # normally run through meetings, but a truly massive gap BETWEEN fixed
    # commitments should not become downtime/BS — use it for the highest-value
    # Top-3 output.
    unplaced = 0
    focus_threshold = int(config.get("field_focus_min_window_min", 120)) if day_type == "field" else max(min_gap, dur["FOCUS"]["min"])
    focus_windows = []
    for w_start, w_end in _subtract(b_start, b_end, occupied):
        if _minutes(w_start, w_end) < focus_threshold:
            continue
        if day_type == "field" and (w_start <= b_start or w_end >= b_end):
            # On field days only fill gaps bounded by real commitments. A wide
            # open morning/evening edge is usually travel/admin flex, not a
            # protected deep-work commitment.
            continue
        focus_windows.append((w_start, w_end))

    if day_type == "field" and not focus_windows:
        if outputs:
            plan_flags.append("field_day_dropped_focus")
    else:
        for output in outputs:
            title = (_output_attr(output, "title", "") or "").strip()
            stream = _output_attr(output, "owner", "") or ""
            oid = _slug(title)
            placed = False
            # Re-derive open windows from the evolving occupied set; prefer morning.
            for w_start, w_end in _subtract(b_start, b_end, occupied):
                if _minutes(w_start, w_end) < focus_threshold:
                    continue
                if day_type == "field" and (w_start <= b_start or w_end >= b_end):
                    continue
                f_end = w_start + timedelta(minutes=min(dur["FOCUS"]["max"],
                                                        _minutes(w_start, w_end)))
                blocks.append(_make_block(oid, "FOCUS", title, w_start, f_end,
                                          stream, _output_markers(output), date, config))
                occupied.append((w_start, f_end))
                placed = True
                break
            if not placed:
                unplaced += 1
    if unplaced:
        plan_flags.append("over_capacity")

    # --- EOD scorecard block ----------------------------------------------
    eod_start = _free_before(b_end, occupied, b_start, dur["EOD"]["max"])
    if _minutes(eod_start, b_end) >= dur["EOD"]["min"]:
        block_start = b_end - timedelta(minutes=min(dur["EOD"]["max"],
                                                    _minutes(eod_start, b_end)))
        blocks.append(_make_block("eod", "EOD", "Output scorecard", block_start,
                                  b_end, "other", ["[derived]"], date, config))
        occupied.append((block_start, b_end))

    blocks.sort(key=lambda b: b.start)
    proposed_minutes = sum(
        _minutes(datetime.fromisoformat(b.start), datetime.fromisoformat(b.end))
        for b in blocks
    )
    return ExecutionPlan(
        blocks=blocks,
        open_minutes=open_minutes,
        proposed_minutes=proposed_minutes,
        unplaced=unplaced,
        flags=plan_flags,
    )


# ---------------------------------------------------------------------------
# render (phone-first; ▹ display lines, NEVER `- [ ]` checkboxes)
# ---------------------------------------------------------------------------

def render_execution_plan_markdown(plan: ExecutionPlan) -> str:
    """Render the `## Execution Plan` section. Lines are `▹` display lines so the
    end-day checkbox parser never ingests them. The `<!-- coo-block:action_id -->`
    marker is what a future EOD scorecard parses; it is NOT a sync marker."""
    lines: List[str] = ["## Execution Plan"]
    lines.append(
        f"_open today: {_hm_dur(plan.open_minutes)} · "
        f"proposing {_hm_dur(plan.proposed_minutes)}_"
    )
    if not plan.blocks:
        if "field_day_dropped_focus" in plan.flags:
            lines.append("_No execution blocks today — field day, running via meetings._")
        elif "all_day_anchor" in plan.flags:
            lines.append("_all-day event consumes today's open window._")
        else:
            lines.append("_No execution blocks today._")
        return "\n".join(lines).rstrip() + "\n"

    for b in plan.blocks:
        s = datetime.fromisoformat(b.start)
        e = datetime.fromisoformat(b.end)
        title = b.summary.split("— ", 1)[-1]
        lines.append(
            f"▹ {_hm(s)}–{_hm(e)} {b.block_type} · {title} "
            f"<!-- coo-block:{b.action_id} -->"
        )

    if plan.unplaced:
        lines.append(
            f"⚠️ {plan.unplaced} output(s) unplaced — capacity full; defer or delegate."
        )
    if "field_day_dropped_focus" in plan.flags:
        lines.append("_field day: no deep-work blocks; outputs run via meetings._")
    return "\n".join(lines).rstrip() + "\n"
