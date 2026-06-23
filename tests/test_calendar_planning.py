"""Tests for scripts/calendar_planning.py — the pure scheduling engine (Slice 1).

No network, no disk: config is an injected dict mirroring config/calendar.yaml.
Covers the plan's §7 test list (all-day anchors, zero windows, no-end meetings,
PREP-no-preroom, DST, idempotent action_id, parser-safe render).
"""
import pathlib
import sys
import unittest
from datetime import datetime

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))

import calendar_planning as cp  # noqa: E402
import output_planning as op  # noqa: E402

DATE = "2026-06-22"  # a Monday in EDT


def cfg(start="09:00", end="17:30"):
    return {
        "working_bounds": {"start": start, "end": end, "tz": "America/New_York"},
        "field_day_bounds": {"end": "19:00"},
        "all_day_busy_default": False,
        "important_meeting_keywords": ["lunch", "dinner", "breakfast", "important", "pitch"],
        "field_focus_min_window_min": 120,
        "block_namespace": "▹",
        "min_gap_min": 20,
        "travel_buffer_min": 15,
        "routine_keywords": ["meditate", "tea", "gym", "lunch", "errand", "drive"],
        "durations": {
            "FOCUS": {"min": 45, "max": 60},
            "PREP": {"min": 15, "max": 30},
            "CAPTURE": {"min": 15, "max": 20},
            "EOD": {"min": 15, "max": 20},
        },
    }


def out(title, owner="Lincoln Lab", refs=None):
    return op.DailyOutput(
        title=title, owner=owner,
        source_refs=refs if refs is not None else [op.SourceRef("derived")],
        done_when=f"{title} shipped",
    )


def meeting(start, end, summary="GI Medical follow-up"):
    return {"start": f"{DATE}T{start}:00-04:00", "end": f"{DATE}T{end}:00-04:00",
            "summary": summary, "location": ""}


def _ivals(plan):
    return [(datetime.fromisoformat(b.start), datetime.fromisoformat(b.end))
            for b in plan.blocks]


class IntervalMath(unittest.TestCase):
    def test_open_windows_merge_overlapping_anchors(self):
        anchors = [meeting("10:00", "11:00", "A"), meeting("10:30", "12:00", "B")]
        windows, all_day = cp.compute_open_windows(anchors, config=cfg(), date=DATE)
        self.assertFalse(all_day)
        # merged busy 10:00–12:00 → open [09:00–10:00] and [12:00–17:30]
        self.assertEqual(len(windows), 2)
        self.assertEqual(windows[0][0].hour, 9)
        self.assertEqual(windows[0][1].hour, 10)
        self.assertEqual(windows[1][0].hour, 12)
        self.assertEqual(windows[1][1].hour, 17)

    def test_zero_open_windows_when_fully_booked(self):
        anchors = [meeting("09:00", "17:30", "all-hands")]
        windows, _ = cp.compute_open_windows(anchors, config=cfg(), date=DATE)
        self.assertEqual(sum(cp._minutes(s, e) for s, e in windows), 0)


