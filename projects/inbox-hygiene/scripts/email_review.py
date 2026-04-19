#!/usr/bin/env python3
"""
Email Hygiene Script - Yahoo IMAP

Five-category classification with:
  - Dry-run / report-only mode (--dry-run)
  - Subject keyword override to needs_attention
  - Age-based retention rules (--min-age-delete, --min-age-archive)
  - Archive action: IMAP COPY to Archive folder + delete from INBOX
  - Needs-attention flagging: marks messages as \\Flagged in IMAP
  - Action digest appended to data/digest.txt and printed at end
"""

import os
import sys
import imaplib
import email
import json
import re
import time
import argparse
from datetime import datetime, timedelta, timezone
from email.utils import parseaddr, parsedate_to_datetime

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CATEGORIES = ('delete', 'digest', 'keep')

LEGACY_CATEGORY_MAP = {
    'keep_never_auto': 'keep',
    'needs_attention': 'keep',
    'summarize': 'digest',
    'archive_reference': 'digest',
    'keep': 'keep',      # safety: legacy keep from oldest version
}

# Prompts shown when classifying new senders interactively
CATEGORY_PROMPTS = (
    '[d]elete',
    '[di]gest',
    '[k]eep',
)

# Subject keywords that upgrade any classification to needs_attention.
# Intentionally focused on transactional/operational signals.
# Broad English tech terms (security, alert, reset, payment, code) are
# excluded because they appear as newsletter topics and generate false positives.
ATTENTION_KEYWORDS = [
    # Password / account access
    'senha', 'password',
    # Financial documents
    'fatura', 'invoice',
    'vencimento',
    'comprovante',
    'recibo', 'receipt',
    'cobrança',
    'débito',
    'pagamento',
    # Travel
    'itinerário', 'itinerary',
    'alteração de voo',
    'check-in',
    # Authentication (phrase-level, not single word)
    'verificação', 'verification',
    'autenticação',
    # Security alerts in Portuguese (specific, not generic "security")
    'segurança', 'alerta',
    # Account status changes
    'suspensão', 'bloqueio', 'encerramento',
    'alteração',
    'renovação',
    # Deadlines
    'prazo', 'vencendo',
]


DEFAULT_MIN_AGE_DELETE = 7


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def atomic_write_json(path, data):
    """Write JSON atomically via a temp file."""
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write('\n')
    os.replace(tmp, path)


def age_days(dt):
    """Return message age in days, or None if dt is unknown."""
    if dt is None:
        return None
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (now - dt).days


def is_old_enough(dt, min_days):
    """Return True if message is at least min_days old (unknown age → True)."""
    d = age_days(dt)
    return d is None or d >= min_days


def attention_keywords_in(subject):
    """Return list of ATTENTION_KEYWORDS found in subject.

    Matching uses case-insensitive whole-token/phrase boundaries so short
    keywords like "senha" do not fire on unrelated substrings.
    """
    if not subject:
        return []
    subj_lower = subject.lower()
    matched = []
    for kw in ATTENTION_KEYWORDS:
        pattern = r'(?<!\w)' + re.escape(kw.lower()) + r'(?!\w)'
        if re.search(pattern, subj_lower, flags=re.IGNORECASE):
            matched.append(kw)
    return matched


# ---------------------------------------------------------------------------
# IMAP connection wrapper
# ---------------------------------------------------------------------------

class ImapConn:
    """imaplib.IMAP4_SSL wrapper with auto-reconnect on abort/EOF."""

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
        for attempt in range(2):
            try:
                return getattr(self._conn, method)(*args, **kwargs)
            except (imaplib.IMAP4.abort, imaplib.IMAP4.error,
                    ConnectionError, OSError) as exc:
                if attempt == 0:
                    print(f'  IMAP error ({exc}), reconnecting…', file=sys.stderr)
                    time.sleep(1)
                    self._connect()
                else:
                    raise

    def uid(self, *args, **kwargs):
        return self.cmd('uid', *args, **kwargs)

    def expunge(self):
        return self.cmd('expunge')

    def ensure_folder(self, folder):
        """Create IMAP folder if it does not already exist."""
        res, listing = self._conn.list('""', folder)
        exists = res == 'OK' and any(x is not None for x in (listing or []))
        if not exists:
            self._conn.create(folder)
            print(f'  Created IMAP folder: {folder}')

    def logout(self):
        try:
            self._conn.logout()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Header / body fetching
# ---------------------------------------------------------------------------

UID_RE = re.compile(rb'UID (\d+)')


