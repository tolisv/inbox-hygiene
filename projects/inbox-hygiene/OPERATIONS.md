# Operação e histórico técnico — Higiene de E-mails

Este documento registra a arquitetura de produção, a migração realizada em
27 de setembro de 2026, os resultados validados e os procedimentos de operação
e recuperação. Ele não contém chaves, senhas ou valores de credenciais.

## Resumo executivo

As rotinas de Gmail e Yahoo deixaram de depender de um agente LLM do OpenClaw
para iniciar. A produção agora usa timers do `systemd`, que chamam diretamente
os wrappers do projeto. O Python consulta o JEV via OpenRouter apenas para
classificar remetentes novos e um notificador determinístico envia o resumo ao
Telegram pelo CLI do OpenClaw.

Fluxo atual:

```text
systemd timer
  -> run_scheduled.sh
  -> run_gmail.sh ou run_yahoo.sh
  -> email_review.py
  -> IMAP + JEV/OpenRouter
  -> digest.json
  -> notify_digest.py
  -> openclaw message send
  -> Telegram
```

Não existe modelo de agente entre o timer e o script Python.

## Incidente que motivou a migração

### Situação anterior

Os antigos agendamentos eram automações OpenClaw com
`payload.kind = agentTurn`. Em vez de executar um comando diretamente, cada
job iniciava um agente a partir de uma instrução em linguagem natural. Esse
agente precisava:

1. interpretar a instrução;
2. chamar o wrapper pelo shell;
3. ler `digest.json`;
4. redigir e entregar o resumo no Telegram.

Por isso o job dependia de um modelo LLM antes de o Python começar.

### Sequência da falha

1. Os jobs antigos herdaram `openai/gpt-5.4`, incompatível com a autenticação
   ChatGPT/Codex instalada após a atualização do OpenClaw.
2. Uma tentativa de reparo substituiu o modelo por
   `openai/codex-mini-latest`.
3. O nome foi adicionado ao catálogo local e passou na validação de
   configuração, mas a chamada real foi rejeitada: esse modelo não era
   oferecido para a autenticação da conta.
4. Os dry-runs dos wrappers passaram porque testavam o Python diretamente;
   eles não provavam que o `agentTurn` conseguia iniciar.
5. Gmail falhou antes de executar o script. Yahoo chegou a 16 falhas
   consecutivas e foi desativado automaticamente.

### Causa raiz

Havia duas falhas de desenho e validação:

- uma rotina determinística dependia desnecessariamente de um agente LLM;
- presença no catálogo e validade sintática foram tratadas como prova de
  disponibilidade real do modelo, sem uma chamada pelo mesmo caminho de
  autenticação do job.

### Regra para futuras manutenções

Um dry-run do Python comprova somente o Python. Se uma automação usar
`agentTurn`, a recuperação só está comprovada depois de uma execução real do
agente pela mesma autenticação. Para estas duas caixas, a solução permanente é
não usar `agentTurn`.

## Arquitetura de produção

### Agendamentos

| Conta | Timer | Serviço | Horário |
|---|---|---|---|
| Gmail | `inbox-hygiene-gmail.timer` | `inbox-hygiene@gmail.service` | 19:00, São Paulo |
| Yahoo | `inbox-hygiene-yahoo.timer` | `inbox-hygiene@yahoo.service` | 20:00, São Paulo |

Os arquivos versionados estão em `systemd/`. A instalação usa links em
`~/.config/systemd/user/` e habilitação no alvo `timers.target`.

Os jobs OpenClaw anteriores permanecem desativados para preservar o histórico:

- `daily-gmail-review` — `9f7669bf-e8ff-45f2-80df-bfdcbb9dc78d`;
- `daily-email-review` — `5a7e85c7-7b2e-4341-8d2b-5788903abc77`.

Eles não devem ser reativados como caminho de produção.

### Executor agendado

`scripts/run_scheduled.sh`:

1. recebe `gmail` ou `yahoo`;
2. chama o wrapper da conta;
3. força `--classifier jev --classifier-content cleaned`;
4. preserva o código de saída do processamento;
5. chama o notificador;
6. considera falha de notificação uma falha do serviço quando o processamento
   tiver terminado com sucesso.

### Notificação

`scripts/notify_digest.py` lê apenas campos estruturados de `digest.json` e
monta uma mensagem fixa. Ele informa:

- mensagens examinadas;
- exclusões `delete` e `digest`;
- mensagens mantidas;
- pendências;
- classificações JEV aceitas ou para revisão;
- quantidade e assuntos dos primeiros itens de atenção.

A entrega usa `openclaw message send`; essa operação usa o canal Telegram, mas
não inicia um modelo LLM.

Se o processo falhar ou não produzir um digest novo, o notificador não aceita
um arquivo antigo como resultado da execução.

## Classificação JEV

### Dados enviados

Para remetentes novos, o Python pode enviar:

- remetente e domínio;
- assunto;
- data;
- trecho limitado do corpo sanitizado.

A sanitização remove ou descarta HTML, scripts, estilos, links, imagens,
anexos, citações, assinaturas e rodapés comuns. O trecho sanitizado não é
persistido em `digest.json`, `state.json` ou relatórios.

### Decisão e confiança

O adaptador usa a API tipada de decisões do JEV via OpenRouter e recebe
categoria, probabilidades e confiança.

- `digest`, `keep` e `receipt`: aceitação automática a partir de 0,85;
- `delete`: aceitação automática a partir de 0,90;
- `purge`: não pode ser atribuído pelo JEV;
- resposta inválida, erro de rede ou baixa confiança: permanece pendente.

O JEV classifica; o Python continua sendo a única camada que decide e executa
ações IMAP.

### Limitação conhecida

Remetentes que permanecem pendentes voltam a ser considerados em execuções
posteriores. Como a confiança pode variar entre chamadas, deve ser criada uma
fila persistente de revisão para evitar reavaliações repetidas até decisão
humana.

## Segurança contra exclusões indevidas

Antes da migração, keywords críticas apenas produziam alertas em mensagens
`digest`, mas não impediam a exclusão.

Agora, se uma mensagem das categorias `delete`, `purge` ou `digest` contiver
uma keyword crítica, ela:

1. não é excluída;
2. é direcionada ao digest;
3. entra em `attention_items`.

Exemplos de sinais críticos: senha, password, fatura, vencimento, pagamento,
recibo, alteração e alerta. Mensagens `keep` e `receipt` já são preservadas
pelas respectivas políticas.

## Configuração OpenClaw após a correção

- modelo principal do agente: `openai/gpt-5.6-sol`;
- modelo alternativo registrado: `openai/gpt-5.6-terra`;
- referências globais a `openai/codex-mini-latest` removidas;
- referência ao antigo `openai/gpt-5.4` removida;
- catálogo manual inválido do provedor OpenAI removido;
- configuração validada sem reiniciar o Gateway.

Os jobs antigos ainda exibem o modelo inválido em seu histórico, mas estão
desativados e não participam do fluxo de produção.

## Validação realizada em 27 de setembro de 2026

### Testes antes da execução normal

- sintaxe Bash validada;
- compilação Python validada;
- unidades `systemd` validadas;
- dry-run Gmail com JEV concluído sem alterações;
- dry-run Yahoo com JEV concluído sem alterações;
- suíte final: 59 testes aprovados.

### Gmail — execução normal

- mensagens examinadas: 330;
- `delete` expurgadas: 70;
- `digest` expurgadas: 63;
- classificações JEV gravadas: 3;
- remetentes pendentes: 3;
- itens críticos preservados: 4;
- serviço: código 0, `Result=success`;
- resumo Telegram entregue.

