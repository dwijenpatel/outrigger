"""Per-op semantics, exactly as pinned by the spec."""

import hashlib
import unittest

from eaitl import apply_ir

from _fixtures import ErrorShapeMixin, one_op_ir


def value(target_field, op, *args, row):
    """Run a single-mapping IR over one row and return (value, errors)."""
    output_rows, errors = apply_ir(one_op_ir(target_field, op, *args), [row])
    return output_rows[0][target_field], errors


class TestCopyAndRename(unittest.TestCase):
    def test_copy_passes_the_value_through_unchanged(self):
        got, errors = value("out", "copy", "a", row={"a": "A1001"})
        self.assertEqual("A1001", got)
        self.assertEqual([], errors)

    def test_copy_preserves_the_value_type(self):
        for raw in (2599, 25.99, True, False, "x", [1, 2], {"k": "v"}):
            with self.subTest(raw=raw):
                got, errors = value("out", "copy", "a", row={"a": raw})
                self.assertEqual(raw, got)
                self.assertEqual([], errors)

    def test_copy_of_a_present_null_field_is_null_and_is_not_an_error(self):
        # A key that is present with value None is NOT a missing field. The
        # value resolves to None and copy hands it back; nothing is captured.
        output_rows, errors = apply_ir(one_op_ir("out", "copy", "a"), [{"a": None}])

        self.assertEqual([{"out": None}], output_rows)
        self.assertEqual([], errors, "a present-but-null field is not an error")

    def test_rename_is_an_alias_of_copy(self):
        row = {"legacy_name": "Ada"}
        copied, copy_errors = value("new_name", "copy", "legacy_name", row=dict(row))
        renamed, rename_errors = value("new_name", "rename", "legacy_name", row=dict(row))

        self.assertEqual("Ada", renamed)
        self.assertEqual(copied, renamed)
        self.assertEqual([], copy_errors)
        self.assertEqual([], rename_errors)


class TestConcat(unittest.TestCase):
    def test_joins_parts_as_strings(self):
        got, errors = value(
            "out",
            "concat",
            "first",
            " ",
            "last",
            row={"first": "Ada", "last": "Lovelace"},
        )
        self.assertEqual("Ada Lovelace", got)
        self.assertEqual([], errors)

    def test_renders_none_as_empty_string(self):
        got, errors = value(
            "out",
            "concat",
            "first",
            "middle",
            "last",
            row={"first": "Ada", "middle": None, "last": "Lovelace"},
        )
        self.assertEqual("AdaLovelace", got)
        self.assertEqual([], errors, "a null part renders as '' -- it is not an error")

    def test_stringifies_non_string_parts(self):
        got, errors = value(
            "out", "concat", "id", "-", "n", row={"id": "A", "n": 2599}
        )
        self.assertEqual("A-2599", got)
        self.assertEqual([], errors)

    def test_single_part(self):
        got, _ = value("out", "concat", "a", row={"a": "solo"})
        self.assertEqual("solo", got)


class TestSubstring(unittest.TestCase):
    def test_start_and_end_are_a_python_slice(self):
        got, errors = value(
            "out", "substring", "ts", 0, 10, row={"ts": "2026-07-10T14:22:11Z"}
        )
        self.assertEqual("2026-07-10", got)
        self.assertEqual([], errors)

    def test_end_is_optional(self):
        got, errors = value(
            "out", "substring", "ts", 11, row={"ts": "2026-07-10T14:22:11Z"}
        )
        self.assertEqual("14:22:11Z", got)
        self.assertEqual([], errors)

    def test_negative_indices_slice_from_the_end(self):
        got, _ = value("out", "substring", "s", -4, row={"s": "abcdefgh"})
        self.assertEqual("efgh", got)

    def test_coerces_the_subject_to_string_first(self):
        # substring(s, ...) is str(s)[start:end] -- a non-string subject is
        # stringified, not an error.
        got, errors = value("out", "substring", "n", 0, 2, row={"n": 2599})
        self.assertEqual("25", got)
        self.assertEqual([], errors)