def batch_fetch_headers(imap, uid_list, batch_size=50):
    """
    Fetch FROM + DATE + SUBJECT headers in batches.
    Returns list of (uid:int, sender:str, subject:str, date:datetime|None).
    """
    results = []
    total = len(uid_list)
    for i in range(0, total, batch_size):
        batch = uid_list[i:i + batch_size]
        uid_set = b','.join(batch)
        res, data = imap.uid(
            'FETCH', uid_set,
            '(UID BODY.PEEK[HEADER.FIELDS (FROM DATE SUBJECT)])')
        if res != 'OK':
            continue
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
                    sender = parseaddr(msg.get('From', ''))[1].lower()
                    subject = msg.get('Subject', '').strip()
                    try:
                        dt = parsedate_to_datetime(msg.get('Date'))
                    except Exception:
                        dt = None
                    results.append((uid, sender, subject, dt))
            j += 1
        print(f'\r  Fetched headers: {min(i + batch_size, total)}/{total}',
              end='', flush=True)
    if total:
        print()
    return results


def fetch_preview(imap, uid):
    """Return (subject, snippet) for a single UID (used during classification)."""
    res, hdr = imap.uid(
        'FETCH', str(uid),
        '(BODY.PEEK[HEADER.FIELDS (SUBJECT DATE)])')
    subj = ''
    if res == 'OK' and hdr and hdr[0] and isinstance(hdr[0], tuple):
        hdr_msg = email.message_from_string(
            hdr[0][1].decode('utf-8', errors='ignore'))
        subj = hdr_msg.get('Subject', '').strip()

    snippet = ''
    res, body_data = imap.uid('FETCH', str(uid), '(BODY.PEEK[TEXT]<0.1024>)')
    if res == 'OK' and body_data and body_data[0] and isinstance(body_data[0], tuple):
        try:
            raw = body_data[0][1].decode('utf-8', errors='ignore')
            snippet = '\n'.join(raw.splitlines()[:5])
        except Exception:
            pass
    return subj, snippet


# ---------------------------------------------------------------------------
# Batch IMAP operations
# ---------------------------------------------------------------------------

def batched_store(imap, uid_ints, flag, label, batch_size=50):
    """Apply an IMAP flag to a list of UIDs in batches."""
    total = len(uid_ints)
    for i in range(0, total, batch_size):
        batch = uid_ints[i:i + batch_size]
        imap.uid('STORE', ','.join(str(u) for u in batch), '+FLAGS', flag)
        print(f'\r  {label}: {min(i + batch_size, total)}/{total}',
              end='', flush=True)
    if total:
        print()



# ---------------------------------------------------------------------------
# Classification and action decision
# ---------------------------------------------------------------------------

def migrate_senders(senders_map):
    """Migrate legacy category names to the 3-category system (delete/digest/keep).
    Returns count of entries migrated."""
    migrated = 0
    for sender, cls in list(senders_map.items()):
        if cls not in CATEGORIES:
            new_cls = LEGACY_CATEGORY_MAP.get(cls)
            if new_cls:
                senders_map[sender] = new_cls
                migrated += 1
    return migrated


def decide_action(sender, subject, dt, senders_map, min_age_delete):
    """
    Determine the action for one message.

    Returns (action, reason, attention, keywords_matched) where action is one of:
        'delete'          – mark \\Deleted + expunge
        'collect_digest'  – append body to for_digest.txt
        'keep'            – no action
        'skip'            – no action (unclassified or too recent)

    attention: True only for 'collect_digest' emails that match attention keywords.
    keywords_matched: list of matched keywords (non-empty only when attention=True).
    """
    classification = senders_map.get(sender)
    if not classification:
        return 'skip', 'unclassified sender', False, []

    if classification == 'keep':
        return 'keep', 'keep — never auto-process', False, []

    if classification == 'delete':
        if not is_old_enough(dt, min_age_delete):
            return 'skip', f'too recent ({age_days(dt)}d < min {min_age_delete}d)', False, []
        return 'delete', f'sender=delete, age={age_days(dt)}d', False, []

    if classification == 'digest':
        matched = attention_keywords_in(subject)
        return 'collect_digest', 'sender=digest', bool(matched), matched

    return 'skip', f'unknown classification: {classification}', False, []


# ---------------------------------------------------------------------------
# Digest
# ---------------------------------------------------------------------------

