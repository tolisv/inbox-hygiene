# Email Hygiene — Agent Brief

This document tells OpenClaw how to operate the email hygiene system.

---

## O que o sistema faz

- Roda diariamente via cron contra a conta Yahoo
- Apaga junk com ≥ 30 dias de idade (`delete` senders)
- Coleta conteúdo de emails de interesse em `data/yahoo/for_digest.txt` para processamento LLM futuro
- Nunca toca emails `keep` (VIP, pessoal, banco crítico)
- Produz `data/yahoo/digest.json` com resultado estruturado a cada execução

---

## Como executar

```bash
# Dry-run (sempre testar primeiro em conta nova)
projects/inbox-hygiene/scripts/run_yahoo.sh --dry-run

# Execução normal
projects/inbox-hygiene/scripts/run_yahoo.sh
```

O wrapper `run_yahoo.sh` carrega as credenciais de `scripts/email_creds.env` e passa `--data-dir` e `--account` automaticamente.

---

## Como interpretar o digest.json

Arquivo: `projects/inbox-hygiene/data/yahoo/digest.json`  
Sobrescrito a cada execução.

| Campo | O que significa |
|-------|----------------|
| `attention_items` | Emails com keywords de urgência (fatura, vencimento, alerta...) — alertar o usuário |
| `pending_senders` | Remetentes aguardando classificação — perguntar ao usuário |
| `summary.deleted` | Quantos emails foram apagados nesta execução |
| `summary.pending_classification` | Quantos remetentes novos aguardam decisão |
| `digest_items` | Conteúdo coletado para processamento futuro (não urgente) |
| `deleted_items` | Lista de emails apagados nesta execução |

---

## Quando alertar o usuário

- `attention_items` não vazio → notificar imediatamente (fatura, vencimento, alerta de segurança)
- `pending_senders` não vazio → perguntar na próxima interação disponível
- Erro na execução do script → notificar

---

## Como classificar um sender pendente

1. Ler `digest.json` → campo `pending_senders`
2. Mostrar ao usuário: sender, subject, data mais recente
3. Aguardar resposta: `delete` / `digest` / `keep`
4. Atualizar `data/yahoo/senders.json` diretamente com a classificação

### Categorias

| Categoria | Significado | Ação do script |
|-----------|-------------|----------------|
| `delete` | Junk puro, marketing sem valor | Apaga com ≥ 30 dias de idade |
| `digest` | Newsletters, conteúdo de interesse | Coleta em `for_digest.txt`, nunca apaga |
| `keep` | VIP, pessoal, banco crítico | Nenhuma ação |

---

## O que nunca fazer sem perguntar

- Rodar sem `--dry-run` numa conta nova pela primeira vez
- Alterar categorias de senders em `senders.json` sem confirmação do usuário
- Apagar `for_digest.txt` ou `digest.txt` (histórico acumulado)
- Rodar contra contas que não sejam Yahoo sem instrução explícita do usuário
- Usar `--min-age-delete` menor que 30 dias

---

## Arquivos do projeto

```
projects/inbox-hygiene/
  scripts/
    email_review.py      # script principal (account-agnostic)
    run_yahoo.sh         # wrapper Yahoo (credenciais + data dir)
    email_creds.env      # credenciais IMAP (não versionado)
    README.md            # documentação técnica
  data/
    yahoo/
      senders.json       # mapa remetente → categoria
      state.json         # last_uid, pending_senders
      digest.json        # digest estruturado (OpenClaw consome)
      digest.txt         # log legível (histórico acumulado)
      for_digest.txt     # conteúdo bruto para LLM futuro
  tests/
    test_email_review.py
  AGENT.md               # este arquivo
  higiene-e-mails.md     # notas e decisões do projeto
```

---

## Fases futuras

- **Fase 2:** OpenClaw lê `digest.json` no heartbeat, notifica e classifica senders via chat
- **Fase 3:** LLM processa `for_digest.txt`, extrai insights, grava em `raw/` do vault Obsidian no Mac Studio
- **Fase 4:** Expansão para Gmail, iCloud, ATV Partners com políticas próprias
