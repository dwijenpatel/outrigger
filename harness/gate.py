#!/usr/bin/env python3
"""Merge gate — clean-checkout reproduction + all-must-pass verdicts (D2).

Design §7 (2026-07-04 amendments). The gate is the objective merge decision:
nothing merges on a model's say-so. Fixed, non-reorderable step order — each
step's placement is justified:

1. ``require_clean`` — a dirty source tree means the diff under judgment is not
   what would merge; refuse before anything else.
2. **diff paths** — resolved from git (``base...branch``), because every
   later path-based check must see the *actual* diff, not the task's claim.
3. **machinery paths** — a task branch editing the loop's own machinery is
   rejected before we spend a checkout on it.
4. **risk floor** — mis-tagged security work is caught before validation cost,
   with the floor map loaded from the ratified base ref (never the branch under
   judgment).
5. **clean checkout** — the branch is reproduced in a scratch clone; visible
   tests run there, not in anyone's working tree.
6. **held-out drop** — the vault manifest must be intact (C4).
7. **verdicts** — every panel verdict must be PASS; an empty panel is a
   failure, not a pass (fail closed).
8. **findings triage** — typed findings (severity × action) against per-step
   auto-fix budgets; any ``error`` finding blocks; mechanical fixes belong to
   the gate pipeline, never the implementer being judged.

Output follows turn economy (§6.1): aggregate header, definitive empties,
test output tail-truncated with the full log spilled to the evidence
directory (the §7 evidence trail) and its path returned.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import tempfile

from . import hooks as _hooks
from . import vault as _vault
from .runlog import PROFILES

SEVERITIES = ("error", "warning", "info")
ACTIONS = ("auto-fix", "ask-user", "no-op")
VERDICTS = ("PASS", "FAIL")

#: Auto-fix budgets per finding origin step; review-class findings default to 0
#: — "always human" (§7). Config may raise mechanical budgets, never silently.
DEFAULT_AUTOFIX_BUDGETS = {"lint": 5, "format": 10, "review": 0}

TAIL_CHARS = 20_000  # failures live at the end (tool-surface research §1)


class GateError(ValueError):
    pass


# -- findings -------------------------------------------------------------------


def validate_finding(doc: dict, i: int = 0) -> dict:
    if not isinstance(doc, dict):
        raise GateError(f"finding {i}: must be an object")
    if doc.get("severity") not in SEVERITIES:
        raise GateError(f"finding {i}: severity {doc.get('severity')!r} "
                        f"not in {SEVERITIES}")
    if doc.get("action") not in ACTIONS:
        raise GateError(f"finding {i}: action {doc.get('action')!r} "
                        f"not in {ACTIONS}")
    if not isinstance(doc.get("summary"), str) or not doc["summary"]:
        raise GateError(f"finding {i}: needs a non-empty summary")
    out = dict(doc)
    out.setdefault("step", "unknown")
    return out


def triage_findings(findings: list, budgets: dict | None = None) -> dict:
    """severity × action triage. error → blocker regardless of action;
    warning/auto-fix consumes the origin step's budget (overflow → needs_human);
    warning/ask-user → needs_human; info/no-op → recorded only."""
    budgets = dict(DEFAULT_AUTOFIX_BUDGETS, **(budgets or {}))
    validated = [validate_finding(f, i) for i, f in enumerate(findings)]
    used: dict = {}
    out = {"blockers": [], "auto_fix": [], "needs_human": [], "info": []}
    for f in validated:
        if f["severity"] == "error":
            out["blockers"].append(f)
        elif f["severity"] == "warning" and f["action"] == "auto-fix":
            budget = budgets.get(f["step"], 0)
            used[f["step"]] = used.get(f["step"], 0) + 1
            if used[f["step"]] <= budget:
                out["auto_fix"].append(f)
            else:
                out["needs_human"].append(dict(f, budget_exceeded=True))
        elif f["action"] == "ask-user" or f["severity"] == "warning":
            out["needs_human"].append(f)
        else:
            out["info"].append(f)
    return out


# -- verdicts --------------------------------------------------------------------


def read_verdicts(verdict_dir: str) -> list:
    """Load panel verdict JSON files. Malformed verdicts are loud — a verdict
    that can't be read must never count as a pass."""
    if not os.path.isdir(verdict_dir):
        raise GateError(f"verdict dir {verdict_dir!r} does not exist")
    verdicts = []
    for name in sorted(os.listdir(verdict_dir)):
        if not name.endswith(".json"):
            continue
        path = os.path.join(verdict_dir, name)
        try:
            with open(path) as fh:
                doc = json.load(fh)
        except json.JSONDecodeError as exc:
            raise GateError(f"verdict {path} corrupt: {exc}") from None
        if not isinstance(doc, dict) or doc.get("verdict") not in VERDICTS:
            raise GateError(f"verdict {path}: needs verdict in {VERDICTS}")
        if not isinstance(doc.get("lens"), str) or not doc["lens"]:
            raise GateError(f"verdict {path}: needs a lens")
        verdicts.append(dict(doc, _file=name))
    return verdicts


