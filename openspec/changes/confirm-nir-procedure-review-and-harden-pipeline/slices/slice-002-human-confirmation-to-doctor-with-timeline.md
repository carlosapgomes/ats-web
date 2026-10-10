# S2 — NIR confirma pedido e médico recebe análise com autoria explícita

## 1. Identity

- Slice: S2 / 002.
- Change: `confirm-nir-procedure-review-and-harden-pipeline`.
- Task: `../tasks.md` 2.1.
- Dependências: S1 aceito, contrato técnico/ADR-0012 revisado e aceite explícito do owner para iniciar S2. Não executar por inferência de autorização de abrir change.

## 2. Objective

Entregar revisão NIR resolutiva no mesmo UUID, mantendo ou trocando seleção, com evento humano explícito na Linha do Tempo, conjunto efetivo autoritativo no pipeline e aviso médico, sem exigir relatório reescrito nem dispensar policy.

## 3. Read first

- AGENTS.md, PROJECT_CONTEXT.md e openspec/config.yaml.
- Proposal, evidence.md, design D1–D6/D8–D9/Migration Plan e tasks desta change; quatro delta specs.
- ADR-0012 e ADR-0011 (restrições automáticas preservadas fora do evento humano).
- `apps/intake/services.py`, `apps/intake/views.py`, `templates/intake/case_detail.html` (card e timeline), `templates/intake/closed_case_detail.html`.
- `apps/cases/models.py`, `apps/cases/signals.py`, `apps/cases/procedures.py`, `apps/intake/services.py:ensure_intake_selection_permitted`.
- `apps/pipeline/orchestrator.py`, `apps/pipeline/procedure_reconciliation.py`, `apps/pipeline/schemas/adapters.py`, `apps/pipeline/llm2_service_v4.py` e guard S1.
- `apps/doctor/views.py`, `apps/doctor/presenters.py`, templates de relatório/decisão; `apps/scheduler/views.py`/`templates/scheduler/context_detail.html`, `apps/dashboard/views.py` (leitores de eventos).
- `apps/intake/tests/test_exam_type_correction.py`, `apps/pipeline/tests/test_conflict_resolution_proceeds.py`, testes de projeção/filas/decisão v4 e `docs/manual/manual-usuarios.md`.

## 4. Requirements → evidence

| ID | Comportamento observável | Evidência planejada |
| --- | --- | --- |
| R1 | POST SSR permite seleção atual ou outra habilitada, exige leitura + justificativa 1–500; errors preservam tentativa sem consentimento implícito | Tests client/serviço mesma/troca, vazios/NUL, POST antigo, HTML option atual enabled |
| R2 | Somente revisão pré-médica/reasons atuais, NIR/role/lease, fonte e revisão atuais; forbidden matriz/flags antes de efeitos | Parametrização de permissões/status/seleções inválidas/flags |
| R3 | Confirmação/declaração/reset/transição/lease sob lock; evento antes de transição; double POST/cleanup sem dupla confirmação/enqueue | Teste transaction/race; evento humano com actor e selection_changed true/false |
| R4 | Event source of truth com fingerprint principal e revisão; legacy event não confere autoridade; evento stale não é consumido | Testes do helper de domínio + job após alteração PDF/texto/revisão/declaração |
| R5 | Divergência repetida não reabre identificação após confirmação válida; raw LLM1/union preservados e projeção efetiva não fabrica consenso | E2E argônio e Eco+CPRE, duas passadas → WAIT_DOCTOR, assertions de eventos e rows |
| R6 | Item confirmado ausente no LLM1 funciona com common/unknown; lista LLM2 exata; policy negativa/pendências e S1 continuam | Fake LLM1 sem item selecionado, fake LLM2; combinado com um item ausente e exceção local |
| R7 | Linha do Tempo mostra pessoa, data/hora, label selecionado, manutenção/troca e justificativa; aplicação/invalidação sistêmicas distintas | Tests HTML ativos/encerrados/CHD e leitores existentes; escaping; fallback username; ausência de raw code genérico |
| R8 | Médico vê confirmação mesmo sem precedence metadata e mantém decisão clínica; labels operacionais distinguem origem humana | Teste SSR/presenter de aviso e fila/procedimentos em análise, legacy sem aviso |
| R9 | Enqueue pós-commit/recovery mantém confirmação e mensagem verdadeira em ambos os resultados de falha | Fault-injection das duas branches + estado/evento duráveis |
| R10 | Sem migração/backfill; legados, auto upgrades, sem consentimento e eventos antigos permanecem; manual descreve novo fluxo | Regressões + manual atualizado com revisão humana ≠ aprovação |

