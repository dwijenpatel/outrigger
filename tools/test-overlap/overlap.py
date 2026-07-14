#!/usr/bin/env python3
"""test-overlap - what does a blind held-out suite catch that self-tests miss?

Standalone: Python stdlib + git only. One thing well: measure the overlap in
*discrimination* between two test suites that target the same code, so you can
see how much a blind held-out suite adds on top of an implementer's own tests
(and where both are blind). Terminal telemetry - nothing gates on its output;
it is read by a person.

Two lenses over one repo state:

  line-reach : which source lines each suite runs. Cheap, but it UNDERCOUNTS -
               a wrong-rounding bug runs the same source line as correct
               rounding, so line coverage cannot see it.

  mutation   : generate many small wrong-versions of the source (flip `<` to
               `<=`, `+` to `-`, an argument index `0` to `1`, `True` to
               `False`, drop a `not`, tweak a constant); for each, does suite A
               notice (some test fails)? does suite B notice? The DIFFERENTIAL
               cells - caught by exactly one suite - are the signal. "caught by
               neither" mixes genuine shared blind spots with equivalent
               mutants (wrong-versions that are behaviourally identical), so
               read that bucket by hand.

It assumes stdlib-`unittest`-discoverable suites and the project's run
convention: the code under test importable with the repo root on PYTHONPATH.
A suite inside the repo moves with the mutated checkout; a suite outside the
repo (a sealed held-out suite) stays put and imports the mutated code via
PYTHONPATH - the same run contract the held-out-suite tool seals.

Exit codes: 0 measured ok . 1 a suite is not green on the pristine tree
(precondition failed, nothing measured) . 2 usage/input error.
"""
from __future__ import annotations

import argparse
import ast
import copy
import datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile

CONTRACT = 1
DEFAULT_TIMEOUT = 60


def _read(p: str) -> str:
    with open(p) as f:
        return f.read()


def _write(p: str, s: str) -> None:
    with open(p, "w") as f:
        f.write(s)


def _env(checkout: str) -> dict:
    return {**os.environ, "PYTHONPATH": checkout, "PYTHONDONTWRITEBYTECODE": "1"}


def _now() -> str:
    return datetime.datetime.now(datetime.UTC).replace(microsecond=0).isoformat()


def _git_head(repo: str) -> str | None:
    try:
        r = subprocess.run(["git", "-C", repo, "rev-parse", "HEAD"],
                           capture_output=True, text=True, timeout=10)
        return r.stdout.strip() if r.returncode == 0 else None
    except Exception:
        return None


