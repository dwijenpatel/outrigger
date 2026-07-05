#!/bin/sh
# Best-effort operator notification (I21, P3v2-1): a firing that needs a human
# decision must not depend on the operator happening to look at a terminal —
# pilot-3-v2 sat 8h25m on an unnoticed interactive prompt.
#
# Usage: tools/notify_operator.sh "<message>" ["<title>"]
#
# Always exits 0 (notification is a courtesy, never a gate). Emits a terminal
# bell + stderr line everywhere; on macOS additionally posts a desktop
# notification via osascript.
MSG="${1:-operator decision needed}"
TITLE="${2:-harness firing}"

printf '\a' 2>/dev/null || true
printf '[notify] %s: %s\n' "$TITLE" "$MSG" >&2 || true

if [ "$(uname -s 2>/dev/null)" = "Darwin" ] && command -v osascript >/dev/null 2>&1; then
    # Single-quote for AppleScript; strip embedded double quotes and
    # backslashes so arbitrary card text cannot break out of the literal.
    SAFE_MSG=$(printf '%s' "$MSG" | tr -d '"\\')
    SAFE_TITLE=$(printf '%s' "$TITLE" | tr -d '"\\')
    osascript -e "display notification \"$SAFE_MSG\" with title \"$SAFE_TITLE\" sound name \"Submarine\"" >/dev/null 2>&1 || true
fi

exit 0
