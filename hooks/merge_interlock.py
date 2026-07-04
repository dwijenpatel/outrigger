#!/usr/bin/env python3
"""H2 — PreToolUse (Bash) gate: merge only through the gate, mechanically.

During a live firing, ``git merge``/``git push`` to a protected ref demands a
fresh PASS gate stamp bound to the merged ref's current HEAD. Inert outside a
live firing (operator sessions, machinery development). Enforcement gate:
**fails closed** — a violation, an undeterminable target, or any internal
error exits 2 with the reason on stderr.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import hooks, interlocks  # noqa: E402


def main() -> int:
    try:
        doc = hooks.parse_hook_input(sys.stdin.read())
        if doc.get("tool_name") != "Bash":
            return 0
        cwd = doc.get("cwd") or os.getcwd()
        project = os.environ.get("CLAUDE_PROJECT_DIR") or cwd
        violation = interlocks.check_merge(
            (doc.get("tool_input") or {}).get("command", ""),
            repo_dir=cwd,
            stamp_dir=os.path.join(project, "state", "gate-stamps"),
            marker_path=os.path.join(project, "state", "run.marker"))
        if violation:
            print(violation, file=sys.stderr)
            return 2
        return 0
    except Exception as exc:  # gate: fail closed
        print(f"merge interlock cannot decide, blocking (fail-closed): {exc}",
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
