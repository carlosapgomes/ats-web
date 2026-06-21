# Tasks: Caso corrigido / vínculo entre reenvios

## Slices verticais

- [x] Slice 001 — Fluxo NIR de reenvio corrigido explícito (`slices/slice-001-explicit-corrected-resubmission-flow.md`)
- [x] Slice 002 — Visibilidade NIR/médico da relação entre casos (`slices/slice-002-correction-relationship-visibility.md`)

## Status final do change

Change **concluído e arquivado**. Todos os itens da Definition of Done abaixo marcados. Commits em `main`:

- `05084cc` — Slice 001 (fluxo NIR explícito + migration + service + view/template + eventos + 13 testes)
- `0b69b82` — Quick fix: validação do checkbox de confirmação no backend (fonte de verdade)
- `67edea9` — Slice 002 (cards NIR, card médico, badge na busca de encerrados, deduplicação R7 + 10 testes)
- `8d138f7` — Quick fix: teste R7 genuíno (mesmo `agency_record_number`, exercita `hide_prior_case_card`) + remoção de `original_status_label` inerte no contexto médico
- `40953e7` / `5282cae` / `f4c1aec` — Runbook de deploy (`docs/deploy/corrected-case-resubmission-linkage.md`), com modelo de 2 atores para `/archive/backups` e Quick reference

### Hardening pós-slices

- **Backend como fonte de verdade do checkbox de confirmação** (R5/R6 do Slice 001): a view rejeita POST sem `confirmation`, sem depender apenas do `required` HTML5.
- **Teste de deduplicação R7 robusto**: o teste original era falso-positivo (usava `agency_record_number` distintos, então o prior-case lookup não encontrava o original e o card genérico sumia pela guarda do template, não pela lógica `hide_prior_case_card`). Corrigido para usar o mesmo número, exercitando de fato a deduplicação — verificado com RED sanity check (quebra da lógica faz o teste falhar).
- **Limpeza**: removida a chave inerte `original_status_label: ""` do `correction_context` da view médica (nunca renderizada em `decision.html`); a view NIR mantém a sua versão preenchida, pois `case_detail.html` a usa.

## Definition of Done do change

- [x] `Case` possui relação opcional para caso anterior corrigido (`corrects_case`).
- [x] `Case` armazena metadados do reenvio corrigido: motivo, autor e data/hora.
- [x] Migration criada e aplicada nos testes.
- [x] NIR consegue iniciar reenvio corrigido a partir de um caso anterior.
- [x] Reenvio corrigido exige motivo obrigatório.
- [x] Reenvio corrigido exige exatamente 1 novo PDF principal.
- [x] Reenvio corrigido aceita anexos opcionais PDF/JPEG/PNG com os mesmos limites do upload inicial.
- [x] Novo `Case` é criado; o caso anterior não é sobrescrito, reaberto ou movido de status.
- [x] Novo `Case` inicia pipeline normal de extração/LLM.
- [x] PDF, anexos, eventos, decisões e dados extraídos do caso anterior não são copiados para o novo caso.
- [x] Anexos enviados no reenvio pertencem apenas ao novo caso.
- [x] Evento `CASE_CORRECTION_CREATED` é registrado no novo caso.
- [x] Evento `CASE_MARKED_SUPERSEDED` é registrado no caso anterior.
- [x] NIR vê no caso novo que ele corrige um caso anterior e vê o motivo do reenvio.
- [x] NIR vê no caso anterior, quando acessível/listado, que existe caso corrigido relacionado.
- [x] Busca de casos encerrados oferece caminho para reenvio corrigido.
- [x] Médico vê card claro de "Reenvio corrigido" na tela de decisão do novo caso.
- [x] Card médico mostra resumo seguro do caso anterior: registro/id, envio, desfecho/decisão e motivo do reenvio.
- [x] Card médico informa explicitamente que documentos/anexos do caso anterior não foram herdados.
- [x] Médico não vê PDF/anexos/timeline completa do caso anterior embutidos no novo caso.
- [x] Card genérico de prior-case lookup não duplica visualmente o mesmo caso anterior quando houver vínculo explícito.
- [x] Prior-case lookup automático continua funcionando para uploads normais sem vínculo explícito.
- [x] `doctor_reason`, `doctor_observation` e `correction_reason` mantêm semânticas separadas.
- [x] `doctor_observation` não é removido nem redesenhado neste change.
- [x] FSM não é alterada.
- [x] Comunicação/thread por caso não é implementada neste change.
- [x] Testes relevantes foram escritos antes da implementação passar (TDD RED → GREEN → REFACTOR).
- [x] Clean code aplicado: funções pequenas, nomes claros, sem lógica de negócio pesada em views/templates, DRY, YAGNI.
- [x] Quality gate do AGENTS.md executado:
  - [x] `uv run ruff check .`
  - [x] `uv run ruff format --check .`
  - [x] `uv run mypy .`
  - [x] `uv run pytest`
- [x] Relatório markdown temporário criado por cada slice.
- [x] Este `tasks.md` atualizado.
- [x] Commit e push realizados após cada slice.

## Notas para implementadores

- Não reabrir o caso anterior.
- Não copiar anexos/documentos do caso anterior.
- Não criar novos estados FSM.
- Não implementar chat/comunicação operacional neste change.
- Não usar `doctor_observation` como thread de conversa.
- Não alterar prior-case lookup automático, salvo ajuste mínimo para evitar duplicidade visual na UI.
- Se um slice precisar tocar mais arquivos que o previsto, justificar no relatório antes de ampliar escopo.
