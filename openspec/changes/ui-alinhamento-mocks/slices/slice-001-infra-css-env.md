# Slice 1: Infra de estáticos + CSS completo + .env loading

## Objetivo

Garantir que CSS e JS são servidos corretamente, completar o CSS com classes que
faltam do mock, e fazer `.env` ser carregado automaticamente.

## Arquivos a modificar

### 1. `config/settings/base.py`

Adicionar no topo (após imports):
```python
from dotenv import load_dotenv
load_dotenv(BASE_DIR / ".env")
```

**Já feito em sessão anterior** — verificar se está commitado. Se não, commitar.

### 2. `static/css/app.css`

Merge do que falta de `demo-reference/css/styles.css`:

- `.decision-section { display: none; }` / `.decision-section.active { display: block; }`
- `.summary-box` / `.summary-label` / `.summary-value`
- `.demo-toast` / `.demo-toast.show`
- `.notif-badge::after` com `data-count`
- `.patient-name` em case cards
- `.waiting-time` / `.waiting-time.urgent`
- `.pulse-dot` animation
- Todos os responsive breakpoints que faltam (login, admin filters, decision two-col, hide-mobile)

NÃO remover regras existentes que são específicas do app (role selection cards, etc.).

### 3. Verificar serving de estáticos

Confirmar que `uv run python manage.py runserver` serve `/static/js/upload.js` (200).
Se não servir, diagnosticar e corrigir.

## Critérios de sucesso

- [ ] `curl localhost:8080/static/js/upload.js` retorna 200
- [ ] `curl localhost:8080/static/css/app.css` retorna 200 e contém `.decision-section`
- [ ] `.env` é carregado: `INTRANET_IP_RANGE` não é string vazia
- [ ] Testes existentes (291) passam sem regressão
- [ ] ruff + mypy clean

## Arquivos: ideal ≤ 3
