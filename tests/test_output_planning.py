import pathlib
import re
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))

import output_planning as op  # noqa: E402


def _sample_outputs():
    return [
        op.DailyOutput(
            title="Reach out to Healthix",
            owner="Nestmate",
            source_refs=[op.SourceRef("gtask", "abc123")],
            status="Not started",
        ),
        op.DailyOutput(
            title="MDland negotiation",
            owner="United IPA",
            source_refs=[op.SourceRef("notion", "343a3158")],
            status="In progress",
        ),
        op.DailyOutput(
            title="Buy RDDT",
            owner="Other / Personal",
            source_refs=[op.SourceRef("derived")],
            status="Not started",
        ),
    ]


class GroupingTests(unittest.TestCase):
    def test_grouping_defaults_to_one_to_one(self):
        outs = _sample_outputs()
        grouped = op.group_outputs(outs)  # default max_children=1
        self.assertEqual(len(grouped), len(outs))
        for g in grouped:
            self.assertEqual(len(g.source_refs), 1)

    def test_preaggregated_output_is_split_under_default_guard(self):
        agg = op.DailyOutput(
            title="Two anchors fused",
            owner="Nestmate",
            source_refs=[op.SourceRef("gtask", "a1"), op.SourceRef("notion", "n2")],
        )
        grouped = op.group_outputs([agg])  # max_children=1 -> must split
        self.assertEqual(len(grouped), 2)
        self.assertTrue(all(len(g.source_refs) == 1 for g in grouped))

    def test_max_children_below_one_rejected(self):
        with self.assertRaises(ValueError):
            op.group_outputs(_sample_outputs(), max_children=0)


class MarkerPlacementTests(unittest.TestCase):
    def test_markers_land_on_non_indented_checkbox_lines(self):
        """Contract #1: every marker line is a column-0 `- [ ] ` line."""
        md = op.render_output_plan_markdown(_sample_outputs())
        marker_pat = re.compile(r"<!--\s*(gtask|notion|derived):?")
        found_marker = False
        for line in md.splitlines():
            if marker_pat.search(line):
                found_marker = True
                # Must be non-indented (no leading whitespace) AND a checkbox line.
                self.assertEqual(line, line.lstrip(), f"marker line indented: {line!r}")
                self.assertTrue(
                    re.match(r"^- \[ \]\s+", line),
                    f"marker not on a top-level checkbox: {line!r}",
                )
        self.assertTrue(found_marker, "expected at least one marker line")

    def test_derived_marker_has_no_id(self):
        md = op.render_output_plan_markdown(_sample_outputs())
        self.assertIn("<!-- derived -->", md)


class RenderShapeTests(unittest.TestCase):
    def test_log_top3_emits_exact_heading(self):
        """Contract #2: heading byte-for-byte `## Top 3 Outcomes`."""
        log = op.render_log_top3(_sample_outputs())
        self.assertTrue(log.startswith("## Top 3 Outcomes\n"))
        self.assertIn("1. Reach out to Healthix", log)
        self.assertIn("2. MDland negotiation", log)
        self.assertIn("3. Buy RDDT", log)

    def test_log_top3_caps_at_three(self):
        outs = _sample_outputs() + [
            op.DailyOutput(title="Fourth", owner="Other", source_refs=[op.SourceRef("derived")])
        ]
        log = op.render_log_top3(outs)
        self.assertNotIn("Fourth", log)

    def test_phone_first_bullets_no_wide_table(self):
        md = op.render_output_plan_markdown(
            _sample_outputs(),
            portfolio_pulse="Nestmate has the tightest provider-outreach constraint today.",
            day_type="desk day",
        )
        # No markdown table pipes anywhere.
        self.assertNotIn("|", md)
        # Section heading present and bullets present.
        self.assertTrue(md.startswith("## Today — Ship These 3\n"))
        self.assertIn("- [ ] Reach out to Healthix", md)


class EdgeCaseGuardTests(unittest.TestCase):
    def test_empty_id_renders_no_marker(self):
        # SourceRef('gtask','') must NOT emit `<!-- gtask: -->` (empty-id write).
        self.assertEqual(op.SourceRef("gtask", "").marker(), "")
        self.assertEqual(op.SourceRef("notion", "").marker(), "")

    def test_newline_in_title_stays_on_one_checkbox_line(self):
        out = op.DailyOutput(
            title="Call clinic\nabout panel",
            owner="Nestmate",
            source_refs=[op.SourceRef("gtask", "xyz789")],
        )
        md = op.render_output_plan_markdown([out])
        marker_lines = [ln for ln in md.splitlines() if "<!--" in ln]
        # marker is on exactly one non-indented checkbox line (contract #1).
        self.assertEqual(len(marker_lines), 1)
        self.assertEqual(marker_lines[0], marker_lines[0].lstrip())
        self.assertRegex(marker_lines[0], r"^- \[ \]\s+")

    def test_render_caps_at_three_outputs(self):
        four = _sample_outputs() + [
            op.DailyOutput(title="Fourth", owner="Other", source_refs=[op.SourceRef("derived")])
        ]
        md = op.render_output_plan_markdown(four)
        self.assertNotIn("Fourth", md)
        self.assertEqual(len([ln for ln in md.splitlines() if ln.startswith("- [ ] ")]), 3)

    def test_empty_outputs_renders_heading_without_crash(self):
        # Degraded morning run (no sources): heading survives, no items, no crash.
        self.assertTrue(op.render_log_top3([]).startswith("## Top 3 Outcomes\n"))
        self.assertTrue(op.render_output_plan_markdown([]).startswith("## Today — Ship These 3"))


if __name__ == "__main__":
    unittest.main()
