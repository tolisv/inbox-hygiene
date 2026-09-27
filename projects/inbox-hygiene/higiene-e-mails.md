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

## Sistema atual (setembro de 2026)

### Categorias em uso

O código trabalha com cinco categorias. A documentação anterior, que descrevia
somente três, estava desatualizada.

| Categoria | Descrição | Ação do script | Retenção |
|-----------|-----------|----------------|----------|
| `delete` | Marketing sem valor ou junk conhecido | Apaga com ≥ 7 dias | 7 dias |
| `digest` | Newsletter ou conteúdo possivelmente útil | Registra no digest; apaga com ≥ 14 dias | 14 dias |
| `keep` | Pessoas, bancos, serviços críticos e VIPs | Nunca altera automaticamente | Indefinida |
| `receipt` | Recibos, faturas e comprovantes | Mantém e remove os de ano-calendário com ≥ 2 anos | ~2 anos |
| `purge` | Spam inequívoco | Apaga imediatamente | Imediata |

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

### Processamento diário

1. Os agendamentos do OpenClaw acionam Gmail às 19h e Yahoo às 20h (America/Sao_Paulo).
2. O wrapper de cada conta carrega a credencial IMAP e chama
   `scripts/email_review.py` com seu diretório de dados.
3. O script busca mensagens dos últimos 360 dias e lê apenas cabeçalhos
   (`From`, `Date` e `Subject`) usando `BODY.PEEK`, portanto não marca e-mails
   como lidos.
4. Cada mensagem é comparada ao mapa de remetentes em `senders.json`; a regra
   é por endereço completo, não por domínio.
5. Nas execuções normais, exclusões são feitas por `\\Deleted` seguido de
   `EXPUNGE`; isso é exclusão definitiva da pasta, não arquivamento ou lixeira.
6. Ao final, o script sobrescreve `digest.json`, acrescenta o relatório em
   `digest.txt` e persiste o estado em `state.json`.

### Remetentes novos e LLM

- **Yahoo:** em execução automática, remetentes desconhecidos são registrados
  em `pending_senders` para decisão posterior do usuário.
- **Gmail:** o wrapper habilita classificação por LLM. Quando houver pendências,
  o script envia ao provedor configurado apenas remetente, assunto mais recente
  e data, recebe uma sugestão de categoria e grava em `data/gmail/senders.json`
  numa execução normal. O provedor atual é Claude Haiku.
- Em `--dry-run`, o sistema consulta a caixa e produz relatório, mas não altera
  mensagens, `senders.json` ou `state.json`. O `digest.json` ainda é atualizado
  para refletir a simulação.

### Classificador padronizado

As duas contas usam o mesmo motor e podem selecionar `none`, `anthropic` ou
`jev` por linha de comando. Gmail mantém `anthropic` como padrão por
compatibilidade; Yahoo mantém `none` até aprovação explícita. O piloto Jev usa
OpenRouter diretamente do Python e pode incluir um trecho de corpo
sanitizado, sem links, imagens, anexos, HTML, citações ou assinaturas. O
trecho nunca é persistido nos arquivos de relatório ou estado. Jev retorna
uma categoria, probabilidades e confiança; sugestões abaixo de 0,85
permanecem pendentes, e `delete` requer no mínimo 0,90.

### Alertas

Para itens `digest`, o assunto é verificado para palavras como senha, fatura,
vencimento, pagamento, alteração, alerta e renovação. Encontrando uma delas,
o registro entra em `attention_items` no `digest.json`, para ser destacado pelo
OpenClaw. A regra atual **não protege** itens classificados como `delete`,
`keep` ou `receipt`; isso é uma lacuna deliberadamente registrada no backlog.

---

## Integração com OpenClaw

O OpenClaw é o agente autônomo que opera este sistema diariamente:

1. Executa `run_gmail.sh` às 19h e `run_yahoo.sh` às 20h.
2. Lê o `digest.json` da conta após a execução e envia o resumo no Telegram.
3. Destaca `attention_items`, pendências de classificação, classificações LLM e erros.
4. Apresenta `pending_senders` para classificação em uma interação posterior.

Para mais detalhes, ver `AGENT.md`.

---

## Estrutura do projeto

```
projects/inbox-hygiene/
  scripts/
    email_review.py      # motor principal (compartilhado pelas contas)
    run_yahoo.sh         # wrapper Yahoo
    run_gmail.sh         # wrapper Gmail + classificação LLM
    email_creds.env      # credenciais Yahoo (não versionado)
    gmail_creds.env      # credenciais Gmail/LLM (não versionado)
    README.md
  data/
    yahoo/
      senders.json       # mapa remetente → categoria
      state.json         # last_uid, pending_senders
      digest.json        # digest estruturado (OpenClaw consome)
      deprecated/        # arquivos descontinuados em Abril 2026 (ver DEPRECATED.md)
    gmail/
      senders.json       # mapa remetente → categoria
      state.json         # estado da conta
      digest.json        # relatório estruturado da última execução
  tests/
    test_email_review.py
  AGENT.md               # brief para o OpenClaw
  higiene-e-mails.md     # este arquivo
```

---

## Fases do projeto

### Implementado ✓

- Motor Python compartilhado pelas contas Yahoo e Gmail.
- Cinco categorias, retenção e digest estruturado.
- Classificação por LLM no Gmail.
- Agendamentos diários no OpenClaw com resumo no Telegram.
- Repositório privado no GitHub: `tolisv/inbox-hygiene`.

### Backlog inicial

1. **Segurança — alerta antes de exclusão:** se um assunto contiver keyword
   crítica, impedir exclusão automática e criar `attention_item` em qualquer
   categoria, não apenas `digest`.
2. **Eficiência — processamento incremental:** fazer `last_uid` limitar o
   processamento, preservando uma janela curta de rechecagem para segurança.
3. **Retenção — recibos por idade exata:** substituir a regra de ano-calendário
   por 24 meses completos.
4. **Qualidade — política por caixa:** formalizar regras próprias para Gmail,
   iCloud, ATV Partners e, separadamente, Ergondata. A conta Ergondata não terá
   automação destrutiva até política aprovada.
5. **LLM — piloto OpenRouter/Jev:** testar em lote não destrutivo, com dados
   minimizados e métricas de custo, precisão e falsos positivos antes de uso
   automático.
6. **Operação — classificação via chat:** oferecer pendências de Yahoo em lotes
   revisáveis e aplicar somente classificações explicitamente aprovadas.
7. **Segurança operacional — Git:** retirar credencial embutida da URL do
   remoto após migrar para autenticação segura e rotacionar a credencial atual.

O backlog deve ser migrado para o Linear assim que a integração for
reautenticada.

---

## Critério de sucesso

O projeto será bem-sucedido quando:
- As caixas estiverem mais limpas sem medo de perder algo relevante
- O OpenClaw notificar proativamente sobre itens que exigem atenção
- O usuário conseguir classificar remetentes novos via chat, sem abrir o terminal
- O conteúdo de newsletters úteis estiver acessível via Obsidian
