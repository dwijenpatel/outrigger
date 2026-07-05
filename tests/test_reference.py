"""I3 — the reference page stays honest: every documented name must exist."""

import importlib
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

REF = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "docs", "reference.md")


class ReferenceHonestyTests(unittest.TestCase):
    def test_every_documented_symbol_resolves(self):
        with open(REF) as fh:
            body = fh.read()
        symbols = set(re.findall(r"harness\.([a-z_]+)\.([A-Za-z_]+)", body))
        self.assertGreater(len(symbols), 40, "reference lost its content?")
        missing = []
        for mod_name, attr in sorted(symbols):
            try:
                mod = importlib.import_module(f"harness.{mod_name}")
            except ImportError:
                missing.append(f"harness.{mod_name} (module)")
                continue
            if not hasattr(mod, attr):
                missing.append(f"harness.{mod_name}.{attr}")
        self.assertEqual(missing, [],
                         "reference.md documents names that do not exist — "
                         "update the page with the code: " + ", ".join(missing))

    def test_every_documented_cli_module_runs(self):
        with open(REF) as fh:
            body = fh.read()
        for mod_name in set(re.findall(r"python3 -m harness\.([a-z_]+)", body)):
            mod = importlib.import_module(f"harness.{mod_name}")
            path = getattr(mod, "__file__", "")
            with open(path) as fh:
                src = fh.read()
            self.assertIn("__main__", src,
                          f"harness.{mod_name} documented as a CLI but has "
                          f"no __main__ guard")


if __name__ == "__main__":
    unittest.main()
