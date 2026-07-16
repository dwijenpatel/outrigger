"""Regression guard: the design draft stays in the repo, with its oracle intact.

design-draft.md is the source of the worked example every other test in this
suite grades against -- the sample row, the proposed mappings, and the expected
preview row. This guard passes on base and must keep passing: the engine is
built *from* the draft, not *instead of* it.

Deliberately imports nothing from `eaitl` so it runs before the package exists.
"""

import pathlib
import re
import unittest


def find_repo_root():
    """The suite runs with cwd set to the repo checkout."""
    here = pathlib.Path.cwd().resolve()
    for candidate in (here, *here.parents):
        if (candidate / "design-draft.md").is_file():
            return candidate
    return here


class TestDesignDraftSurvives(unittest.TestCase):
    def setUp(self):
        self.root = find_repo_root()
        self.draft = self.root / "design-draft.md"

    def test_design_draft_is_still_present(self):
        self.assertTrue(
            self.draft.is_file(),
            f"design-draft.md must remain at the repo root (looked under {self.root})",
        )

    def test_draft_still_carries_the_worked_example_row(self):
        text = self.draft.read_text(encoding="utf-8")

        for token in ("raw_orders", "analytics_orders", "A1001", "2026-07-10T14:22:11Z"):
            self.assertIn(token, text, f"the draft no longer carries {token!r}")

    def test_draft_still_carries_the_expected_preview_values(self):
        text = self.draft.read_text(encoding="utf-8")

        self.assertIn("Ada Lovelace", text)
        self.assertRegex(text, r"25\.99")
        self.assertRegex(text, r'"order_date":\s*"2026-07-10"')

    def test_draft_still_names_the_op_library(self):
        text = self.draft.read_text(encoding="utf-8").lower()

        # The MVP op library the engine implements.
        for op in ("copy", "rename", "concat", "substring", "cast", "hash"):
            self.assertIn(op, text, f"the draft no longer names the {op!r} op")

    def test_draft_still_carries_the_proposed_mappings(self):
        text = self.draft.read_text(encoding="utf-8")

        self.assertIn("proposed_mappings", text)
        self.assertRegex(text, r'"op":\s*"concat"')
        self.assertRegex(text, r'"op":\s*"divide"')
        self.assertRegex(text, r'"op":\s*"to_date"')
        self.assertIsNotNone(
            re.search(r'"target_field":\s*"customer_name"', text),
            "the draft no longer proposes the customer_name mapping",
        )


if __name__ == "__main__":
    unittest.main()
