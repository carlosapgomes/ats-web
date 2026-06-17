# Slice 001: Separar encerramento administrativo em resultado final, badges e cards de totalização

## Contexto

Supervisor/admin podem encerrar um caso administrativamente. O serviço registra evento `CASE_ADMINISTRATIVELY_CLOSED` e move o caso para `CLEANED`.

O problema atual é que `CLEANED` também é usado por encerramentos normais. No dashboard, isso causa duas leituras incorretas:

1. No detalhe, o card “Resultado Final” pode mostrar **Agendamento Confirmado** para caso encerrado administrativamente.
2. Nos cards de totalização, encerrados administrativos sem decisão continuam sobrando em **Em Andamento**.

Exemplo operacional reportado: 11 casos no dia, 1 aceito, 0 negados, 10 em processamento; desses 10, 4 já foram encerrados administrativamente. O dashboard deve mostrar esses 4 separadamente e reduzir “Em Andamento” para 6.

## Objetivo do slice

Implementar uma correção vertical mínima, end-to-end:

- detectar encerramento administrativo pelo evento `CASE_ADMINISTRATIVELY_CLOSED`;
- renderizar “Encerrado administrativamente” no detalhe e na listagem;
- adicionar card “Encerrados admin.” na totalização;
- remover encerrados administrativos do residual “Em Andamento”.

## Arquivos alvo

Idealmente tocar apenas:

1. `apps/dashboard/views.py`
2. `templates/intake/case_detail.html`
3. `templates/dashboard/index.html`
4. `apps/dashboard/tests/test_dashboard.py`

Se precisar tocar mais arquivos, registrar justificativa no relatório do slice.

## Comportamento esperado

### Resultado final no detalhe

Para qualquer caso com evento `CASE_ADMINISTRATIVELY_CLOSED`, o card “Resultado Final” deve mostrar:

- badge: **Encerrado administrativamente**;
- texto: “Caso removido das filas operacionais por intervenção administrativa. Este encerramento não representa confirmação de agendamento.”;
- motivo/justificativa se `reason_text` estiver no payload;
- status anterior se `previous_status` estiver no payload.

Esse branch deve ter prioridade sobre:

- revisão manual;
- recusa médica;
- vinda imediata;
- agendamento negado;
- agendamento confirmado.

### Badge/listagem do dashboard

`_compute_result(case)` deve retornar imediatamente:

```python
("🔒 Encerrado administrativamente", "bg-secondary")
```

quando o caso tiver evento `CASE_ADMINISTRATIVELY_CLOSED`.

### Totalização

`_compute_summary()` deve retornar também:

```python
"administratively_closed": admin_closed_count
```

E `in_progress` deve ser:

```python
total_today - accepted - denied - admin_closed_count
```

com `accepted` e `denied` calculados excluindo casos administrativamente encerrados.

Exemplo-alvo:

```python
{
    "total_today": 11,
    "accepted": 1,
    "denied": 0,
    "administratively_closed": 4,
    "in_progress": 6,
}
```

## Plano TDD

### RED

Adicionar testes falhando em `apps/dashboard/tests/test_dashboard.py`:

1. `test_administrative_closed_detail_shows_admin_outcome_not_confirmed`
   - criar caso aceito/confirmado;
   - encerrar com `administratively_close_case()`;
   - acessar `dashboard:case_detail`;
   - assert contém “Encerrado administrativamente”;
   - assert não contém badge/texto “Agendamento Confirmado” no card de resultado.

2. `test_summary_separates_administrative_closed_from_in_progress`
   - criar cenário 11/1/0/4/6;
   - assert `_compute_summary()` retorna os números esperados.

3. `test_administrative_closed_confirmed_case_counts_only_as_admin_closed`
   - caso aceito/confirmado encerrado administrativamente;
   - assert `accepted == 0` e `administratively_closed == 1`.

4. `test_dashboard_list_result_badge_shows_administrative_closed`
   - caso encerrado administrativamente;
   - abrir `dashboard:index`;
   - assert contém “Encerrado administrativamente”.

### GREEN

Implementar o mínimo:

1. Helper em `apps/dashboard/views.py` para localizar evento administrativo.
2. Prioridade administrativa em `_compute_result()`.
3. Prioridade administrativa em `dashboard_case_detail()`.
4. Novo branch no template `templates/intake/case_detail.html`.
5. Novo campo no retorno de `_compute_summary()`.
6. Novo card em `templates/dashboard/index.html`.

### REFACTOR

- Evitar duplicação excessiva na detecção do evento.
- Manter nomes claros: `administratively_closed`, `admin_close_event`, `admin_closed_cases`.
- Não criar abstrações globais ou novo app/service para este bugfix.
- Garantir que os contadores permaneçam mutuamente exclusivos.

## Critérios de sucesso

- [ ] Caso administrativamente encerrado nunca aparece como “Agendamento Confirmado” no detalhe do dashboard.
- [ ] Caso administrativamente encerrado aparece como “Encerrado administrativamente” na listagem.
- [ ] Card “Encerrados admin.” aparece na totalização.
- [ ] `Em Andamento` exclui encerrados administrativos.
- [ ] Caso aceito/confirmado e depois encerrado administrativamente conta somente como administrativo.
- [ ] Testes novos passam.
- [ ] Quality gate passa ou eventuais falhas externas são documentadas.

## Gates de autoavaliação

Antes de concluir, responder no relatório:

1. Como o código diferencia `CLEANED` normal de `CLEANED` administrativo?
2. Em quais pontos a regra administrativa tem prioridade sobre agendamento confirmado?
3. O que acontece com um caso `accept + confirmed` encerrado administrativamente nos cards?
4. O card “Em Andamento” ainda pode conter caso com `CASE_ADMINISTRATIVELY_CLOSED`? Se sim, por quê?
5. Quais testes provam a correção do cenário 11/1/0/4/6?

## Prompt pronto para implementador LLM

```text
Read AGENTS.md and PROJECT_CONTEXT.md first.
Implement ONLY openspec/changes/fix-administrative-closure-dashboard-semantics/slices/slice-001-dashboard-admin-closure-semantics.md.
Use TDD: add failing dashboard tests first, then implement minimally.
Keep the slice lean and touch ideally only:
- apps/dashboard/views.py
- templates/intake/case_detail.html
- templates/dashboard/index.html
- apps/dashboard/tests/test_dashboard.py

Required behavior:
- CASE_ADMINISTRATIVELY_CLOSED has priority over all normal result classifications.
- Dashboard detail result card shows “Encerrado administrativamente”, not “Agendamento Confirmado”.
- Dashboard list result badge shows “Encerrado administrativamente”.
- Summary cards include administratively_closed and subtract it from in_progress.
- accepted/denied/admin_closed/in_progress must be mutually exclusive.

Run quality gate from AGENTS.md, update tasks.md, create temp markdown report with before/after snippets, commit and push, then stop.
```
