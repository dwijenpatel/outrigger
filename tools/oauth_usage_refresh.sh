#!/bin/sh
# OAuth-usage refresher — the desktop-workflow live rung (I13/P2-8).
#
# The statusline shim can only fire in terminal CLI sessions; desktop-app
# workflows have NO statusline surface, so this operator-started loop keeps
# the governor's OAuth rung continuously fresh instead:
#
#   tools/oauth_usage_refresh.sh [outfile] [interval_s]
#   # e.g. against a pilot repo, from any terminal:
#   #   tools/oauth_usage_refresh.sh /path/to/pilot/state/oauth-usage.json
#
# Interval defaults to 300s — half the governor's 600s staleness ceiling, so
# the rung never goes stale between refreshes. The token is read ONCE from
# the macOS Keychain if CLAUDE_OAUTH_TOKEN is unset (the OS permission prompt
# is the operator ack); it lives only in this process, never in files or the
# firing session's environment. Ctrl-C to stop; a failed fetch is a warning —
# the governor falls through per the ladder when the file stales.
set -eu

OUT="${1:-state/oauth-usage.json}"
INTERVAL="${2:-300}"

if [ -z "${CLAUDE_OAUTH_TOKEN:-}" ]; then
  CLAUDE_OAUTH_TOKEN=$(security find-generic-password -s "Claude Code-credentials" -w \
    | python3 -c "import json,sys; print(json.load(sys.stdin)['claudeAiOauth']['accessToken'])")
fi
export CLAUDE_OAUTH_TOKEN

mkdir -p "$(dirname "$OUT")"
echo "refreshing $OUT every ${INTERVAL}s — Ctrl-C to stop" >&2
while :; do
  if "$(dirname "$0")/oauth_usage_fetch.sh" > "$OUT.tmp" 2>/dev/null; then
    mv "$OUT.tmp" "$OUT"
    echo "$(date '+%H:%M:%S') refreshed" >&2
  else
    rm -f "$OUT.tmp"
    echo "$(date '+%H:%M:%S') fetch failed — governor falls through when the file stales" >&2
  fi
  sleep "$INTERVAL"
done
