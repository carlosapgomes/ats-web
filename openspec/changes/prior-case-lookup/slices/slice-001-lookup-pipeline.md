# Slice 1: Prior case lookup + integração pipeline + audit event

## Objetivo

Criar função de lookup de casos anteriores, integrar no orchestrator (LLM2),
e registrar evento auditável.

## Arquivos

### 1. `apps/pipeline/prior_case.py` — novo

- `PriorCaseSummary` (dataclass): prior_case_id, decided_at, decision, reason
- `PriorCaseContext` (dataclass): prior_case, prior_denial_count_7d
- `lookup_prior_case_context(case_id, agency_record_number, now=None)` → PriorCaseContext
- Lógica portada do legado `build_prior_case_context()`

### 2. `apps/pipeline/orchestrator.py` — modificado

- Antes de chamar `run_llm2_service()`, chamar `lookup_prior_case_context()`
- Passar `prior_case_json` para `run_llm2_service()`
- Se prior_context tem resultados, criar CaseEvent `PRIOR_CASE_LOOKUP`

### 3. `apps/pipeline/tests/test_prior_case.py` — novo

~12 testes unitários:
- No prior cases → prior_case=None, count=None
- One doctor denial within 7d → returned as prior_case
- One appointment denial within 7d → returned as prior_case
- Multiple denials → most recent returned, count correct
- Denial outside 7d window → not included
- Same case_id excluded
- Different agency_record_number excluded
- Mix of doctor deny + appt denied → both counted
- reason normalization ("não informado" for empty/None)
- Empty agency_record_number → empty result

## Critérios de sucesso

- [ ] `lookup_prior_case_context` retorna contexto correto
- [ ] Orchestrator passa prior_case_json para LLM2
- [ ] CaseEvent PRIOR_CASE_LOOKUP criado quando há contexto
- [ ] ~12 testes passando
- [ ] ruff + mypy + pytest clean

## Arquivos: ideal ≤ 3
