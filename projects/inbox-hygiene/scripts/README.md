# Email Hygiene — Scripts

Automação de higiene do inbox Yahoo via IMAP. Classifica remetentes em 3 categorias, apaga junk com ≥ 30 dias, e produz um digest estruturado para o OpenClaw consumir.

## Componentes

- **email_review.py** — Script principal (account-agnostic):
  1. Carrega `senders.json` e migra categorias legadas automaticamente
  2. Conecta ao IMAP e busca headers em batch
  3. Para cada mensagem, decide a ação: `delete`, `collect_digest`, `keep`, ou `skip`
  4. Apaga mensagens `delete` com ≥ 30 dias de idade
  5. Coleta conteúdo de emails `digest` em `for_digest.txt`
  6. Grava `digest.json` (estruturado, sobrescrito) e `digest.txt` (histórico acumulado)
  7. Salva `state.json` com `last_uid` e `pending_senders`

- **run_yahoo.sh** — Wrapper para a conta Yahoo:
  - Carrega credenciais de `email_creds.env`
  - Define `--data-dir` apontando para `data/yahoo/`
  - Cria diretório e arquivos iniciais se necessário
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
| `delete` | Junk puro, marketing sem valor | Apaga com ≥ 30 dias de idade |
| `digest` | Newsletters, conteúdo de interesse | Coleta em `for_digest.txt`, nunca apaga |
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

## Uso

```bash
# Dry-run (sempre testar primeiro)
projects/inbox-hygiene/scripts/run_yahoo.sh --dry-run

# Execução normal
projects/inbox-hygiene/scripts/run_yahoo.sh

# Opções disponíveis
--dry-run             # relatório apenas, não modifica nada
--days N              # janela de busca em dias (padrão: 360)
--min-age-delete N    # idade mínima para delete (padrão: 30)
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
| `digest.txt` | Histórico legível (acumulado) |
| `for_digest.txt` | Conteúdo bruto de emails `digest` para LLM futuro |

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
