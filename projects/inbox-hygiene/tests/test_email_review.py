import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

import email_review as er
from datetime import datetime, timezone, timedelta


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
