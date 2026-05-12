# Slice 2: Badges de contagem + responsividade

## Objetivo

Adicionar badges de contagem nas filas (doctor/scheduler) e ajustes de responsividade mobile.

## Arquivos

### 1. `apps/accounts/context_processors.py` — modificado

Adicionar `queue_counts` context processor:

```python
def queue_counts(request):
    if not request.user.is_authenticated:
        return {}
    active_role = request.session.get("active_role")
    if active_role == "doctor":
        count = Case.objects.filter(status=CaseStatus.WAIT_DOCTOR).count()
        return {"queue_count": count}
    if active_role == "scheduler":
        count = Case.objects.filter(status=CaseStatus.WAIT_APPT).count()
        return {"queue_count": count}
    return {}
```

### 2. `config/settings/base.py` — modificado

Adicionar `queue_counts` aos `context_processors` do template backend.

### 3. `templates/base.html` — modificado

Exibir badge no header quando `queue_count` > 0:
```html
{% if queue_count %}
<span class="badge bg-danger ms-1">{{ queue_count }}</span>
{% endif %}
```

### 4. `static/css/app.css` — modificado

Ajustes de responsividade:
- Botões touch-friendly: `min-height: 44px` para `.btn`
- Verificar tabelas em telas < 576px
- Ajustar fontes e espaçamentos mobile

### 5. Testes

- Context processor: ~4 (doctor count, scheduler count, other roles zero, unauthenticated)
- Template badge: ~2

## Critérios de sucesso

- [ ] Badge de contagem visível no header para doctor/scheduler
- [ ] Contagem reflete casos pendentes reais
- [ ] Botões touch-friendly (≥ 44px)
- [ ] Layout funciona em 320px-576px sem quebra
- [ ] ~6 testes passando
- [ ] ruff + mypy + pytest clean

## Arquivos: ideal ≤ 5
