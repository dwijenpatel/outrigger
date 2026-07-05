#!/usr/bin/env python3
"""Preflight DAG check + scheduler tick — design §6.1/§6.2 (increment B2).

Each tick: candidates = every not-started task whose hard deps are complete —
computed over B4's **reconciled** state (gate/run artifacts beat event claims),
any phase. Idle slots fill prioritized by **critical path, then risk**, gated by
the ``start-early-safe`` predicate (soft ``may_be_invalidated_by`` edges) so
pulled-forward work is never likely rework, and admitted per-task through the
window-aware admission rule (A4) including the per-pipeline cold-prefix warmup
cost for concurrent slots (§6.2).

Window-phase awareness (§6.2): early in a fresh window heavy work goes first;
in the tail the tick runs cheap serial work only. Phase boundaries are tunable
defaults, not quota magnitudes.

The preflight check validates the cross-phase dependency graph is a DAG and
reports cycle members loudly — tasks on a cycle are never runnable (B1/B4
semantics), so an unreported cycle would silently stall the loop forever.
"""

from __future__ import annotations

from . import admission as _admission
from . import ledger as _ledger
from .runlog import PROFILES

DEFAULT_FRESH_BELOW = 0.25   # occupancy under this → "fresh" window phase
DEFAULT_TAIL_ABOVE = 0.60    # occupancy over this → "tail": cheap serial work only


class SchedulerError(ValueError):
    pass


def preflight(ledger: _ledger.Ledger) -> dict:
    """Validate the cross-phase hard-dep graph is a DAG. Returns
    ``{"ok": bool, "cycles": [ [task ids...] ]}`` with every cycle reported."""
    WHITE, GREY, BLACK = 0, 1, 2
    color = {tid: WHITE for tid in ledger.tasks}
    cycles = []

    def visit(tid, stack):
        color[tid] = GREY
        stack.append(tid)
        for dep in ledger.tasks[tid]["deps"]:
            if color[dep] == GREY:
                cycles.append(stack[stack.index(dep):] + [dep])
            elif color[dep] == WHITE:
                visit(dep, stack)
        stack.pop()
        color[tid] = BLACK

    for tid in sorted(ledger.tasks):
        if color[tid] == WHITE:
            visit(tid, [])
    return {"ok": not cycles, "cycles": cycles}


def critical_path_lengths(ledger: _ledger.Ledger) -> dict:
    """Longest downstream dependent chain per task — how much work each task
    unlocks. Cyclic regions get length 0 (they can never run; preflight reports
    them)."""
    dependents: dict = {tid: [] for tid in ledger.tasks}
    for tid, entry in ledger.tasks.items():
        for dep in entry["deps"]:
            dependents[dep].append(tid)
    lengths: dict = {}
    IN_PROGRESS = object()

    def length(tid):
        if tid in lengths:
            return 0 if lengths[tid] is IN_PROGRESS else lengths[tid]
        lengths[tid] = IN_PROGRESS
        value = 1 + max((length(d) for d in dependents[tid]), default=0)
        lengths[tid] = value
        return value

    for tid in ledger.tasks:
        length(tid)
    return lengths


def start_early_safe(task_id: str, ledger: _ledger.Ledger, state: dict) -> bool:
    """Conservative predicate (§6.1): a candidate is safe to start only when every
    task that *may invalidate it* is reconciled done — otherwise the pulled-forward
    work is at risk of rework and waits."""
    return all(state[src]["status"] == "done"
               for src in ledger.tasks[task_id]["may_be_invalidated_by"])


def window_phase(occupancy: float | None,
                 fresh_below: float = DEFAULT_FRESH_BELOW,
                 tail_above: float = DEFAULT_TAIL_ABOVE,
                 reset_headroom_clears: bool = False) -> str:
    """fresh | mid | tail | unknown. 'unknown' occupancy is treated by the tick
    like 'tail' (cannot admit heavy work against an unmeasured window).

    I17: ``reset_headroom_clears`` — the governor's ``reset_headroom``
    verdict. A binding window about to reset with projected-at-reset
    occupancy under pause is a SOFT constraint: tail demotes to mid.
    Unknown occupancy is never waived (nothing to project from)."""
    if occupancy is None:
        return "unknown"
    if not 0 <= fresh_below < tail_above:
        raise SchedulerError(
            f"need 0 <= fresh_below({fresh_below}) < tail_above({tail_above})")
    if occupancy < fresh_below:
        return "fresh"
    if occupancy > tail_above:
        return "mid" if reset_headroom_clears else "tail"
    return "mid"


