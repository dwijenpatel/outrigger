"""run-ledger tests — envelope validation, durability semantics, races.

Run: python3 tools/run-ledger/test_ledger.py
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(HERE, "ledger.py")
sys.path.insert(0, HERE)

import ledger  # noqa: E402


def run_cli(*argv, stdin=None):
    return subprocess.run(
        [sys.executable, LEDGER, *argv],
        capture_output=True,
        text=True,
        input=stdin,
    )


class EnvelopeTests(unittest.TestCase):
    def test_valid_record_passes(self):
        rec = {"ts": "2026-07-11T00:00:00Z", "kind": "note", "subject": "x", "data": {}}
        self.assertEqual(ledger.validate_record(rec), [])

    def test_missing_required_and_unknown_keys_flagged(self):
        problems = ledger.validate_record({"kind": "note", "extra": 1})
        text = "; ".join(problems)
        self.assertIn("missing required key: ts", text)
        self.assertIn("missing required key: subject", text)
        self.assertIn("missing required key: data", text)
        self.assertIn("unknown top-level key(s): extra", text)

    def test_bad_types_flagged(self):
        problems = ledger.validate_record(
            {"ts": "not-a-time", "kind": " ", "subject": "s", "data": []}
        )
        text = "; ".join(problems)
        self.assertIn("ts is not RFC3339", text)
        self.assertIn("kind must be a non-empty string", text)
        self.assertIn("data must be a JSON object", text)


class CliTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.dir.name, "ledger.jsonl")

    def tearDown(self):
        self.dir.cleanup()

    def append(self, *extra, expect=0, stdin=None):
        proc = run_cli("append", self.path, *extra, stdin=stdin)
        self.assertEqual(proc.returncode, expect, proc.stderr)
        return proc

    def test_append_stamps_ts_and_echoes_record(self):
        proc = self.append("--kind", "note", "--subject", "s")
        rec = json.loads(proc.stdout)
        self.assertEqual(rec["kind"], "note")
        self.assertEqual(rec["data"], {})
        ledger.parse_ts(rec["ts"])  # parseable
        with open(self.path) as fh:
            self.assertEqual(json.loads(fh.read()), rec)

    def test_ts_override_and_data_stdin(self):
        proc = self.append(
            "--kind", "measurement", "--subject", "t1/arm-a",
            "--ts", "2026-07-11T01:02:03Z", "--data", "-",
            stdin='{"total_cache_read_tokens": 3289}',
        )
        rec = json.loads(proc.stdout)
        self.assertEqual(rec["ts"], "2026-07-11T01:02:03Z")
        self.assertEqual(rec["data"]["total_cache_read_tokens"], 3289)

    def test_append_rejects_bad_data_without_writing(self):
        self.append("--kind", "k", "--subject", "s", "--data", "{not json", expect=2)
        self.assertFalse(os.path.exists(self.path))

    def test_check_ok_then_flags_corrupt_middle_line(self):
        self.append("--kind", "a", "--subject", "s1")
        self.append("--kind", "b", "--subject", "s2")
        self.assertEqual(run_cli("check", self.path).returncode, 0)

        with open(self.path) as fh:
            lines = fh.readlines()
        lines.insert(1, "{corrupt\n")
        with open(self.path, "w") as fh:
            fh.writelines(lines)

        proc = run_cli("check", self.path)
        self.assertEqual(proc.returncode, 1)
        report = json.loads(proc.stdout)
        self.assertFalse(report["ok"])
        problem = report["files"][self.path]["problems"][0]
        self.assertEqual(problem["line"], 2)
        self.assertFalse(problem["torn_tail"])

    def test_torn_tail_detected_distinctly(self):
        self.append("--kind", "a", "--subject", "s")
        with open(self.path, "a") as fh:
            fh.write('{"ts": "2026-07-11T00:00:00Z", "kind": "b"')  # no newline, cut mid-record
        proc = run_cli("check", self.path)
        self.assertEqual(proc.returncode, 1)
        report = json.loads(proc.stdout)
        [problem] = report["files"][self.path]["problems"]
        self.assertTrue(problem["torn_tail"])

    def test_summarize_tolerant_counts_and_range(self):
        self.append("--kind", "run", "--subject", "gate", "--ts", "2026-07-11T00:00:00Z")
        self.append("--kind", "run", "--subject", "gate", "--ts", "2026-07-11T02:00:00Z")
        self.append("--kind", "note", "--subject", "misc", "--ts", "2026-07-11T01:00:00Z")
        with open(self.path, "a") as fh:
            fh.write("garbage\n")
        proc = run_cli("summarize", self.path)
        self.assertEqual(proc.returncode, 1)  # invalid line present -> nonzero, still summarizes
        summary = json.loads(proc.stdout)
        self.assertEqual(summary["records"], 3)
        self.assertEqual(summary["invalid_lines"], 1)
        self.assertEqual(summary["by_kind"], {"note": 1, "run": 2})
        self.assertEqual(summary["ts_min"], "2026-07-11T00:00:00Z")
        self.assertEqual(summary["ts_max"], "2026-07-11T02:00:00Z")

    def test_concurrent_appends_do_not_interleave_or_drop(self):
        procs = [
            subprocess.Popen(
                [sys.executable, LEDGER, "append", self.path,
                 "--kind", "race", "--subject", f"writer-{i}",
                 "--data", json.dumps({"payload": "x" * 2000})],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            for i in range(10)
        ]
        for proc in procs:
            self.assertEqual(proc.wait(), 0)
        check = run_cli("check", self.path)
        self.assertEqual(check.returncode, 0, check.stdout)
        report = json.loads(check.stdout)
        self.assertEqual(report["records"], 10)
        with open(self.path) as fh:
            subjects = sorted(json.loads(line)["subject"] for line in fh)
        self.assertEqual(subjects, sorted(f"writer-{i}" for i in range(10)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
