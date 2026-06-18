#!/usr/bin/env python3
"""High-output /start-day planning primitives (Phase 1 / T1 + E1 minimal cut).

CONTRACT (this module's renderers exist to preserve, verbatim):

  Contract #1 — Source markers on NON-indented checkbox lines.
    Every rendered line that carries a `<!-- gtask:ID -->` / `<!-- notion:ID -->`
    / `<!-- derived -->` marker MUST be a top-level (column-0) `- [ ] ` line.
    `end_day_orchestrator.extract_checked_source_actions` only reads marked
    `^- \\[[xX]\\]\\s+` lines; a marker absorbed onto an indented sub-bullet of a
    `DailyOutput` parent silently drops that source's sync write. Therefore the
    grouping function DEFAULTS TO 1:1 (one source item -> one output) and carries
    a `max_children=1` guard in shadow mode so markers never aggregate.

  Contract #2 — `## Top 3 Outcomes` heading is exact and lives in `logs/{DATE}.md`.
    `render_log_top3()` emits that heading byte-for-byte. end-day reads it from the
    log file (not the daily note). Drift the heading -> end-day reports 0/3.

This is the ponytail-minimal cut: only the dataclasses, grouping, and the two
renderers needed to prove the roundtrip. OutputScorecard, CalendarBlockProposal,
real_vs_tracked_delta and earliest_start_hint are intentionally OUT of scope
(see TASKS.md cut-list).
"""
from __future__ import annotations

import dataclasses
import re
from typing import List, Optional

# A `done_when` is "lazy" (rejected) if it is empty or, case-insensitive and
# anchored at the START, begins with one of these continuation verbs. These name
# an activity ("work on Healthix"), not a shippable done-state ("Healthix proposal
# sent + decision captured"). The render guard refuses them so the SELECTION layer
# is forced to supply a real done-state, not a reordered task dump.
_LAZY_DONE_WHEN = re.compile(
    r"^\s*(work on|make progress on|follow up on|continue|keep working on)\b",
    re.IGNORECASE,
)

# Marker systems that end_day_orchestrator.extract_checked_source_actions reads.
# `cal` and other systems render WITHOUT a sync marker (display-only) so they are
# never mistaken for a syncable source by the end-day parser.
_MARKER_SYSTEMS = {"gtask", "notion", "derived"}


@dataclasses.dataclass(frozen=True)
class SourceRef:
    """A pointer back to the originating system + id.

    `system` is one of: gtask, notion, derived, cal. Only the first three render
    as `<!-- system:id -->` HTML-comment markers the end-day parser consumes;
    `derived` renders as a bare `<!-- derived -->` (no id, like the orchestrator
    test fixture). `cal` is display-only (no marker).
    """

    system: str
    id: str = ""

    def marker(self) -> str:
        """Render the HTML-comment marker, or '' for non-sync systems."""
        if self.system not in _MARKER_SYSTEMS:
            return ""
        if self.system == "derived":
            return "<!-- derived -->"
        if not self.id:
            # ponytail: no target id -> emit no marker (degrades to a
            # manual_completion) rather than `<!-- gtask: -->`, which the end-day
            # parser would route to a sync write with an empty source_id.
            return ""
        return f"<!-- {self.system}:{self.id} -->"


@dataclasses.dataclass
class DailyOutput:
    """One of the 3 outputs to ship today.

    A DailyOutput maps to exactly one source item in shadow mode (1:1 grouping),
    so `source_refs` holds a single SourceRef. The list shape is kept so a future,
    explicitly-tested aggregation mode can attach >1 child WITHOUT changing the
    type — but the renderer still emits each marker on its own top-level checkbox.
    """

    title: str
    owner: str
    source_refs: List[SourceRef] = dataclasses.field(default_factory=list)
    status: str = "Not started"
    # The shippable done-state for this output. Required at render time: an empty
    # or "lazy" (work on / follow up on / continue ...) value makes
    # render_output_plan_markdown raise. Defaulted to "" so the dataclass stays
    # valid for partially-built fixtures, but the renderer is the enforcement point.
    done_when: str = ""


@dataclasses.dataclass
class DelegationAsk:
    """A first-class 'delegated counts as shipped' ask (minimal schema).

    Minimal per spec change #3: delegatee, ask, date, source_ref. confirmation_state
    and richer fields are deferred to the engine phase.
    """

    delegatee: str
    ask: str
    date: str
    source_ref: Optional[SourceRef] = None


