# Design: Filas compartilhadas com lease temporário

## Estado atual

### Médico

`apps/doctor/views.py::_doctor_queue_context` lista todos os casos em:

```python
Case.objects.filter(status=CaseStatus.WAIT_DOCTOR).order_by("created_at")
```

`doctor_decision` abre o formulário se o caso ainda está em `WAIT_DOCTOR`.
`doctor_submit` salva decisão e executa transições FSM sem verificar propriedade operacional do caso.

### Agendador

`apps/scheduler/views.py::_scheduler_queue_context` lista todos os casos em `WAIT_APPT`.
`apps/scheduler/views.py` usa `@login_required`, mas atualmente precisa ser revisado para exigir papel ativo `scheduler`.

### NIR

`apps/intake/views.py::_my_cases_context` lista casos filtrando `created_by=user`.
`case_detail` e `confirm_receipt` também exigem `created_by=request.user`.

Para continuidade de plantão, todos os usuários NIR precisam ver e abrir todos os casos operacionais (`status != CLEANED`), mesmo quando criados por outro NIR. A conclusão/recebimento continua restrita aos casos em `WAIT_R1_CLEANUP_THUMBS`.

## Decisões de arquitetura

### D1: Persistir lease no `Case`

Adicionar campos ao `Case`:

```python
locked_by = models.ForeignKey(
    settings.AUTH_USER_MODEL,
    null=True,
    blank=True,
    on_delete=models.SET_NULL,
    related_name="cases_locked",
)
locked_at = models.DateTimeField(null=True, blank=True)
locked_until = models.DateTimeField(null=True, blank=True, db_index=True)
lock_token = models.UUIDField(null=True, blank=True)
lock_context = models.CharField(max_length=40, blank=True)
lock_role = models.CharField(max_length=30, blank=True)
```

Justificativa:

- o lock precisa sobreviver a requests HTTP;
- o lock representa trabalho humano, não lock de transação curta;
- PostgreSQL já é a fonte transacional do projeto;
- `lock_token` evita conflito entre múltiplas abas do mesmo usuário;
- `lock_context` diferencia usos como `doctor_decision`, `scheduler_confirm`, `nir_receipt`;
- `lock_role` apoia auditoria em usuários multi-role.

### D2: Não criar novos estados FSM

Não criar estados como `EM_PARECER` ou `EM_AGENDAMENTO`.

A reserva é metadado operacional temporário. O estado de negócio continua sendo:

- `WAIT_DOCTOR`;
- `WAIT_APPT`;
- `WAIT_R1_CLEANUP_THUMBS`.

### D3: Serviço centralizado e transacional

Criar `apps/cases/services.py` com uma API pequena e coesa.

Sugestão de tipos/assinaturas:

```python
@dataclass(frozen=True)
class CaseLockResult:
    acquired: bool
    token: uuid.UUID | None = None
    reason: str = ""
    locked_by_display: str = ""
    locked_until: datetime | None = None


def claim_case_lock(
    *,
    case_id: uuid.UUID,
    user: User,
    expected_status: CaseStatus,
    context: str,
    role: str,
    lease_seconds: int | None = None,
) -> CaseLockResult: ...


def renew_case_lock(
    *,
    case_id: uuid.UUID,
    user: User,
    token: uuid.UUID,
    context: str,
    lease_seconds: int | None = None,
) -> CaseLockResult: ...


def release_case_lock(
    *,
    case_id: uuid.UUID,
    user: User,
    token: uuid.UUID,
    context: str,
) -> bool: ...


def assert_case_lock(
    *,
    case: Case,
    user: User,
    token: uuid.UUID,
    context: str,
) -> None: ...


def expire_stale_locks_for_statuses(*, statuses: Iterable[CaseStatus]) -> int: ...
```

A implementação deve ser simples e DRY, sem criar abstração genérica além do necessário para `Case`.

### D4: Operações atômicas

A aquisição deve ser segura sob concorrência.

Opções aceitáveis:

1. `transaction.atomic()` + `select_for_update()` na linha do caso; ou
2. `QuerySet.update(...)` condicional + checagem de linhas afetadas.

Como a implementação também precisa registrar evento de expiração com dados do usuário anterior, `select_for_update()` tende a ser mais legível.

Regra de aquisição:

```text
pode adquirir se:
- status atual == expected_status;
- e não há locked_by/locked_until ativo;
- ou locked_until <= now;
- ou o lock já pertence ao mesmo user+context e será renovado/continuado conforme regra do serviço.
```

Ao adquirir sobre lock expirado, registrar `WORK_LOCK_EXPIRED` antes de substituir/limpar metadados.

### D5: Auditoria de lock

Usar `CaseEvent` append-only.

Eventos sugeridos:

```text
WORK_LOCK_CLAIMED
WORK_LOCK_RELEASED
WORK_LOCK_EXPIRED
WORK_LOCK_STOLEN_DENIED  # opcional, somente se útil e testado
```

Não registrar cada heartbeat.

Payload mínimo para `WORK_LOCK_EXPIRED`:

```json
{
  "context": "doctor_decision",
  "role": "doctor",
  "expired_locked_by_id": "...",
  "expired_locked_by_display": "Dra. Ana — CRM 12345",
  "expired_locked_at": "2026-05-31T10:00:00Z",
  "expired_locked_until": "2026-05-31T10:05:00Z"
}
```

Não gravar token completo no evento de auditoria. O token é credencial operacional efêmera.

### D6: Configuração de tempo

Adicionar settings com defaults seguros:

