#!/usr/bin/env python3
"""Escapes log + calibration machinery — the self-measuring verifier loop (D4).

Design §7: the panel's catch-rate is measured against ground truth, and rigor
moves only on proof:

- **Escapes log** — defects a panel missed, discovered later (an operator, a
  user, a downstream failure). Labeled ground truth; append-only; the
  controller's catch-rate denominator. An escape is the design's reflection
  trigger and freezes any pending rigor downgrade.
- **Calibration canaries** — a known defect planted where the panel should
  catch it. No "0 findings" result is trusted to justify a downgrade until the
  canaries prove the panel still catches; **a miss freezes the downgrade**.
- **Contract-test kill-rate** — how many planted defects the *visible* suite
  kills. A weak visible oracle **raises** rigor, never lowers it (the visible
  suite being green means little when its kill-rate is low — the ~31% problem).

All records are JSONL with loud validation; decisions are pure functions the
controller (F2) consumes.
"""

from __future__ import annotations

import datetime as _dt
import json
import os

SEVERITIES = ("critical", "major", "minor")


class CalibrationError(ValueError):
    pass


def _utcnow_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class _JsonlLog:
    def __init__(self, path: str):
        self.path = path

    def _append(self, rec: dict) -> dict:
        parent = os.path.dirname(self.path) or "."
        os.makedirs(parent, exist_ok=True)
        with open(self.path, "a") as fh:
            fh.write(json.dumps(rec, sort_keys=True) + "\n")
        return rec

    def read(self) -> list:
        try:
            with open(self.path) as fh:
                lines = fh.readlines()
        except FileNotFoundError:
            return []
        out = []
        for lineno, line in enumerate(lines, start=1):
            if not line.strip():
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise CalibrationError(
                    f"{self.path}:{lineno}: corrupt record: {exc}") from None
        return out


class EscapesLog(_JsonlLog):
    """Ground truth of validation escapes. Append-only; never pruned."""

    def record(self, task_id: str, description: str, severity: str,
               discovered_by: str, panel_lenses: list | None = None) -> dict:
        if not task_id or not description:
            raise CalibrationError("escape needs task_id and description")
        if severity not in SEVERITIES:
            raise CalibrationError(
                f"severity {severity!r} not in {SEVERITIES}")
        return self._append({
            "ts": _utcnow_iso(), "kind": "escape", "task_id": task_id,
            "description": description, "severity": severity,
            "discovered_by": discovered_by,
            "panel_lenses": list(panel_lenses or []),
        })


def backfill_escape(log: EscapesLog, merged_task: str, description: str,
                    severity: str, discovered_in: str,
                    panel_lenses: list | None = None) -> dict:
    """H6(a) — the deterministic backfill rule: a defect surfaced by a
    *later* task/phase on a merged surface is an escape of the task that
    merged it, attributed to the panel that passed it. Discovery is a
    mechanism, not a hope."""
    if not isinstance(discovered_in, str) or not discovered_in:
        raise CalibrationError("backfill needs the discovering task/phase")
    if discovered_in == merged_task:
        raise CalibrationError(
            f"defect discovered in {discovered_in!r} itself is not an escape "
            f"— escapes are misses on already-merged work")
    return log.record(task_id=merged_task, description=description,
                      severity=severity,
                      discovered_by=f"backfill:{discovered_in}",
                      panel_lenses=panel_lenses)


class HuntLog(_JsonlLog):
    """H6(b) — sampled escape-hunts: a fresh high-tier panel re-audits a
    deterministic sample of merged surface. This log is what makes
    'discovery active' checkable instead of asserted."""

    def record(self, hunt_id: str, sampled_tasks: list, lenses: list,
               escapes_found: int) -> dict:
        if not hunt_id:
            raise CalibrationError("hunt needs an id")
        if not isinstance(sampled_tasks, list) or not sampled_tasks:
            raise CalibrationError("hunt needs a non-empty task sample")
        if not isinstance(escapes_found, int) or escapes_found < 0:
            raise CalibrationError("escapes_found must be a non-negative int")
        return self._append({
            "ts": _utcnow_iso(), "kind": "hunt", "hunt_id": hunt_id,
            "sampled_tasks": list(sampled_tasks), "lenses": list(lenses or []),
            "escapes_found": escapes_found,
        })


