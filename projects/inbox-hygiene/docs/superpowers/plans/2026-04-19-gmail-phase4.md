# Gmail Phase 4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expandir inbox-hygiene para Gmail pessoal com wrapper `run_gmail.sh` e classificação automática de senders pendentes via Claude Haiku.

**Architecture:** O script `email_review.py` já é account-agnostic. Esta fase adiciona: (1) wrapper `run_gmail.sh` análogo ao Yahoo, (2) flag `--classify-with-llm` que aciona `classify_pending_with_llm()` antes de finalizar o run, (3) resultado da classificação LLM exposto em `digest.json` para o OpenClaw apresentar ao usuário.

**Tech Stack:** Python 3, imaplib (existente), `anthropic` SDK (novo), bash, pytest.

---

## Mapa de arquivos

| Arquivo | Ação | Responsabilidade |
|---------|------|-----------------|
| `scripts/run_gmail.sh` | Criar | Wrapper Gmail: carrega `gmail_creds.env`, passa `--classify-with-llm` |
| `scripts/gmail_creds.env` | Criar (não versionado) | Credenciais IMAP Gmail + `ANTHROPIC_API_KEY` |
| `scripts/email_review.py` | Modificar | Adicionar `--classify-with-llm`, `classify_pending_with_llm()`, campo `llm_classifications` no digest |
| `tests/test_email_review.py` | Modificar | Testes para `classify_pending_with_llm()` |
| `.gitignore` | Modificar | Adicionar `scripts/gmail_creds.env` |
| `AGENT.md` | Modificar | Seção Gmail: como executar, interpretar `llm_classifications` |
| `scripts/README.md` | Modificar | Documentar `run_gmail.sh` e flag `--classify-with-llm` |

---

## Task 1: Instalar dependência `anthropic` no virtualenv

**Files:**
- Modify: `.venv` (via pip)

- [ ] **Step 1: Instalar o SDK**

```bash
cd /home/tolis/.openclaw/workspace/projects/inbox-hygiene
.venv/bin/pip install anthropic
```

Saída esperada: `Successfully installed anthropic-...`

- [ ] **Step 2: Verificar instalação**

```bash
.venv/bin/python -c "import anthropic; print(anthropic.__version__)"
```

Saída esperada: número de versão sem erro.

- [ ] **Step 3: Commit (requirements implícito via .venv, sem requirements.txt — só verificação)**

```bash
git add -p  # nada a commitar aqui; .venv está no .gitignore
```

Nota: o projeto não tem `requirements.txt`. Não criar agora — fora do escopo.

---

## Task 2: Atualizar `.gitignore` para `gmail_creds.env`

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Adicionar entrada**

Abrir `.gitignore` e adicionar linha após `scripts/email_creds.env`:

```
scripts/email_creds.env
scripts/gmail_creds.env
```

O arquivo completo deve ficar:

```
.venv/
venv/
*.pyc
__pycache__/
scripts/email_creds.env
scripts/gmail_creds.env
```

- [ ] **Step 2: Verificar que git não rastreia o arquivo**

```bash
git check-ignore -v scripts/gmail_creds.env
```

Saída esperada: `scripts/gmail_creds.env`

- [ ] **Step 3: Commit**

```bash
git add .gitignore
git commit -m "chore: add gmail_creds.env to .gitignore"
```

---

## Task 3: Criar `scripts/run_gmail.sh`

**Files:**
- Create: `scripts/run_gmail.sh`

- [ ] **Step 1: Criar o arquivo**

