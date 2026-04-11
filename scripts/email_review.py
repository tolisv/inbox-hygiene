#!/usr/bin/env python3
"""
Daily Email Review Automation Script

Loads IMAP credentials, fetches recent senders via batched header fetches,
maintains classification map, prompts for new senders only, deletes or
summarizes messages accordingly, and tracks state between runs.
"""
import os
import sys
import imaplib
import email
import json
import re
import time
from datetime import datetime, timedelta, timezone
from email.utils import parseaddr, parsedate_to_datetime

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def atomic_write_json(path, data):
    """Write JSON atomically: write to .tmp then os.replace."""
    tmp = path + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(data, f, indent=2)
        f.write('\n')
    os.replace(tmp, path)


class ImapConn:
    """Thin wrapper around imaplib.IMAP4_SSL with auto-reconnect on abort."""

    def __init__(self, host, port, user, password):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self._conn = None
        self._connect()

    def _connect(self):
        self._conn = imaplib.IMAP4_SSL(self.host, self.port)
        self._conn.login(self.user, self.password)
        self._conn.select('INBOX')

    def cmd(self, method, *args, **kwargs):
        """Run an IMAP command, reconnecting once on abort / EOF."""
        for attempt in range(2):
            try:
                fn = getattr(self._conn, method)
                return fn(*args, **kwargs)
            except (imaplib.IMAP4.abort, imaplib.IMAP4.error,
                    ConnectionError, OSError) as e:
                if attempt == 0:
                    print(f"  IMAP error ({e}), reconnecting…",
                          file=sys.stderr)
                    time.sleep(1)
                    self._connect()
                else:
                    raise

    def uid(self, *args, **kwargs):
        return self.cmd('uid', *args, **kwargs)

    def expunge(self):
        return self.cmd('expunge')

    def logout(self):
        try:
            self._conn.logout()
        except Exception:
            pass


UID_RE = re.compile(rb'UID (\d+)')


def batch_fetch_headers(imap, uid_list, batch_size=50):
    """Fetch FROM+DATE headers in batches. Returns list of (uid, sender, date)."""
    results = []
    total = len(uid_list)
    for i in range(0, total, batch_size):
        batch = uid_list[i:i + batch_size]
        uid_set = b','.join(batch)
        res, data = imap.uid(
            'FETCH', uid_set,
            '(UID BODY.PEEK[HEADER.FIELDS (FROM DATE)])')
        if res != 'OK':
            continue
        # data is a flat list: [ (envelope, header_bytes), b')', ... ]
        j = 0
        while j < len(data):
            item = data[j]
            if isinstance(item, tuple) and len(item) == 2:
                envelope, header_bytes = item
                m = UID_RE.search(envelope)
                if m:
                    uid = int(m.group(1))
                    hdr = header_bytes.decode('utf-8', errors='ignore')
                    msg = email.message_from_string(hdr)
                    addr = parseaddr(msg.get('From', ''))[1].lower()
                    try:
                        dt = parsedate_to_datetime(msg.get('Date'))
                    except Exception:
                        dt = None
                    results.append((uid, addr, dt))
            j += 1
        done = min(i + batch_size, total)
        print(f"\r  Fetched headers: {done}/{total}", end='', flush=True)
    if total:
        print()  # newline after progress
    return results


def fetch_preview(imap, uid):
    """Fetch subject + short body snippet for a single UID."""
    res, hdr = imap.uid(
        'FETCH', str(uid),
        '(BODY.PEEK[HEADER.FIELDS (SUBJECT DATE)])')
    subj = ''
    if res == 'OK' and hdr and hdr[0] and isinstance(hdr[0], tuple):
        hdr_txt = hdr[0][1].decode('utf-8', errors='ignore')
        hdr_msg = email.message_from_string(hdr_txt)
        subj = hdr_msg.get('Subject', '').strip()

    snippet = ''
    res, body_data = imap.uid('FETCH', str(uid), '(BODY.PEEK[TEXT]<0.1024>)')
    if (res == 'OK' and body_data and body_data[0]
            and isinstance(body_data[0], tuple)):
        try:
            raw = body_data[0][1].decode('utf-8', errors='ignore')
            snippet = '\n'.join(raw.splitlines()[:5])
        except Exception:
            pass
    return subj, snippet


