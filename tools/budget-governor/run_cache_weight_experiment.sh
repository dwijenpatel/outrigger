#!/usr/bin/env bash
# Cache-read quota-weight experiment runner (T1 in docs/design/evidence-based-harness.md;
# originally design-v1 SS10.2 / SS12 open question #2, now attic'd).
# See cache-read-quota-weight-experiment.md for the full protocol, the math, and how to
# read the result. THIS SCRIPT SPENDS REAL MAX-PLAN QUOTA when run with arm-a/arm-b -- read
# the protocol doc and confirm timing with yourself before running those for real.
#
# Usage:
#   ./run_cache_weight_experiment.sh dry-run                # one trivial turn; inspect the
#                                                            # real --output-format json schema
#                                                            # before trusting `summarize` below
#   ./run_cache_weight_experiment.sh gen-filler WORDS        # print the deterministic filler
#                                                            # text (no API calls; free)
#   ./run_cache_weight_experiment.sh arm-a N WORDS           # cache-preserving arm: N turns,
#                                                            # one growing session, filler-sized
#                                                            # append per turn
#   ./run_cache_weight_experiment.sh arm-b N WORDS           # cache-busting arm: same N turns,
#                                                            # DISABLE_PROMPT_CACHING=1 for the
#                                                            # whole sequence
#   ./run_cache_weight_experiment.sh summarize LOGDIR        # sum token fields across a
#                                                            # completed arm's turn-*.json logs
#                                                            # (no API calls; free; also works
#                                                            # on synthetic/fixture json)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CMD="${1:-}"

usage() {
  echo "usage: $0 {dry-run|gen-filler|arm-a|arm-b|summarize} ..." >&2
  exit 1
}

# Deterministic filler generator. Determinism matters more than content: both arms must read
# from this exact function so a word-count target maps to the same text every time.
gen_filler() {
  local words_needed="${1:?word count required}"
  local para="The quick brown fox jumps over the lazy dog. Pack my box with five dozen liquor jugs. How vexingly quick daft zebras jump. The five boxing wizards jump quickly."
  local para_words
  para_words=$(wc -w <<< "$para")
  local repeats=$(( (words_needed + para_words - 1) / para_words ))
  local i
  for (( i = 0; i < repeats; i++ )); do
    printf '%s ' "$para"
  done
}

# Both arms MUST run the same model explicitly: bare `claude -p` inherits a config
# default that some plans auto-switch under window pressure (e.g. Opus -> Sonnet),
# which would make the arms incomparable. Fail closed rather than pick a default here
# — the model choice is part of the experiment's pre-registration.
require_model() {
  if [ -z "${T1_MODEL:-}" ]; then
    echo "set T1_MODEL to pin one model for both arms, e.g.:" >&2
    echo "  T1_MODEL=claude-opus-4-8 $0 arm-a 5 6000" >&2
    echo "(bare claude -p inherits a config default that may auto-switch mid-window)" >&2
    exit 2
  fi
}

run_turns() {
  local n="${1:?turn count required}"
  local words="${2:?filler word count required}"
  local label="${3:?arm label required}"
  local outdir="$SCRIPT_DIR/experiment-logs/$(date +%Y-%m-%d_%H%M%S)-${label}"
  mkdir -p "$outdir"
  local filler
  filler="$(gen_filler "$words")"
  local i out
  for (( i = 1; i <= n; i++ )); do
    if [ "$i" -eq 1 ]; then
      out=$(claude -p "${filler} (turn ${i}) Reply with exactly: OK" --model "$T1_MODEL" --output-format json)
    else
      out=$(claude -p "${filler} (turn ${i}) Reply with exactly: OK" --model "$T1_MODEL" --output-format json --continue)
    fi
    echo "$out" > "$outdir/turn-${i}.json"
    echo "wrote $outdir/turn-${i}.json" >&2
  done
  echo "$outdir"
}

summarize() {
  local dir="${1:?log directory required}"
  if ! ls "$dir"/turn-*.json >/dev/null 2>&1; then
    echo "no turn-*.json files found in $dir" >&2
    exit 1
  fi
  # Field paths below were VALIDATED 2026-07-11 (zero quota) against real committed
  # `claude -p --output-format json` outputs from build 2.1.201 (the benchmark artifacts in
  # docs/research/internal/model-speed-effort-benchmark-2026-07/results/): .usage.input_tokens,
  # .usage.output_tokens, .usage.cache_read_input_tokens, .usage.cache_creation_input_tokens,
  # and .total_cost_usd all match and sum correctly across multi-file input. Schema decay is
  # vendor-build: still run `dry-run` once as a confirmation on the build you'll use, and
  # adjust here if a newer CLI moved the keys.
  jq -s '{
    turns: length,
    total_input_tokens:          (map(.usage.input_tokens // .input_tokens // 0) | add),
    total_cache_read_tokens:     (map(.usage.cache_read_input_tokens // .cache_read_input_tokens // 0) | add),
    total_cache_creation_tokens: (map(.usage.cache_creation_input_tokens // .cache_creation_input_tokens // 0) | add),
    total_output_tokens:         (map(.usage.output_tokens // .output_tokens // 0) | add),
    total_cost_usd:              (map(.total_cost_usd // 0) | add)
  }' "$dir"/turn-*.json
}

case "$CMD" in
  gen-filler)
    words="${2:?usage: $0 gen-filler WORDS}"
    gen_filler "$words"
    echo
    ;;
  dry-run)
    outdir="$SCRIPT_DIR/experiment-logs/$(date +%Y-%m-%d_%H%M%S)-dry-run"
    mkdir -p "$outdir"
    filler="$(gen_filler 200)"
    claude -p "${filler} Reply with exactly: OK" --output-format json > "$outdir/turn-1.json"
    echo "wrote $outdir/turn-1.json" >&2
    echo "inspect with: jq . '$outdir/turn-1.json'" >&2
    echo "confirm these concepts appear somewhere in it (exact key path may differ -- adjust the summarize() jq filter in this script if so): input tokens, output tokens, cache_read tokens, cache_creation tokens, total_cost_usd" >&2
    ;;
  arm-a)
    n="${2:?usage: T1_MODEL=<model> $0 arm-a N WORDS}"; words="${3:?usage: T1_MODEL=<model> $0 arm-a N WORDS}"
    require_model
    run_turns "$n" "$words" "arm-a"
    ;;
  arm-b)
    n="${2:?usage: T1_MODEL=<model> $0 arm-b N WORDS}"; words="${3:?usage: T1_MODEL=<model> $0 arm-b N WORDS}"
    require_model
    export DISABLE_PROMPT_CACHING=1
    run_turns "$n" "$words" "arm-b"
    ;;
  summarize)
    dir="${2:?usage: $0 summarize LOGDIR}"
    summarize "$dir"
    ;;
  *)
    usage
    ;;
esac
