# Slice 002 Report — UI: card caso anterior na decisão médica + case detail

## Status: ✅ COMPLETO

## Resultados do Quality Gate

| Check | Resultado |
|-------|-----------|
| `ruff check .` | ✅ All checks passed |
| `ruff format --check .` | ✅ 111 files already formatted |
| `mypy .` | ✅ Success: no issues found in 119 source files |
| `pytest` | ✅ 532 passed |

## Arquivos modificados (6 files, +248 linhas)

### 1. `apps/doctor/views.py` (+21 linhas)

**Adicionado:** `PRIOR_DECISION_DISPLAY` map para traduzir códigos de decisão em labels em português:
```python
PRIOR_DECISION_DISPLAY: dict[str, str] = {
    "doctor_denied": "Triagem Negada",
    "appointment_denied": "Agendamento Negado",
}
```

**Modificado:** `_build_decision_context()` — agora consulta `lookup_prior_case_context()` quando o caso tem `agency_record_number`, e injeta `prior_context` e `prior_decision_display` no contexto do template.

### 2. `templates/doctor/decision.html` (+29 linhas)

**Adicionado:** Card condicional "Caso Anterior — Negação Recente" na coluna direita, antes do formulário de decisão:
- `border-warning` + header amarelo (`bg-warning text-dark`)
- Tabela com Decisão, Data, Motivo
- Badge `bg-danger` condicional quando `prior_denial_count_7d > 1`

### 3. `apps/intake/views.py` (+13 linhas)

**Modificado:** `case_detail()` — extrai o primeiro evento `PRIOR_CASE_LOOKUP` dos eventos do caso, serializa `payload` (prior_case_id, decision, prior_denial_count_7d) e passa como `prior_case_lookup` no contexto.

### 4. `templates/intake/case_detail.html` (+27 linhas)

**Adicionado:** Card condicional "Caso Anterior — Negação Recente" entre o resultado final e a timeline:
- `border-warning` no card
- Decisão mapeada para português ("Triagem Negada" / "Agendamento Negado")
- Badge vermelho com contagem quando `prior_denial_count_7d > 1`

### 5. `apps/doctor/tests/test_views.py` (+105 linhas) — 3 testes

| Teste | Descrição |
|-------|-----------|
| `test_prior_case_card_shows_when_recent_denial` | Card aparece quando há negação recente com mesmo ARN |
| `test_prior_case_card_hidden_when_no_prior` | Card não aparece sem caso anterior |
| `test_prior_case_card_shows_multiple_denials_badge` | Badge "2 negações em 7 dias" aparece com múltiplas negações |

### 6. `apps/intake/tests/test_case_detail.py` (+53 linhas) — 2 testes

| Teste | Descrição |
|-------|-----------|
| `test_prior_case_card_appears_with_prior_case_lookup_event` | Card aparece quando há evento PRIOR_CASE_LOOKUP com payload |
| `test_prior_case_card_hidden_without_event` | Card não aparece sem evento PRIOR_CASE_LOOKUP |

## Critérios de Sucesso

- [x] Card "Caso Anterior" aparece na decisão médica quando há negação recente
- [x] Card não aparece quando não há contexto
- [x] Motivo e data exibidos corretamente
- [x] Badge de múltiplas negações funciona
- [x] Card aparece no case_detail se há evento PRIOR_CASE_LOOKUP
- [x] 5 testes passando
- [x] ruff + mypy + pytest clean
