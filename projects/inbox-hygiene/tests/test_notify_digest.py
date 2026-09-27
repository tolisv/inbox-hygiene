import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / 'scripts' / 'notify_digest.py'
SPEC = importlib.util.spec_from_file_location('notify_digest', MODULE_PATH)
notify = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(notify)


def test_build_message_reports_fixed_digest_fields():
    digest = {
        'dry_run': False,
        'summary': {
            'total_messages_scanned': 12,
            'deleted': 2,
            'digest_seen': 3,
            'digest_deleted': 1,
            'kept': 6,
            'pending_classification': 1,
        },
        'attention_items': [{'subject': 'Security alert'}],
        'pending_senders': [{}],
        'llm_classifications': [
            {'accepted': True},
            {'accepted': False},
        ],
    }
    message = notify.build_message('gmail', 0, digest)
    assert 'apagadas: 2' in message
    assert 'JEV aceitas: 1' in message
    assert 'revisão: 1' in message
    assert 'Security alert' in message


def test_build_message_reports_failure_without_stale_digest():
    message = notify.build_message('yahoo', 7, None)
    assert 'falhou (código 7)' in message
