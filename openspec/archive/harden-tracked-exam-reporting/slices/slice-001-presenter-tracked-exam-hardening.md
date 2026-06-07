# Slice 001: Presenter — filtrar ausência de exame e mostrar data em todos os exames válidos

## Contexto zero para implementador

O relatório técnico do médico é montado por `DoctorReportPresenter` em:

```text
apps/doctor/presenters.py
```

A função relevante é:

```python
DoctorReportPresenter._build_tracked_exam_lines()
```

Após o change `show-recent-exam-dates-in-doctor-report`, exames recentes com `exam_datetime_iso` passaram a mostrar data. Porém, em um caso real, o LLM1 gerou itens como:

```json
{"exam_label": "ECG", "result_value": "Sem exame", "exam_datetime_iso": "2026-06-06T07:00:00", "is_most_recent": true}
```

O presenter exibiu:

```text
ECG: Sem exame (mais recente em 06/06/2026 07:00)
```

Isso é confuso para o médico: “Sem exame” não deve ser tratado como exame recente.

Também foi identificado que exames válidos não recentes com data podem aparecer sem data. O relatório deve mostrar a data de todo exame válido que tenha `exam_datetime_iso`, destacando apenas o mais recente.

## Objetivo do slice

Implementar somente hardening determinístico do presenter:

1. não renderizar entradas de `tracked_exams` cujo resultado indique ausência de exame;
2. mostrar data formatada para todos os exames válidos com `exam_datetime_iso`, mesmo quando `is_most_recent=false`;
3. manter marcador de “mais recente” apenas para `is_most_recent=true`.

Este slice não altera prompt, LLM, schema, banco, views, templates, FSM ou decisão.

## Arquivos esperados

Tocar idealmente apenas:

1. `apps/doctor/presenters.py`
2. `apps/doctor/tests/test_presenter.py`

Se tocar qualquer outro arquivo, justificar no relatório do slice.

## Requisitos funcionais

### R1. Filtrar ausência de exame

Não renderizar em `tracked_exam_lines` itens cujo `result_value` indique ausência de exame.

Valores mínimos que devem ser tratados como ausência:

- `Sem exame`
- `Sem Exame`
- `sem exames`
- `Não realizado`
- `Nao realizado`
- `Não consta`
- `Nao consta`
- `Ausente`
- `Sem laudo`
- `Sem resultado`

Exemplo:

```python
{"exam_label": "ECG", "result_value": "Sem exame", "exam_datetime_iso": "2026-06-06T07:00:00", "is_most_recent": True}
```

não deve gerar linha `ECG: Sem exame ...`.

### R2. Mostrar data em exame válido não recente

Para:

```python
{
    "exam_label": "LAB externo",
    "result_value": "HB 12,1; HT 38,3",
    "exam_datetime_iso": "2026-05-28T08:30:00",
    "is_most_recent": False,
}
```

a linha deve conter:

- `LAB externo`
- `HB 12,1`
- `28/05/2026`
- `08:30`

E não deve conter `mais recente`.

### R3. Mostrar data e destaque em exame válido recente

Para:

```python
{
    "exam_label": "LAB interno",
    "result_value": "HB 12,9; HT 34,1",
    "exam_datetime_iso": "2026-06-01T00:00:00",
    "is_most_recent": True,
}
```

a linha deve conter:

- `LAB interno`
- `HB 12,9`
- `01/06/2026`
- `mais recente`

### R4. Preservar robustez para data inválida

Se exame válido tiver `exam_datetime_iso="data inválida"`, `build_report()` não deve lançar exceção. A linha pode aparecer sem data, mas deve manter valor do exame.

### R5. Não aplicar heurística agressiva

Não ocultar resultados válidos que contenham palavras negativas em outro contexto clínico. O filtro deve mirar valores que claramente significam ausência total do exame/laudo/resultado.

## TDD obrigatório

Antes de implementar, adicionar testes falhando em `apps/doctor/tests/test_presenter.py`.

### Testes mínimos

1. `test_tracked_exam_absent_result_is_not_rendered`
   - criar `tracked_exams` com ECG `result_value="Sem exame"`, data e `is_most_recent=True`;
   - assertar que nenhuma linha contém `ECG` nem `Sem exame`.

2. `test_tracked_exam_absent_result_variants_are_not_rendered`
   - parametrizar ou testar lista mínima: `Não realizado`, `Nao consta`, `Ausente`, `Sem laudo`, `Sem resultado`;
   - assertar que não geram linhas.

3. `test_tracked_exam_valid_not_recent_shows_date_without_recent_marker`
   - exame laboratorial válido não recente com data;
   - assertar data/hora presente;
   - assertar ausência de `mais recente`.

4. `test_tracked_exam_valid_recent_shows_date_and_recent_marker`
   - exame laboratorial válido recente com data;
   - assertar data presente e `mais recente` presente.

5. `test_tracked_exam_valid_invalid_datetime_keeps_exam_without_crashing`
   - exame válido com data inválida;
   - assertar que `build_report()` retorna linha com label/valor;
   - assertar que não lança exceção.

## Restrições estritas

- Não alterar prompt neste slice.
- Não alterar `apps/pipeline/*`.
- Não alterar schema Pydantic.
- Não alterar template, salvo se impossível resolver no presenter; se alterar, justificar.
- Não criar migração.
- Não alterar seleção de `is_most_recent`.
- Não reprocessar casos existentes.
- Não introduzir dependência externa.

## Critérios de sucesso

- [ ] Testes novos falham antes da implementação e passam após.
- [ ] “Sem exame” e variantes não aparecem como exame rastreado.
- [ ] Exame válido não recente com data mostra data.
- [ ] Exame válido recente com data mostra data e destaque.
- [ ] Data inválida não quebra o relatório.
- [ ] Quality gate completo passa.

## Gates de autoavaliação

Responder no relatório do slice:

1. Qual helper identifica ausência de exame e quais variantes cobre?
2. O filtro pode ocultar resultados válidos? Como o código evita heurística agressiva?
3. Qual teste prova que “Sem exame” não é renderizado?
4. Qual teste prova que exame não recente com data mostra data?
5. O slice alterou prompt/schema/LLM? Se sim, está errado.

## Prompt pronto para implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md, openspec/changes/harden-tracked-exam-reporting/proposal.md, design.md, tasks.md and slices/slice-001-presenter-tracked-exam-hardening.md.
Implement ONLY Slice 001.
Use TDD strictly: first add failing tests in apps/doctor/tests/test_presenter.py for filtering absent exam results and showing dates on all valid tracked exams. Then implement the minimal presenter change in apps/doctor/presenters.py.
Do not change prompts, LLM services, schemas, database, views, templates, FSM, policy, or decision logic.
Goal: DoctorReportPresenter must not render tracked_exams where result_value means absence of exam (Sem exame, Não realizado, Não consta, Ausente, Sem laudo, Sem resultado). It must show formatted exam_datetime_iso for every valid tracked exam with date, not only is_most_recent=true. Only is_most_recent=true gets the “mais recente” marker. Invalid datetime must not crash.
Run: uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
Update openspec/changes/harden-tracked-exam-reporting/tasks.md marking Slice 001 complete only if all gates pass.
Create a detailed temporary markdown report with before/after snippets and answers to the self-evaluation gates.
Commit and push.
Return REPORT_PATH=<path> and stop. Do not start Slice 002 without explicit user confirmation.
```
