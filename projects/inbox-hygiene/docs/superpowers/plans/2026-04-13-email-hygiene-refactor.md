# Email Hygiene — 3-Category Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor `email_review.py` from 5 categories to 3 (delete/digest/keep), set 30-day delete retention, add structured `digest.json` output for OpenClaw, and create `AGENT.md`.

**Architecture:** Pure-function logic (migration, classification, keyword detection) is extracted and tested first, then the `Digest` class is updated to emit JSON, then `main()` is wired together. The script gains `--data-dir` and `--account` args so each email account gets its own data directory.

**Tech Stack:** Python 3 stdlib only (imaplib, email, json, argparse, re, datetime). Tests: pytest (no extra deps).

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `projects/inbox-hygiene/scripts/email_review.py` | Modify | Core script — all logic changes |
| `projects/inbox-hygiene/scripts/run_yahoo.sh` | Modify | Wrapper — add --data-dir, --account |
| `projects/inbox-hygiene/scripts/README.md` | Modify | Docs update |
| `projects/inbox-hygiene/tests/__init__.py` | Create | Makes tests/ a package |
| `projects/inbox-hygiene/tests/test_email_review.py` | Create | Unit tests |
| `projects/inbox-hygiene/AGENT.md` | Create | OpenClaw brief |
| `projects/inbox-hygiene/higiene-e-mails.md` | Modify | Update to reflect final decisions |

---

## Task 1: Test infrastructure

**Files:**
- Create: `projects/inbox-hygiene/tests/__init__.py`
- Create: `projects/inbox-hygiene/tests/test_email_review.py`

- [ ] **Step 1: Create the tests directory and empty `__init__.py`**

```bash
mkdir -p projects/inbox-hygiene/tests
touch projects/inbox-hygiene/tests/__init__.py
```

- [ ] **Step 2: Create `test_email_review.py` with import scaffold**

```python
# projects/inbox-hygiene/tests/test_email_review.py
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

import email_review as er
from datetime import datetime, timezone, timedelta
```

- [ ] **Step 3: Verify pytest can discover and run (zero tests is fine)**

Run from `projects/inbox-hygiene/`:
```bash
python -m pytest tests/ -v
```
Expected output: `no tests ran` or `0 passed` — no import errors.

- [ ] **Step 4: Commit**

```bash
git add projects/inbox-hygiene/tests/
git commit -m "test: add test infrastructure for email_review"
```

---

## Task 2: Replace `subject_triggers_attention` with `attention_keywords_in`

The old function returns `bool`. The new one returns a `list` of matched keywords. Keywords are only checked for `digest` emails — the function itself is unchanged in what it looks for, but the caller decides when to use it.

**Files:**
- Modify: `projects/inbox-hygiene/scripts/email_review.py`
- Modify: `projects/inbox-hygiene/tests/test_email_review.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_email_review.py`:

```python
class TestAttentionKeywordsIn:
    def test_returns_empty_for_none(self):
        assert er.attention_keywords_in(None) == []

    def test_returns_empty_for_empty_string(self):
        assert er.attention_keywords_in('') == []

    def test_detects_fatura(self):
        result = er.attention_keywords_in('Sua fatura está disponível')
        assert 'fatura' in result

    def test_detects_vencimento(self):
        result = er.attention_keywords_in('Vencimento em 20/04')
        assert 'vencimento' in result

    def test_case_insensitive(self):
        result = er.attention_keywords_in('FATURA PENDENTE')
        assert 'fatura' in result

    def test_no_match_returns_empty(self):
        result = er.attention_keywords_in('Weekly newsletter about gardening')
        assert result == []

    def test_multiple_keywords(self):
        result = er.attention_keywords_in('Fatura vencendo amanhã')
        assert 'fatura' in result
        assert 'vencimento' in result or 'vencendo' in result
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_email_review.py::TestAttentionKeywordsIn -v
```
Expected: `AttributeError: module 'email_review' has no attribute 'attention_keywords_in'`

