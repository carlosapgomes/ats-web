# Slice 007 — Jornada NIR após intake especializado

## Objetivo

Fechar acompanhamento, revisão/correção, encerrados e filtros do NIR para Ecoendoscopia/CPRE usando a dimensão declarada e preservando comparação final.

## Contexto necessário

- deltas `exam-type-intake-routing`, `exam-type-correction`, `exam-type-analytics`
- `design.md`: D12–D14
- intake operational/closed views, templates e testes

## Requisitos verificáveis

- **R1:** listas operacionais/encerradas filtram `all|eda|colonoscopy|eda_colonoscopy|echoendoscopy|cpre` por declarado.
- **R2:** cards/detalhes mostram badge singleton e comparação declarado/detectado/autorizado.
- **R3:** mismatch especializado oferece correção somente quando flag ativa e antes de `WAIT_DOCTOR`.
- **R4:** correção preserva PDF/anexos/texto, invalida derivados e reprocessa uma vez em 3.0 sem analisar anexos.
- **R5:** histórico legado Eco permanece sinal legível e não recebe row por backfill.
- **R6:** busca, polling e parâmetros existentes continuam.

## Escopo e blast radius

```yaml
expected_files:
  - apps/intake/views.py
  - apps/intake/services.py
  - templates/intake/_my_cases_content.html
  - templates/intake/case_detail.html
  - templates/intake/closed_cases_search.html
  - apps/intake/tests/test_my_cases.py
  - apps/intake/tests/test_exam_type_correction.py
  - apps/intake/tests/test_specialized_final_response.py
allowed_incidental_files:
  - templates/intake/closed_case_detail.html
file_cap: 9
out_of_scope:
  - doctor/CHD/dashboard manager
  - backfill/rewrite JSON
```

## Matriz requisito → arquivo → teste/check

| Requisito | Arquivos esperados | Teste/check |
| --- | --- | --- |
| R1/R2/R6 | views/templates | filtros, busca, polling e comparação |
| R3/R4 | service/detail | flag/status/lock, invalidação e único job |
| R5 | detalhe histórico | legado sem nova row |

## RED

1. Ampliar os testes existentes para Eco/CPRE antes de rodar.
2. `uv run pytest apps/intake/tests/test_my_cases.py apps/intake/tests/test_exam_type_correction.py apps/intake/tests/test_specialized_final_response.py -q`
3. RED válido: novas assertions falham; erro de path/collection não vale.

## GREEN / verificação local

- Mesmo comando RED com exit code 0.
- `uv run pytest apps/intake/tests/test_slice_005_nir_correction_and_response.py apps/intake/tests/test_slice_008_nir_declared_projection_authority.py -q`
- Ruff check/format nos Python alterados.

## Critérios de aceitação

- [ ] R1–R6 provados.
- [ ] Dimensão NIR é sempre declarada.
- [ ] Nenhum backfill especializado foi introduzido.

## Handoff

Gerar `REPORT_PATH=/tmp/support-independent-echoendoscopy-cpre-slice-007-report.md`. Parar.

## Prompt para implementador com contexto zero

Leia `AGENTS.md`, `PROJECT_CONTEXT.md`, ADR-0006, `proposal.md`, `design.md`, `tasks.md` e este arquivo. Implemente **somente o Slice 007**: acompanhamento, correção, encerrados e filtros NIR especializados pela dimensão declarada, sem backfill. Crie testes RED antes do código, alcance GREEN, refatore, rode gates e gere o `REPORT_PATH`. Não altere `tasks.md`, não faça commit/push nem altere analytics ou rollout; entregue o handoff ao parent e pare.
