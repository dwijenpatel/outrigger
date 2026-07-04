#!/usr/bin/env python3
"""C2 — PreToolUse gate: destructive git (Bash) + machinery paths (Edit|Write).

Enforcement gate: **fails closed** (§7) — a violation, an undeterminable git
state, or any internal error exits 2 (block) with the reason on stderr.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import hooks  # noqa: E402


def main() -> int:
    try:
        doc = hooks.parse_hook_input(sys.stdin.read())
        tool = doc.get("tool_name", "")
        tool_input = doc.get("tool_input") or {}
        cwd = doc.get("cwd") or os.getcwd()

        if tool == "Bash":
            violation = hooks.check_destructive_git(tool_input.get("command", ""))
            if violation:
                print(violation, file=sys.stderr)
                return 2
            return 0

        violation = hooks.check_machinery_paths(
            tool, tool_input, branch=hooks.current_branch(cwd))
        if violation:
            print(violation, file=sys.stderr)
            return 2
        return 0
    except Exception as exc:  # gate: fail closed
        print(f"git-guard gate cannot decide, blocking (fail-closed): {exc}",
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
