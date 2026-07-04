#!/usr/bin/env python3
"""Closure gate — completion vs a frozen plan snapshot (E5, design §4/§7).

The loop cannot quietly redefine "done": completion is judged against a **plan
snapshot frozen at build start**, under two rules:

- **Fresh-evidence rule** — only evidence newer than the last remediation can
  decide; a green report predating the latest fix proves nothing about it.
- **Bounded remediation** — after ``max_rounds`` remediation rounds the gate
  stops looping and escalates to the operator (an unbounded fix loop is the §9
  stuck-loop event wearing a bow tie).

Descoping a snapshot task is legitimate only through the ratification queue;
``closure_check`` takes the ratified descope list and refuses everything else.
The Stop-hook script (``hooks/closure_gate.py``) blocks a firing from
declaring itself finished while the gate says otherwise — fail closed.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os

from . import ledger as _ledger


class ClosureError(ValueError):
    pass


def _utcnow_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def freeze_snapshot(ledger: _ledger.Ledger, dest_path: str) -> dict:
    """Freeze the task list at build start. The snapshot records ids + a hash;
    closure is judged against THIS, not the (possibly re-scoped) live ledger."""
    task_ids = sorted(ledger.tasks)
    digest = hashlib.sha256(json.dumps(task_ids).encode()).hexdigest()[:16]
    doc = {"frozen_at": _utcnow_iso(), "task_ids": task_ids,
           "task_hash": digest}
    os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)
    tmp = dest_path + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(doc, fh, indent=2, sort_keys=True)
        fh.write("\n")
    os.replace(tmp, dest_path)
    return doc


def load_snapshot(path: str) -> dict:
    try:
        with open(path) as fh:
            doc = json.load(fh)
    except FileNotFoundError:
        raise ClosureError(f"no plan snapshot at {path} — closure cannot be "
                           f"judged without the frozen baseline") from None
    except json.JSONDecodeError as exc:
        raise ClosureError(f"snapshot {path} corrupt: {exc}") from None
    if not isinstance(doc.get("task_ids"), list) or not doc.get("task_hash"):
        raise ClosureError(f"snapshot {path}: malformed")
    expect = hashlib.sha256(
        json.dumps(sorted(doc["task_ids"])).encode()).hexdigest()[:16]
    if expect != doc["task_hash"]:
        raise ClosureError(f"snapshot {path}: task list does not match its "
                           f"hash — snapshot tampered or corrupt")
    return doc


def load_hook_config(path: str, base_dir: str) -> dict:
    """Stop-hook mode config (H1), written by the loop at firing start
    (``loop.closure_hook_config``). Required keys: ``snapshot``, ``ledger``,
    ``events`` — paths resolved against ``base_dir``. Unreadable or malformed
    config raises: during a live firing the hook fails closed on it."""
    try:
        with open(path) as fh:
            doc = json.load(fh)
    except FileNotFoundError:
        raise ClosureError(
            f"no closure hook config at {path} — a live firing must declare "
            f"its closure inputs (loop.closure_hook_config at firing start)"
        ) from None
    except json.JSONDecodeError as exc:
        raise ClosureError(f"closure hook config {path} corrupt: {exc}") from None
    if not isinstance(doc, dict):
        raise ClosureError(f"closure hook config {path}: not an object")
    out = dict(doc)
    for key in ("snapshot", "ledger", "events"):
        val = doc.get(key)
        if not isinstance(val, str) or not val:
            raise ClosureError(f"closure hook config {path}: missing {key!r}")
        out[key] = val if os.path.isabs(val) else os.path.join(base_dir, val)
    return out


def closure_check(snapshot: dict, ledger: _ledger.Ledger, log: _ledger.EventLog,
                  artifacts: dict | None = None,
                  evidence_ts: str | None = None,
                  last_remediation_ts: str | None = None,
                  remediation_rounds: int = 0,
                  max_rounds: int = 3,
                  ratified_descopes: list | None = None) -> dict:
    """Judge completion. Returns {"complete", "status", "why", ...} where
    status ∈ closed | incomplete | stale_evidence | escalate."""
    if max_rounds < 1:
        raise ClosureError(f"max_rounds must be >= 1, got {max_rounds}")
    descoped = set(ratified_descopes or [])
    unknown_descopes = descoped - set(snapshot["task_ids"])
    if unknown_descopes:
        raise ClosureError(f"descope list names tasks not in the snapshot: "
                           f"{sorted(unknown_descopes)}")

    if remediation_rounds >= max_rounds:
        return {"complete": False, "status": "escalate",
                "why": f"{remediation_rounds} remediation rounds reached the "
                       f"bound ({max_rounds}) — operator decision required, "
                       f"the loop stops spending here"}

    # fresh-evidence rule
    if last_remediation_ts is not None:
        if evidence_ts is None or evidence_ts <= last_remediation_ts:
            return {"complete": False, "status": "stale_evidence",
                    "why": f"evidence ({evidence_ts or 'none'}) does not "
                           f"postdate the last remediation "
                           f"({last_remediation_ts}) — re-verify before "
                           f"deciding (§7 fresh-evidence rule)"}

    state = _ledger.reconcile(ledger, log, artifacts)["tasks"]
    missing_from_ledger = [t for t in snapshot["task_ids"]
                           if t not in ledger.tasks and t not in descoped]
    not_done = [t for t in snapshot["task_ids"]
                if t in ledger.tasks and t not in descoped
                and state[t]["status"] != "done"]
    if missing_from_ledger or not_done:
        detail = []
        if missing_from_ledger:
            detail.append(f"vanished from the live ledger without a ratified "
                          f"descope: {missing_from_ledger[:5]}")
        if not_done:
            detail.append(f"not done: {not_done[:10]}")
        return {"complete": False, "status": "incomplete",
                "why": "; ".join(detail),
                "remaining": len(not_done) + len(missing_from_ledger)}

    return {"complete": True, "status": "closed",
            "why": f"all {len(snapshot['task_ids']) - len(descoped)} snapshot "
                   f"tasks reconciled done"
                   + (f" ({len(descoped)} ratified descope(s))" if descoped
                      else "")}
