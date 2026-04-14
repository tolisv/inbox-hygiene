# Email Hygiene — Design Spec
**Date:** 2026-04-13
**Status:** Approved

---

## Objetivo

Refatorar o sistema de higiene de emails para operar com 3 categorias simples, retenção de 30 dias para delete, e produzir um digest estruturado em JSON que o OpenClaw possa consumir. O pipeline para Obsidian/wiki e o processamento LLM dos emails são fases futuras e estão fora do escopo desta iteração.

---

## Escopo desta iteração

1. Refatorar `email_review.py` para 3 categorias nativas
2. Retenção mínima de 30 dias para `delete` (era 7)
3. Digest em JSON estruturado (além do `.txt` legível)
4. Migração automática do `senders.json` existente
5. Reorganização em `projects/email-hygiene/`
6. `README.md` atualizado
7. `higiene-e-mails.md` atualizado
8. `AGENT.md` — brief para o OpenClaw

**Fora do escopo:** processamento LLM dos emails digest, pipeline para Obsidian, integração com outras contas (Gmail, iCloud, ATV Partners, Ergondata).

---

## Categorias

### 3 categorias (simplificadas do sistema anterior de 5)

| Categoria | Descrição | Ação do script | Retenção |
|-----------|-----------|----------------|----------|
| `delete` | Junk puro, marketing sem valor, spam | Apaga mensagens com ≥ 30 dias de idade | 30 dias mínimos |
| `digest` | Newsletters, conteúdo de interesse, emails não-VIP não-junk | Coleta conteúdo bruto em `for_digest.txt`, nunca apaga automaticamente | Indefinido (LLM decide em fase futura) |
| `keep` | VIP, pessoal, banco crítico | Nenhuma ação | Indefinido |

### Migração do `senders.json` existente

Executada automaticamente na primeira execução:

| Categoria antiga | Categoria nova |
|-----------------|----------------|
| `delete` | `delete` |
| `summarize` | `digest` |
| `archive_reference` | `digest` |
| `needs_attention` | `keep` |
| `keep_never_auto` | `keep` |
| `keep` (legado) | `keep` |

### Detecção de keywords

A detecção de palavras-chave (fatura, vencimento, alerta, senha, itinerário, etc.) continua funcionando, mas muda de comportamento:

- **Antes:** promovia o email para `flag_attention` (mudava a ação) para qualquer sender
- **Agora:** keywords são verificadas **somente em emails `digest`** — para `delete` e `keep` não há verificação de keyword (confiamos na classificação do sender)
- Quando encontrada num email `digest`, adiciona `attention: true` e `keywords_matched: [...]` no registro do `digest.json`, sem mudar a ação sobre o email

Isso permite ao OpenClaw filtrar itens urgentes sem que o script tome decisões destrutivas baseadas em keywords. Se um sender manda tanto promo quanto faturas (ex: banco), ele deve ser classificado como `digest` ou `keep`, não `delete`.

---

## Estrutura de diretórios

```
projects/
  email-hygiene/
    scripts/
      email_review.py      # script principal (account-agnostic)
      run_yahoo.sh         # wrapper Yahoo (credenciais + data dir)
      run_gmail.sh         # placeholder futuro
      README.md
    data/
      yahoo/
        senders.json       # mapa remetente → categoria
        state.json         # last_uid, pending_senders
        digest.json        # digest estruturado (para OpenClaw consumir)
        digest.txt         # log legível (histórico acumulado)
        for_digest.txt     # conteúdo bruto de emails digest (para LLM futuro)
      gmail/               # placeholder
      icloud/              # placeholder
```

Os arquivos atualmente em `scripts/` e `data/` são movidos para `projects/email-hygiene/` durante a implementação. Paths nos scripts são atualizados.

---

## Interface do script

```bash
# Dry-run (nenhuma modificação, apenas relatório)
projects/email-hygiene/scripts/run_yahoo.sh --dry-run

# Execução normal
projects/email-hygiene/scripts/run_yahoo.sh

# Flags disponíveis
--dry-run           # report-only, não modifica nada
--days N            # janela de busca em dias (default: 360)
--min-age-delete N  # idade mínima para delete (default: 30)
--data-dir PATH     # diretório de dados da conta
```

O script é account-agnostic. As credenciais e o `--data-dir` são responsabilidade do wrapper `.sh`.

---

## Formato do digest.json

Sobrescrito a cada execução (não acumulado — o `.txt` é o histórico):

