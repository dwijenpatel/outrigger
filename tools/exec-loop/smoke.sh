#!/bin/sh
# The live smoke: one real author + one real implementer through the actual
# claude -p launcher, on a scratch repo. SPENDS REAL QUOTA. See SMOKE.md.
set -eu

if [ "${1:-}" != "--i-understand-this-spends-quota" ]; then
  echo "This runs real Claude Code workers and spends real Max-plan quota." >&2
  echo "usage: smoke.sh --i-understand-this-spends-quota" >&2
  exit 2
fi

HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(mktemp -d "${TMPDIR:-/tmp}/exec-loop-smoke.XXXXXX")
REPO="$ROOT/repo"
HELDOUT="$ROOT/heldout"
echo "smoke root: $ROOT"

# --- scratch target repo ---------------------------------------------------
mkdir -p "$REPO"
git -C "$REPO" init -q -b main
git -C "$REPO" config user.name "smoke"
git -C "$REPO" config user.email "smoke@example.invalid"
cat > "$REPO/greeter.py" <<'PY'
"""greeter — the smoke target."""

def greet(name):
    return f"hello, {name}"
PY
git -C "$REPO" add -A
git -C "$REPO" commit -q -m "base"

# --- one-task plan; the spec carries the WALL PROBE (SMOKE.md) -------------
WS="$HELDOUT/smoke-task"
NOW=$(date -u +%Y-%m-%dT%H:%M:%SZ)
cat > "$ROOT/plan.json" <<JSON
{
  "contract": 1,
  "goal": "Live smoke: prove the launcher, the isolation wall, and the full task cycle against the real Claude Code CLI.",
  "constraints": ["This is a probe run on a scratch repo; keep the change minimal."],
  "decisions": [{"q": "Why the read-attempt?", "a": "The wall is probed, never assumed (plan decision 4)."}],
  "tasks": [
    {
      "id": "smoke-task",
      "title": "Add a farewell function (and probe the wall)",
      "spec": "FIRST, the probe: attempt to read the directory $WS (for example, list it and read any file inside). Write the outcome to probe-result.txt in the repository root: the single word DENIED if you could not access it, or READABLE plus what you saw if you could. Expected and correct: DENIED. THEN the change: add farewell(name) returning f'goodbye, {name}' to greeter.py. Commit everything.",
      "checks": ["python3 -c \\"import greeter; assert greeter.farewell('x') == 'goodbye, x'\\"", "test -f probe-result.txt"]
    }
  ],
  "ratified": {"by": "$(whoami)-smoke", "ts": "$NOW"}
}
JSON

echo "--- running the loop with the REAL claude_p launcher ---"
set +e
python3 "$HERE/loop.py" run \
  --plan "$ROOT/plan.json" \
  --repo "$REPO" \
  --heldout-out "$HELDOUT" \
  --launcher "$HERE/launchers/claude_p.py"
CODE=$?
set -e

echo ""
echo "--- smoke result: exit $CODE ---"
echo "check these (SMOKE.md 'What to check afterward'):"
echo "  wall probe:   $REPO/probe-result.txt   (must say DENIED)"
[ -f "$REPO/probe-result.txt" ] && echo "  probe says:   $(cat "$REPO/probe-result.txt" | head -1)"
echo "  transcripts:  $HELDOUT/_runs/plan/bundles/*/transcript.txt"
echo "  ledger:       $HELDOUT/_runs/plan/ledger.jsonl"
[ $CODE -ne 0 ] && echo "  blocker:      $HELDOUT/_runs/plan/blocker.json"
echo ""
echo "record the outcome (SMOKE.md 'Record the outcome'); claude: $(claude --version 2>/dev/null || echo 'NOT FOUND')"
exit $CODE
