#!/usr/bin/env python3
"""exec-loop — walk a ratified plan task-by-task, unattended.

The first composition (design D3/D4/D5): per task, serially — materialize the
authoring workspace, launch a fresh test-author, seal the held-out suite,
launch a fresh implementer in a confined worktree, gate the merged tree,
land the judged tree fast-forward-only, record everything in the ledger.
Fresh-worker retry with model escalation on gate failure; halt-everything
with a blocker record when a task exhausts attempts. After the last task,
whole-build CLOSURE re-runs every task's checks and every sealed suite
against final main — exit 0 is granted by that stamped report, never claimed
from per-task history (D3).

Composition rule (R5): sibling artifacts are invoked ONLY as subprocess CLIs
(plan-preflight, heldout-suite, merge-gate, run-ledger); workers only through
the launcher file contract (launchers/CONTRACT.md). Pure stdlib.

State rule (plan decision 7): no state file — progress derives from git, the
seals, and the append-only ledger on every start.

Exit codes: 0 plan complete · 1 blocker (see blocker.json) · 2 usage/config error.
"""

import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
HELDOUT = os.path.join(TOOLS, "heldout-suite", "heldout.py")
GATE = os.path.join(TOOLS, "merge-gate", "gate.py")
PREFLIGHT = os.path.join(TOOLS, "plan-preflight", "preflight.py")
LEDGER = os.path.join(TOOLS, "run-ledger", "ledger.py")
ROLE_MD = os.path.join(TOOLS, "heldout-suite", "ROLE.md")

DEFAULT_CONFIG = {
    "launcher": os.path.join(HERE, "launchers", "claude_p.py"),
    "workers": {
        "author": {"tool": "claude", "model": "claude-opus-4-8", "effort": "xhigh"},
        "implementer_a1": {"tool": "claude", "model": "claude-sonnet-5", "effort": "xhigh"},
        "implementer_a2": {"tool": "claude", "model": "claude-opus-4-8", "effort": "xhigh"},
        # tier bare = one strong session, no author, no gate (the operator
        # declared the stakes don't buy machinery) — strong by default.
        "bare": {"tool": "claude", "model": "claude-opus-4-8", "effort": "xhigh"},
    },
    "protect_paths": ["tools/", "plans/", ".claude/", "docs/research/internal/v2-ledger.jsonl"],
    "author_timeout_s": 1800,
    "implementer_timeout_s": 3600,
    "max_attempts": 2,
    "ledger": None,  # resolved at run start: <workdir>/ledger.jsonl unless configured
}


def utcnow():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run(argv, cwd=None, env=None, timeout=None):
    return subprocess.run(
        argv, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout
    )


def git(repo, *args):
    proc = run(["git", "-C", repo, *args])
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def path_inside(child, parent):
    child, parent = os.path.realpath(child), os.path.realpath(parent)
    return child == parent or child.startswith(parent + os.sep)


def parse_shortstat(text):
    """`git diff --shortstat` -> {files, insertions, deletions} (0 when absent).

    "how much code did this worker produce" for an implementer (product code).
    """
    def n(pat):
        m = re.search(pat, text or "")
        return int(m.group(1)) if m else 0
    return {
        "files": n(r"(\d+) files? changed"),
        "insertions": n(r"(\d+) insertions?\(\+\)"),
        "deletions": n(r"(\d+) deletions?\(-\)"),
    }


def suite_stats(ws):
    """Lines and file count of the authored held-out suite (test code produced)."""
    suite_dir = os.path.join(ws, "suite")
    files = sorted(
        f for f in os.listdir(suite_dir)
        if f.startswith("test_") and f.endswith(".py")
    ) if os.path.isdir(suite_dir) else []
    lines = 0
    for f in files:
        with open(os.path.join(suite_dir, f), encoding="utf-8", errors="replace") as fh:
            lines += sum(1 for _ in fh)
    return {"files": len(files), "lines": lines}


class Blocker(Exception):
    def __init__(self, reason, detail):
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


