"""I5 — the firing smoke test: one real walk of the step sequence."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import smoketest


class FiringSmokeTests(unittest.TestCase):
    """One end-to-end walk in a scratch clone. Slow-ish (~10s) by design:
    this is the composition test the hermetic suites cannot be."""

    def test_full_firing_sequence_is_green(self):
        with tempfile.TemporaryDirectory(prefix="smoke-") as workdir:
            result = smoketest.run_smoke(workdir)
        names = [s["step"] for s in result["steps"]]
        # the sequence itself is the contract — order matters
        self.assertEqual(names, [
            "clone", "preflight_cold", "bootstrap_assumption",
            "statusline_shim", "governor_live_rung", "vault_configure",
            "plan_ready", "marker_and_closure_hook", "admission_cold_start",
            "spawn_interlock", "headless_worker_harvest",
            "worker_overlay_untracked", "gate_pass", "gate_heldout_ran",
            "merge_interlock", "closure_inert_after_release", "final_state"])
        failing = [s for s in result["steps"] if not s["ok"]]
        self.assertTrue(result["ok"],
                        "smoke steps failed: " + "; ".join(
                            f"{s['step']}: {s['detail']}" for s in failing))


if __name__ == "__main__":
    unittest.main()
