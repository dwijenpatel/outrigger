#!/bin/sh
# OAuth-usage fetch — operator-side wrapper for the governor's fallback rung
# (design §5.1; UNSTABLE INTERNAL ENDPOINT, community-documented only).
#
# Credentials are deliberately NOT auto-discovered: probed 2026-07-04, they are
# not non-interactively accessible on every environment, and silently reading
# auth stores is not this script's business. The operator supplies the token:
#
#   CLAUDE_OAUTH_TOKEN=$(...) tools/oauth_usage_fetch.sh > state/oauth-usage.json
#
# Output: raw endpoint JSON on stdout (harness.governor.read_oauth_usage parses
# it). Exit 1 on any failure — callers fall through to the estimate rung.
set -eu

if [ -z "${CLAUDE_OAUTH_TOKEN:-}" ]; then
  echo "oauth_usage_fetch: set CLAUDE_OAUTH_TOKEN (operator-supplied)" >&2
  exit 1
fi

exec curl -sf -m 15 \
  -H "Authorization: Bearer ${CLAUDE_OAUTH_TOKEN}" \
  -H "anthropic-beta: oauth-2025-04-20" \
  "https://api.anthropic.com/api/oauth/usage"
