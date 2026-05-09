# Slice 2: UI — card caso anterior na decisão médica + case detail

## Objetivo

Exibir contexto de caso anterior na tela de decisão do médico e no detalhe do caso.

## Arquivos

### 1. `apps/doctor/views.py` — modificado

Na view `doctor_decision()`:
- Se case tem `agency_record_number`, chamar `lookup_prior_case_context()`
- Adicionar `prior_context` ao contexto do template
- Formatar `decision_display` ("Triagem Negada" / "Agendamento Negado")

### 2. `templates/doctor/decision.html` — modificado

Card condicional "Caso Anterior — Negação Recente":
- Border warning, header amarelo
- Decisão, motivo, data
- Badge danger se múltiplas negações (>1)
- Posicionado antes do formulário de decisão

### 3. `templates/intake/case_detail.html` — modificado

Card condicional no case_detail:
- Verificar se há CaseEvent PRIOR_CASE_LOOKUP
- Se sim, mostrar card compacto com informações

### 4. Testes

- `apps/doctor/tests/test_views.py`: ~3 testes
  - Card aparece quando há negação recente
  - Card não aparece quando não há caso anterior
  - Card mostra contagem quando múltiplas negações
- `apps/intake/tests/test_case_detail.py`: ~2 testes
  - Card aparece quando há PRIOR_CASE_LOOKUP event
  - Card não aparece sem o event

## Critérios de sucesso

- [ ] Card "Caso Anterior" aparece na decisão médica quando há negação recente
- [ ] Card não aparece quando não há contexto
- [ ] Motivo e data exibidos corretamente
- [ ] Badge de múltiplas negações funciona
- [ ] Card aparece no case_detail se há evento PRIOR_CASE_LOOKUP
- [ ] ~5 testes passando
- [ ] ruff + mypy + pytest clean

## Arquivos: ideal ≤ 4
