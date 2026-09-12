# Slice 001 — Catálogo de quatro procedimentos e matriz fechada

## Objetivo

Estabelecer a fonte única de tipos, ordem e conjuntos permitidos, corrigindo o pressuposto `len == 2` antes de qualquer intake especializado. É um foundation slice inevitável; flags ainda permanecem desligadas e nenhum fluxo especializado é exposto.

## Contexto necessário

- `AGENTS.md`
- `design.md`: D1–D3 e D15
- `specs/procedure-combination-policy/spec.md`
- `apps/cases/models.py`, `apps/cases/procedures.py`, `apps/cases/exam_profiles.py`
- `apps/pipeline/procedure_reconciliation.py`
- `apps/cases/tests/test_case_procedure.py`

## Requisitos verificáveis

- **R1:** `ProcedureType` contém EDA, Colonoscopia, Ecoendoscopia e CPRE; migration state fica alinhado sem backfill.
- **R2:** catálogo/ordem/matriz e helper de agendamento casado têm uma fonte única.
- **R3:** somente cinco conjuntos são válidos; combinações especializadas e três ou mais tipos falham.
- **R4:** `selection_key` retorna combinado somente para igualdade exata com EDA + Colonoscopia.
- **R5:** reconciliação aplica precedência dos pares EDA+Eco e EDA+CPRE; demais incompatíveis retornam revisão com reason code dedicado.
- **R6:** perfis Eco/CPRE não permitem exceção de corpo estranho.

## Escopo e blast radius

```yaml
expected_files:
  - apps/cases/models.py
  - apps/cases/procedures.py
  - apps/cases/exam_profiles.py
  - apps/cases/migrations/00xx_*.py
  - apps/pipeline/procedure_reconciliation.py
  - apps/cases/tests/test_case_procedure.py
  - apps/pipeline/tests/test_specialized_procedure_reconciliation.py
allowed_incidental_files:
  - apps/cases/tests/test_exam_type.py
file_cap: 8
out_of_scope:
  - UI/intake especializado
  - schemas ou prompts 3.0
  - policy de imagem
  - decisão médica
```

Escalar antes de alterar FSM, `CaseProcedure` fields/constraints ou persistir uma row genérica `combined`.

## Matriz requisito → arquivo → teste/check

| Requisito | Arquivos esperados | Teste/check |
| --- | --- | --- |
| R1/R6 | `models.py`, migration, `exam_profiles.py` | testes de enum/perfis e `makemigrations --check` |
| R2–R4 | `procedures.py` | casos válidos/inválidos e par exato |
| R5 | `procedure_reconciliation.py` | precedência, incompatível e mismatch |

## RED

- Comando: `uv run pytest apps/cases/tests/test_case_procedure.py apps/pipeline/tests/test_specialized_procedure_reconciliation.py -q`
- Falha esperada: enums/perfis/helpers ainda não aceitam os novos tipos e qualquer par de tamanho dois ainda pode ser classificado como combinado.

## GREEN / verificação local

- `uv run pytest apps/cases/tests/test_case_procedure.py apps/cases/tests/test_exam_type.py apps/pipeline/tests/test_specialized_procedure_reconciliation.py -q`
- `uv run python manage.py makemigrations --check --dry-run --settings=config.settings.test`
- `uv run ruff check apps/cases/models.py apps/cases/procedures.py apps/cases/exam_profiles.py apps/pipeline/procedure_reconciliation.py apps/cases/tests/test_case_procedure.py apps/pipeline/tests/test_specialized_procedure_reconciliation.py`
- `uv run ruff format --check` nos mesmos arquivos Python alterados.

## Critérios de aceitação

- [ ] R1–R6 provados pelos checks focados.
- [ ] Nenhum fluxo especializado foi exposto antecipadamente.
- [ ] Não existe decisão de domínio baseada apenas em `len(types) == 2`.
- [ ] Diff permanece no cap ou expansão foi aprovada antes da edição.

## Handoff

Registrar diff, comandos/resultados, riscos residuais e `REPORT_PATH=/tmp/support-independent-echoendoscopy-cpre-slice-001-report.md`. Parar; não iniciar o Slice 002 sem review aceito e confirmação explícita.
