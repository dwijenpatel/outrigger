#!/bin/zsh
# run-arm-F.sh — the frontier-solo control (Opus 4.8, ungated). SPENDS QUOTA
# (~11 Opus sessions ≈ the gated arm's whole budget — that is the point:
# budget-neutral). Pass --yes (or --dry-run first, free).
HERE="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$HERE/null_arm_runner.py" --arm F --model claude-opus-4-8 \
  --repo "${ARM_F_REPO:-$HOME/repos/eaitl-arm-F}" "$@"
