# Slice 009 — Analytics gerencial do catálogo ampliado

## Objetivo

Entregar breakdown e tabela gerencial para dez identidades + EDA/Colonoscopia combinadas, mantendo cada caso em uma categoria exclusiva e cada row em seu volume de componente. Famílias clínicas não agregam identidades e paired continua restrito ao par exato.

## Contexto necessário

- `design.md`: D12 e D15;
- `specs/exam-type-analytics/spec.md`;
- `apps/dashboard/procedure_analytics.py`, views e `templates/dashboard/index.html`;
- `apps/dashboard/tests/test_procedure_analytics.py`, `test_dashboard.py`;
- helpers de catálogo/selection key e testes de filas NIR concluídos.

## Requisitos verificáveis

- **R1:** resumo `declared|detected|approved` oferece categorias exclusivas para cada singleton, `eda_colonoscopy` e `none` quando aplicável; soma fecha com universo.
- **R2:** filtro de tabela compõe dimensão, selection key, busca/status/datas/atenção/paginação e usa igualdade exata; EDA simples não aparece em `eda_gastrostomy`.
- **R3:** volume por componente conta cada código atômico; pacote é um componente, combinado são dois componentes de um caso e profile/família não agrega volumes.
- **R4:** paired confirmado conta uma vez somente o autorizado exato `{eda, colonoscopy}`; nenhuma label com `+` conta.
- **R5:** conjunto inválido não é reduzido/contado silenciosamente como categoria válida.
- **R6:** opções/labels/ordem vêm do catálogo, não de listas locais fechadas.

## Escopo e expected blast radius

```yaml
expected_files:
  - apps/dashboard/procedure_analytics.py
  - apps/dashboard/views.py
  - templates/dashboard/index.html
  - apps/dashboard/tests/test_procedure_analytics.py
  - apps/dashboard/tests/test_expanded_procedure_analytics.py
allowed_incidental_files:
  - partial dashboard diretamente responsável pelo breakdown/tabela
  - helper genérico no catálogo se faltar projeção já prevista
out_of_scope:
  - matriz visual de conversões
  - backfill/reclassificação histórica
  - novos KPIs ou mudanças de universo/status/data
```

Se for necessário mudar semântica de métrica consolidada, introduzir N+1 ou inferir identidade de sinal legado, parar e escalar.

## Matriz requisito → arquivo → teste/check

| Requisito | Arquivo(s) esperado(s) | Teste/check |
| --- | --- | --- |
| R1, R3–R6 | `procedure_analytics.py` | `test_expanded_procedure_analytics.py` |
| R2 | analytics/view/template | teste client com filtros compostos |
| regressão | mesmos arquivos | `test_procedure_analytics.py`, `test_dashboard.py` |

## RED

```bash
uv run pytest apps/dashboard/tests/test_expanded_procedure_analytics.py -q
```

Criar teste antes. Falha esperada: `SELECTIONS`, labels e annotations fechados em quatro tipos. Fixtures mínimas: EDA, EDA+GTT, EDA+Dilatação, Colonoscopia, Retossigmoidoscopia, Retossigmoidoscopia+Argônio, Ecoendoscopia, CPRE, combinado e nenhum autorizado.

## GREEN / verificação local

```bash
uv run pytest \
  apps/dashboard/tests/test_expanded_procedure_analytics.py \
  apps/dashboard/tests/test_procedure_analytics.py \
  apps/dashboard/tests/test_dashboard.py \
  apps/intake/tests/test_expanded_nir_queues.py -q
uv run ruff check apps/dashboard
uv run ruff format --check apps/dashboard
```

Inventário:

```bash
rg -n 'SELECTIONS|eda_colonoscopy|ProcedureType\.(EDA|COLONOSCOPY|ECHOENDOSCOPY|CPRE)|"combined"' \
  apps/dashboard templates/dashboard
```

Toda ocorrência restante deve ser derivação genérica, regra paired exata, adapter histórico ou teste intencional classificado no relatório.

## Critérios de aceitação

- [ ] R1: categorias são exclusivas e fecham com o universo.
- [ ] R2: filtros compostos preservam identidade exata/paginação.
- [ ] R3: caso e componente não são confundidos nem agregados por família.
- [ ] R4/R5: paired e inconsistência são tratados fail-closed.
- [ ] R6: opções/labels não duplicam o catálogo.

## Handoff

Worker implementa apenas analytics gerencial e para. Reviewer recalcula manualmente ao menos uma fixture mista e verifica ausência de dupla contagem/backfill implícito.