Conteúdo completo de `scripts/run_gmail.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DATA_DIR="$PROJECT_DIR/data/gmail"
CREDS_FILE="$SCRIPT_DIR/gmail_creds.env"
if [[ ! -f "$CREDS_FILE" ]]; then
    for candidate in \
        "$PROJECT_DIR/../../scripts/gmail_creds.env" \
        "$PROJECT_DIR/../../gmail_creds.env"
    do
        if [[ -f "$candidate" ]]; then
            CREDS_FILE="$candidate"
            break
        fi
    done
fi

if [[ ! -f "$CREDS_FILE" ]]; then
    echo "Error: credentials file not found: $CREDS_FILE" >&2
    exit 1
fi

set -a
source "$CREDS_FILE"
set +a

mkdir -p "$DATA_DIR"
chmod 700 "$DATA_DIR"

if [[ ! -f "$DATA_DIR/state.json" ]]; then
    echo '{"last_uid": 0}' > "$DATA_DIR/state.json"
fi

if [[ ! -f "$DATA_DIR/senders.json" ]]; then
    echo '{}' > "$DATA_DIR/senders.json"
fi

exec python3 "$SCRIPT_DIR/email_review.py" \
    --data-dir "$DATA_DIR" \
    --account "gmail" \
    --classify-with-llm \
    "$@"
```

- [ ] **Step 2: Tornar executável**

```bash
chmod +x scripts/run_gmail.sh
```

- [ ] **Step 3: Verificar sintaxe bash**

```bash
bash -n scripts/run_gmail.sh
```

Saída esperada: nenhuma saída (sem erros).

- [ ] **Step 4: Commit**

```bash
git add scripts/run_gmail.sh
git commit -m "feat: add run_gmail.sh wrapper"
```

---

## Task 4: Escrever testes para `classify_pending_with_llm()`

**Files:**
- Modify: `tests/test_email_review.py`

Os testes usam `unittest.mock` para não fazer chamadas reais à API.

- [ ] **Step 1: Adicionar imports no topo do arquivo de testes**

Verificar se `unittest.mock` já está importado. Se não, adicionar após os imports existentes:

```python
from unittest.mock import patch, MagicMock
```

- [ ] **Step 2: Adicionar classe de testes ao final de `tests/test_email_review.py`**

```python
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
```

- [ ] **Step 3: Rodar os testes novos para confirmar que falham (função não existe ainda)**

```bash
cd /home/tolis/.openclaw/workspace/projects/inbox-hygiene
.venv/bin/pytest tests/test_email_review.py::TestClassifyPendingWithLlm -v
```

Saída esperada: `AttributeError: module 'email_review' has no attribute 'classify_pending_with_llm'`

---

## Task 5: Implementar `classify_pending_with_llm()` em `email_review.py`

**Files:**
- Modify: `scripts/email_review.py`

- [ ] **Step 1: Adicionar import `anthropic` no bloco de imports (lazy, para não quebrar sem SDK)**

Localizar o bloco de imports no topo de `email_review.py` (linha ~14) e adicionar após `import argparse`:

```python
try:
    import anthropic as _anthropic
except ImportError:
    _anthropic = None
```

- [ ] **Step 2: Adicionar função `classify_pending_with_llm()` antes da seção `# Argument parsing`**

Inserir após a função `collect_digest` (que foi removida) e antes de `# ---------------------------------------------------------------------------\n# Argument parsing`:

