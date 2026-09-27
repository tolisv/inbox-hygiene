#!/usr/bin/env bash
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

if [[ $# -lt 1 || ( "$1" != "gmail" && "$1" != "yahoo" ) ]]; then
    echo "Usage: $0 gmail|yahoo [wrapper options]" >&2
    exit 2
fi

ACCOUNT="$1"
shift
STARTED_AT="$(date +%s)"
WRAPPER="$SCRIPT_DIR/run_${ACCOUNT}.sh"
DATA_DIR="$PROJECT_DIR/data/$ACCOUNT"

"$WRAPPER" \
    --classifier jev \
    --classifier-content cleaned \
    "$@"
RUN_STATUS=$?

NOTIFY_ARGS=(
    "$ACCOUNT"
    --exit-code "$RUN_STATUS"
    --started-at "$STARTED_AT"
    --data-dir "$DATA_DIR"
)
if [[ " ${*} " == *" --dry-run "* ]]; then
    NOTIFY_ARGS+=(--dry-run)
fi

"$PROJECT_DIR/.venv/bin/python3" "$SCRIPT_DIR/notify_digest.py" "${NOTIFY_ARGS[@]}"
NOTIFY_STATUS=$?
if [[ $NOTIFY_STATUS -ne 0 ]]; then
    echo "Warning: Telegram notification failed with code $NOTIFY_STATUS" >&2
fi

if [[ $RUN_STATUS -ne 0 ]]; then
    exit "$RUN_STATUS"
fi
exit "$NOTIFY_STATUS"
