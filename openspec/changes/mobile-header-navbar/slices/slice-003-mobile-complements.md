# Slice 003: Ajustes complementares mobile

## Objetivo

Polish sobre o Slice 002 para garantir UX mobile de qualidade:

1. **Avatar em iniciais** em telas < `sm` (576px), sem texto (nome completo + papel já estão no menu colapsável).
2. **Área de toque ≥ 44×44px** nos botões de notificação e avatar no mobile (WCAG 2.5.5).
3. **`flex-wrap`** defensivo para telas muito estreitas (<360px) sem overflow horizontal.

Depende do Slice 002 estar concluído.

## Arquivos

- `templates/base.html` (apenas markup do avatar, se necessário).
- `static/css/app.css` (regras `.avatar-circle`, `.avatar-meta`, toque 44px).
- `tests/test_base_header_navbar.py` (extensão com assertions de avatar/toque — onde aplicável).

## Handoff / prompt para implementador (contexto zero)

> No header refatorado (Slice 002), o avatar atualmente é um link `<a class="avatar-circle">JS</a>`.
>
> 1. Em `templates/base.html`, envolva o texto completo (nome · papel) em `<span class="avatar-meta d-none d-sm-inline">...</span>` se ele ainda aparecer ao lado do avatar. (O Slice 002 já moveu nome+papel para o menu colapsável; aqui garantimos que, se houver texto residual ao lado do círculo, ele só apareça em ≥ `sm`.)
>
> 2. Em `static/css/app.css`, adicione:
>
> ```css
> /* Avatar circle */
> .navbar .avatar-circle {
>   width: 2rem;
>   height: 2rem;
>   border-radius: 999px;
>   background: #fff;
>   color: var(--hospital-primary);
>   display: inline-flex;
>   align-items: center;
>   justify-content: center;
>   font-weight: 700;
>   font-size: 0.8rem;
>   text-decoration: none;
> }
>
> @media (max-width: 991.98px) {
>   /* Touch targets >= 44px (WCAG 2.5.5) */
>   .navbar .notification-icon-btn,
>   .navbar .avatar-circle,
>   .navbar .navbar-toggler {
>     min-width: 44px;
>     min-height: 44px;
>     display: inline-flex;
>     align-items: center;
>     justify-content: center;
>   }
> }
>
> @media (max-width: 359.98px) {
>   /* Defensive wrap for very narrow screens */
>   .navbar .d-flex.gap-2 {
>     flex-wrap: wrap;
>   }
> }
> ```
>
> 3. Estenda `tests/test_base_header_navbar.py` com:
>    - `test_avatar_circle_class_present`: o HTML contém `avatar-circle`.
>    - `test_touch_target_css_present`: `app.css` contém `min-width: 44px` e `min-height: 44px` dentro do bloco mobile.

## TDD

### RED

Adicionar os 2 testes acima; devem falhar.

### GREEN

Implementar CSS + ajuste de template.

### REFACTOR

Consolidar regras de toque com as já existentes para `.app-nav .nav-link` (que já usa `min-height: 44px`).

## Critérios de sucesso

- [ ] Avatar mostra apenas iniciais (círculo) em <576px; sem overflow.
- [ ] Botões de notificação, avatar e hambúrguer têm área de toque ≥44×44px no mobile.
- [ ] Em 360px, nenhum overflow horizontal no header.
- [ ] Testes novos passam; `uv run pytest` verde.
- [ ] Quality gate: `uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest`.

## Gates de autoavaliação

- [ ] Verifiquei visualmente em 360px e 320px (sem overflow).
- [ ] Inspecionei no DevTools que `min-width/min-height: 44px` está aplicado aos botões.
- [ ] Commit com mensagem rastreável (`style(header): mobile avatar initials and 44px touch targets`).