class TestCast(ErrorShapeMixin, unittest.TestCase):
    def test_cast_to_int(self):
        got, errors = value("out", "cast", "v", "int", row={"v": "2599"})
        self.assertEqual(2599, got)
        self.assertIsInstance(got, int)
        self.assertEqual([], errors)

    def test_cast_to_float(self):
        got, errors = value("out", "cast", "v", "float", row={"v": "25.5"})
        self.assertEqual(25.5, got)
        self.assertIsInstance(got, float)
        self.assertEqual([], errors)

    def test_cast_to_string(self):
        got, errors = value("out", "cast", "v", "string", row={"v": 2599})
        self.assertEqual("2599", got)
        self.assertIsInstance(got, str)
        self.assertEqual([], errors)

    def test_cast_to_int_goes_through_int_not_through_float(self):
        # `via str/int/float` is literal: int("25.99") is a ValueError, so the
        # field is nulled and the error captured. An engine that routed the
        # cast through float() would silently truncate this to 25 and lose
        # data without telling anyone.
        output_rows, errors = apply_ir(
            one_op_ir("out", "cast", "v", "int"), [{"v": "25.99"}]
        )

        self.assertEqual([{"out": None}], output_rows)
        self.assertErrorsMatch(errors, [(0, "out")])

    def test_cast_of_a_float_value_to_int_truncates(self):
        # int(25.99) is 25 -- truncating a real float is not an error.
        got, errors = value("out", "cast", "v", "int", row={"v": 25.99})

        self.assertEqual(25, got)
        self.assertEqual([], errors)

    def test_failed_cast_is_captured_not_raised(self):
        output_rows, errors = apply_ir(
            one_op_ir("out", "cast", "v", "int"), [{"v": "not-a-number"}]
        )

        self.assertEqual([{"out": None}], output_rows)
        self.assertErrorsMatch(errors, [(0, "out")])


class TestArithmetic(ErrorShapeMixin, unittest.TestCase):
    ROW = {"a": 7, "b": 2}

    def test_add(self):
        got, errors = value("out", "add", "a", "b", row=dict(self.ROW))
        self.assertEqual(9, got)
        self.assertEqual([], errors)

    def test_subtract(self):
        got, errors = value("out", "subtract", "a", "b", row=dict(self.ROW))
        self.assertEqual(5, got)
        self.assertEqual([], errors)

    def test_multiply(self):
        got, errors = value("out", "multiply", "a", "b", row=dict(self.ROW))
        self.assertEqual(14, got)
        self.assertEqual([], errors)

    def test_divide_is_true_division(self):
        # Not floor division: 7 / 2 is 3.5.
        got, errors = value("out", "divide", "a", "b", row=dict(self.ROW))
        self.assertEqual(3.5, got)
        self.assertIsInstance(got, float)
        self.assertEqual([], errors)

    def test_arithmetic_accepts_literal_operands(self):
        got, _ = value("out", "multiply", "a", 3, row={"a": 4})
        self.assertEqual(12, got)

    def test_divide_by_zero_is_captured_not_raised(self):
        output_rows, errors = apply_ir(
            one_op_ir("out", "divide", "a", "b"), [{"a": 10, "b": 0}]
        )

        self.assertEqual([{"out": None}], output_rows)
        self.assertErrorsMatch(errors, [(0, "out")])

    def test_divide_by_a_zero_literal_is_captured_not_raised(self):
        output_rows, errors = apply_ir(one_op_ir("out", "divide", "a", 0), [{"a": 10}])

        self.assertEqual([{"out": None}], output_rows)
        self.assertErrorsMatch(errors, [(0, "out")])


