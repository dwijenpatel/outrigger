#!/usr/bin/env python3
"""Controller lever proposals — evidence-gated, never self-applied (F2, §8).

The reflection layer's teeth, with every §8 discipline mechanized:

- **one lever at a time** — an unresolved proposal blocks new ones;
- **minimum-sample floors** — no proposal from a thin cell;
- **protected profiles strengthen-only** — high/critical never get downgrade
  proposals from this code path, period;
- **every downgrade needs calibration proof** — the D4 gate
  (:func:`harness.calibration.downgrade_allowed`) must say yes first;
- output is a **decision card** (E3) carrying a cost/benefit estimate and the
  **paired-arm evaluation plan** (harness-evaluation-prior-art.md §2): one
  lever = one arm, continuous metric, paired per-task stats, out-of-sample
  difficulty strata, confirmatory label — so the flip, if ratified, is
  measured the way the evidence says levers must be.
"""

from __future__ import annotations

from .calibration import downgrade_allowed

PROTECTED_PROFILES = ("high", "critical")
DEFAULT_MIN_SAMPLES = 20

LEVERS = ("validator_count", "starting_tier", "effort", "concurrency_cap",
          "vault_replay_rate")
DIRECTIONS = ("strengthen", "downgrade")


class ControllerError(ValueError):
    pass


def arm_evaluation_plan(lever: str, change: str) -> dict:
    """The paired-arm template attached to every proposal."""
    return {
        "design": "paired-arm",
        "arms": {"baseline": "current config", "treatment": change},
        "metric": "mean hidden-test pass rate (continuous, never binarized) "
                  "+ tokens/task",
        "pairing": "same task in both arms; paired non-parametric test",
        "strata": "difficulty terciles defined out-of-sample",
        "label": "confirmatory (registered before the data)",
        "lever": lever,
    }


def propose(lever: str, direction: str, profile: str, change: str,
            cell_samples: int, cost_benefit: str,
            pending_unresolved_proposals: int,
            canary_trials: list, escapes: list,
            min_samples: int = DEFAULT_MIN_SAMPLES) -> dict:
    """Gate one lever proposal. Returns {"proposed": bool, "why", "card"?}."""
    if lever not in LEVERS:
        raise ControllerError(f"unknown lever {lever!r}; known: {LEVERS}")
    if direction not in DIRECTIONS:
        raise ControllerError(f"direction must be one of {DIRECTIONS}")
    if not change or not cost_benefit:
        raise ControllerError("proposal needs a change and a cost/benefit "
                              "estimate")

    if pending_unresolved_proposals > 0:
        return {"proposed": False,
                "why": f"{pending_unresolved_proposals} unresolved proposal(s) "
                       f"in the queue — one lever at a time"}
    if cell_samples < min_samples:
        return {"proposed": False,
                "why": f"cell has {cell_samples} samples, floor is "
                       f"{min_samples} — no proposal from a thin cell"}
    if direction == "downgrade":
        if profile in PROTECTED_PROFILES:
            return {"proposed": False,
                    "why": f"profile {profile!r} is protected: strengthen-only "
                           f"(§8) — this code path cannot propose a downgrade"}
        proof = downgrade_allowed(canary_trials, escapes)
        if not proof["allowed"]:
            return {"proposed": False,
                    "why": f"downgrade needs calibration proof: {proof['why']}"}

    card = {
        "card_id": f"lever-{lever}-{profile}-{direction}",
        "situation": (f"Lever: {lever} · profile: {profile} · direction: "
                      f"{direction}. Cell samples: {cell_samples}. "
                      f"Cost/benefit: {cost_benefit}"),
        "recommendation": change,
        "options": [
            {"key": "approve", "label": f"Approve: {change}"},
            {"key": "decline", "label": "Decline — keep current config"},
            {"key": "defer", "label": "Defer — ask again with more samples"},
        ],
        "evaluation_plan": arm_evaluation_plan(lever, change),
    }
    return {"proposed": True, "why": "all gates passed", "card": card}