- [ ] **Step 3: In `email_review.py`, replace `subject_triggers_attention` with `attention_keywords_in`**

Find and remove:
```python
def subject_triggers_attention(subject):
    """Return True if subject contains any high-importance keyword."""
    return bool(ATTENTION_RE.search(subject or ''))
```

Add in its place:
```python
def attention_keywords_in(subject):
    """Return list of ATTENTION_KEYWORDS found in subject (case-insensitive)."""
    if not subject:
        return []
    subj_lower = subject.lower()
    return [kw for kw in ATTENTION_KEYWORDS if kw.lower() in subj_lower]
```

Also remove the `ATTENTION_RE` compiled regex (no longer needed):
```python
ATTENTION_RE = re.compile(
    r'(?:' + '|'.join(re.escape(kw) for kw in ATTENTION_KEYWORDS) + r')',
    re.IGNORECASE,
)
```

And remove the `re` import if nothing else uses it — check first:
```bash
grep -n "re\." projects/inbox-hygiene/scripts/email_review.py
```
If `re` is only used for `ATTENTION_RE` and `UID_RE`, keep `UID_RE` but remove `ATTENTION_RE`. Leave the `import re` since `UID_RE` still uses it.

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_email_review.py::TestAttentionKeywordsIn -v
```
Expected: all 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add projects/inbox-hygiene/scripts/email_review.py projects/inbox-hygiene/tests/test_email_review.py
git commit -m "refactor: replace subject_triggers_attention with attention_keywords_in returning list"
```

---

## Task 3: Update `migrate_senders` for 5→3 categories

**Files:**
- Modify: `projects/inbox-hygiene/scripts/email_review.py`
- Modify: `projects/inbox-hygiene/tests/test_email_review.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_email_review.py`:

```python
class TestMigrateSenders:
    def test_delete_unchanged(self):
        m = {'a@b.com': 'delete'}
        count = er.migrate_senders(m)
        assert m['a@b.com'] == 'delete'
        assert count == 0

    def test_digest_unchanged(self):
        m = {'a@b.com': 'digest'}
        count = er.migrate_senders(m)
        assert m['a@b.com'] == 'digest'
        assert count == 0

    def test_keep_unchanged(self):
        m = {'a@b.com': 'keep'}
        count = er.migrate_senders(m)
        assert m['a@b.com'] == 'keep'
        assert count == 0

    def test_summarize_becomes_digest(self):
        m = {'a@b.com': 'summarize'}
        count = er.migrate_senders(m)
        assert m['a@b.com'] == 'digest'
        assert count == 1

    def test_archive_reference_becomes_digest(self):
        m = {'a@b.com': 'archive_reference'}
        count = er.migrate_senders(m)
        assert m['a@b.com'] == 'digest'
        assert count == 1

    def test_needs_attention_becomes_keep(self):
        m = {'a@b.com': 'needs_attention'}
        count = er.migrate_senders(m)
        assert m['a@b.com'] == 'keep'
        assert count == 1

    def test_keep_never_auto_becomes_keep(self):
        m = {'a@b.com': 'keep_never_auto'}
        count = er.migrate_senders(m)
        assert m['a@b.com'] == 'keep'
        assert count == 1

    def test_mixed_map_migrated_correctly(self):
        m = {
            'junk@spam.com': 'delete',
            'news@sub.com': 'summarize',
            'bank@itau.com': 'needs_attention',
            'old@legacy.com': 'keep_never_auto',
            'ref@docs.com': 'archive_reference',
        }
        count = er.migrate_senders(m)
        assert m['junk@spam.com'] == 'delete'
        assert m['news@sub.com'] == 'digest'
        assert m['bank@itau.com'] == 'keep'
        assert m['old@legacy.com'] == 'keep'
        assert m['ref@docs.com'] == 'digest'
        assert count == 4
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_email_review.py::TestMigrateSenders -v
```
Expected: most tests FAIL — current `migrate_senders` only handles `keep` → `keep_never_auto`.

- [ ] **Step 3: In `email_review.py`, add `LEGACY_CATEGORY_MAP` and update `migrate_senders`**

