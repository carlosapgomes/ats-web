# Slice 004 — Scope Gate Direto para Resultado NIR

## Handoff para Implementador LLM

Leia os artefatos do change. Confirme que os slices 001 a 003 estão aplicados.

Implemente somente este slice.

## Problema

No legado, casos `non_eda` ou `unknown` não entram na fila médica. Eles geram resultado final para o NIR com revisão manual obrigatória.

No Django atual, `scope_gate_bypass()` transiciona `LLM_STRUCT → WAIT_DOCTOR`, e o teste atual espera esse comportamento divergente.

## Decisão Aprovada

Para Django web:

```text
non_eda/unknown → WAIT_R1_CLEANUP_THUMBS
```

O NIR deve ver resultado de revisão manual obrigatória e poder confirmar recebimento. O caso não deve aparecer na fila médica.

## Escopo Preferencial

Arquivos prováveis:

- `apps/cases/models.py`
- `apps/pipeline/orchestrator.py`
- `apps/intake/views.py`
- `templates/intake/case_detail.html`, se necessário
- `apps/pipeline/tests/test_orchestrator.py`
- `apps/intake/tests/test_case_detail.py`

## Fonte Legada

- `/home/carlos/projects/augmented-triage-system/src/triage_automation/application/services/process_pdf_case_service.py`
- `/home/carlos/projects/augmented-triage-system/src/triage_automation/application/services/post_room1_final_service.py`
- `/home/carlos/projects/augmented-triage-system/tests/integration/test_process_pdf_case_llm2.py`

## Requisitos Funcionais

1. Quando `classify_exam_scope()` retornar payload manual review:
   - persistir `case.suggested_action`;
   - registrar `EDA_SCOPE_GATED_MANUAL_REVIEW`;
   - não chamar LLM2;
   - não criar evento enganoso `LLM2_OK`;
   - não entrar em `WAIT_DOCTOR`;
   - terminar em `WAIT_R1_CLEANUP_THUMBS`.
2. O resultado NIR deve indicar revisão manual obrigatória para:
   - `non_eda_request`;
   - `unknown_exam_type`.
3. A fila médica não deve listar esses casos.
4. O botão de confirmação de recebimento deve funcionar como nos demais resultados finais.

## TDD — Testes RED Esperados

Atualize/adicionar testes que falhem com o comportamento atual:

1. `non_eda` termina em `WAIT_R1_CLEANUP_THUMBS`, não `WAIT_DOCTOR`.
2. `unknown` termina em `WAIT_R1_CLEANUP_THUMBS`, não `WAIT_DOCTOR`.
3. LLM2 não é chamado.
4. Fila médica não mostra caso manual review.
5. Detalhe NIR mostra resultado tipo revisão manual.
6. `can_confirm_receipt` é verdadeiro para esse caso.

## Critérios de Sucesso

- Comportamento confirmado do legado é preservado semanticamente no Django.
- Nenhum caso scope-gated entra na fila médica.
- Eventos de auditoria são claros.

## Comandos de Validação Focados

```bash
uv run pytest apps/pipeline/tests/test_orchestrator.py apps/doctor/tests/test_views.py apps/intake/tests/test_case_detail.py -q
uv run ruff check apps/cases apps/pipeline apps/intake apps/doctor
uv run mypy apps/cases apps/pipeline apps/intake apps/doctor
```

## Relatório Obrigatório

Crie:

```text
/tmp/ats-web-slice-004-scope-gate-nir-final-report.md
```

Responda com:

```text
REPORT_PATH=/tmp/ats-web-slice-004-scope-gate-nir-final-report.md
```

## Stop Rule

Não implemente presenter médico ou role guard neste slice.
