"""The `filters` section and the order of operations.

Pinned:
  - mappings are applied to EVERY input row first (errors captured by INPUT
    row_index), then filters gate which mapped rows are emitted;
  - each filter is a {op, args} predicate evaluated against the MAPPED OUTPUT
    row, using the same op/arg grammar;
  - all filters are AND-ed; a row is emitted only if every filter is truthy;
  - `errors` covers all input rows regardless of filtering.
"""

import unittest

from eaitl import apply_ir

from _fixtures import ErrorShapeMixin, make_ir, mapping, predicate


def orders_ir(filters=None):
    """id/amount_usd/is_paid over raw_orders-shaped rows."""
    return make_ir(
        [
            mapping("id", "copy", "order_id"),
            mapping("amount_usd", "divide", "amount_cents", 100),
            mapping("is_paid", "equals", "status", "paid"),
        ],
        filters=filters,
    )


ORDERS = [
    {"order_id": "A1", "amount_cents": 2599, "status": "paid"},
    {"order_id": "A2", "amount_cents": 100, "status": "pending"},
    {"order_id": "A3", "amount_cents": 5000, "status": "paid"},
]


class TestFiltersEvaluateAgainstTheMappedOutputRow(unittest.TestCase):
    def test_a_filter_drops_a_row(self):
        # `is_paid` exists only in the OUTPUT row -- it is a target_field, not
        # an input key. The filter must see the mapped value.
        ir = orders_ir([predicate("equals", "is_paid", True)])

        output_rows, errors = apply_ir(ir, ORDERS)

        self.assertEqual(
            [
                {"id": "A1", "amount_usd": 25.99, "is_paid": True},
                {"id": "A3", "amount_usd": 50.0, "is_paid": True},
            ],
            output_rows,
        )
        self.assertEqual([], errors)

    def test_a_filter_on_a_derived_numeric_target_field(self):
        # amount_usd is derived (cents / 100); the predicate compares against
        # the derived dollars, not the raw cents.
        ir = orders_ir([predicate("greater_than", "amount_usd", 30)])

        output_rows, _ = apply_ir(ir, ORDERS)

        self.assertEqual([{"id": "A3", "amount_usd": 50.0, "is_paid": True}], output_rows)

    def test_filters_are_anded(self):
        ir = orders_ir(
            [
                predicate("equals", "is_paid", True),
                predicate("greater_than", "amount_usd", 30),
            ]
        )

        output_rows, _ = apply_ir(ir, ORDERS)

        # A1 is paid but only $25.99; A2 is $1 and unpaid; only A3 clears both.
        self.assertEqual([{"id": "A3", "amount_usd": 50.0, "is_paid": True}], output_rows)

    def test_a_filter_that_matches_nothing_yields_no_rows(self):
        ir = orders_ir([predicate("greater_than", "amount_usd", 1000)])

        output_rows, errors = apply_ir(ir, ORDERS)

        self.assertEqual([], output_rows)
        self.assertEqual([], errors)

    def test_a_filter_that_matches_everything_keeps_the_order(self):
        ir = orders_ir([predicate("greater_equal", "amount_usd", 0)])

        output_rows, _ = apply_ir(ir, ORDERS)

        self.assertEqual(["A1", "A2", "A3"], [r["id"] for r in output_rows])

    def test_filters_do_not_add_or_remove_fields(self):
        ir = orders_ir([predicate("equals", "is_paid", True)])

        output_rows, _ = apply_ir(ir, ORDERS)

        for row in output_rows:
            self.assertEqual({"id", "amount_usd", "is_paid"}, set(row))

    def test_a_row_is_kept_only_when_the_filter_is_truthy(self):
        # "included only if every filter is truthy" -- a falsy value drops it.
        ir = make_ir([mapping("n", "copy", "n")], filters=[predicate("copy", "n")])

        output_rows, errors = apply_ir(ir, [{"n": 0}, {"n": 5}, {"n": 0}])

        self.assertEqual([{"n": 5}], output_rows)
        self.assertEqual([], errors)


