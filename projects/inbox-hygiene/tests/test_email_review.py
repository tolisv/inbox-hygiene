import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

import email_review as er
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock


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


def _dt(days_ago):
    """Helper: datetime N days ago."""
    return datetime.now(timezone.utc) - timedelta(days=days_ago)


class TestDecideAction:
    def _decide(self, sender, subject, dt, senders_map, min_age=30, min_age_digest=14):
        return er.decide_action(sender, subject, dt, senders_map, min_age, min_age_digest)

    # Unclassified sender
    def test_unclassified_is_skip(self):
        action, reason, attention, kw, also_delete = self._decide(
            'unknown@x.com', 'hello', _dt(5), {})
        assert action == 'skip'
        assert attention is False
        assert kw == []
        assert also_delete is False

    # keep category
    def test_keep_sender_is_keep(self):
        action, _, attention, kw, also_delete = self._decide(
            'vip@x.com', 'hello', _dt(5), {'vip@x.com': 'keep'})
        assert action == 'keep'
        assert attention is False
        assert kw == []
        assert also_delete is False

    # delete category — age checks
    def test_delete_old_enough(self):
        action, _, attention, kw, also_delete = self._decide(
            'junk@x.com', 'sale!', _dt(31), {'junk@x.com': 'delete'})
        assert action == 'delete'
        assert attention is False
        assert also_delete is False

    def test_delete_too_recent_is_skip(self):
        action, _, _, _, _ = self._decide(
            'junk@x.com', 'sale!', _dt(10), {'junk@x.com': 'delete'})
        assert action == 'skip'

    def test_delete_exactly_at_min_age(self):
        action, _, _, _, _ = self._decide(
            'junk@x.com', 'sale!', _dt(30), {'junk@x.com': 'delete'})
        assert action == 'delete'

    def test_delete_keyword_in_subject_does_not_change_action(self):
        # keywords are NOT checked for delete senders
        action, _, attention, kw, also_delete = self._decide(
            'junk@x.com', 'Fatura pendente', _dt(31), {'junk@x.com': 'delete'})
        assert action == 'delete'
        assert attention is False
        assert kw == []
        assert also_delete is False

    # digest category
    def test_digest_no_keywords(self):
        action, _, attention, kw, also_delete = self._decide(
            'news@x.com', 'Weekly roundup', _dt(5), {'news@x.com': 'digest'})
        assert action == 'collect_digest'
        assert attention is False
        assert kw == []
        assert also_delete is False  # too recent to delete

    def test_digest_with_keyword_sets_attention(self):
        action, _, attention, kw, also_delete = self._decide(
            'bank@x.com', 'Fatura disponível', _dt(5), {'bank@x.com': 'digest'})
        assert action == 'collect_digest'
        assert attention is True
        assert 'fatura' in kw
        assert also_delete is False  # too recent to delete

    def test_digest_not_age_gated(self):
        # digest emails are always collected regardless of age
        action, _, _, _, _ = self._decide(
            'news@x.com', 'Old newsletter', _dt(200), {'news@x.com': 'digest'})
        assert action == 'collect_digest'

    def test_digest_old_enough_sets_also_delete(self):
        # digest emails >= min_age_digest should be flagged for deletion after collection
        action, _, _, _, also_delete = self._decide(
            'news@x.com', 'Old newsletter', _dt(14), {'news@x.com': 'digest'},
            min_age_digest=14)
        assert action == 'collect_digest'
        assert also_delete is True

    def test_digest_too_recent_also_delete_false(self):
        action, _, _, _, also_delete = self._decide(
            'news@x.com', 'Recent newsletter', _dt(5), {'news@x.com': 'digest'},
            min_age_digest=14)
        assert action == 'collect_digest'
        assert also_delete is False

    def test_custom_min_age(self):
        action, _, _, _, _ = self._decide(
            'junk@x.com', 'sale', _dt(10), {'junk@x.com': 'delete'}, min_age=7)
        assert action == 'delete'


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
        assert data['summary']['digest_seen'] == 1
        assert data['summary']['pending_classification'] == 1
        assert len(data['attention_items']) == 1
        assert data['attention_items'][0]['sender'] == 'bank@x.com'
        assert data['attention_items'][0]['attention'] is True
        assert 'fatura' in data['attention_items'][0]['keywords_matched']
        assert len(data['deleted_items']) == 1
        assert 'digest_items' not in data

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


class TestClassifyPendingWithLlm:
    """Tests for classify_pending_with_llm() — all using mocked Anthropic API."""

    def _pending(self, sender, subject, date=None):
        return {
            'sender': sender,
            'subject': subject,
            'latest_date': date or '2026-04-01T10:00:00+00:00',
            'latest_uid': 999,
        }

    def test_returns_dict_with_categories(self):
        """Valid JSON response → returns sender→category dict."""
        pending = [
            self._pending('spam@promo.com', 'Big Sale Today!'),
            self._pending('news@substack.com', 'Weekly digest'),
        ]
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"spam@promo.com": "delete", "news@substack.com": "digest"}')]

        with patch('anthropic.Anthropic') as MockClient:
            MockClient.return_value.messages.create.return_value = mock_response
            result = er.classify_pending_with_llm(pending, api_key='test-key')

        assert result == {'spam@promo.com': 'delete', 'news@substack.com': 'digest'}

    def test_invalid_json_falls_back_to_digest(self):
        """Malformed JSON response → all senders get 'digest'."""
        pending = [
            self._pending('weird@x.com', 'Some subject'),
        ]
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='this is not json at all')]

        with patch('anthropic.Anthropic') as MockClient:
            MockClient.return_value.messages.create.return_value = mock_response
            result = er.classify_pending_with_llm(pending, api_key='test-key')

        assert result == {'weird@x.com': 'digest'}

    def test_unknown_category_falls_back_to_digest(self):
        """Unknown category in response → that sender gets 'digest'."""
        pending = [
            self._pending('a@x.com', 'Hi'),
            self._pending('b@x.com', 'Hello'),
        ]
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"a@x.com": "archive", "b@x.com": "delete"}')]

        with patch('anthropic.Anthropic') as MockClient:
            MockClient.return_value.messages.create.return_value = mock_response
            result = er.classify_pending_with_llm(pending, api_key='test-key')

        assert result['a@x.com'] == 'digest'   # unknown → digest
        assert result['b@x.com'] == 'delete'   # valid → keep as-is

    def test_empty_pending_returns_empty_dict(self):
        """Empty pending list → no API call, returns empty dict."""
        with patch('anthropic.Anthropic') as MockClient:
            result = er.classify_pending_with_llm([], api_key='test-key')

        MockClient.assert_not_called()
        assert result == {}

    def test_missing_sender_in_response_falls_back_to_digest(self):
        """If API doesn't return a category for a sender → that sender gets 'digest'."""
        pending = [
            self._pending('a@x.com', 'Hi'),
            self._pending('b@x.com', 'Hello'),
        ]
        mock_response = MagicMock()
        # Only 'a@x.com' in response — 'b@x.com' missing
        mock_response.content = [MagicMock(text='{"a@x.com": "keep"}')]

        with patch('anthropic.Anthropic') as MockClient:
            MockClient.return_value.messages.create.return_value = mock_response
            result = er.classify_pending_with_llm(pending, api_key='test-key')

        assert result['a@x.com'] == 'keep'
        assert result['b@x.com'] == 'digest'
