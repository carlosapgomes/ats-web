# Slice 002b: Remediação — subnav no navbar e ordem do toggler

## Objetivo

O Slice 002 introduziu o `navbar`, mas dois defeitos de layout (invisíveis aos testes de string) restam:

1. **`{% block nav %}` virou item flex errado.** O `<header>` agora é `navbar`, e o Bootstrap 5.3 força `.navbar > .container { display: flex; justify-content: space-between; }`. Logo, a subnav injetada por 22 templates via `{% block nav %}` passou a ser um 4º item flex na mesma linha do header (empurrada para a extrema direita ao lado de sino/avatar), em vez de ocupar uma linha própria abaixo. Regressão de layout em todas as páginas com subnav.

2. **Ordem do DOM faz sino/avatar/toggler caírem abaixo do menu expandido no mobile.** A ordem atual é `brand → collapse → bloco-sempre-visível`. Ao expandir o hambúrguer no mobile, o `collapse` vira `flex-basis: 100%` e, por vir antes do bloco sempre-visível, o sino, o avatar e o próprio botão ✕ (fechar) caem para baixo do menu — contrário à Opção C.

## Arquivos (3)

- `templates/base.html` — reorderar DOM (toggler antes do collapse) + `order-lg-*` para reposicionar no desktop.
- `static/css/app.css` — `.app-header .app-nav { flex-basis: 100%; }` para a subnav ocupar linha própria.
- `tests/test_base_header_navbar.py` — +3 testes (DOM order, `order-lg`, CSS da subnav).

## Decisões

- **D1. Padrão Bootstrap canônico.** `brand → bloco-sempre-visível(bell, avatar, toggler) → collapse`. No mobile colapsado, brand + controles persistentes em uma linha; ao expandir, o menu abre abaixo (flex-basis 100%), mantendo toggler/sino/avatar no topo.
- **D2. `order-lg-2`/`order-lg-3`** para, no desktop, o collapse (order 2, com `flex-grow` preenchendo o espaço) ficar à esquerda do bloco sempre-visível (order 3, extremo direito). Conteúdo do collapse usa `ms-auto` para alinhar à direita dentro de seu container.
- **D3. Subnav full-width.** `.app-header .app-nav { flex-basis: 100%; }` força a quebra de linha, devolvendo o comportamento de "linha própria abaixo do header" que existia antes do `navbar`.

## TDD

### RED

- `test_toggler_precedes_collapse_in_dom` — índice de `class="navbar-toggler"` deve ser menor que o de `class="collapse navbar-collapse"`.
- `test_order_lg_utilities_present` — HTML contém `order-lg-2` e `order-lg-3`.
- `test_app_nav_full_width_css` — `app.css` contém regra `.app-header .app-nav` com `flex-basis: 100%`.

### GREEN

Reorderar DOM em `base.html` + adicionar `order-lg-*` + adicionar regra CSS.

### REFACTOR

Nenhum — ajuste pontual e consistente.

## Critérios de sucesso

- [ ] Testes novos passam.
- [ ] `uv run pytest` verde.
- [ ] Subnav volta a ocupar linha própria abaixo do header (verificação visual registrada).
- [ ] No mobile expandido, toggler/sino/avatar permanecem no topo.
- [ ] Quality gate completo.

## Gates de autoavaliação

- [ ] Confirmei (lógica DOM + CSS) a ordem visual nos 3 tamanhos.
- [ ] Commit rastreável (`fix(header): subnav full-width and canonical toggler DOM order`).
