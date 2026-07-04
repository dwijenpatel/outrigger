#!/usr/bin/env python3
"""C1 — PreToolUse (Edit|Write) advisory: warn on mid-firing prefix edits.

Advisory layer: **fails open by design** (§7 split) — it never blocks and never
exits non-zero, even on internal error. The warning lands on stderr where the
transcript records it.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import hooks  # noqa: E402


def main() -> int:
    try:
        doc = hooks.parse_hook_input(sys.stdin.read())
        warning = hooks.check_prefix_edit(doc.get("tool_name", ""),
                                          doc.get("tool_input") or {})
        if warning:
            print(warning, file=sys.stderr)
    except Exception as exc:  # advisory: never block on our own failure
        print(f"prefix-edit hook (advisory) errored, allowing: {exc}",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