def _priority_key(tid: str, ledger: _ledger.Ledger, cp: dict):
    profile_rank = PROFILES.index(ledger.tasks[tid]["profile"])
    return (-cp[tid], -profile_rank, tid)


def tick(ledger: _ledger.Ledger, log: _ledger.EventLog,
         artifacts: dict | None = None,
         occupancy: float | None = None,
         estimates_doc: dict | None = None,
         window_ceiling_tokens: float | None = None,
         slots: int = 1, in_flight: int = 0,
         pipeline_warmup_tokens: float = 0.0,
         degrade: float = _admission.DEFAULT_DEGRADE,
         fresh_below: float = DEFAULT_FRESH_BELOW,
         tail_above: float = DEFAULT_TAIL_ABOVE,
         reset_headroom_clears: bool = False) -> dict:
    """One scheduler tick. Pure decision — starts nothing itself.

    ``pipeline_warmup_tokens`` is the measured per-pipeline cold-prefix cost
    (§6.2), charged on every admission that lands in a concurrent slot (slot
    index ≥ 1, counting in-flight work); calibrated from telemetry, never
    hard-coded here.
    """
    if slots < 1:
        raise SchedulerError(f"slots must be >= 1, got {slots}")
    if in_flight < 0 or in_flight > slots:
        raise SchedulerError(f"in_flight {in_flight} outside 0..slots({slots})")

    flight_check = preflight(ledger)
    view = _ledger.reconcile(ledger, log, artifacts)
    state = view["tasks"]
    on_cycle = sorted({tid for cyc in flight_check["cycles"] for tid in cyc})

    candidates = [tid for tid, entry in ledger.tasks.items()
                  if entry and state[tid]["status"] == "not_started"
                  and all(state[d]["status"] == "done"
                          for d in ledger.tasks[tid]["deps"])]
    safe = [t for t in candidates if start_early_safe(t, ledger, state)]
    held = [t for t in candidates if t not in safe]

    phase = window_phase(occupancy, fresh_below, tail_above,
                         reset_headroom_clears)
    cp = critical_path_lengths(ledger)

    def forecast(tid):
        if estimates_doc is None:
            return {"tokens": None, "sample_size": 0, "low_confidence": True,
                    "quantile": "p95"}
        return _admission.forecast_tokens(ledger.tasks[tid]["profile"],
                                          estimates_doc)

    ordered = sorted(safe, key=lambda t: _priority_key(t, ledger, cp))
    if phase in ("tail", "unknown"):
        # tail of a window: cheap serial work first; unknown-cost tasks last
        ordered = sorted(
            ordered, key=lambda t: (forecast(t)["tokens"] is None,
                                    forecast(t)["tokens"] or 0.0, t))
        slots = min(slots, 1)

    start, deferred = [], []
    used = in_flight
    for tid in ordered:
        if used >= slots:
            deferred.append({"task": tid, "reason": "no idle slot"})
            continue
        fc = forecast(tid)
        if used >= 1 and fc["tokens"] is not None:
            fc = dict(fc, tokens=fc["tokens"] + pipeline_warmup_tokens)
        decision = _admission.admit(occupancy, fc,
                                    window_ceiling_tokens=window_ceiling_tokens,
                                    degrade=degrade)
        if decision["admit"]:
            start.append(tid)
            used += 1
        else:
            deferred.append({"task": tid, "reason": decision["reason"]})

    return {
        "start": start,
        "deferred": deferred,
        "held_unsafe": sorted(held),
        "on_cycle": on_cycle,
        "window_phase": phase,
        "preflight_ok": flight_check["ok"],
        "generation": view["generation"],
        "discrepancies": view["discrepancies"],
    }
