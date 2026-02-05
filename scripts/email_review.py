#!/usr/bin/env python3
"""
Daily Email Review Automation Script

Loads IMAP credentials, fetches recent senders, maintains classification map,
prompts for new senders, deletes or summarizes messages accordingly,
and tracks state between runs.
"""
import os
import sys
import imaplib
import email
import json
from datetime import datetime, timedelta, timezone
from email.utils import parseaddr, parsedate_to_datetime

# Configuration
def main():
    # Determine paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.abspath(os.path.join(script_dir, '..'))
    data_dir = os.path.join(root_dir, 'data')
    senders_file = os.path.join(data_dir, 'senders.json')
    state_file = os.path.join(data_dir, 'state.json')
    summary_file = os.path.join(data_dir, 'for_summary.txt')

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

    # Get IMAP credentials from environment
    IMAP_HOST = os.getenv('IMAP_HOST', 'imap.mail.yahoo.com')
    IMAP_PORT = int(os.getenv('IMAP_PORT', '993'))
    IMAP_USER = os.getenv('IMAP_USER')
    IMAP_PASS = os.getenv('IMAP_PASS')
    if not IMAP_USER or not IMAP_PASS:
        print('Error: IMAP_USER and IMAP_PASS must be set in environment.', file=sys.stderr)
        sys.exit(1)

    # Connect to IMAP
    mail = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
    mail.login(IMAP_USER, IMAP_PASS)
    mail.select('INBOX')

    # Fetch UIDs since 90 days ago
    cutoff = (datetime.now(timezone.utc) - timedelta(days=90)).strftime('%d-%b-%Y')
    result, data = mail.uid('SEARCH', None, f'(SINCE {cutoff})')
    if result != 'OK':
        print('Error searching mailbox:', result, file=sys.stderr)
        sys.exit(1)
    uid_list = data[0].split()

    # Gather senders and message dates
    messages = []
    unique_senders = set()
    for uid_bytes in uid_list:
        uid = uid_bytes.decode()
        res, msg_data = mail.uid('FETCH', uid, '(BODY.PEEK[HEADER.FIELDS (FROM DATE)])')
        if res != 'OK':
            continue
        header = msg_data[0][1].decode('utf-8', errors='ignore')
        msg = email.message_from_string(header)
        addr = parseaddr(msg.get('From'))[1].lower()
        try:
            dt = parsedate_to_datetime(msg.get('Date'))
        except Exception:
            dt = None
        messages.append({'uid': int(uid), 'sender': addr, 'date': dt})
        unique_senders.add(addr)

    # Prompt classification for new senders
    updated = False
    for sender in sorted(unique_senders):
        if sender in senders_map:
            continue
        while True:
            resp = input(f'Classify sender {sender} ([d]elete / [s]ummarize): ').strip().lower()
            if resp in ('d', 'delete'):
                senders_map[sender] = 'delete'
                break
            elif resp in ('s', 'summarize'):
                senders_map[sender] = 'summarize'
                break
            else:
                print('Please enter "d" or "s".')
        updated = True
    if updated:
        with open(senders_file, 'w') as f:
            json.dump(senders_map, f, indent=2)

    # Sort messages by UID
    messages.sort(key=lambda x: x['uid'])

    # Process deletions and summarizations for new messages
    max_uid = last_uid
    # Prepare summary file
    summary_fh = open(summary_file, 'a', encoding='utf-8')

    for msg in messages:
        uid = msg['uid']
        sender = msg['sender']
        date = msg['date']
        if uid <= last_uid:
            continue
        max_uid = max(max_uid, uid)
        classification = senders_map.get(sender)
        if classification == 'delete':
            # Fetch subject for display
            res, hdr = mail.uid('FETCH', str(uid), '(BODY.PEEK[HEADER.FIELDS (SUBJECT DATE)])')
            if res != 'OK':
                continue
            hdr_txt = hdr[0][1].decode('utf-8', errors='ignore')
            hdr_msg = email.message_from_string(hdr_txt)
            subj = hdr_msg.get('Subject', '').strip()
            print(f"Message UID {uid} from {sender} on {date}: {subj}")
            c = input('Delete? ([y]/n): ').strip().lower()
            if c in ('', 'y', 'yes'):
                mail.uid('STORE', str(uid), '+FLAGS', r'(\\Deleted)')
        elif classification == 'summarize':
            # Fetch full message
            res, full = mail.uid('FETCH', str(uid), '(RFC822)')
            if res != 'OK':
                continue
            raw = full[0][1]
            parsed = email.message_from_bytes(raw)
            # Get plain-text parts
            body = ''
            if parsed.is_multipart():
                for part in parsed.walk():
                    if part.get_content_type() == 'text/plain' and not part.get_content_disposition():
                        try:
                            body += part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8', errors='ignore')
                        except Exception:
                            pass
            else:
                try:
                    body = parsed.get_payload(decode=True).decode(parsed.get_content_charset() or 'utf-8', errors='ignore')
                except Exception:
                    pass
            # Strip links
            body = '\n'.join(line for line in body.splitlines() if 'http://' not in line and 'https://' not in line)
            # Write to summary file
            summary_fh.write(f'---\nSender: {sender}\nDate: {date}\nSubject: {parsed.get("Subject","")}\n\n')
            summary_fh.write(body.strip() + '\n\n')

    summary_fh.close()

    # Expunge deletions
    mail.expunge()
    mail.logout()

    # Update state
    state['last_uid'] = max_uid
    with open(state_file, 'w') as f:
        json.dump(state, f, indent=2)

    print('Email review complete.')

if __name__ == '__main__':
    main()