def check_verdicts(verdicts: list, min_lenses: int = 1) -> dict:
    """All-must-pass (§7 — consensus voting only for redundant panels, which is
    not this path). An empty or too-small panel fails closed."""
    if len(verdicts) < min_lenses:
        return {"ok": False,
                "why": f"panel too small: {len(verdicts)} verdict(s), "
                       f"need >= {min_lenses} — no panel, no pass"}
    failing = [v for v in verdicts if v["verdict"] != "PASS"]
    if failing:
        return {"ok": False,
                "why": "all-must-pass violated: " + ", ".join(
                    f"{v['lens']}=FAIL" for v in failing),
                "failing": [v["lens"] for v in failing]}
    return {"ok": True, "why": f"{len(verdicts)} lens(es), all PASS",
            "lenses": [v["lens"] for v in verdicts]}


# -- git helpers -----------------------------------------------------------------


def _git(repo: str, *args, check=True) -> subprocess.CompletedProcess:
    out = subprocess.run(["git", "-C", repo, *args],
                         capture_output=True, text=True, timeout=120)
    if check and out.returncode != 0:
        raise GateError(f"git {' '.join(args)} failed: {out.stderr.strip()}")
    return out


def diff_paths(repo: str, base: str, branch: str) -> list:
    out = _git(repo, "diff", "--name-only", f"{base}...{branch}")
    return [ln for ln in out.stdout.splitlines() if ln.strip()]


def clean_checkout(repo: str, ref: str, dest: str) -> str:
    """Reproduce ``ref`` in a scratch clone — the gate judges committed state
    only, never anyone's working tree."""
    _git(".", "clone", "-q", "--no-hardlinks", repo, dest)
    _git(dest, "checkout", "-q", ref)
    return dest


# -- the gate --------------------------------------------------------------------


