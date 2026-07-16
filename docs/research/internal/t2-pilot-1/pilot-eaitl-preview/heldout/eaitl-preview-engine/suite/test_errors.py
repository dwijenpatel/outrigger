"""The error model.

FATAL -> raise MappingError, for STRUCTURAL IR problems only. These are
independent of row data, so they must raise even when `rows` is empty.

CAPTURED -> append to `errors`, set the target field to None, keep going. Per-row
DATA problems only. The batch is never aborted.
"""

import unittest

from eaitl import MappingError, apply_ir

from _fixtures import ErrorShapeMixin, make_ir, mapping, one_op_ir


GOOD_ROWS = [{"a": 1}]


class TestStructuralProblemsRaise(unittest.TestCase):
    def test_ir_that_is_not_a_dict(self):
        for bad_ir in ([], "mappings", None, 42, ["mappings"]):
            with self.subTest(ir=bad_ir):
                with self.assertRaises(MappingError):
                    apply_ir(bad_ir, list(GOOD_ROWS))

    def test_missing_mappings_key(self):
        with self.assertRaises(MappingError):
            apply_ir({"filters": []}, list(GOOD_ROWS))

    def test_mappings_that_is_not_a_list(self):
        for bad in ({"id": "copy"}, "copy", 7, None):
            with self.subTest(mappings=bad):
                with self.assertRaises(MappingError):
                    apply_ir({"mappings": bad}, list(GOOD_ROWS))

    def test_mapping_missing_target_field(self):
        ir = {"mappings": [{"transform": {"op": "copy", "args": ["a"]}}]}
        with self.assertRaises(MappingError):
            apply_ir(ir, list(GOOD_ROWS))

    def test_transform_missing_op(self):
        ir = {"mappings": [{"target_field": "out", "transform": {"args": ["a"]}}]}
        with self.assertRaises(MappingError):
            apply_ir(ir, list(GOOD_ROWS))

    def test_transform_missing_args(self):
        ir = {"mappings": [{"target_field": "out", "transform": {"op": "copy"}}]}
        with self.assertRaises(MappingError):
            apply_ir(ir, list(GOOD_ROWS))

    def test_unknown_op_name(self):
        with self.assertRaises(MappingError):
            apply_ir(one_op_ir("out", "frobnicate", "a"), list(GOOD_ROWS))

    def test_encrypt_is_not_in_this_slices_op_set(self):
        # `encrypt` is deferred to its own slice; it must be an unknown op here,
        # not a silently-accepted no-op.
        with self.assertRaises(MappingError):
            apply_ir(one_op_ir("out", "encrypt", "a"), list(GOOD_ROWS))

    def test_unknown_op_in_a_filter(self):
        ir = make_ir([mapping("out", "copy", "a")], filters=[{"op": "nope", "args": ["out"]}])
        with self.assertRaises(MappingError):
            apply_ir(ir, list(GOOD_ROWS))


class TestStructuralProblemsRaiseIndependentlyOfRowData(unittest.TestCase):
    """A structural problem is not a data problem: no rows are needed to see it."""

    def test_unknown_op_raises_even_with_no_rows(self):
        with self.assertRaises(MappingError):
            apply_ir(one_op_ir("out", "frobnicate", "a"), [])

    def test_missing_target_field_raises_even_with_no_rows(self):
        ir = {"mappings": [{"transform": {"op": "copy", "args": ["a"]}}]}
        with self.assertRaises(MappingError):
            apply_ir(ir, [])

    def test_transform_missing_op_raises_even_with_no_rows(self):
        ir = {"mappings": [{"target_field": "out", "transform": {"args": ["a"]}}]}
        with self.assertRaises(MappingError):
            apply_ir(ir, [])

    def test_a_structural_problem_in_a_later_mapping_still_raises(self):
        # The first mapping is fine; validation must not stop at the first
        # good entry.
        ir = make_ir([mapping("ok", "copy", "a"), mapping("bad", "frobnicate", "a")])
        with self.assertRaises(MappingError):
            apply_ir(ir, list(GOOD_ROWS))

    def test_structural_problems_are_never_captured_into_errors(self):
        # An engine that swallowed the unknown op into `errors` instead of
        # raising would fail here.
        try:
            apply_ir(one_op_ir("out", "frobnicate", "a"), list(GOOD_ROWS))
        except MappingError:
            return
        self.fail("an unknown op must raise MappingError, not be captured in errors")


