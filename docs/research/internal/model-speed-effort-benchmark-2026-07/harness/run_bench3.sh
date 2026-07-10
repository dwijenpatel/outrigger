#!/bin/bash
# Round 3: coding tasks at xhigh effort, 3 reps per cell
cd "$(dirname "$0")"
BENCH="$(pwd)"
CLAUDE="$HOME/.local/bin/claude"

GEN_PROMPT='Write a Python module implementing exactly one function:

    evaluate(expr: str) -> float

It evaluates arithmetic expressions with these rules:
- Operators: + - * / ** and parentheses; unary minus (possibly nested like -(-3)).
- Standard precedence; ** is right-associative and binds tighter than unary minus, so -2**2 == -4, (-2)**2 == 4, 2**-1 == 0.5, 2**3**2 == 512.
- Integer and decimal literals; whitespace anywhere is ignored.
- Division is float division; 1/0 must raise ZeroDivisionError.
- Malformed input (empty string, trailing operators, unbalanced parentheses, illegal characters) must raise ValueError.
- Do not use eval/exec/ast.

Output ONLY the raw Python source code of the module. No markdown fences, no commentary.'

FIX_PROMPT='This directory contains wordwrap.py (implementation, with a spec in its docstring) and test_wordwrap.py (test suite). Run the tests, find and fix all bugs in wordwrap.py so that the entire suite passes. Do not modify test_wordwrap.py. When all tests pass, reply with a one-line summary of the bugs you fixed.'

run_gen() {
  local model="$1" effort="$2" rep="$3"
  local out="$BENCH/result3_gen_${model}_r${rep}.json"
  local args=(-p "$GEN_PROMPT" --model "$model" --output-format json --tools "" --strict-mcp-config --mcp-config '{"mcpServers":{}}')
  [ "$effort" != "none" ] && args+=(--effort "$effort")
  ( cd "$BENCH" && "$CLAUDE" "${args[@]}" > "$out" 2> "${out%.json}.err" )
  echo "done: $(basename "$out")"
}

run_fix() {
  local model="$1" effort="$2" rep="$3"
  local ws="$BENCH/ws_fix_${model}_r${rep}"
  rm -rf "$ws" && cp -r "$BENCH/fixtures/fixws" "$ws"
  local out="$BENCH/result3_fix_${model}_r${rep}.json"
  local args=(-p "$FIX_PROMPT" --model "$model" --output-format json \
    --strict-mcp-config --mcp-config '{"mcpServers":{}}' \
    --allowedTools "Bash(python3:*)" "Bash(python:*)" "Bash(pytest:*)" "Edit" "Read" "Write" "Glob" "Grep")
  [ "$effort" != "none" ] && args+=(--effort "$effort")
  ( cd "$ws" && "$CLAUDE" "${args[@]}" > "$out" 2> "${out%.json}.err" )
  echo "done: $(basename "$out")"
}

RUNS=()
for rep in 1 2 3; do
  for m in "fable xhigh" "opus xhigh" "sonnet xhigh" "haiku none"; do
    RUNS+=("gen $m $rep")
    RUNS+=("fix $m $rep")
  done
done

MAX_JOBS=4
for spec in "${RUNS[@]}"; do
  set -- $spec
  task="$1"; model="$2"; effort="$3"; rep="$4"
  while [ "$(jobs -rp | wc -l)" -ge "$MAX_JOBS" ]; do sleep 2; done
  if [ "$task" = "gen" ]; then
    run_gen "$model" "$effort" "$rep" &
  else
    run_fix "$model" "$effort" "$rep" &
  fi
done
wait
echo "ALL ROUND3 RUNS COMPLETE"