class Placement(unittest.TestCase):
    def test_field_day_drops_all_focus(self):
        plan = cp.propose_calendar_blocks(
            [out("Telecor pilot"), out("Blessan referral")], [],
            config=cfg(), day_type="field", date=DATE)
        self.assertFalse(any(b.block_type == "FOCUS" for b in plan.blocks))
        self.assertIn("field_day_dropped_focus", plan.flags)

    def test_prep_before_and_capture_after_meeting(self):
        plan = cp.propose_calendar_blocks(
            [], [meeting("12:00", "13:00")], config=cfg(),
            day_type="deep-work", date=DATE)
        preps = [b for b in plan.blocks if b.block_type == "PREP"]
        caps = [b for b in plan.blocks if b.block_type == "CAPTURE"]
        self.assertTrue(preps and datetime.fromisoformat(preps[0].end).hour == 12)
        self.assertTrue(caps and datetime.fromisoformat(caps[0].start).hour == 13)

    def test_important_lunch_gets_full_30_minute_prep(self):
        plan = cp.propose_calendar_blocks(
            [], [meeting("12:00", "13:00", "GI Medical lunch with Doreen")],
            config=cfg(), day_type="field", date=DATE)
        prep = next(b for b in plan.blocks if b.block_type == "PREP")
        start = datetime.fromisoformat(prep.start)
        end = datetime.fromisoformat(prep.end)
        self.assertEqual(cp._minutes(start, end), 30)
        self.assertEqual(end.hour, 12)

    def test_important_dinner_gets_full_30_minute_prep(self):
        plan = cp.propose_calendar_blocks(
            [], [meeting("17:00", "18:00", "Nalbanian Jennifer dinner")],
            config=cfg(), day_type="field", date=DATE)
        prep = next(b for b in plan.blocks if b.block_type == "PREP")
        start = datetime.fromisoformat(prep.start)
        end = datetime.fromisoformat(prep.end)
        self.assertEqual(cp._minutes(start, end), 30)
        self.assertEqual((start.hour, start.minute), (16, 30))
        self.assertEqual((end.hour, end.minute), (17, 0))

    def test_field_day_uses_massive_gap_for_high_value_focus(self):
        anchors = [meeting("09:30", "10:00", "Quick provider stop"),
                   meeting("15:00", "16:00", "Important dinner planning")]
        plan = cp.propose_calendar_blocks(
            [out("Blessan referral"), out("Telecor pilot")], anchors,
            config=cfg(), day_type="field", date=DATE)
        focus = [b for b in plan.blocks if b.block_type == "FOCUS"]
        self.assertTrue(focus)
        self.assertEqual(focus[0].summary, "▹ FOCUS — Blessan referral")
        self.assertNotIn("field_day_dropped_focus", plan.flags)

    def test_field_day_small_gaps_still_drop_focus(self):
        anchors = [meeting("10:00", "11:00", "A"), meeting("12:00", "13:00", "B"),
                   meeting("14:00", "15:00", "C"), meeting("16:00", "17:00", "D")]
        plan = cp.propose_calendar_blocks(
            [out("Blessan referral")], anchors, config=cfg(),
            day_type="field", date=DATE)
        self.assertFalse(any(b.block_type == "FOCUS" for b in plan.blocks))
        self.assertIn("field_day_dropped_focus", plan.flags)

    def test_prep_no_preroom_when_meeting_at_bounds_start(self):
        plan = cp.propose_calendar_blocks(
            [], [meeting("09:00", "10:00")], config=cfg(),
            day_type="deep-work", date=DATE)
        self.assertIn("prep_no_preroom", plan.flags)
        self.assertFalse(any(b.block_type == "PREP" for b in plan.blocks))

    def test_no_block_overlaps_a_fixed_anchor(self):
        anchors = [meeting("11:00", "12:00"), meeting("14:00", "15:00", "DocPro")]
        plan = cp.propose_calendar_blocks(
            [out("A"), out("B")], anchors, config=cfg(),
            day_type="deep-work", date=DATE)
        busy = [(datetime.fromisoformat(a["start"]), datetime.fromisoformat(a["end"]))
                for a in anchors]
        for bs, be in _ivals(plan):
            for as_, ae in busy:
                self.assertFalse(bs < ae and as_ < be, f"{bs}-{be} overlaps anchor")

    def test_all_day_anchor_is_informational_by_default(self):
        anchors = [{"start": DATE, "end": "2026-06-23", "summary": "Telecor touchbase"}]
        plan = cp.propose_calendar_blocks(
            [out("A")], anchors, config=cfg(), day_type="deep-work", date=DATE)
        self.assertIn("all_day_anchor", plan.flags)
        self.assertGreater(plan.open_minutes, 0)
        self.assertTrue(any(b.block_type == "FOCUS" for b in plan.blocks))

    def test_all_day_anchor_can_be_marked_busy(self):
        anchors = [{"start": DATE, "end": "2026-06-23", "summary": "Telecor touchbase", "busy": True}]
        plan = cp.propose_calendar_blocks(
            [out("A")], anchors, config=cfg(), day_type="deep-work", date=DATE)
        self.assertIn("all_day_anchor", plan.flags)
        self.assertEqual(plan.open_minutes, 0)
        self.assertFalse(any(b.block_type == "FOCUS" for b in plan.blocks))

    def test_field_day_uses_extended_bounds_for_evening_eod(self):
        anchors = [meeting("17:00", "18:00", "Nalbanian and Jennifer Aquino dinner")]
        plan = cp.propose_calendar_blocks(
            [out("A")], anchors, config=cfg(), day_type="field", date=DATE)
        eods = [b for b in plan.blocks if b.block_type == "EOD"]
        self.assertTrue(eods)
        self.assertEqual(datetime.fromisoformat(eods[0].start).hour, 18)
        self.assertEqual(datetime.fromisoformat(eods[0].end).hour, 19)

    def test_anchor_missing_end_does_not_crash(self):
        anchors = [{"start": f"{DATE}T10:00:00-04:00", "summary": "x"}]
        plan = cp.propose_calendar_blocks(
            [out("A")], anchors, config=cfg(), day_type="deep-work", date=DATE)
        self.assertIsInstance(plan, cp.ExecutionPlan)

    def test_capacity_overload_reduces_and_flags(self):
        plan = cp.propose_calendar_blocks(
            [out("A"), out("B"), out("C")], [], config=cfg(end="10:00"),
            day_type="deep-work", date=DATE)
        focus = [b for b in plan.blocks if b.block_type == "FOCUS"]
        self.assertEqual(len(focus), 1)          # only one 60-min FOCUS fits
        self.assertGreaterEqual(plan.unplaced, 1)
        self.assertIn("over_capacity", plan.flags)


