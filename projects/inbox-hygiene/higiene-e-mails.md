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

A conta Yahoo é usada principalmente como caixa de junk mail, propagandas e newsletters.

Apesar disso, ainda recebe alguns e-mails importantes ou úteis, como por exemplo:
- Latam
- Itaú
- Apple
- assinaturas diversas
- notificações e comprovantes

Já existe uma automação inicial para essa conta, via script Python, capaz de:
- analisar remetentes de uma janela recente
- classificar remetentes
- apagar mensagens de certos remetentes
- extrair conteúdo de alguns e-mails para resumo

Essa automação resolve apenas parte do problema.

### Outras contas no escopo futuro

A lógica pensada aqui poderá ser aplicada também a:
- Gmail pessoal
- iCloud
- ATV Partners

### Conta Ergondata

A conta de e-mail da Ergondata ainda não deve entrar em automação destrutiva.

Antes disso, será necessário decidir uma política específica para e-mails de negócio.

## Hipóteses e racional já definidos

- E-mails com mais de 30 dias têm baixíssima chance de serem lidos
- E-mails com mais de 90 dias dificilmente serão acessados, salvo quando funcionam como registro
- Nem todo e-mail que precisa ser guardado precisa continuar na inbox
- O sistema deve separar claramente o que é lixo, referência, revisão e ação

## Meta principal

Permitir que a inbox contenha apenas o que ainda tem chance real de leitura, revisão ou ação.

Todo o restante deve ser:
- apagado com segurança
- arquivado como referência
- resumido
- ou classificado para revisão posterior

## Taxonomia proposta

### 1. delete

E-mails descartáveis, promocionais, junk, newsletters irrelevantes, marketing repetitivo, ofertas sem valor, ruído puro.

Ação esperada:
- apagar automaticamente ou quase automaticamente
- retenção curta

### 2. archive_reference

E-mails que raramente serão lidos, mas que podem precisar ser recuperados como registro.

Exemplos:
- recibos
- comprovantes
- confirmações
- renovações
- itinerários
- algumas notificações bancárias
- alguns registros de saúde, compra ou assinatura

Ação esperada:
- tirar da inbox
- arquivar ou mover para pasta/label de referência
- opcionalmente extrair metadados importantes

### 3. summarize

E-mails informativos que não exigem ação imediata, mas podem gerar valor se forem condensados.

Exemplos:
- newsletters selecionadas
- updates de mercado
- conteúdos com potencial de insight

Ação esperada:
- extrair conteúdo
- gerar resumos periódicos
- remover da inbox ou reduzir visibilidade

### 4. needs_attention

E-mails que podem exigir leitura, decisão, resposta, pagamento, acompanhamento ou ação operacional.

Exemplos:
- alertas importantes
- faturas
- cobranças
- alteração de voo
- renovação crítica
- aviso de segurança
- verificação de conta
- pendências bancárias

Ação esperada:
- nunca apagar automaticamente
- destacar para revisão
- eventualmente gerar fila de ação

### 5. keep_never_auto

E-mails, remetentes ou categorias que nunca devem entrar em automação destrutiva.

Exemplos:
- contatos sensíveis
- mensagens consideradas VIP
- qualquer categoria que exija cautela máxima

Ação esperada:
- manter preservado
- nenhuma exclusão automática

## Critérios de classificação

A decisão não deve depender apenas do remetente.

A classificação ideal deve considerar quatro camadas:

### Camada 1. Conta

Cada conta terá política própria.

- Yahoo: política mais agressiva
- Gmail pessoal: política intermediária e mais cuidadosa
- iCloud: política conservadora
- ATV Partners: política própria, com separação entre relacionamento útil e ruído
- Ergondata: por enquanto, sem automação destrutiva

### Camada 2. Remetente

Remetente é um bom primeiro filtro, especialmente para campanhas, newsletters, bancos, companhias aéreas e serviços recorrentes.

### Camada 3. Conteúdo

O sistema deve evoluir para considerar padrões de assunto e palavras-chave.

Exemplos de palavras ou sinais de alta importância:
- código
- verification
- segurança
- pagamento
- vencimento
- fatura
- recibo
- comprovante
- itinerário
- alteração
- renovação
- cancelamento
- alerta

