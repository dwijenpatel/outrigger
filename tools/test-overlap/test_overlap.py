#!/usr/bin/env python3
"""Tests for test-overlap. Run: python3 tools/test-overlap/test_overlap.py"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import overlap  # noqa: E402


class GenMutants(unittest.TestCase):
    def _descs(self, source, fname="m.py"):
        return [d for (d, _s) in overlap.gen_mutants(source, fname)]

    def test_compare_swaps(self):
        muts = overlap.gen_mutants("def f(a, b):\n    return a < b\n", "m.py")
        descs = [d for d, _ in muts]
        # CMP[Lt] = [LtE, Gt]
        self.assertEqual(len(muts), 2)
        self.assertTrue(any("Lt->LtE" in d for d in descs))
        self.assertTrue(any("Lt->Gt" in d for d in descs))
        for _d, src2 in muts:
            self.assertNotEqual(src2, "def f(a, b):\n    return a < b\n")

    def test_arithmetic_swap(self):
        self.assertTrue(any("Add->Sub" in d for d in self._descs("z = a + b\n")))

    def test_boolean_swap(self):
        self.assertTrue(any("And->Or" in d for d in self._descs("z = a and b\n")))

    def test_const_and_bool(self):
        # x=1 -> {2, 0}; y=True -> {False}
        descs = self._descs("x = 1\ny = True\n")
        self.assertTrue(any("1->2" in d for d in descs))
        self.assertTrue(any("1->0" in d for d in descs))
        self.assertTrue(any("True->False" in d for d in descs))

    def test_zero_const_no_zero_to_zero(self):
        descs = self._descs("x = 0\n")
        self.assertTrue(any("0->1" in d for d in descs))
        self.assertFalse(any("0->0" in d for d in descs))

    def test_drop_not(self):
        muts = overlap.gen_mutants("def g(a):\n    return not a\n", "m.py")
        self.assertEqual(len(muts), 1)
        desc, src2 = muts[0]
        self.assertIn("drop-not", desc)
        self.assertIn("return a", src2)
        self.assertNotIn("not a", src2)

    def test_single_point_only(self):
        # two comparisons: mutating one must leave the other intact
        muts = overlap.gen_mutants("def f(a, b, c):\n    return a < b or b < c\n", "m.py")
        # each Lt yields 2 swaps -> 4 mutants; plus the BoolOp Or->And -> 5
        self.assertEqual(len(muts), 5)
        for _d, src2 in muts:
            # exactly one of the three operators changed; the source still parses
            self.assertTrue(src2.count("<") + src2.count(">") == 2)


class ResolveSuite(unittest.TestCase):
    def test_internal_vs_external(self):
        with tempfile.TemporaryDirectory() as repo, tempfile.TemporaryDirectory() as checkout:
            start, top, kind = overlap.resolve_suite(checkout, repo, "tests")
            self.assertEqual(kind, "internal")
            self.assertEqual(top, checkout)
            self.assertTrue(start.startswith(checkout))
            with tempfile.TemporaryDirectory() as outside:
                s2, t2, k2 = overlap.resolve_suite(checkout, repo, outside)
                self.assertEqual(k2, "external")
                self.assertEqual(s2, t2)
                self.assertEqual(s2, os.path.abspath(outside))


class EndToEndDifferential(unittest.TestCase):
    """A boundary-testing held suite catches a `<=`->`<` mutant that a self suite
    which never tests the boundary lets pass. Proves the differential machinery."""

    def _build(self, root):
        pkg = os.path.join(root, "mini")
        tests = os.path.join(root, "tests")
        os.makedirs(pkg)
        os.makedirs(tests)
        overlap._write(os.path.join(pkg, "__init__.py"), "from .core import f as f\n")
        overlap._write(os.path.join(pkg, "core.py"), "def f(a, b):\n    return a <= b\n")
        overlap._write(os.path.join(tests, "__init__.py"), "")
        overlap._write(os.path.join(tests, "test_self.py"),
                       "import unittest\nfrom mini import f\n"
                       "class T(unittest.TestCase):\n"
                       "    def test_lt(self): self.assertTrue(f(1, 2))\n")

    def test_boundary_is_held_only(self):
        with tempfile.TemporaryDirectory() as repo, tempfile.TemporaryDirectory() as held:
            self._build(repo)
            overlap._write(os.path.join(held, "test_held.py"),
                           "import unittest\nfrom mini import f\n"
                           "class T(unittest.TestCase):\n"
                           "    def test_lt(self): self.assertTrue(f(1, 2))\n"
                           "    def test_eq(self): self.assertTrue(f(2, 2))\n")
            report = overlap.measure(repo, "mini", ("self", "tests"), ("held", held),
                                     mutate_files=["core.py"], timeout=30)
            self.assertTrue(report["pristine"]["ok"], report["pristine"])
            self.assertIn("line_reach", report)
            m = report["mutation"]
            # LtE -> Lt : self survives (only tests 1<2), held catches (2<=2 now False)
            # LtE -> GtE: self catches (1>=2 False), held catches too -> both
            self.assertEqual(m["valid"], 2)
            self.assertEqual(m["caught_only_by_held"], 1)
            self.assertEqual(m["caught_only_by_self"], 0)
            self.assertEqual(m["caught_by_both"], 1)
            self.assertEqual(m["caught_by_neither"], 0)
            self.assertTrue(any("LtE->Lt" in d for d in m["examples"]["only_held"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
