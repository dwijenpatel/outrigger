"""I21 (P3v2-1): the operator-notification helper is best-effort — it must
exist, be executable, and exit 0 even on a platform with no notification
surface (empty PATH strips uname/osascript; the bell+stderr path remains)."""

import os
import subprocess
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "tools", "notify_operator.sh")


class NotifyOperatorTests(unittest.TestCase):
    def test_script_present_and_executable(self):
        self.assertTrue(os.path.isfile(SCRIPT), SCRIPT)
        self.assertTrue(os.access(SCRIPT, os.X_OK),
                        "notify_operator.sh must be executable")

    def test_exits_zero_without_notification_surface(self):
        out = subprocess.run(
            ["/bin/sh", SCRIPT, "GL1: decision needed", "test firing"],
            env={"PATH": ""}, capture_output=True, text=True, timeout=10)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("GL1: decision needed", out.stderr)

    def test_exits_zero_with_no_args(self):
        out = subprocess.run(["/bin/sh", SCRIPT], env={"PATH": ""},
                             capture_output=True, text=True, timeout=10)
        self.assertEqual(out.returncode, 0, out.stderr)


if __name__ == "__main__":
    unittest.main()