```python
# ---------------------------------------------------------------------------
# LLM classification
# ---------------------------------------------------------------------------

def classify_pending_with_llm(pending_senders, api_key):
    """Classify pending senders using Claude Haiku.

    Args:
        pending_senders: list of dicts with keys sender, subject, latest_date, latest_uid
        api_key: Anthropic API key string

    Returns:
        dict mapping sender -> category ('delete'|'digest'|'keep')
        Falls back to 'digest' for any sender with unknown/missing/invalid category.
    """
    if not pending_senders:
        return {}

    if _anthropic is None:
        print('Warning: anthropic SDK not installed — skipping LLM classification.',
              file=sys.stderr)
        return {}

    sender_lines = '\n'.join(
        f"- {p['sender']} | subject: {p.get('subject', '')} | date: {p.get('latest_date', '')}"
        for p in pending_senders
    )

    prompt = f"""You are classifying email senders for an inbox hygiene system.
For each sender, suggest one of: delete, digest, keep.

Rules:
- delete: clearly junk — marketing, promotions, newsletters with no value, spam
- digest: newsletters or content of interest, transactional emails, services used
- keep: personal contacts, banks, critical services, VIP senders
- When in doubt, prefer digest or keep over delete
- Base your decision on sender address, domain, and most recent subject

Respond with a JSON object only, no explanation: {{"sender@domain.com": "category", ...}}

Senders to classify:
{sender_lines}"""

    client = _anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model='claude-haiku-4-5-20251001',
        max_tokens=1024,
        messages=[{'role': 'user', 'content': prompt}],
    )

    raw = response.content[0].text.strip()

    try:
        suggestions = json.loads(raw)
    except (json.JSONDecodeError, IndexError):
        print(f'Warning: LLM returned invalid JSON — falling back to digest for all senders.',
              file=sys.stderr)
        return {p['sender']: 'digest' for p in pending_senders}

    result = {}
    for p in pending_senders:
        sender = p['sender']
        category = suggestions.get(sender, 'digest')
        if category not in CATEGORIES:
            category = 'digest'
        result[sender] = category

    return result
```

- [ ] **Step 3: Rodar os testes novos para confirmar que passam**

```bash
.venv/bin/pytest tests/test_email_review.py::TestClassifyPendingWithLlm -v
```

Saída esperada: `5 passed`

- [ ] **Step 4: Rodar todos os testes para confirmar que nada quebrou**

```bash
.venv/bin/pytest tests/ -v
```

Saída esperada: todos os testes existentes + 5 novos passando (≥ 39 passed).

- [ ] **Step 5: Commit**

```bash
git add scripts/email_review.py tests/test_email_review.py
git commit -m "feat: add classify_pending_with_llm() with Haiku integration"
```

---

## Task 6: Adicionar `--classify-with-llm` ao CLI e integrar no `main()`

**Files:**
- Modify: `scripts/email_review.py`

- [ ] **Step 1: Adicionar argumento em `parse_args()`**

Localizar o bloco `parse_args()` e adicionar após `--min-age-digest`:

```python
    p.add_argument('--classify-with-llm', action='store_true', default=False,
                   help='Classify pending senders using Claude Haiku (requires ANTHROPIC_API_KEY)')
```

- [ ] **Step 2: Integrar classificação LLM em `main()` — fase 2 (após coletar `pending_senders`)**

Localizar o bloco que inicia com `# --- Phase 3: Determine action per message` em `main()`. Logo antes dele, inserir o bloco de classificação LLM:

```python
    # --- Phase 2b: LLM classification of pending senders (optional) ----------
    llm_classifications = []
    if args.classify_with_llm and pending_senders:
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            print('Warning: --classify-with-llm set but ANTHROPIC_API_KEY not found — skipping.',
                  file=sys.stderr)
        else:
            print(f'Classifying {len(pending_senders)} pending sender(s) with LLM…')
            suggestions = classify_pending_with_llm(pending_senders, api_key)
            for p in pending_senders:
                sender = p['sender']
                if sender in suggestions:
                    category = suggestions[sender]
                    senders_map[sender] = category
                    llm_classifications.append({
                        'sender': sender,
                        'category': category,
                        'subject': p.get('subject', ''),
                    })
                    print(f'  {sender} → {category}')
            if not dry_run and llm_classifications:
                # Mark entries as LLM-classified in senders.json
                # senders_map stores category strings; we write with llm_classified flag
                # using a separate tracking set to avoid changing the map structure
                atomic_write_json(senders_file, senders_map)
                print(f'  Saved {len(llm_classifications)} classification(s) to senders.json.')
            # Clear pending_senders for senders that got classified
            classified_senders = {c['sender'] for c in llm_classifications}
            pending_senders = [p for p in pending_senders if p['sender'] not in classified_senders]
```

- [ ] **Step 3: Passar `llm_classifications` para o `Digest` — atualizar `set_pending_senders` call**

