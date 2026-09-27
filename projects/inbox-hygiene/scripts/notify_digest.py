#!/usr/bin/env python3
"""Send a deterministic Telegram summary for an inbox-hygiene run."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


OPENCLAW = Path('/home/tolis/.npm-global/bin/openclaw')
TELEGRAM_TARGET = '7613219749'


def load_fresh_digest(path: Path, started_at: int) -> dict | None:
    if not path.is_file() or path.stat().st_mtime < started_at - 1:
        return None
    with path.open(encoding='utf-8') as handle:
        return json.load(handle)


def build_message(account: str, exit_code: int, digest: dict | None) -> str:
    label = 'Gmail' if account == 'gmail' else 'Yahoo'
    if exit_code != 0:
        return (
            f'⚠️ Higiene {label}: execução falhou (código {exit_code}). '
            f'Nenhum resumo novo foi aceito; consulte o journal do serviço.'
        )
    if digest is None:
        return (
            f'⚠️ Higiene {label}: o script terminou, mas não produziu um '
            f'digest novo. Consulte o journal do serviço.'
        )

    summary = digest.get('summary') or {}
    attention = digest.get('attention_items') or []
    pending = digest.get('pending_senders') or []
    classifications = digest.get('llm_classifications') or []
    accepted = sum(1 for item in classifications if item.get('accepted', True))
    review = sum(1 for item in classifications if not item.get('accepted', True))
    mode = 'dry-run; nenhuma mensagem alterada' if digest.get('dry_run') else 'execução normal'

    lines = [
        f'✅ Higiene {label}: {mode}.',
        (
            f"Lidas: {summary.get('total_messages_scanned', 0)} | "
            f"apagadas: {summary.get('deleted', 0)} | "
            f"digest: {summary.get('digest_seen', 0)} "
            f"(apagadas: {summary.get('digest_deleted', 0)}) | "
            f"mantidas: {summary.get('kept', 0)}"
        ),
        (
            f"Pendentes: {summary.get('pending_classification', len(pending))} | "
            f"JEV aceitas: {accepted} | revisão: {review} | "
            f"atenção: {len(attention)}"
        ),
    ]
    if attention:
        subjects = [str(item.get('subject') or '(sem assunto)')[:120] for item in attention[:3]]
        lines.append('⚠️ Atenção: ' + ' · '.join(subjects))
    return '\n'.join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('account', choices=('gmail', 'yahoo'))
    parser.add_argument('--exit-code', type=int, required=True)
    parser.add_argument('--started-at', type=int, required=True)
    parser.add_argument('--data-dir', type=Path, required=True)
    parser.add_argument('--dry-run', action='store_true', help='Print instead of sending')
    args = parser.parse_args()

    digest = load_fresh_digest(args.data_dir / 'digest.json', args.started_at)
    message = build_message(args.account, args.exit_code, digest)
    if args.dry_run:
        print(message)
        return 0

    command = [
        str(OPENCLAW), 'message', 'send',
        '--channel', 'telegram',
        '--target', TELEGRAM_TARGET,
        '--message', message,
    ]
    completed = subprocess.run(command, check=False)
    return completed.returncode


if __name__ == '__main__':
    sys.exit(main())