def hunt_sample(merged_task_ids: list, k: int = 3, seed: str = "") -> list:
    """Deterministic hunt sample: rank by sha256(seed:id), take k. No RNG —
    replayable, spread across the id space, seedable per hunt round."""
    import hashlib as _hashlib
    ranked = sorted(set(merged_task_ids),
                    key=lambda t: _hashlib.sha256(
                        f"{seed}:{t}".encode()).hexdigest())
    return ranked[:max(0, k)]


def discovery_active(merged_since_last_hunt: int | None,
                     every_n_merges: int = 10) -> dict:
    """H6(c) — is the escape-discovery channel actually running? 'escapes ≈ 0'
    gates nothing while nothing could have discovered one. Active = an
    escape-hunt has happened and its cadence hasn't lapsed. ``None`` = no hunt
    has ever run (inactive)."""
    if every_n_merges < 1:
        raise CalibrationError(f"every_n_merges must be >= 1, "
                               f"got {every_n_merges}")
    if merged_since_last_hunt is None:
        return {"active": False,
                "why": "no escape-hunt has ever run — the escapes log is "
                       "silence, not evidence"}
    if not isinstance(merged_since_last_hunt, int) or \
            merged_since_last_hunt < 0:
        raise CalibrationError("merged_since_last_hunt must be None or a "
                               "non-negative int")
    if merged_since_last_hunt > every_n_merges:
        return {"active": False,
                "why": f"{merged_since_last_hunt} merge(s) since the last "
                       f"hunt exceeds the {every_n_merges}-merge cadence — "
                       f"overdue, channel lapsed"}
    return {"active": True,
            "why": f"last hunt {merged_since_last_hunt} merge(s) ago "
                   f"(cadence {every_n_merges})"}


class CanaryLog(_JsonlLog):
    """Planted-defect trials: a 'planted' record then a 'result' record."""

    def plant(self, canary_id: str, description: str, planted_in: str,
              expected_lens: str) -> dict:
        if not canary_id:
            raise CalibrationError("canary needs an id")
        return self._append({
            "ts": _utcnow_iso(), "kind": "planted", "canary_id": canary_id,
            "description": description, "planted_in": planted_in,
            "expected_lens": expected_lens,
        })

    def result(self, canary_id: str, caught: bool,
               caught_by_lens: str | None = None,
               lens_results: dict | None = None) -> dict:
        """Record a trial outcome. ``lens_results`` (H5: {lens: caught_bool},
        one entry per panel lens) enables panel-correlation telemetry; when
        present it must agree with ``caught`` — an inconsistent record would
        poison both measurements."""
        planted = {r["canary_id"] for r in self.read() if r["kind"] == "planted"}
        if canary_id not in planted:
            raise CalibrationError(
                f"canary {canary_id!r} was never planted — results only exist "
                f"for real trials")
        rec = {
            "ts": _utcnow_iso(), "kind": "result", "canary_id": canary_id,
            "caught": bool(caught), "caught_by_lens": caught_by_lens,
        }
        if lens_results is not None:
            if not isinstance(lens_results, dict) or not lens_results or \
                    not all(isinstance(k, str) and k for k in lens_results):
                raise CalibrationError(
                    "lens_results must be a non-empty {lens: bool} dict")
            normalized = {k: bool(v) for k, v in lens_results.items()}
            if any(normalized.values()) != bool(caught):
                raise CalibrationError(
                    f"canary {canary_id!r}: caught={bool(caught)} contradicts "
                    f"lens_results {normalized} — refusing an inconsistent "
                    f"trial record")
            rec["lens_results"] = normalized
        return self._append(rec)

    def trials(self) -> list:
        """Completed trials, oldest→newest: [{'canary_id', 'caught', ...}]."""
        return [r for r in self.read() if r["kind"] == "result"]