After the `CATEGORIES` constant, add:

```python
CATEGORIES = ('delete', 'digest', 'keep')

LEGACY_CATEGORY_MAP = {
    'keep_never_auto': 'keep',
    'needs_attention': 'keep',
    'summarize': 'digest',
    'archive_reference': 'digest',
    'keep': 'keep',      # safety: legacy keep from oldest version
}
```

Replace the existing `migrate_senders` function:

```python
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
```

Also update the `CATEGORY_PROMPTS` constant (used in interactive classification):

```python
CATEGORY_PROMPTS = (
    '[d]elete',
    '[di]gest',
    '[k]eep',
)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_email_review.py::TestMigrateSenders -v
```
Expected: all 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add projects/inbox-hygiene/scripts/email_review.py projects/inbox-hygiene/tests/test_email_review.py
git commit -m "refactor: update migrate_senders for 5→3 category system"
```

---

## Task 4: Update `decide_action` for 3 categories

The new signature returns 4 values: `(action, reason, attention, keywords_matched)`. Keywords are only checked for `digest` senders. Remove `min_age_archive` parameter.

**Files:**
- Modify: `projects/inbox-hygiene/scripts/email_review.py`
- Modify: `projects/inbox-hygiene/tests/test_email_review.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_email_review.py`:

```python
def _dt(days_ago):
    """Helper: datetime N days ago."""
    return datetime.now(timezone.utc) - timedelta(days=days_ago)


class TestDecideAction:
    def _decide(self, sender, subject, dt, senders_map, min_age=30):
        return er.decide_action(sender, subject, dt, senders_map, min_age)

    # Unclassified sender
    def test_unclassified_is_skip(self):
        action, reason, attention, kw = self._decide(
            'unknown@x.com', 'hello', _dt(5), {})
        assert action == 'skip'
        assert attention is False
        assert kw == []

    # keep category
    def test_keep_sender_is_keep(self):
        action, _, attention, kw = self._decide(
            'vip@x.com', 'hello', _dt(5), {'vip@x.com': 'keep'})
        assert action == 'keep'
        assert attention is False
        assert kw == []

    # delete category — age checks
    def test_delete_old_enough(self):
        action, _, attention, kw = self._decide(
            'junk@x.com', 'sale!', _dt(31), {'junk@x.com': 'delete'})
        assert action == 'delete'
        assert attention is False

    def test_delete_too_recent_is_skip(self):
        action, _, _, _ = self._decide(
            'junk@x.com', 'sale!', _dt(10), {'junk@x.com': 'delete'})
        assert action == 'skip'

    def test_delete_exactly_at_min_age(self):
        action, _, _, _ = self._decide(
            'junk@x.com', 'sale!', _dt(30), {'junk@x.com': 'delete'})
        assert action == 'delete'

    def test_delete_keyword_in_subject_does_not_change_action(self):
        # keywords are NOT checked for delete senders
        action, _, attention, kw = self._decide(
            'junk@x.com', 'Fatura pendente', _dt(31), {'junk@x.com': 'delete'})
        assert action == 'delete'
        assert attention is False
        assert kw == []

    # digest category
    def test_digest_no_keywords(self):
        action, _, attention, kw = self._decide(
            'news@x.com', 'Weekly roundup', _dt(5), {'news@x.com': 'digest'})
        assert action == 'collect_digest'
        assert attention is False
        assert kw == []

    def test_digest_with_keyword_sets_attention(self):
        action, _, attention, kw = self._decide(
            'bank@x.com', 'Fatura disponível', _dt(5), {'bank@x.com': 'digest'})
        assert action == 'collect_digest'
        assert attention is True
        assert 'fatura' in kw

    def test_digest_not_age_gated(self):
        # digest emails are collected regardless of age
        action, _, _, _ = self._decide(
            'news@x.com', 'Old newsletter', _dt(200), {'news@x.com': 'digest'})
        assert action == 'collect_digest'

    def test_custom_min_age(self):
        action, _, _, _ = self._decide(
            'junk@x.com', 'sale', _dt(10), {'junk@x.com': 'delete'}, min_age=7)
        assert action == 'delete'
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_email_review.py::TestDecideAction -v
```
Expected: failures — function signature mismatch and missing `collect_digest` action.

- [ ] **Step 3: Replace `decide_action` in `email_review.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_email_review.py::TestDecideAction -v
```
Expected: all 11 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add projects/inbox-hygiene/scripts/email_review.py projects/inbox-hygiene/tests/test_email_review.py
git commit -m "refactor: update decide_action for 3-category system, keywords only for digest"
```

