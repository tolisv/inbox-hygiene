# Daily Email Review Automation

This directory contains scripts to automate daily review of your Yahoo email inbox, including message classification, deletion, and summary extraction for later processing.

## Components

- **email_review.py**: Python script that:
  1. Loads IMAP credentials from environment variables (via `email_creds.env`).
  2. Connects to Yahoo IMAP and fetches unique senders of messages in the last 90 days using batched header fetches.
  3. Maintains `data/senders.json` mapping senders to a classification: `delete`, `summarize`, or `keep`.
  4. In interactive mode, prompts for any new senders to classify them. In non-interactive mode (e.g. cron), defers unclassified senders to `data/state.json` for later review.
  5. Automatically deletes all messages from `delete`-classified senders (no confirmation prompt).
  6. For `summarize` senders, fetches new message bodies (plain text only, stripping link lines) and appends them to `data/for_summary.txt`.
  7. Messages from `keep` senders are left untouched.
  8. Tracks the last-processed message UID in `data/state.json` to avoid re-summarizing.

- **email_review.sh**: Shell wrapper that sets up the `data/` directory (with secure permissions), initializes state files if missing, loads credentials from `email_creds.env`, and invokes the Python script.

- **email_creds.env**: (Not version-controlled) Environment file containing your IMAP login credentials. See below.

## Setup

1. **Ensure Python 3 is installed** (no additional packages required).
2. **Create your credentials file** at `scripts/email_creds.env` (this file should _not_ be committed to version control):
   ```bash
   IMAP_USER="your_yahoo_email_address"
   IMAP_PASS="your_app_password_or_token"
   # Optionally override defaults:
   # IMAP_HOST="imap.mail.yahoo.com"
   # IMAP_PORT="993"
   ```
3. **Make the shell wrapper executable** (if not already):
   ```bash
   chmod +x scripts/email_review.sh
   ```

## Usage

Run the wrapper script manually:
```bash
scripts/email_review.sh
```

- The first time you run interactively, for each new sender you will see a preview of their most recent email (subject and snippet) and be prompted to classify the sender as **d**elete, **s**ummarize, or **k**eep.
- All messages from `delete` senders are automatically deleted and expunged.
- Messages from `summarize` senders (newer than last run) are appended to `data/for_summary.txt`.
- Messages from `keep` senders are left in the inbox.

### Non-interactive mode

When run without a tty (e.g. from cron), new unclassified senders are saved to `data/state.json` under `pending_senders` instead of prompting. The next interactive run or manual review can classify them.

## Data files

- `senders.json` — sender classification map (`delete` / `summarize` / `keep`)
- `state.json` — `last_uid` (last processed UID) and optionally `pending_senders` (deferred from non-interactive runs)
- `for_summary.txt` — accumulated message texts for summarization

## Cron Job Integration

To automate daily runs, add an entry to your crontab. For example, to run every day at 7:00 AM:

```cron
0 7 * * * /path/to/your/workspace/scripts/email_review.sh >> /path/to/your/workspace/data/email_review.log 2>&1
```

Be sure the cron environment can access your `email_creds.env` (absolute paths recommended) and that the workspace directory permissions allow execution.
