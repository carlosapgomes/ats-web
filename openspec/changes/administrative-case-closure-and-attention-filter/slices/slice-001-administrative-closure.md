# Slice 001: Encerramento administrativo auditável

## Contexto zero para implementador

O sistema é um monolito Django SSR. A entidade central é `apps.cases.models.Case`, com status controlado por `django-fsm`. O estado `CaseStatus.CLEANED` já é o terminal operacional: casos `CLEANED` saem das filas de trabalho e ficam disponíveis apenas por rotas de auditoria/dashboard.

Problema operacional: alguns casos podem ficar presos por erro de LLM, bug, worker interrompido, falha de handoff ou lock estranho. Esses casos continuam poluindo filas de NIR/médico/agendador. O supervisor (`manager`) e o administrador (`admin`) precisam de uma ação excepcional para retirar o caso da operação sem apagar histórico.

A auditoria é `CaseEvent` append-only. Transições FSM chamam `Case._record_event()` e o signal pós-save cria o evento.

O dashboard de supervisor/admin fica em `apps/dashboard/views.py` e renderiza detalhes por `templates/intake/case_detail.html` via `dashboard_case_detail`.

Leia antes de implementar:

- `AGENTS.md`
- `PROJECT_CONTEXT.md`
- `openspec/changes/administrative-case-closure-and-attention-filter/proposal.md`
- `openspec/changes/administrative-case-closure-and-attention-filter/design.md`
- `openspec/changes/administrative-case-closure-and-attention-filter/tasks.md`
- este slice

## Objetivo do slice

Entregar fluxo vertical completo:

```text
Supervisor/admin abre detalhe do dashboard
→ informa motivo obrigatório
→ confirma encerramento administrativo
→ caso vai para CLEANED
→ lock/intercorrência operacional são limpos quando aplicável
→ evento auditável aparece na timeline
→ caso sai das filas operacionais existentes
```

## Arquivos esperados

Este slice provavelmente tocará mais de 5 arquivos por ser uma entrega vertical com FSM + serviço + UI + auditoria. Mantenha o mínimo necessário e justifique no relatório se tocar arquivos adicionais.

1. `apps/cases/models.py`
2. `apps/cases/services.py`
3. `apps/cases/tests/test_administrative_closure.py` ou arquivo equivalente
4. `apps/dashboard/views.py`
5. `apps/dashboard/urls.py`
6. `templates/intake/case_detail.html`
7. `apps/dashboard/tests/test_dashboard.py` ou arquivo equivalente
8. `apps/intake/views.py` para label/dot do novo evento

Evite criar nova tabela ou migração de campos. Não criar novo estado FSM.

## Requisitos funcionais

### R1. Transição FSM excepcional

Em `apps/cases/models.py`, adicionar transição para `CLEANED` a partir de qualquer estado não `CLEANED`.

Nome sugerido:

```python
def administratively_close(self, *, user=None, payload=None):
    ...
```

Evento obrigatório:

```text
CASE_ADMINISTRATIVELY_CLOSED
```

Não criar eventos `CLEANUP_TRIGGERED` ou `CLEANUP_COMPLETED`.

Preferência: source list explícita com todos os `CaseStatus` exceto `CLEANED`.

### R2. Serviço transacional

Em `apps/cases/services.py`, implementar serviço com assinatura equivalente:

```python
def administratively_close_case(
    *,
    case: Case,
    user: Any,
    reason_code: str,
    reason_text: str,
    active_role: str,
) -> Case:
    ...
```

Validações:

- `reason_text.strip()` é obrigatório;
- `reason_code` é obrigatório e deve ser um dos códigos aceitos;
- caso já `CLEANED` deve gerar erro controlado (`ValueError` é aceitável);
- usar `transaction.atomic()`;
- reabrir o caso com `select_for_update()` para evitar corrida.

Códigos sugeridos:

```python
ADMINISTRATIVE_CLOSURE_REASONS = {
    "processing_error": "Erro de processamento",
    "llm_failure": "Falha do LLM",
    "system_bug": "Bug do sistema",
    "stuck_lock": "Reserva/lock travado",
    "duplicate_reprocess": "Duplicado/reapresentação manual",
    "other": "Outro",
}
```

Payload mínimo do evento:

