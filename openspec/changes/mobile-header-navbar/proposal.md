# Proposal: Header responsivo com `navbar` do Bootstrap (mobile-first)

**Change ID**: `mobile-header-navbar`
**Risco**: MÉDIO (template base + CSS; risco de regressão visual em desktop e mobile, mas sem FSM/models/migrations/runtime operacional)
**Dependências**: nenhuma direta

## Problema

No mobile, o header da aplicação (`templates/base.html`) renderiza "verticalizado e desarrumado": o nome do app, ícones de notificação, manual, avatar, trocar papel e botão sair empilham-se de forma caótica. Raízes técnicas identificadas:

1. **Bug de CSS global**: a regra `.d-flex.gap-2:has(> .btn) { flex-direction: column }` (em `static/css/app.css`, bloco `@media (max-width: 767.98px)`) — criada para empilhar ações de *case cards* — casa acidentalmente com a fileira de ícones+avatar do header, forçando-a a virar coluna.
2. **Estrutura frágil**: o header é um `<header class="app-header">` com `d-flex` e alinhamento pensado apenas para `lg` (`justify-content-lg-end`, `text-lg-end`), sem direção consistente abaixo de `lg`.
3. **Aninhamento excessivo** de `<div>` com regras de alinhamento conflitantes no mobile.
4. **Texto longo do avatar** ("Nome · **papel**") estoura a largura em telas estreitas.

## Objetivo

Adotar o componente `navbar` do Bootstrap 5.3 (`navbar navbar-expand-lg`, breakpoint `lg` = 992px) como base do header, com padrão **híbrido (Opção C)**:

- **Sempre visíveis** (em todos os breakpoints): marca (logo + nome) + ícone de notificação 🔔 + avatar (iniciais).
- **Colapsáveis em hambúrguer** (apenas < `lg`): nome completo + papel ativo, manual do usuário, trocar papel, sair.
- **Desktop (≥ `lg`)**: tudo expandido em linha, **sem regressão visual** em relação ao comportamento atual.

## Escopo

### Dentro
- Refatorar `<header class="app-header">` → `navbar navbar-expand-lg` mantendo o gradiente hospitalar.
- Estruturar dois agrupamentos: `navbar-brand` (marca) + bloco de sessão (ações).
- Introduzir `navbar-toggler` + `navbar-collapse` (somente mobile, com ações secundárias).
- Avatar compacto (iniciais) em < `sm` (576px); nome completo + papel movidos para dentro do menu colapsável.
- Corrigir o seletor global `.d-flex.gap-2:has(> .btn)` escopando-o a `.case-card` (ou classe utilitária explícita).
- Alvos de toque ≥ 44px nos botões do header.
- Reaproveitar ícones existentes em `static/icons/` (`icon-192.png` / `icon.svg`) no `navbar-brand`.
- Testes de renderização do template base (autenticado/não autenticado; presença de elementos esperados).

### Fora
- Mudanças em FSM, models ou migrations.
- Novas dependências (continua Bootstrap 5.3 via CDN).
- Refator de templates filhos (apenas `base.html`).
- Alterar rotas/URLs existentes.
- Alterar lógica de `notifications.js` / badge (apenas marcação/estrutura).

## Decisões

- **D1. `navbar-expand-lg` (≥992px), sem `navbar-collapse` no desktop.** Preserva 100% do comportamento desktop atual (tudo visível em linha). Acima de `lg` não há botão hambúrguer.
- **D2. Padrão híbrido (Opção C).** Notificação e avatar sempre visíveis; nome+papel+manual+trocar papel+sair entram no hambúrguer apenas no mobile. Evita tanto amontoamento quanto perda de identidade.
- **D3. Avatar em iniciais no mobile (< `sm`).** Nome completo e papel vão para dentro do menu colapsável (acessíveis via perfil). Evita estouro de largura.
- **D4. Bug CSS corrigido por escopagem.** Restringir o `:has()` a `.case-card` (ou classe utilitária `.btn-stack-mobile`), eliminando o efeito colateral global.
- **D5. Sem nova dependência.** Apenas Bootstrap 5.3 (já presente) + CSS customizado.
- **D6. Acessibilidade.** `navbar-toggler` com `aria-controls`/`aria-expanded`; ícones com `aria-label`/`title` descritivos.
- **D7. Tocáveis ≥44px.** Mínimo de área de toque para notificação e avatar no mobile (WCAG 2.5.5).

## Critérios de sucesso

- Header renderiza em linha única no desktop (≥992px), idêntico em comportamento ao atual.
- Header no mobile (<992px): marca + notificação + avatar + hambúrguer em uma linha, sem overflow horizontal.
- Ações secundárias (manual, trocar papel, sair, nome+papel) acessíveis via hambúrguer no mobile.
- Avatar mostra apenas iniciais em <576px; nome completo e papel no menu.
- A regra `.d-flex.gap-2:has(> .btn)` não afeta mais o header (escopada).
- Alvos de toque (notificação, avatar) ≥ 44×44px no mobile.
- Sem regressão visual em desktop.
- Sem alteração de FSM/models/migrations.
- Quality gate (ruff, ruff format, mypy, pytest) passa.
- Teste de renderização do template base cobre estados autenticado/não autenticado.