def downgrade_allowed(canary_trials: list, escapes: list,
                      min_trials: int = 3,
                      recent_window: int = 5,
                      discovery: dict | None = None) -> dict:
    """The §7 rule for any rigor downgrade (panel shrink, tier drop, effort
    drop): allowed only when (a) enough canary trials exist, (b) every trial in
    the recent window was caught, (c) there is no unresolved escape newer
    than the newest trial, and (d — H6) the **escape-discovery channel is
    active** (``discovery_active``): zero escapes only means something when
    something could have discovered one. ``discovery=None`` (unchecked) is
    treated as inactive — unknown fails toward rigor, like the kill-rate."""
    if min_trials < 1 or recent_window < min_trials:
        raise CalibrationError(
            f"need 1 <= min_trials({min_trials}) <= recent_window"
            f"({recent_window})")
    if len(canary_trials) < min_trials:
        return {"allowed": False,
                "why": f"only {len(canary_trials)} canary trial(s); "
                       f"{min_trials} required before trusting a downgrade"}
    recent = canary_trials[-recent_window:]
    missed = [t for t in recent if not t["caught"]]
    if missed:
        return {"allowed": False,
                "why": f"{len(missed)} canary miss(es) in the last "
                       f"{len(recent)} trials — downgrade frozen "
                       f"({', '.join(t['canary_id'] for t in missed)})"}
    if escapes:
        newest_trial = max(t["ts"] for t in recent)
        late_escapes = [e for e in escapes if e["ts"] >= newest_trial]
        if late_escapes:
            return {"allowed": False,
                    "why": f"{len(late_escapes)} escape(s) newer than the last "
                           f"canary trial — recalibrate before any downgrade"}
    if discovery is None or not discovery.get("active"):
        why = (discovery or {}).get("why", "discovery unchecked")
        return {"allowed": False,
                "why": f"escape-discovery channel inactive ({why}) — "
                       f"'escapes ≈ 0' gates nothing while nothing could "
                       f"have discovered one (H6)"}
    return {"allowed": True,
            "why": f"last {len(recent)} canary trials all caught; no escape "
                   f"since; discovery active ({discovery['why']})"}


def panel_correlation(trials: list) -> dict:
    """H5 — aggregate canary trials panel-wide (§7 panel amendment): errors
    correlate across models, so N same-family lenses are not N independent
    draws. A planted defect missed by **every** lens is a *correlated blind
    spot* — direct evidence the panel's redundancy bought nothing on that
    defect class. Trials without per-lens results cannot measure correlation
    and are reported unscored, never guessed."""
    scored = [t for t in trials
              if isinstance(t.get("lens_results"), dict) and t["lens_results"]]
    blind_ids, sole = [], 0
    per_lens: dict = {}
    for trial in scored:
        results = {k: bool(v) for k, v in trial["lens_results"].items()}
        for lens, caught in results.items():
            cell = per_lens.setdefault(lens, {"trials": 0, "caught": 0})
            cell["trials"] += 1
            cell["caught"] += 1 if caught else 0
        catchers = sum(results.values())
        if catchers == 0:
            blind_ids.append(trial["canary_id"])
        elif catchers == 1:
            sole += 1
    if not scored:
        why = ("panel correlation unmeasured — no per-lens canary results yet "
               "(pass lens_results to CanaryLog.result)")
    elif blind_ids:
        why = (f"{len(blind_ids)} of {len(scored)} scored trial(s) missed by "
               f"EVERY lens ({', '.join(blind_ids[:5])}) — correlated blind "
               f"spot(s); redundancy bought nothing there")
    else:
        why = (f"no all-lenses-missed trial in {len(scored)} scored trial(s); "
               f"{sole} caught by a single lens (lens diversity carrying)")
    return {"trials_scored": len(scored),
            "trials_unscored": len(trials) - len(scored),
            "correlated_blind_spots": len(blind_ids),
            "blind_spot_ids": blind_ids,
            "sole_catcher_trials": sole,
            "per_lens": per_lens,
            "why": why}


def kill_rate(trials: list) -> float | None:
    """Fraction of planted defects the visible suite killed. None = no data
    (never fabricated)."""
    if not trials:
        return None
    return sum(1 for t in trials if t.get("killed")) / len(trials)


def rigor_adjustment(rate: float | None, weak_below: float = 0.7) -> dict:
    """A weak visible oracle raises rigor, never lowers it (§7). Unknown rate
    is treated as weak — fail toward rigor."""
    if not 0 < weak_below <= 1:
        raise CalibrationError(f"weak_below must be in (0,1], got {weak_below}")
    if rate is None:
        return {"adjustment": "raise",
                "why": "kill-rate unmeasured — treat the visible oracle as weak"}
    if not 0 <= rate <= 1:
        raise CalibrationError(f"kill rate {rate} outside [0,1]")
    if rate < weak_below:
        return {"adjustment": "raise",
                "why": f"visible-suite kill-rate {rate:.0%} below "
                       f"{weak_below:.0%} — green means little; rigor goes up"}
    return {"adjustment": "hold",
            "why": f"kill-rate {rate:.0%} at/above threshold; rigor holds "
                   f"(downgrades still need canary proof)"}
