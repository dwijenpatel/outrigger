"""The import-stable public boundary: `from eaitl import apply_ir, MappingError`.

Also the purity/determinism constraints: apply_ir is a pure function of its
arguments -- it must not mutate them, must not carry state between calls, and
must return identical results for identical input.
"""

import copy
import inspect
import unittest

import eaitl
from eaitl import MappingError, apply_ir

from _fixtures import DRAFT_IR, DRAFT_ROW, make_ir, mapping, one_op_ir, predicate


class TestPublicSurface(unittest.TestCase):
    def test_package_exports_both_public_names(self):
        self.assertTrue(hasattr(eaitl, "apply_ir"))
        self.assertTrue(hasattr(eaitl, "MappingError"))
        self.assertTrue(callable(eaitl.apply_ir))

    def test_mapping_error_is_an_exception_class(self):
        self.assertTrue(inspect.isclass(MappingError))
        self.assertTrue(issubclass(MappingError, Exception))

    def test_apply_ir_returns_a_two_tuple_of_lists(self):
        result = apply_ir(one_op_ir("id", "copy", "a"), [{"a": 1}])

        self.assertIsInstance(result, tuple, "apply_ir must return a tuple")
        self.assertEqual(2, len(result))
        output_rows, errors = result
        self.assertIsInstance(output_rows, list)
        self.assertIsInstance(errors, list)
        self.assertTrue(all(isinstance(r, dict) for r in output_rows))

    def test_apply_ir_accepts_its_pinned_keyword_names(self):
        # The signature is pinned as apply_ir(ir, rows); a consumer may call it
        # either positionally or by keyword.
        output_rows, errors = apply_ir(ir=one_op_ir("id", "copy", "a"), rows=[{"a": "x"}])

        self.assertEqual([{"id": "x"}], output_rows)
        self.assertEqual([], errors)

    def test_apply_ir_is_annotated(self):
        # The package is fully type-annotated (`mypy --strict eaitl` is a gate);
        # the public entrypoint must carry annotations for both params and the
        # return. `from __future__ import annotations` keeps these as strings,
        # which is fine -- we only require that they exist.
        hints = getattr(apply_ir, "__annotations__", {})

        for name in ("ir", "rows", "return"):
            self.assertIn(name, hints, f"apply_ir is missing an annotation for {name!r}")


class TestEmptyAndDegenerateInputs(unittest.TestCase):
    def test_no_rows_yields_two_empty_lists(self):
        self.assertEqual(([], []), apply_ir(copy.deepcopy(DRAFT_IR), []))

    def test_no_mappings_yields_one_empty_dict_per_row(self):
        # An output row holds "every mapping's target_field" -- with no
        # mappings that is the empty dict. Source fields are never passed
        # through.
        output_rows, errors = apply_ir(make_ir([]), [{"a": 1}, {"b": 2}])

        self.assertEqual([{}, {}], output_rows)
        self.assertEqual([], errors)

    def test_missing_filters_key_defaults_to_no_filtering(self):
        ir = make_ir([mapping("id", "copy", "a")])
        self.assertNotIn("filters", ir)

        output_rows, errors = apply_ir(ir, [{"a": 1}, {"a": 2}])

        self.assertEqual([{"id": 1}, {"id": 2}], output_rows)
        self.assertEqual([], errors)

    def test_empty_filters_list_keeps_every_row(self):
        ir = make_ir([mapping("id", "copy", "a")], filters=[])

        output_rows, _ = apply_ir(ir, [{"a": 1}, {"a": 2}])

        self.assertEqual([{"id": 1}, {"id": 2}], output_rows)


class TestPurity(unittest.TestCase):
    """No side-effects: the arguments come back untouched."""

    def test_input_rows_are_not_mutated(self):
        rows = [copy.deepcopy(DRAFT_ROW)]
        before = copy.deepcopy(rows)

        apply_ir(copy.deepcopy(DRAFT_IR), rows)

        self.assertEqual(before, rows, "apply_ir must not mutate the rows it is given")

    def test_input_ir_is_not_mutated(self):
        ir = copy.deepcopy(DRAFT_IR)
        before = copy.deepcopy(ir)

        apply_ir(ir, [copy.deepcopy(DRAFT_ROW)])

        self.assertEqual(before, ir, "apply_ir must not mutate the IR it is given")

    def test_output_rows_are_fresh_objects(self):
        # A same-named passthrough mapping is the case where an engine could
        # get away with handing the caller's own dict back.
        rows = [{"a": 1}]

        output_rows, _ = apply_ir(one_op_ir("a", "copy", "a"), rows)

        self.assertEqual([{"a": 1}], output_rows)
        self.assertIsNot(rows[0], output_rows[0])

    def test_mutating_a_result_does_not_affect_later_calls(self):
        ir = copy.deepcopy(DRAFT_IR)
        rows = [copy.deepcopy(DRAFT_ROW)]

        first_rows, first_errors = apply_ir(ir, rows)
        first_rows[0]["id"] = "TAMPERED"
        first_rows.append({"injected": True})
        first_errors.append({"row_index": 99, "target_field": None, "reason": "injected"})

        second_rows, second_errors = apply_ir(ir, rows)

        self.assertEqual("A1001", second_rows[0]["id"])
        self.assertEqual(1, len(second_rows))
        self.assertEqual([], second_errors)


class TestDeterminism(unittest.TestCase):
    def test_identical_input_yields_identical_output(self):
        ir = copy.deepcopy(DRAFT_IR)
        rows = [copy.deepcopy(DRAFT_ROW)]

        self.assertEqual(apply_ir(ir, rows), apply_ir(ir, rows))

    def test_no_state_carries_between_calls(self):
        # Interleave two different IRs; the third call must match the first.
        ir_a = make_ir(
            [mapping("id", "copy", "order_id"), mapping("h", "hash", "status")],
            filters=[predicate("equals", "id", "A1001")],
        )
        ir_b = make_ir([mapping("cents", "multiply", "amount_cents", 2)])
        rows = [copy.deepcopy(DRAFT_ROW)]

        first = apply_ir(ir_a, rows)
        apply_ir(ir_b, rows)
        third = apply_ir(ir_a, rows)

        self.assertEqual(first, third)


if __name__ == "__main__":
    unittest.main()
