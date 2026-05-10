# Proposal: Prior Case Lookup

**Change ID**: `prior-case-lookup`
**Fase**: 9 — Prior Case Lookup
**Risco**: PROFISSIONAL (nova service function, integração no pipeline existente, UI na decisão médica — sem mudança em modelos)
**Dependências**: Fases 3-5 (doctor decision, scheduler decision, agency_record_number)

## Objetivo

Permitir que médicos e supervisores vejam contexto de casos anteriores do mesmo paciente
(mesmo `agency_record_number`) com negações nos últimos 7 dias, informando a decisão
e registrando o lookup como evento auditável.

## Escopo

### Funcionalidades

1. **Prior case lookup** — função de domínio
   - Busca casos com mesmo `agency_record_number` (excluindo o caso atual)
   - Filtra negações nos últimos 7 dias (doctor_decision=deny ou appointment_status=denied)
   - Retorna: caso mais recente negado + contagem de negações no período
   - Portado fielmente do legado `prior_case_queries.py` + `build_prior_case_context()`

2. **Integração no pipeline** — enriquecer LLM2
   - Orchestrator chama prior case lookup antes de chamar LLM2
   - Passa `prior_case_json` para `run_llm2_service()` (já suportado)
   - Placeholder `{prior_case}` no prompt do LLM2 já funciona

3. **Exibição na decisão médica** — card "Caso Anterior"
   - Na tela de decisão do médico (`doctor/decision.html`), card destacado quando há negação recente
   - Mostra: decisão anterior, motivo, data, contagem de negações no período
   - Alerta visual (badge warning) para múltiplas negações

4. **Evento auditável** — CaseEvent
   - Registrar `PRIOR_CASE_LOOKUP` como CaseEvent quando lookup retorna resultados
   - Payload: prior_case_id, decision, reason, denial_count

5. **Exibição no case detail** — NIR e admin
   - Na tela de detalhe do caso, se houver lookup registrado, mostrar card de contexto

### Referência legada

- `infrastructure/db/prior_case_queries.py` — queries + `build_prior_case_context()`
- `application/ports/prior_case_query_port.py` — PriorCaseContext, PriorCaseSummary
- `post_room2_widget_service.py` — integração no widget

## Fora de escopo

- PWA (Fase 10)
- Busca manual por paciente (lookup é automático pelo agency_record_number)
- API REST
