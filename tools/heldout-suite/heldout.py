#!/usr/bin/env python3
"""heldout-suite — the held-out test suite lifecycle: materialize, validate, seal, verify.

One thing well: manage the GRADED tests' lifecycle so that the agent writing the
code never writes, sees, or reaches the tests that judge it (design D2/D11).
This tool prepares an authoring workspace OUTSIDE the target repo, checks an
authored suite has teeth against the pre-change code (fails-on-base), and locks
it with a spec-hash-bound manifest plus a deny-fragment for the implementer's
spawner. It never launches any agent — who authors is composition (ROLE.md is
the authoring contract).

Pure stdlib. Contract: README.md next to this file. Built from the ratified
plans/heldout-suite.plan.json.

Exit codes: 0 ok · 1 refusal or policy failure · 2 usage or input error.
"""

import argparse
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

PLAN_CONTRACT = 1
MANIFEST_CONTRACT = 1
VALIDATE_DEADLINE_S = 600  # a hung suite is a policy failure, not a wait

# Runs inside the base checkout: discover + run the suite, report exact counts
# as JSON (text-output parsing is brittle; counts must be exact).
RUNNER = r"""
import json, os, sys, unittest
suite_dir = sys.argv[1]
loader = unittest.TestLoader()
tests = loader.discover(start_dir=suite_dir, top_level_dir=suite_dir)
sink = open(os.devnull, "w")
result = unittest.TextTestRunner(stream=sink, verbosity=0).run(tests)
print(json.dumps({
    "ran": result.testsRun,
    "failed": len(result.failures),
    "errored": len(result.errors),
}))
"""


def utcnow() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fail(code, message):
    print(f"error: {message}", file=sys.stderr)
    return code


def git(repo, *args):
    """Run git in repo; returns (rc, stdout). Never raises on git failure."""
    proc = subprocess.run(
        ["git", "-C", repo, *args], capture_output=True, text=True
    )
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def repo_toplevel(repo):
    rc, out, _ = git(repo, "rev-parse", "--show-toplevel")
    return os.path.realpath(out) if rc == 0 else None


def resolve_commit(repo, ref):
    rc, out, _ = git(repo, "rev-parse", "--verify", f"{ref}^{{commit}}")
    return out if rc == 0 else None


def path_inside(child, parent):
    child, parent = os.path.realpath(child), os.path.realpath(parent)
    return child == parent or child.startswith(parent + os.sep)


def write_json(path, obj):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, sort_keys=True)
        fh.write("\n")


AUTHORING_MD = """\
# Authoring workspace — held-out suite for task `{task_id}`

You are the TEST-AUTHOR for exactly one task. Full role instructions:
`ROLE.md` in the heldout-suite artifact directory of the orchestrating repo
(tools/heldout-suite/ROLE.md). The short version:

- **Your inputs are `task.json` (in this directory) and the base checkout of
  the target repository — nothing else.** task.json holds the task's spec and
  the plan-level goal/non-goals/constraints/decisions (the why). There is no
  implementation yet; you write tests from the SPEC.
- **Write stdlib-unittest tests as `test_*.py` files into `../suite/`.**
- Your suite will be judged by `heldout.py validate` against a clean checkout
  of base commit `{base_sha}`: the runner must complete, and **at least one
  test must fail on base** (a suite that fully passes before the change proves
  nothing). Base-passing regression guards are allowed and welcome.
- You may run `validate` yourself, iteratively. You never run `seal`.
- You never assert your suite is good — validate and the seal decide.
"""