class Digest:
    """Accumulates action records and writes structured JSON + human-readable report."""

    def __init__(self, account: str):
        self._account = account
        self._total_scanned = 0
        self._buckets = {
            'deleted': [],
            'digest_collected': [],
            'kept': [],
            'skipped': [],
        }
        self._attention_items = []
        self._pending_senders = []

    def set_total_scanned(self, n: int):
        self._total_scanned = n

    def set_pending_senders(self, pending: list):
        self._pending_senders = pending

    def record(self, action: str, sender: str, uid: int, subject: str,
               dt=None, reason: str = '', attention: bool = False,
               keywords_matched: list = None):
        if keywords_matched is None:
            keywords_matched = []
        entry = {
            'uid': uid,
            'sender': sender,
            'subject': (subject or '')[:100],
            'date': dt.isoformat() if dt else None,
        }
        if action == 'delete':
            entry['age_days'] = age_days(dt)
            self._buckets['deleted'].append(entry)
        elif action == 'collect_digest':
            digest_entry = {**entry, 'attention': attention,
                            'keywords_matched': keywords_matched}
            self._buckets['digest_collected'].append(digest_entry)
            if attention:
                self._attention_items.append({**digest_entry, 'category': 'digest'})
        elif action == 'keep':
            self._buckets['kept'].append(entry)
        elif action == 'skip':
            self._buckets['skipped'].append(entry)

    def totals(self):
        return {k: len(v) for k, v in self._buckets.items()}

    def write_json(self, path: str, dry_run: bool) -> dict:
        """Write structured JSON digest (overwrites on each run)."""
        data = {
            'run_at': datetime.now(timezone.utc).isoformat(),
            'dry_run': dry_run,
            'account': self._account,
            'summary': {
                'total_messages_scanned': self._total_scanned,
                'deleted': len(self._buckets['deleted']),
                'digest_collected': len(self._buckets['digest_collected']),
                'kept': len(self._buckets['kept']),
                'skipped': len(self._buckets['skipped']),
                'pending_classification': len(self._pending_senders),
            },
            'attention_items': self._attention_items,
            'pending_senders': self._pending_senders,
            'digest_items': self._buckets['digest_collected'],
            'deleted_items': self._buckets['deleted'],
        }
        atomic_write_json(path, data)
        return data

    def write_txt(self, path: str, dry_run: bool) -> str:
        """Append human-readable digest to path (accumulates across runs)."""
        prefix = '[DRY RUN] ' if dry_run else ''
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        lines = [
            '=' * 60,
            f'Email Hygiene Digest  {prefix}{now}',
            '=' * 60,
            '',
            (f"Scanned: {self._total_scanned} | "
             f"Deleted: {len(self._buckets['deleted'])} | "
             f"Digest: {len(self._buckets['digest_collected'])} | "
             f"Pending: {len(self._pending_senders)}"),
            '',
        ]
        if self._attention_items:
            lines.append(f'### ATTENTION ({len(self._attention_items)})')
            for e in self._attention_items:
                lines.append(f"  [{e['uid']}] {e['sender']}")
                lines.append(f"       {e['subject']}")
                lines.append(f"       Keywords: {', '.join(e['keywords_matched'])}")
            lines.append('')
        if self._pending_senders:
            lines.append(f'### Pending classification ({len(self._pending_senders)})')
            for p in self._pending_senders:
                lines.append(f"  {p['sender']}")
            lines.append('')
        lines.append(f'### Deleted ({len(self._buckets["deleted"])})')
        for e in self._buckets['deleted']:
            lines.append(f"  [{e['uid']}] {e['sender']} ({e.get('age_days', '?')}d)")
        lines.append('')
        lines.append(f'### Digest collected ({len(self._buckets["digest_collected"])})')
        for e in self._buckets['digest_collected']:
            flag = ' [!]' if e.get('attention') else ''
            lines.append(f"  [{e['uid']}] {e['sender']}{flag}")
        lines.append('')
        content = '\n'.join(lines)
        with open(path, 'a', encoding='utf-8') as fh:
            fh.write(content + '\n')
        return content


# ---------------------------------------------------------------------------
# Interactive classification
# ---------------------------------------------------------------------------

def classify_interactively(sender, imap, sender_latest, senders_map, dry_run):
    """Prompt user to classify a sender. Updates senders_map in place."""
    uid, latest_subj, latest_dt = sender_latest[sender]
    subj, snippet = fetch_preview(imap, uid)
    print(f'  Latest (UID {uid}, {latest_dt}): {subj}')
    if snippet:
        for line in snippet.splitlines():
            print(f'  | {line}')

    while True:
        resp = input(
            '  [d]elete / [di]gest / [k]eep? '
        ).strip().lower()
        mapping = {
            'd': 'delete', 'delete': 'delete',
            'di': 'digest', 'dig': 'digest', 'digest': 'digest',
            'k': 'keep', 'keep': 'keep',
        }
        if resp in mapping:
            senders_map[sender] = mapping[resp]
            break
        print('  Please enter d, di, or k.')