def batched_store_deleted(imap, uid_ints, batch_size=50):
    """Mark UIDs as \\Deleted in batches."""
    total = len(uid_ints)
    for i in range(0, total, batch_size):
        batch = uid_ints[i:i + batch_size]
        uid_set = ','.join(str(u) for u in batch)
        imap.uid('STORE', uid_set, '+FLAGS', r'(\Deleted)')
        done = min(i + batch_size, total)
        print(f"\r  Flagged for deletion: {done}/{total}", end='', flush=True)
    if total:
        print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.abspath(os.path.join(script_dir, '..'))
    data_dir = os.path.join(root_dir, 'data')
    senders_file = os.path.join(data_dir, 'senders.json')
    state_file = os.path.join(data_dir, 'state.json')
    summary_file = os.path.join(data_dir, 'for_summary.txt')
    interactive = sys.stdin.isatty()

    os.makedirs(data_dir, exist_ok=True)

    # Load classification mapping
    if os.path.exists(senders_file):
        with open(senders_file, 'r') as f:
            senders_map = json.load(f)
    else:
        senders_map = {}

    # Load state
    if os.path.exists(state_file):
        with open(state_file, 'r') as f:
            state = json.load(f)
    else:
        state = {}
    last_uid = state.get('last_uid', 0)

    # Credentials
    IMAP_HOST = os.getenv('IMAP_HOST', 'imap.mail.yahoo.com')
    IMAP_PORT = int(os.getenv('IMAP_PORT', '993'))
    IMAP_USER = os.getenv('IMAP_USER')
    IMAP_PASS = os.getenv('IMAP_PASS')
    if not IMAP_USER or not IMAP_PASS:
        print('Error: IMAP_USER and IMAP_PASS must be set in environment.',
              file=sys.stderr)
        sys.exit(1)

    imap = ImapConn(IMAP_HOST, IMAP_PORT, IMAP_USER, IMAP_PASS)

    # Search for messages in the last 90 days
    cutoff = (datetime.now(timezone.utc) - timedelta(days=90)).strftime('%d-%b-%Y')
    print(f"Searching for messages since {cutoff}…")
    res, data = imap.uid('SEARCH', None, f'(SINCE {cutoff})')
    if res != 'OK':
        print('Error searching mailbox:', res, file=sys.stderr)
        sys.exit(1)
    uid_list = data[0].split() if data[0] else []
    print(f"  Found {len(uid_list)} messages")

    if not uid_list:
        print("No messages to process.")
        imap.logout()
        return

    # ---- Phase 1: Batch-fetch headers ----------------------------------
    print("Fetching headers…")
    messages = batch_fetch_headers(imap, uid_list)
    # messages: list of (uid, sender, date)

    # Build per-sender info: latest UID for preview
    sender_latest = {}  # sender -> (uid, date)
    for uid, sender, dt in messages:
        if sender not in sender_latest or uid > sender_latest[sender][0]:
            sender_latest[sender] = (uid, dt)

    new_senders = sorted(s for s in sender_latest if s and s not in senders_map)
    print(f"  Unique senders: {len(sender_latest)}, "
          f"already classified: {len(sender_latest) - len(new_senders)}, "
          f"new: {len(new_senders)}")

    # ---- Phase 2: Classify new senders ---------------------------------
    pending_senders = []
    if new_senders:
        if interactive:
            print(f"\nClassify {len(new_senders)} new sender(s):\n")
        else:
            print(f"\nSkipping {len(new_senders)} new sender(s) in non-interactive mode.")
    for idx, sender in enumerate(new_senders, 1):
        latest_uid, latest_dt = sender_latest[sender]
        # Fetch preview only for new senders
        subj, snippet = fetch_preview(imap, latest_uid)
        print(f"[{idx}/{len(new_senders)}] {sender}")
        print(f"  Latest (UID {latest_uid}, {latest_dt}): {subj}")
        if snippet:
            for line in snippet.splitlines():
                print(f"  | {line}")

        if not interactive:
            pending_senders.append({
                'sender': sender,
                'latest_uid': latest_uid,
                'latest_date': latest_dt.isoformat() if latest_dt else None,
                'subject': subj,
            })
            print('  Deferred classification (non-interactive mode).\n')
            continue

        while True:
            resp = input('  [d]elete / [s]ummarize / [k]eep? ').strip().lower()
            if resp in ('d', 'delete'):
                senders_map[sender] = 'delete'
                break
            elif resp in ('s', 'summarize'):
                senders_map[sender] = 'summarize'
                break
            elif resp in ('k', 'keep'):
                senders_map[sender] = 'keep'
                break
            else:
                print('  Please enter d, s, or k.')
        # Save after each classification so progress survives crashes
        atomic_write_json(senders_file, senders_map)
        print()

    # ---- Phase 3: Delete ALL messages from "delete" senders ------------
    delete_senders = {s for s, c in senders_map.items() if c == 'delete'}
    delete_uids = [uid for uid, sender, _ in messages if sender in delete_senders]
    if delete_uids:
        print(f"Deleting {len(delete_uids)} message(s) from "
              f"{len(delete_senders)} delete-classified sender(s)…")
        batched_store_deleted(imap, delete_uids)
        imap.expunge()
        print("  Expunged.")
    else:
        print("No messages to delete.")

    # ---- Phase 4: Summarize NEW messages (uid > last_uid) ---------------
    summarize_senders = {s for s, c in senders_map.items() if c == 'summarize'}
    new_summarize = [(uid, sender, dt) for uid, sender, dt in messages
                     if uid > last_uid and sender in summarize_senders]
    new_summarize.sort(key=lambda x: x[0])

    if new_summarize:
        print(f"Appending {len(new_summarize)} message(s) to for_summary.txt…")
        with open(summary_file, 'a', encoding='utf-8') as fh:
            for uid, sender, dt in new_summarize:
                res, full = imap.uid('FETCH', str(uid), '(RFC822)')
                if res != 'OK':
                    continue
                raw = full[0][1]
                parsed = email.message_from_bytes(raw)
                body = ''
                if parsed.is_multipart():
                    for part in parsed.walk():
                        ct = part.get_content_type()
                        cd = part.get_content_disposition()
                        if ct == 'text/plain' and not cd:
                            try:
                                body += part.get_payload(
                                    decode=True).decode(
                                    part.get_content_charset() or 'utf-8',
                                    errors='ignore')
                            except Exception:
                                pass
                else:
                    try:
                        body = parsed.get_payload(
                            decode=True).decode(
                            parsed.get_content_charset() or 'utf-8',
                            errors='ignore')
                    except Exception:
                        pass
                # Strip link-only lines
                body = '\n'.join(
                    line for line in body.splitlines()
                    if 'http://' not in line and 'https://' not in line)
                fh.write(f'---\nSender: {sender}\nDate: {dt}\n'
                         f'Subject: {parsed.get("Subject","")}\n\n')
                fh.write(body.strip() + '\n\n')
        print("  Done.")
    else:
        print("No new messages to summarize.")

    # ---- Phase 5: Save state -------------------------------------------
    max_uid = max(uid for uid, _, _ in messages)
    state['last_uid'] = max_uid
    if pending_senders:
        state['pending_senders'] = pending_senders
    else:
        state.pop('pending_senders', None)
    atomic_write_json(state_file, state)
    print(f"State saved (last_uid={max_uid}).")
    if pending_senders:
        print(f"Pending classification for {len(pending_senders)} sender(s).")

    imap.logout()
    print("Email review complete.")


if __name__ == '__main__':
    main()
