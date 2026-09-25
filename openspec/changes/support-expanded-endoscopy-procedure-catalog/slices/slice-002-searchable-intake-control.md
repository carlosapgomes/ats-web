# Slice 002 — Controle pesquisável no upload NIR

## Objetivo

Substituir os radios de procedimento do upload atual por combobox acessível e pesquisável, sem ainda expor as novas identidades. EDA, Colonoscopia, EDA + Colonoscopia, Ecoendoscopia e CPRE preservam flags, contrato POST e persistência existentes; busca sem acentos e fallback SSR ficam prontos para o catálogo ampliado.

## Contexto necessário

- `design.md`: D9–D10;
- `specs/searchable-procedure-selection/spec.md`;
- requisito de intake em `specs/exam-type-intake-routing/spec.md`;
- `templates/intake/intake_home.html`, `static/js/upload.js`, `static/css/app.css`;
- `apps/intake/views.py`, `apps/intake/services.py`;
- `apps/intake/tests/test_exam_type_intake.py` e `test_specialized_procedure_intake.py`.

## Requisitos verificáveis

- **R1:** upload SSR renderiza `<select name="exam_type">` sem opção real pré-selecionada e com exatamente as opções atualmente permitidas pelas flags, fornecidas pelo helper de jornada de `apps/intake/services.py` (lista ordenada explícita composta com o catálogo).
- **R2:** JS aprimora o select em combobox/listbox com ARIA, foco visível e teclado Arrow/Home/End/Enter/Escape/Tab; o select permanece o valor submetido.
- **R3:** busca ignora caixa/acentos, encontra labels/aliases aprovados e nunca cria valor livre.
- **R4:** sem JS, upload continua funcional; re-render inválido preserva seleção; `upload.js` habilita submit pela mudança do select.
- **R5:** backend aceita somente selection key canônica e continua rejeitando alias/texto livre/combinação indisponível sem criar caso.
- **R6:** nenhum pacote novo fica disponível neste slice e nenhuma dependência frontend é adicionada.

## Escopo e expected blast radius

```yaml
expected_files:
  - templates/intake/intake_home.html
  - static/js/procedure_combobox.js
  - static/js/upload.js
  - static/css/app.css
  - apps/intake/views.py
  - apps/intake/services.py
  - apps/intake/tests/test_searchable_procedure_upload.py
  - static/js/tests/procedure_combobox.test.js
allowed_incidental_files:
  - helper/template parcial reutilizável sob templates/cases/
out_of_scope:
  - correção/reenvio NIR
  - decisão médica
  - novas identidades no intake
  - filtros de filas
```

Novo vocabulário CSS exige `static/css/app.css` neste slice. Se o componente precisar de framework/dependência, mudar nome de campo POST ou tocar policy/pipeline, parar e escalar.

## Matriz requisito → arquivo → teste/check

| Requisito | Arquivo(s) esperado(s) | Teste/check |
| --- | --- | --- |
| R1, R4–R6 | template/view/upload JS | `test_searchable_procedure_upload.py` |
| R2–R3 | `procedure_combobox.js`, CSS | `node --test static/js/tests/procedure_combobox.test.js` (complementar; cobertura canônica é Django-side) |
| R5 | view/service | POSTs manipulados no teste Django |

## RED

Após criar os testes:

```bash
uv run pytest apps/intake/tests/test_searchable_procedure_upload.py -q
node --test static/js/tests/procedure_combobox.test.js
```

Falha esperada: HTML ainda contém radios, módulo de combobox/comportamentos não existem e `upload.js` só observa radios. O teste Node deve carregar o arquivo existente/fixture corretamente; erro de arquivo ausente não conta como RED depois que o teste foi criado.

## GREEN / verificação local

```bash
uv run pytest \
  apps/intake/tests/test_searchable_procedure_upload.py \
  apps/intake/tests/test_exam_type_intake.py \
  apps/intake/tests/test_specialized_procedure_intake.py \
  apps/intake/tests/test_upload.py -q
node --test static/js/tests/procedure_combobox.test.js
uv run ruff check apps/intake
uv run ruff format --check apps/intake
```

Inspeção manual obrigatória registrada no relatório (desktop ou browser disponível): operar o controle somente por teclado, desabilitar JS e submeter EDA, e confirmar foco visível/erro textual. Se browser não estiver disponível, registrar explicitamente como evidência pendente para o Slice 010, sem declarar o check como executado.

## Critérios de aceitação

- [ ] R1/R6: opções e flags atuais permanecem idênticas, sem pacote novo.
- [ ] R2/R3: teclado, ARIA e busca sem acentos passam no teste JS.
- [ ] R4: fallback SSR e preservação após erro funcionam.
- [ ] R5: código exato continua autoridade no backend.

## Handoff

Implementar somente a jornada de upload atual. Entregar relatório com RED/GREEN, teste Node e smoke manual possível; não migrar correção/médico nem expor identidades futuras. Parent/reviewer decide aceite antes do próximo slice.