---

## Task 5: Refactor `Digest` class

Add `write_json()`, rename `write()` → `write_txt()`, update `record()` signature. The constructor now takes an `account` name. `set_total_scanned()` and `set_pending_senders()` allow main() to feed data after processing.

**Files:**
- Modify: `projects/inbox-hygiene/scripts/email_review.py`
- Modify: `projects/inbox-hygiene/tests/test_email_review.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_email_review.py`:

```python
import json
import tempfile

class TestDigest:
    def _make_digest(self, account='yahoo'):
        return er.Digest(account)

    def _dt_obj(self, days_ago=1):
        return datetime.now(timezone.utc) - timedelta(days=days_ago)

    def test_totals_empty(self):
        d = self._make_digest()
        t = d.totals()
        assert t['deleted'] == 0
        assert t['digest_collected'] == 0

    def test_record_delete(self):
        d = self._make_digest()
        d.record('delete', 'junk@x.com', 100, 'Sale!', dt=self._dt_obj(31))
        assert d.totals()['deleted'] == 1

    def test_record_collect_digest_no_attention(self):
        d = self._make_digest()
        d.record('collect_digest', 'news@x.com', 200, 'Weekly', dt=self._dt_obj(1),
                 attention=False, keywords_matched=[])
        assert d.totals()['digest_collected'] == 1

    def test_record_collect_digest_with_attention(self):
        d = self._make_digest()
        d.record('collect_digest', 'bank@x.com', 300, 'Fatura vencendo',
                 dt=self._dt_obj(1), attention=True, keywords_matched=['fatura'])
        assert d.totals()['digest_collected'] == 1

    def test_write_json_structure(self):
        d = self._make_digest('yahoo')
        d.set_total_scanned(50)
        d.record('delete', 'junk@x.com', 100, 'Sale!', dt=self._dt_obj(31))
        d.record('collect_digest', 'bank@x.com', 200, 'Fatura vencendo',
                 dt=self._dt_obj(1), attention=True, keywords_matched=['fatura'])
        d.set_pending_senders([{'sender': 'new@x.com', 'subject': 'hi'}])

        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            path = f.name

        data = d.write_json(path, dry_run=False)

        assert data['account'] == 'yahoo'
        assert data['dry_run'] is False
        assert data['summary']['total_messages_scanned'] == 50
        assert data['summary']['deleted'] == 1
        assert data['summary']['digest_collected'] == 1
        assert data['summary']['pending_classification'] == 1
        assert len(data['attention_items']) == 1
        assert data['attention_items'][0]['sender'] == 'bank@x.com'
        assert data['attention_items'][0]['attention'] is True
        assert 'fatura' in data['attention_items'][0]['keywords_matched']
        assert len(data['deleted_items']) == 1
        assert len(data['digest_items']) == 1

        # verify file was written and parses correctly
        with open(path) as f:
            on_disk = json.load(f)
        assert on_disk['account'] == 'yahoo'

    def test_write_json_dry_run_flag(self):
        d = self._make_digest()
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            path = f.name
        data = d.write_json(path, dry_run=True)
        assert data['dry_run'] is True

    def test_write_txt_appends(self):
        d = self._make_digest()
        d.set_total_scanned(10)
        with tempfile.NamedTemporaryFile(suffix='.txt', mode='w', delete=False) as f:
            path = f.name
        d.write_txt(path, dry_run=False)
        d.write_txt(path, dry_run=False)
        with open(path) as f:
            content = f.read()
        assert content.count('Email Hygiene Digest') == 2
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_email_review.py::TestDigest -v
```
Expected: failures — `Digest` constructor doesn't accept `account`, `write_json` doesn't exist, etc.