class TestFiltersAndErrorsInteract(ErrorShapeMixin, unittest.TestCase):
    def test_row_index_indexes_input_rows_not_surviving_rows(self):
        # Row 0 is filtered out; row 2 has a divide-by-zero. The error must be
        # recorded against INPUT index 2 -- an engine that numbered the
        # surviving rows would say 1.
        ir = make_ir(
            [
                mapping("id", "copy", "order_id"),
                mapping("is_paid", "equals", "status", "paid"),
                mapping("ratio", "divide", "amount_cents", "divisor"),
            ],
            filters=[predicate("equals", "is_paid", True)],
        )
        rows = [
            {"order_id": "A1", "amount_cents": 2599, "status": "pending", "divisor": 100},
            {"order_id": "A2", "amount_cents": 100, "status": "paid", "divisor": 100},
            {"order_id": "A3", "amount_cents": 5000, "status": "paid", "divisor": 0},
        ]

        output_rows, errors = apply_ir(ir, rows)

        self.assertEqual(
            [
                {"id": "A2", "is_paid": True, "ratio": 1.0},
                {"id": "A3", "is_paid": True, "ratio": None},
            ],
            output_rows,
        )
        self.assertErrorsMatch(errors, [(2, "ratio")])

    def test_errors_are_recorded_for_rows_the_filters_drop(self):
        # "`errors` covers all input rows regardless of filtering." Row 0 has an
        # unparseable date AND is filtered out; its error must survive.
        ir = make_ir(
            [
                mapping("id", "copy", "order_id"),
                mapping("is_paid", "equals", "status", "paid"),
                mapping("order_date", "to_date", "created_at"),
            ],
            filters=[predicate("equals", "is_paid", True)],
        )
        rows = [
            {"order_id": "A1", "status": "pending", "created_at": "garbage"},
            {"order_id": "A2", "status": "paid", "created_at": "2026-07-10T00:00:00Z"},
        ]

        output_rows, errors = apply_ir(ir, rows)

        self.assertEqual(
            [{"id": "A2", "is_paid": True, "order_date": "2026-07-10"}], output_rows
        )
        self.assertErrorsMatch(errors, [(0, "order_date")])

    def test_a_row_with_a_captured_error_can_still_pass_the_filters(self):
        ir = make_ir(
            [mapping("keep", "copy", "keep"), mapping("ratio", "divide", "a", "b")],
            filters=[predicate("equals", "keep", True)],
        )

        output_rows, errors = apply_ir(ir, [{"keep": True, "a": 1, "b": 0}])

        self.assertEqual([{"keep": True, "ratio": None}], output_rows)
        self.assertErrorsMatch(errors, [(0, "ratio")])


class TestFilterEvaluationErrors(ErrorShapeMixin, unittest.TestCase):
    def test_a_failing_filter_is_captured_with_a_null_target_field(self):
        # A filter error is a row-level error: it is not tied to one target
        # field, so target_field is null. The row is not truthy-passing, so it
        # is not emitted.
        ir = make_ir([mapping("b", "copy", "a")], filters=[predicate("divide", "b", 0)])

        output_rows, errors = apply_ir(ir, [{"a": 1}])

        self.assertEqual([], output_rows)
        self.assertErrorsMatch(errors, [(0, None)])

    def test_a_filter_error_on_one_row_does_not_abort_the_batch(self):
        ir = make_ir(
            [mapping("n", "copy", "n"), mapping("d", "copy", "d")],
            filters=[predicate("greater_than", "n", "d")],
        )
        # Row 1 compares an int against a string -> TypeError inside the filter.
        rows = [{"n": 5, "d": 1}, {"n": 5, "d": "x"}, {"n": 9, "d": 2}]

        output_rows, errors = apply_ir(ir, rows)

        self.assertEqual([{"n": 5, "d": 1}, {"n": 9, "d": 2}], output_rows)
        self.assertErrorsMatch(errors, [(1, None)])


if __name__ == "__main__":
    unittest.main()
