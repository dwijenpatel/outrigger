#!/bin/zsh
# setup-arms.sh — one-time, quota-free environment preparation for the
# long-horizon value experiment. Idempotent; safe to re-run.
#
#   ./setup-arms.sh
#
# Creates the three arm repositories (clean clones of eaitl at the shared
# base commit c646832), the held-out roots (outside every repo, as the
# heldout-suite tool requires), and the per-arm results directories.
# Aborts loudly if the toolchain or the base commit is wrong.

set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
EAITL_SRC="${EAITL_SRC:-$HOME/repos/eaitl}"
BASE_SHA="c646832"
ARM_ROOT="${ARM_ROOT:-$HOME/repos}"
RUNS="$HERE/../runs"

fail() { echo "ABORT: $1" >&2; exit 1 }

echo "--- toolchain probe (T7's checks shell out to tsc + node) ---"
for tool in python3 mypy tsc node git; do
  command -v "$tool" >/dev/null || fail "$tool not on PATH"
done
python3 --version && mypy --version && echo "tsc $(tsc --version 2>/dev/null || tsc -v)" && node --version

echo "--- base repo check ---"
[ -d "$EAITL_SRC/.git" ] || fail "$EAITL_SRC is not a git repo"
head="$(git -C "$EAITL_SRC" rev-parse HEAD)"
case "$head" in
  ${BASE_SHA}*) echo "eaitl HEAD = $head (matches base $BASE_SHA)" ;;
  *) fail "eaitl HEAD $head != expected base $BASE_SHA — the arms must start from the landed engine" ;;
esac
[ -z "$(git -C "$EAITL_SRC" status --porcelain)" ] || fail "$EAITL_SRC has uncommitted changes"

echo "--- arm clones ---"
for arm in H N F; do
  repo="$ARM_ROOT/eaitl-arm-$arm"
  if [ -d "$repo/.git" ]; then
    echo "exists: $repo"
  else
    git clone --no-hardlinks "$EAITL_SRC" "$repo" || fail "clone $repo"
  fi
  ahead="$(git -C "$repo" rev-parse HEAD)"
  case "$ahead" in
    ${BASE_SHA}*) echo "  $repo @ $ahead ok" ;;
    *) echo "  NOTE: $repo HEAD $ahead is past base (a run is in progress or done)" ;;
  esac
done

echo "--- held-out roots (must live OUTSIDE every repo) + results dirs ---"
mkdir -p "$ARM_ROOT/eaitl-arm-H-heldout" "$ARM_ROOT/eaitl-heldout-slice2"
mkdir -p "$RUNS/arm-H" "$RUNS/arm-N" "$RUNS/arm-F"
echo "held-out (arm H, in-loop): $ARM_ROOT/eaitl-arm-H-heldout"
echo "held-out (slice 2, grading-only): $ARM_ROOT/eaitl-heldout-slice2"
echo "results: $RUNS/arm-{H,N,F}"

echo "--- plan admission (all 11 must pass --require-ratified) ---"
plans=(${(f)"$(grep -Ev '^#|^$' "$HERE/chain-order.txt")"})
for plan in $plans; do
  python3 "$HERE/../../../../../tools/plan-preflight/preflight.py" check \
    "$HERE/../specs/$plan" --require-ratified >/dev/null || fail "preflight failed: $plan"
  echo "  ok: $plan"
done

echo ""
echo "SETUP COMPLETE. Start order: run-arm-N.sh / run-arm-F.sh / run-arm-H.sh (any order,"
echo "independent repos). Optional first: author-slice2.sh (grading oracle, recommended)."
