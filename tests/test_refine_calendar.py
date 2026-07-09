"""Tests for scripts/refine_calendar.py — morning runner/wiring.

No Google API calls here; calendar input is injected.
"""
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))

import refine_calendar as rc  # noqa: E402


DAILY = """# Daily Briefing — 2026-06-22

_Day type: field — use meetings to create decisions._

## Today — Ship These 3
- [ ] Vendor A x Operations + DocPro — convert 3-week touchbase into pilot handoff
  Operations / Product · Calendar · done when: Vendor A status captured + handoff owner/date set
- [ ] Example Contact Thomas — advance Dr. Miao Huang referral cadence <!-- gtask:abc123 -->
  Operations · Due today · done when: Example Contact contacted and next weekly referral action/date captured

## Calendar
- **[lab]** all-day — Vendor A x Operations
"""


class RefineCalendarRunner(unittest.TestCase):
    def test_extract_outputs_and_day_type_from_daily_note(self):
        outputs = rc.extract_top_outputs(DAILY)
        self.assertEqual(len(outputs), 2)
        self.assertEqual(outputs[0].owner, "Operations / Product")
        self.assertEqual(outputs[0].source_refs[0].system, "cal")
        self.assertEqual(outputs[1].source_refs[0].system, "gtask")
        self.assertEqual(outputs[1].source_refs[0].id, "abc123")
        self.assertEqual(rc.extract_day_type(DAILY), "field")

    def _root_with_daily(self):
        td = tempfile.TemporaryDirectory()
        root = pathlib.Path(td.name)
        (root / "vault" / "daily").mkdir(parents=True)
        (root / "config").mkdir()
        (root / "vault" / "daily" / "2026-06-22.md").write_text(DAILY)
        (root / "config" / "calendar.yaml").write_text("""
working_bounds: {start: "09:00", end: "17:30", tz: "America/New_York"}
field_day_bounds: {end: "19:00"}
all_day_busy_default: false
important_meeting_keywords: ["lunch", "dinner", "breakfast", "important", "pitch"]
field_focus_min_window_min: 120
block_namespace: "▹"
min_gap_min: 20
travel_buffer_min: 15
routine_keywords: ["meditate", "tea", "gym", "lunch", "errand", "drive"]
durations:
  FOCUS: {min: 45, max: 60}
  PREP: {min: 15, max: 30}
  CAPTURE: {min: 15, max: 20}
  EOD: {min: 15, max: 20}
""")
        return td, root

    def test_generate_preview_writes_markdown_and_json_under_preview_dir(self):
        td, root = self._root_with_daily()
        with td:
            calendar = {"events": [{"start": "2026-06-22T10:30:00-04:00", "end": "2026-06-22T11:30:00-04:00", "summary": "Visit Jumpstart Medical"}]}
            preview = rc.generate_preview(root=root, date="2026-06-22", day_type=None, calendar_data=calendar)
            self.assertTrue(preview["markdown_path"].match("*/.context/preview/exec-plan-2026-06-22.md"))
            self.assertTrue(preview["json_path"].match("*/.context/preview/exec-plan-2026-06-22.json"))
            payload = json.loads(preview["json_path"].read_text())
            self.assertEqual(payload["status"], "preview_only_no_external_writes")
            self.assertEqual(payload["day_type"], "field")
            self.assertIn("## Execution Plan", preview["markdown"])
            self.assertNotIn("- [ ]", preview["markdown"])

    def test_attention_candidates_extend_outputs_in_priority_order(self):
        td, root = self._root_with_daily()
        with td:
            candidates = {
                "tasks": [
                    {"title": "Low attention admin cleanup", "workspace": "Other", "attention_pct": 5, "value_score": 20},
                    {"title": "High-value contact subset follow-up", "workspace": "Operations", "attention_pct": 45, "value_score": 90,
                     "done_when": "contact next step is scheduled", "subset": "contact-followups",
                     "source_refs": [{"system": "notion", "id": "task-high"}]},
                ]
            }
            preview = rc.generate_preview(root=root, date="2026-06-22", day_type="deep-work",
                                          calendar_data={"events": []}, task_candidates=candidates)
            titles = [o["title"] for o in preview["payload"]["outputs"]]
            self.assertEqual(titles[:2], [
                "Vendor A x Operations + DocPro — convert 3-week touchbase into pilot handoff",
                "Example Contact Thomas — advance Dr. Miao Huang referral cadence",
            ])
            self.assertEqual(titles[2], "High-value contact subset follow-up")
            self.assertEqual(preview["payload"]["outputs"][2]["source_refs"], [{"system": "notion", "id": "task-high"}])
            self.assertIn("High-value contact subset follow-up", preview["markdown"])


if __name__ == "__main__":
    unittest.main()
