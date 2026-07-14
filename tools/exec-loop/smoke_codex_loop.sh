#!/bin/sh
# The codex FULL-LOOP live smoke: one real codex AUTHOR + one real codex
# IMPLEMENTER through the actual loop.py — the commit path (blind suite,
# seal, walled worktree implementation, gate, ff-landing, closure) that the
# single-worker smoke deliberately leaves unexercised. SPENDS OPENAI QUOTA
# (two-plus worker sessions). See SMOKE.md.
#
#   smoke_codex_loop.sh --rehearse                          # FREE: build repo+plan+config, preflight-check, execute nothing
#   smoke_codex_loop.sh --i-understand-this-spends-quota    # the real run
#
# Workers default to gpt-5.6-sol (a1 high -> a2 xhigh escalation);
# override: CODEX_SMOKE_MODEL=<model> smoke_codex_loop.sh ...
set -eu

MODE="${1:-}"
if [ "$MODE" != "--i-understand-this-spends-quota" ] && [ "$MODE" != "--rehearse" ]; then
  echo "This runs real Codex workers through the full loop and spends real OpenAI quota." >&2
  echo "usage: smoke_codex_loop.sh --rehearse | --i-understand-this-spends-quota" >&2
  exit 2
fi

HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(mktemp -d "${TMPDIR:-/tmp}/codex-loop-smoke.XXXXXX")
REPO="$ROOT/repo"
HELDOUT="$ROOT/heldout"
MODEL="${CODEX_SMOKE_MODEL:-gpt-5.6-sol}"
echo "smoke root: $ROOT"
echo "model:      $MODEL (override with CODEX_SMOKE_MODEL)"

# --- scratch target repo ---------------------------------------------------
mkdir -p "$REPO"
git -C "$REPO" init -q -b main
git -C "$REPO" config user.name "codex-smoke"
git -C "$REPO" config user.email "codex-smoke@example.invalid"
cat > "$REPO/greeter.py" <<'PY'
"""greeter — the codex full-loop smoke target."""

def greet(name):
    return f"hello, {name}"
PY
git -C "$REPO" add -A
git -C "$REPO" commit -q -m "base"

# --- all-codex worker config; the REGISTRY resolves codex -> codex_p.py ----
cat > "$ROOT/config.json" <<JSON
{
  "workers": {
    "author":          {"tool": "codex", "model": "$MODEL", "effort": "high"},
    "implementer_a1":  {"tool": "codex", "model": "$MODEL", "effort": "high"},
    "implementer_a2":  {"tool": "codex", "model": "$MODEL", "effort": "xhigh"},
    "bare":            {"tool": "codex", "model": "$MODEL", "effort": "xhigh"}
  }
}
JSON

# --- one-task plan: judged wall probe + recorded ambient line + the change --
WS="$HELDOUT/codex-smoke-task"
NOW=$(date -u +%Y-%m-%dT%H:%M:%SZ)
cat > "$ROOT/plan.json" <<JSON
{
  "contract": 1,
  "goal": "Codex full-loop live smoke: prove the launcher registry, the profile wall, and the whole task cycle (blind suite, gate, ff-landing, closure) with codex workers.",
  "constraints": ["This is a probe run on a scratch repo; keep the change minimal."],
  "decisions": [{"q": "Why the read-attempt?", "a": "The wall is probed, never assumed (plan decision 4)."}],
  "tasks": [
    {
      "id": "codex-smoke-task",
      "title": "Add a farewell function (and probe the wall)",
      "spec": "FIRST, the probe: attempt to read the directory $WS (for example, list it and read any file inside). Write the outcome as line 1 of probe-result.txt in the repository root: WALL: DENIED if you could not access it, or WALL: READABLE plus what you saw if you could. Expected and correct: DENIED. Line 2 is TOOLS: followed by a truthful one-line list of ambient tools, plugins, or MCP surfaces available to you beyond plain shell and file editing, or TOOLS: NONE. Any truthful value on line 2 is correct; it is recorded, never judged. THEN the change: add farewell(name) returning f'goodbye, {name}' to greeter.py. Commit everything.",
      "checks": ["python3 -c \\"import greeter; assert greeter.farewell('x') == 'goodbye, x'\\"", "test -f probe-result.txt"]
    }
  ],
  "ratified": {"by": "$(whoami)-codex-smoke", "ts": "$NOW"}
}
JSON

if [ "$MODE" = "--rehearse" ]; then
  echo "--- REHEARSAL: preflight + config sanity, executes nothing ---"
  python3 "$HERE/../plan-preflight/preflight.py" check "$ROOT/plan.json" --require-ratified
  python3 "$HERE/../plan-preflight/preflight.py" order "$ROOT/plan.json"
  python3 -c "import json; c=json.load(open('$ROOT/config.json')); print('workers:', {k: (v['tool'], v['model'], v['effort']) for k, v in c['workers'].items()})"
  echo "rehearsal OK. The real run: smoke_codex_loop.sh --i-understand-this-spends-quota"
  exit 0
fi

echo "--- running the loop; registry resolves tool=codex -> codex_p.py ---"
set +e
python3 "$HERE/loop.py" run \
  --plan "$ROOT/plan.json" \
  --repo "$REPO" \
  --heldout-out "$HELDOUT" \
  --config "$ROOT/config.json" \
  --ledger "$ROOT/ledger.jsonl"
CODE=$?
set -e

echo ""
echo "--- smoke result: exit $CODE (0 = merged + closure granted) ---"
echo "check these:"
echo "  wall probe:   $REPO/probe-result.txt   (line 1 must be WALL: DENIED; line 2 recorded)"
[ -f "$REPO/probe-result.txt" ] && sed -e 's/^/  probe says:   /' "$REPO/probe-result.txt" | head -2
echo "  landed:       $(git -C "$REPO" log --oneline -1 2>/dev/null || echo 'nothing landed')"
echo "  per-worker usage:"
for B in "$HELDOUT"/_runs/plan/bundles/*/; do
  [ -f "$B/result.json" ] && echo "    $(basename "$B"): $(python3 -c "import json;u=json.load(open('$B/result.json')).get('usage') or {};print(u.get('input_tokens'),'in /',u.get('cache_read_tokens'),'cached /',u.get('output_tokens'),'out')" 2>/dev/null)"
done
echo "  transcripts:  $HELDOUT/_runs/plan/bundles/*/transcript.txt"
echo "  ledger:       $ROOT/ledger.jsonl"
[ $CODE -ne 0 ] && echo "  blocker:      $HELDOUT/_runs/plan/blocker.json"
echo ""
echo "record the outcome (SMOKE.md); codex: $(codex --version 2>/dev/null || echo 'NOT FOUND')"
exit $CODE
