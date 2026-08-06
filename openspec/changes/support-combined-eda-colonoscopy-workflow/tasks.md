# Tasks: Suportar EDA e Colonoscopia combinadas

## Branch obrigatória

```text
feature/support-combined-eda-colonoscopy-workflow
```

Branch diferente, árvore suja herdada ou ausência da ADR-0004 aceita antes do Slice 001 = `INCOMPLETE/BLOQUEADO`. Não criar branch alternativa, não rebasear e não usar force-push.

## Pré-condição arquitetural

- [x] **Responsável: planner/humano, antes do Slice 001.** Criada, revisada e aceita `docs/adr/ADR-0004-procedimentos-multiplos-e-contrato-llm-neutro.md` com `.pi/skills/adr-generator/SKILL.md` e `docs/adr/template.md`, marcando as decisões 1, 2, 3, 5, 6, 8 e 9 da ADR-0003 como parcialmente superadas.

A ADR-0004 deve ser commitada, enviada e aprovada explicitamente antes de entregar o prompt do Slice 001 ao implementador. O Slice 008 somente ajusta status/links finais da ADR-0003/ADR-0004; não é responsável por criar ou aceitar a decisão. A pré-condição não autoriza implementação. Cada slice ainda exige confirmação explícita após revisão do relatório anterior.

## Regra de execução

- Implementar exatamente um slice vertical por vez.
- Baseline completo antes de editar; falha bloqueia o slice.
- TDD RED → GREEN → REFACTOR obrigatório.
- Tocar apenas arquivos esperados; extras exigem justificativa e, acima do cap, revisão prévia do planner.
- Atualizar apenas o checkbox do slice concluído e os itens DoD efetivamente provados.
- Commit normal e push antes da revisão; sem amend/squash/rebase/force-push.
- Gerar `REPORT_PATH` temporário e parar. Não iniciar o próximo slice sem aprovação explícita.

## Slices verticais

- [x] Slice 001 — NIR cria e acompanha um único caso combinado (`slices/slice-001-combined-intake-procedure-projection.md`)
- [x] Slice 002 — Pipeline neutro analisa um ou dois procedimentos e entrega ao médico (`slices/slice-002-procedure-neutral-pipeline.md`)
- [ ] Slice 003 — Médico decide cada procedimento com justificativa e histórico próprio (`slices/slice-003-per-procedure-doctor-decision.md`)
- [ ] Slice 004 — CHD recebe conjunto autorizado e faz um agendamento casado (`slices/slice-004-paired-scheduler-appointment.md`)
- [ ] Slice 005 — NIR corrige, filtra e recebe resposta comparativa (`slices/slice-005-nir-correction-and-final-response.md`)
- [ ] Slice 006 — Gestor acompanha casos, procedimentos e conversões (`slices/slice-006-procedure-dimension-analytics.md`)
- [ ] Slice 007 — Cutover remove fonte única e prompts específicos legados (`slices/slice-007-authoritative-procedure-cutover.md`)
- [ ] Slice 008 — Operação ativa e reverte o fluxo combinado com segurança (`slices/slice-008-rollout-documentation-and-verification.md`)

## Definition of Done do change

### Modelo e intake

- [x] Um `Case` possui 1–2 procedimentos únicos, sem criar segundo caso para combinado.
- [x] Declaração, detecção e decisão médica são distinguíveis e auditáveis.
- [x] Upload e reenvio corrigido aceitam EDA, Colonoscopia e EDA + Colonoscopia.
- [x] Flag falsa bloqueia Colonoscopia e combinado, mas não EDA nem casos existentes.
- [x] Dados anteriores são preservados por migration conservadora.

### Pipeline e prompts

- [x] Novos processamentos usam schema procedure-neutral v2.
- [x] LLM1 extrai história comum uma vez e lista somente procedimentos sustentados por evidência.
- [x] Single→combined recebe upgrade automático auditável.
- [x] Combinado→single, unique mismatch e unknown retornam ao NIR.
- [x] Policy e LLM2 produzem resultado por procedimento sem duas execuções completas.
- [x] LLM2 não adiciona/remove procedimentos e suporte global usa nível mais restritivo.
- [x] Artefatos 1.1 permanecem legíveis, sem rewrite.

### Médico e histórico

- [ ] Médico aprova/nega cada procedimento.
- [ ] Procedimento negado exige razão específica.
- [ ] Procedimento adicionado exige razão específica e não reexecuta LLM.
- [ ] Troca completa exige razão em ambos os componentes afetados.
- [ ] Lock, role e FSM existentes permanecem protegidos.
- [ ] Históricos EDA/Colonoscopia são consultados e exibidos separadamente.

### CHD e NIR

- [ ] CHD vê apenas conjunto autorizado e alterações explícitas.
- [ ] Combinado usa um único `appointment_at`; split é impossível no fluxo normal.
- [ ] Filtros CHD usam autorizado; filtros médicos usam detectado; filtros NIR usam declarado.
- [ ] Correção NIR reprocessa o mesmo caso sem reextrair PDF e sem race.
- [ ] Resposta final mostra solicitado, detectado, autorizado e razões.

### Analytics e cutover

- [ ] Caso combinado conta uma vez em métricas de casos e duas no volume de procedimentos.
- [ ] Dashboard permite dimensão declarado/detectado/autorizado e mostra matriz de conversão.
- [ ] `Case.exam_type` e dispatch operacional dependente dele foram removidos.
- [ ] Quatro prompts neutros são canônicos; prompts antigos permanecem apenas como histórico inativo.
- [ ] Nenhum reset de produção é requisito.

### Operação e evidência

- [ ] ADR-0004, OpenSpec, manual, contexto e runbook estão alinhados.
- [ ] Rollout mantém flag desligada até migration/prompts/prechecks passarem.
- [ ] Rollback preferencial mantém imagem nova; bridge para imagem antiga é binário/fail-fast.
- [ ] Todos os slices têm relatório revisado, baseline/final, zero failures/errors e `passed_final >= passed_baseline`.
- [ ] Quality gate completo e `openspec validate --strict` passam.
- [ ] Cada slice foi commitado e enviado antes do próximo.
