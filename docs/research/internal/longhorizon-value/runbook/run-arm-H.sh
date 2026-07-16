#!/bin/zsh
# run-arm-H.sh — the gated-harness arm (Sonnet 5 implementer, Opus 4.8 blind
# author, hard merge gate, 3 same-model attempts, honest stop on exhaustion).
#
#   ./run-arm-H.sh --yes        # SPENDS QUOTA: ~$7/task measured => ~$80 notional
#
# Walks the 11 ratified plans in chain order, one exec-loop run per plan
# (each plan is single-task, ratified, strict-preflight clean). The loop
# authors + seals the blind suite in-loop, spawns the implementer in a
# confined worktree, gates the merged tree, and lands ff-only on pass.
# A nonzero exit is the CORRECT-OR-STOP channel working: the run halts,
# blocker.json in the run dir names why, and this script refuses to continue
# past it. Re-running after adjudication resumes (completed plans are
# skipped via runs/arm-H/completed.txt).

set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
OUTRIGGER="$(cd "$HERE/../../../../.." && pwd)"
SPECS="$HERE/../specs"
REPO="${ARM_H_REPO:-$HOME/repos/eaitl-arm-H}"
HELDOUT="${ARM_H_HELDOUT:-$HOME/repos/eaitl-arm-H-heldout}"
RUNS="$HERE/../runs/arm-H"
LEDGER="$RUNS/ledger.jsonl"
DONE="$RUNS/completed.txt"

if [ "${1:-}" != "--yes" ]; then
  echo "This run SPENDS REAL QUOTA (Max-plan window): 11 full-tier tasks,"
  echo "each = 1 Opus author + 1-3 Sonnet implementer sessions + gate runs."
  echo "Measured pilot cost: ~\$7.10 notional per task => ~\$80 for the chain."
  echo "Re-run as: $0 --yes"
  exit 2
fi

mkdir -p "$RUNS"; touch "$DONE"
grep -v '^#' "$HERE/chain-order.txt" | while read -r plan; do
  [ -n "$plan" ] || continue
  if grep -qx "$plan" "$DONE"; then
    echo "=== skip (completed): $plan"
    continue
  fi
  echo "=== arm H: $plan"
  python3 "$OUTRIGGER/tools/exec-loop/loop.py" run \
    --plan "$SPECS/$plan" \
    --repo "$REPO" \
    --heldout-out "$HELDOUT" \
    --config "$HERE/arm-H.config.json" \
    --ledger "$LEDGER"
  rc=$?
  if [ $rc -ne 0 ]; then
    echo ""
    echo "ARM H STOPPED at $plan (exit $rc). This is the honest-stop channel."
    echo "Adjudicate: read blocker.json under $HELDOUT/_runs/<plan>/, resolve via"
    echo "the two doors (amend spec -> re-ratify -> rerun; or edit suite ->"
    echo "seal --retire --adjudicated-by ... -> rerun), append the lesson_target"
    echo "ledger record, then re-run this script — completed plans are skipped."
    exit $rc
  fi
  echo "$plan" >> "$DONE"
done
echo "ARM H COMPLETE — all 11 tasks landed behind the gate. Ledger: $LEDGER"