## 5. Expected blast radius

Domínio: novo helper coeso `apps/cases/procedure_review.py` (fingerprint/consumo/validação) e presenter puro de evento; `apps/intake/services.py`/views; pipeline orchestrator (conjunto efetivo/proveniência), adapters/contexto LLM2 somente se necessários para D5; `apps/doctor/presenters.py`/views/partial de aviso; templates NIR ativo/encerrado e CHD; leitores de timeline existentes; manual e testes focados novos.

Novos testes sugeridos:
- `apps/intake/tests/test_procedure_review_confirmation.py` (serviço/POST/reserva/HTML).
- `apps/pipeline/tests/test_human_confirmed_procedures.py` (duas passadas, seleção ausente, policy, provenance).
- `apps/cases/tests/test_procedure_review.py` (event/fingerprint/legado).
- testes SSR/presenter nas apps de médico/CHD e arquivo de auditoria da timeline conforme convenção existente.

Justificativa de >5 arquivos já aprovada no design D9: confirmação só é segura com backend, pipeline e visibilidade humana juntos. **Não** antecipar refactor geral de events/timelines, novo schema/migration, detector de argônio/capacidade, catálogo, analytics dimensional nova, thread/notificações ou CSS novo. Reutilizar CSS/combobox atuais. Arquivos adicionais mínimos devem ser listados e justificados; escalar se nova arquitetura for necessária.

## 6. Failing-before plan

TDD RED → GREEN → REFACTOR. Construir fixtures sintéticas de evidence.md, nunca copiar PDF/PII/credencial real.

1. Testes client para confirmar seleção igual com consentimento: baseline falha pelo disabled/backend igualdade. Testes devem provar erro de comportamento, não só helper ausente.
2. E2E duas passadas (revisão → confirmação → execução fake pipeline): baseline repete gate para union sem cobertura; assert esperado WAIT_DOCTOR com evento humano/union original.
3. Seleção confirmada ausente no array LLM1: baseline não tem autoridade/contexto, não atinge conjunto esperado.
4. SSR da Linha do Tempo: baseline só reconhece labels antigos e não mostra quem confirmou qual seleção. Teste HTML escopado ao evento, não busca global que pode achar procedimento em outro card.

```sh
uv run pytest apps/intake/tests/test_procedure_review_confirmation.py apps/pipeline/tests/test_human_confirmed_procedures.py -q
```

Guardar output RED e passar a integração de eventos depois da falha comportamental demonstrada. Testes de concorrência devem usar banco isolado PostgreSQL e protocolo de lock real, não apenas mocks de flags.

## 7. Implementation constraints

- CaseEvent é autoridade; nenhum force=true task/query-string/permissão implícita, nem retroatividade de CASE_PROCEDURE_DECLARATION_CORRECTED.
- Referência à revisão/fingerprint validada no POST e consumo; se mais recente inválida, não reaplicar confirmação antiga.
- Caso CLEANED/WAIT_DOCTOR/FAILED não confirma por este fluxo; mesma seleção só após revisão explícita.
- Raw artifact/union intactos; detection_status é projeção operacional efetiva com labels de proveniência. Não substituir union pela seleção humana em CASE_PROCEDURES_DETECTED.
- Não mudar regex/precedências automáticas. Sem evento humano válido, suite automática deve permanecer.
- Dados ausentes unknown; não sintetizar item clínico/evidence_span nem emprestar exceção/subtipo. Lista autoritativa para LLM2 vem do evento, mas a justificativa livre não vira system prompt.
- Policy, imagem verificada, schema/pt-BR/echo rc.10 e guard S1 continuam; confirmação não produz aprovação/agendamento.
- Auditadores renderizam texto escapado, nome fallback username e labels canônicos; novos detalhes usam presenter/partial compartilhado, sem regra de negócio em template.
- Follow the repository engineering policy in AGENTS.md and preserve existing conventions. Prefer the smallest correct change; avoid speculative abstraction and unrelated refactoring.

## 8. Validation

