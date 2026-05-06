# Slice 1: App doctor + queue view + templates

## Objetivo

Criar o app `apps/doctor/` com a view de fila médica e template alinhado ao mock.

## Arquivos a criar

### 1. `apps/doctor/` (app scaffold)
- `__init__.py`
- `apps.py` (`DoctorConfig`)
- `urls.py` — namespace `doctor`
- `views.py` — `doctor_queue` view

### 2. `config/urls.py`
Adicionar `path("doctor/", include("apps.doctor.urls"))`

### 3. `config/settings/base.py`
Adicionar `"apps.doctor"` em `INSTALLED_APPS`

### 4. `templates/doctor/queue.html`
Alinhar com `demo-reference/doctor/queue.html`:
- Header "Avaliação Médica" com nav pills (Pendentes / Decididos Hoje)
- Alert com contagem + tempo médio de espera
- Cards com `.patient-name`, `.summary-box`, `.waiting-time`, `.waiting-time.urgent`
- Seção "Decididos Hoje" com cards de casos já decididos
- JS inline para behavior (se necessário)

### 5. `apps/accounts/views.py`
Atualizar `home_view`: `doctor` → `redirect("doctor:queue")` em vez de `intake:home`

## Query da fila

```python
# Pendentes
Case.objects.filter(status=CaseStatus.WAIT_DOCTOR).order_by("created_at")

# Decididos hoje (pelo médico logado)
Case.objects.filter(
    status__in=[CaseStatus.DOCTOR_ACCEPTED, CaseStatus.DOCTOR_DENIED, ...],
    events__event_type__startswith="DOCTOR_",
    events__timestamp__date=today,
).distinct()
```

## Critérios de sucesso

- [ ] App doctor registrado e acessível
- [ ] `/doctor/` retorna 200 para usuário com role `doctor`
- [ ] `/doctor/` redireciona para login se não autenticado
- [ ] Queue template alinhado visualmente com mock
- [ ] Cards mostram dados do paciente + sugestão IA + tempo de espera
- [ ] `home_view` redireciona doctor para `/doctor/`
- [ ] Testes: queue view (3-5), redirect home_view (1-2)
- [ ] ruff + mypy + pytest clean

## Arquivos: ideal ≤ 8
