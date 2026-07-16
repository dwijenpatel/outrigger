"""The worked-example oracle from design-draft.md.

raw_orders -> analytics_orders must reproduce the draft's `preview_rows` /
`example_output_rows` exactly, with no errors.
"""

import copy
import pathlib
import unittest

import eaitl
from eaitl import apply_ir

from _fixtures import DRAFT_EXPECTED_ROW, DRAFT_IR, DRAFT_ROW


class TestWorkedExample(unittest.TestCase):
    def test_reproduces_the_drafts_preview_row_exactly(self):
        output_rows, errors = apply_ir(copy.deepcopy(DRAFT_IR), [copy.deepcopy(DRAFT_ROW)])

        self.assertEqual([], errors, "the worked example must transform cleanly")
        self.assertEqual([DRAFT_EXPECTED_ROW], output_rows)

    def test_output_row_holds_only_the_target_fields(self):
        # Exact dict equality above already pins this, but state it directly:
        # the output row is built from target_field names, it is not the input
        # row with the targets overlaid onto it.
        output_rows, _ = apply_ir(copy.deepcopy(DRAFT_IR), [copy.deepcopy(DRAFT_ROW)])

        self.assertEqual(
            {"id", "customer_name", "amount_usd", "order_date", "is_paid"},
            set(output_rows[0]),
        )
        for source_field in DRAFT_ROW:
            self.assertNotIn(
                source_field,
                output_rows[0],
                "source fields must not leak into the output row",
            )

    def test_worked_example_value_types(self):
        (row,), _ = apply_ir(copy.deepcopy(DRAFT_IR), [copy.deepcopy(DRAFT_ROW)])

        self.assertIsInstance(row["id"], str)
        self.assertIsInstance(row["customer_name"], str)
        # divide is true division: 2599 / 100 is 25.99, not 25.
        self.assertIsInstance(row["amount_usd"], float)
        self.assertEqual(25.99, row["amount_usd"])
        self.assertIsInstance(row["order_date"], str)
        # equals yields a real bool, not a truthy stand-in.
        self.assertIs(True, row["is_paid"])

    def test_batch_of_the_same_row_maps_each_row(self):
        rows = [copy.deepcopy(DRAFT_ROW) for _ in range(3)]

        output_rows, errors = apply_ir(copy.deepcopy(DRAFT_IR), rows)

        self.assertEqual([], errors)
        self.assertEqual([DRAFT_EXPECTED_ROW] * 3, output_rows)

    def test_proposal_metadata_is_ignored(self):
        # `sources`, `type`, `confidence`, `rationale`, `status` are proposal
        # metadata. An engine that resolves args from `sources` (rather than
        # from transform.args) would still pass the oracle above, so poison
        # `sources` here and demand the same answer.
        ir = copy.deepcopy(DRAFT_IR)
        for entry in ir["mappings"]:
            entry["sources"] = ["no_such_field"]
            entry["type"] = "nonsense"
            entry["confidence"] = 0.0
            entry["status"] = "rejected"

        output_rows, errors = apply_ir(ir, [copy.deepcopy(DRAFT_ROW)])

        self.assertEqual([], errors)
        self.assertEqual([DRAFT_EXPECTED_ROW], output_rows)

    def test_validations_section_is_not_executed(self):
        # Executing `validations` is an explicit non-goal of this slice. A
        # validation that would certainly fail must be inert.
        ir = copy.deepcopy(DRAFT_IR)
        ir["validations"] = [
            {"kind": "not_null", "field": "field_that_does_not_exist"},
            {"kind": "type_check", "field": "id", "expected": "integer"},
        ]

        output_rows, errors = apply_ir(ir, [copy.deepcopy(DRAFT_ROW)])

        self.assertEqual([], errors, "the validations section must be ignored")
        self.assertEqual([DRAFT_EXPECTED_ROW], output_rows)

    def test_unknown_top_level_ir_keys_are_ignored(self):
        ir = copy.deepcopy(DRAFT_IR)
        ir["mapping_version"] = "v1"
        ir["questions"] = []
        ir["some_future_key"] = {"anything": True}

        output_rows, errors = apply_ir(ir, [copy.deepcopy(DRAFT_ROW)])

        self.assertEqual([], errors)
        self.assertEqual([DRAFT_EXPECTED_ROW], output_rows)


class TestExampleFixtureIsShipped(unittest.TestCase):
    """The spec requires the example IR/rows to be shipped under examples/."""

    def _repo_root_candidates(self):
        roots = [pathlib.Path(eaitl.__file__).resolve().parent.parent]
        roots.append(pathlib.Path.cwd().resolve())
        return roots

    def test_examples_directory_exists_and_is_not_empty(self):
        checked = []
        for root in self._repo_root_candidates():
            examples = root / "examples"
            checked.append(str(examples))
            if examples.is_dir() and any(p.is_file() for p in examples.rglob("*")):
                return
        self.fail(
            "the example IR/rows fixture must be shipped under examples/; "
            f"looked in: {', '.join(checked)}"
        )


if __name__ == "__main__":
    unittest.main()
