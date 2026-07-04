"""Tests for harness.vault (D1/C4) and harness.selftest (C5)."""

import json
import os
import stat
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import selftest, vault


class IsolationConfigTests(unittest.TestCase):
    def test_settings_fragment_covers_layers_1_to_3(self):
        frag = vault.isolation_settings(".vault")
        self.assertIn("Read(.vault/**)", frag["permissions"]["deny"])
        self.assertEqual(frag["sandbox"]["denyRead"], [".vault"])
        self.assertFalse(frag["sandbox"]["allowUnsandboxedCommands"])
        self.assertTrue(frag["sandbox"]["failIfUnavailable"])

    def test_suspicious_vault_path_rejected(self):
        for path in ("", "../outside", "a/../b"):
            with self.assertRaises(vault.VaultError):
                vault.isolation_settings(path)

    def test_validate_isolation_reports_missing_layers(self):
        missing = vault.validate_isolation({})
        self.assertEqual(set(missing), set(vault.REQUIRED_LAYERS))

    def test_committed_declaration_is_complete(self):
        cfg = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "harness", "config",
            "vault-isolation.json")
        with open(cfg) as fh:
            doc = json.load(fh)
        self.assertEqual(vault.validate_isolation(doc), [])

    def test_strict_flags_must_be_exact(self):
        doc = {"worker_settings": vault.isolation_settings(".vault"),
               "structural_layers": {k: "yes" for k in
                                     ("config_out_of_scope", "egress_control",
                                      "role_processes")}}
        self.assertEqual(vault.validate_isolation(doc), [])
        doc["worker_settings"]["sandbox"]["allowUnsandboxedCommands"] = True
        self.assertIn("strict_flags", vault.validate_isolation(doc))


