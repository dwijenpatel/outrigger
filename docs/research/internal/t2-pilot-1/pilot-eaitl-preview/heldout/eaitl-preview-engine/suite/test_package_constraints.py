"""Package-level constraints: layout, and a stdlib-only runtime.

The base repo needs no install step for the code to run -- `eaitl`'s runtime
imports must all come from the Python 3 standard library.
"""

import ast
import pathlib
import sys
import unittest

import eaitl


class TestLayout(unittest.TestCase):
    def test_eaitl_is_a_package(self):
        self.assertTrue(hasattr(eaitl, "__path__"), "eaitl must be a package, not a module")

    def test_package_has_an_init_module(self):
        init = pathlib.Path(eaitl.__file__).resolve()
        self.assertEqual("__init__.py", init.name)
        self.assertTrue(init.is_file())


class TestRuntimeIsStdlibOnly(unittest.TestCase):
    def _package_sources(self):
        root = pathlib.Path(eaitl.__file__).resolve().parent
        return sorted(root.rglob("*.py"))

    def _imported_top_level_modules(self, path):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        found = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    found.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                # level > 0 is a relative (intra-package) import.
                if node.level == 0 and node.module:
                    found.add(node.module.split(".")[0])
        return found

    def test_at_least_one_source_file_is_present(self):
        self.assertTrue(self._package_sources(), "eaitl has no Python sources")

    @unittest.skipUnless(
        hasattr(sys, "stdlib_module_names"), "needs Python 3.10+ for stdlib_module_names"
    )
    def test_no_third_party_runtime_imports(self):
        stdlib = set(sys.stdlib_module_names)
        offenders = {}
        for path in self._package_sources():
            for module in self._imported_top_level_modules(path):
                if module == "eaitl" or module in stdlib:
                    continue
                offenders.setdefault(path.name, set()).add(module)

        self.assertEqual(
            {},
            offenders,
            f"eaitl's runtime must import only the standard library; found: {offenders}",
        )


if __name__ == "__main__":
    unittest.main()
