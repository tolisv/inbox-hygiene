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
