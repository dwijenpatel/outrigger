#!/usr/bin/env python3
"""Park-and-continue + ratification queue — decision cards (E3).

Design §6.3/§7 (2026-07-04 amendments; blueprint:
unattended-operation-prior-art.md §6). The queue (``docs/PROPOSALS.md``) holds
**decision cards**: the loop proposes, deterministic code executes, only a
human authorizes. Card anatomy:

- **Situation** — deterministic facts;
- **Triage** — advisory model commentary, **cached per content revision** (one
  triage per revision, ever — spend control); advisory fails open (a failed
  triage still publishes the card);
- **Recommended action** + exactly-one-choice checkbox options with
  machine-parseable ``<!-- opt:key -->`` markers;
- a hidden state comment carrying the **content hash** — ratification is
  **refused if the proposal changed after review** (stale-decision guard).

Park blockers ride the same shapes: a blocker record (schema E1) becomes a
card whose options are the operator's decision.
"""

from __future__ import annotations

import hashlib
import json
import re

from .schemas import validate_blocker

STATE_RE = re.compile(r"<!-- card-state: (\{.*?\}) -->", re.DOTALL)
OPT_RE = re.compile(r"^- \[(?P<tick>[ xX])\] (?P<label>.+?) <!-- opt:(?P<key>[\w-]+) -->\s*$",
                    re.MULTILINE)
CARD_SPLIT_RE = re.compile(r"^## card: ", re.MULTILINE)


class RatificationError(ValueError):
    pass


def content_hash(card: dict) -> str:
    """Hash of everything a human's decision is *about* — situation, options,
    recommendation. Triage is advisory and excluded (a re-triage must not
    invalidate a review of unchanged substance)."""
    basis = json.dumps({
        "card_id": card["card_id"],
        "situation": card["situation"],
        "recommendation": card["recommendation"],
        "options": [(o["key"], o["label"]) for o in card["options"]],
    }, sort_keys=True)
    return hashlib.sha256(basis.encode()).hexdigest()[:16]


def validate_card(card: dict) -> dict:
    for field in ("card_id", "situation", "recommendation"):
        if not isinstance(card.get(field), str) or not card[field].strip():
            raise RatificationError(f"card: {field!r} must be a non-empty string")
    options = card.get("options")
    if not isinstance(options, list) or len(options) < 2:
        raise RatificationError("card: needs >= 2 options")
    keys = []
    for i, opt in enumerate(options):
        if not isinstance(opt, dict) or not opt.get("key") or not opt.get("label"):
            raise RatificationError(f"card: option {i} needs key and label")
        if not re.fullmatch(r"[\w-]+", opt["key"]):
            raise RatificationError(f"card: option key {opt['key']!r} must be "
                                    f"word characters/dashes")
        keys.append(opt["key"])
    if len(set(keys)) != len(keys):
        raise RatificationError("card: option keys must be unique")
    return card


def render_card(card: dict, triage: str | None = None) -> str:
    """Render one card as committed markdown."""
    card = validate_card(card)
    digest = content_hash(card)
    lines = [f"## card: {card['card_id']}", ""]
    lines += ["### Situation", "", card["situation"].strip(), ""]
    lines += ["### Triage (advisory)", "",
              (triage.strip() if triage else
               "_triage unavailable — card published anyway (advisory fails "
               "open)_"), ""]
    lines += ["### Recommended action", "", card["recommendation"].strip(), ""]
    lines += ["### Your decision (tick exactly one)", ""]
    for opt in card["options"]:
        lines.append(f"- [ ] {opt['label']} <!-- opt:{opt['key']} -->")
    lines += ["",
              f"<!-- card-state: "
              f"{json.dumps({'card_id': card['card_id'], 'content_hash': digest, 'triage_cached_for': digest}, sort_keys=True)} -->",
              ""]
    return "\n".join(lines)


def blocker_to_card(blocker: dict) -> dict:
    """A park blocker becomes a decision card (one round-trip resolves it)."""
    b = validate_blocker(blocker)
    return {
        "card_id": f"blocker-{b['task_id']}",
        "situation": f"Task {b['task_id']} is parked.\n\nRepro: {b['repro']}",
        "recommendation": b["recommendation"],
        "options": b["options"],
    }