```python
CASE_LOCK_LEASE_SECONDS = 5 * 60
CASE_LOCK_HEARTBEAT_SECONDS = 60
CASE_LOCK_ACTIVITY_GRACE_SECONDS = 4 * 60
```

O serviço deve usar `getattr(settings, "CASE_LOCK_LEASE_SECONDS", 300)` para manter compatibilidade.

### D7: Heartbeat com Vanilla JS

Criar `static/js/work_lock.js` ou equivalente, sem dependências externas.

Comportamento:

- registrar atividade humana via `mousemove`, `mousedown`, `keydown`, `scroll`, `touchstart`, `focus`;
- a cada `CASE_LOCK_HEARTBEAT_SECONDS`, renovar apenas se houve atividade nos últimos `CASE_LOCK_ACTIVITY_GRACE_SECONDS`;
- usar `navigator.sendBeacon` ou `fetch(..., {keepalive: true})` em `pagehide` para tentar liberar;
- nunca confiar no release de navegador como garantia; expiração no backend é a garantia real;
- exibir aviso se renew falhar ou lock for perdido.

### D8: Endpoints SSR simples, não REST/DRF

Endpoints podem retornar `JsonResponse`, mas não criar API REST nem DRF.

Exemplo:

```text
POST /doctor/<case_id>/lock/renew/
POST /doctor/<case_id>/lock/release/
POST /scheduler/<case_id>/lock/renew/
POST /scheduler/<case_id>/lock/release/
POST /cases/<case_id>/lock/renew/
POST /cases/<case_id>/lock/release/
```

Todos devem exigir login, papel ativo correto e CSRF.

### D9: Queue rendering

Antes de montar contexto de filas operacionais, chamar expiração lazy dos locks relevantes:

- médico: `WAIT_DOCTOR`;
- agendador: `WAIT_APPT`;
- NIR: `WAIT_R1_CLEANUP_THUMBS`.

Cards devem receber dados derivados:

```python
is_locked
is_locked_by_current_user
locked_by_display
locked_until
lock_context
```

Evitar lógica complexa em templates. Preferir helpers/presenters pequenos na view.

### D10: NIR compartilhado para todos os casos operacionais

Alterar `_my_cases_context` para mostrar todos os casos operacionais:

```text
status != CLEANED
```

Isto substitui a visão individual por criador e permite continuidade de plantão. O queryset deve continuar aceitando os filtros existentes de status e busca.

Alterar acesso ao detalhe operacional:

```text
permitir se:
- usuário tem papel ativo nir
- e case.status != CLEANED
```

Confirmação de recebimento continua aplicável somente a `WAIT_R1_CLEANUP_THUMBS` e deve exigir lock válido no Slice 006.

### D11: Scheduler role guard

Adicionar `@role_required("scheduler")` em todas as views públicas do `apps/scheduler/views.py`:

- `scheduler_queue`;
- `scheduler_queue_partial`;
- `immediate_ack`;
- `scheduler_confirm`;
- `scheduler_submit`.

Manter `@login_required`.

### D12: Clean code / DRY / YAGNI

- Serviço de lock deve ser pequeno, testável e específico para `Case`.
- Não criar framework genérico de filas.
- Não criar classes complexas sem necessidade.
- Não duplicar regra de lock nas views.
- Views devem orquestrar request/response; regra de concorrência fica no serviço.
- Templates recebem flags prontas; não fazem regra de negócio.

## Slices planejados

1. **Scheduler role guard** — corrigir autorização do agendador antes de ampliar fluxo.
2. **Médico: lease básico end-to-end** — campos, serviço inicial, claim ao abrir, submit exige lock, fila mostra reserva.
3. **Médico: heartbeat/idle/release** — JS e endpoints para manter lock enquanto usuário ativo.
4. **Agendador: lease end-to-end** — aplicar serviço/JS ao agendamento e proteger ciência operacional.
5. **NIR: casos operacionais compartilhados** — todos NIR veem e acessam todos os casos operacionais (`status != CLEANED`).
6. **NIR: lease para confirmação de recebimento** — claim/heartbeat/submit protegido no resultado final.
7. **Dashboard: bugfix de timezone em métricas do dia** — corrigir contagens de “hoje” para usar dia local, não data UTC.
8. **Hardening e quality gate final** — cobertura cruzada, contadores, auditoria de expiração e documentação final.

## Riscos e mitigação

| Risco | Mitigação |
|---|---|
| Corrida na aquisição do lock | `transaction.atomic()` + `select_for_update()` ou update condicional testado |
| Usuário abandonar aba aberta | lease curto + heartbeat condicionado à atividade |
| Heartbeat ingênuo prender caso indefinidamente | renovar só com atividade recente e permitir expiração |
| Múltiplas abas do mesmo usuário | `lock_token` por tela/aba |
| Poluição da auditoria | não registrar heartbeat; registrar claim/release/expired |
| Templates com lógica demais | montar flags nas views/presenters |
| Change grande demais | slices verticais, cada um com relatório e parada |
| NIR acessar casos concluídos pela fila operacional | filtrar sempre `status != CLEANED`; casos concluídos permanecem fora da fila operacional e disponíveis apenas em auditoria/dashboard conforme regras existentes |

## Rollback

Rollback funcional:

1. Reverter templates/views/endpoints que usam lock.
2. Manter campos de lock sem uso temporariamente, se necessário.
3. Se rollback completo for exigido, reverter migration removendo campos de lock após confirmar que não há locks ativos relevantes.

Como os campos são metadados opcionais e não alteram FSM, o rollback é controlado.
