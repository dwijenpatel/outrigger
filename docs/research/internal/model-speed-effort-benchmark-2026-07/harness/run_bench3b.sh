#!/bin/bash
# Round 3b: HARD coding task (mini regex engine) at xhigh, 3 reps
cd "$(dirname "$0")"
BENCH="$(pwd)"
CLAUDE="$HOME/.local/bin/claude"

HARD_PROMPT='Write a Python module implementing exactly one function:

    match(pattern: str, text: str) -> bool

It returns True if and only if the ENTIRE text matches the pattern (full-match semantics, like re.fullmatch). Supported pattern syntax:
- literal characters
- "." matches any single character
- quantifiers "*" (zero or more), "+" (one or more), "?" (zero or one), applying to the preceding literal, ".", character class, or group
- grouping with "(" ")", which can be quantified, e.g. "(ab)*"
- alternation "|" with the usual low precedence, e.g. "ab|cd" means (ab)|(cd); works inside groups like "a(b|c)d"
- character classes "[abc]", ranges "[a-z0-9]", and negation "[^ab]"
- the empty pattern matches only the empty text

You may assume the pattern is well-formed. No backreferences, no escapes, no anchors. Correct backtracking behavior is required (e.g. "a*a" must match "aaa"; "(a|b)*abb" must match "aababb").

Do NOT import anything; do not use the re module.

Output ONLY the raw Python source code of the module. No markdown fences, no commentary.'

run_one() {
  local model="$1" effort="$2" rep="$3"
  local out="$BENCH/result3_hard_${model}_r${rep}.json"
  local args=(-p "$HARD_PROMPT" --model "$model" --output-format json --tools "" --strict-mcp-config --mcp-config '{"mcpServers":{}}')
  [ "$effort" != "none" ] && args+=(--effort "$effort")
  "$CLAUDE" "${args[@]}" > "$out" 2> "${out%.json}.err"
  echo "done: $(basename "$out")"
}

RUNS=()
for rep in 1 2 3; do
  for m in "fable xhigh" "opus xhigh" "sonnet xhigh" "haiku none"; do
    RUNS+=("$m $rep")
  done
done

MAX_JOBS=4
for spec in "${RUNS[@]}"; do
  set -- $spec
  model="$1"; effort="$2"; rep="$3"
  while [ "$(jobs -rp | wc -l)" -ge "$MAX_JOBS" ]; do sleep 2; done
  run_one "$model" "$effort" "$rep" &
done
wait
echo "ALL ROUND3B RUNS COMPLETE"
