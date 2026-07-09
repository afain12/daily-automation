#!/usr/bin/env python3
"""capture_meeting_parse.py — extract + categorize + idempotency-check meeting notes.

Extracted from `/capture-meeting` Steps 4 + 4.5 so that `/sync-sweep` (class C path)
and any future programmatic caller can re-use the same parse/categorize logic.

CLI:
    capture_meeting_parse.py (--notes-file PATH | --stdin) --date YYYY-MM-DD
                             --meeting-key STR
                             [--business-tag {product,product,sales,lab,other}]
                             [--attendees STR] [--config-dir PATH]
                             [--routing-config PATH] [--sources-config PATH]
                             [--self-test]

Output (stdout): JSON array of categorized items. See README in sync-sweep-tasks.md T3a.

Exit codes:
    0 — success
    1 — config error / file not found / parse error
    2 — empty input
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

try:
    import yaml  # type: ignore
except ImportError:
    print("error: pyyaml is required", file=sys.stderr)
    sys.exit(1)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT: Path = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_DIR: Path = REPO_ROOT / "config"
ACTION_ID_SCRIPT: Path = REPO_ROOT / "scripts" / "action_id.sh"

VALID_BUSINESS_TAGS = ("product", "product", "sales", "lab", "other")
CONFIDENCE_THRESHOLD = 0.70


# ---------------------------------------------------------------------------
# gws banner strip (G7 acceptance criterion)
# ---------------------------------------------------------------------------

_GWS_BANNER_RE = re.compile(rb"^Using keyring backend: \S+\s*\n")


def strip_gws_keyring_banner(stdout_bytes: bytes) -> bytes:
    """Strip the 'Using keyring backend: <name>\\n' prefix that gws emits
    on Windows before JSON output. Returns cleaned bytes safe for json.loads.

    No-op if the banner is absent. Strips at most one banner line.
    """
    if not isinstance(stdout_bytes, (bytes, bytearray)):
        raise TypeError("strip_gws_keyring_banner requires bytes input")
    m = _GWS_BANNER_RE.match(stdout_bytes)
    if m:
        return stdout_bytes[m.end():]
    return bytes(stdout_bytes)


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

@dataclass
class Config:
    routing: dict[str, Any]
    calendar_business_keywords: dict[str, list[str]]
    workspace_values: dict[str, str]
    single_dept_persons: dict[str, str]
    entity_aliases: dict[str, str]


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"config file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"expected mapping at top of {path}, got {type(data).__name__}")
    return data


def load_config(routing_path: Path, sources_path: Path) -> Config:
    routing_yaml = _load_yaml(routing_path)
    sources_yaml = _load_yaml(sources_path)

    routing = routing_yaml.get("routing", {})
    if not routing:
        raise ValueError(f"{routing_path}: missing 'routing' top-level key")

    cbk = sources_yaml.get("calendar_business_keywords", {}) or {}

    # workspace_values lives under notion_databases → Master Tasks entry
    workspace_values: dict[str, str] = {}
    for db in sources_yaml.get("notion_databases", []) or []:
        if db.get("name") == "Master Tasks":
            workspace_values = db.get("workspace_values", {}) or {}
            break

    single_dept = sources_yaml.get("single_dept_persons", {}) or {}
    entity_aliases = sources_yaml.get("entity_aliases", {}) or {}

    return Config(
        routing=routing,
        calendar_business_keywords=cbk,
        workspace_values=workspace_values,
        single_dept_persons=single_dept,
        entity_aliases=entity_aliases,
    )


# ---------------------------------------------------------------------------
# Categorization
# ---------------------------------------------------------------------------

# Map routing-rules.yaml keys → output category labels.
ROUTING_KEY_TO_CATEGORY = {
    "action_items": "task",
    "insights": "learning",
    "follow_ups": "follow_up",
    "decisions": "decision",
    "contact_updates": "contact",
}

# Strong indicator patterns that warrant a confidence boost beyond the simple count.
STRONG_INDICATORS = {
    "decided", "agreed", "approved", "finalized", "confirmed",
    "TODO", "deadline", "follow up with",
    "schedule", "follow-up meeting",
    "spoke with Dr", "credentialing", "identifier",
}


@dataclass
class ParsedItem:
    category: str
    confidence: float
    source_line: int
    source_text: str
    owner: str | None
    owner_resolved_from: str
    due: str | None
    due_resolved_from: str | None
    secondary_hint: str | None
    action_id: str
    skip_idempotent: bool


def _split_lines(notes: str) -> list[tuple[int, str]]:
    """Return [(line_number, cleaned_line), ...] for non-empty lines.
    Strips leading bullet/checkbox markers but preserves the rest.
    """
    out: list[tuple[int, str]] = []
    for i, raw in enumerate(notes.splitlines(), start=1):
        text = raw.strip()
        if not text:
            continue
        # Strip common bullet/checkbox markers.
        text = re.sub(r"^[-*•]\s+", "", text)
        text = re.sub(r"^\[\s?[xX ]?\s?\]\s+", "", text)
        text = re.sub(r"^#+\s+", "", text)
        if text:
            out.append((i, text))
    return out


def _match_indicators(
    line: str, indicators: list[str]
) -> tuple[int, list[str]]:
    """Return (match_count, matched_terms) — case-insensitive substring search.

    `[date]` in the indicator is a sentinel; treat it as 'match if a date-like
    token is present'.
    """
    matched: list[str] = []
    low = line.lower()
    for ind in indicators:
        ind_str = str(ind)
        if "[date]" in ind_str.lower():
            head = ind_str.lower().split("[date]", 1)[0].strip()
            if head and head in low and _has_date_token(line):
                matched.append(ind_str)
            continue
        if ind_str.lower() in low:
            matched.append(ind_str)
    return len(matched), matched


_DATE_TOKEN_RE = re.compile(
    r"\b(\d{4}-\d{2}-\d{2}|"
    r"\d{1,2}/\d{1,2}(?:/\d{2,4})?|"
    r"(?:mon|tue|wed|thu|fri|sat|sun)[a-z]*|"
    r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s*\d{0,2}|"
    r"today|tomorrow|asap|next\s+\w+|by\s+end\s+of\s+(?:week|month)|by\s+\w+|eod|eow)\b",
    re.IGNORECASE,
)


def _has_date_token(line: str) -> bool:
    return bool(_DATE_TOKEN_RE.search(line))


_NAMED_ENTITY_RE = re.compile(
    r"\b(?:Dr\.?\s+[A-Z][a-zA-Z]+|"
    r"[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?)\b"
)


def _has_named_entity(line: str, attendees: list[str]) -> bool:
    if any(a and a.lower() in line.lower() for a in attendees):
        return True
    return bool(_NAMED_ENTITY_RE.search(line))


def _matches_business_tag(line: str, business_tag: str, cbk: dict[str, list[str]]) -> bool:
    if not business_tag or business_tag not in cbk:
        return False
    low = line.lower()
    return any(kw.lower() in low for kw in cbk.get(business_tag, []))


def _infer_business_tag_from_text(notes: str, cbk: dict[str, list[str]]) -> str:
    """Score each business by total keyword hits across all notes. Pick the highest."""
    low = notes.lower()
    scores: dict[str, int] = {}
    for tag, kws in cbk.items():
        c = 0
        for kw in kws:
            if not kw:
                continue
            c += low.count(kw.lower())
        if c > 0:
            scores[tag] = c
    if not scores:
        return "other"
    return max(scores.items(), key=lambda kv: kv[1])[0]


def _infer_secondary_hint(line: str, primary: str, cbk: dict[str, list[str]]) -> str | None:
    """If the line contains business-keywords other than the primary tag,
    surface the strongest 'other' tag as a hint. Implements the E1 line-override
    pattern noted in sync-sweep-tasks.md (Example Contact → lab even in product section).
    """
    low = line.lower()
    candidates: dict[str, int] = {}
    for tag, kws in cbk.items():
        if tag == primary:
            continue
        c = sum(1 for kw in kws if kw and kw.lower() in low)
        if c > 0:
            candidates[tag] = c
    if not candidates:
        return None
    return max(candidates.items(), key=lambda kv: kv[1])[0]


# ---------------------------------------------------------------------------
# Owner + due-date resolution
# ---------------------------------------------------------------------------

_OWNER_PATTERNS = [
    re.compile(r"(?:assigned to|owner|owned by)\s+([A-Z][\w.\-']+)", re.IGNORECASE),
    re.compile(r"(?:tell|ask|have)\s+([A-Z][\w.\-']+)\s+(?:to|that)", re.IGNORECASE),
]

# Common sentence-initial verbs / words that look like proper nouns but aren't
# owners. Used to filter out false-positive owner extractions.
_NON_OWNER_TOKENS = {
    "decided", "agreed", "approved", "confirmed", "finalized", "we", "i",
    "they", "spoke", "tell", "ask", "have", "need", "should", "follow",
    "schedule", "circle", "next", "going", "random", "observation", "insight",
    "idea", "remember", "interesting", "learned", "key", "the",
}


def _resolve_owner(line: str, attendees: list[str]) -> tuple[str, str]:
    """Return (owner, owner_resolved_from). Default to the operator when not found."""
    # explicit-pattern match
    for pat in _OWNER_PATTERNS:
        m = pat.search(line)
        if m:
            cand = m.group(1).strip()
            if cand and cand.lower() not in _NON_OWNER_TOKENS:
                return cand, "explicit"

    # attendee mention
    for att in attendees:
        att = att.strip()
        if not att:
            continue
        if re.search(rf"\b{re.escape(att)}\b", line, re.IGNORECASE):
            return att, "attendee_match"

    return "the operator", "default_operator"


_WEEKDAYS = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}

_MONTH_NAMES = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7,
    "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _next_weekday(anchor: date, target_idx: int, include_today: bool = False) -> date:
    delta = (target_idx - anchor.weekday()) % 7
    if delta == 0 and not include_today:
        delta = 7
    return anchor + timedelta(days=delta)


def _resolve_due(line: str, anchor: date) -> tuple[str | None, str | None]:
    """Return (due_iso_or_none, due_resolved_from_or_none).

    `anchor` is the explicit --date passed in. All 'next Tuesday' / 'tomorrow'
    parsing is RELATIVE TO THIS ANCHOR (Explore worker risk #1).
    """
    low = line.lower()

    # ISO date
    m = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", line)
    if m:
        try:
            datetime.strptime(m.group(1), "%Y-%m-%d")
            return m.group(1), "explicit_iso"
        except ValueError:
            pass

    # MM/DD/YYYY or MM/DD
    m = re.search(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b", line)
    if m:
        mo, dy, yr = m.group(1), m.group(2), m.group(3)
        try:
            mo_i, dy_i = int(mo), int(dy)
            if yr:
                yr_i = int(yr) + 2000 if len(yr) == 2 else int(yr)
            else:
                yr_i = anchor.year
            d = date(yr_i, mo_i, dy_i)
            if not yr and d < anchor:
                d = date(yr_i + 1, mo_i, dy_i)
            return d.isoformat(), "explicit_iso"
        except ValueError:
            pass

    # "today" / "tomorrow" / "asap" / "eod"
    if re.search(r"\b(today|asap|eod)\b", low):
        return anchor.isoformat(), "relative_phrase"
    # tomorrow + the operator's recurring spellings (tomm/tommrow/tommorw/…)
    if re.search(TOMORROW_ALT_RE, low):
        return (anchor + timedelta(days=1)).isoformat(), "relative_phrase"

    # "next week" → anchor + 7 days (added 2026-05-29 for annotation execution)
    if re.search(r"\bnext\s+week\b", low):
        return (anchor + timedelta(days=7)).isoformat(), "relative_phrase"

    # "by end of week" / "eow" / "this week" → Friday of anchor's week
    if re.search(
        r"\bby\s+end\s+of\s+week\b|\beow\b|\bend\s+of\s+the\s+week\b"
        r"|\bthis\s+week\b|\bwithin\s+the\s+next\s+week\b", low
    ):
        return _next_weekday(anchor, 4, include_today=True).isoformat(), "relative_phrase"

    # "by end of month"
    if re.search(r"\bby\s+end\s+of\s+month\b|\beom\b", low):
        if anchor.month == 12:
            last = date(anchor.year, 12, 31)
        else:
            last = date(anchor.year, anchor.month + 1, 1) - timedelta(days=1)
        return last.isoformat(), "relative_phrase"

    # "next <weekday>" / "this <weekday>" / "by <weekday>" / bare <weekday>
    m = re.search(
        r"\b(next|this|by)\s+(mon|tue|wed|thu|fri|sat|sun)[a-z]*\b", low
    )
    if m:
        prefix = m.group(1)
        wd_short = m.group(2)
        wd_full = next(
            (k for k in _WEEKDAYS if k.startswith(wd_short)), None
        )
        if wd_full:
            include_today = prefix == "by"
            d = _next_weekday(anchor, _WEEKDAYS[wd_full], include_today=include_today)
            return d.isoformat(), "relative_phrase"

    m = re.search(r"\b(mon|tue|wed|thu|fri|sat|sun)[a-z]*\b", low)
    if m:
        wd_short = m.group(1)
        wd_full = next(
            (k for k in _WEEKDAYS if k.startswith(wd_short)), None
        )
        if wd_full:
            d = _next_weekday(anchor, _WEEKDAYS[wd_full])
            return d.isoformat(), "relative_phrase"

    # "by <Month> <Day>" / "<Month> <Day>"
    m = re.search(
        r"\b(?:by\s+)?(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+(\d{1,2})\b",
        low,
    )
    if m:
        mon_key = m.group(1)
        dy_i = int(m.group(2))
        mo_i = _MONTH_NAMES.get(mon_key)
        if mo_i:
            try:
                d = date(anchor.year, mo_i, dy_i)
                if d < anchor:
                    d = date(anchor.year + 1, mo_i, dy_i)
                return d.isoformat(), "relative_phrase"
            except ValueError:
                pass

    return None, None


# ---------------------------------------------------------------------------
# Inline-annotation execution (added 2026-05-29)
#
# the operator writes imperative scheduling directives into the daily note as checkbox
# tails or braindump prose ("handle 9am tomm set on calender", "create cal
# event 10am", "set for 4pm tomm"). These are instructions to create a calendar
# event / gtask, NOT passive notes — and were being silently dropped. This block
# extracts them so /end-day (and /start-day's safety net) can execute them.
# See memory feedback_daily_note_annotations_are_actions.
#
# Doctrine: route by VERB, not by mere presence of a time. When unsure, the
# caller surfaces (does not auto-create) — wrongly creating is the worse failure.
# ---------------------------------------------------------------------------

# the operator's tomorrow spellings (reused by _resolve_due above and the classifier).
TOMORROW_ALT_RE = r"\b(tomorrow|tomm|tommrow|tommorw|tommorrow|tomorow|tommtorw)\b"

# Verb classifier. create_event is checked FIRST so that "11am task on calender"
# routes to the calendar (the "on calender" location wins over the word "task").
#
# Patterns are deliberately TIGHT: they require an explicit create/set/schedule
# IMPERATIVE next to a calendar/task object. Broad triggers (bare "schedule" +
# any "call/meeting" noun, bare "gtask", bare "in task") were removed 2026-05-29
# after they flooded on briefing prose ("3pm panel-loss call", "Master Tasks",
# "calendar match +2"). The trust gate is the backstop, not the filter.
_SCHED_VERB_PATTERNS = {
    "create_event": [
        r"\bset\s+(it\s+|this\s+)?on\s+(the\s+)?calend?er\b",
        r"\bset\s+(it\s+|this\s+)?on\s+(the\s+)?call?ender\b",
        r"\b(create|add|make|put|leave|throw)\s+.{0,25}\b(on\s+(the\s+)?calend?er|on\s+(the\s+)?call?ender)\b",
        r"\bcal\s+event\b", r"\bcalend?er\s+event\b", r"\bcall?ender\s+event\b",
        r"\b(create|add|make)\s+(a\s+|an\s+)?(cal\b|calend?er\b|call?ender\b)",
        r"\b(create|add|make)\s+.{0,20}\b(event|egvent|evgent|evnet)\b",
        r"\breminder\s+in\s+(the\s+)?(calend?er|call?ender)\b",
        r"\bset\s+(a\s+|an\s+)?(\d{1,2}|reminder)",      # "set 10am ...", "set a reminder"
        r"\bset\s+for\s+\d",                              # "set for 4pm"
        r"\b(set|add|block)\s+(off\s+|out\s+)?(a\s+|the\s+)?\w{0,12}\s*block\b",
        r"\btask\s+on\s+(the\s+)?calend",                 # "11am task on calender" → event
        r"\bschedule\b.{0,25}(\d{1,2}\s*[ap]\.?m|mon|tue|wed|thu|fri|sat|sun)",
        r"\bcreate\s+cal\b",
    ],
    "create_task": [
        r"\bcreate\s+(a\s+|an\s+|one\s+)?.{0,18}\btask\b",
        r"\bmake\s+(a\s+|an\s+|this\s+)?.{0,18}\btask\b",
        r"\bas\s+a\s+task\b",
        r"\bcreate\s+one\s+large\s+task\b",
        r"\bset\s+.{0,15}\btask\b",
        r"\bcreate\s+in\s+task\b",
        r"\badd\s+(a\s+|this\s+)?.{0,12}\b(to\s+)?(google\s+)?tasks?\b",
    ],
    "reschedule": [
        r"\breschedule\b", r"\bmove\s+(it\s+|this\s+)?to\b",
        r"\bpush\s+(it\s+|this\s+)?to\b", r"\bbump\s+(it\s+|this\s+)?to\b",
        r"\bpostpone\b", r"\bmove\s+.{0,20}\bto\b.{0,12}(tomm|next|tomorrow)",
    ],
}
_SCHED_VERB_COMPILED = {
    verb: [re.compile(p, re.IGNORECASE) for p in pats]
    for verb, pats in _SCHED_VERB_PATTERNS.items()
}

# Lines we must NOT re-process (already handled / synced / explicitly done).
_ANNOTATION_SKIP_RES = [
    re.compile(r"<!--\s*synced", re.IGNORECASE),
    re.compile(r"<!--\s*sched-done", re.IGNORECASE),
    re.compile(r"\(already\s+(in\s+tasks|on\s+calend)", re.IGNORECASE),
    re.compile(r"already\s+on\s+calend", re.IGNORECASE),
    re.compile(r"already\s+created", re.IGNORECASE),
    re.compile(r"not\s+a?\s*duplicate", re.IGNORECASE),
    re.compile(r"verified,?\s+not\s+duplicated", re.IGNORECASE),
]

_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_STRIKE_RE = re.compile(r"~~.+?~~", re.DOTALL)

_TIME_WORD_DEFAULTS = [
    (r"\bend\s+of\s+day\b", 17, 0), (r"\beod\b", 17, 0),
    (r"\bmorning\b", 9, 0), (r"\bnoon\b", 12, 0), (r"\bmidday\b", 12, 0),
    (r"\bafternoon\b", 14, 0), (r"\bevening\b", 18, 0), (r"\bnight\b", 19, 0),
]


def _guess_meridiem(hour: int) -> int:
    """Bare hour with no am/pm → 24h heuristic. Always flagged by the caller."""
    if hour == 12:
        return 12          # noon
    if hour < 8:
        return hour + 12   # 1–7 → PM
    return hour            # 8–11 → AM (as-is)


def _resolve_time(line: str) -> dict[str, Any] | None:
    """Extract a start (and optional end) time from a line.

    Returns {start_h, start_m, end_h, end_m, meridiem_guessed, resolved_from}
    or None if no time-like token is present. Bare numbers without am/pm,
    '@', or ':mm' are NOT treated as times (avoids matching "$3300" / "954").
    """
    low = line.lower()

    def _apply_mer(h: int, mer: str | None) -> int:
        if mer == "p" and h != 12:
            return h + 12
        if mer == "a" and h == 12:
            return 0
        return h

    # Range with meridiem: "3-4pm", "3:30-4:30pm", "3 to 4 pm"
    m = re.search(
        r"\b(\d{1,2})(?::(\d{2}))?\s*(?:-|–|to)\s*(\d{1,2})(?::(\d{2}))?\s*([ap])\.?\s*m\.?\b",
        low,
    )
    if m:
        sh, sm, eh, em, mer = m.groups()
        sh_i, eh_i = int(sh), int(eh)
        sm_i, em_i = int(sm or 0), int(em or 0)
        sh_24, eh_24 = _apply_mer(sh_i, mer), _apply_mer(eh_i, mer)
        if eh_24 <= sh_24:           # e.g. "11-12pm" → bump start to AM
            sh_24 = _apply_mer(sh_i, "a") if mer == "p" else sh_24
        if eh_24 <= sh_24:
            eh_24 = sh_24 + 1
        return {"start_h": sh_24, "start_m": sm_i, "end_h": eh_24, "end_m": em_i,
                "meridiem_guessed": False, "resolved_from": "range"}

    # Comma range: "1,2pm"
    m = re.search(r"\b(\d{1,2})\s*,\s*(\d{1,2})\s*([ap])\.?\s*m\.?\b", low)
    if m:
        sh_i, eh_i, mer = int(m.group(1)), int(m.group(2)), m.group(3)
        sh_24, eh_24 = _apply_mer(sh_i, mer), _apply_mer(eh_i, mer)
        if eh_24 <= sh_24:
            eh_24 = sh_24 + 1
        return {"start_h": sh_24, "start_m": 0, "end_h": eh_24, "end_m": 0,
                "meridiem_guessed": False, "resolved_from": "comma_range"}

    # Single time WITH meridiem: "9am", "10:30 pm", "@ 12pm", "by 4 p.m."
    m = re.search(
        r"(?:@\s*|at\s+|by\s+)?\b(\d{1,2})(?::(\d{2}))?\s*([ap])\.?\s*m\.?\b", low
    )
    if m:
        h_24 = _apply_mer(int(m.group(1)), m.group(3))
        return {"start_h": h_24, "start_m": int(m.group(2) or 0),
                "end_h": None, "end_m": None,
                "meridiem_guessed": False, "resolved_from": "single_meridiem"}

    # Single time, NO meridiem but anchored by "@" / "at " / ":mm": guess am/pm
    m = re.search(r"(?:@\s*|at\s+)(\d{1,2})(?::(\d{2}))?\b", low)
    if not m:
        m = re.search(r"\b(\d{1,2}):(\d{2})\b", low)   # "10:30" alone
    if m:
        h_raw = int(m.group(1))
        if 0 <= h_raw <= 23:
            return {"start_h": _guess_meridiem(h_raw),
                    "start_m": int((m.groups()[1] if len(m.groups()) > 1 else 0) or 0),
                    "end_h": None, "end_m": None,
                    "meridiem_guessed": True, "resolved_from": "single_guessed"}

    # Word defaults: "EOD", "morning", "evening", …
    for pat, h, mm in _TIME_WORD_DEFAULTS:
        if re.search(pat, low):
            return {"start_h": h, "start_m": mm, "end_h": None, "end_m": None,
                    "meridiem_guessed": False, "resolved_from": "word_default"}

    return None


def classify_scheduling_verb(line: str) -> str:
    """Return 'create_event' | 'create_task' | 'reschedule' | 'none'.

    create_event is tested first so a calendar location ('on calender') wins
    over the literal word 'task'. A line matching BOTH a task verb and an event
    verb resolves to create_event but is flagged 'verb_ambiguous' by the caller.
    """
    for verb in ("create_event", "create_task", "reschedule"):
        if any(rx.search(line) for rx in _SCHED_VERB_COMPILED[verb]):
            return verb
    return "none"


def _annotation_skip(raw_line: str) -> bool:
    if _STRIKE_RE.search(raw_line):
        return True
    return any(rx.search(raw_line) for rx in _ANNOTATION_SKIP_RES)


def _clean_summary(line: str) -> str:
    """Best-effort event/task title: strip bullets, checkboxes, HTML comments,
    and trailing instruction phrases. The /end-day skill refines this further.
    """
    s = _HTML_COMMENT_RE.sub("", line).strip()
    s = re.sub(r"^[-*•]\s+", "", s)
    s = re.sub(r"^\[\s?[xX ]?\s?\]\s+", "", s)
    s = re.sub(r"^#+\s+", "", s)
    # Drop common trailing instruction tails so the title stays clean.
    s = re.split(
        r"(?i)\b(set\s+on\s+calend|create\s+.*?\bevent\b|create\s+.*?\btask\b|"
        r"set\s+for\b|reminder\s+in|on\s+(the\s+)?calend|move\s+to|push\s+to)\b",
        s, maxsplit=1,
    )[0].strip(" -—:·")
    return s or _HTML_COMMENT_RE.sub("", line).strip(" -—:·")


def _annotation_confidence(verb: str, tinfo: dict | None,
                           date_from: str | None) -> float:
    base = 0.5
    if tinfo and not tinfo["meridiem_guessed"] and tinfo["resolved_from"] != "word_default":
        base += 0.20
    if date_from and date_from in ("explicit_iso", "relative_phrase"):
        base += 0.15
    if verb in ("create_event", "create_task"):
        base += 0.10
    if tinfo is None and verb == "create_event":
        base -= 0.15        # event with no time at all → needs a decision
    return max(0.0, min(1.0, round(base, 2)))


def extract_annotations(notes: str, anchor_date: date) -> list[dict[str, Any]]:
    """Extract imperative scheduling directives from daily-note text.

    Returns a list of intent dicts:
        {verb, suggested_summary, source_line, original_text,
         date_iso, date_resolved_from, start_iso, end_iso,
         meridiem_guessed, time_resolved_from, confidence, flags[]}
    Skips struck-through / synced / already-done lines. start_iso/end_iso are
    only set for create_event when both a date AND a time resolved; the caller
    runs the dedupe-against-calendar + trust gate before any write.
    """
    out: list[dict[str, Any]] = []
    for i, raw in enumerate(notes.splitlines(), start=1):
        raw_line = raw.rstrip("\n")
        stripped = raw_line.strip()
        if not stripped:
            continue
        # Skip briefing structure (not the operator's hand-typed directives):
        # markdown headers, table rows, blockquotes, horizontal rules, and
        # Top-3 score-rationale lines.
        if stripped[0] in "#|>" or stripped.startswith("---"):
            continue
        if re.search(r"—\s*score\s|\bscore\s+\*\*|\bconf[=:]\s*0", raw_line):
            continue
        if _annotation_skip(raw_line):
            continue
        work = _HTML_COMMENT_RE.sub("", raw_line)
        verb = classify_scheduling_verb(work)
        if verb == "none":
            continue

        date_iso, date_from = _resolve_due(work, anchor_date)
        tinfo = _resolve_time(work)

        flags: list[str] = []
        # Ambiguity: matches both an event verb and a task verb.
        if verb == "create_event" and any(
            rx.search(work) for rx in _SCHED_VERB_COMPILED["create_task"]
        ) and not any(
            rx.search(work) for rx in _SCHED_VERB_COMPILED["create_event"]
            if "calend" in rx.pattern or "call?ender" in rx.pattern
        ):
            flags.append("verb_ambiguous")

        start_iso = end_iso = None
        if tinfo:
            d = date_iso or anchor_date.isoformat()
            sd = date.fromisoformat(d)
            start_dt = datetime(sd.year, sd.month, sd.day,
                                tinfo["start_h"], tinfo["start_m"])
            if tinfo["end_h"] is not None:
                end_dt = datetime(sd.year, sd.month, sd.day,
                                  tinfo["end_h"], tinfo["end_m"])
            else:
                end_dt = start_dt + timedelta(minutes=60)
            start_iso = start_dt.isoformat()
            end_iso = end_dt.isoformat()
            if tinfo["meridiem_guessed"]:
                flags.append("meridiem_guessed")
        if verb == "create_event" and not date_iso:
            flags.append("no_explicit_date_assumed_note_date")
        if verb == "create_event" and tinfo is None:
            flags.append("no_time_resolved")

        conf = _annotation_confidence(verb, tinfo, date_from)
        if conf < CONFIDENCE_THRESHOLD:
            flags.append("low_confidence")

        out.append({
            "verb": verb,
            "suggested_summary": _clean_summary(raw_line),
            "source_line": i,
            "original_text": raw_line.strip(),
            "date_iso": date_iso,
            "date_resolved_from": date_from,
            "start_iso": start_iso,
            "end_iso": end_iso,
            "meridiem_guessed": bool(tinfo and tinfo["meridiem_guessed"]),
            "time_resolved_from": tinfo["resolved_from"] if tinfo else None,
            "confidence": conf,
            "flags": flags,
        })
    return out


# ---------------------------------------------------------------------------
# Confidence rubric
# ---------------------------------------------------------------------------

def compute_confidence(
    indicators_matched: int,
    matched_terms: list[str],
    has_named_entity: bool,
    has_concrete_due: bool,
    matches_business_tag: bool,
) -> float:
    """Confidence rubric per /capture-meeting Step 4.

    Anchored on the simple form from the T3a spec:
        conf = 0.5 + 0.15 * indicators_matched + 0.10 * has_named_entity
             + 0.10 * has_concrete_due + 0.05 * matches_business_tag

    Strong indicator terms get a small bump (cap at 1.0).
    """
    if indicators_matched == 0:
        return 0.0
    base = 0.5
    base += 0.15 * min(indicators_matched, 3)
    if has_named_entity:
        base += 0.10
    if has_concrete_due:
        base += 0.10
    if matches_business_tag:
        base += 0.05
    if any(t in STRONG_INDICATORS for t in matched_terms):
        base += 0.05
    return max(0.0, min(1.0, base))


# ---------------------------------------------------------------------------
# Idempotency (shell out to action_id.sh)
# ---------------------------------------------------------------------------

def _generate_action_id(
    meeting_key: str, anchor_date: str, payload: str
) -> str:
    """Shell out to scripts/action_id.sh to generate the action_id."""
    if not ACTION_ID_SCRIPT.is_file():
        # Fallback: replicate the script's hash so callers can still run when
        # bash is unavailable. Format is documented in scripts/action_id.sh.
        h = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:8]
        return f"capture-meeting:{meeting_key}:{anchor_date}:{h}"

    try:
        result = subprocess.run(
            ["bash", str(ACTION_ID_SCRIPT), "generate",
             "capture-meeting", meeting_key, anchor_date, payload],
            check=False, capture_output=True, text=True, timeout=15,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        h = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:8]
        return f"capture-meeting:{meeting_key}:{anchor_date}:{h}"

    if result.returncode != 0 or not result.stdout.strip():
        h = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:8]
        return f"capture-meeting:{meeting_key}:{anchor_date}:{h}"
    return result.stdout.strip()


def _check_action_id_applied(action_id: str) -> bool:
    """True if action_id.sh check exits 0 (already applied)."""
    if not ACTION_ID_SCRIPT.is_file():
        # Best-effort: look directly at .context/applied/<aid>.json
        fname = action_id.replace(":", "_") + ".json"
        return (REPO_ROOT / ".context" / "applied" / fname).is_file()
    try:
        result = subprocess.run(
            ["bash", str(ACTION_ID_SCRIPT), "check", action_id],
            check=False, capture_output=True, text=True, timeout=15,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        fname = action_id.replace(":", "_") + ".json"
        return (REPO_ROOT / ".context" / "applied" / fname).is_file()
    return result.returncode == 0


# ---------------------------------------------------------------------------
# Core parse pipeline
# ---------------------------------------------------------------------------

def categorize_line(
    line: str,
    line_no: int,
    attendees: list[str],
    business_tag: str,
    anchor_date: date,
    config: Config,
) -> dict[str, Any]:
    """Categorize a single line. Returns a dict of all the output fields
    EXCEPT action_id + skip_idempotent (those are filled in by the caller
    so the subprocess calls happen in one place).
    """
    # Score each routing category.
    scores: list[tuple[str, int, list[str]]] = []
    for routing_key, cat_label in ROUTING_KEY_TO_CATEGORY.items():
        rules = config.routing.get(routing_key, {}) or {}
        inds = rules.get("indicators", []) or []
        n, matched = _match_indicators(line, inds)
        if n > 0:
            scores.append((cat_label, n, matched))

    primary_cat = "uncategorized"
    matched_terms: list[str] = []
    indicators_matched = 0
    secondary_hint_cat: str | None = None

    if scores:
        scores.sort(key=lambda t: t[1], reverse=True)
        primary_cat, indicators_matched, matched_terms = scores[0]
        if len(scores) > 1 and scores[1][1] >= 1 and scores[1][0] != primary_cat:
            secondary_hint_cat = scores[1][0]

    # Owner + due
    owner, owner_from = _resolve_owner(line, attendees)
    due, due_from = _resolve_due(line, anchor_date)

    # Confidence inputs
    named = _has_named_entity(line, attendees)
    biz_match = _matches_business_tag(line, business_tag, config.calendar_business_keywords)
    confidence = compute_confidence(
        indicators_matched=indicators_matched,
        matched_terms=matched_terms,
        has_named_entity=named,
        has_concrete_due=due is not None,
        matches_business_tag=biz_match,
    )

    # Confidence threshold (AAC GROUNDED)
    if confidence < CONFIDENCE_THRESHOLD:
        primary_cat = "uncategorized"

    # Secondary hint: prefer a routing-category alternative, else surface a
    # business-tag hint (E1 line-override pattern).
    secondary_hint: str | None = secondary_hint_cat
    if secondary_hint is None:
        secondary_hint = _infer_secondary_hint(
            line, business_tag, config.calendar_business_keywords
        )

    return {
        "category": primary_cat,
        "confidence": round(confidence, 2),
        "source_line": line_no,
        "source_text": line,
        "owner": owner,
        "owner_resolved_from": owner_from if primary_cat != "uncategorized" else "unresolved",
        "due": due,
        "due_resolved_from": due_from,
        "secondary_hint": secondary_hint,
    }


def parse_notes(
    notes: str,
    *,
    anchor_date: date,
    meeting_key: str,
    business_tag: str | None,
    attendees: list[str],
    config: Config,
) -> list[dict[str, Any]]:
    """Parse meeting notes into a list of categorized item dicts.

    Pipeline matches /capture-meeting Steps 4 + 4.5:
      1. Split into source lines (preserving line numbers).
      2. Categorize each.
      3. Apply confidence threshold (< 0.70 → uncategorized).
      4. Generate action_id (subprocess) + check idempotency (subprocess).
    """
    if business_tag is None or business_tag.strip() == "":
        business_tag = _infer_business_tag_from_text(
            notes, config.calendar_business_keywords
        )
    if business_tag not in VALID_BUSINESS_TAGS:
        business_tag = "other"

    out: list[dict[str, Any]] = []
    anchor_iso = anchor_date.isoformat()
    for line_no, line in _split_lines(notes):
        item = categorize_line(
            line=line,
            line_no=line_no,
            attendees=attendees,
            business_tag=business_tag,
            anchor_date=anchor_date,
            config=config,
        )
        payload = (
            f"{item['category']}|{item['source_text']}|"
            f"{item.get('owner') or ''}|{item.get('due') or ''}"
        )
        aid = _generate_action_id(meeting_key, anchor_iso, payload)
        item["action_id"] = aid
        item["skip_idempotent"] = _check_action_id_applied(aid)
        out.append(item)
    return out


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

PARITY_FIXTURE = """\
- Decided to onboard Example Account to Product this week
- Tell Person E to follow up with Contact Person C by Friday
- Spoke with Contact Person F about credentialing for Sales
- Random observation: office intake forms are terrible
"""


def _self_test() -> int:
    failures: list[str] = []

    # 1. Banner strip — banner present
    banner = b"Using keyring backend: keyring\n"
    payload = b'{"hello": "world"}'
    cleaned = strip_gws_keyring_banner(banner + payload)
    try:
        obj = json.loads(cleaned)
        if obj != {"hello": "world"}:
            failures.append("banner-strip: parsed object mismatch")
    except json.JSONDecodeError as e:
        failures.append(f"banner-strip: JSONDecodeError after strip: {e}")

    # 2. Banner strip — no banner (no-op)
    cleaned2 = strip_gws_keyring_banner(payload)
    if cleaned2 != payload:
        failures.append("banner-strip: no-op case altered bytes")

    # 3. Banner strip — variant keyring name
    banner_variant = b"Using keyring backend: SecretService\n"
    cleaned3 = strip_gws_keyring_banner(banner_variant + payload)
    try:
        json.loads(cleaned3)
    except json.JSONDecodeError as e:
        failures.append(f"banner-strip: variant name failed: {e}")

    # 4. Banner-prefixed payload WITHOUT strip should fail to parse (asserts
    #    the strip is load-bearing).
    try:
        json.loads(banner + payload)
        failures.append("banner-strip: raw banner+json unexpectedly parsed")
    except json.JSONDecodeError:
        pass

    # 5. Parity fixture: parse it and verify expected categories.
    routing_path = DEFAULT_CONFIG_DIR / "routing-rules.yaml"
    sources_path = DEFAULT_CONFIG_DIR / "sources.yaml"
    try:
        cfg = load_config(routing_path, sources_path)
    except Exception as e:
        failures.append(f"parity: config load failed: {e}")
        cfg = None  # type: ignore

    parity_summary = "skipped (config unavailable)"
    if cfg is not None:
        items = parse_notes(
            PARITY_FIXTURE,
            anchor_date=date(2026, 5, 19),
            meeting_key="parity-test-001",
            business_tag="product",
            attendees=["the operator", "Person E"],
            config=cfg,
        )
        if len(items) != 4:
            failures.append(f"parity: expected 4 items, got {len(items)}")
        expected = {
            1: "decision",       # "Decided to onboard..."
            2: "task",           # "Tell Person E to follow up..."
            3: "contact",        # "Spoke with Contact Person F about credentialing..."
            4: "learning",       # "Random observation..."
        }
        seen = {it["source_line"]: it["category"] for it in items}
        matches = 0
        divergences: list[str] = []
        for ln, exp in expected.items():
            got = seen.get(ln)
            if got == exp:
                matches += 1
            else:
                divergences.append(f"line {ln}: expected {exp}, got {got}")
        parity_summary = f"{matches}/{len(expected)} items categorized identically"
        if divergences:
            parity_summary += " — divergences: " + "; ".join(divergences)
        # Confidence threshold check: any uncategorized result must have conf < 0.70
        for it in items:
            if it["category"] == "uncategorized" and it["confidence"] >= CONFIDENCE_THRESHOLD:
                failures.append(
                    f"conf-threshold violated: line {it['source_line']} "
                    f"uncategorized with conf={it['confidence']}"
                )
        # action_id format: capture-meeting:<key>:<date>:<8hex>
        aid_re = re.compile(r"^capture-meeting:[^:]+:\d{4}-\d{2}-\d{2}:[0-9a-f]{8}$")
        for it in items:
            if not aid_re.match(it["action_id"]):
                failures.append(f"action_id format bad: {it['action_id']}")

    # 6. Annotation extraction (added 2026-05-29).
    anno_fixture = (
        "- [ ] Bill for trish handle 9am tomm set on calender\n"
        "- Followup with julie tomm task set for 10 am for hv portal.\n"
        "- [ ] Person X credentialing ceate 11am task on calender\n"
        "- [ ] 15:00 Union NJ — Vendor A close set for 4pm tomm\n"
        "- [ ] Contact Person G postpone until next wednsay 12pm creasae calender event\n"
        "- [ ] Call Raghda move to next tuesday\n"
        "- this line is just prose with no scheduling directive at all\n"
        "## A header line that mentions calendar should be skipped\n"
        "- [ ] already done item <!-- sched-done:cal:abc12345 2026-05-28 -->\n"
    )
    intents = extract_annotations(anno_fixture, date(2026, 5, 28))
    by_line = {it["source_line"]: it for it in intents}

    def _expect(line_no, verb, start_iso):
        it = by_line.get(line_no)
        if it is None:
            failures.append(f"annotation: line {line_no} not extracted")
            return
        if it["verb"] != verb:
            failures.append(f"annotation L{line_no}: verb {it['verb']} != {verb}")
        if start_iso is not None and it["start_iso"] != start_iso:
            failures.append(f"annotation L{line_no}: start {it['start_iso']} != {start_iso}")

    _expect(1, "create_event", "2026-05-29T09:00:00")   # 9am tomm
    _expect(2, "create_event", "2026-05-29T10:00:00")   # 10 am tomm
    _expect(3, "create_event", "2026-05-28T11:00:00")   # 11am task on calender → event (no date → note date)
    _expect(4, "create_event", "2026-05-29T16:00:00")   # set for 4pm tomm
    _expect(5, "create_event", "2026-06-03T12:00:00")   # next wednsay 12pm
    _expect(6, "reschedule", None)                       # move to next tuesday
    if 7 in by_line:
        failures.append("annotation: prose line 7 wrongly extracted")
    if 8 in by_line:
        failures.append("annotation: header line 8 wrongly extracted")
    if 9 in by_line:
        failures.append("annotation: sched-done line 9 not skipped")
    anno_summary = f"{len([l for l in (1,2,3,4,5,6) if l in by_line])}/6 directives extracted"

    print(f"parity_check: {parity_summary}")
    print(f"annotation_check: {anno_summary}")
    if failures:
        print("FAIL")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("PASS")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="capture_meeting_parse.py",
        description=(
            "Parse + categorize + idempotency-check meeting notes. "
            "Extracted from /capture-meeting Steps 4 + 4.5."
        ),
    )
    src = p.add_mutually_exclusive_group()
    src.add_argument("--notes-file", type=Path, help="Path to a meeting notes file")
    src.add_argument("--stdin", action="store_true", help="Read notes from stdin")

    p.add_argument("--mode", choices=("categorize", "annotations"),
                   default="categorize",
                   help="categorize = meeting-note routing (default); "
                        "annotations = extract inline scheduling directives "
                        "(create_event/create_task/reschedule) from daily-note text")
    p.add_argument("--date", help="Anchor date YYYY-MM-DD (REQUIRED for normal runs)")
    p.add_argument("--meeting-key", help="Unique meeting key (URL hash, slug, etc.)")
    p.add_argument("--business-tag", choices=list(VALID_BUSINESS_TAGS),
                   default=None,
                   help="Business tag; falls back to keyword inference if omitted")
    p.add_argument("--attendees", default="",
                   help="Comma-separated attendee names")
    p.add_argument("--config-dir", type=Path, default=None,
                   help="Override the default config/ directory")
    p.add_argument("--routing-config", type=Path, default=None,
                   help="Override path to routing-rules.yaml")
    p.add_argument("--sources-config", type=Path, default=None,
                   help="Override path to sources.yaml")
    p.add_argument("--self-test", action="store_true",
                   help="Run built-in self-test (banner-strip + parity) and exit")
    return p


def main(argv: list[str] | None = None) -> int:
    # Force UTF-8 stdout so emoji / em-dashes in notes don't crash on Windows cp1252.
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.self_test:
        return _self_test()

    # Validate required args for normal runs
    if not args.date:
        parser.error("--date is required (use YYYY-MM-DD)")
    if args.mode == "categorize" and not args.meeting_key:
        parser.error("--meeting-key is required (mode=categorize)")
    if not args.notes_file and not args.stdin:
        parser.error("one of --notes-file or --stdin is required")

    try:
        anchor_date = datetime.strptime(args.date, "%Y-%m-%d").date()
    except ValueError:
        print(f"error: --date '{args.date}' is not YYYY-MM-DD", file=sys.stderr)
        return 1

    # --- annotations mode: extract inline scheduling directives, no config needed
    if args.mode == "annotations":
        if args.notes_file:
            try:
                notes = args.notes_file.read_text(encoding="utf-8")
            except OSError as e:
                print(f"error: failed reading {args.notes_file}: {e}", file=sys.stderr)
                return 1
        else:
            notes = sys.stdin.read()
        if not notes.strip():
            print("error: empty notes input", file=sys.stderr)
            return 2
        intents = extract_annotations(notes, anchor_date)
        json.dump(intents, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0

    # Resolve config paths
    config_dir = args.config_dir or DEFAULT_CONFIG_DIR
    routing_path = args.routing_config or (config_dir / "routing-rules.yaml")
    sources_path = args.sources_config or (config_dir / "sources.yaml")

    try:
        cfg = load_config(routing_path, sources_path)
    except (FileNotFoundError, ValueError, yaml.YAMLError) as e:
        print(f"error: config load failed: {e}", file=sys.stderr)
        return 1

    # Read notes
    if args.notes_file:
        try:
            notes = args.notes_file.read_text(encoding="utf-8")
        except FileNotFoundError:
            print(f"error: notes file not found: {args.notes_file}", file=sys.stderr)
            return 1
        except OSError as e:
            print(f"error: failed reading {args.notes_file}: {e}", file=sys.stderr)
            return 1
    else:
        notes = sys.stdin.read()

    if not notes.strip():
        print("error: empty notes input", file=sys.stderr)
        return 2

    attendees = [a.strip() for a in args.attendees.split(",") if a.strip()]

    items = parse_notes(
        notes,
        anchor_date=anchor_date,
        meeting_key=args.meeting_key,
        business_tag=args.business_tag,
        attendees=attendees,
        config=cfg,
    )

    json.dump(items, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
