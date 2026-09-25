# Design: Affordances visuais da seleção de procedimentos

Mudança de apresentação pura sobre o componente D9 (combobox pesquisável).
Nenhuma decisão aqui altera contrato POST, catálogo, policy ou FSM.

## D1. Contrato intacto — apenas aditivo

O `<select>` canônico permanece o único valor submetido. Tudo o que este
change adiciona ao HTML são atributos/elementos decorativos ou de associação:
`data-combobox-placeholder` no select, elemento `<p>` de hint, ampliação do
`aria-describedby`. O JS apenas lê o novo data-attribute e marca a row
selecionada. Zero mudança em `name`, `id`, `required`, options ou POST.

## D2. Placeholder é decoração; hint é o portador durável

- O JS propaga `data-combobox-placeholder` do select para o `placeholder` do
  input aprimorado. Sem o data-attribute, nenhum placeholder é adicionado
  (compatibilidade com usos futuros do componente).
- Placeholder some ao digitar e não atende contraste como texto informativo —
  por isso a orientação funcional vive no hint persistente (D3), e o fallback
  SSR continua usando a primeira option instrucional do `<select>`
  ("Selecione o tipo de exame…" já existe nas quatro superfícies).
- Copy por jornada: upload "Digite para buscar — ex.: EDA, cápsula,
  dilatação…"; correção "Buscar novo conjunto de procedimentos…"; reenvio
  "Buscar tipo de exame do novo envio…"; destino médico "Buscar procedimento
  de destino…".

## D3. Hint persistente associado por `aria-describedby`

- Elemento `<p class="form-text procedure-combobox__hint" id="…-search-hint">`
  imediatamente abaixo do controle, em cada superfície.
- O `aria-describedby` do select passa a referenciar o hint (somando ao que
  já existe: guidance do upload; error condicional quando presente). O JS já
  propaga `describedby` ao input aprimorado (`procedure_combobox.js`,
  `enhance()`), então a associação é herdada sem novo código.
- Copy uniforme nas quatro superfícies: "Busca ignora acentos e aceita
  sinônimos aprovados. Navegue com ↑ ↓ e confirme com Enter."
- O hint é HTML estático do template — sobrevive a re-render com erro por
  construção.

## D4. Chevron CSS-only, ligado à expansão

- `::after` no wrapper `.procedure-combobox--enhanced` (que já é
  `position: relative`), com `pointer-events: none` e margem à direita no
  input para não sobrepor texto.
- Rotação do chevron via
  `.procedure-combobox--enhanced:has(.procedure-combobox__input[aria-expanded="true"])::after`.
  `:has()` é suportado nos navegadores do hospital (Chrome 105+, Firefox
  121+, Safari 15.4+); se ausente, o chevron fica estático — degradação
  aceitável porque é decorativo. Nenhuma mudança de JS para o chevron.
- Indicador não depende só de cor: a rotação é geométrica.

## D5. Bordas, hover e alvo de toque

- Repouso: a borda do input passa a usar `var(--hospital-control-border)`
  (token de fato mais presente: ~3,35:1 contra a superfície; `--hospital-border`
  é o token claro, ~1,46:1). Como `.hospital-shell .form-control`
  (especificidade 0,2,0) já aplica `--hospital-border` a todos os controles
  dentro do shell, a regra do componente precisa vencer por especificidade:
  `.hospital-shell .procedure-combobox__input { border-color:
  var(--hospital-control-border); }`. *(Emenda pós-review-1: a redação
  original invertia os tokens e a troca seria no-op visual — evidência do
  reviewer: `app.css:496-501` já pintava a borda de repouso.)*
- `:hover` muda a cor da borda (afordância de interatividade; não é portador
  de informação).
- `min-height: 44px` no input (alvo de toque; tablets de enfermaria).
- O foco-visível forte existente (outline + box-shadow) permanece intacto.

## D6. Estado selecionado na listbox

- JS marca a row cujo `value` corresponde ao `select.value` com classe
  `procedure-combobox__option--selected` e atributo `aria-selected="true"`
  (na construção das rows, em `syncFromSelect` e após `commit`). Row ativa de
  teclado continua `--active`/`aria-activedescendant` — conceitos distintos.
- CSS: peso 600 + barra à esquerda em accent (marcador além de cor).
- `aria-selected` corrige a semântica do padrão combobox (role=option) sem
  alterar teclado/foco.

## D7. Guarda de vocabulário CSS (AGENTS §8)

Novo teste `tests/test_procedure_combobox_css.py` (padrão do
`tests/test_exam_type_badge_css.py`) pina, sem comentários, a existência de:
`.procedure-combobox__hint`, `.procedure-combobox__option--selected`, a regra
do chevron (`procedure-combobox--enhanced:has(` + `::after`), `:hover` do
input e `min-height` do input. O `static/css/app.css` está no blast radius do
Slice 001 por construção.

## D8. Cobertura de testes

- **Node** (`static/js/tests/procedure_combobox.test.js`): placeholder
  propagado quando o data-attribute existe; ausente quando não existe; classe
  `--selected` + `aria-selected` na row do valor selecionado; placeholder
  preservado após re-render (syncFromSelect com valor selecionado mostra o
  label no value, placeholder permanece no atributo).
- **Django-side** (cobertura canônica por superfície): `data-combobox-
  placeholder` presente no select com o copy da jornada; hint com id estável;
  `aria-describedby` do select referencia o hint (e mantém guidance/error no
  upload); re-render com erro preserva hint + associação.
- **CSS guard**: D7.

## Decisão de dimensionamento

Dois slices verticais: (001) componente compartilhado provado na jornada
upload (JS + CSS + template + os três tipos de teste); (002) as três
superfícies restantes ganham placeholder/hint/associação com testes
Django-side de cada jornada. Não fragmentar além disso — o comportamento é
uno por componente.