```python
{
    "previous_status": previous_status,
    "reason_code": reason_code,
    "reason_text": reason_text.strip(),
    "active_role": active_role,
    "had_lock": bool(previous_locked_by_id),
    "previous_lock": {...},
    "post_schedule_issue_status": previous_issue_status,
}
```

O serviço deve limpar os campos de lock:

```python
locked_by = None
locked_at = None
locked_until = None
lock_token = None
lock_context = ""
lock_role = ""
```

Se houver intercorrência pós-agendamento ativa (`post_schedule_issue_status`), a opção preferida é limpar os campos de intercorrência após registrar snapshot no payload, para não deixar o caso parecendo operacionalmente ativo mesmo estando `CLEANED`.

### R3. Label de auditoria

Em `apps/intake/views.py`, adicionar:

```python
EVENT_LABELS["CASE_ADMINISTRATIVELY_CLOSED"] = "Encerrado administrativamente"
EVENT_DOT_CSS["CASE_ADMINISTRATIVELY_CLOSED"] = "system"
```

Use o padrão existente de dicionário literal, não mutação no fim do arquivo.

### R4. Rota POST no dashboard

Em `apps/dashboard/urls.py`, adicionar rota:

```python
path("<uuid:case_id>/administrative-close/", views.dashboard_administrative_close, name="administrative_close")
```

Em `apps/dashboard/views.py`, criar view:

- `@login_required`
- `@role_required("manager", "admin")`
- `@require_POST`
- busca o caso por UUID;
- lê `reason_code` e `reason_text` do POST;
- chama `administratively_close_case(...)` com `active_role=request.session.get("active_role", "")`;
- em sucesso, `messages.success` e redirect para `dashboard:case_detail`;
- em erro de validação, `messages.error` e redirect para `dashboard:case_detail`.

Não aceitar GET para mudar estado.

### R5. Formulário no detalhe do dashboard

Em `dashboard_case_detail`, passar contexto somente para manager/admin:

```python
"can_administratively_close": case.status != CaseStatus.CLEANED,
"administrative_close_url": reverse("dashboard:administrative_close", args=[case.case_id]),
"administrative_close_reason_choices": ADMINISTRATIVE_CLOSURE_REASON_CHOICES,
```

Em `templates/intake/case_detail.html`, dentro do card de ações, renderizar uma seção de encerramento administrativo quando `can_administratively_close` for verdadeiro.

Requisitos do formulário:

- método POST;
- CSRF;
- select `reason_code` obrigatório;
- textarea/input `reason_text` obrigatório;
- botão visualmente perigoso (`btn-outline-danger` ou similar);
- confirmação explícita via texto e/ou `onclick="return confirm(...)"`;
- texto deve deixar claro: “remove das filas operacionais; permanece na auditoria”.

Não exibir essa ação para NIR/médico/agendador. Como o template é compartilhado, use default seguro: se a variável não existir, nada aparece.

### R6. Caso encerrado sai das filas operacionais

Não altere diretamente as filas. O efeito esperado vem do status `CLEANED`:

- `intake:my_cases` exclui `CLEANED`;
- fila médica filtra `WAIT_DOCTOR`;
- fila scheduler filtra `WAIT_APPT`.

Adicione testes que provem pelo menos a fila NIR e uma fila operacional específica relevante ao status testado.

## TDD obrigatório

Antes de implementar, adicionar testes falhando.

### Testes mínimos de serviço/FSM

1. `test_administrative_close_moves_non_cleaned_case_to_cleaned`
   - criar caso em `LLM_SUGGEST` ou `WAIT_DOCTOR`;
   - chamar serviço;
   - assert `status == CLEANED`.

2. `test_administrative_close_creates_audit_event_with_previous_status_and_reason`
   - assert existe `CaseEvent(event_type="CASE_ADMINISTRATIVELY_CLOSED")`;
   - payload contém `previous_status`, `reason_code`, `reason_text`, `active_role`.

3. `test_administrative_close_requires_reason_text`
   - motivo vazio levanta erro;
   - status permanece inalterado;
   - evento não é criado.

4. `test_administrative_close_rejects_already_cleaned_case`
   - caso `CLEANED` não deve gerar novo evento.

5. `test_administrative_close_clears_lock_fields`
   - criar lock manual ou via serviço existente;
   - encerrar;
   - todos os campos de lock estão limpos;
   - payload registra `had_lock=True` e snapshot.