class Loop:
    def __init__(self, plan_path, repo, heldout_out, config):
        self.repo = os.path.realpath(repo)
        self.heldout_out = os.path.realpath(heldout_out)
        self.config = config
        with open(plan_path, encoding="utf-8") as fh:
            self.plan = json.load(fh)  # snapshot: read exactly once (decision 8)
        self.plan_name = os.path.splitext(os.path.basename(plan_path))[0]
        self.workdir = os.path.join(self.heldout_out, "_runs", self.plan_name)
        os.makedirs(self.workdir, exist_ok=True)
        self.snapshot_path = os.path.join(self.workdir, "plan-snapshot.json")
        with open(self.snapshot_path, "w", encoding="utf-8") as fh:
            json.dump(self.plan, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        self.ledger = config.get("ledger") or os.path.join(self.workdir, "ledger.jsonl")

    # ---------- ledger ----------

    def record(self, kind, subject_suffix, data):
        proc = run(
            [
                sys.executable, LEDGER, "append", self.ledger,
                "--kind", kind,
                "--subject", f"exec-loop/{self.plan_name}/{subject_suffix}",
                "--source", "exec-loop",
                "--data", json.dumps(data),
            ]
        )
        if proc.returncode != 0:
            raise Blocker("ledger-append-failed", {"stderr": proc.stderr.strip()})

    def ledger_records(self):
        if not os.path.exists(self.ledger):
            return []
        records = []
        with open(self.ledger, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue  # tolerant read; ledger.py check is the strict path
        return records

    # ---------- risk tiers ----------

    def task_tier(self, task):
        """full | gate-only | bare — task override, else plan risk_tier, else
        full. The tier is the operator's declared blast-radius/budget context
        (set in the interview, validated by preflight); lowering the guard is
        always an explicit recorded choice, never a default."""
        return task.get("tier") or self.plan.get("risk_tier") or "full"

    # ---------- workers ----------

    def launch(self, task_id, role, attempt, worker, isolation, cwd, instructions, timeout_s,
               tier="full"):
        self._bundle_seq = getattr(self, "_bundle_seq", 0) + 1
        stem = os.path.join(
            self.workdir, "bundles",
            f"{utcnow().replace(':', '')}-{self._bundle_seq:03d}-{task_id}-{role}-a{attempt}",
        )
        bundle, suffix = stem, 1
        while True:  # unique across runs even at same-second timestamps
            try:
                os.makedirs(bundle)
                break
            except FileExistsError:
                suffix += 1
                bundle = f"{stem}-{suffix}"
        with open(os.path.join(bundle, "instructions.md"), "w", encoding="utf-8") as fh:
            fh.write(instructions)
        with open(os.path.join(bundle, "params.json"), "w", encoding="utf-8") as fh:
            json.dump(
                {
                    "role": role,
                    "attempt": attempt,
                    "worker": worker,
                    "isolation": isolation,
                    "cwd": cwd,
                    "timeout_s": timeout_s,
                },
                fh,
                indent=2,
            )
        self.record(
            "run", f"{task_id}/spawn/{role}-a{attempt}",
            {"worker": worker, "bundle": bundle, "tier": tier},
        )
        proc = run([sys.executable, self.config["launcher"], bundle], timeout=timeout_s + 120)
        result_path = os.path.join(bundle, "result.json")
        result = {}
        if os.path.exists(result_path):
            with open(result_path, encoding="utf-8") as fh:
                result = json.load(fh)
        result["bundle"] = bundle
        result["launcher_exit"] = proc.returncode
        return result

    # ---------- held-out suite ----------

    def expected_task_inputs(self, task):
        return {
            "task": task,
            "goal": self.plan.get("goal", ""),
            "non_goals": self.plan.get("non_goals", []),
            "constraints": self.plan.get("constraints", []),
            "decisions": self.plan.get("decisions", []),
        }

    def workspace(self, task_id):
        return os.path.join(self.heldout_out, task_id)

    def suite_fresh(self, task):
        """Sealed, verify-fresh, and authored from the CURRENT plan's inputs."""
        ws = self.workspace(task["id"])
        if not os.path.exists(os.path.join(ws, "manifest.json")):
            return False
        if run([sys.executable, HELDOUT, "verify", "--workspace", ws]).returncode != 0:
            raise Blocker(
                "heldout-verify-failed",
                {"workspace": ws, "note": "sealed suite diverged — operator adjudication"},
            )
        with open(os.path.join(ws, "authoring", "task.json"), encoding="utf-8") as fh:
            frozen = json.load(fh)
        expected = self.expected_task_inputs(task)
        for key, value in expected.items():
            if frozen.get(key) != value:
                raise Blocker(
                    "suite-stale-spec-changed",
                    {"workspace": ws, "changed_field": key,
                     "note": "plan inputs changed since sealing — retire/re-author is an operator decision"},
                )
        return True

    def author_instructions(self, task, ws, validation_counts=None):
        parts = [
            f"You are the TEST-AUTHOR for task `{task['id']}`.",
            f"Your authoring workspace is: {ws}",
            f"Read {ws}/authoring/task.json (your task and the plan context) and "
            f"{ws}/authoring/AUTHORING.md, then follow the role contract at {ROLE_MD}.",
            f"The target repository (base checkout) is: {self.repo} — read it to match "
            "conventions and real module paths. Write stdlib-unittest tests into "
            f"{ws}/suite/ as test_*.py files.",
            "At least one test must FAIL against the unchanged base (that is the seal "
            "policy); base-passing regression guards are welcome. You never run seal.",
        ]
        if validation_counts:
            parts.append(
                "Your previous suite failed the seal policy — every test passed against "
                f"base (counts: {json.dumps(validation_counts)}). Write tests that pin the "
                "CHANGE the spec describes, not only current behavior."
            )
        return "\n\n".join(parts)

    def ensure_suite(self, task):
        ws = self.workspace(task["id"])
        if os.path.exists(ws):
            if os.path.exists(os.path.join(ws, "manifest.json")):
                if self.suite_fresh(task):
                    return ws
                # unreachable: suite_fresh raises on any not-fresh condition
            else:
                # Materialized but never sealed: in-flight authoring debris from
                # an interrupted run — torn down and redone (decision 7). Sealed
                # workspaces are NEVER auto-removed; that is the operator's call.
                shutil.rmtree(ws)
        proc = run(
            [
                sys.executable, HELDOUT, "materialize",
                "--plan", self.snapshot_path,
                "--task", task["id"],
                "--repo", self.repo,
                "--base", "main",
                "--out", self.heldout_out,
            ]
        )
        if proc.returncode != 0:
            raise Blocker("materialize-failed", {"stderr": proc.stderr.strip()})

        counts = None
        for round_no in (1, 2):
            result = self.launch(
                task_id=task["id"],
                role="author",
                attempt=round_no,
                worker=self.config["workers"]["author"],
                isolation={"deny_read": [], "sandbox": True, "network": True},
                cwd=ws,
                instructions=self.author_instructions(task, ws, counts),
                timeout_s=self.config["author_timeout_s"],
            )
            if not result.get("ok"):
                raise Blocker("author-launch-failed", {"result": result})
            seal = run([sys.executable, HELDOUT, "seal", "--workspace", ws, "--repo", self.repo])
            if seal.returncode == 0:
                summary = json.loads(seal.stdout)
                # Instrument the author leg: token spend (from the launcher's
                # result.json) + the size of the test code it produced.
                summary["author_usage"] = result.get("usage")
                summary["suite"] = suite_stats(ws)
                self.record("run", f"{task['id']}/seal", summary)
                return ws
            if "policy" in (seal.stderr or "") and round_no == 1:
                validation = os.path.join(ws, "validation.json")
                if os.path.exists(validation):
                    with open(validation, encoding="utf-8") as fh:
                        counts = json.load(fh).get("split")
                continue
            raise Blocker(
                "author-policy-exhausted" if "policy" in (seal.stderr or "") else "seal-failed",
                {"stderr": seal.stderr.strip(), "workspace": ws},
            )

    # ---------- implementation attempts ----------

    def heldout_check_commands(self, ws):
        with open(os.path.join(ws, "manifest.json"), encoding="utf-8") as fh:
            manifest = json.load(fh)
        suite_args = " ".join(manifest["run"]["argv"][1:])  # drop leading python3
        return [
            f"python3 {HELDOUT} verify --workspace {ws}",
            f"PYTHONPATH=. python3 {suite_args}",
        ]

    def implementer_instructions(self, task, attempt, feedback):
        parts = [
            f"You are the IMPLEMENTER for task `{task['id']}`: {task['title']}",
            f"SPEC:\n{task['spec']}",
            f"PLAN GOAL: {self.plan.get('goal', '')}",
            "PLAN CONSTRAINTS:\n" + "\n".join(f"- {c}" for c in self.plan.get("constraints", [])),
            "DECISIONS (the why — do not re-decide these):\n"
            + "\n".join(f"- Q: {d['q']}\n  A: {d['a']}" for d in self.plan.get("decisions", [])),
            "You are on a dedicated branch in a dedicated worktree (your cwd). Implement the "
            "spec, run the task's own checks"
            + (f" ({'; '.join(task.get('checks', []))})" if task.get("checks") else "")
            + ", then COMMIT all changes (git add -A && git commit). Work not committed does "
            "not exist. Do not touch paths outside this repository.",
        ]
        if feedback:
            parts.append("PREVIOUS ATTEMPT FAILED THE GATE:\n" + feedback)
        return "\n\n".join(parts)

    def redacted_feedback(self, report, heldout_cmds):
        """Decision 5: full tails for the worker's own checks; counts-only for
        the held-out suite. A redaction bug is a silent leak — tested."""
        lines = []
        for check in report.get("checks", []):
            if check["cmd"] in heldout_cmds:
                tail_text = "\n".join(check.get("output_tail", []))
                counts = re.search(r"(FAILED \([^)]*\)|OK)\s*$", tail_text)
                lines.append(
                    f"- HELD-OUT SUITE: exit {check['exit']}"
                    + (f" — {counts.group(1)}" if counts else "")
                    + " (contents withheld by policy)"
                )
            else:
                tail = "\n".join(check.get("output_tail", [])[-40:])
                lines.append(f"- your check `{check['cmd']}`: exit {check['exit']}\n{tail}")
        if report.get("merge", {}).get("conflicts"):
            lines.append(f"- merge conflicts: {report['merge']['conflicts']}")
        return "\n".join(lines)

    def attempt_implementation(self, task, ws, attempt, feedback, tier="full"):
        branch = f"task/{task['id']}-a{attempt}"
        worktree = os.path.join(self.workdir, f"wt-{task['id']}-a{attempt}")
        # Idempotent redo (decision 7): a crashed prior run may have left the
        # branch/worktree behind — in-flight work is torn down and redone.
        git(self.repo, "worktree", "remove", "--force", worktree)
        git(self.repo, "worktree", "prune")
        shutil.rmtree(worktree, ignore_errors=True)
        git(self.repo, "branch", "-D", branch)
        rc, _, err = git(self.repo, "worktree", "add", "-b", branch, worktree, "main")
        if rc != 0:
            raise Blocker("worktree-failed", {"stderr": err})
        try:
            worker_key = "bare" if tier == "bare" else f"implementer_a{min(attempt, 2)}"
            result = self.launch(
                task_id=task["id"],
                role="implementer",
                attempt=attempt,
                worker=self.config["workers"][worker_key],
                isolation={
                    # the deny wall exists to protect a held-out suite; only
                    # tier full has one
                    "deny_read": [os.path.realpath(ws)] if ws else [],
                    "sandbox": True,
                    "network": True,
                },
                cwd=worktree,
                instructions=self.implementer_instructions(task, attempt, feedback),
                timeout_s=self.config["implementer_timeout_s"],
                tier=tier,
            )
            if not result.get("ok"):
                return {"outcome": "failed", "feedback": f"worker session failed: {json.dumps({k: result.get(k) for k in ('exit', 'timed_out', 'refused_reason')})}"}
            rc, ahead, _ = git(self.repo, "rev-list", "--count", f"main..{branch}")
            if rc != 0 or int(ahead or "0") == 0:
                return {"outcome": "failed", "feedback": "no commit was produced — work not committed does not exist"}

            # Instrument the implementer leg: how much product code it produced
            # (same three-dot diff the protected-paths check uses below).
            _, shortstat, _ = git(self.repo, "diff", "--shortstat", f"main...{branch}")
            churn = parse_shortstat(shortstat)

            # Protected paths (decision 8): checked BEFORE any gating.
            rc, names, _ = git(self.repo, "diff", "--name-only", f"main...{branch}")
            touched = [
                n for n in names.splitlines()
                if any(n == p.rstrip("/") or n.startswith(p) for p in self.config["protect_paths"])
            ]
            if touched:
                raise Blocker(
                    "protected-paths",
                    {"task": task["id"], "attempt": attempt, "paths": touched,
                     "branch": branch,
                     "note": "machinery-touching diff — operator hand-review, never auto-merged"},
                )

            if tier == "bare":
                # Tier bare (operator-declared): one strong session, commit,
                # land — no suite, no gate. The protected-paths interlock
                # above still applies at every tier; the ff-only rule still
                # guarantees exactly the committed tree lands or nothing does.
                rc, tip, err = git(self.repo, "rev-parse", branch)
                if rc != 0:
                    raise Blocker("merge-not-fast-forward", {"stderr": err})
                rc, _, err = git(self.repo, "merge", "--ff-only", tip)
                if rc != 0:
                    raise Blocker(
                        "merge-not-fast-forward",
                        {"stderr": err, "source_sha": tip,
                         "note": "main moved since the worktree was cut; nothing landed"},
                    )
                rc, sha, _ = git(self.repo, "rev-parse", "main")
                self.record(
                    "outcome", f"{task['id']}/merged",
                    {"sha": sha, "attempt": attempt, "tier": tier,
                     "impl_usage": result.get("usage"), "churn": churn},
                )
                return {"outcome": "merged", "sha": sha}

            heldout_cmds = self.heldout_check_commands(ws) if tier == "full" else []
            report_path = os.path.join(self.workdir, f"gate-{task['id']}-a{attempt}.json")
            gate_argv = [
                sys.executable, GATE, "run",
                "--repo", self.repo, "--base", "main", "--ref", branch,
                "--report", report_path,
            ]
            for cmd in list(task.get("checks", [])) + heldout_cmds:
                gate_argv += ["--check", cmd]
            gate = run(gate_argv)
            with open(report_path, encoding="utf-8") as fh:
                report = json.load(fh)
            self.record(
                "run", f"{task['id']}/gate-a{attempt}",
                {"ok": report["ok"], "report": report_path,
                 "worker": self.config["workers"][worker_key], "tier": tier,
                 "impl_usage": result.get("usage"), "churn": churn},
            )
            if gate.returncode == 0:
                verify = run([sys.executable, GATE, "verify", "--report", report_path, "--repo", self.repo])
                if verify.returncode != 0:
                    raise Blocker("gate-stamp-stale", {"report": report_path})
                # Land EXACTLY the judged tree, or refuse (closes the
                # verify->merge race): the branch was cut from the gated base,
                # so whenever fast-forward holds, the gate-judged merged tree
                # IS the source tip's tree. --ff-only by the report's pinned
                # SHA either lands that tree byte-identically or fails. A
                # non-FF here means main moved mid-flight or the worker
                # rewrote history — either way nothing lands unjudged.
                source_sha = report["source"]["sha"]
                rc, _, err = git(self.repo, "merge", "--ff-only", source_sha)
                if rc != 0:
                    raise Blocker(
                        "merge-not-fast-forward",
                        {"stderr": err, "source_sha": source_sha,
                         "note": "main moved since gating or branch history was "
                                 "rewritten; nothing was landed — operator adjudication"},
                    )
                rc, sha, _ = git(self.repo, "rev-parse", "main")
                self.record(
                    "outcome", f"{task['id']}/merged",
                    {"sha": sha, "attempt": attempt, "tier": tier},
                )
                return {"outcome": "merged", "sha": sha}
            return {"outcome": "failed", "feedback": self.redacted_feedback(report, heldout_cmds)}
        finally:
            git(self.repo, "worktree", "remove", "--force", worktree)
            git(self.repo, "worktree", "prune")
            shutil.rmtree(worktree, ignore_errors=True)

    def task_cycle(self, task, starting_attempt=1):
        tier = self.task_tier(task)
        if tier == "gate-only" and not task.get("checks"):
            raise Blocker(
                "gate-only-task-has-no-checks",
                {"task": task["id"],
                 "note": "a gate with nothing to run is a rubber stamp — add "
                         "checks or drop the task to tier bare (operator decision)"},
            )
        ws = self.ensure_suite(task) if tier == "full" else None
        feedback = None
        max_attempts = 1 if tier == "bare" else self.config["max_attempts"]
        for attempt in range(starting_attempt, max_attempts + 1):
            result = self.attempt_implementation(task, ws, attempt, feedback, tier=tier)
            if result["outcome"] == "merged":
                return result
            feedback = result["feedback"]
        raise Blocker(
            "bare-task-failed" if tier == "bare" else "attempts-exhausted",
            {"task": task["id"], "attempts": max_attempts, "tier": tier,
             "last_feedback": feedback},
        )

    # ---------- the walker (derive state, walk serially, halt on blocker) ----------

    def subject(self, suffix):
        return f"exec-loop/{self.plan_name}/{suffix}"

    def task_done(self, task):
        """Done iff a merge record's sha is an ancestor of current main —
        the artifacts are the bookkeeping (decision 7)."""
        for record in reversed(self.ledger_records()):
            if record.get("subject") == self.subject(f"{task['id']}/merged"):
                sha = record.get("data", {}).get("sha", "")
                rc, _, _ = git(self.repo, "merge-base", "--is-ancestor", sha, "main")
                if rc == 0:
                    return True
        return False

    def gates_recorded(self, task_id):
        """Attempts that reached a gate VERDICT. A crashed mid-attempt spawn
        with no gate record is redone as the same attempt number."""
        count = 0
        for record in self.ledger_records():
            if record.get("subject", "").startswith(self.subject(f"{task_id}/gate-a")):
                count += 1
        return count

    # ---------- whole-build closure ----------

    def plan_sha256(self):
        with open(self.snapshot_path, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()

    def closure_already_granted(self, main_sha, plan_hash):
        """A passing closure record bound to exactly this main SHA and plan
        snapshot — restart idempotency, same artifacts-are-the-bookkeeping
        rule as task_done (decision 7)."""
        for record in reversed(self.ledger_records()):
            if record.get("subject") == self.subject("closure"):
                data = record.get("data", {})
                if (
                    data.get("ok")
                    and data.get("sha") == main_sha
                    and data.get("plan_sha256") == plan_hash
                ):
                    return True
        return False

    def closure(self):
        """Whole-build closure (D3): plan completion is GRANTED by re-running
        every task's checks and every sealed held-out suite against final
        main, bound to this plan snapshot + main SHA — never claimed from
        per-task history. Per-task gates only run the current task's
        verifiers, so a later merge can regress an earlier task invisibly;
        this is the verifier that sees the whole build. Non-adaptive: the
        results reach only the operator, never a worker, so D2's per-suite
        reuse budget is untouched."""
        rc, main_sha, err = git(self.repo, "rev-parse", "main")
        if rc != 0:
            raise Blocker("closure-failed", {"stderr": err})
        plan_hash = self.plan_sha256()
        if self.closure_already_granted(main_sha, plan_hash):
            return 0
        checks = []
        for task in self.plan["tasks"]:
            checks += list(task.get("checks", []))
            if self.task_tier(task) != "full":
                continue  # only tier full has a sealed suite to replay
            try:
                checks += self.heldout_check_commands(self.workspace(task["id"]))
            except OSError as exc:
                raise Blocker(
                    "closure-missing-suite",
                    {"task": task["id"], "error": str(exc),
                     "note": "a sealed suite this plan merged under is gone — "
                             "closure cannot re-verify it; operator adjudication"},
                )
        if not checks:
            # An all-bare composition has nothing mechanical to re-run. The
            # tier was the operator's explicit recorded choice; closure
            # records that honestly rather than inventing a verdict.
            data = {"ok": True, "sha": main_sha, "plan_sha256": plan_hash,
                    "checks": 0,
                    "note": "no mechanical checks at this tier composition"}
            self.record("outcome", "closure", data)
            return 0
        report_path = os.path.join(self.workdir, f"closure-{main_sha[:12]}.json")
        gate_argv = [
            sys.executable, GATE, "run",
            "--repo", self.repo, "--base", "main", "--ref", "main",
            "--report", report_path,
        ]
        for cmd in checks:
            gate_argv += ["--check", cmd]
        gate = run(gate_argv)
        report = {}
        if os.path.exists(report_path):
            with open(report_path, encoding="utf-8") as fh:
                report = json.load(fh)
        data = {
            "ok": gate.returncode == 0,
            "sha": main_sha,
            "plan_sha256": plan_hash,
            "report": report_path,
            "checks": len(checks),
        }
        if gate.returncode == 0:
            self.record("outcome", "closure", data)
            return 0
        data["failing"] = [
            c["cmd"] for c in report.get("checks", []) if c.get("exit") != 0
        ]
        raise Blocker(
            "closure-failed",
            {**data,
             "note": "final main fails checks/suites that were green at their own "
                     "merges — a later change regressed an accepted task; the plan "
                     "is NOT complete"},
        )

    def walk(self):
        preflight = run(
            [sys.executable, PREFLIGHT, "check", self.snapshot_path, "--require-ratified"]
        )
        if preflight.returncode != 0:
            print(preflight.stdout or preflight.stderr, file=sys.stderr)
            raise UsageError("plan refused by preflight (is it ratified?)")
        order = run([sys.executable, PREFLIGHT, "order", self.snapshot_path])
        if order.returncode != 0:
            raise UsageError(f"preflight order failed: {order.stderr.strip()}")
        tasks_by_id = {t["id"]: t for t in self.plan["tasks"]}

        for task_id in order.stdout.split():
            task = tasks_by_id[task_id]
            if self.task_done(task):
                continue
            verdicts = self.gates_recorded(task_id)
            if verdicts >= self.config["max_attempts"]:
                raise Blocker(
                    "attempts-exhausted",
                    {"task": task_id, "attempts": verdicts,
                     "note": "derived from ledger on startup — prior run exhausted this task"},
                )
            self.task_cycle(task, starting_attempt=verdicts + 1)
        return self.closure()


class UsageError(Exception):
    pass


def acquire_lock(workdir):
    """One loop per plan-workdir (bundles, gate reports, worktrees live here).
    flock dies with the process — no stale locks."""
    import fcntl

    path = os.path.join(workdir, "loop.lock")
    handle = open(path, "w")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        return None
    return handle


def acquire_repo_lock(repo):
    """One loop per REPOSITORY (D4's single-writer is repo-scoped): two plans
    aimed at the same repo must contend no matter what they are named or
    where their heldout dirs live. The flock sits in the git common dir —
    shared by every checkout and worktree of the repo, outside any worker
    diff — and dies with the process."""
    import fcntl

    rc, common, _ = git(repo, "rev-parse", "--git-common-dir")
    if rc != 0:
        return None  # not a git repository — caller reports
    if not os.path.isabs(common):
        common = os.path.join(repo, common)
    handle = open(os.path.join(os.path.realpath(common), "exec-loop.lock"), "w")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        return None
    return handle


def main(argv=None):
    parser = argparse.ArgumentParser(prog="loop.py", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_run = sub.add_parser("run", help="walk a ratified plan task-by-task")
    p_run.add_argument("--plan", required=True, help="ratified plan.json")
    p_run.add_argument("--repo", required=True, help="target git repository")
    p_run.add_argument("--heldout-out", required=True, help="held-out workspace parent (outside the repo)")
    p_run.add_argument("--config", help="JSON file overriding DEFAULT_CONFIG keys")
    p_run.add_argument("--launcher", help="launcher executable (overrides config)")
    p_run.add_argument("--ledger", help="ledger file (default: <workdir>/ledger.jsonl)")
    args = parser.parse_args(argv)

    config = json.loads(json.dumps(DEFAULT_CONFIG))  # deep copy
    if args.config:
        try:
            with open(args.config, encoding="utf-8") as fh:
                config.update(json.load(fh))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"error: cannot read config: {exc}", file=sys.stderr)
            return 2
    if args.launcher:
        config["launcher"] = args.launcher
    if args.ledger:
        config["ledger"] = args.ledger

    try:
        loop = Loop(args.plan, args.repo, args.heldout_out, config)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    repo_lock = acquire_repo_lock(loop.repo)
    if repo_lock is None:
        print(
            "error: another exec-loop already holds this repository's lock "
            "(one writer per repo, regardless of plan name) — or the target "
            "is not a git repository",
            file=sys.stderr,
        )
        return 2
    lock = acquire_lock(loop.workdir)
    if lock is None:
        repo_lock.close()
        print("error: another exec-loop already holds this plan's lock", file=sys.stderr)
        return 2
    try:
        loop.walk()
        print(json.dumps({"ok": True, "plan": loop.plan_name, "ledger": loop.ledger}))
        return 0
    except UsageError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except Blocker as blocker:
        payload = {
            "reason": blocker.reason,
            "detail": blocker.detail,
            "ts": utcnow(),
            "note": "all automated progress is stopped; operator adjudication required",
        }
        blocker_path = os.path.join(loop.workdir, "blocker.json")
        with open(blocker_path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, sort_keys=True)
            fh.write("\n")
        try:
            loop.record("note", f"blocker/{blocker.reason}", blocker.detail)
        except Blocker:
            pass  # ledger unavailable must not mask the original blocker
        print(json.dumps({"ok": False, "blocker": blocker_path, "reason": blocker.reason}))
        return 1
    finally:
        lock.close()
        repo_lock.close()


if __name__ == "__main__":
    sys.exit(main())
