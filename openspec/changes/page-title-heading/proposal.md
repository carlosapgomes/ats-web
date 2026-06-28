# Proposal: Separar identidade do app do título de página (`<h1>`)

**Change ID**: `page-title-heading`
**Risco**: BAIXO–MÉDIO (apresentação/semântica; sem FSM/models/migrations/runtime operacional; risco de regressão visual pontual por template)
**Dependências**: `mobile-header-navbar` (já mergeado)

## Problema

Hoje o `app-header__subtitle` (em `templates/base.html`) mistura duas responsabilidades:

1. **Identidade do app** (default: `"Sistema de Regulação Hospitalar CHD"`) — deveria ser constante.
2. **Contexto da página** (override por `{% block subtitle %}` em 23 templates, com textos variáveis e às vezes longos, ex.: `"Upload de encaminhamentos e acompanhamento de casos"`, `"Caso {nº} · {paciente}"`).

Como o `subtitle` fica dentro do `navbar-brand` (lado a lado com sino/avatar/toggler, sob `align-items: center`), textos longos **variam a altura do header de página para página** e empurram os ícones da direita para baixo — inconsistência visual no mobile.

Agravante: a maioria das páginas **não tem `<h1>` no conteúdo**. Logo, o `subtitle` é, na prática, o único identificador de "onde estou" — e desde o Slice 002 do change anterior ele é um `<span>`, não semântico. Várias páginas estão sem `<h1>` no outline do documento (regressão de acessibilidade/SEO).

## Objetivo

**Separar responsabilidades (Opção A da discussão):**

- `navbar-brand` fica **só com identidade constante** (logo + nome + tagline curta). Altura do header passa a ser **constante em todas as páginas**.
- O texto por-página vira um **`<h1 class="page-title">`** no topo de `<main>`, com largura total e destaque adequado.

## Escopo

### Dentro
- `templates/base.html`: `{% block subtitle %}` removido do header; novo bloco `{% block page_title %}` renderizado como `<h1 class="page-title">` no topo de `<main>`; tagline constante no header.
- `static/css/app.css`: nova classe `.page-title`; estabilizar altura do header.
- 23 templates: converter `{% block subtitle %}...{% endblock %}` → `{% block page_title %}...{% endblock %}` (texto idêntico, só muda o bloco).
- Testes: renderização do `base.html` (header sem subtitle variável; `<h1 class="page-title">` presente); caracterização por módulo.

### Fora
- Mudanças em FSM/models/migrations.
- Reescrever os textos do subtitle (mantêm-se).
- Redesenhar o header (já estabilizado pelo change `mobile-header-navbar`).
- Templates que não fazem override de subtitle (herdam tagline; alguns sem `<h1>` ficam fora deste change — deferido).

## Decisões

- **D1. Tagline constante no header.** O `navbar-brand` passa a exibir apenas `app_display_name` + uma tagline curta fixa (ex.: `"Sistema de Regulação Hospitalar CHD"`, o atual default). Sem `{% block subtitle %}`.
- **D2. `<h1 class="page-title">` no `<main>`.** Novo bloco `{% block page_title %}...{% endblock %}` renderizado no topo do `<main>`, **antes** de `{% block content %}`. Em desktop e mobile ocupa largura total.
- **D3. Migração mecânica dos textos.** Cada `{% block subtitle %}X{% endblock %}` vira `{% block page_title %}X{% endblock %}` — mesmo texto, sem reescrita.
- **D4. Sem `<h1>` quando não houver título.** Templates que não definem `page_title` não renderizam `<h1>` (mantém comportamento atual para esses casos). Páginas sem título continuam sem `<h1>` — fora de escopo.
- **D5. `<h1>` único por página.** Onde um template já tiver `<h1>`/`<h2>` no conteúdo que conflite com o novo `page-title`, consolidar (ex.: `notifications.html` já tem `<h2>`; avaliar caso a caso nos slices).
- **D6. Acessibilidade.** `<h1 class="page-title">` restabelece outline do documento (WCAG 1.3.1, 2.4.6).

## Critérios de sucesso

- Header tem altura **constante** em todas as páginas (não varia com o título).
- Ícones de notificação/avatar/toggler não são mais empurrados por texto longo.
- Cada uma das 23 páginas com override tem `<h1 class="page-title">` no `<main>`.
- `navbar-brand` exibe só nome + tagline fixa.
- Sem alteração de FSM/models/migrations.
- Quality gate (ruff, ruff format, mypy, pytest) passa.
- Sem `<h1>` duplicado por página.
