# Fase 4 — Gmail Pessoal: Design Spec

**Data:** 2026-04-19
**Status:** Aprovado

---

## Objetivo

Expandir o sistema de higiene de emails para a conta Gmail pessoal do usuário, mantendo o mesmo script Python account-agnostic (`email_review.py`) e adicionando classificação automática de senders pendentes via LLM (Claude Haiku).

---

## Escopo desta fase

1. Novo wrapper `scripts/run_gmail.sh`
2. Setup de credenciais Gmail via senha de app IMAP
3. Dados isolados em `data/gmail/`
4. Novo modo `--classify-with-llm` em `email_review.py`
5. Nova função `classify_pending_with_llm()` com testes
6. `AGENT.md` atualizado para operar duas contas
7. `.gitignore` atualizado para `gmail_creds.env`

**Fora do escopo:** iCloud, ATV Partners, Ergondata, Fase 3 (Obsidian/LLM pipeline).

---

## Setup Gmail (passo a passo para o usuário)

O Gmail IMAP usa senha de app — igual ao Yahoo, sem OAuth2.

### 1. Ativar IMAP no Gmail

1. Abrir Gmail → `Settings (⚙️)` → `See all settings`
2. Aba `Forwarding and POP/IMAP`
3. Em `IMAP access` → selecionar `Enable IMAP`
4. Clicar `Save Changes`

### 2. Ativar verificação em 2 etapas (obrigatório para senhas de app)

1. Acessar `myaccount.google.com/security`
2. Em `How you sign in to Google` → `2-Step Verification` → ativar

### 3. Gerar senha de app

1. Acessar `myaccount.google.com/apppasswords`
2. Nome: `inbox-hygiene`
3. Clicar `Create`
4. Copiar a senha de 16 caracteres gerada

### 4. Criar arquivo de credenciais

Criar `scripts/gmail_creds.env` (não versionado):

```bash
IMAP_HOST="imap.gmail.com"
IMAP_PORT="993"
IMAP_USER="seu@gmail.com"
IMAP_PASS="xxxx xxxx xxxx xxxx"
ANTHROPIC_API_KEY="sk-ant-..."
```

---

## Política de retenção Gmail

Igual ao Yahoo:

| Categoria | Retenção |
|-----------|----------|
| `delete`  | 7 dias   |
| `digest`  | 14 dias  |
| `keep`    | Nunca    |

---

## Classificação LLM de senders pendentes

### Quando ativa

O wrapper `run_gmail.sh` passa `--classify-with-llm`. O modo **não é ativado** para Yahoo.

### Fluxo

1. Script coleta `pending_senders` normalmente (senders sem classificação)
2. Se `--classify-with-llm` e `ANTHROPIC_API_KEY` estão presentes:
   - Monta lista de senders com `sender`, `domain`, `subject mais recente`
   - Chama `claude-haiku-4-5` com prompt conservador (ver abaixo)
   - Recebe JSON com sugestão por sender: `{"sender@foo.com": "delete", ...}`
   - Aplica classificações em `senders.json` com flag `"llm_classified": true`
   - `pending_senders` fica vazio após o run
3. `digest.json` inclui campo `llm_classifications` com lista do que foi classificado

### Prompt (conservador)

```
You are classifying email senders for an inbox hygiene system.
For each sender, suggest one of: delete, digest, keep.

Rules:
- delete: clearly junk — marketing, promotions, newsletters with no value, spam
- digest: newsletters or content of interest, transactional emails, services used
- keep: personal contacts, banks, critical services, VIP senders
- When in doubt, prefer digest or keep over delete
- Base your decision on sender address, domain, and most recent subject

Respond with a JSON object: {"sender@domain.com": "category", ...}

Senders to classify:
{sender_list}
```

### Modelo

`claude-haiku-4-5-20251001` — barato e suficiente para classificação de senders por subject/domain.

### Revisão pelo usuário

O OpenClaw apresenta `llm_classifications` do `digest.json` ao usuário após o run Gmail, listando o que foi classificado automaticamente. O usuário pode corrigir qualquer entrada editando `senders.json` via chat com o OpenClaw.

---

## Componentes

### Novo: `scripts/run_gmail.sh`

```bash
#!/bin/bash
# Wrapper Gmail — carrega credenciais e chama email_review.py
# com --data-dir data/gmail/ --account gmail --classify-with-llm
```

Mesma lógica de fallback de credenciais do `run_yahoo.sh`.

### Modificado: `scripts/email_review.py`

- Novo argumento CLI: `--classify-with-llm` (flag booleana, default: off)
- Nova função: `classify_pending_with_llm(pending_senders, api_key) -> dict`
  - Input: lista de dicts `{sender, subject, latest_date}`
  - Output: dict `{sender: category}`
  - Isolada e testável sem IMAP
- `digest.json` ganha campo `llm_classifications: [{sender, category, subject}]`
- Dependência opcional: `anthropic` SDK

### Novo: `data/gmail/`

Criado automaticamente no primeiro run. Estrutura idêntica ao `data/yahoo/`:

```
data/gmail/
  senders.json   # começa vazio, populado pelo LLM no primeiro run
  state.json     # last_uid, pending_senders
  digest.json    # digest estruturado (sobrescrito a cada run)
```

---

## Testes

- `test_classify_pending_with_llm_mock()` — mock da API, verifica parse do JSON retornado
- `test_classify_pending_with_llm_invalid_response()` — resposta malformada → fallback para `digest`
- `test_classify_pending_noop_without_flag()` — sem `--classify-with-llm`, função não é chamada
- Testes existentes: nenhum quebra (flag default off)

---

## Segurança

- `gmail_creds.env` adicionado ao `.gitignore`
- `ANTHROPIC_API_KEY` carregado via env var pelo wrapper, nunca hardcoded
- Classificações LLM gravam `llm_classified: true` para rastreabilidade

---

## Integração OpenClaw

`AGENT.md` receberá seção nova:

- Como executar o wrapper Gmail: `scripts/run_gmail.sh --dry-run` / `scripts/run_gmail.sh`
- Como interpretar `llm_classifications` no `digest.json`
- Instrução: após run Gmail, apresentar resumo das classificações automáticas ao usuário
- Nunca rodar `--classify-with-llm` sem `ANTHROPIC_API_KEY` configurada

---

## Fases futuras (não nesta spec)

- **Fase 5:** Expansão para iCloud, ATV Partners
- **Fase 3 (retomada):** LLM processa emails `digest` de senders premium → Obsidian