class CanaryTests(unittest.TestCase):
    def test_readable_vault_is_detected_as_broken(self):
        with tempfile.TemporaryDirectory() as root:
            vdir = os.path.join(root, "v")
            vault.write_canary(vdir)
            got = vault.canary_read_attempt(vdir)
            self.assertFalse(got["isolation_ok"])
            self.assertIn("READABLE", got["detail"])

    def test_denied_vault_passes(self):
        with tempfile.TemporaryDirectory() as root:
            vdir = os.path.join(root, "v")
            vault.write_canary(vdir)
            os.chmod(vdir, 0)
            try:
                got = vault.canary_read_attempt(vdir)
            finally:
                os.chmod(vdir, stat.S_IRWXU)
            self.assertTrue(got["isolation_ok"])

    def test_missing_vault_reads_as_isolated_not_crash(self):
        got = vault.canary_read_attempt("/nonexistent/vault")
        self.assertTrue(got["isolation_ok"])


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.vdir = os.path.join(self.dir.name, "vault")
        vault.write_canary(self.vdir)
        self._write("tests/test_a.py", "def test_a(): pass\n")
        self._write("tests/test_b.py", "def test_b(): pass\n")

    def tearDown(self):
        self.dir.cleanup()

    def _write(self, rel, content):
        path = os.path.join(self.vdir, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write(content)

    def test_manifest_excludes_canary_and_itself(self):
        entries = vault.build_manifest(self.vdir)
        vault.save_manifest(self.vdir, entries)
        again = vault.build_manifest(self.vdir)
        self.assertEqual(set(again), {"tests/test_a.py", "tests/test_b.py"})

    def test_intact_corpus_passes(self):
        entries = vault.build_manifest(self.vdir)
        vault.save_manifest(self.vdir, entries)
        got = vault.check_heldout_drop(vault.load_manifest(self.vdir),
                                       vault.build_manifest(self.vdir))
        self.assertTrue(got["ok"])

    def test_dropped_test_blocks(self):
        vault.save_manifest(self.vdir, vault.build_manifest(self.vdir))
        os.unlink(os.path.join(self.vdir, "tests/test_b.py"))
        got = vault.check_heldout_drop(vault.load_manifest(self.vdir),
                                       vault.build_manifest(self.vdir))
        self.assertFalse(got["ok"])
        self.assertEqual(got["dropped"], ["tests/test_b.py"])

    def test_mutated_test_blocks(self):
        vault.save_manifest(self.vdir, vault.build_manifest(self.vdir))
        self._write("tests/test_a.py", "def test_a(): assert False  # weakened\n")
        got = vault.check_heldout_drop(vault.load_manifest(self.vdir),
                                       vault.build_manifest(self.vdir))
        self.assertFalse(got["ok"])
        self.assertEqual(got["mutated"], ["tests/test_a.py"])

    def test_fresh_authoring_grows_the_corpus_fine(self):
        vault.save_manifest(self.vdir, vault.build_manifest(self.vdir))
        self._write("tests/test_c.py", "def test_c(): pass\n")
        got = vault.check_heldout_drop(vault.load_manifest(self.vdir),
                                       vault.build_manifest(self.vdir))
        self.assertTrue(got["ok"])
        self.assertEqual(got["added"], ["tests/test_c.py"])

    def test_missing_manifest_is_loud(self):
        with self.assertRaises(vault.VaultError):
            vault.load_manifest(self.vdir)


class SelfTestHarnessTests(unittest.TestCase):
    def test_every_gate_proves_both_directions(self):
        report = selftest.run_selftests()
        failures = [c for c in report["cases"] if not c["ok"]]
        self.assertEqual(failures, [], failures)
        self.assertTrue(report["ok"])
        # sanity: the suite exercises all gates + canary + declaration
        names = " ".join(c["case"] for c in report["cases"])
        for token in ("C1", "C2", "C3", "C4", "canary", "six layers"):
            self.assertIn(token, names)


if __name__ == "__main__":
    unittest.main()


class EvidenceLeakageTests(unittest.TestCase):
    """H7 — held-out content must not exit via evidence artifacts."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.vault_dir = os.path.join(self.dir.name, ".vault")
        vault.write_canary(self.vault_dir)
        with open(os.path.join(self.vault_dir, "test_holdout_secret.py"),
                  "w") as fh:
            fh.write("def test_hidden(): assert True\n")
        vault.save_manifest(self.vault_dir,
                            vault.build_manifest(self.vault_dir))

    def tearDown(self):
        self.dir.cleanup()

    def test_evidence_dir_lives_inside_the_vault(self):
        path = vault.heldout_evidence_dir(self.vault_dir)
        self.assertTrue(path.startswith(self.vault_dir))
        self.assertTrue(os.path.isdir(path))

    def test_evidence_dir_excluded_from_manifest_and_drop_check(self):
        recorded = vault.load_manifest(self.vault_dir)
        evidence = vault.heldout_evidence_dir(self.vault_dir)
        with open(os.path.join(evidence, "run-1.log"), "w") as fh:
            fh.write("held-out execution output\n")
        current = vault.build_manifest(self.vault_dir)
        self.assertEqual(recorded, current)  # evidence never trips C4
        self.assertTrue(vault.check_heldout_drop(recorded, current)["ok"])

    def test_scrub_replaces_paths_basenames_and_stems(self):
        entries = vault.load_manifest(self.vault_dir)
        text = ("FAIL: test_hidden (test_holdout_secret.TestX) — see "
                "test_holdout_secret.py; module test_holdout_secret leaked")
        scrubbed = vault.scrub(text, entries)
        self.assertNotIn("test_holdout_secret", scrubbed)
        self.assertIn("vault:", scrubbed)
        # behavior-level text survives
        self.assertIn("FAIL: test_hidden", scrubbed)

    def test_scrub_for_repo_tolerates_missing_manifest(self):
        text = "nothing to scrub"
        self.assertEqual(
            vault.scrub_for_repo(text, os.path.join(self.dir.name, "ghost")),
            text)

    def test_verdict_verbosity_counts_identifier_mentions(self):
        entries = vault.load_manifest(self.vault_dir)
        verdicts = [
            {"lens": "correctness", "verdict": "FAIL",
             "evidence": ["test_holdout_secret.py failed on tenant B"],
             "intent": "t"},
            {"lens": "security", "verdict": "PASS",
             "evidence": ["ran the abuse suite"], "intent": "t"},
        ]
        got = vault.verdict_verbosity(verdicts, entries)
        self.assertEqual(got["mentions"], 1)
        self.assertEqual(got["by_lens"]["correctness"], 1)
        self.assertEqual(got["by_lens"]["security"], 0)
        self.assertIn("scrub", got["why"])
        clean = vault.verdict_verbosity(
            [{"lens": "a", "verdict": "PASS", "evidence": ["ok"],
              "intent": "t"}], entries)
        self.assertEqual(clean["mentions"], 0)