- [ ] **Step 3: Replace the `Digest` class in `email_review.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_email_review.py::TestDigest -v
```
Expected: all tests PASS.

- [ ] **Step 5: Run the full test suite to check for regressions**

```bash
python -m pytest tests/ -v
```
Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add projects/inbox-hygiene/scripts/email_review.py projects/inbox-hygiene/tests/test_email_review.py
git commit -m "refactor: update Digest class with write_json(), write_txt(), 3-category buckets"
```

---

## Task 6: Update `classify_interactively` and constants

No tests needed (interactive I/O). Update prompts for 3 categories.

**Files:**
- Modify: `projects/inbox-hygiene/scripts/email_review.py`

- [ ] **Step 1: Update `classify_interactively` in `email_review.py`**

Replace the existing function:

```python
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
```

- [ ] **Step 2: Run the full test suite to make sure nothing broke**

```bash
python -m pytest tests/ -v
```
Expected: all tests PASS.

- [ ] **Step 3: Commit**

```bash
git add projects/inbox-hygiene/scripts/email_review.py
git commit -m "refactor: update classify_interactively for 3-category system (d/di/k)"
```

---

## Task 7: Rename `append_summaries` → `collect_digest`

**Files:**
- Modify: `projects/inbox-hygiene/scripts/email_review.py`

- [ ] **Step 1: Rename the function and update its docstring**

Find:
```python
def append_summaries(imap, to_summarize, summary_file):
    """Fetch RFC822 for each message and append plain-text body to summary_file."""
```

Replace with:
```python
def collect_digest(imap, to_collect, digest_raw_file):
    """Fetch RFC822 for each message and append plain-text body to digest_raw_file."""
```

Also rename the parameter throughout the function body: `to_summarize` → `to_collect`, `summary_file` → `digest_raw_file`.

The full updated function:

```python
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
```

- [ ] **Step 2: Run the full test suite**

```bash
python -m pytest tests/ -v
```
Expected: all tests PASS.

- [ ] **Step 3: Commit**

```bash
git add projects/inbox-hygiene/scripts/email_review.py
git commit -m "refactor: rename append_summaries to collect_digest"
```

---

## Task 8: Update `parse_args` and `main`

This wires everything together. Add `--data-dir` and `--account` args. Change default `--min-age-delete` to 30. Remove `--min-age-archive`. Remove archive/flag logic. Add collect_digest. Write both `digest.json` and `digest.txt`.

**Files:**
- Modify: `projects/inbox-hygiene/scripts/email_review.py`

- [ ] **Step 1: Replace `parse_args` in `email_review.py`**

```python
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
```

- [ ] **Step 2: Update the `DEFAULT_MIN_AGE_DELETE` constant**

Find:
```python
DEFAULT_MIN_AGE_DELETE = 7
```
Replace with:
```python
DEFAULT_MIN_AGE_DELETE = 30
```

Also remove (no longer needed):
```python
DEFAULT_MIN_AGE_ARCHIVE = 7
ARCHIVE_FOLDER = 'Archive'
```

- [ ] **Step 3: Replace `main` in `email_review.py`**

```python
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
```

- [ ] **Step 4: Also remove `batched_copy_move` function (no longer used)**

Find and delete the entire `batched_copy_move` function:
```python
def batched_copy_move(imap, uid_ints, dest_folder, batch_size=50):
    ...