def run_gate(repo: str, branch: str, base: str = "main",
             test_cmd: str | None = None,
             verdict_dir: str | None = None,
             findings: list | None = None,
             autofix_budgets: dict | None = None,
             task_profile: str = "routine",
             floor_config_path: str | None = None,
             vault_path: str | None = None,
             evidence_dir: str | None = None,
             require_clean: bool = True,
             min_lenses: int = 1,
             test_timeout: int = 1800) -> dict:
    """Run the full gate. Fail-fast on the first blocking step; every executed
    step is reported. Returns the report dict (see ``render_report``)."""
    if task_profile not in PROFILES:
        raise GateError(f"unknown profile {task_profile!r}")
    steps: list = []
    report = {"ok": False, "branch": branch, "base": base, "steps": steps,
              "findings": None, "evidence_dir": evidence_dir,
              "test_output_tail": None, "full_log": None}

    def step(name, ok, detail):
        steps.append({"step": name, "ok": ok, "detail": detail})
        return ok

    def finish(ok):
        report["ok"] = ok
        if evidence_dir:
            os.makedirs(evidence_dir, exist_ok=True)
            with open(os.path.join(evidence_dir, "gate-report.json"), "w") as fh:
                json.dump(report, fh, indent=2, sort_keys=True)
                fh.write("\n")
        return report

    # 1. require-clean
    dirty = _git(repo, "status", "--porcelain").stdout.strip()
    if require_clean and dirty:
        step("require_clean", False,
             f"source tree dirty ({len(dirty.splitlines())} entries) — the "
             f"diff under judgment is not what would merge")
        return finish(False)
    step("require_clean", True, "clean" if not dirty else "dirty tree allowed")

    # 2. diff paths
    try:
        paths = diff_paths(repo, base, branch)
    except GateError as exc:
        step("diff_paths", False, str(exc))
        return finish(False)
    step("diff_paths", True, f"{len(paths)} file(s) changed")
    if not paths:
        step("empty_diff", True, "empty diff — nothing to gate, remaining "
                                 "steps skipped")
        return finish(True)

    # 3. machinery paths
    machinery = [p for p in paths
                 if any(_hooks.path_matches(p, g) for g in _hooks.MACHINERY_GLOBS)]
    if machinery and not _hooks.MACHINERY_BRANCH_ALLOW.match(branch):
        step("machinery_paths", False,
             f"task branch edits loop machinery: {machinery[:5]}")
        return finish(False)
    step("machinery_paths", True, "no protected machinery edits")

    # 4. risk floor (config from the ratified base ref)
    if floor_config_path:
        cfg = _hooks.load_ratified_config(repo, floor_config_path, ref=base)
        if cfg is None:
            step("risk_floor", False,
                 f"cannot load {floor_config_path} from {base} (fail-closed)")
            return finish(False)
        floor = _hooks.check_risk_floor(
            task_profile, paths, _hooks.validate_floor_map(cfg.get("floors", [])))
        if not step("risk_floor", floor["ok"], floor["why"]):
            return finish(False)
    else:
        step("risk_floor", True, "no floor config supplied (caller's choice)")

    # 5. clean checkout + visible tests
    if test_cmd:
        with tempfile.TemporaryDirectory(prefix="gate-checkout-") as scratch:
            dest = os.path.join(scratch, "co")
            try:
                clean_checkout(repo, branch, dest)
            except GateError as exc:
                step("clean_checkout", False, str(exc))
                return finish(False)
            step("clean_checkout", True, f"reproduced {branch}")
            try:
                proc = subprocess.run(
                    shlex.split(test_cmd), cwd=dest, capture_output=True,
                    text=True, timeout=test_timeout)
            except (OSError, subprocess.TimeoutExpired) as exc:
                step("visible_tests", False, f"test command failed to run: {exc}")
                return finish(False)
            output = (proc.stdout or "") + (proc.stderr or "")
            report["test_output_tail"] = output[-TAIL_CHARS:]
            if evidence_dir:
                os.makedirs(evidence_dir, exist_ok=True)
                full = os.path.join(evidence_dir, "test-output-full.log")
                with open(full, "w") as fh:
                    fh.write(output)
                report["full_log"] = full
            if not step("visible_tests", proc.returncode == 0,
                        f"exit {proc.returncode}"
                        + (f"; full log: {report['full_log']} (grep it for "
                           f"earlier context)" if report["full_log"] and
                           proc.returncode != 0 else "")):
                return finish(False)
    else:
        step("visible_tests", True, "no test command supplied (caller's choice)")

    # 6. held-out drop
    if vault_path:
        try:
            drop = _vault.check_heldout_drop(_vault.load_manifest(vault_path),
                                             _vault.build_manifest(vault_path))
        except _vault.VaultError as exc:
            step("heldout_drop", False, f"{exc} (fail-closed)")
            return finish(False)
        if not step("heldout_drop", drop["ok"], drop["why"]):
            return finish(False)
    else:
        step("heldout_drop", True, "no vault supplied (caller's choice)")

    # 7. verdicts, all-must-pass
    if verdict_dir is not None:
        try:
            verdicts = read_verdicts(verdict_dir)
        except GateError as exc:
            step("verdicts", False, f"{exc} (fail-closed)")
            return finish(False)
        panel = check_verdicts(verdicts, min_lenses=min_lenses)
        if not step("verdicts", panel["ok"], panel["why"]):
            return finish(False)
    else:
        step("verdicts", True, "no panel dir supplied (caller's choice)")

    # 8. findings triage
    triage = triage_findings(findings or [], autofix_budgets)
    report["findings"] = triage
    if triage["blockers"]:
        step("findings", False,
             f"{len(triage['blockers'])} error finding(s) block")
        return finish(False)
    step("findings", True,
         f"{len(triage['auto_fix'])} auto-fixable, "
         f"{len(triage['needs_human'])} for a human, "
         f"{len(triage['info'])} informational")
    return finish(True)


def render_report(report: dict) -> str:
    """Turn-economy rendering: aggregate header first, definitive empties."""
    steps = report["steps"]
    passed = sum(1 for s in steps if s["ok"])
    header = (f"gate: {'PASS' if report['ok'] else 'FAIL'} · "
              f"{passed} of {len(steps)} steps ok · branch {report['branch']} "
              f"vs {report['base']}")
    lines = [header]
    failing = [s for s in steps if not s["ok"]]
    if failing:
        lines.append(f"blocking step: {failing[0]['step']} — "
                     f"{failing[0]['detail']}")
    else:
        lines.append("blocking step: none")
    tri = report.get("findings")
    if tri:
        lines.append(f"findings: {len(tri['blockers'])} blocker · "
                     f"{len(tri['auto_fix'])} auto-fix · "
                     f"{len(tri['needs_human'])} needs-human · "
                     f"{len(tri['info'])} info")
    else:
        lines.append("findings: none recorded")
    if report.get("full_log"):
        lines.append(f"full test log: {report['full_log']}")
    lines.append("")
    lines.append("| step | ok | detail |")
    lines.append("|---|---|---|")
    for s in steps:
        detail = s["detail"][:100]
        lines.append(f"| {s['step']} | {'ok' if s['ok'] else 'FAIL'} | {detail} |")
    return "\n".join(lines)