**Focused:**
```sh
uv run pytest apps/cases/tests/test_procedure_review.py apps/intake/tests/test_procedure_review_confirmation.py apps/pipeline/tests/test_human_confirmed_procedures.py -q
uv run pytest apps/intake/tests/test_exam_type_correction.py apps/pipeline/tests/test_conflict_resolution_proceeds.py -q
uv run pytest apps/cases/tests/ apps/intake/tests/ apps/pipeline/tests/ apps/doctor/tests/ apps/scheduler/tests/ apps/dashboard/tests/ -q
```

Asserts antigos de “igual rejeita”, “outra seleção retorna à revisão” e old POST precisam ser classificados: sem consentimento mantém recusa; confirmação explícita tem o novo contrato. Não tornar todos os testes autoritativos inserindo defaults de consentimento em fixture compartilhada e assim perder guardas sem revisão.

**Project-required gates:** AGENTS.md §2/DoD; validar deltas OpenSpec desta change. Node checks apenas se JS for de fato tocado; no-JS SSR é obrigatório.

**Runtime/verification:** em ambiente de teste/dev com fake LLM: abrir card, confirmar seleção igual e diferente, ver autoria/label na timeline, processar, abrir aviso do médico e, após encerramento sintético, conservar histórico. Pelo menos keyboard/no-JS do formulário e error re-render. Não usar produção/live LLM como gate.

## 9. Acceptance criteria

- [ ] R1–R2: igualdade permitida só com consentimento; seleção inválida/ator/reserva/status recusados sem efeitos.
- [ ] R3–R4: transação/concorrência/fingerprint/revisão e eventos legados provados.
- [ ] R5: argônio e Eco+CPRE resolvidos por escolha humana válida sem reescrever fonte/union.
- [ ] R6: seleção ausente funciona; policy não é ignorada; NUL continua falha segura.
- [ ] R7: quem confirmou qual seleção aparece na Linha do Tempo, também na manutenção/encerramento; escaping correto.
- [ ] R8: médico informado com decisão própria, labels sem falsa detecção automática.
- [ ] R9: recovery/mensagens verdadeiras e evento humano durável.
- [ ] R10: manual e legados coerentes, sem migration/backfill/estado novo.
- [ ] Gates, RED/GREEN, runtime sintético e riscos registrados no relatório.

## 10. Escalation conditions

Retornar **BLOCKED_NEEDS_DECISION** diante de conflito spec/design, necessidade de schema externo/migration/FSM/novo catálogo, alteração de decisão clínica/permissões, mecanismo de job locking global não previsto, ou impossibilidade de honrar seleção ausente sem fabricar dados. Se consumidor tratar projection como evidência clínica e isso não puder ser rotulado com proveniência sem expansão material, listar consumidor/teste e escalar. Nunca concluir “só botão” ou “helper de evento” como este slice.

## 11. Evidence report

`/tmp/sirhosp-slice-002-report.md` (path canônico do skill solicitado).

Status READY_FOR_REVIEW ou BLOCKED_NEEDS_DECISION; R1–R10 → teste/runtime; arquivos e expansão justificada; RED/GREEN; comandos/exit status; screenshots/HTML sintéticos quando úteis; risco de rollback/proveniência; decisões humanas pendentes. Snippets antes/depois pequenos conforme AGENTS.md, sem diff duplicado nem dados de produção.

## 12. Worker handoff / prompt fresh

```text
Read AGENTS.md and PROJECT_CONTEXT.md first.
Implement ONLY approved S2 from openspec/changes/confirm-nir-procedure-review-and-harden-pipeline/slices/slice-002-human-confirmation-to-doctor-with-timeline.md, starting from an accepted S1.
Reconstruct context from Read first, not from conversation; proposal/spec/design/ADR are the contract.
Prove behavioral RED, implement the smallest complete end-to-end confirmation flow, REFACTOR, run focused/project-required gates and synthetic SSR verification, and write /tmp/sirhosp-slice-002-report.md.
Do not update tasks.md, commit, push, merge, archive, deploy or recover production cases; owner/controller handles project control steps after review.
If a new decision is required, return BLOCKED_NEEDS_DECISION with evidence. Otherwise return READY_FOR_REVIEW and REPORT_PATH.
```

Handoff ao reviewer fresh: tentar confirmação mantida, stale source e falta de item LLM1; examinar união bruta/evento aplicado; verificar timeline especificamente no evento novo e médico avisado sem metadata de precedência. Parent sintetiza/faz fixes/controla commit e gate; este contrato não autoriza lançá-lo automaticamente.
