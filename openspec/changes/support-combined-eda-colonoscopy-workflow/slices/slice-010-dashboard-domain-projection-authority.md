# Slice 010: Dashboard e helpers tornam CaseProcedure autoritativo

## Handoff com contexto zero

Leia artefatos, ADR-0004 e relatórios 001–009. Inspecione `apps/dashboard/views.py`, `apps/dashboard/procedure_analytics.py`, templates/testes do dashboard e getters em `apps/cases/procedures.py`.

### Fluxo entregue

```text
gestor escolhe dimensão declarado/detectado/autorizado
→ tabela/breakdown/volume/matriz usam somente CaseProcedure
→ filtro singular legado do dashboard desaparece
→ getters de domínio não caem em Case.exam_type
→ ausência de row é vazia/fail-closed
```

Após este slice, nenhum reader operacional deve depender da coluna; apenas dual-write/schema serão removidos no Slice 011.

## Protocolo obrigatório para DeepSeek4-Flash

Confirme branch/árvore/ADR e `BASE_REF`; matriz e baseline completo antes de editar; inventário global; RED real; GREEN mínimo; REFACTOR local; inspeções e quality gate completo; relatório; marcar somente 010, commit/push e PARE. Qualquer failure/error ou passed final menor = INCOMPLETO.

**Cap: 11 arquivos produto/teste/template.** Acima disso, pare antes de editar.

## Requisitos

### R1. Remover dashboard singular superseded

Remover `_compute_exam_type_breakdown`, filtros/query de coluna e UI singular que competem com a dimensão do Slice 006. Preservar o parâmetro `exam_type` apenas onde ele for contrato de outra tela; no dashboard final, usar `procedure_dimension` + `procedure_selection` como fonte única de filtro.

### R2. Analytics SQL sem fallback

`apply_procedure_selection_filter` usa somente `Exists`/predicados de `CaseProcedure`. Remover `_exam_type_selection_q`, `_legacy_fallback_q`, `_none_fallback_q` baseados na coluna. `none` significa ausência na dimensão consultada segundo contrato explícito, sem inferência por valor legado.

### R3. Getters fail-closed

`get_declared_procedure_types`, `get_detected_procedure_types` e `get_approved_procedure_types` retornam apenas rows normalizadas. Remover fallback para coluna e fallback global de `doctor_decision=accept`. Seleção combinada continua sendo chave derivada de duas rows; `eda_colonoscopy` pode permanecer como valor de UI, não ponte persistida.

### R4. Fixtures e fechamento

Testes de dashboard/cases afetados criam rows explicitamente. Combinado fecha como 1 caso/2 componentes; categorias exclusivas e matriz permanecem corretas; caso inválido sem rows entra apenas em `none` quando aplicável e nunca em EDA.

### R5. Índices revalidados

Registrar SQL/plano das queries dimensionais reais e confirmar uso/adequação dos índices `proc_declared_idx`, `proc_detection_idx`, `proc_disposition_idx`. Não criar índice novo sem evidência.

### R6. Inventário global de readers

Executar busca em produto inteiro. Toda ocorrência de acesso à coluna deve estar destinada ao writer/schema temporário do Slice 011, payload histórico ou nome de parâmetro. Reader/query fora disso = INCOMPLETO.

## Arquivos esperados

- `apps/dashboard/views.py`;
- `apps/dashboard/procedure_analytics.py`;
- `templates/dashboard/index.html` e/ou `_case_list.html` se necessário;
- `apps/cases/procedures.py`;
- testes dashboard/cases estritamente afetados.

Proibido: model/migration/dual-write, pipeline/prompts, intake/doctor/scheduler já concluídos, docs rollout, UI redesign.

## TDD obrigatório

RED prova query fallback, badge direto da coluna, getter com default e caso sem row contado como EDA. GREEN remove-os; REFACTOR elimina código/template morto sem alterar fórmulas case-level.

## Inspeções obrigatórias

```bash
rg -n "Case\.exam_type|case\.exam_type|self\.exam_type|get_exam_type_display|filter\([^\n]*exam_type|Q\([^\n]*exam_type|exam_type__" apps config templates static --glob '!**/migrations/**'
rg -n "_compute_exam_type_breakdown|_legacy_fallback_q|_exam_type_selection_q|_none_fallback_q" apps/dashboard templates/dashboard
rg -n "procedure_dimension|procedure_selection|CaseProcedure|Exists|declared_by_nir|detection_status|doctor_disposition" apps/dashboard templates/dashboard
rg -n "eda_colonoscopy" apps/cases/procedures.py apps/dashboard templates/dashboard static
uv run python manage.py shell --settings=config.settings.test -c "from apps.cases.models import CaseProcedure; print(CaseProcedure.objects.filter(procedure_type='eda', declared_by_nir=True).explain())"
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
openspec validate support-combined-eda-colonoscopy-workflow --strict
git diff --check
git diff --name-only "$BASE_REF"
```

A interpretação global deve listar escritores/schema permitidos que restam para 011.

## Critérios/gates

- [ ] R1–R6 provados.
- [ ] Dashboard tem apenas filtro dimensional novo.
- [ ] Analytics/getters sem fallback de coluna.
- [ ] Ausência não vira EDA.
- [ ] Fechamentos e combinado regressam.
- [ ] Índices revalidados com evidência.
- [ ] Inventário global deixa apenas schema/writer temporário e histórico legítimo.
- [ ] Cap/gates verdes.

Responder: qual UI singular saiu; como `none` funciona; quais testes provam fail-closed; plano dos índices; resíduos globais classificados; fixtures; arquivos; baseline-final.

### Condições automáticas de INCOMPLETO

Filtro/getter/badge operacional ainda lê coluna; ausência vira EDA; UI singular conflita; índice alegado sem plano; reader residual fora do destino 011; fórmula dashboard quebra; cap/gate falha; relatório ausente.

## Relatório obrigatório

Criar `/tmp/support-combined-eda-colonoscopy-workflow-slice-010-report.md` com matriz, baseline, RED/GREEN, snippets, inventário global, EXPLAIN interpretado, cap/gates, comparação final e Handoff R1–R6.

## Prompt pronto

```text
Read all artifacts, ADR-0004 and approved reports 001-009. Implement ONLY resized Slice 010 using TDD and its DeepSeek protocol.

Retire the dashboard's old singular exam_type breakdown/filter/UI, keep only procedure_dimension/procedure_selection, remove all column fallbacks from procedure analytics and the three domain getters, make missing rows fail closed, migrate affected dashboard/cases fixtures explicitly, and revalidate the Slice 001 indexes with an actual query plan. Perform a global reader inventory; only temporary schema/writers for Slice 011 and historical payload/parameter names may remain. Do not remove the field/migration/dual-write yet or touch completed apps/docs. Above 11 files or any gate failure = INCOMPLETE.

Create /tmp/support-combined-eda-colonoscopy-workflow-slice-010-report.md; if complete mark only Slice 010, commit, push, reply REPORT_PATH and STOP.
```
