# Slice 001 — Domínio: follow-up versionado + auditoria

## Objetivo

Comportamento observável: um serviço de domínio registra o desfecho de um caso (internação + desfecho por procedimento) como **versão append-only** com espelho em `CaseEvent`, rejeitando gravações inválidas. Sem UI — observável via ORM/`CaseEvent` e testes.

Slice **preparatório justificado**: models + service são a base obrigatória das duas slices de UI; sem eles não há comportamento end-to-end possível. É o único slice horizontal do change.

## Contexto necessário (ler antes de editar)

- `apps/cases/models.py` — `Case` (linhas ~140-210: `agency_record_number`, `appointment_*`, `post_schedule_issue_*`), `ProcedureType`, `CaseProcedure` (~L77-102), `CaseEvent` (~L700-720). FK de usuário: `settings.AUTH_USER_MODEL` com `on_delete=models.SET_NULL, null=True` (ex.: `Case.scheduler`, ~L168).
- `apps/cases/admission.py` — apenas para conferir que NÃO se toca nele.
- `apps/cases/services.py::_record_event` (~L61) — padrão de criação direta de `CaseEvent` (não reaproveitar o helper: ele é privado de services; crie `CaseEvent.objects.create` no novo módulo, mesmo padrão).
- `tests/shared_case_fixtures.py` — fixtures de usuário/caso (`case` etc.) e `attach_procedure_projection` para criar rows `CaseProcedure` quando útil (ou `CaseProcedure.objects.create` direto).
- `openspec/changes/supervisor-appointment-follow-up/design.md` — seções D1, D2, D3 (contratos de dados e payload).

## Requisitos verificáveis

- **R1** — `record_case_follow_up(case=..., performed_by=user, patient_admitted=bool, procedure_outcomes=[ProcedureOutcomeInput(...)])` cria `CaseFollowUp` versão 1 + uma `ProcedureFollowUp` por procedimento do caso + `CaseEvent` `FOLLOWUP_RECORDED` com payload snapshot (`version`, `patient_admitted`, `outcomes[...]`).
- **R2** — Segunda gravação no mesmo caso cria versão 2 (rows anteriores intactas) + `CaseEvent` `FOLLOWUP_UPDATED`; `get_current_follow_up(case)` retorna a versão 2; caso sem follow-up → `None`.
- **R3** — Validações rejeitam com `ValueError` (mensagem PT-BR) e não gravam nada: procedimento do caso ausente da lista; id de procedimento estranho; `performed=False` sem `non_performance_reason`; `non_performance_reason="resource_shortage"` sem `resource_shortage_detail`; `"other"` sem `other_reason`. Com `performed=True`, reason/detail/other são normalizados para vazio.
- **R4** — Integridade no banco: `UNIQUE (case, version)`, `UNIQUE (follow_up, procedure)` e `CheckConstraint`s condicionais (motivo obrigatório quando não realizado; submotivo só com `resource_shortage`; texto só com `other`; campos vazios quando `performed=True`).

## Matriz requisito → arquivo → teste/check

| Requisito | Arquivo(s) esperado(s) | Teste/check |
| --- | --- | --- |
| R1 | `apps/cases/models.py`, `apps/cases/followup.py`, `apps/cases/migrations/00XX_followup_models.py` | `pytest apps/cases/tests/test_followup_services.py::test_record_creates_first_version_with_event` |
| R2 | idem | `pytest apps/cases/tests/test_followup_services.py -k "update or current"` |
| R3 | `apps/cases/followup.py` | `pytest apps/cases/tests/test_followup_services.py -k validation` |
| R4 | `apps/cases/models.py` + migration | `pytest apps/cases/tests/test_followup_services.py::test_unique_constraints` (integrity error esperado) |

## Escopo e expected blast radius

