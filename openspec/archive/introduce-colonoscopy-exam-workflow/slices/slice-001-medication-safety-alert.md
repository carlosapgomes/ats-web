# Slice 001: Medicamentos relevantes no relatório médico

## Handoff para implementador LLM com contexto zero

Leia integralmente, nesta ordem:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `openspec/changes/introduce-colonoscopy-exam-workflow/proposal.md`
4. `openspec/changes/introduce-colonoscopy-exam-workflow/design.md` — especialmente D6
5. `openspec/changes/introduce-colonoscopy-exam-workflow/specs/medication-safety/spec.md`
6. `openspec/changes/introduce-colonoscopy-exam-workflow/tasks.md`
7. este slice
8. `apps/pipeline/schemas/llm1.py`
9. `apps/pipeline/llm1_service.py`
10. `apps/doctor/presenters.py`
11. `apps/doctor/reporting.py`
12. testes atuais de LLM1 e presenter.

### Estado atual

LLM1 extrai comorbidades e exames, mas não possui coleção de medicamentos. O presenter médico monta sete blocos e é reutilizado na reconstrução gerencial. Não existe hard rule para anticoagulante/antiagregante.

### Objetivo exato

```text
EDA atual contém medicamento explícito
→ LLM1 valida coleção estruturada com evidência
→ artefato é persistido normalmente
→ relatório médico destaca anticoagulante/antiagregante
→ sugestão/policy não muda
```

### Limites

Não implementar `Case.exam_type`, colonoscopia, catálogo farmacológico, suspensão, janela de dose, nova tabela/model/migration ou alteração de policy.

## Protocolo obrigatório para implementador DeepSeek4-Flash

Este slice será implementado por modelo rápido. Siga literalmente. **Qualquer falha torna o slice INCOMPLETO**: não marque `tasks.md`, não faça commit/push.

1. Registre `BASE_REF=$(git rev-parse HEAD)`, branch e `git status --short`; branch deve ser `feature/colonoscopy-exam-workflow` e árvore inicial limpa.
2. Antes de editar, crie no relatório matriz `Requisito → arquivo(s) → teste(s)` e rode `uv run pytest`. Registre exit code e resumo. Baseline com failure/error bloqueia implementação.
3. Escreva testes primeiro e prove RED real no subconjunto alvo pelo motivo funcional esperado.
4. Faça GREEN mínimo; não antecipe slices seguintes.
5. Faça REFACTOR apenas no código tocado, com clean code, DRY, YAGNI, funções coesas, nomes claros e nenhum código morto.
6. Execute todas as inspeções `rg`/diff deste slice e interprete resultados.
7. Execute exatamente `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy .`, `uv run pytest`. Final exige exit 0, zero failures/errors e `passed_final >= passed_baseline`.
8. Relatório deve conter evidência factual, snippets reais antes/depois e `Handoff para verificador`.
9. Só então marque Slice 001, commit, push, responda `REPORT_PATH=...` e PARE.

## Requisitos funcionais

### R1. Contrato estruturado

Adicionar modelos estritos para medicamentos no contrato LLM1:

- `name`: obrigatório, não vazio, limite razoável;
- `normalized_name`: opcional;
- `medication_class`: `anticoagulant | antiplatelet | other | unknown`;
- `use_status`: `current | recent | historical | suspended | unknown`;
- `last_dose_or_schedule`: opcional;
- `source_text_hint`: obrigatório e não vazio;
- lista `medications_described`, default vazio e limite defensivo.

Payload antigo sem a chave deve validar como lista vazia. Campo desconhecido continua proibido.

### R2. Instruções LLM1

Defaults e prompt final devem exigir:

- somente medicamentos explicitamente descritos;
- evidência por item;
- destaque/classificação de anticoagulantes/antiagregantes;
- não inferir por comorbidade, idade, exame ou diagnóstico;
- não inventar última dose;
- lista vazia na ausência.

Não alterar nomes canônicos dos prompts neste slice.

### R3. Alerta no presenter

O relatório técnico deve mostrar seção/linhas claras de medicamentos. Quando houver `anticoagulant` ou `antiplatelet`, incluir alerta no início de `Achados críticos` ou em posição igualmente proeminente:

```text
Medicamento relevante: <nome> — anticoagulante/antiagregante
Uso descrito: <status>
Conduta: confirmar manejo peri-procedimento.
```

Não recomendar suspensão. Renderizar evidência/última dose apenas quando disponível. Payload ausente/malformado não causa erro.

### R4. Policy permanece independente

Nenhum arquivo de policy deve mudar. Teste deve provar que adicionar medicamentos ao mesmo payload não altera sugestão/reason da policy ou, no mínimo, inspeção deve provar ausência de leitura medicamentosa na policy.

### R5. Compatibilidade da reconstrução gerencial

Como `prepare_doctor_case_report` usa o mesmo presenter, o alerta deve aparecer automaticamente no texto reconstruído sem duplicar regra no dashboard.

## Arquivos esperados

Ideal máximo de **5 arquivos de produto/teste**, além de `tasks.md`:

1. `apps/pipeline/schemas/llm1.py`
2. `apps/pipeline/llm1_service.py`
3. `apps/doctor/presenters.py`
4. `apps/pipeline/tests/test_llm1_service.py`
5. `apps/doctor/tests/test_presenter.py`

Se precisar de arquivo novo coeso, deve substituir — não simplesmente ampliar — esta lista ou justificar. Não tocar template se o presenter existente já entrega a informação.

## Arquivos proibidos