Os itens preservados incluíram alertas de senha do Bradesco e Microsoft,
inclusive para `ergondata.com.br`, e um alerta sobre CNH.

### Yahoo — execução normal

- mensagens examinadas: 1.000;
- `delete` expurgadas: 380;
- `digest` expurgadas: 159;
- classificações JEV gravadas: 15;
- remetentes pendentes: 37;
- itens críticos preservados: 11;
- serviço: código 0, `Result=success`;
- resumo Telegram entregue.

Os itens preservados incluíram redefinições de senha Microsoft, recibo fiscal e
documentos de folha/pagamento.

As exclusões usam `\\Deleted` seguido de `EXPUNGE`; portanto foram definitivas
na pasta processada.

## Operação diária

### Conferir próximos horários

```bash
systemctl --user list-timers \
  inbox-hygiene-gmail.timer inbox-hygiene-yahoo.timer --all
```

### Conferir resultado do último serviço

```bash
systemctl --user show inbox-hygiene@gmail.service \
  -p Result -p ExecMainStatus
systemctl --user show inbox-hygiene@yahoo.service \
  -p Result -p ExecMainStatus
```

### Consultar logs

```bash
journalctl --user -u inbox-hygiene@gmail.service -n 200 --no-pager
journalctl --user -u inbox-hygiene@yahoo.service -n 200 --no-pager
```

### Executar dry-run manual

O dry-run consulta IMAP e JEV, atualiza o digest de simulação e imprime a
mensagem de notificação, mas não altera mensagens, regras ou estado.

```bash
projects/inbox-hygiene/scripts/run_scheduled.sh gmail --dry-run
projects/inbox-hygiene/scripts/run_scheduled.sh yahoo --dry-run
```

### Executar normalmente pelo mesmo caminho da produção

```bash
systemctl --user start inbox-hygiene@gmail.service
systemctl --user start inbox-hygiene@yahoo.service
```

### Pausar ou retomar

```bash
systemctl --user disable --now inbox-hygiene-gmail.timer
systemctl --user disable --now inbox-hygiene-yahoo.timer

systemctl --user enable --now inbox-hygiene-gmail.timer
systemctl --user enable --now inbox-hygiene-yahoo.timer
```

## Recuperação e rollback

Se houver comportamento inesperado:

1. desative o timer da conta afetada;
2. preserve `digest.json`, `state.json` e o journal para diagnóstico;
3. execute o wrapper em `--dry-run`;
4. valide IMAP, OpenRouter/JEV e notificação separadamente;
5. só reative após teste pelo mesmo caminho do serviço.

Para retirar a integração `systemd`, desabilite os timers e remova somente os
links correspondentes de `~/.config/systemd/user/`, depois execute
`systemctl --user daemon-reload`. Não reative automaticamente os jobs antigos
do OpenClaw: eles dependem de `agentTurn` e conservam referências inválidas em
seu histórico.

## Arquivos adicionados ou alterados

- `scripts/run_scheduled.sh` — executor determinístico;
- `scripts/notify_digest.py` — notificação Telegram sem LLM;
- `scripts/email_review.py` — JEV tipado, conteúdo sanitizado, confiança e
  proteção por keywords;
- `systemd/inbox-hygiene@.service` — serviço parametrizado;
- `systemd/inbox-hygiene-gmail.timer` — timer Gmail;
- `systemd/inbox-hygiene-yahoo.timer` — timer Yahoo;
- `tests/test_notify_digest.py` — testes do notificador;
- `tests/test_email_review.py` — testes de JEV e proteção;
- `higiene-e-mails.md` — desenho funcional atualizado.

## Histórico Git relacionado

- `2ac0d09` — classificador unificado opcional;
- `41b3e41` — API tipada JEV e limiares de confiança;
- `efb4b55` — timers determinísticos, notificador e proteção de exclusão.

Os arquivos de dados modificados pelas execuções não fizeram parte do commit
de infraestrutura, para não misturar estado operacional com código.
