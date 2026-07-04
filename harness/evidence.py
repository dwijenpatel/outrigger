#!/usr/bin/env python3
"""Telemetry roll-up + EVIDENCE.md generator (F1, design §8).

The committed justification surface: *is the machinery catching real defects,
is the cost justified, which features actually fire.* Inputs are artifacts only
(run-log records, escapes log, canary trials, governor decisions); output
follows the §5.4 format policy — aggregate header first, flattened Markdown
tables, definitive empty states, sticky-``~`` on any estimate-tainted total.
"""

from __future__ import annotations

import os

from . import governor as _governor
from .calibration import kill_rate as _kill_rate


class EvidenceError(ValueError):
    pass


def rollup(runlog_records: list) -> dict:
    """Aggregate task_complete records per (role, tier, effort, profile)."""
    cells: dict = {}
    totals = {"tasks": 0, "tokens": 0, "fails": 0}
    for rec in runlog_records:
        if rec.get("event") != "task_complete":
            continue
        key = (rec.get("role") or "?", rec.get("tier") or "?",
               rec.get("effort") or "?", rec.get("profile") or "?")
        cell = cells.setdefault(key, {"tasks": 0, "tokens": 0, "fails": 0})
        cell["tasks"] += 1
        cell["tokens"] += rec.get("total_tokens") or 0
        if rec.get("outcome") == "fail":
            cell["fails"] += 1
        totals["tasks"] += 1
        totals["tokens"] += rec.get("total_tokens") or 0
        if rec.get("outcome") == "fail":
            totals["fails"] += 1
    return {"cells": cells, "totals": totals}


def catch_rate(escapes: list, merged_tasks: int) -> dict:
    """Escapes per merged task — the panel's ground-truth miss rate. None when
    nothing merged (never fabricated)."""
    if merged_tasks < 0:
        raise EvidenceError("merged_tasks must be >= 0")
    if merged_tasks == 0:
        return {"escapes": len(escapes), "merged_tasks": 0, "rate": None}
    return {"escapes": len(escapes), "merged_tasks": merged_tasks,
            "rate": len(escapes) / merged_tasks}


def generate_evidence_md(runlog_records: list, escapes: list,
                         canary_trials: list, governor_decisions: list,
                         merged_tasks: int,
                         kill_trials: list | None = None) -> str:
    roll = rollup(runlog_records)
    catches = catch_rate(escapes, merged_tasks)
    gov = _governor.summarize_decisions(governor_decisions)
    est = gov["estimated"]
    canaries_caught = sum(1 for t in canary_trials if t.get("caught"))
    krate = _kill_rate(kill_trials or [])

    fmt = _governor.fmt_estimated
    header = (f"evidence: {roll['totals']['tasks']} worker runs · "
              f"{fmt(roll['totals']['tokens'], est)} tokens · "
              f"{catches['escapes']} escape(s) over {merged_tasks} merged "
              f"task(s) · canaries {canaries_caught}/{len(canary_trials)} caught")
    lines = [header, ""]

    lines.append(f"catch-rate: "
                 + (f"{1 - catches['rate']:.1%} (escape rate "
                    f"{catches['rate']:.1%})" if catches["rate"] is not None
                    else "n/a (0 merged tasks — nothing to measure yet)"))
    lines.append(f"visible-oracle kill-rate: "
                 + (f"{krate:.0%}" if krate is not None else
                    "unmeasured (treated as weak — rigor stays up)"))
    lines.append(f"governor: {gov['readings']} reading(s) from "
                 + (", ".join(gov["sources"]) or "no sources")
                 + (f"; worst windows {gov['worst_windows']}"
                    if gov["worst_windows"] else "; no window fractions")
                 + ("; totals estimated (~) — at least one estimate-rung "
                    "reading" if est else ""))
    lines.append("")

    if roll["cells"]:
        lines.append("| role | tier | effort | profile | tasks | tokens | fail-rate |")
        lines.append("|---|---|---|---|---|---|---|")
        for key in sorted(roll["cells"]):
            cell = roll["cells"][key]
            fr = cell["fails"] / cell["tasks"]
            lines.append(f"| {key[0]} | {key[1]} | {key[2]} | {key[3]} | "
                         f"{cell['tasks']} | {fmt(cell['tokens'], est)} | "
                         f"{fr:.0%} |")
    else:
        lines.append("worker runs: 0 recorded — no cost table yet")
    lines.append("")

    if escapes:
        lines.append("| escape | task | severity | discovered by |")
        lines.append("|---|---|---|---|")
        for e in escapes:
            lines.append(f"| {e.get('description', '?')[:60]} | "
                         f"{e.get('task_id', '?')} | {e.get('severity', '?')} | "
                         f"{e.get('discovered_by', '?')} |")
    else:
        lines.append("escapes: 0 recorded (the desired state — insurance "
                     "machinery stays)")
    return "\n".join(lines) + "\n"


def write_evidence_md(path: str, content: str) -> str:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        fh.write(content)
    os.replace(tmp, path)
    return path