def cmd_materialize(args):
    top = repo_toplevel(args.repo)
    if top is None:
        return fail(2, f"not a git repository: {args.repo}")

    out_real = os.path.realpath(args.out)
    if path_inside(out_real, top):
        return fail(
            1,
            f"--out resolves inside the target repo ({out_real}) — held-out suites "
            "never live in the judged tree; choose a location outside it",
        )

    base_sha = resolve_commit(args.repo, args.base)
    if base_sha is None:
        return fail(2, f"cannot resolve base ref {args.base!r} in {args.repo}")

    try:
        with open(args.plan, encoding="utf-8") as fh:
            plan = json.load(fh)
    except OSError as exc:
        return fail(2, f"cannot read plan: {exc}")
    except json.JSONDecodeError as exc:
        return fail(2, f"plan is not valid JSON: {exc.msg}")

    if not isinstance(plan, dict) or plan.get("contract") != PLAN_CONTRACT:
        return fail(2, f"plan contract must be {PLAN_CONTRACT}")
    tasks = {
        t.get("id"): t
        for t in plan.get("tasks", [])
        if isinstance(t, dict) and isinstance(t.get("id"), str)
    }
    if args.task not in tasks:
        return fail(2, f"task {args.task!r} not found in plan (has: {', '.join(sorted(tasks))})")

    workspace = os.path.join(out_real, args.task)
    if os.path.exists(workspace):
        return fail(
            1,
            f"workspace already exists: {workspace} — re-materialization of a sealed "
            "workspace is the retire flow in seal, never an overwrite",
        )

    # The interview-scoped inputs (plan decisions[4]): this task's full entry
    # plus the plan-level preamble. Never other tasks' specs.
    task_inputs = {
        "task": tasks[args.task],
        "goal": plan.get("goal", ""),
        "non_goals": plan.get("non_goals", []),
        "constraints": plan.get("constraints", []),
        "decisions": plan.get("decisions", []),
        "base": {"ref": args.base, "sha": base_sha},
        "plan_contract": PLAN_CONTRACT,
    }

    authoring = os.path.join(workspace, "authoring")
    suite = os.path.join(workspace, "suite")
    os.makedirs(authoring)
    os.makedirs(suite)
    write_json(os.path.join(authoring, "task.json"), task_inputs)
    with open(os.path.join(authoring, "AUTHORING.md"), "w", encoding="utf-8") as fh:
        fh.write(AUTHORING_MD.format(task_id=args.task, base_sha=base_sha))

    print(
        json.dumps(
            {
                "workspace": workspace,
                "task_id": args.task,
                "base": {"ref": args.base, "sha": base_sha},
                "files": ["authoring/task.json", "authoring/AUTHORING.md", "suite/"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_workspace(workspace):
    """Common workspace loading; returns (task_inputs, err_msg)."""
    task_json = os.path.join(workspace, "authoring", "task.json")
    if not os.path.isfile(task_json):
        return None, f"not an authoring workspace (no authoring/task.json): {workspace}"
    try:
        with open(task_json, encoding="utf-8") as fh:
            return json.load(fh), None
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"cannot read authoring/task.json: {exc}"


def suite_files(workspace):
    """Sorted relative paths of every file under suite/."""
    suite = os.path.join(workspace, "suite")
    found = []
    for root, _dirs, files in os.walk(suite):
        for name in files:
            if name.endswith(".pyc") or "__pycache__" in root:
                continue
            found.append(os.path.relpath(os.path.join(root, name), suite))
    return sorted(found)


def run_validation(workspace, repo):
    """Run the suite against a clean checkout of the recorded base.

    Returns (split_dict, problem_msg): split on completion (even when the
    policy fails), problem_msg set when the fails-on-base policy is violated
    or the runner did not complete.
    """
    inputs, err = load_workspace(workspace)
    if inputs is None:
        return None, err
    base_sha = inputs.get("base", {}).get("sha")
    if not base_sha:
        return None, "workspace task.json carries no base.sha"
    if resolve_commit(repo, base_sha) is None:
        return None, f"base commit {base_sha} not present in {repo}"

    suite = os.path.join(workspace, "suite")
    checkout = tempfile.mkdtemp(prefix="heldout-validate-")
    try:
        rc, _, err_out = git(repo, "worktree", "add", "--detach", checkout, base_sha)
        if rc != 0:
            return None, f"cannot create base checkout: {err_out}"
        env = dict(os.environ)
        env["PYTHONPATH"] = checkout
        try:
            proc = subprocess.run(
                [sys.executable, "-c", RUNNER, os.path.abspath(suite)],
                cwd=checkout,
                env=env,
                capture_output=True,
                text=True,
                timeout=VALIDATE_DEADLINE_S,
            )
        except subprocess.TimeoutExpired:
            return None, f"suite runner exceeded {VALIDATE_DEADLINE_S}s — a hung suite is a policy failure"
        try:
            counts = json.loads(proc.stdout.strip().splitlines()[-1])
        except (json.JSONDecodeError, IndexError):
            return None, (
                "suite runner did not complete and report "
                f"(exit {proc.returncode}): {(proc.stderr or proc.stdout)[-500:]}"
            )
    finally:
        git(repo, "worktree", "remove", "--force", checkout)
        git(repo, "worktree", "prune")
        shutil.rmtree(checkout, ignore_errors=True)

    split = {
        "failed": counts["failed"],
        "errored": counts["errored"],
        "passed": counts["ran"] - counts["failed"] - counts["errored"],
    }
    if counts["failed"] + counts["errored"] < 1:
        return split, (
            "fails-on-base policy violated: every test passes against base "
            f"(ran {counts['ran']}) — a suite that fully passes before the change "
            "proves nothing about the change"
        )
    return split, None


def cmd_validate(args):
    workspace = os.path.realpath(args.workspace)
    split, problem = run_validation(workspace, args.repo)
    if split is None:
        return fail(2 if "policy" not in (problem or "") else 1, problem)

    inputs, _ = load_workspace(workspace)
    record = {
        "base_sha": inputs["base"]["sha"],
        "split": split,
        "ts": utcnow(),
        "ok": problem is None,
    }
    write_json(os.path.join(workspace, "validation.json"), record)
    print(json.dumps(record, indent=2, sort_keys=True))
    if problem:
        print(f"error: {problem}", file=sys.stderr)
        return 1
    return 0


def cmd_seal(args):
    workspace = os.path.realpath(args.workspace)
    if bool(args.adjudicated_by) != bool(args.adjudication_note):
        return fail(2, "--adjudicated-by and --adjudication-note go together")

    inputs, err = load_workspace(workspace)
    if inputs is None:
        return fail(2, err)

    manifest_path = os.path.join(workspace, "manifest.json")
    if os.path.exists(manifest_path):
        if not args.retire:
            return fail(
                1,
                "workspace is already sealed — pass --retire to archive the current "
                "seal (evidence is preserved, never overwritten)",
            )
        stamp = utcnow().replace(":", "").replace("-", "")
        retired = os.path.join(workspace, "retired", stamp)
        os.makedirs(retired)
        shutil.move(manifest_path, os.path.join(retired, "manifest.json"))
        validation = os.path.join(workspace, "validation.json")
        if os.path.exists(validation):
            shutil.move(validation, os.path.join(retired, "validation.json"))
        # Snapshot the current suite content. If files were edited in place the
        # pre-edit bytes are gone — the archived manifest still detects that
        # (its hashes will not match this snapshot). Honest, not magic.
        shutil.copytree(os.path.join(workspace, "suite"), os.path.join(retired, "suite-snapshot"))

    split, problem = run_validation(workspace, args.repo)
    if split is None:
        return fail(2 if "policy" not in (problem or "") else 1, problem)
    if problem:
        return fail(1, f"seal refused: {problem}")

    files = suite_files(workspace)
    suite_abs = os.path.join(workspace, "suite")
    manifest = {
        "contract": MANIFEST_CONTRACT,
        "task_id": inputs["task"]["id"],
        "spec_hash": sha256_file(os.path.join(workspace, "authoring", "task.json")),
        "base_sha": inputs["base"]["sha"],
        "run": {
            "argv": [
                "python3", "-m", "unittest", "discover",
                "-s", suite_abs, "-t", suite_abs,
            ],
            "cwd": "$CHECKOUT",
            "env": {"PYTHONPATH": "$CHECKOUT"},
            "note": "$CHECKOUT = a clean checkout of the tree under judgment",
        },
        "files": {rel: sha256_file(os.path.join(suite_abs, rel)) for rel in files},
        "fails_on_base": split,
        "sealed_at": utcnow(),
    }
    if args.adjudicated_by:
        manifest["adjudication"] = {
            "by": args.adjudicated_by,
            "note": args.adjudication_note,
            "ts": utcnow(),
        }
    write_json(manifest_path, manifest)
    write_json(
        os.path.join(workspace, "deny-fragment.json"),
        {
            "comment": "merge into the implementer-spawner's settings: the implementer must never read this workspace",
            "deny_read": [workspace],
        },
    )
    print(
        json.dumps(
            {
                "manifest": manifest_path,
                "manifest_sha256": sha256_file(manifest_path),
                "task_id": manifest["task_id"],
                "fails_on_base": split,
                "files": len(files),
                "adjudicated": "adjudication" in manifest,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def cmd_verify(args):
    workspace = os.path.realpath(args.workspace)
    manifest_path = os.path.join(workspace, "manifest.json")
    try:
        with open(manifest_path, encoding="utf-8") as fh:
            manifest = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        return fail(2, f"cannot read manifest: {exc}")
    if manifest.get("contract") != MANIFEST_CONTRACT:
        return fail(2, f"manifest contract must be {MANIFEST_CONTRACT}")

    reasons = []
    current = {
        rel: sha256_file(os.path.join(workspace, "suite", rel))
        for rel in suite_files(workspace)
    }
    recorded = manifest.get("files", {})
    for rel in sorted(set(recorded) - set(current)):
        reasons.append(f"missing suite file: {rel}")
    for rel in sorted(set(current) - set(recorded)):
        reasons.append(f"extra suite file not in the seal: {rel}")
    for rel in sorted(set(current) & set(recorded)):
        if current[rel] != recorded[rel]:
            reasons.append(f"suite file changed since sealing: {rel}")

    task_json = os.path.join(workspace, "authoring", "task.json")
    if not os.path.isfile(task_json):
        reasons.append("authoring/task.json is missing")
    elif sha256_file(task_json) != manifest.get("spec_hash"):
        reasons.append("spec changed since sealing (task.json hash mismatch)")

    fresh = not reasons
    print(json.dumps({"fresh": fresh, "reasons": reasons}, indent=2, sort_keys=True))
    return 0 if fresh else 1


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="heldout.py", description=__doc__.splitlines()[0]
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_mat = sub.add_parser(
        "materialize", help="build an authoring workspace outside the repo"
    )
    p_mat.add_argument("--plan", required=True, help="ratified plan.json path")
    p_mat.add_argument("--task", required=True, help="task id within the plan")
    p_mat.add_argument("--repo", required=True, help="target git repository")
    p_mat.add_argument("--base", default="main", help="base ref (default: main)")
    p_mat.add_argument(
        "--out", required=True, help="workspace parent directory — must be OUTSIDE the repo"
    )
    p_mat.set_defaults(fn=cmd_materialize)

    p_val = sub.add_parser(
        "validate", help="run the suite against a clean base checkout (fails-on-base policy)"
    )
    p_val.add_argument("--workspace", required=True, help="OUT/TASK_ID directory")
    p_val.add_argument("--repo", required=True, help="target git repository")
    p_val.set_defaults(fn=cmd_validate)

    p_seal = sub.add_parser(
        "seal", help="validate, then bind suite <-> spec-hash <-> base-sha into manifest.json"
    )
    p_seal.add_argument("--workspace", required=True, help="OUT/TASK_ID directory")
    p_seal.add_argument("--repo", required=True, help="target git repository")
    p_seal.add_argument(
        "--retire", action="store_true",
        help="archive the existing seal to retired/<ts>/ before re-sealing",
    )
    p_seal.add_argument("--adjudicated-by", help="operator name for an on-the-record human suite edit")
    p_seal.add_argument("--adjudication-note", help="why the operator edited the suite")
    p_seal.set_defaults(fn=cmd_seal)

    p_ver = sub.add_parser(
        "verify", help="tamper check: recompute suite hashes + spec hash against the seal"
    )
    p_ver.add_argument("--workspace", required=True, help="OUT/TASK_ID directory")
    p_ver.set_defaults(fn=cmd_verify)

    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
