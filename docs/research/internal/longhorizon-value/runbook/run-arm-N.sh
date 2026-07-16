#!/bin/zsh
# run-arm-N.sh — the diligent-ungated Sonnet control. SPENDS QUOTA (~11 Sonnet
# sessions). Pass --yes (or --dry-run first, free).
HERE="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$HERE/null_arm_runner.py" --arm N --model claude-sonnet-5 \
  --repo "${ARM_N_REPO:-$HOME/repos/eaitl-arm-N}" "$@"