def group_outputs(
    source_items: List[DailyOutput],
    max_children: int = 1,
) -> List[DailyOutput]:
    """Group source items into outputs. DEFAULTS TO 1:1 (contract #1).

    In shadow mode `max_children=1` is the guard: every source item stays its own
    output so no marker is ever folded onto an indented sub-bullet. The function is
    pure and returns a new list; with the default it is effectively identity, but
    it ALSO splits any pre-aggregated output whose `source_refs` exceeds
    `max_children` back into one-output-per-ref, which is the actual safety
    behavior the contract needs.
    """
    if max_children < 1:
        raise ValueError("max_children must be >= 1")
    grouped: List[DailyOutput] = []
    for item in source_items:
        refs = item.source_refs or []
        if len(refs) <= max_children:
            grouped.append(item)
            continue
        # Split a pre-aggregated output so markers never share a parent bullet.
        for ref in refs:
            grouped.append(
                DailyOutput(
                    title=item.title,
                    owner=item.owner,
                    source_refs=[ref],
                    status=item.status,
                )
            )
    return grouped


def _output_checkbox_lines(output: DailyOutput) -> List[str]:
    """Render the top-level `- [ ] ` checkbox line(s) for one output.

    ONE marker per line (contract #1 + the end-day parser only `re.search`es a
    single marker per line, so two markers on one line would silently drop all
    but the first). With 1:1 grouping that is one line; a multi-ref output that
    bypassed `group_outputs` still renders one column-0 checkbox PER ref here,
    never two markers sharing a line and never an indented sub-bullet.
    """
    # ponytail: a newline in the title would push the marker onto a continuation
    # line that is not a `- [ ]` checkbox -> contract #1 break. Flatten it.
    title = output.title.replace("\n", " ")
    refs = output.source_refs or [None]
    lines: List[str] = []
    for ref in refs:
        marker = ref.marker() if ref is not None else ""
        line = f"- [ ] {title}"
        if marker:
            line = f"{line} {marker}"
        lines.append(line)
    return lines


def render_output_plan_markdown(
    outputs: List[DailyOutput],
    portfolio_pulse: str = "",
    day_type: str = "",
) -> str:
    """Render the new '## Today — Ship These 3' shadow section.

    Phone-first compact bullets — NO wide tables. Every line carrying a sync
    marker is a NON-INDENTED `- [ ] ` line (contract #1). Context (pulse, day type,
    owner, status) goes on separate display lines that carry no marker, so the
    end-day parser never sees them as syncable.
    """
    # Guard: every rendered output MUST carry a real done-state. This forces the
    # selection layer to commit to a shippable result, not a reordered task dump.
    for output in outputs[:3]:
        if not output.done_when.strip() or _LAZY_DONE_WHEN.match(output.done_when):
            raise ValueError(
                f"output {output.title!r} has a lazy or empty done_when "
                f"({output.done_when!r}); supply a shippable done-state "
                f"(e.g. 'proposal sent + decision captured'), not an activity."
            )

    lines: List[str] = ["## Today — Ship These 3", ""]
    if portfolio_pulse:
        lines.append(f"_Portfolio Pulse:_ {portfolio_pulse}")
    if day_type:
        lines.append(f"_Day type:_ {day_type}")
    if portfolio_pulse or day_type:
        lines.append("")

    # Cap at 3 so the "Ship These 3" heading is always true and the two
    # renderers stay in sync (render_log_top3 also slices [:3]).
    for output in outputs[:3]:
        # One column-0 checkbox per source ref; one marker per line.
        lines.extend(_output_checkbox_lines(output))
        # Compact context lines are indented and marker-free (display only).
        # done_when on the INDENTED display line, never on the column-0 checkbox
        # (contract #1). The guard above guarantees done_when is non-empty here.
        meta = f"  {output.owner} · done when: {output.done_when}"
        lines.append(meta)
    return "\n".join(lines).rstrip() + "\n"


def render_log_top3(outputs: List[DailyOutput]) -> str:
    """Render the `## Top 3 Outcomes` section for `logs/{DATE}.md` (contract #2).

    Heading is exact. Each outcome is a numbered line. This is what end-day reads
    from the LOG file, so it stays simple and parser-stable.
    """
    lines: List[str] = ["## Top 3 Outcomes", ""]
    for i, output in enumerate(outputs[:3], start=1):
        lines.append(f"{i}. {output.title} — {output.owner}")
    return "\n".join(lines).rstrip() + "\n"
