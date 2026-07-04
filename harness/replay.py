#!/usr/bin/env python3
"""Safe-RTS vault replay + leakage budget (D3) — **ships disabled**.

Design §5.5: on a durable-FAIL re-validation, a naive loop re-authors held-out
tests and re-reviews a ~95%-unchanged diff — pure token redundancy. This module
plans the reuse under three non-negotiables:

- **Safe-RTS property** (Ekstazi/TIA): never skip a test the change could
  affect. A test is replayable-as-is only when *none* of its recorded
  dependencies intersect the changed paths; a test with **no dependency
  record is treated as affected** (full-run fallback for the unanalyzable).
- **Fresh authoring on the changed surface is mandatory** — a replayed corpus
  is a regression floor, structurally unable to find a new hole.
- **Risk-floored surfaces never replay** — full fresh re-derivation exactly
  where a gamed frozen set is most dangerous. And a **leakage budget** bounds
  adaptive reuse of any fixed hidden set (Ladder/Thresholdout): per-test replay
  counts persist; over-budget tests rotate out for re-derivation.

Enabling is a **Stage-2 flip** gated on Stage-1 telemetry (§11): every entry
point takes ``enabled`` and returns the full-fresh plan when False (default) —
building the machinery early is fine, *trusting* it is evidence-gated.
"""

from __future__ import annotations

import json
import os

DEFAULT_REPLAY_BUDGET = 10  # replays per corpus entry before rotation
ENABLED_DEFAULT = False     # Stage-2 flip; never enable by default


class ReplayError(ValueError):
    pass


def validate_dep_manifest(doc: dict) -> dict:
    """{test_relpath: [dependency paths]} recorded at authoring time."""
    if not isinstance(doc, dict):
        raise ReplayError("dependency manifest must be an object")
    for test, deps in doc.items():
        if not isinstance(test, str) or not test:
            raise ReplayError("manifest keys must be test paths")
        if not isinstance(deps, list) or not all(
                isinstance(d, str) and d for d in deps):
            raise ReplayError(f"{test}: deps must be a list of paths")
    return doc


def _touches(deps: list, changed: set) -> bool:
    return any(d in changed for d in deps)


def replay_plan(dep_manifest: dict, changed_paths: list,
                corpus_tests: list,
                floored_paths: list | None = None,
                replay_counts: dict | None = None,
                replay_budget: int = DEFAULT_REPLAY_BUDGET,
                enabled: bool = ENABLED_DEFAULT) -> dict:
    """Plan one re-validation. Returns::

        {"replay": [...],          # unchanged surface: re-execute, zero authoring
         "rerun_fresh": [...],     # affected/unanalyzable/floored/over-budget:
                                   # re-run AND fresh authoring on their surface
         "fresh_authoring_required": bool,   # always True on a non-empty diff
         "reasons": {test: why}, "enabled": bool}

    Disabled (default): everything lands in ``rerun_fresh`` — behaviorally the
    naive full-fresh loop, so flipping the flag can only *remove* work, never
    rigor.
    """
    manifest = validate_dep_manifest(dep_manifest)
    if replay_budget < 1:
        raise ReplayError(f"replay_budget must be >= 1, got {replay_budget}")
    changed = set(changed_paths)
    floored = set(floored_paths or [])
    counts = replay_counts or {}

    replay, rerun, reasons = [], [], {}
    for test in sorted(corpus_tests):
        if not enabled:
            rerun.append(test)
            reasons[test] = "replay disabled (Stage-2 flip not taken)"
            continue
        deps = manifest.get(test)
        if deps is None:
            rerun.append(test)
            reasons[test] = "no dependency record — unanalyzable, safe-RTS " \
                            "fallback is full fresh"
            continue
        if _touches(deps, changed):
            rerun.append(test)
            reasons[test] = "depends on the changed surface"
            continue
        if _touches(deps, floored) or any(d in floored for d in [test]):
            rerun.append(test)
            reasons[test] = "risk-floored surface — never replayed (§5.5)"
            continue
        if counts.get(test, 0) >= replay_budget:
            rerun.append(test)
            reasons[test] = f"leakage budget exhausted " \
                            f"({counts.get(test, 0)} replays) — rotate/refresh"
            continue
        replay.append(test)
        reasons[test] = "unaffected by the diff; within leakage budget"

    return {"replay": replay, "rerun_fresh": rerun,
            "fresh_authoring_required": bool(changed),
            "reasons": reasons, "enabled": enabled}


# -- leakage-budget state --------------------------------------------------------


class ReplayCounts:
    """Persisted per-test replay counters (the leakage-budget state)."""

    def __init__(self, path: str):
        self.path = path

    def read(self) -> dict:
        try:
            with open(self.path) as fh:
                doc = json.load(fh)
        except FileNotFoundError:
            return {}
        except json.JSONDecodeError as exc:
            raise ReplayError(f"replay counts {self.path} corrupt: {exc}") from None
        if not isinstance(doc, dict):
            raise ReplayError(f"replay counts {self.path}: not an object")
        return doc

    def record_replays(self, tests: list) -> dict:
        counts = self.read()
        for test in tests:
            counts[test] = counts.get(test, 0) + 1
        parent = os.path.dirname(self.path) or "."
        os.makedirs(parent, exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w") as fh:
            json.dump(counts, fh, indent=2, sort_keys=True)
            fh.write("\n")
        os.replace(tmp, self.path)
        return counts

    def rotate(self, tests: list) -> dict:
        """Reset counters for re-derived tests (the corpus entry was refreshed,
        so its leakage clock restarts)."""
        counts = self.read()
        for test in tests:
            counts.pop(test, None)
        tmp = self.path + ".tmp"
        with open(tmp, "w") as fh:
            json.dump(counts, fh, indent=2, sort_keys=True)
            fh.write("\n")
        os.replace(tmp, self.path)
        return counts