# ---------------------------------------------------------------------------
# Summarize: fetch and append full text content
# ---------------------------------------------------------------------------

def collect_digest(imap, to_collect, digest_raw_file):
    """Fetch RFC822 for each message and append plain-text body to digest_raw_file."""
    with open(digest_raw_file, 'a', encoding='utf-8') as fh:
        for uid, sender, subj, dt in to_collect:
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
                            body += part.get_payload(decode=True).decode(
                                part.get_content_charset() or 'utf-8',
                                errors='ignore')
                        except Exception:
                            pass
            else:
                try:
                    body = parsed.get_payload(decode=True).decode(
                        parsed.get_content_charset() or 'utf-8',
                        errors='ignore')
                except Exception:
                    pass
            body = '\n'.join(
                line for line in body.splitlines()
                if 'http://' not in line and 'https://' not in line)
            fh.write(
                f'---\nSender: {sender}\nDate: {dt}\n'
                f'Subject: {parsed.get("Subject", "")}\n\n'
            )
            fh.write(body.strip() + '\n\n')


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(description='Email hygiene — IMAP (3-category)')
    p.add_argument('--dry-run', action='store_true',
                   help='Report-only: plan actions but do not execute them')
    p.add_argument('--days', type=int, default=360,
                   help='Search window in days (default: 360)')
    p.add_argument('--min-age-delete', type=int, default=DEFAULT_MIN_AGE_DELETE,
                   help=f'Min age in days before deleting (default: {DEFAULT_MIN_AGE_DELETE})')
    p.add_argument('--data-dir', default=None,
                   help='Path to account data directory '
                        '(default: <script-dir>/../data/yahoo)')
    p.add_argument('--account', default='yahoo',
                   help='Account name written into digest.json (default: yahoo)')
    return p.parse_args()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    args = parse_args()
    dry_run = args.dry_run

    script_dir = os.path.dirname(os.path.abspath(__file__))

    if args.data_dir:
        data_dir = os.path.abspath(args.data_dir)
    else:
        data_dir = os.path.abspath(os.path.join(script_dir, '..', 'data', 'yahoo'))

    senders_file = os.path.join(data_dir, 'senders.json')
    state_file = os.path.join(data_dir, 'state.json')
    digest_raw_file = os.path.join(data_dir, 'for_digest.txt')
    digest_json_file = os.path.join(data_dir, 'digest.json')
    digest_txt_file = os.path.join(data_dir, 'digest.txt')

    os.makedirs(data_dir, exist_ok=True)

    if dry_run:
        print('*** DRY RUN MODE — no messages will be modified ***\n')

    # --- Load senders map and migrate legacy entries -------------------------
    senders_map = {}
    if os.path.exists(senders_file):
        with open(senders_file, 'r', encoding='utf-8') as f:
            senders_map = json.load(f)
    migrated = migrate_senders(senders_map)
    if migrated:
        print(f'Migrated {migrated} legacy sender(s) to 3-category system.')
        if not dry_run:
            atomic_write_json(senders_file, senders_map)

    # --- Load state ----------------------------------------------------------
    state = {}
    if os.path.exists(state_file):
        with open(state_file, 'r', encoding='utf-8') as f:
            state = json.load(f)
    last_uid = state.get('last_uid', 0)

    # --- Credentials ---------------------------------------------------------
    IMAP_HOST = os.getenv('IMAP_HOST', 'imap.mail.yahoo.com')
    IMAP_PORT = int(os.getenv('IMAP_PORT', '993'))
    IMAP_USER = os.getenv('IMAP_USER')
    IMAP_PASS = os.getenv('IMAP_PASS')
    if not IMAP_USER or not IMAP_PASS:
        print('Error: IMAP_USER and IMAP_PASS must be set.', file=sys.stderr)
        sys.exit(1)

    imap = ImapConn(IMAP_HOST, IMAP_PORT, IMAP_USER, IMAP_PASS)

    # --- Phase 1: Search and fetch headers -----------------------------------
    cutoff = (datetime.now(timezone.utc) - timedelta(days=args.days)).strftime('%d-%b-%Y')
    print(f'Searching messages since {cutoff} ({args.days} days)…')
    res, data = imap.uid('SEARCH', None, f'(SINCE {cutoff})')
    if res != 'OK':
        print('Error searching mailbox:', res, file=sys.stderr)
        sys.exit(1)
    uid_list = data[0].split() if data[0] else []
    print(f'  Found {len(uid_list)} messages')

    if not uid_list:
        print('No messages to process.')
        imap.logout()
        return

    print('Fetching headers…')
    messages = batch_fetch_headers(imap, uid_list)

    # Build per-sender latest info for interactive classification preview
    sender_latest = {}
    for uid, sender, subject, dt in messages:
        if sender not in sender_latest or uid > sender_latest[sender][0]:
            sender_latest[sender] = (uid, subject, dt)

    new_senders = sorted(s for s in sender_latest if s and s not in senders_map)
    classified_count = len(sender_latest) - len(new_senders)
    print(f'  Unique senders: {len(sender_latest)}, '
          f'classified: {classified_count}, new: {len(new_senders)}')

    # --- Phase 2: Classify new senders ---------------------------------------
    interactive = sys.stdin.isatty()
    pending_senders = []

    if new_senders:
        if interactive:
            print(f'\nClassify {len(new_senders)} new sender(s).\n'
                  f'Categories: {" / ".join(CATEGORY_PROMPTS)}\n')
        else:
            print(f'\nDeferring {len(new_senders)} new sender(s) (non-interactive).')

    for idx, sender in enumerate(new_senders, 1):
        uid, latest_subj, latest_dt = sender_latest[sender]
        print(f'[{idx}/{len(new_senders)}] {sender}')

        if not interactive:
            pending_senders.append({
                'sender': sender,
                'latest_uid': uid,
                'latest_date': latest_dt.isoformat() if latest_dt else None,
                'subject': latest_subj,
            })
            print('  Deferred.\n')
            continue

        classify_interactively(sender, imap, sender_latest, senders_map, dry_run)
        if not dry_run:
            atomic_write_json(senders_file, senders_map)
        print()

    # --- Phase 3: Determine action per message --------------------------------
    print('Determining actions…')
    digest = Digest(args.account)

    to_delete = []
    to_collect = []  # (uid, sender, subject, dt) — only newer than last_uid

    for uid, sender, subject, dt in messages:
        action, reason, attention, keywords_matched = decide_action(
            sender, subject, dt, senders_map, args.min_age_delete)

        digest.record(action, sender, uid, subject, dt, reason, attention, keywords_matched)

        if action == 'delete':
            to_delete.append(uid)
        elif action == 'collect_digest' and uid > last_uid:
            to_collect.append((uid, sender, subject, dt))

    totals = digest.totals()
    print(f'  Planned: {totals["deleted"]} delete, '
          f'{totals["digest_collected"]} collect, '
          f'{totals["kept"]} keep')

    # --- Phase 4a: Delete ----------------------------------------------------
    if to_delete:
        if dry_run:
            print(f'[DRY RUN] Would delete {len(to_delete)} message(s).')
        else:
            print(f'Deleting {len(to_delete)} message(s)…')
            batched_store(imap, to_delete, r'(\Deleted)', 'Flagged for deletion')
            imap.expunge()
            print('  Expunged.')
    else:
        print('No messages to delete.')

    # --- Phase 4b: Collect digest content ------------------------------------
    to_collect.sort(key=lambda x: x[0])
    if to_collect:
        if dry_run:
            print(f'[DRY RUN] Would collect {len(to_collect)} message(s) for digest.')
        else:
            print(f'Collecting {len(to_collect)} message(s) → for_digest.txt…')
            collect_digest(imap, to_collect, digest_raw_file)
            print('  Done.')
    else:
        print('No new messages to collect for digest.')

    # --- Phase 5: Write digest -----------------------------------------------
    digest.set_total_scanned(len(messages))
    digest.set_pending_senders(pending_senders)

    digest.write_json(digest_json_file, dry_run)
    digest_content = digest.write_txt(digest_txt_file, dry_run)
    print()
    print(digest_content)

    # --- Phase 6: Save state -------------------------------------------------
    if messages:
        max_uid = max(uid for uid, _, _, _ in messages)
        state.pop('pending_senders', None)
        if pending_senders:
            state['pending_senders'] = pending_senders
        if not dry_run:
            state['last_uid'] = max_uid
            atomic_write_json(state_file, state)
            print(f'State saved (last_uid={max_uid}).')
        else:
            print(f'[DRY RUN] State not saved (would be last_uid={max_uid}).')

    if pending_senders:
        print(f'Pending classification: {len(pending_senders)} sender(s).')

    imap.logout()
    print('Email review complete.')


if __name__ == '__main__':
    main()
