"""Tests for scripts/output_calendar.py — gated Google Calendar write adapter.

These tests use a fake runner; they never call the real Google API.
"""
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))

import output_calendar as oc  # noqa: E402


BLOCK = {
    "block_type": "PREP",
    "summary": "▹ PREP — Visit Jumpstart Medical",
    "start": "2026-06-22T10:00:00-04:00",
    "end": "2026-06-22T10:30:00-04:00",
    "source_markers": ["[cal]"],
    "write_eligible": False,
    "dedupe_key": "meeting:visit-jumpstart-medical|PREP|2026-06-22|10:00",
    "action_id": "refine-calendar:cal:2026-06-22:922aa45e",
    "flags": [],
}


class OutputCalendarAdapter(unittest.TestCase):
    def test_build_calendar_insert_command_uses_google_api_with_action_description(self):
        cmd = oc.build_calendar_insert_command(BLOCK)
        self.assertEqual(cmd[:4], ["python3", "scripts/google_api.py", "calendar", "insert"])
        self.assertIn("--summary", cmd)
        self.assertIn("▹ PREP — Visit Jumpstart Medical", cmd)
        self.assertIn("--start", cmd)
        self.assertIn("2026-06-22T10:00:00-04:00", cmd)
        self.assertIn("--end", cmd)
        self.assertIn("2026-06-22T10:30:00-04:00", cmd)
        desc = cmd[cmd.index("--description") + 1]
        self.assertIn("action_id: refine-calendar:cal:2026-06-22:922aa45e", desc)
        self.assertIn("source_markers: [cal]", desc)

    def test_preview_mode_does_not_call_runner(self):
        calls = []
        result = oc.apply_blocks([BLOCK], apply=False, mode="draft", already_applied=lambda aid: False,
                                 stamp=lambda aid, meta: None, runner=lambda cmd: calls.append(cmd))
        self.assertEqual(result["status"], "preview")
        self.assertEqual(calls, [])
        self.assertEqual(result["created"], [])

    def test_apply_requires_approved_or_auto_mode(self):
        with self.assertRaisesRegex(oc.CalendarApplyError, "requires mode approved/auto"):
            oc.apply_blocks([BLOCK], apply=True, mode="draft", already_applied=lambda aid: False,
                            stamp=lambda aid, meta: None, runner=lambda cmd: {"status": "ok"})

    def test_apply_creates_and_stamps_once(self):
        calls = []
        stamps = []
        result = oc.apply_blocks([BLOCK], apply=True, mode="approved", already_applied=lambda aid: False,
                                 stamp=lambda aid, meta: stamps.append((aid, meta)),
                                 runner=lambda cmd: calls.append(cmd) or {"status": "ok", "id": "evt_123", "link": "https://cal/evt_123"})
        self.assertEqual(len(calls), 1)
        self.assertEqual(result["status"], "applied")
        self.assertEqual(result["created"][0]["event_id"], "evt_123")
        self.assertEqual(stamps[0][0], BLOCK["action_id"])
        self.assertEqual(stamps[0][1]["calendar_event_id"], "evt_123")

    def test_apply_skips_already_stamped_action_id(self):
        calls = []
        stamps = []
        result = oc.apply_blocks([BLOCK], apply=True, mode="approved", already_applied=lambda aid: True,
                                 stamp=lambda aid, meta: stamps.append((aid, meta)),
                                 runner=lambda cmd: calls.append(cmd) or {"status": "ok"})
        self.assertEqual(calls, [])
        self.assertEqual(stamps, [])
        self.assertEqual(result["skipped"][0]["reason"], "already_applied")

    def test_load_preview_accepts_blocks_or_plan_blocks_shape(self):
        with tempfile.TemporaryDirectory() as td:
            p1 = pathlib.Path(td) / "direct.json"
            p1.write_text(json.dumps({"blocks": [BLOCK]}))
            p2 = pathlib.Path(td) / "plan.json"
            p2.write_text(json.dumps({"plan": {"blocks": [BLOCK]}}))
            self.assertEqual(oc.load_preview_blocks(p1), [BLOCK])
            self.assertEqual(oc.load_preview_blocks(p2), [BLOCK])


if __name__ == "__main__":
    unittest.main()
