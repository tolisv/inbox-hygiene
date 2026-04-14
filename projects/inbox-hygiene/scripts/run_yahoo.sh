#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DATA_DIR="$PROJECT_DIR/data/yahoo"
CREDS_FILE="$SCRIPT_DIR/email_creds.env"

if [[ ! -f "$CREDS_FILE" ]]; then
    echo "Error: credentials file not found: $CREDS_FILE" >&2
    exit 1
fi

source "$CREDS_FILE"

mkdir -p "$DATA_DIR"
chmod 700 "$DATA_DIR"

if [[ ! -f "$DATA_DIR/state.json" ]]; then
    echo '{"last_uid": 0}' > "$DATA_DIR/state.json"
fi

if [[ ! -f "$DATA_DIR/senders.json" ]]; then
    echo '{}' > "$DATA_DIR/senders.json"
fi

exec python3 "$SCRIPT_DIR/email_review.py" \
    --data-dir "$DATA_DIR" \
    --account "yahoo" \
    "$@"