class IdsAndDeterminism(unittest.TestCase):
    def test_round15_buckets_collapse_minutes(self):
        d1 = datetime.fromisoformat(f"{DATE}T09:21:00-04:00")
        d2 = datetime.fromisoformat(f"{DATE}T09:23:00-04:00")
        self.assertEqual(cp._round15(d1), cp._round15(d2))
        self.assertEqual(cp._round15(d1), "09:15")

    def test_action_id_stable_across_reruns(self):
        outs, anchors = [out("Telecor pilot")], [meeting("12:00", "13:00")]
        p1 = cp.propose_calendar_blocks(outs, anchors, config=cfg(),
                                        day_type="deep-work", date=DATE)
        p2 = cp.propose_calendar_blocks(outs, anchors, config=cfg(),
                                        day_type="deep-work", date=DATE)
        self.assertEqual([b.action_id for b in p1.blocks],
                         [b.action_id for b in p2.blocks])
        for b in p1.blocks:
            self.assertTrue(b.action_id.startswith(f"refine-calendar:cal:{DATE}:"))

    def test_dst_offset_is_date_correct(self):
        summer = cp.propose_calendar_blocks([out("A")], [], config=cfg(),
                                            day_type="deep-work", date="2026-06-22")
        winter = cp.propose_calendar_blocks([out("A")], [], config=cfg(),
                                            day_type="deep-work", date="2026-01-15")
        self.assertTrue(summer.blocks[0].start.endswith("-04:00"))  # EDT
        self.assertTrue(winter.blocks[0].start.endswith("-05:00"))  # EST


class MarkersAndRender(unittest.TestCase):
    def test_source_markers_grounded(self):
        plan = cp.propose_calendar_blocks(
            [out("MDland", refs=[op.SourceRef("notion", "343a3158")])],
            [meeting("12:00", "13:00")], config=cfg(),
            day_type="deep-work", date=DATE)
        focus = next(b for b in plan.blocks if b.block_type == "FOCUS")
        prep = next(b for b in plan.blocks if b.block_type == "PREP")
        self.assertEqual(focus.source_markers, ["[notion:343a3158]"])
        self.assertEqual(prep.source_markers, ["[cal]"])

    def test_render_uses_sigil_not_checkbox(self):
        plan = cp.propose_calendar_blocks(
            [out("Telecor pilot")], [meeting("12:00", "13:00")], config=cfg(),
            day_type="deep-work", date=DATE)
        md = cp.render_execution_plan_markdown(plan)
        self.assertIn("## Execution Plan", md)
        self.assertIn("▹", md)
        self.assertIn("<!-- coo-block:refine-calendar:cal:", md)
        self.assertNotIn("- [ ]", md)
        self.assertNotIn("- [x]", md)

    def test_render_empty_states(self):
        field = cp.render_execution_plan_markdown(
            cp.propose_calendar_blocks([out("A")], [], config=cfg(),
                                       day_type="field", date=DATE))
        self.assertIn("field day", field.lower())


if __name__ == "__main__":
    unittest.main()
