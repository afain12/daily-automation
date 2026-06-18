import json
import pathlib
import tempfile
import unittest

import sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))

import end_day_orchestrator as edo


class EndDayOrchestratorTests(unittest.TestCase):
    def test_extract_braindump_variants_and_boundaries(self):
        text = """# Daily
Intro
**Braindump:**
Talked to Alex about Roosevelt.
Dr Tim ENG followup.
**Observations:**
Stop here.
"""
        self.assertEqual(
            edo.extract_braindump(text),
            "Talked to Alex about Roosevelt.\nDr Tim ENG followup.",
        )

        h2 = """## Braindump
Line one
Line two
## End of Day Review
ignore
"""
        self.assertEqual(edo.extract_braindump(h2), "Line one\nLine two")

    def test_extract_checked_source_actions_from_daily_note(self):
        text = """
- [x] **Reach out to Healthix** <!-- gtask:abc123 --> done
- [X] **MDland negotiation** <!-- notion:343a3158 -->
- [x] **Buy RDDT** <!-- derived -->
- [ ] **Open item** <!-- gtask:open -->
"""
        actions = edo.extract_checked_source_actions(text)
        self.assertEqual(len(actions), 3)
        self.assertEqual(actions[0]["type"], "gtask_complete")
        self.assertEqual(actions[0]["source_id"], "abc123")
        self.assertEqual(actions[1]["type"], "notion_done")
        self.assertEqual(actions[2]["type"], "manual_completion")

    def test_merge_previews_dedupes_by_source_line_and_type(self):
        a1 = edo.WriteAction(owner="note_harvest", type="gtask", title="Call Alex", source_line=10, source_text="Call Alex", confidence=0.9)
        a2 = edo.WriteAction(owner="sync_sweep", type="notion_append", title="Call Alex", source_line=10, source_text="Call Alex", confidence=0.9)
        a3 = edo.WriteAction(owner="end_day", type="gtask_complete", title="Close Healthix", source_line=11, source_text="Healthix", confidence=1.0)
        plan = edo.merge_previews(
            edo.RunContext(date="2026-06-16", mode="draft", run_id="ed-test"),
            [edo.SkillPreview(skill="note_harvest", actions=[a1]), edo.SkillPreview(skill="sync_sweep", actions=[a2]), edo.SkillPreview(skill="end_day", actions=[a3])],
        )
        # note_harvest action owns the line; sync_sweep duplicate is downgraded to warning/noop.
        self.assertEqual([w.owner for w in plan.proposed_writes], ["end_day", "note_harvest"])
        self.assertTrue(any("sync_sweep skipped" in w for w in plan.warnings))

    def test_sync_sweep_preview_noops_when_no_braindump(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            daily = root / "vault" / "daily"
            daily.mkdir(parents=True)
            (daily / "2026-06-16.md").write_text("# Daily\n## End of Day Review\n", encoding="utf-8")
            ctx = edo.RunContext(date="2026-06-16", mode="draft", run_id="ed-test", repo_dir=root)
            preview = edo.preview_sync_sweep(ctx)
            self.assertEqual(preview.actions, [])
            self.assertIn("no Braindump", preview.summary)


if __name__ == "__main__":
    unittest.main()
