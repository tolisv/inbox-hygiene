# Higiene de E-mails

## Objetivo

Criar um sistema de higiene de e-mails que reduza carga mental e mantenha as caixas organizadas sem gerar a sensação de perda de algo importante.

O projeto deve priorizar confiança, rastreabilidade e revisão fácil, e não apenas limpeza agressiva da inbox.

## Problema que o projeto resolve

Hoje existe excesso de e-mails promocionais, informativos e operacionais misturados com mensagens que podem exigir atenção ou servir como registro futuro.

A solução precisa equilibrar quatro necessidades:

1. Remover lixo e ruído
2. Preservar o que pode ser útil como referência
3. Destacar o que exige ação
4. Reduzir a ansiedade de "ter perdido algo importante"

## Princípios

- Limpeza sem perda de confiança
- Automação gradual, começando em modo seguro
- Regras diferentes por conta de e-mail
- Classificação por risco e utilidade, não apenas por remetente
- Inbox como espaço de curto prazo, não como arquivo histórico
- Tudo que for apagado, resumido, arquivado ou sinalizado deve ser rastreável

## Contexto atual

### Conta Yahoo

A conta Yahoo é usada principalmente como caixa de junk mail, propagandas e newsletters. Ainda recebe alguns e-mails importantes ou úteis:
- Latam, Apple, Itaú
- Newsletters de interesse (produtividade, economia, geopolítica, culinária)
- Notificações e comprovantes
- Marketing tolerado (Backroads, Condé Nast) — continua por escolha, mas não é prioridade

### Outras contas no escopo futuro

- Gmail pessoal
- iCloud
- ATV Partners
- Ergondata (sem automação destrutiva ainda — exige política de negócio aprovada)

---

## Sistema atual (implementado em Abril 2026)

### 3 categorias

Simplificamos de 5 para 3 categorias:

| Categoria | Descrição | Ação do script | Retenção |
|-----------|-----------|----------------|----------|
| `delete` | Junk puro, marketing sem valor, spam | Apaga com ≥ 7 dias | 7 dias |
| `digest` | Newsletters, conteúdo de interesse, não-VIP não-junk | Apaga com ≥ 14 dias; subject verificado para keywords de atenção | 14 dias |
| `keep` | VIP, pessoal, banco crítico | Nenhuma ação | Indefinida |

### Migração das categorias legadas

| Categoria antiga | Categoria nova |
|-----------------|----------------|
| `delete` | `delete` |
| `summarize` | `digest` |
| `archive_reference` | `digest` |
| `needs_attention` | `keep` |
| `keep_never_auto` | `keep` |

A migração é feita automaticamente na primeira execução com o novo script.

### Detecção de keywords

Palavras-chave (fatura, vencimento, alerta, senha, itinerário, etc.) são verificadas **somente em emails `digest`**:
- Para `delete` e `keep`, não há verificação de keyword, confia-se na classificação do remetente
- Quando encontrada num email `digest`, adiciona `attention: true` no `digest.json` sem mudar a ação
- A detecção usa fronteiras de palavra/expressão, para evitar falsos positivos por substring acidental
- Isso permite ao OpenClaw filtrar itens urgentes sem que o script tome decisões destrutivas

### Retenção

- `delete`: 7 dias
- `digest`: 14 dias
- `keep`: sem deleção automática

---

## Integração com OpenClaw

O OpenClaw é o agente autônomo que opera este sistema diariamente:

1. Executa `run_yahoo.sh` via cron (7h da manhã)
2. Lê `data/yahoo/digest.json` após a execução
3. Notifica o usuário se houver itens com `attention: true` (faturas, vencimentos)
4. Apresenta `pending_senders` para classificação na próxima interação disponível
5. Atualiza `senders.json` com a classificação confirmada pelo usuário

Para mais detalhes, ver `AGENT.md`.

---

## Estrutura do projeto

```
projects/inbox-hygiene/
  scripts/
    email_review.py      # script principal (account-agnostic)
    run_yahoo.sh         # wrapper Yahoo
    email_creds.env      # credenciais IMAP (não versionado)
    README.md
  data/
    yahoo/
      senders.json       # mapa remetente → categoria
      state.json         # last_uid, pending_senders
      digest.json        # digest estruturado (OpenClaw consome)
      deprecated/        # arquivos descontinuados em Abril 2026 (ver DEPRECATED.md)
  tests/
    test_email_review.py
  AGENT.md               # brief para o OpenClaw
  higiene-e-mails.md     # este arquivo
```

---

## Fases do projeto

### Fase 1 — Implementado ✓

- Script Python com 3 categorias
- Retenção mínima de 30 dias para `delete`
- Digest estruturado em JSON para OpenClaw consumir
- Migração automática do `senders.json` existente
- Integração com OpenClaw via `AGENT.md`
- Repositório privado no GitHub: `tolisv/inbox-hygiene`

### Fase 2 — Próxima

- OpenClaw lê `digest.json` no heartbeat e notifica o usuário
- Classificação de senders pendentes via chat com o OpenClaw

### Fase 3 — Futura (redesenho necessário)

- LLM processa conteúdo selecionado de emails `digest` de alto valor
- Grava em `raw/` do vault Obsidian no Mac Studio (estilo Karpathy)
- Nota: o acumulador bruto (`for_digest.txt`) foi descontinuado em Abril 2026 por
  excesso de ruído. A Fase 3 precisará de um funil de seleção antes de enviar para LLM.

### Fase 4 — Futura

- Expansão para Gmail, iCloud, ATV Partners com políticas próprias

---

## Critério de sucesso

O projeto será bem-sucedido quando:
- As caixas estiverem mais limpas sem medo de perder algo relevante
- O OpenClaw notificar proativamente sobre itens que exigem atenção
- O usuário conseguir classificar remetentes novos via chat, sem abrir o terminal
- O conteúdo de newsletters úteis estiver acessível via Obsidian