6. `test_administrative_close_clears_active_post_schedule_issue_or_records_snapshot`
   - se optar por limpar campos de intercorrência, assert campos limpos e snapshot no payload;
   - se optar por manter, justificar e provar que não aparece em fila operacional.

### Testes mínimos de dashboard/UI

7. `test_dashboard_detail_shows_administrative_close_form_for_manager_on_operational_case`
   - login com papel ativo `manager`;
   - caso não `CLEANED`;
   - GET detalhe contém texto “Encerrar administrativamente” e action correta.

8. `test_dashboard_detail_hides_administrative_close_form_for_cleaned_case`
   - caso `CLEANED`;
   - form não aparece.

9. `test_dashboard_administrative_close_post_requires_manager_or_admin`
   - usuário com papel `doctor`, `scheduler` ou `nir` não consegue postar;
   - status não muda.

10. `test_dashboard_administrative_close_post_requires_reason`
    - POST sem `reason_text`;
    - status não muda;
    - evento não existe.

11. `test_dashboard_administrative_close_post_success_redirects_and_closes_case`
    - POST válido;
    - redirect para detalhe;
    - status `CLEANED`;
    - evento criado.

12. `test_administratively_closed_case_leaves_operational_lists`
    - criar caso em status operacional;
    - encerrar;
    - assert não aparece em `intake:my_cases`;
    - se status original era `WAIT_DOCTOR`, assert não aparece na fila médica; se era `WAIT_APPT`, assert não aparece na fila scheduler.

13. `test_timeline_shows_administrative_closure_label`
    - após encerramento, detalhe dashboard mostra “Encerrado administrativamente”.

## Critérios de sucesso

- [ ] TDD seguido: testes novos falham antes da implementação e passam após.
- [ ] Não há novo estado FSM nem migração de campo.
- [ ] Encerramento usa transição FSM, não update direto do campo protegido.
- [ ] `CASE_ADMINISTRATIVELY_CLOSED` diferencia claramente de cleanup normal.
- [ ] Motivo obrigatório é validado no serviço e na rota POST.
- [ ] Apenas `manager`/`admin` com papel ativo conseguem encerrar.
- [ ] Caso encerrado fica `CLEANED` e sai das filas operacionais.
- [ ] Lock é limpo e auditado no payload.
- [ ] Timeline tem label legível.
- [ ] Quality gate do AGENTS.md passa.

## Gates de autoavaliação

Responder no relatório do slice:

1. O código criou novo estado FSM ou nova tabela? Se sim, está fora do escopo.
2. A mudança de status passa por método FSM? Onde?
3. O evento criado é `CASE_ADMINISTRATIVELY_CLOSED` e não cleanup normal? Qual teste prova?
4. POST sem motivo mantém o status anterior? Qual teste prova?
5. Um usuário sem `manager`/`admin` consegue acionar a rota? Qual teste prova que não?
6. O lock é limpo? Qual teste prova?
7. O caso encerrado some das filas operacionais? Quais URLs foram testadas?
8. O relatório contém snippets antes/depois dos pontos principais?

## Prompt pronto para implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md, openspec/changes/administrative-case-closure-and-attention-filter/proposal.md, design.md, tasks.md and slices/slice-001-administrative-closure.md.
Implement ONLY Slice 001.
Use vertical slicing and TDD: first add failing tests for service/FSM/dashboard UI, then implement the minimal code.
Do not create a new FSM state and do not delete cases. Use CaseStatus.CLEANED as terminal operational state.
Add an explicit FSM transition for administrative closure from any non-CLEANED state to CLEANED.
Create a transactional service that validates reason_code/reason_text, records payload with previous_status/lock/intercurrence snapshot, clears locks, and creates CaseEvent CASE_ADMINISTRATIVELY_CLOSED.
Add manager/admin-only POST route on dashboard and a form in the shared case_detail template shown only for dashboard manager/admin operational cases.
Ensure NIR/doctor/scheduler cannot see or execute this action.
Run: uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
Update openspec/changes/administrative-case-closure-and-attention-filter/tasks.md when this slice is complete.
Create a detailed temporary markdown report with before/after snippets, commit and push.
Return REPORT_PATH=<path> and stop. Do not start Slice 002 without explicit confirmation.
```
