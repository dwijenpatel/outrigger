#!/bin/bash
# Model x effort speed benchmark via claude -p
cd "$(dirname "$0")"
CLAUDE="$HOME/.local/bin/claude"

REASON_PROMPT="A bookshelf has 6 distinct math books and 4 distinct physics books. In how many ways can they be arranged in a row so that no two physics books are adjacent? Reason it out yourself and reply with just the final number."
PROSE_PROMPT="Write a vivid 300-word description of a tide pool at dawn. Output only the prose, nothing else."

run_one() {
  local model="$1" effort="$2" task="$3" prompt
  case "$task" in
    reason) prompt="$REASON_PROMPT" ;;
    prose)  prompt="$PROSE_PROMPT" ;;
  esac
  local out="result_${task}_${model}_${effort}.json"
  local args=(-p "$prompt" --model "$model" --output-format json --tools "" --strict-mcp-config --mcp-config '{"mcpServers":{}}')
  if [ "$effort" != "none" ]; then
    args+=(--effort "$effort")
  fi
  "$CLAUDE" "${args[@]}" > "$out" 2> "${out%.json}.err"
  echo "done: $out"
}
export -f run_one 2>/dev/null || true

# Build run list: task model effort
RUNS=()
for m in fable opus sonnet; do
  for e in low medium high xhigh max; do
    RUNS+=("reason $m $e")
  done
done
RUNS+=("reason haiku none")
RUNS+=("reason haiku low")   # expected: effort unsupported on haiku — record what happens
for m in fable opus sonnet; do
  RUNS+=("prose $m low")
done
RUNS+=("prose haiku none")

# Simple concurrency pool of 5
MAX_JOBS=5
for spec in "${RUNS[@]}"; do
  set -- $spec
  task="$1"; model="$2"; effort="$3"
  while [ "$(jobs -rp | wc -l)" -ge "$MAX_JOBS" ]; do sleep 2; done
  run_one "$model" "$effort" "$task" &
done
wait
echo "ALL RUNS COMPLETE"