```yaml
expected_files:
  - apps/cases/models.py                  # +2 models, +2 TextChoices
  - apps/cases/followup.py                # novo: service + dataclass + get_current_follow_up
  - apps/cases/migrations/00XX_followup_models.py  # makemigrations
  - apps/cases/tests/test_followup_services.py     # novo

allowed_incidental_files: []

out_of_scope:
  - qualquer view/template/url (slices 002/003)
  - FSM, signals, OPERATIONAL_NOTICE/SUPPORTED_SYSTEM_NOTICE event types
  - dashboard, métricas, notificações
  - alteração em models existentes (nem um campo novo em Case)
```

**Escalar em vez de ampliar** se: precisar tocar `Case`, `signals.py`, listas de event types operacionais, ou criar mensagem de sistema para follow-up.

## Plano de testes do slice

### RED

```bash
uv run pytest apps/cases/tests/test_followup_services.py -q
```

Falha esperada: `ImportError`/collection error — `CaseFollowUp` não existe em `apps.cases.models`. Escreva ANTES os testes de R1–R4 (veja matriz).

### GREEN

```bash
uv run pytest apps/cases/tests/test_followup_services.py -q
```

Resultado esperado: exit 0.

### Verificação do slice

```bash
uv run pytest apps/cases/tests -q                 # regressão do app domínio
uv run ruff check apps/cases/followup.py apps/cases/models.py apps/cases/tests/test_followup_services.py
uv run ruff format --check apps/cases/followup.py apps/cases/models.py apps/cases/tests/test_followup_services.py
uv run mypy apps/cases
```

NÃO rodar a suíte completa neste slice (gate final do change roda).

## Contratos de assinatura (para contexto zero)

```python
# apps/cases/followup.py
@dataclass(frozen=True)
class ProcedureOutcomeInput:
    procedure_id: int
    performed: bool
    non_performance_reason: str = ""      # FollowUpNonPerformanceReason value ou ""
    resource_shortage_detail: str = ""    # FollowUpResourceShortageDetail value ou ""
    other_reason: str = ""

def record_case_follow_up(*, case: Case, performed_by: Any, patient_admitted: bool,
                          procedure_outcomes: Sequence[ProcedureOutcomeInput]) -> CaseFollowUp: ...

def get_current_follow_up(case: Case) -> CaseFollowUp | None: ...
```

- Choices em `apps/cases/models.py`: `FollowUpNonPerformanceReason` (`absenteeism`, `resource_shortage`, `other`) e `FollowUpResourceShortageDetail` (`emergency_occupied`, `insufficient_time`, `equipment_unavailable`), labels PT-BR conforme design D2.
- `CaseFollowUp.recorded_by`: `settings.AUTH_USER_MODEL`, `SET_NULL`, `null=True`, `related_name="follow_ups_recorded"`.
- Evento: `CaseEvent.objects.create(case=case, actor=performed_by, actor_type="human", event_type="FOLLOWUP_RECORDED"|"FOLLOWUP_UPDATED", payload={...})` dentro do mesmo `transaction.atomic()` das rows.

## Critérios de aceitação

- [x] R1: versão 1 + outcomes + evento com snapshot corretos.
- [x] R2: versão 2 criada, v1 imutável, `get_current_follow_up` correto, evento `FOLLOWUP_UPDATED`.
- [x] R3: validações falham com `ValueError` e não persistem rows (expandidas no ciclo de review: valores de choices e combinações incompatíveis).
- [x] R4: constraints ativas na migration (unique ×2 + checks condicionais) — cobertura completa dos 6 checks após review.
- [x] Verificações locais do slice passam; nenhum arquivo fora do blast radius.

## Registro de execução

- Implementado em commit `0d004b6` (base `f95b38f`). RED: coleção falhou por `ImportError` (motivo esperado). 12 testes → **21 testes** após correções do review (ver `design.md` § Registro de review): service valida submotivo fora das choices e combinações incompatíveis; TestConstraints reescrito (um teste não era coletado por falta do prefixo `test_`; colisão de UNIQUE eliminada usando rows diretas). Checks: pytest focado, regressão `apps/cases`, ruff, mypy — verdes.
