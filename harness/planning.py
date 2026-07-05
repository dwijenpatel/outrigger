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
import glob as _glob
import hashlib
import json
import os
import sys

from . import closure as _closure
from . import hooks as _hooks
from . import ledger as _ledger
from . import schemas as _schemas
from . import vault as _vault

RATIFICATION_NAME = "ratification.json"
MIN_SPEC_CHARS = 200  # a scoped spec below this cannot pin interfaces + criteria

#: I19/I21 convention: the card kind an operator's ambiguity adjudication
#: carries (what pilot-3-v2's session wrote, adopted as the contract).
H9_CARD_KIND = "H9-spec-ambiguity"


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


def _resolved_ambiguity_card(blockers_dir: str, task_id: str) -> str | None:
    """Path of a RESOLVED operator card adjudicating ``task_id``'s spec
    ambiguities, or None. Matches by card ``kind`` (H9_CARD_KIND) or, for
    cards written before the kind convention, an 'ambiguity' filename."""
    if not os.path.isdir(blockers_dir):
        return None
    for name in sorted(os.listdir(blockers_dir)):
        if not name.endswith(".json"):
            continue
        path = os.path.join(blockers_dir, name)
        try:
            card = json.loads(_read(path))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(card, dict) or card.get("task_id") != task_id:
            continue
        if card.get("kind") != H9_CARD_KIND and "ambiguity" not in name:
            continue
        res = card.get("resolved")
        if isinstance(res, dict) and res.get("decision"):
            return path
    return None