class TestCapturedRowErrors(ErrorShapeMixin, unittest.TestCase):
    def test_a_failing_field_is_none_and_the_row_is_still_emitted(self):
        output_rows, errors = apply_ir(
            one_op_ir("ratio", "divide", "a", "b"), [{"a": 1, "b": 0}]
        )

        self.assertEqual(1, len(output_rows), "a captured error must not drop the row")
        self.assertIn("ratio", output_rows[0], "the target field must still be present")
        self.assertIsNone(output_rows[0]["ratio"])
        self.assertErrorsMatch(errors, [(0, "ratio")])

    def test_sibling_fields_in_the_same_row_still_transform(self):
        ir = make_ir(
            [
                mapping("id", "copy", "order_id"),
                mapping("ratio", "divide", "amount", "divisor"),
                mapping("h", "hash", "order_id"),
            ]
        )
        rows = [{"order_id": "A1", "amount": 10, "divisor": 0}]

        output_rows, errors = apply_ir(ir, rows)

        self.assertEqual("A1", output_rows[0]["id"])
        self.assertIsNone(output_rows[0]["ratio"])
        self.assertEqual(64, len(output_rows[0]["h"]))
        self.assertErrorsMatch(errors, [(0, "ratio")])

    def test_the_batch_is_not_aborted_by_a_bad_row(self):
        ir = one_op_ir("ratio", "divide", "a", "b")
        rows = [{"a": 10, "b": 2}, {"a": 10, "b": 0}, {"a": 9, "b": 3}]

        output_rows, errors = apply_ir(ir, rows)

        self.assertEqual([{"ratio": 5.0}, {"ratio": None}, {"ratio": 3.0}], output_rows)
        self.assertErrorsMatch(errors, [(1, "ratio")])

    def test_row_index_indexes_the_input_rows(self):
        ir = one_op_ir("d", "to_date", "ts")
        rows = [
            {"ts": "2026-01-01"},
            {"ts": "2026-01-02"},
            {"ts": "nonsense"},
            {"ts": "2026-01-04"},
        ]

        _, errors = apply_ir(ir, rows)

        self.assertErrorsMatch(errors, [(2, "d")])

    def test_several_failing_fields_in_one_row_yield_several_records(self):
        ir = make_ir(
            [
                mapping("ratio", "divide", "a", 0),
                mapping("when", "to_date", "ts"),
                mapping("n", "cast", "ts", "int"),
                mapping("ok", "copy", "a"),
            ]
        )

        output_rows, errors = apply_ir(ir, [{"a": 1, "ts": "nope"}])

        self.assertEqual([{"ratio": None, "when": None, "n": None, "ok": 1}], output_rows)
        self.assertErrorsMatch(errors, [(0, "ratio"), (0, "when"), (0, "n")])

    def test_errors_from_several_rows_are_all_recorded(self):
        ir = one_op_ir("d", "to_date", "ts")
        rows = [{"ts": "bad"}, {"ts": "2026-01-02"}, {"ts": "also bad"}]

        _, errors = apply_ir(ir, rows)

        self.assertErrorsMatch(errors, [(0, "d"), (2, "d")])

    def test_a_captured_error_names_the_target_field_not_the_source(self):
        _, errors = apply_ir(one_op_ir("order_date", "to_date", "created_at"), [{"created_at": "x"}])

        self.assertEqual(1, len(errors))
        self.assertEqual("order_date", errors[0]["target_field"])


class TestMissingSourceField(ErrorShapeMixin, unittest.TestCase):
    """A referenced source field that is absent from the row is captured.

    Note the interaction with the arg-resolution rule: a bare string that
    matches no key falls back to being a LITERAL (the worked example's " "
    separator depends on that fallback). So these cases use ops for which the
    literal fallback cannot itself succeed -- the field is absent, the op has
    nothing valid to work on, and the outcome the spec pins is the same either
    way: the target field is None and one error is captured for it.
    """

    def test_arithmetic_on_an_absent_field(self):
        output_rows, errors = apply_ir(
            one_op_ir("amount_usd", "divide", "amount_cents", 100), [{"order_id": "A1"}]
        )

        self.assertEqual([{"amount_usd": None}], output_rows)
        self.assertErrorsMatch(errors, [(0, "amount_usd")])

    def test_to_date_on_an_absent_field(self):
        output_rows, errors = apply_ir(
            one_op_ir("order_date", "to_date", "created_at"), [{"order_id": "A1"}]
        )

        self.assertEqual([{"order_date": None}], output_rows)
        self.assertErrorsMatch(errors, [(0, "order_date")])

    def test_cast_to_int_on_an_absent_field(self):
        output_rows, errors = apply_ir(
            one_op_ir("n", "cast", "amount_cents", "int"), [{"order_id": "A1"}]
        )

        self.assertEqual([{"n": None}], output_rows)
        self.assertErrorsMatch(errors, [(0, "n")])

    def test_only_the_rows_actually_missing_the_field_are_flagged(self):
        # Rows in a batch need not be homogeneous.
        ir = one_op_ir("usd", "divide", "cents", 100)
        rows = [{"cents": 2599}, {"other": 1}, {"cents": 100}]

        output_rows, errors = apply_ir(ir, rows)

        self.assertEqual([{"usd": 25.99}, {"usd": None}, {"usd": 1.0}], output_rows)
        self.assertErrorsMatch(errors, [(1, "usd")])


if __name__ == "__main__":
    unittest.main()