def make_checkout(repo: str) -> str:
    d = tempfile.mkdtemp(prefix="overlap-checkout-")
    shutil.copytree(repo, d, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"))
    return d


def resolve_suite(checkout: str, repo: str, path: str) -> tuple[str, str, str]:
    """(discover-start, discover-top, kind). A suite under the repo is remapped
    into the mutated checkout (kind='internal'); a suite elsewhere is used as-is
    and imports the mutated code via PYTHONPATH (kind='external')."""
    repo_abs = os.path.abspath(repo)
    p = path if os.path.isabs(path) else os.path.join(repo_abs, path)
    p = os.path.abspath(p)
    if p == repo_abs or p.startswith(repo_abs + os.sep):
        rel = os.path.relpath(p, repo_abs)
        return (os.path.join(checkout, rel), checkout, "internal")
    return (p, p, "external")


def run_suite(checkout: str, start: str, top: str, timeout: int) -> int:
    try:
        r = subprocess.run(
            [sys.executable, "-B", "-m", "unittest", "discover", "-s", start, "-t", top],
            cwd=checkout, env=_env(checkout), capture_output=True, text=True, timeout=timeout)
        return r.returncode
    except subprocess.TimeoutExpired:
        return 124


def imports_ok(checkout: str, pkg_name: str, timeout: int) -> bool:
    try:
        r = subprocess.run([sys.executable, "-B", "-c", f"import {pkg_name}"],
                           cwd=checkout, env=_env(checkout), capture_output=True,
                           text=True, timeout=timeout)
        return r.returncode == 0
    except subprocess.TimeoutExpired:
        return False


# ---------------- line-reach lens (runs as a subprocess entrypoint) ----------------
def _covworker() -> None:
    import unittest
    pkg_dir, start, top, out = (os.path.abspath(sys.argv[2]), sys.argv[3],
                                sys.argv[4], sys.argv[5])
    covered: set = set()

    def tr(frame, event, arg):
        fn = frame.f_code.co_filename
        if not fn.startswith(pkg_dir):
            return None
        if event == "line":
            covered.add((os.path.relpath(fn, pkg_dir), frame.f_lineno))
        return tr

    loader = unittest.TestLoader()
    with open(os.devnull, "w") as devnull:
        sys.settrace(tr)
        try:
            suite = loader.discover(start, top_level_dir=top)
            res = unittest.TextTestRunner(stream=devnull, verbosity=0).run(suite)
        finally:
            sys.settrace(None)
    with open(out, "w") as f:
        json.dump({"covered": sorted([list(x) for x in covered]),
                   "run": res.testsRun, "ok": res.wasSuccessful()}, f)


def coverage_for(checkout: str, pkg_dir: str, start: str, top: str, tag: str, timeout: int) -> dict:
    out = os.path.join(checkout, f"_cov_{tag}.json")
    subprocess.run([sys.executable, "-B", os.path.abspath(__file__),
                    "_covworker", pkg_dir, start, top, out],
                   cwd=checkout, env=_env(checkout), timeout=max(timeout, 120), check=True)
    with open(out) as f:
        return json.load(f)


# ---------------- mutation lens ----------------
CMP = {ast.Lt: [ast.LtE, ast.Gt], ast.LtE: [ast.Lt, ast.GtE],
       ast.Gt: [ast.GtE, ast.Lt], ast.GtE: [ast.Gt, ast.LtE],
       ast.Eq: [ast.NotEq], ast.NotEq: [ast.Eq]}
BIN = {ast.Add: [ast.Sub], ast.Sub: [ast.Add], ast.Mult: [ast.Div],
       ast.Div: [ast.Mult], ast.Mod: [ast.Mult]}
BOOL = {ast.And: ast.Or, ast.Or: ast.And}


class _Mut(ast.NodeTransformer):
    """Apply exactly one mutation, at the node tagged with the matching _mid."""

    def __init__(self, mid: int, kind: str, payload):
        self.mid, self.kind, self.payload, self.done = mid, kind, payload, False

    def visit(self, node):
        self.generic_visit(node)
        if getattr(node, "_mid", None) == self.mid:
            self.done = True
            if self.kind == "cmp":
                node.ops = [self.payload()]
            elif self.kind in ("bin", "bool"):
                node.op = self.payload()
            elif self.kind == "const":
                node.value = self.payload
            elif self.kind == "not":
                return node.operand
        return node


def gen_mutants(source: str, fname: str) -> list[tuple[str, str]]:
    """Yield (description, mutated-source) pairs - one single-point wrong-version
    each. Covers comparison-operator swaps, arithmetic swaps, boolean swaps,
    `not`-removal, and numeric/boolean constant tweaks. String literals, slice
    bounds, and control-flow shape are deliberately not mutated (noisy / low
    signal); narrow with --mutate if a file adds noise."""
    tree = ast.parse(source)
    for i, n in enumerate(ast.walk(tree)):
        n._mid = i
    cands: list = []
    for n in ast.walk(tree):
        ln = getattr(n, "lineno", "?")
        if isinstance(n, ast.Compare) and len(n.ops) == 1:
            for r in CMP.get(type(n.ops[0]), []):
                cands.append((n._mid, "cmp", r, f"{fname}:{ln} {type(n.ops[0]).__name__}->{r.__name__}"))
        elif isinstance(n, ast.BinOp):
            for r in BIN.get(type(n.op), []):
                cands.append((n._mid, "bin", r, f"{fname}:{ln} {type(n.op).__name__}->{r.__name__}"))
        elif isinstance(n, ast.BoolOp) and type(n.op) in BOOL:
            r = BOOL[type(n.op)]
            cands.append((n._mid, "bool", r, f"{fname}:{ln} {type(n.op).__name__}->{r.__name__}"))
        elif isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.Not):
            cands.append((n._mid, "not", None, f"{fname}:{ln} drop-not"))
        elif isinstance(n, ast.Constant):
            v = n.value
            if isinstance(v, bool):
                cands.append((n._mid, "const", (not v), f"{fname}:{ln} {v}->{not v}"))
            elif isinstance(v, int):
                cands.append((n._mid, "const", v + 1, f"{fname}:{ln} {v}->{v + 1}"))
                if v != 0:
                    cands.append((n._mid, "const", 0, f"{fname}:{ln} {v}->0"))
            elif isinstance(v, float):
                cands.append((n._mid, "const", v + 1.0, f"{fname}:{ln} {v}->{v + 1.0}"))
    out: list = []
    for (mid, kind, payload, desc) in cands:
        m = _Mut(mid, kind, payload)
        newtree = m.visit(copy.deepcopy(tree))
        if not m.done:
            continue
        try:
            ast.fix_missing_locations(newtree)
            src2 = ast.unparse(newtree)
        except Exception:
            continue
        if src2 != source:
            out.append((desc, src2))
    return out


