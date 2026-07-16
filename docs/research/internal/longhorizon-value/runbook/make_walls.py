#!/usr/bin/env python3
"""make_walls.py — generate + install the OS deny-read walls for every arm
repo and for arm H's authoring root (walls, not politeness).

Two wall surfaces, per worker cwd:

1. Each ARM REPO gets a committed `.claude/settings.json` denying reads of:
   both held-out roots (slice-2 + arm H's), outrigger (the chain design names
   the canary locations), and the two SIBLING arm repos. Its own repo is
   never denied. Committed pre-run and identically-structured across arms
   (fair); arm H's protected-paths interlock guards `.claude/` against
   worker edits, and N/F workers additionally carry the same walls in their
   launcher params (belt and braces).

2. The ARM-H HELD-OUT ROOT gets a plain `.claude/settings.json` (not a git
   repo) for the in-loop AUTHORS whose cwd is a workspace under it: denies
   slice-2, both sibling arm repos, and outrigger/docs — but NOT the tools
   dir (the authoring role contract lives at tools/heldout-suite/ROLE.md and
   authors read it by design) and NOT the arm-H repo (authors read the
   target repo by design).

Idempotent. Run via setup-arms.sh or directly:  python3 make_walls.py
"""
import json
import os
import subprocess
import sys

HOME = os.path.expanduser("~")
REPOS = os.path.join(HOME, "repos")
OUTRIGGER = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                         "..", "..", "..", "..", ".."))
ARMS = ["eaitl-arm-H", "eaitl-arm-N", "eaitl-arm-F"]
SLICE2 = os.path.join(REPOS, "eaitl-heldout-slice2")
H_HELDOUT = os.path.join(REPOS, "eaitl-arm-H-heldout")


def rules(paths):
    out = []
    for p in paths:
        out.append(f"Read(//{p.lstrip('/')})")
        out.append(f"Read(//{p.lstrip('/')}/**)")
    return {"permissions": {"deny": out}}


def write_settings(directory, settings):
    os.makedirs(os.path.join(directory, ".claude"), exist_ok=True)
    path = os.path.join(directory, ".claude", "settings.json")
    body = json.dumps(settings, indent=2) + "\n"
    if os.path.exists(path) and open(path, encoding="utf-8").read() == body:
        return path, False
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(body)
    return path, True


def main():
    for arm in ARMS:
        repo = os.path.join(REPOS, arm)
        if not os.path.isdir(os.path.join(repo, ".git")):
            print(f"skip (no repo): {repo}")
            continue
        siblings = [os.path.join(REPOS, a) for a in ARMS if a != arm]
        walls = [SLICE2, H_HELDOUT, OUTRIGGER] + siblings
        path, changed = write_settings(repo, rules(walls))
        if changed:
            subprocess.run(["git", "-C", repo, "add", ".claude/settings.json"],
                           check=True)
            subprocess.run(["git", "-C", repo, "commit", "-q", "-m",
                            "infra: OS deny-read walls (pre-run, identical "
                            "in structure across all arms)"], check=True)
            print(f"walled + committed: {path}")
        else:
            print(f"walls current: {path}")
        head = subprocess.run(["git", "-C", repo, "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True).stdout.strip()
        print(f"  {arm} HEAD now {head}")

    # Arm H's authoring root (authors' cwd lives under it; not a git repo).
    author_walls = [SLICE2, os.path.join(REPOS, "eaitl-arm-N"),
                    os.path.join(REPOS, "eaitl-arm-F"),
                    os.path.join(OUTRIGGER, "docs")]
    path, changed = write_settings(H_HELDOUT, rules(author_walls))
    print(("walled: " if changed else "walls current: ") + path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