```

- [ ] **Step 5: Run the full test suite**

```bash
python -m pytest tests/ -v
```
Expected: all tests PASS.

- [ ] **Step 6: Verify the script at least parses without error**

```bash
python projects/inbox-hygiene/scripts/email_review.py --help
```
Expected output shows `--data-dir`, `--account`, `--min-age-delete` (default: 30), no `--min-age-archive`.

- [ ] **Step 7: Commit**

```bash
git add projects/inbox-hygiene/scripts/email_review.py
git commit -m "refactor: update parse_args and main for 3-category system, add --data-dir and --account"
```

---

## Task 9: Update `run_yahoo.sh`

**Files:**
- Modify: `projects/inbox-hygiene/scripts/run_yahoo.sh`

- [ ] **Step 1: Replace content of `run_yahoo.sh`**

```bash
#!/usr/bin/env bash
# run_yahoo.sh — wrapper for email_review.py against Yahoo IMAP
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DATA_DIR="$PROJECT_DIR/data/yahoo"
CREDS_FILE="$SCRIPT_DIR/email_creds.env"

if [[ ! -f "$CREDS_FILE" ]]; then
    echo "Error: credentials file not found: $CREDS_FILE" >&2
    echo "Create it with IMAP_USER and IMAP_PASS variables." >&2
    exit 1
fi

# shellcheck source=/dev/null
source "$CREDS_FILE"

mkdir -p "$DATA_DIR"
chmod 700 "$DATA_DIR"

# Initialize state file if missing
if [[ ! -f "$DATA_DIR/state.json" ]]; then
    echo '{"last_uid": 0}' > "$DATA_DIR/state.json"
fi

# Initialize senders file if missing
if [[ ! -f "$DATA_DIR/senders.json" ]]; then
    echo '{}' > "$DATA_DIR/senders.json"
fi

exec python3 "$SCRIPT_DIR/email_review.py" \
    --data-dir "$DATA_DIR" \
    --account "yahoo" \
    "$@"
```

- [ ] **Step 2: Make it executable**

```bash
chmod +x projects/inbox-hygiene/scripts/run_yahoo.sh
```

- [ ] **Step 3: Verify `--help` works through the wrapper (without real credentials)**

Set dummy env and confirm it reaches the Python script's argument parser:
```bash
IMAP_USER=test IMAP_PASS=test bash projects/inbox-hygiene/scripts/run_yahoo.sh --help 2>&1 | head -5
```
Expected: shows usage from `email_review.py` (will error on connect, but `--help` exits before that).

Actually, sourcing the creds file will fail if the file doesn't exist. Just verify the script has correct syntax:
```bash
bash -n projects/inbox-hygiene/scripts/run_yahoo.sh && echo "syntax OK"
```
Expected: `syntax OK`

- [ ] **Step 4: Commit**

```bash
git add projects/inbox-hygiene/scripts/run_yahoo.sh
git commit -m "feat: update run_yahoo.sh with --data-dir, --account, and cleaner structure"
```

---

## Task 10: Create `AGENT.md`

**Files:**
- Create: `projects/inbox-hygiene/AGENT.md`

- [ ] **Step 1: Create `projects/inbox-hygiene/AGENT.md`**

```markdown
# Email Hygiene — Agent Brief

This document tells an OpenClaw agent how to operate the inbox-hygiene system.

## What the system does

Runs daily against the Yahoo IMAP account:
- Deletes junk emails aged ≥ 30 days
- Collects content from "digest" emails into `data/yahoo/for_digest.txt` for future LLM processing
- Leaves "keep" emails untouched
- Writes `data/yahoo/digest.json` — the structured report for this agent to consume

## How to run

```bash
# Always test with dry-run first when in doubt
projects/inbox-hygiene/scripts/run_yahoo.sh --dry-run

# Normal daily run
projects/inbox-hygiene/scripts/run_yahoo.sh
```

Credentials (`email_creds.env`) must exist at `projects/inbox-hygiene/scripts/email_creds.env`.
This file is gitignored and never committed.

## How to read digest.json

File: `projects/inbox-hygiene/data/yahoo/digest.json`

This file is **overwritten on each run**. Key fields:

| Field | Meaning | When to act |
|-------|---------|-------------|
| `attention_items` | Digest emails with urgent keywords (fatura, vencimento, alerta…) | Alert user immediately |
| `pending_senders` | New senders not yet classified | Ask user when convenient |
| `summary.deleted` | How many emails were deleted | Report on request |
| `summary.digest_collected` | How many emails collected for future processing | Report on request |
| `dry_run` | True if script ran in report-only mode | No changes were made |

## When to alert the user

- `attention_items` is not empty → notify immediately (urgent emails detected)
- `pending_senders` is not empty → ask user to classify during next interaction
- Script exits with non-zero status → notify with the error output

## What NEVER to do without asking

- Run without `--dry-run` on a new/unfamiliar account
- Edit `senders.json` without user confirmation
- Delete `for_digest.txt` or `digest.txt` (historical data)
- Run against any account other than Yahoo without explicit instruction

## How to classify a pending sender

1. Read `digest.json` → look at `pending_senders`
2. Show user: sender address, subject, date
3. Ask: classify as **delete**, **digest**, or **keep**?
4. Update `data/yahoo/senders.json` directly with the classification

Example senders.json entry to add:
```json
"no-reply@github.com": "digest"
```

## Three categories

| Category | Meaning |
|----------|---------|
| `delete` | Pure junk. Auto-deleted after 30 days. |
| `digest` | Content of interest. Collected for future LLM processing. Never auto-deleted. |
| `keep` | VIP / personal / critical. Never touched by automation. |

## File reference

| File | Purpose |
|------|---------|
| `data/yahoo/senders.json` | Sender → category map |
| `data/yahoo/state.json` | Last processed UID + pending senders |
| `data/yahoo/digest.json` | Latest run report (overwritten each run) |
| `data/yahoo/digest.txt` | Human-readable log (appends each run) |
| `data/yahoo/for_digest.txt` | Raw email content for future LLM processing |
| `scripts/email_creds.env` | IMAP credentials (local only, gitignored) |
```

- [ ] **Step 2: Commit**

```bash
git add projects/inbox-hygiene/AGENT.md
git commit -m "docs: add AGENT.md brief for OpenClaw integration"
```

---

## Task 11: Update `README.md`

**Files:**
- Modify: `projects/inbox-hygiene/scripts/README.md`

- [ ] **Step 1: Replace content of `scripts/README.md`**

```markdown
# Email Hygiene — Yahoo IMAP

Daily automation to keep the Yahoo inbox clean. Classifies senders into
three categories and takes action accordingly.

## Categories

| Category | Description | Action |
|----------|-------------|--------|
| `delete` | Pure junk, spam, marketing | Auto-deleted after 30 days |
| `digest` | Newsletters, content of interest | Collected for future LLM processing |
| `keep` | VIP, personal, critical senders | Never touched |

## Components

- **`email_review.py`** — account-agnostic core script
- **`run_yahoo.sh`** — wrapper for Yahoo (loads credentials, sets data dir)
- **`email_creds.env`** — IMAP credentials (gitignored, not committed)

## Setup

1. Create `scripts/email_creds.env`:
   ```bash
   IMAP_USER="your_yahoo_email@yahoo.com"
   IMAP_PASS="your_app_password"
   # Optional overrides:
   # IMAP_HOST="imap.mail.yahoo.com"
   # IMAP_PORT="993"
   ```

2. Make the wrapper executable:
   ```bash
   chmod +x scripts/run_yahoo.sh
   ```

## Usage

```bash
# Dry run — see what would happen, no changes
scripts/run_yahoo.sh --dry-run

# Normal run
scripts/run_yahoo.sh

# Custom options
scripts/run_yahoo.sh --days 180 --min-age-delete 14
```

On the first interactive run, new senders are shown with a preview and
you classify each as **d**elete / **di**gest / **k**eep.

In non-interactive mode (cron), new senders are deferred to
`data/yahoo/state.json` under `pending_senders`.

## Output files

| File | Description |
|------|-------------|
| `data/yahoo/senders.json` | Sender → category map |
| `data/yahoo/state.json` | Last processed UID + pending senders |
| `data/yahoo/digest.json` | Latest run report — overwritten each run |
| `data/yahoo/digest.txt` | Human-readable log — appended each run |
| `data/yahoo/for_digest.txt` | Raw email content for future LLM processing |

