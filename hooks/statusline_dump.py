#!/usr/bin/env python3
"""Statusline-dump shim (design §5.1/§12 Q1) — the headless quota bridge.

Configured as the statusline command on the operator's interactive session, it
tees the statusline stdin JSON (which carries `rate_limits`) to a file the
budget governor reads, then prints a minimal statusline. Official data,
unofficial acquisition; the dump stales when the host session idles — the
governor treats file age accordingly (`captured_at` is embedded).

    "statusLine": {"type": "command",
                   "command": "python3 hooks/statusline_dump.py --out ~/.harness/statusline.json"}
"""
import argparse
import datetime
import json
import os
import sys


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--out", required=True)
    args = p.parse_args(argv)
    line = ""
    try:
        doc = json.loads(sys.stdin.read())
        doc["_captured_at"] = datetime.datetime.now(
            datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        out = os.path.expanduser(args.out)
        os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
        tmp = out + ".tmp"
        with open(tmp, "w") as fh:
            json.dump(doc, fh)
        os.replace(tmp, out)
        rl = doc.get("rate_limits") or {}
        parts = []
        for window, label in (("five_hour", "5h"), ("seven_day", "7d")):
            entry = rl.get(window) or {}
            pct = entry.get("used_percentage")
            if isinstance(pct, (int, float)):
                parts.append(f"{label} {pct:.0f}%")
        line = " · ".join(parts) or "windows: n/a"
    except Exception as exc:  # a broken statusline must never break the session
        line = f"statusline-dump error: {exc}"
    print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
