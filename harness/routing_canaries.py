#!/usr/bin/env python3
"""Skill-routing canaries — is the right skill invoked for the right prompt? (E4)

Design §5.4 skills discipline: triggering is unreliable (recall measured at
38–69% in the wild) and the skill list silently truncates. Load-bearing
procedures are phase-gated in prompts (immune to recall); for everything else,
these canaries measure routing the way §7's calibration canaries measure
panels:

- fixtures pair a prompt with its **expected skill set — including negative
  controls** where the expected set is empty (without them, over-invocation is
  invisible);
- scoring is exact-set precision/recall/F1 per fixture;
- **body fingerprints** (distinctive phrases from a skill's body, never its
  frontmatter) prove a skill actually *loaded* rather than being paraphrased —
  the detection channel when invocation telemetry is absent.

Running fixtures against a live agent spends quota and is **operator-gated**
(same rule as trace re-recording); this module owns fixture validity and
scoring, so the paid run is nothing but data collection.
"""

from __future__ import annotations

import json
import os

FIXTURES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "config", "skill-routing-canaries.json")


class RoutingError(ValueError):
    pass


def validate_fixtures(doc) -> list:
    if not isinstance(doc, list) or not doc:
        raise RoutingError("fixtures must be a non-empty list")
    seen = set()
    negatives = 0
    for i, fx in enumerate(doc):
        if not isinstance(fx, dict):
            raise RoutingError(f"fixture {i}: must be an object")
        fid = fx.get("id")
        if not isinstance(fid, str) or not fid or fid in seen:
            raise RoutingError(f"fixture {i}: needs a unique string id")
        seen.add(fid)
        if not isinstance(fx.get("prompt"), str) or not fx["prompt"].strip():
            raise RoutingError(f"fixture {fid}: needs a prompt")
        expected = fx.get("expected_skills")
        if not isinstance(expected, list) or not all(
                isinstance(s, str) and s for s in expected):
            raise RoutingError(f"fixture {fid}: expected_skills must be a list "
                               f"of skill names (empty = negative control)")
        if not expected:
            negatives += 1
    if negatives == 0:
        raise RoutingError("fixture set has no negative controls — "
                           "over-invocation would be unmeasurable")
    return doc


def score_fixture(expected: list, detected: list) -> dict:
    e, d = set(expected), set(detected)
    tp = len(e & d)
    precision = tp / len(d) if d else (1.0 if not e else 0.0)
    recall = tp / len(e) if e else (1.0 if not d else 0.0)
    f1 = (2 * precision * recall / (precision + recall)
          if precision + recall else 0.0)
    return {"pass": e == d, "precision": precision, "recall": recall, "f1": f1,
            "missing": sorted(e - d), "extra": sorted(d - e)}


def score_run(fixtures: list, invocations: dict) -> dict:
    """Score one collection run. ``invocations`` maps fixture id → skills the
    agent invoked. A fixture with no recorded run is a *coverage hole*,
    reported, never silently skipped (no silent caps)."""
    fixtures = validate_fixtures(fixtures)
    per, holes = {}, []
    for fx in fixtures:
        if fx["id"] not in invocations:
            holes.append(fx["id"])
            continue
        per[fx["id"]] = score_fixture(fx["expected_skills"],
                                      invocations[fx["id"]])
    scored = list(per.values())
    negatives = [per[fx["id"]] for fx in fixtures
                 if not fx["expected_skills"] and fx["id"] in per]
    return {
        "fixtures": len(fixtures),
        "scored": len(scored),
        "coverage_holes": holes,
        "perfect_match_rate": (sum(1 for s in scored if s["pass"]) / len(scored)
                               if scored else None),
        "mean_recall": (sum(s["recall"] for s in scored) / len(scored)
                        if scored else None),
        "mean_precision": (sum(s["precision"] for s in scored) / len(scored)
                           if scored else None),
        "negative_control_violations": sum(1 for s in negatives if not s["pass"]),
        "per_fixture": per,
    }


def fingerprint_hits(transcript_text: str, fingerprints: dict) -> dict:
    """``fingerprints``: skill → [distinctive body phrases]. A skill counts as
    loaded when any of its phrases appears verbatim — phrases must come from
    the body (frontmatter descriptions are always visible, so they prove
    nothing)."""
    if not isinstance(transcript_text, str):
        raise RoutingError("transcript must be a string")
    hits = {}
    for skill, phrases in fingerprints.items():
        if not isinstance(phrases, list) or not all(
                isinstance(p, str) and len(p) >= 12 for p in phrases):
            raise RoutingError(f"{skill}: fingerprints must be phrases of >= 12 "
                               f"chars (short strings false-positive)")
        hits[skill] = [p for p in phrases if p in transcript_text]
    return {skill: bool(found) for skill, found in hits.items()}


def load_fixtures(path: str = FIXTURES_PATH) -> list:
    with open(path) as fh:
        return validate_fixtures(json.load(fh))
