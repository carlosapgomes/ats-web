# Slice 005 — Jornada médica nas filas especializadas

## Objetivo

Permitir que o médico encontre e filtre Ecoendoscopia/CPRE em Pendentes e Decididos Hoje, vendo a dimensão correta e transformações sem alterar a decisão já entregue.

## Contexto necessário

- delta `exam-type-work-queues`
- `design.md`: D12–D13
- doctor queue views/templates/JS e testes atuais de filtros

## Requisitos verificáveis

- **R1:** Pendentes filtra por detectado: Todos, EDA, Colonoscopia, EDA+Colonoscopia, Eco e CPRE.
- **R2:** Decididos Hoje filtra por autorizado e preserva `Nenhum autorizado`.
- **R3:** busca, polling e seleção compõem sem perder parâmetros.
- **R4:** cards especializados usam badge singleton e mostram detectado→autorizado quando divergem.
- **R5:** não existe inferência por texto do badge nem lógica binária de “outro tipo”.

## Escopo e blast radius

```yaml
expected_files:
  - apps/doctor/views.py
  - templates/doctor/_queue_content.html
  - static/js/doctor-queue.js
  - apps/doctor/tests/test_queue_exam_type_filters.py
allowed_incidental_files:
  - apps/doctor/tests/test_views.py
file_cap: 5
out_of_scope:
  - CHD/NIR/dashboard/follow-up
  - formulário de decisão
```

## Matriz requisito → arquivo → teste/check

| Requisito | Arquivos esperados | Teste/check |
| --- | --- | --- |
| R1/R2 | view/template | universos detected/approved parametrizados |
| R3/R5 | JS/data attributes | polling+search+filter e ausência de inferência textual |
| R4 | template/context | badges e transformação acessível |

## RED

1. Adicionar casos Eco/CPRE aos testes existentes antes de rodar.
2. `uv run pytest apps/doctor/tests/test_queue_exam_type_filters.py -q`
3. RED válido: assertions dos novos filtros/cards falham, não collection.

## GREEN / verificação local

- Mesmo módulo com exit code 0.
- `uv run pytest apps/doctor/tests/test_views.py -q -k 'queue or decided'`
- Ruff check/format nos Python alterados.

## Critérios de aceitação

- [ ] R1–R5 provados.
- [ ] Nenhum arquivo de outro ator foi tocado.
- [ ] EDA+Colon preserva semântica exata.

## Handoff

Gerar `REPORT_PATH=/tmp/support-independent-echoendoscopy-cpre-slice-005-report.md`. Parar.

## Prompt para implementador com contexto zero

Leia `AGENTS.md`, `PROJECT_CONTEXT.md`, ADR-0006, `proposal.md`, `design.md`, `tasks.md` e este arquivo. Implemente **somente o Slice 005**: jornada médica especializada em Pendentes/Decididos Hoje, usando as dimensões corretas, badges e transformação textual. Crie primeiro os testes RED, alcance GREEN, refatore, rode os gates e gere o `REPORT_PATH`. Não altere `tasks.md`, não faça commit/push nem altere filas CHD/NIR ou analytics; entregue o handoff ao parent e pare.
