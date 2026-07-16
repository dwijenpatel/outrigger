"""Arg resolution: row-key match, literal fallback, and the {"lit": v} escape.

The rule, pinned:
  - a STRING arg equal to a key in the input row -> that row's value;
  - any other arg (non-matching string, number, bool) -> a literal;
  - {"lit": v} -> ALWAYS the literal v, even when v matches a field key.

The worked example depends on the literal fallback (the " " separator in
concat is not a field), so it is not optional.
"""

import unittest

from eaitl import apply_ir

from _fixtures import make_ir, mapping, one_op_ir


class TestRowKeyMatch(unittest.TestCase):
    def test_a_string_matching_a_key_resolves_to_that_rows_value(self):
        output_rows, errors = apply_ir(
            one_op_ir("out", "copy", "status"), [{"status": "paid"}, {"status": "void"}]
        )

        self.assertEqual([{"out": "paid"}, {"out": "void"}], output_rows)
        self.assertEqual([], errors)

    def test_resolution_is_per_row(self):
        # The same IR against rows with different values for the same key.
        output_rows, _ = apply_ir(
            one_op_ir("out", "multiply", "n", 2), [{"n": 1}, {"n": 5}, {"n": 10}]
        )

        self.assertEqual([{"out": 2}, {"out": 10}, {"out": 20}], output_rows)

    def test_a_key_present_with_a_null_value_still_resolves_as_a_reference(self):
        # A key whose value is None is present. It must resolve to None -- it
        # must NOT fall through to being treated as the literal string "note".
        output_rows, errors = apply_ir(
            one_op_ir("out", "concat", "note", "-tail"), [{"note": None}]
        )

        self.assertEqual([{"out": "-tail"}], output_rows)
        self.assertEqual([], errors)


class TestLiteralFallback(unittest.TestCase):
    def test_a_non_matching_string_is_a_literal(self):
        # " " is the draft's own concat separator: a bare string that is not a
        # field name is a literal.
        output_rows, errors = apply_ir(
            one_op_ir("out", "concat", "first", " ", "last"),
            [{"first": "Ada", "last": "Lovelace"}],
        )

        self.assertEqual([{"out": "Ada Lovelace"}], output_rows)
        self.assertEqual([], errors)

    def test_numbers_are_literals(self):
        output_rows, _ = apply_ir(one_op_ir("out", "divide", "cents", 100), [{"cents": 2599}])
        self.assertEqual([{"out": 25.99}], output_rows)

    def test_booleans_are_literals(self):
        output_rows, _ = apply_ir(
            one_op_ir("out", "equals", "flag", True), [{"flag": True}, {"flag": False}]
        )
        self.assertEqual([{"out": True}, {"out": False}], output_rows)

    def test_a_string_that_matches_no_key_stays_a_literal_in_a_comparison(self):
        output_rows, _ = apply_ir(
            one_op_ir("out", "equals", "status", "paid"),
            [{"status": "paid"}, {"status": "pending"}],
        )
        self.assertEqual([{"out": True}, {"out": False}], output_rows)


class TestLitEscapeHatch(unittest.TestCase):
    def test_lit_forces_a_literal_even_when_it_matches_a_field_name(self):
        # The row HAS an `order_id` key. {"lit": "order_id"} must still be the
        # literal string "order_id", not the row's value "A1001".
        output_rows, errors = apply_ir(
            one_op_ir("out", "copy", {"lit": "order_id"}), [{"order_id": "A1001"}]
        )

        self.assertEqual([{"out": "order_id"}], output_rows)
        self.assertEqual([], errors)

    def test_lit_in_a_comparison_compares_against_the_name_not_the_value(self):
        # equals({"lit": "status"}, "status") compares the literal "status"
        # against the row's value "paid" -> False. An engine that ignores the
        # escape would compare "paid" to "paid" and wrongly answer True.
        output_rows, _ = apply_ir(
            one_op_ir("out", "equals", {"lit": "status"}, "status"), [{"status": "paid"}]
        )

        self.assertEqual([{"out": False}], output_rows)

    def test_lit_wrapping_a_field_name_inside_concat(self):
        output_rows, _ = apply_ir(
            one_op_ir("out", "concat", {"lit": "first"}, "=", "first"), [{"first": "Ada"}]
        )

        self.assertEqual([{"out": "first=Ada"}], output_rows)

    def test_lit_carries_non_string_payloads(self):
        output_rows, _ = apply_ir(
            one_op_ir("out", "divide", "cents", {"lit": 100}), [{"cents": 2599}]
        )
        self.assertEqual([{"out": 25.99}], output_rows)

    def test_lit_none_renders_as_empty_string_in_concat(self):
        output_rows, errors = apply_ir(
            one_op_ir("out", "concat", {"lit": None}, "tail"), [{"a": 1}]
        )

        self.assertEqual([{"out": "tail"}], output_rows)
        self.assertEqual([], errors)

    def test_lit_works_in_filter_args(self):
        # Same arg grammar in filters. {"lit": "keep"} vs the mapped `label`.
        ir = make_ir(
            [mapping("label", "copy", "label")],
            filters=[{"op": "equals", "args": ["label", {"lit": "keep"}]}],
        )

        output_rows, errors = apply_ir(ir, [{"label": "keep"}, {"label": "drop"}])

        self.assertEqual([{"label": "keep"}], output_rows)
        self.assertEqual([], errors)


class TestMultipleMappingsShareTheRow(unittest.TestCase):
    def test_each_mapping_resolves_against_the_same_input_row(self):
        ir = make_ir(
            [
                mapping("a", "copy", "x"),
                mapping("b", "copy", "y"),
                mapping("both", "concat", "x", "y"),
            ]
        )

        output_rows, errors = apply_ir(ir, [{"x": "1", "y": "2"}])

        self.assertEqual([{"a": "1", "b": "2", "both": "12"}], output_rows)
        self.assertEqual([], errors)

    def test_a_later_mapping_cannot_reference_an_earlier_target_field(self):
        # Mappings resolve against the INPUT row. `full` is a target field, not
        # an input key, so referencing it from another mapping falls back to
        # the literal string -- the engine must not thread mapped values back
        # into the row it resolves against.
        ir = make_ir(
            [
                mapping("full", "concat", "first", "last"),
                mapping("echo", "copy", "full"),
            ]
        )

        output_rows, _ = apply_ir(ir, [{"first": "Ada", "last": "Lovelace"}])

        self.assertEqual([{"full": "AdaLovelace", "echo": "full"}], output_rows)


if __name__ == "__main__":
    unittest.main()
