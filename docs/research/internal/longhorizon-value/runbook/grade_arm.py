#!/usr/bin/env python3
"""grade_arm.py — post-hoc, quota-free grading: replay every sealed held-out
suite against one arm's final tree.

For each task workspace under the given held-out roots: verify the seal
(tamper check — a diverged workspace is recorded and its suite is NOT run),
then execute the manifest's pinned consumer invocation with $CHECKOUT
substituted by a fresh clean clone of the arm repo's main. Unittest counts
are parsed from the runner output; everything lands in a JSON report.

Non-adaptive by construction: run this AFTER an arm finishes; results reach
only the operator. Canary edges live inside the suites, so no separate
canary step exists here. Per-task compounding depth and the three-outcome
grading (correct-complete / honest-stop / silent-wrong) are operator
judgments made FROM this report plus the arm ledgers.

Usage:
  python3 grade_arm.py --arm-repo ~/repos/eaitl-arm-N \\
      --workspaces ~/repos/eaitl-arm-H-heldout ~/repos/eaitl-heldout-slice2 \\
      --out runs/arm-N/grade-report.json
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
OUTRIGGER = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
HELDOUT_CLI = os.path.join(OUTRIGGER, "tools", "heldout-suite", "heldout.py")


def find_workspaces(roots):
    for root in roots:
        root = os.path.abspath(os.path.expanduser(root))
        if not os.path.isdir(root):
            continue
        for name in sorted(os.listdir(root)):
            ws = os.path.join(root, name)
            if os.path.isfile(os.path.join(ws, "manifest.json")):
                yield ws


def run_suite(ws, checkout):
    with open(os.path.join(ws, "manifest.json"), encoding="utf-8") as fh:
        manifest = json.load(fh)
    run = manifest["run"]
    sub = lambda v: v.replace("$CHECKOUT", checkout)
    argv = [sub(a) for a in run["argv"]]
    env = dict(os.environ)
    env.update({k: sub(v) for k, v in run.get("env", {}).items()})
    cwd = sub(run.get("cwd", checkout))
    proc = subprocess.run(argv, cwd=cwd, env=env, capture_output=True,
                          text=True, timeout=600)
    tail = (proc.stderr or proc.stdout).strip().splitlines()[-15:]
    counts = {"ran": None, "failures": 0, "errors": 0}
    for line in tail:
        m = re.match(r"Ran (\d+) tests?", line)
        if m:
            counts["ran"] = int(m.group(1))
        m = re.search(r"failures=(\d+)", line)
        if m:
            counts["failures"] = int(m.group(1))
        m = re.search(r"errors=(\d+)", line)
        if m:
            counts["errors"] = int(m.group(1))
    return {"task_id": manifest["task_id"], "exit": proc.returncode,
            "ok": proc.returncode == 0, **counts, "tail": tail[-4:]}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm-repo", required=True)
    ap.add_argument("--workspaces", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    arm_repo = os.path.abspath(os.path.expanduser(args.arm_repo))
    head = subprocess.run(["git", "-C", arm_repo, "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()
    results = []
    with tempfile.TemporaryDirectory(prefix="grade-") as tmp:
        checkout = os.path.join(tmp, "checkout")
        subprocess.run(["git", "clone", "--no-hardlinks", "-q", arm_repo, checkout],
                       check=True)
        for ws in find_workspaces(args.workspaces):
            verify = subprocess.run(
                [sys.executable, HELDOUT_CLI, "verify", "--workspace", ws],
                capture_output=True, text=True)
            if verify.returncode != 0:
                results.append({"workspace": ws, "seal": "DIVERGED",
                                "detail": verify.stdout.strip() or verify.stderr.strip()})
                continue
            entry = {"workspace": ws, "seal": "fresh"}
            try:
                entry.update(run_suite(ws, checkout))
            except subprocess.TimeoutExpired:
                entry.update({"exit": None, "ok": False, "timeout": True})
            results.append(entry)

    report = {"arm_repo": arm_repo, "graded_head": head, "suites": results}
    out = os.path.abspath(os.path.expanduser(args.out))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)

    print(f"graded {arm_repo} @ {head[:9]} — {len(results)} suites")
    for r in results:
        if r.get("seal") == "DIVERGED":
            print(f"  {r['workspace']}: SEAL DIVERGED — not run")
        else:
            print(f"  {r.get('task_id', '?'):28s} exit {r['exit']}  "
                  f"ran={r.get('ran')} failures={r.get('failures')} errors={r.get('errors')}")
    print(f"report: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