Localizar no `main()` a linha:
```python
    digest.set_pending_senders(pending_senders)
```
E adicionar logo após:
```python
    digest.set_llm_classifications(llm_classifications)
```

- [ ] **Step 4: Adicionar `set_llm_classifications()` e campo `llm_classifications` no `Digest`**

Na classe `Digest`, após `set_pending_senders()`:

```python
    def set_llm_classifications(self, classifications: list):
        self._llm_classifications = classifications
```

E inicializar no `__init__`:

```python
        self._llm_classifications = []
```

E adicionar campo no `write_json()`, após `'pending_senders'`:

```python
            'llm_classifications': self._llm_classifications,
```

- [ ] **Step 5: Rodar todos os testes**

```bash
.venv/bin/pytest tests/ -v
```

Saída esperada: todos passando (≥ 39 passed).

- [ ] **Step 6: Commit**

```bash
git add scripts/email_review.py
git commit -m "feat: wire --classify-with-llm flag into main(), expose llm_classifications in digest.json"
```

---

## Task 7: Atualizar `AGENT.md` para duas contas

**Files:**
- Modify: `AGENT.md`

- [ ] **Step 1: Adicionar seção Gmail ao `AGENT.md`**

Após a seção `## Como executar`, adicionar:

```markdown
## Conta Gmail

```bash
# Dry-run Gmail
projects/inbox-hygiene/scripts/run_gmail.sh --dry-run

# Execução normal Gmail
projects/inbox-hygiene/scripts/run_gmail.sh
```

O wrapper carrega `scripts/gmail_creds.env` (com `ANTHROPIC_API_KEY`) e passa `--classify-with-llm` automaticamente.

### Como interpretar `llm_classifications` no digest.json

Após um run Gmail, `digest.json` pode conter:

```json
"llm_classifications": [
  {"sender": "spam@promo.com", "category": "delete", "subject": "Big Sale!"},
  {"sender": "news@sub.com",   "category": "digest", "subject": "Weekly digest"}
]
```

Apresentar este resumo ao usuário após o run. O usuário pode corrigir qualquer entrada dizendo "muda spam@promo.com para digest" — atualizar `data/gmail/senders.json` diretamente.

### O que nunca fazer sem perguntar (Gmail)

- Rodar sem `--dry-run` na primeira vez numa conta nova
- Rodar `--classify-with-llm` sem `ANTHROPIC_API_KEY` configurada
- Alterar categorias em `data/gmail/senders.json` sem confirmação do usuário
```

- [ ] **Step 2: Commit**

```bash
git add AGENT.md
git commit -m "docs: update AGENT.md with Gmail section and llm_classifications"
```

---

## Task 8: Atualizar `scripts/README.md`

**Files:**
- Modify: `scripts/README.md`

- [ ] **Step 1: Adicionar `run_gmail.sh` na seção Componentes**

Após a descrição de `run_yahoo.sh`, adicionar:

```markdown
- **run_gmail.sh** — Wrapper para a conta Gmail:
  - Carrega credenciais de `gmail_creds.env` (inclui `ANTHROPIC_API_KEY`)
  - Define `--data-dir` apontando para `data/gmail/`
  - Passa `--classify-with-llm` automaticamente
  - Encaminha todos os argumentos extras para `email_review.py`
```

- [ ] **Step 2: Adicionar `--classify-with-llm` na seção de opções**

Na seção `## Uso`, adicionar linha na lista de opções:

```
--classify-with-llm   # classifica pending senders via Claude Haiku (requer ANTHROPIC_API_KEY)
```

- [ ] **Step 3: Adicionar seção de setup Gmail**

Após a seção `## Setup`, adicionar:

```markdown
### Setup Gmail

Além das credenciais IMAP, o Gmail usa classificação LLM. Criar `scripts/gmail_creds.env`:

```bash
IMAP_HOST="imap.gmail.com"
IMAP_PORT="993"
IMAP_USER="seu@gmail.com"
IMAP_PASS="xxxx xxxx xxxx xxxx"   # senha de app (16 chars), não a senha da conta
ANTHROPIC_API_KEY="sk-ant-..."
```

Ver `docs/superpowers/specs/2026-04-19-gmail-phase4-design.md` para o passo a passo de como ativar IMAP e gerar senha de app no Gmail.
```

- [ ] **Step 4: Commit**

```bash
git add scripts/README.md
git commit -m "docs: update README.md with run_gmail.sh and --classify-with-llm"
```

---

## Task 9: Criar `scripts/gmail_creds.env` (template)

**Files:**
- Create: `scripts/gmail_creds.env.template` (versionado como template, sem dados reais)

- [ ] **Step 1: Criar arquivo template**

Conteúdo de `scripts/gmail_creds.env.template`:

```bash
# Gmail IMAP credentials
# Copy to gmail_creds.env and fill in real values
# See docs/superpowers/specs/2026-04-19-gmail-phase4-design.md for setup instructions

IMAP_HOST="imap.gmail.com"
IMAP_PORT="993"
IMAP_USER="seu@gmail.com"
IMAP_PASS="xxxx xxxx xxxx xxxx"   # App password (16 chars) from myaccount.google.com/apppasswords

# Anthropic API key — required for --classify-with-llm
ANTHROPIC_API_KEY="sk-ant-..."
```

- [ ] **Step 2: Verificar que o arquivo real (sem .template) está ignorado**

```bash
touch scripts/gmail_creds.env
git status scripts/gmail_creds.env
```

Saída esperada: `scripts/gmail_creds.env` não aparece como untracked (está no .gitignore).

```bash
rm scripts/gmail_creds.env
```

- [ ] **Step 3: Commit**

```bash
git add scripts/gmail_creds.env.template
git commit -m "docs: add gmail_creds.env.template"
```

---

## Task 10: Push e dry-run de verificação

**Files:** nenhum novo

- [ ] **Step 1: Rodar todos os testes uma última vez**

```bash
cd /home/tolis/.openclaw/workspace/projects/inbox-hygiene
.venv/bin/pytest tests/ -v
```

Saída esperada: todos passando, nenhuma falha.

- [ ] **Step 2: Push para origin**

```bash
git push origin master
```

- [ ] **Step 3: Verificar que `gmail_creds.env` não foi commitado**

```bash
git log --oneline --name-only | head -30
```

Confirmar que `scripts/gmail_creds.env` não aparece em nenhum commit.

- [ ] **Step 4: (Quando o usuário tiver configurado as credenciais) Dry-run Gmail**

```bash
projects/inbox-hygiene/scripts/run_gmail.sh --dry-run
```

Saída esperada: conexão IMAP bem-sucedida, mensagens listadas, nenhuma modificação feita, classificações LLM sugeridas mas não aplicadas.

---

## Self-review

**Spec coverage:**
- ✅ `run_gmail.sh` — Task 3
- ✅ `.gitignore` para `gmail_creds.env` — Task 2
- ✅ `--classify-with-llm` flag — Task 6
- ✅ `classify_pending_with_llm()` — Task 5
- ✅ Testes para a função — Task 4
- ✅ `llm_classifications` em `digest.json` — Task 6
- ✅ `AGENT.md` atualizado — Task 7
- ✅ `README.md` atualizado — Task 8
- ✅ Template de credenciais — Task 9
- ✅ `data/gmail/` criado automaticamente pelo wrapper — Task 3 (mkdir -p no script)

**Placeholders:** nenhum encontrado.

**Type consistency:** `classify_pending_with_llm(pending_senders: list, api_key: str) -> dict` — usado consistentemente nas Tasks 4 e 5. Campo `llm_classifications` é `list[dict]` com chaves `sender`, `category`, `subject` — consistente entre Task 6 e AGENT.md (Task 7).