## OpenClaw integration

See `../AGENT.md` for how an OpenClaw agent should run and interpret
results from this script.

## Cron example

```cron
0 7 * * * /path/to/projects/inbox-hygiene/scripts/run_yahoo.sh >> /path/to/projects/inbox-hygiene/data/yahoo/run.log 2>&1
```
```

- [ ] **Step 2: Commit**

```bash
git add projects/inbox-hygiene/scripts/README.md
git commit -m "docs: update README for 3-category system and new directory structure"
```

---

## Task 12: Update `higiene-e-mails.md`

**Files:**
- Modify: `projects/inbox-hygiene/higiene-e-mails.md`

- [ ] **Step 1: Update the "Fases do projeto" section to reflect what's done**

Find the `## Fases do projeto` section and update it:

```markdown
## Status atual (2026-04-13)

As fases 1 e 2 foram concluídas. O sistema opera com 3 categorias nativas:
delete, digest, keep.

- Fase 1 (Mapeamento): ✅ Concluída
- Fase 2 (Taxonomia e regras): ✅ Concluída — simplificada para 3 categorias
- Fase 3 (Execução segura): ✅ Concluída — dry-run implementado
- Fase 4 (Automação parcial): ✅ Concluída — delete automático após 30 dias
- Fase 5 (Expansão multi-conta): 🔜 Próxima fase
```

- [ ] **Step 2: Update the "Taxonomia proposta" section to reflect the simplified system**

Replace the 5-category taxonomy section with:

```markdown
## Taxonomia atual (simplificada)

### 1. delete

Junk puro, marketing, spam, newsletters sem valor.

Ação: apagado automaticamente após 30 dias.

### 2. digest

Newsletters selecionadas, conteúdo de interesse (produtividade, economia,
filosofia, culinária, viagem). Emails não-VIP, não-junk.

Ação: conteúdo coletado em `for_digest.txt` para processamento LLM futuro.
Nunca apagado automaticamente. Emails com keywords urgentes (fatura, vencimento,
alerta) são marcados com `attention: true` no digest.json para notificação via OpenClaw.

### 3. keep

VIP, pessoal, banco crítico, qualquer remetente que nunca deve ser tocado.

Ação: nenhuma. Preservado indefinidamente.
```

- [ ] **Step 3: Commit**

```bash
git add projects/inbox-hygiene/higiene-e-mails.md
git commit -m "docs: update higiene-e-mails.md to reflect 3-category system and current status"
```

---

## Task 13: Final push to GitHub

- [ ] **Step 1: Run full test suite one last time**

```bash
python -m pytest projects/inbox-hygiene/tests/ -v
```
Expected: all tests PASS.

- [ ] **Step 2: Verify script help output**

```bash
python projects/inbox-hygiene/scripts/email_review.py --help
```
Expected: shows `--data-dir`, `--account`, `--min-age-delete` (default 30), no `--min-age-archive`.

- [ ] **Step 3: Push to GitHub**

```bash
git push origin master
```

---

## Self-Review

**Spec coverage:**
- ✅ 3 categories (delete/digest/keep) — Tasks 3, 4, 8
- ✅ 30-day default delete retention — Task 8 (DEFAULT_MIN_AGE_DELETE = 30)
- ✅ digest.json structured output — Task 5
- ✅ Migration from 5-category senders.json — Task 3
- ✅ Directory reorganization — already done before this plan
- ✅ README updated — Task 11
- ✅ higiene-e-mails.md updated — Task 12
- ✅ AGENT.md created — Task 10
- ✅ Keywords only for digest senders — Task 4
- ✅ run_yahoo.sh updated — Task 9

**No placeholders found.**

**Type consistency:** `decide_action` returns `(action, reason, attention, keywords_matched)` defined in Task 4, consumed in Task 8 `main()`. `Digest.record()` signature defined in Task 5, called in Task 8. All consistent.