class TestToDate(ErrorShapeMixin, unittest.TestCase):
    def test_parses_iso_8601_with_trailing_z(self):
        got, errors = value("out", "to_date", "ts", row={"ts": "2026-07-10T14:22:11Z"})
        self.assertEqual("2026-07-10", got)
        self.assertEqual([], errors)

    def test_parses_iso_8601_with_an_explicit_offset(self):
        got, errors = value(
            "out", "to_date", "ts", row={"ts": "2026-07-10T14:22:11+00:00"}
        )
        self.assertEqual("2026-07-10", got)
        self.assertEqual([], errors)

    def test_parses_a_bare_iso_date(self):
        got, errors = value("out", "to_date", "ts", row={"ts": "2026-07-10"})
        self.assertEqual("2026-07-10", got)
        self.assertEqual([], errors)

    def test_returns_the_yyyy_mm_dd_string_not_a_date_object(self):
        got, _ = value("out", "to_date", "ts", row={"ts": "2026-07-10T14:22:11Z"})
        self.assertIsInstance(got, str)

    def test_unparseable_input_is_captured_not_raised(self):
        for bad in ("not-a-date", "10/07/2026", ""):
            with self.subTest(bad=bad):
                output_rows, errors = apply_ir(
                    one_op_ir("out", "to_date", "ts"), [{"ts": bad}]
                )
                self.assertEqual([{"out": None}], output_rows)
                self.assertErrorsMatch(errors, [(0, "out")])


class TestComparisons(unittest.TestCase):
    ROW = {"a": 5, "b": 5, "c": 9, "status": "paid"}

    def _cmp(self, op, *args):
        got, errors = value("out", op, *args, row=dict(self.ROW))
        self.assertEqual([], errors)
        self.assertIsInstance(got, bool, f"{op} must return a real bool")
        return got

    def test_equals(self):
        self.assertIs(True, self._cmp("equals", "a", "b"))
        self.assertIs(False, self._cmp("equals", "a", "c"))

    def test_equals_against_a_string_literal(self):
        self.assertIs(True, self._cmp("equals", "status", "paid"))
        self.assertIs(False, self._cmp("equals", "status", "pending"))

    def test_not_equals(self):
        self.assertIs(False, self._cmp("not_equals", "a", "b"))
        self.assertIs(True, self._cmp("not_equals", "a", "c"))

    def test_greater_than_is_strict(self):
        self.assertIs(True, self._cmp("greater_than", "c", "a"))
        self.assertIs(False, self._cmp("greater_than", "a", "b"))

    def test_less_than_is_strict(self):
        self.assertIs(True, self._cmp("less_than", "a", "c"))
        self.assertIs(False, self._cmp("less_than", "a", "b"))

    def test_greater_equal_includes_the_boundary(self):
        self.assertIs(True, self._cmp("greater_equal", "a", "b"))
        self.assertIs(True, self._cmp("greater_equal", "c", "a"))
        self.assertIs(False, self._cmp("greater_equal", "a", "c"))

    def test_less_equal_includes_the_boundary(self):
        self.assertIs(True, self._cmp("less_equal", "a", "b"))
        self.assertIs(True, self._cmp("less_equal", "a", "c"))
        self.assertIs(False, self._cmp("less_equal", "c", "a"))


class TestHash(unittest.TestCase):
    def test_is_unsalted_sha256_of_the_utf8_string(self):
        got, errors = value("out", "hash", "v", row={"v": "A1001"})

        self.assertEqual(hashlib.sha256(b"A1001").hexdigest(), got)
        self.assertEqual([], errors)

    def test_stringifies_before_hashing(self):
        got, _ = value("out", "hash", "n", row={"n": 2599})
        self.assertEqual(hashlib.sha256(b"2599").hexdigest(), got)

    def test_handles_non_ascii(self):
        got, _ = value("out", "hash", "v", row={"v": "Ada Lovelace — é"})
        expected = hashlib.sha256("Ada Lovelace — é".encode("utf-8")).hexdigest()
        self.assertEqual(expected, got)

    def test_is_a_64_char_lowercase_hexdigest(self):
        got, _ = value("out", "hash", "v", row={"v": "A1001"})

        self.assertIsInstance(got, str)
        self.assertEqual(64, len(got))
        self.assertEqual(got.lower(), got)
        int(got, 16)  # raises if it is not hex

    def test_is_deterministic_across_rows(self):
        output_rows, _ = apply_ir(
            one_op_ir("out", "hash", "v"), [{"v": "same"}, {"v": "same"}]
        )
        self.assertEqual(output_rows[0]["out"], output_rows[1]["out"])


if __name__ == "__main__":
    unittest.main()
