"""Tests for harness.planning (I2) — plan readiness + content-bound ratification."""

import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import closure, ledger as ledger_mod, planning
from harness.planning import PlanningError

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SPEC_BODY = (
    "## Scope\nTenant-scoped customer records.\n\n"
    "## Interfaces\n`POST /customers` `{name, phone}` -> 201 `{id}`.\n\n"
    "## Acceptance criteria\n- tenant B cannot read tenant A's customers\n"
    "- empty name -> 422 with field error\n\n## Non-goals\nSearch, import.\n")


def tasks_doc():
    return {"tasks": [
        {"id": "t1", "phase": "p1", "profile": "critical", "deps": []},
        {"id": "t2", "phase": "p1", "profile": "routine", "deps": ["t1"]},
    ]}


class PlanFixture(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.plan = os.path.join(self.dir.name, "plan")
        os.makedirs(os.path.join(self.plan, "specs"))
        with open(os.path.join(self.plan, "tasks.json"), "w") as fh:
            json.dump(tasks_doc(), fh)
        for tid in ("t1", "t2"):
            with open(os.path.join(self.plan, "specs", f"{tid}.md"), "w") as fh:
                fh.write(SPEC_BODY)
        with open(os.path.join(self.plan, "floors.json"), "w") as fh:
            json.dump({"floors": [{"glob": "pilot/**/auth/**",
                                   "min_profile": "critical"}]}, fh)
        self.snapshot = os.path.join(self.dir.name, "snapshot.json")
        closure.freeze_snapshot(
            ledger_mod.Ledger(ledger_mod.validate_tasks(tasks_doc())),
            self.snapshot)

    def tearDown(self):
        self.dir.cleanup()

    def ready(self):
        return planning.plan_ready(self.plan, self.snapshot)

    def failing_check(self, result):
        return next(c for c in result["checks"] if not c["ok"])


class PlanReadyTests(PlanFixture):
    def test_unratified_plan_not_ready(self):
        result = self.ready()
        self.assertFalse(result["ready"])
        self.assertEqual(self.failing_check(result)["check"], "ratification")
        self.assertIn("plan-build", self.failing_check(result)["detail"])

    def test_ratified_plan_ready(self):
        planning.ratify(self.plan, "dwijen")
        result = self.ready()
        self.assertTrue(result["ready"], result["why"])
        rat = next(c for c in result["checks"]
                   if c["check"] == "ratification")
        self.assertIn("approved by dwijen", rat["detail"])

    def test_edit_after_ratification_voids_it(self):
        planning.ratify(self.plan, "dwijen")
        with open(os.path.join(self.plan, "specs", "t1.md"), "a") as fh:
            fh.write("\n(edited after approval)\n")
        result = self.ready()
        self.assertFalse(result["ready"])
        self.assertIn("changed after ratification", result["why"])

    def test_missing_spec_blocks(self):
        os.unlink(os.path.join(self.plan, "specs", "t2.md"))
        result = self.ready()
        self.assertFalse(result["ready"])
        self.assertIn("no spec file", result["why"])
        self.assertIn("t2", result["why"])

    def test_thin_spec_blocks(self):
        with open(os.path.join(self.plan, "specs", "t2.md"), "w") as fh:
            fh.write("do the thing")
        result = self.ready()
        self.assertFalse(result["ready"])
        self.assertIn("too thin", result["why"])

    def test_missing_floors_blocks(self):
        os.unlink(os.path.join(self.plan, "floors.json"))
        result = self.ready()
        self.assertFalse(result["ready"])
        self.assertIn("risk floors are part of the plan", result["why"])

    def test_snapshot_ledger_drift_blocks(self):
        doc = tasks_doc()
        doc["tasks"].append({"id": "t3", "phase": "p1", "profile": "routine",
                             "deps": []})
        with open(os.path.join(self.plan, "tasks.json"), "w") as fh:
            json.dump(doc, fh)
        with open(os.path.join(self.plan, "specs", "t3.md"), "w") as fh:
            fh.write(SPEC_BODY)
        result = self.ready()
        self.assertFalse(result["ready"])
        self.assertIn("does not match tasks.json", result["why"])

    def test_missing_snapshot_blocks(self):
        os.unlink(self.snapshot)
        result = self.ready()
        self.assertFalse(result["ready"])
        self.assertIn("snapshot", result["why"])

    def test_malformed_ledger_blocks(self):
        with open(os.path.join(self.plan, "tasks.json"), "w") as fh:
            fh.write("not json")
        result = self.ready()
        self.assertFalse(result["ready"])
        self.assertEqual(self.failing_check(result)["check"], "ledger")


class RatifyTests(PlanFixture):
    def test_ratify_writes_content_bound_stamp(self):
        doc = planning.ratify(self.plan, "dwijen")
        self.assertEqual(doc["content_hash"], planning.content_hash(self.plan))
        self.assertEqual(doc["approved_by"], "dwijen")

    def test_ratify_refuses_blank_approver(self):
        with self.assertRaises(PlanningError):
            planning.ratify(self.plan, "  ")

    def test_ratify_refuses_malformed_plan(self):
        with open(os.path.join(self.plan, "tasks.json"), "w") as fh:
            fh.write("{}")
        with self.assertRaises((PlanningError, ledger_mod.LedgerError)):
            planning.ratify(self.plan, "dwijen")

    def test_stamp_itself_not_hashed(self):
        before = planning.content_hash(self.plan)
        planning.ratify(self.plan, "dwijen")
        self.assertEqual(planning.content_hash(self.plan), before)


class CliTests(PlanFixture):
    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, "-m", "harness.planning", *args],
            capture_output=True, text=True, timeout=30, cwd=REPO_ROOT)

    def test_ready_exit_codes(self):
        not_ready = self.run_cli("ready", "--plan-dir", self.plan,
                                 "--snapshot", self.snapshot)
        self.assertEqual(not_ready.returncode, 2)
        self.assertIn("plan NOT ready", not_ready.stderr)
        self.run_cli("ratify", "--plan-dir", self.plan,
                     "--approved-by", "dwijen")
        ready = self.run_cli("ready", "--plan-dir", self.plan,
                             "--snapshot", self.snapshot)
        self.assertEqual(ready.returncode, 0)


