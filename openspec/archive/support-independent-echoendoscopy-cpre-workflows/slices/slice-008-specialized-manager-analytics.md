# Slice 008 — Analytics gerencial especializado

## Objetivo

Entregar ao gestor categorias exclusivas, filtros e volumes de Ecoendoscopia/CPRE nas três dimensões, sem dupla contagem nem matriz visual nova.

## Contexto necessário

- delta `exam-type-analytics`
- `design.md`: D13 e D15
- `apps/dashboard/procedure_analytics.py`, dashboard views/templates/tests

## Requisitos verificáveis

- **R1:** breakdown declarado/detectado/autorizado contém EDA, Colon, EDA+Colon, Eco, CPRE e none quando aplicável.
- **R2:** cada caso pertence a exatamente uma categoria e soma fecha com universo.
- **R3:** volume por componente inclui quatro tipos; Eco/CPRE não aumentam EDA.
- **R4:** agendamento casado conta somente conjunto exato EDA+Colon confirmado.
- **R5:** tabela compõe dimensão/tipo com busca/status/datas/atenção/paginação.
- **R6:** dashboard não introduz matriz de conversão visual ou painel proibido.

## Escopo e blast radius

```yaml
expected_files:
  - apps/dashboard/procedure_analytics.py
  - apps/dashboard/views.py
  - templates/dashboard/index.html
  - templates/dashboard/_case_list.html
  - apps/dashboard/tests/test_procedure_analytics.py
  - apps/dashboard/tests/test_dashboard.py
allowed_incidental_files: []
file_cap: 6
out_of_scope:
  - filas NIR/doctor/CHD
  - follow-up
  - nova métrica clínica
```

## Matriz requisito → arquivo → teste/check

| Requisito | Arquivos esperados | Teste/check |
| --- | --- | --- |
| R1–R4 | analytics helper/tests | categorias, fechamento, componentes, paired exact |
| R5/R6 | views/templates/tests | composição de params e ausência de nova matriz visual |

## RED

1. Adicionar fixtures/assertions Eco/CPRE aos testes existentes.
2. `uv run pytest apps/dashboard/tests/test_procedure_analytics.py apps/dashboard/tests/test_dashboard.py -q -k 'procedure or exam_type or specialized or echoendoscopy or cpre'`
3. RED válido: assertions especializadas falham; collection vazia/erro não vale.

## GREEN / verificação local

- Rodar ambos os módulos completos com exit code 0.
- Ruff check/format nos Python alterados.

## Critérios de aceitação

- [ ] R1–R6 provados.
- [ ] Caso especializado conta uma vez e um componente próprio.
- [ ] Combinado existente permanece exato.

## Handoff

Gerar `REPORT_PATH=/tmp/support-independent-echoendoscopy-cpre-slice-008-report.md`. Parar.

## Prompt para implementador com contexto zero

Leia `AGENTS.md`, `PROJECT_CONTEXT.md`, ADR-0006, `proposal.md`, `design.md`, `tasks.md` e este arquivo. Implemente **somente o Slice 008**: filtros e analytics gerenciais exclusivos para quatro tipos, preservando as dimensões declarado/detectado/autorizado e sem dupla contagem. Crie testes RED primeiro, alcance GREEN, refatore, rode gates e gere o `REPORT_PATH`. Não altere `tasks.md`, não faça commit/push, não execute rollout nem arquive o change; entregue o handoff ao parent e pare.
