# Design: Intake NIR

## Decisões

### D1: App `apps/intake/` separado do `apps/cases/`

`cases/` tem o modelo Case (domínio). `intake/` tem views/forms/templates do fluxo NIR.
Dependência unidirecional: `intake` → `cases` (never the reverse).

### D2: Paleta hospitalar integrada no `app.css`

O demo-reference (`demo-reference/css/styles.css`) define CSS vars com paleta hospitalar.
Vamos mesclar no `static/css/app.css` existente, mantendo compatibilidade com Bootstrap 5.3.
Fontes Google (Merriweather Sans + Source Sans 3) via CDN.

### D3: Upload síncrono com PyMuPDF

No MVP o upload + extração são síncronos. O usuário faz upload, o sistema extrai o texto
na mesma request e já mostra o caso criado.django-q2 será usado na Fase 2 para pipeline LLM.

### D4: Número de registro manual

No primeiro slice o `agency_record_number` é preenchido manualmente pelo NIR no formulário
de upload. Extração automática do PDF fica para refinamento futuro.

### D5: Proteção por role via decorator

Decorator `@role_required("nir")` que verifica `request.session["active_role"]`.
Reutilizável para outros papéis nas próximas fases.

### D6: "Meus Casos" mostra apenas casos do NIR logado

Query: `Case.objects.filter(created_by=request.user).exclude(status="CLEANED")`.

## Slice Plan

1. **Tema hospitalar** — integrar paleta + fontes no app.css + base.html
2. **App intake + decorator role_required** — estrutura do app + decorator reutilizável
3. **Upload de PDF + criação do caso** — view, form, template com drag & drop, FSM transition
4. **Meus Casos** — lista com filtros por status, cards no estilo demo-reference
5. **Detalhe do caso** — dados + PDF inline + timeline de CaseEvents
6. **Quality gate** — testes completos, ruff, mypy