if __name__ == "__main__":
    unittest.main()


class VaultReadinessTests(PlanFixture):
    """I4b — a plan is not fireable against an unconfigured/absent vault."""

    def vault_cfg(self, configure=True):
        cfg = os.path.join(self.dir.name, "vault-isolation.json")
        with open(cfg, "w") as fh:
            json.dump({"_meta": {}, "structural_layers": {
                "config_out_of_scope": "x", "egress_control": "x",
                "role_processes": "x"},
                "vault_path": None, "worker_settings": None}, fh)
        if configure:
            import shutil
            from harness import vault
            vault_home = tempfile.mkdtemp(prefix="outside-vault-")
            self.addCleanup(lambda: shutil.rmtree(vault_home,
                                                  ignore_errors=True))
            vault.configure_vault(self.dir.name,
                                  os.path.join(vault_home, "vault"),
                                  config_path=cfg)
        return cfg

    def test_unconfigured_vault_blocks_readiness(self):
        planning.ratify(self.plan, "dwijen")
        cfg = self.vault_cfg(configure=False)
        result = planning.plan_ready(self.plan, self.snapshot,
                                     vault_config_path=cfg,
                                     repo_root=self.dir.name)
        self.assertFalse(result["ready"])
        self.assertIn("unconfigured", result["why"])

    def test_configured_vault_passes_readiness(self):
        planning.ratify(self.plan, "dwijen")
        cfg = self.vault_cfg(configure=True)
        result = planning.plan_ready(self.plan, self.snapshot,
                                     vault_config_path=cfg,
                                     repo_root=self.dir.name)
        self.assertTrue(result["ready"], result["why"])
        # I19: the gate preflight runs after (and only after) a coherent vault
        self.assertEqual([c["check"] for c in result["checks"][-2:]],
                         ["vault", "preflight"])

    def test_missing_vault_dir_blocks_readiness(self):
        import shutil
        planning.ratify(self.plan, "dwijen")
        cfg = self.vault_cfg(configure=True)
        from harness import vault
        doc = vault.load_vault_config(self.dir.name, cfg)
        shutil.rmtree(doc["vault_path"])
        result = planning.plan_ready(self.plan, self.snapshot,
                                     vault_config_path=cfg,
                                     repo_root=self.dir.name)
        self.assertFalse(result["ready"])
        self.assertIn("does not exist", result["why"])

    def test_no_vault_config_keeps_prior_behavior(self):
        planning.ratify(self.plan, "dwijen")
        result = planning.plan_ready(self.plan, self.snapshot)
        self.assertTrue(result["ready"], result["why"])