def cross_provider_card(profile: str, correlation: dict,
                        cost_note: str = "API-billed, outside the Max "
                                         "windows") -> dict:
    """H5 — the §7 cross-provider validator is a decision-card *option*:
    operator-ratified, never a silent default. Built from panel-correlation
    telemetry (``calibration.panel_correlation``) so the card carries the
    evidence the decision is about."""
    blind = correlation.get("correlated_blind_spots", 0)
    scored = correlation.get("trials_scored", 0)
    ids = ", ".join(correlation.get("blind_spot_ids", [])[:5]) or "none"
    situation = (
        f"Panel-correlation telemetry for profile {profile!r}: "
        f"{blind} correlated blind-spot trial(s) over {scored} scored canary "
        f"trial(s) (all-lenses-missed: {ids}). Same-family lenses are not "
        f"independent draws (errors correlate across models, rising with "
        f"capability); a cross-provider validator adds de-correlated "
        f"leverage. Cost: {cost_note}.")
    recommendation = (
        f"Add one cross-provider validator lens to {profile!r} — the panel "
        f"demonstrated a correlated blind spot." if blind else
        f"Hold — no all-lenses-missed trial observed on {profile!r}; keep "
        f"the cross-provider option in reserve.")
    return {
        "card_id": f"cross-provider-validator-{profile}",
        "situation": situation,
        "recommendation": recommendation,
        "options": [
            {"key": "adopt",
             "label": f"Add a cross-provider validator to {profile} "
                      f"(opt-in, {cost_note})"},
            {"key": "hold",
             "label": "Keep the all-Claude panel; revisit on the next "
                      "blind-spot event"},
        ],
    }


def parse_cards(text: str) -> list:
    """Parse committed cards back out of PROPOSALS.md."""
    cards = []
    chunks = CARD_SPLIT_RE.split(text)[1:]
    for chunk in chunks:
        card_id = chunk.splitlines()[0].strip()
        state_m = STATE_RE.search(chunk)
        if not state_m:
            raise RatificationError(f"card {card_id!r}: missing state comment")
        try:
            state = json.loads(state_m.group(1))
        except json.JSONDecodeError as exc:
            raise RatificationError(
                f"card {card_id!r}: corrupt state comment: {exc}") from None
        options = [{"key": m.group("key"), "label": m.group("label"),
                    "ticked": m.group("tick").lower() == "x"}
                   for m in OPT_RE.finditer(chunk)]
        cards.append({"card_id": card_id, "state": state, "options": options})
    return cards


def decision_of(parsed_card: dict) -> dict:
    """Extract the human decision. Exactly one tick decides; zero = pending;
    more than one = ambiguous (refused, never guessed)."""
    ticked = [o for o in parsed_card["options"] if o["ticked"]]
    if not ticked:
        return {"status": "pending"}
    if len(ticked) > 1:
        return {"status": "ambiguous",
                "why": f"{len(ticked)} options ticked — refusing to guess"}
    return {"status": "decided", "key": ticked[0]["key"],
            "label": ticked[0]["label"]}


def ratify(parsed_card: dict, current_card: dict) -> dict:
    """Apply the stale-decision guard: the decision counts only if the card's
    substance is unchanged since review (content hash match)."""
    decision = decision_of(parsed_card)
    if decision["status"] != "decided":
        return dict(decision, ratified=False)
    reviewed_hash = parsed_card["state"].get("content_hash")
    now_hash = content_hash(validate_card(current_card))
    if reviewed_hash != now_hash:
        return {"status": "stale", "ratified": False,
                "why": f"proposal changed after review (reviewed "
                       f"{reviewed_hash}, now {now_hash}) — re-review required"}
    return dict(decision, ratified=True)


def needs_triage(card: dict, triage_cache: dict) -> bool:
    """One triage per content revision, ever (spend control): triage runs only
    when the current hash has no cached triage."""
    return content_hash(validate_card(card)) not in triage_cache
