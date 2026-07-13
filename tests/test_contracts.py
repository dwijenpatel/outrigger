"""Contract-envelope guard (T11, tools/CONTRACTS.md).

Each golden in tools/contracts-golden/ is one canonical current-major instance
of an envelope. These tests are the drift alarm: an envelope-shape change that
does not update its golden in the same commit fails here. Shape only — values
(shas, timestamps, paths) are the producing tool's business.

Run: python3 -m unittest tests.test_contracts -q
"""

import json
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOLDEN = os.path.join(ROOT, "tools", "contracts-golden")


def load(name):
    with open(os.path.join(GOLDEN, name), encoding="utf-8") as fh:
        return json.load(fh)


class GoldenEnvelopes(unittest.TestCase):
    def test_gate_report(self):
        r = load("gate-report.golden.json")
        self.assertEqual(r["contract"], 1)
        self.assertEqual(r["tool"], "merge-gate")
        for key in ("ok", "ts", "repo", "base", "source", "merge", "checks"):
            self.assertIn(key, r)
        for side in ("base", "source"):
            self.assertIn("ref", r[side])
            self.assertIn("sha", r[side])

    def test_ledger_record(self):
        r = load("ledger-record.golden.json")
        self.assertEqual(r["contract"], 1)
        for key in ("ts", "kind", "subject", "data"):
            self.assertIn(key, r)
        self.assertIsInstance(r["data"], dict)

    def test_launcher_params(self):
        p = load("launcher-params.golden.json")
        self.assertEqual(p["contract"], 1)
        for key in ("role", "worker", "isolation", "cwd", "timeout_s"):
            self.assertIn(key, p)
        self.assertIn("tool", p["worker"])
        self.assertIn("model", p["worker"])
        for key in ("deny_read", "sandbox", "network"):
            self.assertIn(key, p["isolation"])

    def test_launcher_result(self):
        r = load("launcher-result.golden.json")
        self.assertEqual(r["contract"], 1)
        for key in ("ok", "exit", "started_at", "finished_at"):
            self.assertIn(key, r)


if __name__ == "__main__":
    unittest.main(verbosity=2)
