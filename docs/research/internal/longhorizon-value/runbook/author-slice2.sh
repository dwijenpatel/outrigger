#!/bin/zsh
# author-slice2.sh — the SECOND, independently-authored held-out slice
# (the oracle-circularity control: arm H is gated on the in-loop suites, so
# head-to-head silent-wrong claims need an oracle no arm was optimized
# against). Grading-only: nothing gates on these suites.
#
#   ./author-slice2.sh --yes    # SPENDS QUOTA: 11 Opus author sessions, ~$4/task measured
#
# Per ratified plan: materialize an authoring workspace OUTSIDE every repo
# (heldout-suite CLI), spawn one fresh blind Opus 4.8 author against the
# BASE eaitl repo (the author sees this task's ratified scope only — never
# siblings, never implementations, never the other slice), then seal
# (fails-on-base policy) and record the manifest anchor in the ledger.
# Idempotent: already-sealed workspaces are skipped. Fail-fast: any
# materialize/launch/seal failure aborts (this is prep, not an arm).

set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
OUTRIGGER="$(cd "$HERE/../../../../.." && pwd)"
SPECS="$HERE/../specs"
HELDOUT_CLI="$OUTRIGGER/tools/heldout-suite/heldout.py"
LAUNCHER="$OUTRIGGER/tools/exec-loop/launchers/claude_p.py"
LEDGER_CLI="$OUTRIGGER/tools/run-ledger/ledger.py"
BASE_REPO="${EAITL_SRC:-$HOME/repos/eaitl}"
OUT="${SLICE2_OUT:-$HOME/repos/eaitl-heldout-slice2}"
RUNS="$HERE/../runs/slice2"
LEDGER="$RUNS/ledger.jsonl"

if [ "${1:-}" != "--yes" ]; then
  echo "This SPENDS REAL QUOTA: up to 11 fresh Opus 4.8 author sessions"
  echo "(~\$4/task measured on the pilot => ~\$45 notional). Grading-only slice."
  echo "Re-run as: $0 --yes"
  exit 2
fi

mkdir -p "$RUNS"
seq=0
grep -v '^#' "$HERE/chain-order.txt" | while read -r plan; do
  [ -n "$plan" ] || continue
  seq=$((seq + 1))
  tid="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['tasks'][0]['id'])" "$SPECS/$plan")"
  ws="$OUT/$tid"
  if [ -f "$ws/manifest.json" ]; then
    echo "=== skip (sealed): $tid"
    continue
  fi
  echo "=== slice2 author: $tid ($plan)"
  if [ ! -d "$ws" ]; then
    python3 "$HELDOUT_CLI" materialize --plan "$SPECS/$plan" --task "$tid" \
      --repo "$BASE_REPO" --out "$OUT" || { echo "ABORT: materialize $tid" >&2; exit 1 }
  fi

  ts="$(date -u +%Y-%m-%dT%H%M%SZ)"
  bundle="$RUNS/bundles/$ts-$(printf %03d $seq)-$tid-author-slice2"
  mkdir -p "$bundle"
  cat > "$bundle/instructions.md" <<EOF
You are the TEST-AUTHOR for task \`$tid\`.

Your authoring workspace is: $ws

Read $ws/authoring/task.json (your task and the plan context) and $ws/authoring/AUTHORING.md, then follow the role contract at $OUTRIGGER/tools/heldout-suite/ROLE.md.

The target repository (base checkout) is: $BASE_REPO — read it to match conventions and real module paths. Write stdlib-unittest tests into $ws/suite/ as test_*.py files.

At least one test must FAIL against the unchanged base (that is the seal policy); base-passing regression guards are welcome. You never run seal.
EOF
  python3 - "$bundle" "$ws" <<'EOF'
import json, sys
bundle, ws = sys.argv[1], sys.argv[2]
json.dump({
    "contract": 1, "role": "author", "attempt": 1,
    "worker": {"tool": "claude", "model": "claude-opus-4-8", "effort": "xhigh"},
    "isolation": {"deny_read": [], "sandbox": True, "network": True},
    "cwd": ws, "timeout_s": 1800,
}, open(f"{bundle}/params.json", "w"), indent=2)
EOF
  python3 "$LAUNCHER" "$bundle" || { echo "ABORT: author launch failed for $tid (see $bundle/result.json)" >&2; exit 1 }

  seal_out="$(python3 "$HELDOUT_CLI" seal --workspace "$ws" --repo "$BASE_REPO")" \
    || { echo "ABORT: seal refused for $tid (policy failure — inspect $ws)" >&2; exit 1 }
  echo "$seal_out"
  # seal prints a JSON object whose manifest_sha256 is the out-of-band anchor;
  # record the whole object (plus workspace + bundle provenance) on the ledger.
  echo "$seal_out" | python3 - "$LEDGER_CLI" "$LEDGER" "$tid" "$ws" "$bundle" <<'EOF' \
    || { echo "ABORT: ledger append failed for $tid" >&2; exit 1 }
import json, subprocess, sys
ledger_cli, ledger, tid, ws, bundle = sys.argv[1:6]
seal = json.load(sys.stdin)
seal.update({"task_id": tid, "workspace": ws, "bundle": bundle})
subprocess.run([sys.executable, ledger_cli, "append", ledger, "--kind", "run",
                "--subject", f"longhorizon/slice2/{tid}/seal",
                "--data", json.dumps(seal)], check=True)
EOF
done
echo "SLICE 2 COMPLETE — sealed workspaces under $OUT, anchors in $LEDGER"
