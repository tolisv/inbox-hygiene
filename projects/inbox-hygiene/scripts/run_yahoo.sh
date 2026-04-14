#!/usr/bin/env bash
# Wrapper to run the email hygiene script.
# All arguments are forwarded to email_review.py.
#
# Usage:
#   ./email_review.sh                   # normal run
#   ./email_review.sh --dry-run         # report-only, no changes
#   ./email_review.sh --dry-run --days 90
#   ./email_review.sh --min-age-delete 14 --min-age-archive 3
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT_DIR=$(cd "$SCRIPT_DIR/.." && pwd)

# Ensure data directory exists
DATA_DIR="$ROOT_DIR/data"
if [[ ! -d "$DATA_DIR" ]]; then
  mkdir -p "$DATA_DIR"
  chmod 700 "$DATA_DIR"
fi
[[ -f "$DATA_DIR/senders.json" ]] || echo '{}' > "$DATA_DIR/senders.json"
[[ -f "$DATA_DIR/state.json" ]]   || echo '{}' > "$DATA_DIR/state.json"
[[ -f "$DATA_DIR/for_summary.txt" ]] || touch "$DATA_DIR/for_summary.txt"

# Load IMAP credentials
CRED_FILE="$SCRIPT_DIR/email_creds.env"
if [[ -f "$CRED_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$CRED_FILE"
  set +a
else
  echo "Warning: email_creds.env not found; ensure IMAP_USER and IMAP_PASS are set." >&2
fi

exec python3 "$SCRIPT_DIR/email_review.py" "$@"
