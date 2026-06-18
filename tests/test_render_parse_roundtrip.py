"""E2E contract gate (Phase 2 / E3).

Proves the new '## Today — Ship These 3' shadow section does NOT drop or alter any
source-sync action that end-day's REAL parser extracts. Imports the real
`end_day_orchestrator.extract_checked_source_actions` — no stubbed parser. If
start-day's renderer and end-day's parser ever drift, this fails.

Two assertions:
  1. Golden render-pair: the old-format note and the new (mixed-format) note yield
     an IDENTICAL extracted action set (same {type, source_id} per checked item).
     This is the contract-#1 proof — appending the shadow section changes nothing
     the parser reads.
  2. Render -> parse: feed a renderer-produced section (with checked markers) to
     the real parser and confirm the markers survive as top-level checkbox lines.
"""
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import end_day_orchestrator as edo  # noqa: E402  (the REAL parser)
import output_planning as op  # noqa: E402

FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures"


def _action_signature(actions):
    """Normalize extracted actions to a comparable set of (type, source_id, title)."""
    return sorted(
        (a["type"], a.get("source_id"), a["title"]) for a in actions
    )


class RenderParseRoundtripTests(unittest.TestCase):
    def test_old_and_new_format_yield_identical_action_set(self):
        old_text = (FIXTURES / "old_format_note.md").read_text(encoding="utf-8")
        new_text = (FIXTURES / "new_format_note.md").read_text(encoding="utf-8")

        old_actions = edo.extract_checked_source_actions(old_text)
        new_actions = edo.extract_checked_source_actions(new_text)

        # Contract #1: the appended shadow section (unchecked planning markers)
        # adds zero phantom actions and drops none.
        self.assertEqual(
            _action_signature(old_actions),
            _action_signature(new_actions),
            "new-format note altered the extracted action set",
        )

    def test_expected_three_syncable_actions_present(self):
        new_text = (FIXTURES / "new_format_note.md").read_text(encoding="utf-8")
        actions = edo.extract_checked_source_actions(new_text)
        sig = _action_signature(actions)
        self.assertEqual(len(sig), 3)
        self.assertIn(("gtask_complete", "abc123", "Reach out to Healthix"), sig)
        self.assertIn(("notion_done", "343a3158", "MDland negotiation"), sig)
        # derived -> manual_completion with no source_id
        self.assertIn(("manual_completion", None, "Buy RDDT"), sig)

    def test_renderer_output_is_parseable_when_checked(self):
        """Render via the real renderer, check the boxes, parse with the real parser."""
        outputs = [
            op.DailyOutput(
                title="Reach out to Healthix",
                owner="Nestmate",
                source_refs=[op.SourceRef("gtask", "abc123")],
            ),
            op.DailyOutput(
                title="MDland negotiation",
                owner="United IPA",
                source_refs=[op.SourceRef("notion", "343a3158")],
            ),
            op.DailyOutput(
                title="Buy RDDT",
                owner="Other / Personal",
                source_refs=[op.SourceRef("derived")],
            ),
        ]
        section = op.render_output_plan_markdown(outputs)
        # Simulate Aaron checking the boxes off: the marker-bearing lines are
        # top-level, so flipping `- [ ]` -> `- [x]` makes them parser-visible.
        checked = section.replace("- [ ] ", "- [x] ")
        actions = edo.extract_checked_source_actions(checked)
        sig = _action_signature(actions)

        self.assertEqual(len(sig), 3)
        self.assertIn(("gtask_complete", "abc123", "Reach out to Healthix"), sig)
        self.assertIn(("notion_done", "343a3158", "MDland negotiation"), sig)
        self.assertIn(("manual_completion", None, "Buy RDDT"), sig)


class ContractEnforcementTests(unittest.TestCase):
    """The two Codex [P1] findings, regression-guarded."""

    def test_multi_ref_output_renders_one_marker_per_line_no_drop(self):
        # [P1] #2: an aggregated output (2 refs) must NOT put both markers on one
        # line, or the parser's single re.search drops the second sync action.
        out = op.DailyOutput(
            title="Two-system task",
            owner="Nestmate",
            source_refs=[op.SourceRef("gtask", "g111"), op.SourceRef("notion", "n222")],
        )
        section = op.render_output_plan_markdown([out])
        marker_lines = [ln for ln in section.splitlines() if "<!--" in ln]
        # exactly one marker per line, each a column-0 checkbox.
        self.assertEqual(len(marker_lines), 2)
        for ln in marker_lines:
            self.assertEqual(ln, ln.lstrip())
            self.assertEqual(ln.count("<!--"), 1)
        # both survive the real parser when checked.
        actions = edo.extract_checked_source_actions(section.replace("- [ ] ", "- [x] "))
        ids = sorted(a.get("source_id") for a in actions)
        self.assertEqual(ids, ["g111", "n222"])

    def test_indented_checked_marker_is_not_synced(self):
        # [P1] #1: an indented sub-bullet with a marker must NOT be treated as a
        # sync completion (contract #1 is now enforced by the parser itself).
        note = (
            "## Today — Ship These 3\n\n"
            "- [x] Top level task <!-- gtask:real -->\n"
            "  - [x] Indented child <!-- gtask:shouldskip -->\n"
        )
        actions = edo.extract_checked_source_actions(note)
        ids = [a.get("source_id") for a in actions]
        self.assertIn("real", ids)
        self.assertNotIn("shouldskip", ids)


if __name__ == "__main__":
    unittest.main()
