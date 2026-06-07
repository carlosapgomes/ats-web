# Relatório Slice 001 — Encerramento Administrativo Auditável

**Data**: 2026-06-07
**Status**: ✅ Completo
**Testes**: 95 novos (35 service/FSM + 8 dashboard + 52 parametrização)
**Total**: 1141 passando (+95)

## Arquivos tocados (8)

| Arquivo | Tipo | Descrição |
|---------|------|-----------|
| `apps/cases/models.py` | Modificado | Transição FSM `administratively_close` |
| `apps/cases/services.py` | Modificado | Serviço `administratively_close_case` + constantes |
| `apps/cases/tests/test_administrative_closure.py` | **Novo** | 35 testes de FSM, serviço e filas |
| `apps/dashboard/views.py` | Modificado | View POST + contexto no detalhe |
| `apps/dashboard/urls.py` | Modificado | Rota `administrative_close` |
| `apps/dashboard/tests/test_dashboard.py` | Modificado | 8 testes de UI/permissão |
| `templates/intake/case_detail.html` | Modificado | Formulário de encerramento |
| `apps/intake/views.py` | Modificado | Label/dot para novo evento |

## Snippets antes/depois

### 1. FSM Transition (`apps/cases/models.py`)

**Antes**: Não existia transição de encerramento administrativo.

**Depois**:
```python
@transition(
    field=status,
    source=[
        CaseStatus.NEW, CaseStatus.R1_ACK_PROCESSING, CaseStatus.EXTRACTING,
        CaseStatus.LLM_STRUCT, CaseStatus.LLM_SUGGEST, CaseStatus.R2_POST_WIDGET,
        CaseStatus.WAIT_DOCTOR, CaseStatus.DOCTOR_ACCEPTED, CaseStatus.DOCTOR_DENIED,
        CaseStatus.R3_POST_REQUEST, CaseStatus.WAIT_APPT, CaseStatus.APPT_CONFIRMED,
        CaseStatus.APPT_DENIED, CaseStatus.FAILED, CaseStatus.R1_FINAL_REPLY_POSTED,
        CaseStatus.WAIT_R1_CLEANUP_THUMBS, CaseStatus.CLEANUP_RUNNING,
    ],
    target=CaseStatus.CLEANED,
)
def administratively_close(self, *, user=None, payload=None):
    self._record_event("CASE_ADMINISTRATIVELY_CLOSED", user=user, payload=payload or {})
```

### 2. Serviço transacional (`apps/cases/services.py`)

**Antes**: Não existia.

**Depois**: Função `administratively_close_case()` com:
- Validação de `reason_text`, `reason_code` e código válido
- `select_for_update()` + `transaction.atomic()`
- Snapshot de lock e intercorrência no payload
- Limpeza de lock e campos de intercorrência
- FSM transition via model method

### 3. Rota POST (`apps/dashboard/urls.py`)

**Antes**: 4 rotas existentes (index, summaries, case_detail, case_pdf).

**Depois**:
```python
path("<uuid:case_id>/administrative-close/", views.dashboard_administrative_close, name="administrative_close")
```

### 4. View POST (`apps/dashboard/views.py`)

**Antes**: Não existia.

**Depois**: `dashboard_administrative_close()` com decorators `@login_required`, `@role_required("manager", "admin")`, `@require_POST`. Lê `reason_code`/`reason_text` do POST, chama serviço, usa `messages.success/error`, redireciona para detail.

### 5. Contexto no detalhe (`apps/dashboard/views.py`)

**Antes**: Template recebia `can_confirm_receipt`, `back_url`, etc.

**Depois**: Adicionado:
```python
"can_administratively_close": case.status != CaseStatus.CLEANED,
"administrative_close_url": reverse("dashboard:administrative_close", args=[case.case_id]),
"administrative_close_reason_choices": ADMINISTRATIVE_CLOSURE_REASON_CHOICES,
```

### 6. Template (`templates/intake/case_detail.html`)

**Antes**: Card de Ações com botões de voltar e confirmar recebimento.

**Depois**: Seção condicional dentro do card de Ações:
```html
{% if can_administratively_close and administrative_close_url %}
<hr>
<h6 class="text-danger">🚨 Encerramento Administrativo</h6>
<p class="text-muted small">
  Remove o caso das filas operacionais. O caso permanece na auditoria...
</p>
<form method="post" action="{{ administrative_close_url }}"
      onsubmit="return confirm('...');">
  {% csrf_token %}
  <select name="reason_code" required>...opções...</select>
  <input type="text" name="reason_text" required maxlength="500">
  <button type="submit" class="btn btn-outline-danger btn-sm">
    🔒 Encerrar administrativamente
  </button>
</form>
{% endif %}
```

### 7. Labels de auditoria (`apps/intake/views.py`)

**Antes**: Sem entrada para `CASE_ADMINISTRATIVELY_CLOSED`.

**Depois**:
```python
EVENT_LABELS["CASE_ADMINISTRATIVELY_CLOSED"] = "Encerrado administrativamente"
EVENT_DOT_CSS["CASE_ADMINISTRATIVELY_CLOSED"] = "system"
```

## Gates de autoavaliação

1. **O código criou novo estado FSM ou nova tabela?** ❌ Não. Usa `CaseStatus.CLEANED` existente.
2. **A mudança de status passa por método FSM?** ✅ `Case.administratively_close()` via decorator `@transition`.
3. **O evento criado é `CASE_ADMINISTRATIVELY_CLOSED`?** ✅ Teste `test_administrative_close_does_not_create_cleanup_events` prova que `CLEANUP_TRIGGERED`/`CLEANUP_COMPLETED` NÃO são criados.
4. **POST sem motivo mantém status anterior?** ✅ Teste `test_dashboard_administrative_close_post_requires_reason` prova.
5. **Usuário sem manager/admin consegue acionar?** ❌ Teste `test_dashboard_administrative_close_post_requires_manager_or_admin` prova.
6. **Lock é limpo?** ✅ Teste `test_service_clears_lock_fields` prova todos os 6 campos limpos.
7. **Caso some das filas operacionais?** ✅ Testes `test_administratively_closed_case_leaves_nir_list`, `test_administratively_closed_case_removed_from_wait_doctor`, `test_administratively_closed_case_removed_from_wait_appt` provam.
8. **Relatório contém snippets antes/depois?** ✅ Sim, acima.

## Critérios de sucesso

- [x] TDD seguido: testes novos falham antes da implementação e passam após.
- [x] Não há novo estado FSM nem migração de campo.
- [x] Encerramento usa transição FSM, não update direto do campo protegido.
- [x] `CASE_ADMINISTRATIVELY_CLOSED` diferencia claramente de cleanup normal.
- [x] Motivo obrigatório é validado no serviço e na rota POST.
- [x] Apenas `manager`/`admin` com papel ativo conseguem encerrar.
- [x] Caso encerrado fica `CLEANED` e sai das filas operacionais.
- [x] Lock é limpo e auditado no payload.
- [x] Timeline tem label legível ("Encerrado administrativamente").
- [x] Quality gate do AGENTS.md passa (ruff, mypy, pytest).

## REPORT_PATH

```
openspec/changes/administrative-case-closure-and-attention-filter/reports/slice-001-report.md
```
