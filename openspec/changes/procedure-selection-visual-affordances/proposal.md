# Proposal: Affordances visuais da seleção de procedimentos

## Problema

Durante o smoke da `v0.10.0-rc.1` em produção, o campo de seleção de tipo de
exame (NIR e médico) mostrou pouca dica visual de funcionalidade. Inspeção do
código confirma:

- o input aprimorado criado por `static/js/procedure_combobox.js` nasce **sem
  `placeholder`** — vazio, parece um campo de texto inerte;
- a borda de repouso é 1px com `--hospital-control-border` (sutil) e **não há
  estado `:hover`**, chevron ou outro indício de que o controle abre uma lista;
- a listbox não distingue a **opção selecionada** do destaque de navegação por
  teclado;
- apenas o upload tem hint textual (`exam-type-guidance`); correção, reenvio e
  destino médico não têm orientação de busca — e a busca sem acentos/por
  sinônimos é um recurso que o usuário não adivinha.

## Objetivo

Tornar a funcionalidade do combobox autoevidente em **todas as quatro
superfícies** (upload, correção, reenvio NIR e destino médico), por:

1. placeholder específico da jornada no input aprimorado (decorativo);
2. hint persistente sobre a busca (sem acentos, sinônimos, teclado) associado
   por `aria-describedby`;
3. chevron indicando lista expansível, com estado ligado à expansão;
4. bordas de repouso/hover mais presentes e alvo de toque ≥ 44 px;
5. estado "selecionado" distinguível na listbox, distinto do ativo de teclado.

## Escopo

- Componente compartilhado: `static/js/procedure_combobox.js` (aditivo),
  `static/css/app.css` (bloco `.procedure-combobox*`).
- Templates das quatro superfícies: `intake_home.html`, `case_detail.html`,
  `corrected_resubmission.html`, `decision.html`.
- Testes: Node do componente, Django-side das superfícies e guarda de
  vocabulário CSS.

### Fora de escopo (inalerável)

- Qualquer mudança em nomes de campo POST, valores/labels de `<option>`,
  validação backend, catálogo, matriz de combinações ou policy.
- Semântica ARIA base do D9 (role combobox, aria-expanded/controls/
  activedescendant, fallback SSR).
- Paleta global (`:root`), redesign visual além do bloco do componente.

## Sucesso

- As quatro superfícies exibem placeholder + hint; hint associado por
  `aria-describedby` ao select e herdado pelo input aprimorado.
- Sem JavaScript, nada regride (a primeira option do select continua sendo o
  placeholder natural).
- Guarda de CSS pina o vocabulário novo (anti-pattern do AGENTS §8 coberto).
- Gate final verde (ruff/format/mypy/pytest + node --test).