class PreflightTests(PlanFixture):
    """I19 (P3-2, P3v2-1) — both pilot-3 halts were statically foreseeable at
    (re-)ratification; the preflight makes the machine do that sweep."""

    HANDOFF = {"outcome": "pass", "summary": "authored held-out tests",
               "intent": "pin the contract", "key_changes_made": ["pins x"],
               "key_learnings": []}

    def set_touches(self, task_id, touches):
        path = os.path.join(self.plan, "tasks.json")
        with open(path) as fh:
            doc = json.load(fh)
        for t in doc["tasks"]:
            if t["id"] == task_id:
                t["touches"] = touches
        with open(path, "w") as fh:
            json.dump(doc, fh)

    def vault_with_handoff(self, task_id, ambiguities):
        vault = os.path.join(self.dir.name, "vault")
        os.makedirs(os.path.join(vault, "evidence"), exist_ok=True)
        cfg = os.path.join(self.dir.name, "vault-config.json")
        with open(cfg, "w") as fh:
            json.dump({"vault_path": vault}, fh)
        handoff = dict(self.HANDOFF, spec_ambiguities=ambiguities)
        name = f"{task_id}.test-author.handoff.json"
        with open(os.path.join(vault, "evidence", name), "w") as fh:
            json.dump(handoff, fh)
        return cfg

    def resolve_card(self, task_id):
        blockers = os.path.join(self.dir.name, "state", "blockers")
        os.makedirs(blockers, exist_ok=True)
        card = {"task_id": task_id, "kind": planning.H9_CARD_KIND,
                "repro": "10 ambiguities", "recommendation": "proceed",
                "options": [{"key": "a", "label": "A"},
                            {"key": "b", "label": "B"}],
                "resolved": {"decision": "proceed-as-read", "by": "op",
                             "at": "2026-07-05T20:40:45Z"}}
        with open(os.path.join(blockers, f"{task_id}-ambiguity.json"),
                  "w") as fh:
            json.dump(card, fh)

    # -- floors × touches -----------------------------------------------------

    def test_no_touches_skips_silently(self):
        pf = planning.gate_preflight(self.plan, repo_root=self.dir.name)
        self.assertTrue(pf["ok"])
        self.assertEqual(pf["findings"], [])

    def test_touches_floor_collision_is_fatal(self):
        # t2 is routine; the fixture floors pilot/**/auth/** at critical
        self.set_touches("t2", ["pilot/app/auth/login.py"])
        pf = planning.gate_preflight(self.plan, repo_root=self.dir.name)
        self.assertFalse(pf["ok"])
        f = pf["findings"][0]
        self.assertEqual((f["task_id"], f["kind"], f["fatal"]),
                         ("t2", "floor-collision", True))
        self.assertIn("WILL bounce", f["detail"])

    def test_touches_clear_of_floors_passes(self):
        self.set_touches("t2", ["pilot/app/views.py"])
        pf = planning.gate_preflight(self.plan, repo_root=self.dir.name)
        self.assertTrue(pf["ok"], pf["findings"])

    def test_malformed_touches_fatal(self):
        self.set_touches("t2", "app.py")
        pf = planning.gate_preflight(self.plan, repo_root=self.dir.name)
        self.assertFalse(pf["ok"])
        self.assertEqual(pf["findings"][0]["kind"], "touches-invalid")

    def test_plan_ready_fails_on_collision(self):
        self.set_touches("t2", ["pilot/app/auth/login.py"])
        planning.ratify(self.plan, "dwijen")
        result = planning.plan_ready(self.plan, self.snapshot,
                                     repo_root=self.dir.name)
        self.assertFalse(result["ready"])
        self.assertIn("preflight", result["why"])

    # -- H9 × existing handoffs -----------------------------------------------

    def test_unadjudicated_ambiguities_fatal(self):
        # t1 is critical (blocking); carried-over handoff has raw strings
        cfg = self.vault_with_handoff("t1", ["Is deletion soft or hard?"])
        pf = planning.gate_preflight(self.plan, vault_config_path=cfg,
                                     repo_root=self.dir.name)
        self.assertFalse(pf["ok"])
        f = pf["findings"][0]
        self.assertEqual((f["task_id"], f["kind"]), ("t1", "h9-will-park"))
        self.assertIn("WILL park", f["detail"])

    def test_resolved_card_adjudicates(self):
        cfg = self.vault_with_handoff("t1", ["Is deletion soft or hard?"])
        self.resolve_card("t1")
        pf = planning.gate_preflight(self.plan, vault_config_path=cfg,
                                     repo_root=self.dir.name)
        self.assertTrue(pf["ok"], pf["findings"])
        self.assertEqual(pf["findings"][0]["kind"], "h9-adjudicated")

    def test_dual_covered_handoff_no_finding(self):
        # I20 discharge: corpus absorbs both readings -> nothing to adjudicate
        cfg = self.vault_with_handoff(
            "t1", [{"text": "Soft or hard?", "corpus_covers": "both"}])
        pf = planning.gate_preflight(self.plan, vault_config_path=cfg,
                                     repo_root=self.dir.name)
        self.assertTrue(pf["ok"])
        self.assertEqual(pf["findings"], [])

    def test_non_blocking_profile_handoff_ignored(self):
        cfg = self.vault_with_handoff("t2", ["Soft or hard?"])  # t2 routine
        pf = planning.gate_preflight(self.plan, vault_config_path=cfg,
                                     repo_root=self.dir.name)
        self.assertTrue(pf["ok"])
        self.assertEqual(pf["findings"], [])

    def test_corrupt_handoff_fatal(self):
        cfg = self.vault_with_handoff("t1", [])
        evidence = os.path.join(self.dir.name, "vault", "evidence")
        with open(os.path.join(evidence, "t1.retry.handoff.json"), "w") as fh:
            fh.write("not json")
        pf = planning.gate_preflight(self.plan, vault_config_path=cfg,
                                     repo_root=self.dir.name)
        self.assertFalse(pf["ok"])
        self.assertEqual(pf["findings"][0]["kind"], "handoff-invalid")

    # -- CLI --------------------------------------------------------------------

    def test_cli_exit_codes(self):
        clean = subprocess.run(
            [sys.executable, "-m", "harness.planning", "preflight",
             "--plan-dir", self.plan, "--repo", self.dir.name],
            capture_output=True, text=True, timeout=30, cwd=REPO_ROOT)
        self.assertEqual(clean.returncode, 0, clean.stderr)
        self.set_touches("t2", ["pilot/app/auth/login.py"])
        fatal = subprocess.run(
            [sys.executable, "-m", "harness.planning", "preflight",
             "--plan-dir", self.plan, "--repo", self.dir.name],
            capture_output=True, text=True, timeout=30, cwd=REPO_ROOT)
        self.assertEqual(fatal.returncode, 2)
        self.assertIn("preflight FATAL", fatal.stderr)
