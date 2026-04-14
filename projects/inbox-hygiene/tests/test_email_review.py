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
