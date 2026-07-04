#!/usr/bin/env python3
"""H2 — PreToolUse (Task|Agent|Bash) gate: no spawn without admission.

During a live firing, spawning a worker (Task/Agent tool, or headless
``claude -p``) demands a fresh admission stamp — proof the governor +
scheduler tick actually ran ("governor between tasks" as machinery, not
prose). Inert outside a live firing. Enforcement gate: **fails closed**.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import hooks, interlocks  # noqa: E402


def main() -> int:
    try:
        doc = hooks.parse_hook_input(sys.stdin.read())
        cwd = doc.get("cwd") or os.getcwd()
        project = os.environ.get("CLAUDE_PROJECT_DIR") or cwd
        violation = interlocks.check_spawn(
            doc.get("tool_name", ""), doc.get("tool_input") or {},
            marker_path=os.path.join(project, "state", "run.marker"),
            stamp_path=os.path.join(project, "state", "admission-stamp.json"))
        if violation:
            print(violation, file=sys.stderr)
            return 2
        return 0
    except Exception as exc:  # gate: fail closed
        print(f"spawn interlock cannot decide, blocking (fail-closed): {exc}",
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
