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
    repro = doc.get("repro")
    if repro is not None:
        if not isinstance(repro, dict) or \
                not isinstance(repro.get("command"), str) or \
                not repro["command"].strip():
            raise GateError(f"finding {i}: repro must be an object with a "
                            f"non-empty 'command'")
        if repro.get("expect_exit", "nonzero") not in ("nonzero", "zero"):
            raise GateError(f"finding {i}: repro.expect_exit must be "
                            f"'nonzero' or 'zero'")
    out = dict(doc)
    out.setdefault("step", "unknown")
    return out


# -- H4: repro replay — a FAIL must demonstrate itself before it blocks -------------


def replay_repro(finding: dict, cwd: str, timeout: int = 300) -> dict:
    """Execute a finding's repro in the clean checkout. ``reproduced`` means
    the command demonstrated the claimed failure (default expectation:
    nonzero exit; optional expect_substring on combined output)."""
    repro = finding.get("repro")
    if not isinstance(repro, dict) or \
            not isinstance(repro.get("command"), str) or \
            not repro["command"].strip():
        return {"replayed": False, "reproduced": None,
                "why": "no executable repro on the finding"}
    try:
        proc = subprocess.run(shlex.split(repro["command"]), cwd=cwd,
                              capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
        return {"replayed": True, "reproduced": False,
                "why": f"repro command failed to run: {exc}"}
    output = (proc.stdout or "") + (proc.stderr or "")
    expect_exit = repro.get("expect_exit", "nonzero")
    exit_ok = ((proc.returncode != 0) if expect_exit == "nonzero"
               else (proc.returncode == 0))
    sub = repro.get("expect_substring")
    sub_ok = (sub in output) if isinstance(sub, str) and sub else True
    why = f"exit {proc.returncode} (expected {expect_exit})"
    if isinstance(sub, str) and sub:
        why += f"; expected substring {'found' if sub_ok else 'MISSING'}"
    return {"replayed": True, "reproduced": exit_ok and sub_ok, "why": why,
            "exit": proc.returncode}


def replay_failing_verdicts(verdicts: list, cwd: str, strict: bool = False,
                            timeout: int = 300) -> dict:
    """Adjudicate the error findings of FAIL verdicts by replaying their
    repros. Reproduced findings confirm the block; unreproduced findings are
    downgraded to ask-user (false-FAIL candidates — human adjudication, not
    escalation fuel); findings with no repro block conservatively unless
    ``strict``, where they downgrade too. Telemetry feeds the run-log (§8)."""
    confirmed, downgraded, no_repro = [], [], []
    telemetry = {"error_findings": 0, "replayed": 0, "reproduced": 0,
                 "unreproduced": 0, "no_repro": 0, "by_lens": {}}

    def lens_bucket(lens):
        return telemetry["by_lens"].setdefault(
            lens, {"reproduced": 0, "unreproduced": 0, "no_repro": 0})

    for verdict in verdicts:
        if verdict.get("verdict") == "PASS":
            continue
        lens = verdict.get("lens", "unknown")
        for i, raw in enumerate(verdict.get("findings") or []):
            finding = validate_finding(raw, i)
            if finding["severity"] != "error":
                continue
            telemetry["error_findings"] += 1
            result = replay_repro(finding, cwd, timeout)
            if not result["replayed"]:
                telemetry["no_repro"] += 1
                lens_bucket(lens)["no_repro"] += 1
                if strict:
                    downgraded.append(dict(finding, action="ask-user",
                                           unreplayable=True, lens=lens))
                else:
                    no_repro.append(dict(finding, lens=lens))
                continue
            telemetry["replayed"] += 1
            if result["reproduced"]:
                telemetry["reproduced"] += 1
                lens_bucket(lens)["reproduced"] += 1
                confirmed.append(dict(finding, lens=lens,
                                      replay=result["why"]))
            else:
                telemetry["unreproduced"] += 1
                lens_bucket(lens)["unreproduced"] += 1
                downgraded.append(dict(finding, action="ask-user",
                                       unreproduced=True, lens=lens,
                                       replay=result["why"]))
    return {"confirmed": confirmed, "downgraded": downgraded,
            "unreplayable_block": bool(no_repro), "telemetry": telemetry}


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


def _rev_parse_head(repo: str, ref: str) -> str:
    return _git(repo, "rev-parse", ref).stdout.strip()


# -- H3: required-steps manifest ---------------------------------------------------

#: manifest step name → the run_gate input that must be supplied to enforce it
REQUIRED_STEP_INPUTS = {
    "visible_tests": "test_cmd",
    "verdicts": "verdict_dir",
    "risk_floor": "floor_config_path",
    "heldout_drop": "vault_path",
}


def validate_required_steps(doc) -> dict:
    """Manifest shape: ``{profile: [step, ...]}``. Unknown profiles or steps
    are loud — a typo'd manifest must not silently require nothing."""
    if not isinstance(doc, dict):
        raise GateError("required-steps manifest must be a JSON object")
    out = {}
    for profile, step_list in doc.items():
        if profile not in PROFILES:
            raise GateError(f"required-steps manifest: unknown profile "
                            f"{profile!r} (not in {PROFILES})")
        if not isinstance(step_list, list):
            raise GateError(f"required-steps manifest: {profile!r} must map "
                            f"to a list of step names")
        for name in step_list:
            if name not in REQUIRED_STEP_INPUTS:
                raise GateError(
                    f"required-steps manifest: unknown step {name!r} for "
                    f"{profile!r} (known: {sorted(REQUIRED_STEP_INPUTS)})")
        out[profile] = list(step_list)
    return out


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
             test_timeout: int = 1800,
             stamp_dir: str | None = None,
             required_steps_path: str | None = None,
             repro_mode: str = "off",
             repro_timeout: int = 300) -> dict:
    """Run the full gate. Fail-fast on the first blocking step; every executed
    step is reported. Returns the report dict (see ``render_report``).

    With ``stamp_dir``, a PASS writes the H2 gate stamp (branch + HEAD sha)
    the merge interlock demands during a live firing — and only a PASS does.

    With ``required_steps_path`` (repo-relative, loaded from the **ratified
    base ref**, never the branch under test), the H3 manifest turns
    "caller's choice" omissions into fail-closed refusals for the task's
    profile — an under-configured gate call cannot yield a green gate."""
    if task_profile not in PROFILES:
        raise GateError(f"unknown profile {task_profile!r}")
    if repro_mode not in ("off", "replay", "strict"):
        raise GateError(f"unknown repro_mode {repro_mode!r} "
                        f"(off | replay | strict)")
    steps: list = []
    report = {"ok": False, "branch": branch, "base": base, "steps": steps,
              "findings": None, "evidence_dir": evidence_dir,
              "test_output_tail": None, "full_log": None}

    def step(name, ok, detail):
        steps.append({"step": name, "ok": ok, "detail": detail})
        return ok

    def finish(ok):
        report["ok"] = ok
        if ok and stamp_dir:
            from . import interlocks as _interlocks  # lazy: no import cycle
            head = _rev_parse_head(repo, branch)
            report["gate_stamp"] = _interlocks.write_gate_stamp(
                stamp_dir, branch, head, base, ok=True)
        if evidence_dir:
            os.makedirs(evidence_dir, exist_ok=True)
            payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
            if vault_path:
                # H7: in-repo evidence never names held-out content
                payload = _vault.scrub_for_repo(payload, vault_path)
            with open(os.path.join(evidence_dir, "gate-report.json"), "w") as fh:
                fh.write(payload)
        return report

    # 0. required-steps manifest (H3): a required step whose input is absent
    # is a fail-closed refusal, never a caller's-choice pass
    if required_steps_path:
        cfg = _hooks.load_ratified_config(repo, required_steps_path, ref=base)
        if cfg is None:
            step("required_steps", False,
                 f"cannot load {required_steps_path} from {base} (fail-closed)")
            return finish(False)
        try:
            manifest = validate_required_steps(cfg)
        except GateError as exc:
            step("required_steps", False, f"{exc} (fail-closed)")
            return finish(False)
        supplied = {"test_cmd": test_cmd, "verdict_dir": verdict_dir,
                    "floor_config_path": floor_config_path,
                    "vault_path": vault_path}
        required = manifest.get(task_profile, [])
        missing = [name for name in required
                   if supplied[REQUIRED_STEP_INPUTS[name]] is None]
        if missing:
            step("required_steps", False,
                 f"profile {task_profile!r} requires {missing} but the "
                 f"corresponding input(s) were not supplied (fail-closed)")
            return finish(False)
        step("required_steps", True,
             f"all {len(required)} required step input(s) supplied for "
             f"{task_profile!r}")
    else:
        step("required_steps", True, "no manifest supplied (caller's choice)")

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

    # 5–7 share one clean checkout (visible tests + H4 repro replay)
    with tempfile.TemporaryDirectory(prefix="gate-checkout-") as scratch:
        dest = os.path.join(scratch, "co")
        checkout = {"ready": False, "error": None}

        def ensure_checkout():
            if not checkout["ready"] and not checkout["error"]:
                try:
                    clean_checkout(repo, branch, dest)
                    checkout["ready"] = True
                    step("clean_checkout", True, f"reproduced {branch}")
                except GateError as exc:
                    checkout["error"] = str(exc)
                    step("clean_checkout", False, str(exc))
            return checkout

        # 5. visible tests
        if test_cmd:
            if ensure_checkout()["error"]:
                return finish(False)
            try:
                proc = subprocess.run(
                    shlex.split(test_cmd), cwd=dest, capture_output=True,
                    text=True, timeout=test_timeout)
            except (OSError, subprocess.TimeoutExpired) as exc:
                step("visible_tests", False, f"test command failed to run: {exc}")
                return finish(False)
            output = (proc.stdout or "") + (proc.stderr or "")
            if vault_path:
                # H7: the in-repo spill never names held-out content
                output = _vault.scrub_for_repo(output, vault_path)
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
            step("visible_tests", True,
                 "no test command supplied (caller's choice)")

        # 6. held-out drop
        if vault_path:
            try:
                drop = _vault.check_heldout_drop(
                    _vault.load_manifest(vault_path),
                    _vault.build_manifest(vault_path))
            except _vault.VaultError as exc:
                step("heldout_drop", False, f"{exc} (fail-closed)")
                return finish(False)
            if not step("heldout_drop", drop["ok"], drop["why"]):
                return finish(False)
        else:
            step("heldout_drop", True, "no vault supplied (caller's choice)")

        # 7. verdicts, all-must-pass — with H4 repro replay before a FAIL
        # blocks: a hallucinated FAIL must not drive the escalation ladder
        if verdict_dir is not None:
            try:
                verdicts = read_verdicts(verdict_dir)
            except GateError as exc:
                step("verdicts", False, f"{exc} (fail-closed)")
                return finish(False)
            panel = check_verdicts(verdicts, min_lenses=min_lenses)
            if panel["ok"]:
                step("verdicts", True, panel["why"])
            elif repro_mode == "off" or not panel.get("failing"):
                # replay disabled, or the panel itself is inadequate
                step("verdicts", False, panel["why"])
                return finish(False)
            else:
                if ensure_checkout()["error"]:
                    return finish(False)
                try:
                    adjudication = replay_failing_verdicts(
                        verdicts, dest, strict=(repro_mode == "strict"),
                        timeout=repro_timeout)
                except GateError as exc:
                    step("verdicts", False,
                         f"replay adjudication failed: {exc} (fail-closed)")
                    return finish(False)
                report["false_fail"] = adjudication["telemetry"]
                report["downgraded_findings"] = adjudication["downgraded"]
                if adjudication["confirmed"]:
                    step("verdicts", False,
                         f"{panel['why']} — {len(adjudication['confirmed'])} "
                         f"error finding(s) CONFIRMED by replay")
                    return finish(False)
                if adjudication["unreplayable_block"]:
                    step("verdicts", False,
                         f"{panel['why']} — error finding(s) without an "
                         f"executable repro block (repro_mode='replay' is "
                         f"conservative; 'strict' downgrades them)")
                    return finish(False)
                report["needs_adjudication"] = True
                step("verdicts", False,
                     f"FAIL verdict(s) present but 0 of "
                     f"{adjudication['telemetry']['error_findings']} error "
                     f"finding(s) reproduced on replay — route to human "
                     f"adjudication (false-FAIL candidates), NOT the "
                     f"escalation ladder")
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


def false_fail_records(report: dict, task_id: str | None = None) -> list:
    """Run-log records (event=false_fail) from a gate report's replay
    telemetry — one per lens, so the controller segments verifier precision
    by lens (§8). Empty when no replay ran."""
    telemetry = report.get("false_fail")
    if not telemetry:
        return []
    out = []
    for lens, counts in (telemetry.get("by_lens") or {}).items():
        rec = {"event": "false_fail", "lens": lens, **counts}
        if task_id:
            rec["task_id"] = task_id
        out.append(rec)
    return out


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