def _default_targets(pkg_path: str) -> list[str]:
    if not os.path.isdir(pkg_path):
        return []
    return sorted(f for f in os.listdir(pkg_path)
                  if f.endswith(".py") and f != "__init__.py")


def measure(repo: str, source_pkg: str, suite_a: tuple[str, str], suite_b: tuple[str, str],
            mutate_files: list[str] | None = None, timeout: int = DEFAULT_TIMEOUT,
            stage: str = "all") -> dict:
    repo = os.path.abspath(repo)
    pkg_name = os.path.basename(source_pkg.rstrip("/"))
    pkg_path = os.path.join(repo, source_pkg)
    la, pa = suite_a
    lb, pb = suite_b
    checkout = make_checkout(repo)
    a_start, a_top, a_kind = resolve_suite(checkout, repo, pa)
    b_start, b_top, b_kind = resolve_suite(checkout, repo, pb)
    pkg_dir = os.path.join(checkout, source_pkg)

    report: dict = {
        "contract": CONTRACT, "tool": "test-overlap", "generated_at": _now(),
        "repo": repo, "repo_head": _git_head(repo), "source_pkg": source_pkg,
        "suites": {la: {"path": pa, "kind": a_kind}, lb: {"path": pb, "kind": b_kind}},
    }

    ra = run_suite(checkout, a_start, a_top, timeout)
    rb = run_suite(checkout, b_start, b_top, timeout)
    report["pristine"] = {la: ra, lb: rb, "ok": ra == 0 and rb == 0}
    if not report["pristine"]["ok"]:
        report["ok"] = False
        return report

    cov_a = coverage_for(checkout, pkg_dir, a_start, a_top, "a", timeout)
    cov_b = coverage_for(checkout, pkg_dir, b_start, b_top, "b", timeout)
    A = set(map(tuple, cov_a["covered"]))
    B = set(map(tuple, cov_b["covered"]))
    report["line_reach"] = {
        f"tests_run_{la}": cov_a["run"], f"tests_run_{lb}": cov_b["run"],
        f"lines_{la}": len(A), f"lines_{lb}": len(B), "lines_both": len(A & B),
        f"lines_only_{la}": sorted(f"{f}:{l}" for f, l in (A - B)),
        f"lines_only_{lb}": sorted(f"{f}:{l}" for f, l in (B - A)),
    }
    if stage == "lens1":
        report["ok"] = True
        return report

    targets = mutate_files or _default_targets(pkg_path)
    results: list = []
    for fname in targets:
        path = os.path.join(pkg_dir, fname)
        if not os.path.exists(path):
            continue
        original = _read(path)
        for (desc, src2) in gen_mutants(original, fname):
            _write(path, src2)
            try:
                if not imports_ok(checkout, pkg_name, timeout):
                    results.append((desc, "invalid"))
                    continue
                ka = run_suite(checkout, a_start, a_top, timeout) != 0
                kb = run_suite(checkout, b_start, b_top, timeout) != 0
                cell = ("both" if ka and kb else f"only_{la}" if ka
                        else f"only_{lb}" if kb else "neither")
                results.append((desc, cell))
            finally:
                _write(path, original)
        _write(path, original)

    valid = [r for r in results if r[1] != "invalid"]
    buckets: dict = {}
    for desc, cell in valid:
        buckets.setdefault(cell, []).append(desc)
    n = len(valid)
    both = len(buckets.get("both", []))
    report["mutation"] = {
        "mutate_files": targets, "generated": len(results),
        "invalid": len(results) - n, "valid": n,
        "caught_by_both": both,
        f"caught_only_by_{la}": len(buckets.get(f"only_{la}", [])),
        f"caught_only_by_{lb}": len(buckets.get(f"only_{lb}", [])),
        "caught_by_neither": len(buckets.get("neither", [])),
        f"mutation_score_{la}": round((both + len(buckets.get(f"only_{la}", []))) / n, 4) if n else None,
        f"mutation_score_{lb}": round((both + len(buckets.get(f"only_{lb}", []))) / n, 4) if n else None,
        "examples": {
            f"only_{la}": buckets.get(f"only_{la}", []),
            f"only_{lb}": buckets.get(f"only_{lb}", []),
            "neither": buckets.get("neither", []),
        },
    }
    report["ok"] = True
    return report


