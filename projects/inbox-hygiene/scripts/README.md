# Email Hygiene — Scripts

Automação de higiene do inbox Yahoo via IMAP. Classifica remetentes em 3 categorias e apaga emails por idade.

## Componentes

- **email_review.py** — Script principal (account-agnostic):
  1. Carrega `senders.json` e migra categorias legadas automaticamente
  2. Conecta ao IMAP e busca headers em batch
  3. Para cada mensagem, decide a ação: `delete`, `collect_digest`, `keep`, ou `skip`
  4. Apaga emails `delete` com ≥ 7 dias de idade
  5. Apaga emails `digest` com ≥ 14 dias de idade (subject verificado para keywords de atenção)
  6. Grava `digest.json` (estruturado, sobrescrito a cada run)
  7. Salva `state.json` com `last_uid` e `pending_senders`

- **run_yahoo.sh** — Wrapper para a conta Yahoo:
  - Carrega credenciais de `email_creds.env` (com busca em paths alternativos)
  - Define `--data-dir` apontando para `data/yahoo/`
  - Cria diretório e arquivos iniciais se necessário
  - Encaminha todos os argumentos extras para `email_review.py`

- **run_gmail.sh** — Wrapper para a conta Gmail:
  - Carrega credenciais de `gmail_creds.env` (inclui `ANTHROPIC_API_KEY`)
  - Define `--data-dir` apontando para `data/gmail/`
  - Passa `--classify-with-llm` automaticamente
  - Encaminha todos os argumentos extras para `email_review.py`

- **email_creds.env** — Credenciais IMAP (não versionado):
  ```bash
  IMAP_USER="seu_email@yahoo.com"
  IMAP_PASS="sua_senha_de_app"
  # Opcional:
  # IMAP_HOST="imap.mail.yahoo.com"
  # IMAP_PORT="993"
  ```

## Categorias

| Categoria | Descrição | Ação |
|-----------|-----------|------|
| `delete` | Junk puro, marketing sem valor | Apaga com ≥ 7 dias |
| `digest` | Newsletters, conteúdo de interesse | Apaga com ≥ 14 dias; keywords de atenção detectadas pelo subject |
| `keep` | VIP, pessoal, banco crítico | Nenhuma ação |

## Setup

1. Crie o arquivo de credenciais em `scripts/email_creds.env`
2. Dê permissão de execução ao wrapper:
   ```bash
   chmod +x scripts/run_yahoo.sh
   ```
3. (Opcional) Crie o virtualenv e instale dependências:
   ```bash
   cd projects/inbox-hygiene
   python3 -m venv .venv
   .venv/bin/pip install pytest
   ```

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

## Uso

```bash
# Dry-run (sempre testar primeiro)
projects/inbox-hygiene/scripts/run_yahoo.sh --dry-run

# Execução normal
projects/inbox-hygiene/scripts/run_yahoo.sh

# Opções disponíveis
--dry-run             # relatório apenas, não modifica nada
--days N              # janela de busca em dias (padrão: 360)
--min-age-delete N    # idade mínima para delete (padrão: 7)
--min-age-digest N    # idade mínima para apagar digest (padrão: 14)
--classify-with-llm   # classifica pending senders via Claude Haiku (requer ANTHROPIC_API_KEY)
--data-dir PATH       # diretório de dados da conta (definido pelo wrapper)
--account NAME        # nome da conta para o digest (definido pelo wrapper)
```

### Modo interativo

Na primeira execução ou ao encontrar remetentes novos, o script exibe o subject mais recente e pergunta:

```
[d]elete / [di]gest / [k]eep?
```

### Modo não-interativo (cron)

Sem TTY, remetentes não classificados vão para `pending_senders` em `state.json`. O OpenClaw os apresenta ao usuário na próxima interação disponível.

## Arquivos de dados

Todos os arquivos ficam em `data/yahoo/`:

| Arquivo | Descrição |
|---------|-----------|
| `senders.json` | Mapa remetente → categoria |
| `state.json` | `last_uid` + `pending_senders` |
| `digest.json` | Digest estruturado (sobrescrito a cada run) |
| `deprecated/` | Arquivos descontinuados — ver `deprecated/DEPRECATED.md` |

## Testes

```bash
cd projects/inbox-hygiene
.venv/bin/pytest tests/ -v
```

## Integração com cron (via OpenClaw)

```cron
0 7 * * * /path/to/projects/inbox-hygiene/scripts/run_yahoo.sh >> /tmp/email_hygiene.log 2>&1
```

Após a execução, o OpenClaw lê `digest.json` e notifica o usuário se houver `attention_items` ou `pending_senders`.