### Camada 4. Tempo

Tempo é essencial para retenção e priorização.

Regras iniciais sugeridas:
- até 7 dias: janela de alta relevância
- até 30 dias: ainda pode haver leitura e ação
- acima de 30 dias: baixa chance de leitura
- acima de 90 dias: quase sempre candidato a arquivo ou descarte, salvo valor de registro

## Políticas iniciais por conta

### Yahoo

Objetivo: ambiente de laboratório do projeto.

Estratégia:
- delete mais agressivo
- summarize para informativos úteis
- archive_reference para confirmações, recibos, viagens, saúde, assinaturas e registros relevantes
- needs_attention para tudo que sinalize risco, prazo ou ação

### Gmail pessoal

Estratégia:
- menos deleção automática
- mais arquivamento e detecção de ação
- alta cautela com segurança, banco, viagem e identidade digital

### iCloud

Estratégia:
- foco em segurança, Apple, identidade digital, compras e contas
- política conservadora

### ATV Partners

Estratégia:
- separar ruído comercial de oportunidades reais, relacionamento útil, financeiro e operação
- evitar deleção automática até entender melhor os padrões

### Ergondata

Estratégia inicial:
- somente mapeamento, classificação e sinalização
- sem deleção automática até existir política de negócio aprovada

## Retenção sugerida por categoria

### delete
- retenção de 7 a 30 dias, conforme confiança na regra

### archive_reference
- retenção longa ou arquivamento fora da inbox
- pode variar de 90 a 365 dias ou mais, dependendo do tipo

### summarize
- manter só o necessário para gerar resumo e histórico útil

### needs_attention
- manter até resolução

### keep_never_auto
- sem retenção automática destrutiva

## Medidas para reduzir a sensação de perda

O sistema deve ser desenhado para evitar arrependimento.

Para isso, precisa ter:
- modo report-only ou dry-run
- logs do que seria apagado
- digest do que foi apagado, resumido, arquivado ou sinalizado
- lista de pendências e possíveis ações
- rastreabilidade suficiente para auditoria posterior

A meta é que a automação pareça uma triagem confiável, e não uma caixa-preta destrutiva.

## Fases do projeto

### Fase 1. Mapeamento

Objetivo:
- listar remetentes por conta
- medir frequência e volume
- identificar tipos recorrentes de mensagem
- mapear categorias prováveis

### Fase 2. Taxonomia e regras

Objetivo:
- consolidar categorias
- definir regras por conta
- definir retenção
- definir exceções
- definir remetentes VIP
- definir palavras-chave de atenção

### Fase 3. Execução segura

Objetivo:
- rodar em modo report-only
- classificar sem apagar
- produzir relatórios e pendências

### Fase 4. Automação parcial

Objetivo:
- automatizar apenas casos de baixíssimo risco
- resumir informativos úteis
- arquivar referências
- destacar o que exige ação

### Fase 5. Expansão multi-conta

Objetivo:
- replicar a abordagem nas outras caixas
- adaptar política por conta
- amadurecer critérios

## Situação atual da automação existente

No momento existe um script para a conta Yahoo que:
- analisa mensagens de uma janela recente
- classifica remetentes
- deleta mensagens de remetentes classificados para deleção
- extrai mensagens de remetentes classificados para resumo
- guarda estado em arquivos locais

Limitações atuais percebidas:
- modelo de classificação ainda simples demais
- ausência de dry-run implementado no código atual
- lógica ainda muito orientada a remetente
- parte destrutiva exige cautela adicional
- ainda não existe uma camada mais inteligente para detectar ação, referência e risco

## Direção desejada para a próxima iteração

A próxima evolução do projeto deve buscar:
- classes mais ricas do que delete/summarize/keep
- modo seguro de operação
- retenção por regra
- distinção entre leitura, ação e preservação como registro
- visão por conta de e-mail
- mecanismos de revisão periódica e digest

## Critério de sucesso

O projeto será bem-sucedido quando:
- as caixas estiverem mais limpas
- a inbox representar apenas o que ainda importa
- houver baixo medo de perder algo relevante
- existir confiança suficiente para delegar parte importante da triagem
- o sistema puder ser adaptado entre contas com políticas diferentes