def _summary(report: dict) -> str:
    la, lb = list(report["suites"].keys())
    lines = [f"test-overlap  repo={report['repo_head'] or '?'}  pkg={report['source_pkg']}"]
    p = report["pristine"]
    lines.append(f"pristine: {la} rc={p[la]}  {lb} rc={p[lb]}  ok={p['ok']}")
    if not p["ok"]:
        lines.append("ABORT: a suite is not green on the pristine tree; nothing measured.")
        return "\n".join(lines)
    lr = report["line_reach"]
    lines.append(f"line-reach: {la}={lr[f'lines_{la}']} {lb}={lr[f'lines_{lb}']} "
                 f"both={lr['lines_both']} only-{la}={len(lr[f'lines_only_{la}'])} "
                 f"only-{lb}={len(lr[f'lines_only_{lb}'])}")
    if "mutation" in report:
        m = report["mutation"]
        lines.append(f"mutation: {m['valid']} valid wrong-versions "
                     f"({m['invalid']} discarded)")
        lines.append(f"  caught by both        : {m['caught_by_both']}")
        lines.append(f"  caught only by {la:<7}: {m[f'caught_only_by_{la}']}")
        lines.append(f"  caught only by {lb:<7}: {m[f'caught_only_by_{lb}']}")
        lines.append(f"  caught by neither     : {m['caught_by_neither']}  "
                     f"(mix of shared gaps + equivalent mutants - read by hand)")
        lines.append(f"  mutation score: {la}={m[f'mutation_score_{la}']} {lb}={m[f'mutation_score_{lb}']}")
    return "\n".join(lines)


def _parse_suite(s: str) -> tuple[str, str]:
    if "=" not in s:
        raise argparse.ArgumentTypeError(f"suite must be LABEL=PATH, got {s!r}")
    label, path = s.split("=", 1)
    if not label or not path:
        raise argparse.ArgumentTypeError(f"suite must be LABEL=PATH, got {s!r}")
    return (label, path)


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "_covworker":
        _covworker()
        return 0
    ap = argparse.ArgumentParser(description="Measure discrimination overlap between two test suites.")
    ap.add_argument("--repo", required=True, help="repo under test (copied to a temp checkout)")
    ap.add_argument("--source-pkg", required=True,
                    help="package path under --repo whose lines are traced and files mutated")
    ap.add_argument("--suite-a", required=True, type=_parse_suite, metavar="LABEL=PATH",
                    help="first suite, e.g. self=tests")
    ap.add_argument("--suite-b", required=True, type=_parse_suite, metavar="LABEL=PATH",
                    help="second suite, e.g. held=/abs/path/to/sealed/suite")
    ap.add_argument("--mutate", default=None,
                    help="comma-separated files under --source-pkg to mutate "
                         "(default: every *.py except __init__.py)")
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="per-suite-run seconds")
    ap.add_argument("--stage", choices=["all", "lens1"], default="all")
    ap.add_argument("--out", default="overlap-report.json", help="report JSON path")
    args = ap.parse_args()

    if args.suite_a[0] == args.suite_b[0]:
        print("error: the two suites need distinct labels", file=sys.stderr)
        return 2
    mutate = [f.strip() for f in args.mutate.split(",")] if args.mutate else None

    report = measure(args.repo, args.source_pkg, args.suite_a, args.suite_b,
                     mutate_files=mutate, timeout=args.timeout, stage=args.stage)
    with open(args.out, "w") as f:
        json.dump(report, f, indent=2)
    print(_summary(report))
    print(f"\nreport -> {args.out}")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
