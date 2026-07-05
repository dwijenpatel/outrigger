#!/usr/bin/env python3
"""Plan readiness + ratification — the deterministic half of plan-first (I2).

Pilot-1 finding P1-8: every guard *downstream* of the spec was mechanized,
but nothing mechanized producing — or requiring — a good plan. The
``plan-build`` skill is the elicitation half; this module is the teeth:

- **Plan artifacts** live in a plan dir: ``tasks.json`` (ledger shape),
  ``specs/<task-id>.md`` (scoped spec per task: pinned interfaces,
  acceptance criteria), ``floors.json`` (path-glob → minimum profile).
- **Ratification is content-bound.** ``ratify`` records a sha256 over the
  plan artifacts; *any* later edit invalidates readiness (the E3
  stale-decision guard, applied to the plan itself).
- **``plan_ready``** is the gate the build-loop consults at step 0: ledger
  valid, every task's spec present and non-trivial, floors valid, frozen
  snapshot matching the ledger, ratification stamp matching the current
  content hash. Not ready → no firing (fail closed).

CLI:

    python3 -m harness.planning ready  --plan-dir plan --snapshot state/plan-snapshot.json
    python3 -m harness.planning ratify --plan-dir plan --approved-by <operator>
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import sys

from . import closure as _closure
from . import hooks as _hooks
from . import ledger as _ledger
from . import vault as _vault

RATIFICATION_NAME = "ratification.json"
MIN_SPEC_CHARS = 200  # a scoped spec below this cannot pin interfaces + criteria


class PlanningError(ValueError):
    pass


def _utcnow_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read(path: str) -> bytes:
    with open(path, "rb") as fh:
        return fh.read()


def load_tasks(plan_dir: str) -> _ledger.Ledger:
    path = os.path.join(plan_dir, "tasks.json")
    try:
        doc = json.loads(_read(path))
    except FileNotFoundError:
        raise PlanningError(f"no {path} — the plan has no ledger") from None
    except json.JSONDecodeError as exc:
        raise PlanningError(f"{path} corrupt: {exc}") from None
    return _ledger.Ledger(_ledger.validate_tasks(doc))


def content_hash(plan_dir: str) -> str:
    """sha256 over every plan artifact except the ratification stamp itself —
    the substance a ratification is *about*."""
    h = hashlib.sha256()
    for root, dirs, files in os.walk(plan_dir):
        dirs.sort()
        for name in sorted(files):
            rel = os.path.relpath(os.path.join(root, name), plan_dir)
            if rel == RATIFICATION_NAME:
                continue
            h.update(rel.encode() + b"\x00")
            h.update(_read(os.path.join(root, name)))
            h.update(b"\x00")
    return h.hexdigest()[:16]


def ratify(plan_dir: str, approved_by: str) -> dict:
    """Record the operator's approval, bound to the current plan content.
    Run this ONLY after the operator has explicitly approved the presented
    plan — the stamp names them, and a changed plan voids it."""
    if not approved_by or not approved_by.strip():
        raise PlanningError("ratification needs --approved-by <operator>")
    load_tasks(plan_dir)  # a malformed plan is not ratifiable
    doc = {"content_hash": content_hash(plan_dir),
           "approved_by": approved_by.strip(),
           "ratified_at": _utcnow_iso()}
    path = os.path.join(plan_dir, RATIFICATION_NAME)
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(doc, fh, indent=2, sort_keys=True)
        fh.write("\n")
    os.replace(tmp, path)
    return doc


def plan_ready(plan_dir: str, snapshot_path: str,
               vault_config_path: str | None = None,
               repo_root: str = ".") -> dict:
    """Every check the firing's inputs depend on. Returns {"ready", "why",
    "checks": [...]}; the first failing check decides ``why`` (fail closed).

    With ``vault_config_path`` (I4b — ported from the pilot session's
    parallel implementation), readiness additionally requires the vault to
    be configured, coherent, and present: a plan is not fireable against an
    unconfigured or drifted vault."""
    checks = []

    def check(name, ok, detail):
        checks.append({"check": name, "ok": ok, "detail": detail})
        return ok

    def finish():
        ok = all(c["ok"] for c in checks)
        failing = next((c for c in checks if not c["ok"]), None)
        return {"ready": ok, "checks": checks,
                "why": ("plan ready: all "
                        f"{len(checks)} checks passed" if ok else
                        f"{failing['check']}: {failing['detail']}")}

    # 1. ledger
    try:
        ledger = load_tasks(plan_dir)
    except (PlanningError, _ledger.LedgerError) as exc:
        check("ledger", False, str(exc))
        return finish()
    check("ledger", True, f"{len(ledger.tasks)} task(s), schema valid")

    # 2. per-task scoped specs
    missing, thin = [], []
    for task_id in sorted(ledger.tasks):
        spec = os.path.join(plan_dir, "specs", f"{task_id}.md")
        if not os.path.isfile(spec):
            missing.append(task_id)
        elif os.path.getsize(spec) < MIN_SPEC_CHARS:
            thin.append(task_id)
    if missing or thin:
        detail = []
        if missing:
            detail.append(f"no spec file for {missing[:5]}")
        if thin:
            detail.append(f"spec under {MIN_SPEC_CHARS} chars for {thin[:5]} "
                          f"— too thin to pin interfaces + acceptance "
                          f"criteria")
        check("specs", False, "; ".join(detail))
        return finish()
    check("specs", True, f"scoped spec present for all {len(ledger.tasks)} "
                         f"task(s)")

    # 3. floors
    floors_path = os.path.join(plan_dir, "floors.json")
    try:
        floors_doc = json.loads(_read(floors_path))
        _hooks.validate_floor_map(floors_doc.get("floors", []))
    except FileNotFoundError:
        check("floors", False, f"no {floors_path} — risk floors are part of "
                               f"the plan, not an afterthought")
        return finish()
    except (json.JSONDecodeError, _hooks.HookError) as exc:
        check("floors", False, str(exc))
        return finish()
    check("floors", True, "floor map valid")

    # 4. frozen snapshot matches the ledger
    try:
        snapshot = _closure.load_snapshot(snapshot_path)
    except _closure.ClosureError as exc:
        check("snapshot", False, str(exc))
        return finish()
    if sorted(snapshot["task_ids"]) != sorted(ledger.tasks):
        check("snapshot", False,
              "frozen snapshot's task list does not match tasks.json — "
              "re-freeze after the plan settles (or the plan moved after "
              "freezing)")
        return finish()
    check("snapshot", True, "snapshot frozen and matches the ledger")

    # 5. ratification, content-bound
    rat_path = os.path.join(plan_dir, RATIFICATION_NAME)
    try:
        rat = json.loads(_read(rat_path))
    except FileNotFoundError:
        check("ratification", False,
              "no ratification stamp — the operator has not approved this "
              "plan (run the plan-build skill to completion)")
        return finish()
    except json.JSONDecodeError as exc:
        check("ratification", False, f"{rat_path} corrupt: {exc}")
        return finish()
    current = content_hash(plan_dir)
    if rat.get("content_hash") != current:
        check("ratification", False,
              f"plan changed after ratification (approved "
              f"{rat.get('content_hash')}, now {current}) — re-present and "
              f"re-ratify (stale-decision guard)")
        return finish()
    check("ratification", True,
          f"approved by {rat.get('approved_by', '?')} at "
          f"{rat.get('ratified_at', '?')}")

    # 6. vault configured + coherent + present (I4b)
    if vault_config_path:
        try:
            vault_doc = _vault.load_vault_config(repo_root, vault_config_path)
        except _vault.VaultError as exc:
            check("vault", False, f"{exc} (fail-closed)")
            return finish()
        vres = _vault.check_vault_config(vault_doc, repo_root)
        if not vres["configured"] or not vres["ok"]:
            check("vault", False, vres["why"])
            return finish()
        check("vault", True,
              f"vault at {vault_doc['vault_path']} configured + coherent")
    return finish()


def _cli(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    ready_p = sub.add_parser("ready", help="is the plan fireable?")
    ready_p.add_argument("--plan-dir", default="plan")
    ready_p.add_argument("--snapshot", default="state/plan-snapshot.json")
    ready_p.add_argument("--vault-config",
                         help="also require a configured, coherent vault "
                              "(I4b); the build-loop passes "
                              "harness/config/vault-isolation.json")
    ready_p.add_argument("--repo", default=".")
    rat_p = sub.add_parser("ratify", help="record operator approval "
                                          "(only after explicit approval)")
    rat_p.add_argument("--plan-dir", default="plan")
    rat_p.add_argument("--approved-by", required=True)
    args = p.parse_args(argv)

    if args.cmd == "ratify":
        try:
            doc = ratify(args.plan_dir, args.approved_by)
        except (PlanningError, _ledger.LedgerError) as exc:
            print(f"ratification refused: {exc}", file=sys.stderr)
            return 2
        print(json.dumps(doc, indent=2))
        return 0

    result = plan_ready(args.plan_dir, args.snapshot,
                        vault_config_path=args.vault_config,
                        repo_root=args.repo)
    print(json.dumps(result, indent=2))
    if not result["ready"]:
        print(f"plan NOT ready: {result['why']}", file=sys.stderr)
    return 0 if result["ready"] else 2


if __name__ == "__main__":
    sys.exit(_cli())
