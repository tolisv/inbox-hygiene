# Arquivos descontinuados

Movidos em Abril 2026 como parte da refatoração para modo minimalista.

## Por que foram movidos

O sistema foi simplificado: deixou de coletar o corpo dos emails `digest`
e passou a apenas apagá-los após 14 dias. Com isso, os arquivos abaixo
perderam sua função operacional.

Foram preservados aqui (em vez de deletados) por conterem histórico
acumulado e para referência futura caso o sistema evolua.

## Arquivos

### `for_digest.txt`

Acumulava o corpo completo (texto plano) de emails da categoria `digest`,
destinado à Fase 3 do projeto: processamento LLM → Obsidian.

A Fase 3 foi adiada indefinidamente. O conteúdo bruto tinha muito ruído
(HTML quebrado, propaganda, caracteres especiais) e não valia o custo
de tokens para processar.

O script parou de alimentar este arquivo a partir do commit `2175538`.

### `digest.txt`

Log legível acumulado por execução. Listava todos os emails deletados
e coletados por run.

Substituído pelo `digest.json` enxuto, que contém apenas o que o
OpenClaw precisa: `attention_items`, `pending_senders`, `deleted_items`
e `summary`.

O script parou de alimentar este arquivo a partir do commit `2175538`.

## Reativar no futuro?

Se a Fase 3 (LLM + Obsidian) for implementada, `for_digest.txt` pode
voltar como destino de conteúdo já filtrado e limpo — não mais conteúdo
bruto de todos os `digest`, mas apenas dos senders que valerem a pena.