def gate_preflight(plan_dir: str, vault_config_path: str | None = None,
                   repo_root: str = ".",
                   blockers_dir: str | None = None) -> dict:
    """I19 (P3-2, P3v2-1): simulate every statically-evaluable pre-spawn gate
    at ratification/readiness time — while the operator is still in the room.
    Both pilot-3 halts were foreseeable from artifacts that already existed
    when the plan was (re-)ratified; each instead surfaced mid-firing, once
    as a full halt and once as an 8h25m interactive stall.

    Two halves, each active only where the plan/vault records enough to check
    (old plans stay valid — absence skips, it never fails):

    - **floors × touches**: a task recording ``touches`` (representative
      concrete paths its spec pins) is checked with the same
      ``check_risk_floor`` the merge gate runs; a collision is a plan defect,
      fatal here instead of a mid-firing bounce.
    - **H9 × existing handoffs**: a blocking-profile task with a carried-over
      test-author handoff in the vault evidence store gets
      ``ambiguity_blockers`` run now. Undischarged ambiguities WILL park it at
      spawn — fatal unless a resolved operator card (state/blockers/) already
      adjudicates them; adjudicated ones surface as non-fatal notes.

    Returns {"ok", "findings": [{"task_id", "kind", "fatal", "detail"}]}.
    """
    ledger = load_tasks(plan_dir)
    floors_path = os.path.join(plan_dir, "floors.json")
    try:
        floor_map = _hooks.validate_floor_map(
            json.loads(_read(floors_path)).get("floors", []))
    except FileNotFoundError:
        raise PlanningError(f"no {floors_path} — preflight needs the plan's "
                            f"floors") from None
    except json.JSONDecodeError as exc:
        raise PlanningError(f"{floors_path} corrupt: {exc}") from None

    evidence_dir = None
    if vault_config_path:
        vdoc = _vault.load_vault_config(repo_root, vault_config_path)
        if vdoc.get("vault_path"):
            evidence_dir = _vault.heldout_evidence_dir(vdoc["vault_path"])
    if blockers_dir is None:
        blockers_dir = os.path.join(repo_root, "state", "blockers")

    findings = []
    for task_id in sorted(ledger.tasks):
        task = ledger.tasks[task_id]

        touches = task.get("touches")
        if touches is not None:
            if (not isinstance(touches, list) or not touches
                    or not all(isinstance(t, str) and t for t in touches)):
                findings.append({
                    "task_id": task_id, "kind": "touches-invalid",
                    "fatal": True,
                    "detail": "touches must be a non-empty list of concrete "
                              "paths the spec pins"})
            else:
                res = _hooks.check_risk_floor(task["profile"], touches,
                                              floor_map)
                if not res["ok"]:
                    floored = [m["path"] for m in res["matched"]]
                    findings.append({
                        "task_id": task_id, "kind": "floor-collision",
                        "fatal": True,
                        "detail": f"{res['why']} (pinned paths: "
                                  f"{floored[:4]}) — the gate WILL bounce "
                                  f"this merge; re-profile or re-scope "
                                  f"before ratifying"})

        if evidence_dir and task["profile"] in \
                _schemas.BLOCKING_AMBIGUITY_PROFILES:
            pattern = os.path.join(evidence_dir, f"{task_id}.*handoff*.json")
            for hpath in sorted(_glob.glob(pattern)):
                base = os.path.basename(hpath)
                try:
                    blockers = _schemas.ambiguity_blockers(
                        json.loads(_read(hpath)), task_id, task["profile"])
                except (OSError, json.JSONDecodeError,
                        _schemas.SchemaError) as exc:
                    findings.append({
                        "task_id": task_id, "kind": "handoff-invalid",
                        "fatal": True, "detail": f"{base}: {exc}"})
                    continue
                if not blockers:
                    continue
                card = _resolved_ambiguity_card(blockers_dir, task_id)
                if card:
                    findings.append({
                        "task_id": task_id, "kind": "h9-adjudicated",
                        "fatal": False,
                        "detail": f"{len(blockers)} ambiguity blocker(s) "
                                  f"from {base} already adjudicated by "
                                  f"resolved card "
                                  f"{os.path.relpath(card, repo_root)}"})
                else:
                    findings.append({
                        "task_id": task_id, "kind": "h9-will-park",
                        "fatal": True,
                        "detail": f"{len(blockers)} undischarged spec "
                                  f"ambiguit{'y' if len(blockers) == 1 else 'ies'} "
                                  f"in {base} WILL park {task_id} pre-spawn — "
                                  f"adjudicate now (resolved card under "
                                  f"{os.path.join('state', 'blockers')}) or "
                                  f"re-author with corpus_covers"})

    return {"ok": not any(f["fatal"] for f in findings), "findings": findings}


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

    # 7. gate preflight (I19) — what would bounce or park pre-spawn,
    # surfaced while the operator is still in the room
    try:
        pf = gate_preflight(plan_dir, vault_config_path=vault_config_path,
                            repo_root=repo_root)
    except (PlanningError, _hooks.HookError, _vault.VaultError) as exc:
        check("preflight", False, f"{exc} (fail-closed)")
        return finish()
    fatal = [f for f in pf["findings"] if f["fatal"]]
    if fatal:
        check("preflight", False, "; ".join(
            f"{f['task_id']}: {f['detail']}" for f in fatal[:3]))
        return finish()
    notes = [f for f in pf["findings"] if not f["fatal"]]
    check("preflight", True,
          "; ".join(f"{f['task_id']}: {f['detail']}" for f in notes[:3])
          if notes else "no pre-spawn bounce/park foreseen")
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
    pf_p = sub.add_parser("preflight",
                          help="I19: simulate statically-evaluable pre-spawn "
                               "gates (floors×touches, H9×handoffs) — run "
                               "before ratifying, and after any profile or "
                               "floor change")
    pf_p.add_argument("--plan-dir", default="plan")
    pf_p.add_argument("--vault-config",
                      help="also check carried-over handoffs in the vault "
                           "evidence store")
    pf_p.add_argument("--repo", default=".")
    pf_p.add_argument("--blockers-dir",
                      help="operator adjudication cards "
                           "(default <repo>/state/blockers)")
    args = p.parse_args(argv)

    if args.cmd == "preflight":
        try:
            pf = gate_preflight(args.plan_dir,
                                vault_config_path=args.vault_config,
                                repo_root=args.repo,
                                blockers_dir=args.blockers_dir)
        except (PlanningError, _ledger.LedgerError, _hooks.HookError,
                _vault.VaultError) as exc:
            print(f"preflight failed: {exc}", file=sys.stderr)
            return 2
        print(json.dumps(pf, indent=2))
        if not pf["ok"]:
            print("preflight FATAL: the firing would bounce/park on the "
                  "findings above — adjudicate or amend before ratifying",
                  file=sys.stderr)
        return 0 if pf["ok"] else 2

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