```json
{
  "run_at": "2026-04-13T07:00:00Z",
  "dry_run": false,
  "account": "yahoo",
  "summary": {
    "total_messages_scanned": 312,
    "deleted": 42,
    "digest_collected": 8,
    "kept": 3,
    "skipped": 259,
    "pending_classification": 2
  },
  "attention_items": [
    {
      "uid": 12345,
      "sender": "itau@itau.com.br",
      "subject": "Fatura disponível - vencimento 20/04",
      "date": "2026-04-12T14:30:00Z",
      "category": "digest",
      "attention": true,
      "keywords_matched": ["fatura", "vencimento"]
    }
  ],
  "pending_senders": [
    {
      "sender": "no-reply@github.com",
      "subject": "GitHub is updating Actions pricing",
      "latest_date": "2025-12-16",
      "latest_uid": 618868
    }
  ],
  "digest_items": [
    {
      "uid": 67890,
      "sender": "newsletter@example.com",
      "subject": "Weekly Productivity Digest",
      "date": "2026-04-12T08:00:00Z",
      "attention": false,
      "keywords_matched": []
    }
  ],
  "deleted_items": [
    {
      "uid": 11111,
      "sender": "promo@shop.com",
      "subject": "50% off today only!",
      "date": "2026-03-01T10:00:00Z",
      "age_days": 43
    }
  ]
}
```

---

## AGENT.md — Brief para o OpenClaw

Um arquivo `projects/email-hygiene/AGENT.md` com:

### Conteúdo

**O que o sistema faz:**
- Roda diariamente via cron contra a conta Yahoo
- Apaga junk com ≥ 30 dias de idade
- Coleta conteúdo de emails de interesse em `for_digest.txt` para processamento LLM futuro
- Nunca toca emails `keep`
- Produz `digest.json` com resultado estruturado

**Como executar:**
```bash
# Dry-run (sempre testar primeiro em nova conta)
projects/email-hygiene/scripts/run_yahoo.sh --dry-run

# Execução normal
projects/email-hygiene/scripts/run_yahoo.sh
```

**Como interpretar o digest.json:**
- `attention_items`: emails com keywords de urgência — alertar o usuário
- `pending_senders`: remetentes aguardando classificação — perguntar ao usuário quando disponível
- `summary.deleted`: quantos emails foram apagados
- `digest_items`: conteúdo coletado para processamento futuro (não urgente)

**Quando alertar o usuário:**
- `attention_items` não vazio → notificar imediatamente (fatura, vencimento, alerta)
- `pending_senders` não vazio → perguntar na próxima interação disponível
- Erro na execução do script → notificar

**O que nunca fazer sem perguntar:**
- Rodar sem `--dry-run` numa conta nova pela primeira vez
- Alterar categorias de senders em `senders.json` sem confirmação
- Apagar `for_digest.txt` ou `digest.txt` (histórico)
- Rodar contra contas que não sejam Yahoo sem instrução explícita

**Como classificar um sender pendente:**
1. Ler `digest.json` → campo `pending_senders`
2. Mostrar ao usuário: sender, subject, data
3. Aguardar resposta: delete / digest / keep
4. Atualizar `senders.json` diretamente com a classificação

---

## Fluxo de execução do script

```
1. Carregar senders.json + migrar categorias legadas
2. Conectar ao IMAP, buscar mensagens da janela (--days)
3. Buscar headers em batch (FROM, DATE, SUBJECT)
4. Identificar remetentes novos → pendentes para classificação
5. Para cada mensagem:
   a. Determinar categoria do sender
   b. Checar keywords no subject → marcar attention se encontrar
   c. Decidir ação:
      - delete + idade ≥ 30d → marcar para deleção
      - digest → coletar para for_digest.txt
      - keep → ignorar
      - não classificado → skip, adicionar a pending_senders
6. Executar ações (ou simular se --dry-run)
7. Escrever digest.json (sobrescreve) + digest.txt (acumula)
8. Salvar state.json (last_uid, pending_senders)
```

---

## Tratamento de erros

- Falha de conexão IMAP → reconecta uma vez, depois aborta com erro no log
- Sender sem classificação → adicionado a `pending_senders` no `state.json`, nunca apagado
- Keyword detectada em email de sender `delete` → keywords não são verificadas para senders `delete` (confia-se na classificação; se um sender manda emails importantes, deve ser reclassificado como `digest` ou `keep`)
- Falha ao escrever `digest.json` → abortar, não executar ações destrutivas

---

## O que não muda

- Mecanismo de reconexão IMAP (já robusto)
- Batch fetching de headers
- Atomic write do JSON (via arquivo temporário)
- Modo `--dry-run` (já implementado)
- Wrapper `.sh` com credenciais via env

---

## Fases futuras (fora deste escopo)

- **Fase 2:** OpenClaw lê `digest.json` no heartbeat, notifica e classifica senders via chat
- **Fase 3:** LLM processa `for_digest.txt`, extrai insights, grava em `raw/` do vault Obsidian
- **Fase 4:** Expansão para Gmail, iCloud, ATV Partners com políticas próprias
