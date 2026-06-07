# Design: Encerramento administrativo e filtro de atenção

## Estado atual

### FSM e filas

`Case.status` usa `django-fsm` e o estado `CLEANED` já representa caso encerrado operacionalmente. As listagens operacionais normalmente excluem `CLEANED` ou filtram estados específicos:

- NIR: `apps/intake/views.py::_my_cases_context()` usa `exclude(status=CaseStatus.CLEANED)`.
- Médico: fila pendente usa `WAIT_DOCTOR`.
- Agendador: fila pendente usa `WAIT_APPT`.
- Dashboard: lista todos os casos, inclusive `CLEANED`, e já tem detalhe read-only para manager/admin.

### Auditoria

A auditoria é append-only via `CaseEvent`. Transições FSM usam `Case._record_event()` e signal pós-save para criar eventos.

### Locks

Locks operacionais ficam nos campos:

- `locked_by`
- `locked_at`
- `locked_until`
- `lock_token`
- `lock_context`
- `lock_role`

Serviços existentes em `apps/cases/services.py` já fazem claim/release/renew/expire para filas específicas.

## Decisões

### D1. Usar `CLEANED` como terminal operacional

Não criar novo estado FSM. O encerramento administrativo deve transicionar para `CLEANED`.

Motivos:

- `CLEANED` já remove o caso das filas operacionais.
- Evita alterar todos os filtros de filas.
- Mantém a rastreabilidade pelo evento de auditoria, não pelo nome do estado.

### D2. Evento específico para diferenciar encerramento normal

Criar evento:

```text
CASE_ADMINISTRATIVELY_CLOSED
```

Payload mínimo:

```json
{
  "previous_status": "LLM_SUGGEST",
  "reason_code": "llm_failure",
  "reason_text": "LLM retornou fora do contrato e caso ficou preso",
  "active_role": "manager",
  "had_lock": true,
  "previous_lock": {
    "locked_by_id": 123,
    "locked_by_display": "...",
    "locked_until": "...",
    "lock_context": "doctor_decision",
    "lock_role": "doctor"
  },
  "post_schedule_issue_status": ""
}
```

O evento deve ser criado uma única vez por encerramento. Não criar `CLEANUP_TRIGGERED`/`CLEANUP_COMPLETED`, pois isso confundiria encerramento normal com intervenção administrativa.

### D3. Transição FSM excepcional explícita

Adicionar método no model `Case`, por exemplo:

```python
@transition(
    field=status,
    source=[...todos os estados exceto CLEANED...],
    target=CaseStatus.CLEANED,
)
def administratively_close(self, *, user=None, payload=None):
    self._record_event("CASE_ADMINISTRATIVELY_CLOSED", user=user, payload=payload or {})
```

Preferir lista explícita de fontes em vez de atualização direta do campo protegido. Se usar `source="*"`, garantir por teste que `CLEANED -> CLEANED` não gera evento duplicado.

### D4. Serviço transacional

Implementar serviço em `apps/cases/services.py`, por exemplo:

```python
def administratively_close_case(*, case: Case, user: Any, reason_code: str, reason_text: str, active_role: str) -> Case:
    ...
```

Responsabilidades:

1. validar `reason_text.strip()`;
2. reabrir o caso com `select_for_update()`;
3. rejeitar se já estiver `CLEANED`;
4. montar snapshot de status anterior, lock e intercorrência;
5. limpar campos de lock;
6. executar `case.administratively_close(user=user, payload=payload)`;
7. `case.save()`;
8. retornar caso recarregado.

Não apagar PDF, texto extraído, artefatos LLM, decisão médica, agendamento ou timeline.

#### Intercorrência pós-agendamento

Se houver `post_schedule_issue_status` ativo, o serviço deve registrar o valor no payload. Para evitar que o caso continue parecendo uma intercorrência ativa após `CLEANED`, é aceitável limpar campos de intercorrência **desde que** o snapshot completo esteja no payload. Se o implementador optar por não limpar, deve provar por teste que nenhuma fila operacional fica poluída. A opção preferida é limpar campos de intercorrência ativa no encerramento administrativo.

### D5. UI no detalhe do dashboard

Adicionar ação no detalhe do dashboard (`dashboard_case_detail`) usando o template compartilhado `templates/intake/case_detail.html`.

Contexto novo sugerido:

```python
"can_administratively_close": case.status != CaseStatus.CLEANED,
"administrative_close_url": reverse("dashboard:administrative_close", args=[case.case_id]),
"administrative_close_reason_choices": [...],
```

A ação deve aparecer apenas quando o contexto permitir. Views NIR/médico/agendador que reutilizem o template devem passar `False` ou depender de default seguro no template.

