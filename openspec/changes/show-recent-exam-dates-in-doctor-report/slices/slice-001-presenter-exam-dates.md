# Slice 001: Correção determinística do presenter médico para datas de exames recentes

## Contexto zero para implementador

O relatório técnico exibido para o médico em `templates/doctor/decision.html` usa `DoctorReportPresenter` de `apps/doctor/presenters.py`.

O LLM1 já persiste exames rastreados em:

```python
case.structured_data["tracked_exams"]
```

Cada exame pode ter:

```json
{
  "exam_type": "lab",
  "exam_label": "Hb",
  "result_value": "10.0 g/dL",
  "exam_datetime_iso": "2025-12-01T10:00:00",
  "is_most_recent": true
}
```

Hoje `DoctorReportPresenter._build_tracked_exam_lines()` mostra apenas:

```text
Hb: 10.0 g/dL (mais recente)
```

Mesmo quando `exam_datetime_iso` existe. O médico precisa ver a data.

## Objetivo do slice

Implementar somente a correção determinística no presenter médico:

```text
structured_data.tracked_exams[] com is_most_recent=true e exam_datetime_iso válido
→ relatório técnico mostra a data/hora do exame recente
```

Este slice não altera prompts, LLM, schema, banco, views ou templates.

## Arquivos esperados

Tocar idealmente apenas:

1. `apps/doctor/presenters.py`
2. `apps/doctor/tests/test_presenter.py`

Se tocar qualquer outro arquivo, justificar no relatório do slice.

## Requisitos funcionais

### R1. Exibir data para exame recente com `exam_datetime_iso`

Quando um exame tiver:

```python
is_most_recent is True
exam_datetime_iso = "2025-12-01T10:00:00"
```

a linha deve conter:

```text
Hb: 10.0 g/dL
01/12/2025
```

Formato recomendado:

```text
Hb: 10.0 g/dL (mais recente em 01/12/2025 10:00)
```

### R2. Exibir apenas data quando não houver hora útil

Para:

```python
exam_datetime_iso = "2025-12-01"
```

a linha deve conter:

```text
01/12/2025
```

Formato recomendado:

```text
Hb: 10.0 g/dL (mais recente em 01/12/2025)
```

### R3. Preservar fallback sem data

Quando `is_most_recent is True` mas `exam_datetime_iso` estiver ausente/vazio/inválido, manter indicação clara de ausência de data.

Texto atual aceitável:

```text
Hb: 10.0 g/dL (recência indeterminada (sem data no laudo))
```

Pode ajustar levemente o texto, desde que contenha claramente:

- recência indeterminada ou equivalente;
- sem data no laudo.

### R4. Não alterar exames não recentes

Exames com `is_most_recent is False` não devem ganhar marcador de data/recência por este slice.

### R5. Robustez para data inválida

Se `exam_datetime_iso` for uma string inválida, o presenter não deve lançar exceção. Deve cair no fallback sem data.

## TDD obrigatório

Antes de implementar, adicionar testes falhando em `apps/doctor/tests/test_presenter.py`.

### Testes mínimos

1. `test_tracked_exam_recent_with_datetime_shows_date_and_time`
   - montar `DoctorReportPresenter` com `tracked_exams` contendo Hb recente e `exam_datetime_iso="2025-12-01T10:00:00"`;
   - `report["context"]["tracked_exam_lines"]` deve conter `Hb`, `10.0 g/dL`, `mais recente`, `01/12/2025` e `10:00`.

2. `test_tracked_exam_recent_with_date_only_shows_date`
   - usar `exam_datetime_iso="2025-12-01"`;
   - deve conter `01/12/2025`;
   - não exigir `00:00`.

3. `test_tracked_exam_recent_without_datetime_keeps_no_date_fallback`
   - sem `exam_datetime_iso`;
   - deve conter indicação de `sem data`.

4. `test_tracked_exam_recent_with_invalid_datetime_does_not_crash_and_uses_fallback`
   - usar `exam_datetime_iso="data inválida"`;
   - build_report não lança exceção;
   - linha contém indicação de `sem data`.

5. `test_tracked_exam_not_recent_does_not_show_recent_date_marker`
   - exame com `is_most_recent=False` e `exam_datetime_iso` preenchido;
   - linha não deve conter `mais recente` nem a data formatada `01/12/2025`.

## Restrições estritas

- Não alterar schema Pydantic.
- Não alterar prompt LLM1 neste slice.
- Não alterar template `templates/doctor/decision.html` salvo se impossível resolver pelo presenter; se alterar, justificar.
- Não mudar lógica de qual exame é mais recente.
- Não alterar dados persistidos.
- Não introduzir dependência externa.
- Não criar função genérica global para todo o projeto.

## Critérios de sucesso

- [ ] Testes novos falham antes da implementação e passam após.
- [ ] Data/hora aparece no relatório quando `exam_datetime_iso` existe.
- [ ] Fallback sem data continua claro.
- [ ] Data inválida não quebra o presenter.
- [ ] Exames não recentes não ganham marcador indevido.
- [ ] Quality gate completo passa.

## Gates de autoavaliação

Responder no relatório do slice:

1. Qual função formata `exam_datetime_iso` e como ela trata valor inválido?
2. O código altera a escolha de `is_most_recent`? Se sim, está errado.
3. Qual teste prova que data/hora aparece?
4. Qual teste prova que data inválida não quebra a tela?
5. Algum arquivo fora dos dois esperados foi alterado? Se sim, por quê?

## Prompt pronto para implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md, openspec/changes/show-recent-exam-dates-in-doctor-report/proposal.md, design.md, tasks.md and slices/slice-001-presenter-exam-dates.md.
Implement ONLY Slice 001.
Use TDD strictly: first add failing tests in apps/doctor/tests/test_presenter.py, then implement the minimal presenter change.
Do not change prompts, LLM services, schemas, database, views, templates, FSM, policy, or decision logic.
Goal: DoctorReportPresenter must show formatted exam_datetime_iso for tracked_exams with is_most_recent=true. Use DD/MM/AAAA or DD/MM/AAAA HH:MM. Invalid/missing datetime must not crash and must keep a clear “sem data no laudo” fallback. Non-recent exams must not receive recent/date marker.
Run: uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
Update openspec/changes/show-recent-exam-dates-in-doctor-report/tasks.md marking Slice 001 complete only if all gates pass.
Create a detailed temporary markdown report with before/after snippets and answers to the self-evaluation gates.
Commit and push.
Return REPORT_PATH=<path> and stop. Do not start Slice 002 without explicit user confirmation.
```
