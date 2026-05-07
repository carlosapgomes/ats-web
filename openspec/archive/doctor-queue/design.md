# Design: Fila Médica (Doctor Queue)

## Decisões

### D1: Novo app `apps/doctor/`

App dedicado para views do médico, separado do intake. Segue o mesmo padrão
de `apps/intake/` com `@role_required("doctor")`.

### D2: URL namespace `doctor:`

```
/doctor/              → doctor:queue        (lista de casos WAIT_DOCTOR)
/doctor/<uuid:id>/    → doctor:decision     (tela de decisão)
/doctor/<uuid:id>/submit/ → doctor:submit   (POST da decisão)
```

### D3: Queue view — query e contexto

Busca casos em `WAIT_DOCTOR`, ordenados por `created_at`. Para cada caso,
extrai do `structured_data` e `suggested_action`:
- Patient name/age (via `structured_data.patient`)
- Summary one-liner
- Suporte sugerido (`suggested_action.support_recommendation`)
- Fluxo sugerido (`suggested_action.suggestion`)
- Tempo de espera (desde `created_at`)
- Prioridade (se `support_recommendation == "anesthesist_icu"`)

### D4: Decision view — duas colunas

Esquerda (contexto):
- Dados do paciente (tabela)
- Extração IA (summary boxes: diagnóstico, comorbidades, exames, sugestão)
- PDF inline (mesmo padrão do case_detail do NIR)

Direita (formulário):
- Form Django com campos: `decision` (ChoiceField), `support_flag`, `admission_flow`, `reason`
- Validação condicional: support_flag + admission_flow obrigatórios se accept; reason obrigatório se deny
- JS do mock para toggle de seções e modal de confirmação

### D5: Submit — FSM transition + persist

```python
case.doctor_decision = form.cleaned_data["decision"]
case.doctor_support_flag = form.cleaned_data["support_flag"]
case.doctor_admission_flow = form.cleaned_data["admission_flow"]
case.doctor_reason = form.cleaned_data["reason"]
case.doctor_decide(decision=case.doctor_decision, user=request.user)
case.save()

if case.doctor_decision == "accept":
    case.ready_for_scheduler(user=request.user)
    case.save()
```

### D6: Decididos Hoje — query separada

Cases decididos pelo médico atual no dia (`doctor_decided_at` ou timestamp do
CaseEvent `DOCTOR_ACCEPT`/`DOCTOR_DENIED`). Exibe nome, registro, decisão, timestamp.

### D7: home_view redirect para doctor

Atualizar `apps/accounts/views.py` para redirecionar `doctor` → `doctor:queue`
(em vez do fallback temporário para `intake:home`).

## Arquivos previstos

| Arquivo | Tipo |
|---------|------|
| `apps/doctor/__init__.py` | novo |
| `apps/doctor/apps.py` | novo |
| `apps/doctor/views.py` | novo |
| `apps/doctor/forms.py` | novo |
| `apps/doctor/urls.py` | novo |
| `apps/doctor/decorators.py` | novo (re-export de intake ou criar próprio) |
| `templates/doctor/queue.html` | novo |
| `templates/doctor/decision.html` | novo |
| `config/urls.py` | modificado (incluir doctor urls) |
| `config/settings/base.py` | modificado (INSTALLED_APPS) |
| `apps/accounts/views.py` | modificado (home_view redirect) |
| `static/js/decision.js` | novo (toggle + modal) |

## Orçamento de testes

- Testes de view (queue + decision + submit): ~15
- Testes de form (validação condicional): ~8
- Testes de FSM (doctor_decide, ready_for_scheduler): ~5
- Testes de redirect home_view: ~2 (ajustar existente)
- Total estimado: ~30 novos testes