### D6. Rota POST no dashboard

Adicionar rota:

```python
path("<uuid:case_id>/administrative-close/", views.dashboard_administrative_close, name="administrative_close")
```

A view deve:

- ser `@login_required`;
- exigir `@role_required("manager", "admin")`;
- aceitar apenas POST (`@require_POST`);
- validar motivo;
- chamar o serviço;
- usar `messages.success/error`;
- redirecionar para `dashboard:case_detail` ou `dashboard:index`.

Preferência: redirecionar para o detalhe, para o supervisor ver o status `Concluído` e a timeline com o evento.

### D7. Filtro “Atenção necessária” no dashboard

Adicionar filtro por query string:

```text
/dashboard/?attention=1
```

O filtro compõe com filtros existentes (`status`, `date_from`, `date_to`) quando presentes, mas `attention=1` sempre deve excluir `CLEANED`.

Critérios iniciais determinísticos:

1. `FAILED` sempre entra.
2. Lock expirado entra:
   - `locked_by IS NOT NULL`
   - `locked_until IS NOT NULL`
   - `locked_until <= now`
3. Estados de processamento/handoff antigos entram se `updated_at <= now - 30min`:
   - `NEW`
   - `R1_ACK_PROCESSING`
   - `EXTRACTING`
   - `LLM_STRUCT`
   - `LLM_SUGGEST`
   - `R2_POST_WIDGET`
   - `DOCTOR_ACCEPTED`
   - `DOCTOR_DENIED`
   - `R3_POST_REQUEST`
   - `APPT_CONFIRMED`
   - `APPT_DENIED`
   - `R1_FINAL_REPLY_POSTED`
   - `CLEANUP_RUNNING`
4. Estados de espera humanos antigos entram se `updated_at <= now - 48h`:
   - `WAIT_DOCTOR`
   - `WAIT_APPT`
   - `WAIT_R1_CLEANUP_THUMBS`

Esses thresholds devem ficar em constantes no código, para ajuste futuro.

### D8. Motivo compacto nos cards

`_enrich_case()` no dashboard pode incluir:

```python
"attention_reason": get_attention_reason(case, now=timezone.now())
```

Motivos sugeridos:

- `Falha no processamento`
- `Lock expirado`
- `Processamento parado há mais de 30 min`
- `Aguardando ação humana há mais de 48 h`

Na listagem, exibir badge discreto:

```html
<span class="badge bg-warning text-dark">⚠ Atenção necessária</span>
<small class="text-muted">{{ item.attention_reason }}</small>
```

## Arquivos previstos

### Slice 001 — encerramento administrativo

| Arquivo | Tipo | Mudança |
|---------|------|---------|
| `apps/cases/models.py` | modificado | transição FSM excepcional |
| `apps/cases/services.py` | modificado | serviço transacional de encerramento |
| `apps/cases/tests/test_administrative_closure.py` | novo | testes unitários do serviço/FSM |
| `apps/dashboard/views.py` | modificado | contexto do detalhe + view POST |
| `apps/dashboard/urls.py` | modificado | rota POST |
| `templates/intake/case_detail.html` | modificado | formulário/botão de encerramento |
| `apps/dashboard/tests/test_dashboard.py` ou novo teste | modificado/novo | testes da UI/permissão |
| `apps/intake/views.py` | modificado | labels/dot para novo evento |

> Justificativa para >5 arquivos: o slice é vertical e precisa entregar fluxo completo com FSM, auditoria, permissão e UI. Não separar em camada horizontal sem valor ao usuário.

### Slice 002 — filtro de atenção

| Arquivo | Tipo | Mudança |
|---------|------|---------|
| `apps/dashboard/views.py` | modificado | query/filter + reason helper |
| `templates/dashboard/index.html` | modificado | preset/filtro + badge/motivo |
| `apps/dashboard/tests/test_dashboard.py` | modificado | testes do filtro e preservação de query |

## Riscos e mitigação

| Risco | Mitigação |
|-------|-----------|
| Confundir encerramento administrativo com sucesso normal | Evento específico e sem criar eventos de cleanup normal |
| Encerrar caso por engano | Confirmação explícita + motivo obrigatório + permissão manager/admin |
| Perder rastreabilidade de lock/intercorrência | Snapshot no payload antes de limpar campos |
| Quebrar filas operacionais | Usar `CLEANED`, que já é excluído ou não selecionado nas filas |
| Critérios de atenção gerarem falso positivo | Nome “Atenção necessária”, não “Travado”; thresholds conservadores para waits humanos |
| Usuário não autorizado acionar POST | `role_required("manager", "admin")`, CSRF e testes de bloqueio |