- `apps/cases/models.py`, migrations e FSM
- `apps/pipeline/policy/**`
- `apps/intake/**`, `apps/scheduler/**`
- templates de fila
- settings/dependencies

## TDD obrigatório

### RED mínimo

Adicionar testes que falhem antes da implementação:

1. schema aceita anticoagulante com evidência;
2. schema rejeita item sem evidência;
3. payload antigo omisso produz lista vazia;
4. prompt final contém regra explícita de medicamentos e não inferência;
5. presenter destaca anticoagulante;
6. presenter distingue suspenso de uso atual;
7. presenter sem medicamentos preserva relatório existente;
8. HTML-like em nome/evidência permanece texto normal escapável — presenter não gera markup seguro.

Comandos alvo sugeridos:

```bash
uv run pytest apps/pipeline/tests/test_llm1_service.py -q
uv run pytest apps/doctor/tests/test_presenter.py -q
```

### GREEN

Implementar apenas schema, instruções e projeção no presenter.

### REFACTOR

Centralizar labels/status em helpers pequenos se houver repetição. Não criar engine farmacológica.

## Checks de inspeção obrigatórios

```bash
rg -n "medications_described|medication_class|use_status|source_text_hint" \
  apps/pipeline/schemas/llm1.py apps/pipeline/llm1_service.py apps/doctor/presenters.py
rg -n "anticoagul|antiagreg|confirmar manejo|suspens" apps/doctor/presenters.py apps/doctor/tests/test_presenter.py
rg -n "medications_described|anticoagul|antiagreg" apps/pipeline/policy || true
rg -n "safe|mark_safe" apps/doctor/presenters.py

git diff --name-only "$BASE_REF"
git diff -- apps/cases apps/intake apps/scheduler apps/pipeline/policy config
```

Interpretar: policy/proibidos devem ter diff vazio; nenhum `safe/mark_safe`; texto não pode prometer suspensão.

## Critérios de sucesso binários

- [ ] R1–R5 possuem teste/inspeção.
- [ ] RED real registrado.
- [ ] Ausência de medicamentos é retrocompatível.
- [ ] Anticoagulante e antiagregante geram alerta.
- [ ] Status suspenso não aparece como atual.
- [ ] Nenhuma hard rule/conduta farmacológica foi criada.
- [ ] No máximo 5 arquivos de produto/teste, ou justificativa aprovada.
- [ ] Baseline e quality gate completos atendem comparação.
- [ ] Relatório existe e é verificável.

## Gates de autoavaliação

1. Qual teste prova que o LLM não pode devolver medicamento sem evidência?
2. Qual teste prova compatibilidade de payload antigo?
3. Onde o alerta aparece e por que é proeminente?
4. Há qualquer leitura de medicamento na policy? A resposta esperada é não.
5. Algum texto recomenda suspensão/dose/janela? A resposta esperada é não.
6. A reconstrução gerencial reutiliza o presenter sem regra duplicada?
7. Quais arquivos foram tocados e por quê?
8. `passed_final >= passed_baseline`, zero failures/errors, exit 0?

### Condições automáticas de INCOMPLETO

- baseline ausente/falhando;
- RED não comprovado;
- item sem evidência aceito;
- medicamento inferido sem texto explícito;
- policy/decisão alterada por medicamento;
- instrução de suspensão/dose criada;
- payload antigo passa a falhar;
- arquivo proibido alterado;
- requisito sem teste/inspeção;
- gate completo ausente/falhando;
- final com exit != 0, failure/error ou menos passed que baseline;
- relatório sem snippets/comandos/handoff;
- `tasks.md` marcado ou commit/push com pendência.

## Relatório markdown temporário obrigatório

Criar exatamente:

```text
/tmp/introduce-colonoscopy-exam-workflow-slice-001-report.md
```

Incluir: Status COMPLETE/INCOMPLETE; BASE_REF/branch/status; matriz requisito-arquivo-teste; baseline; RED; GREEN; REFACTOR; snippets antes/depois; inspeções e interpretação; baseline vs final; quality gate com exit codes; respostas aos gates; `git diff --name-only`; justificativas; commit; e **Handoff para verificador** com arquivos, requisitos R1–R5, riscos e comandos exatos para rerun.

## Prompt pronto para implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md and all artifacts listed in the handoff of openspec/changes/introduce-colonoscopy-exam-workflow/slices/slice-001-medication-safety-alert.md. Implement ONLY Slice 001 on branch feature/colonoscopy-exam-workflow.

Follow the DeepSeek4-Flash protocol literally: clean branch/status and BASE_REF, full pytest baseline before editing, real RED tests first, minimal GREEN, narrow REFACTOR with clean code/DRY/YAGNI, all rg/diff inspections, exact full quality gate and baseline-vs-final comparison. Any missing/failing item means INCOMPLETE: do not update tasks.md and do not commit/push.

Add strict structured medications_described extraction with explicit evidence and an informative doctor-report alert for anticoagulants/antiplatelets. Preserve old payloads with an empty default. Do not change policy, models, migrations, FSM, queues or add pharmacological suspension/decision rules. Keep the slice within the expected files unless the report proves a blocker.

Create /tmp/introduce-colonoscopy-exam-workflow-slice-001-report.md with RED/GREEN evidence, before/after snippets, quality gate, rerun commands and Handoff para verificador. Only after all gates pass, mark only Slice 001, commit, push, reply REPORT_PATH=/tmp/introduce-colonoscopy-exam-workflow-slice-001-report.md and STOP.
```
