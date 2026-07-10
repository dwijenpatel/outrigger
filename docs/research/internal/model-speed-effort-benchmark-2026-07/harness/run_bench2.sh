#!/bin/bash
# Round 2: thinking-heavy task to expose effort-level differences
cd "$(dirname "$0")"
CLAUDE="$HOME/.local/bin/claude"

HARD_PROMPT="A Harshad number is divisible by the sum of its digits. What is the sum of all Harshad numbers strictly between 100 and 500? Work it out by careful reasoning (no tools are available). Reply with just the final number."

run_one() {
  local model="$1" effort="$2"
  local out="result2_${model}_${effort}.json"
  local args=(-p "$HARD_PROMPT" --model "$model" --output-format json --tools "" --strict-mcp-config --mcp-config '{"mcpServers":{}}')
  if [ "$effort" != "none" ]; then
    args+=(--effort "$effort")
  fi
  "$CLAUDE" "${args[@]}" > "$out" 2> "${out%.json}.err"
  echo "done: $out"
}

RUNS=()
for m in fable opus sonnet; do
  for e in low medium high xhigh max; do
    RUNS+=("$m $e")
  done
done
RUNS+=("haiku none")

MAX_JOBS=4
for spec in "${RUNS[@]}"; do
  set -- $spec
  model="$1"; effort="$2"
  while [ "$(jobs -rp | wc -l)" -ge "$MAX_JOBS" ]; do sleep 2; done
  run_one "$model" "$effort" &
done
wait
echo "ALL ROUND2 RUNS COMPLETE"
