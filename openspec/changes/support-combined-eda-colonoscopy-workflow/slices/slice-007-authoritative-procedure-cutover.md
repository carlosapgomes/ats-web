# Slice 007: Cutover remove fonte única e prompts específicos legados

## Handoff com contexto zero

Leia todos os artefatos/ADR/relatórios 001–006, código inteiro via buscas abaixo, migrations 0014+ e:

- `apps/cases/models.py`, migrations, helpers/services/querysets;
- fixtures/factories/test helpers;
- `apps/cases/exam_profiles.py`;
- `apps/pipeline` e prompt seed/admin;
- todos os usos de `exam_type`, nomes de prompts EDA/Colon e `get_exam_type_display`.

### Fluxo entregue

Até agora `Case.exam_type` e prompts específicos formam ponte interna. Este slice torna a arquitetura final autoritativa:

```text
todos os readers/writers usam CaseProcedure
→ migration remove Case.exam_type
→ dual-write desaparece
→ quatro prompts neutros são os únicos usados por novos jobs
→ fixtures não têm default silencioso
→ toda suite passa sem compatibilidade operacional antiga
```

Não é opcional deixar resíduos como dívida.

## Protocolo obrigatório para implementador DeepSeek4-Flash

**Falha ou resíduo não classificado = INCOMPLETO; não marque task, não faça commit/push e reporte bloqueio com evidência.**

1. Confirme branch, árvore limpa, ADR-0004 e registre BASE_REF.
2. Faça o inventário R1, registre matriz requisito→arquivo→teste e rode pytest completo antes de editar; baseline falho bloqueia.
3. Escreva testes primeiro e prove RED real da remoção/cutover.
4. Faça GREEN mínimo, sem docs/rollout do Slice 008.
5. REFACTOR local com clean code, DRY, YAGNI e remoção de código morto da ponte.
6. Execute/interprete todas as buscas globais e classifique cada resíduo.
7. Rode ruff check, format check, mypy, pytest, makemigrations check, OpenSpec strict e diff check; final exit 0, zero failures/errors e passed >= baseline.
8. Gere relatório factual com inventário antes/depois, snippets e Handoff para verificador.
9. Só então marque Slice 007, commit normal, push, responda REPORT_PATH e PARE.

**Cap: 14 arquivos produto/teste.** Se buscas revelarem footprint maior, PARE antes de editar e peça revisão; não faça remoção parcial.

### Quality gate obrigatório

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
```

## Requisitos

### R1. Inventário antes da edição

Registrar no relatório todas as ocorrências operacionais de `Case.exam_type`, `ExamType`, `get_exam_type_display`, `exam_type=` em queries/forms e oito prompt names antigos. Classificar cada ocorrência: migrar, compatibilidade histórica permitida ou falso positivo. Nenhuma ocorrência sem destino.

### R2. Remoção de fonte/ponte

Migration remove `Case.exam_type` após comprovar backfill/projeção válida para todo Case. Remover enum combinado transitório, dual-write e defaults. Caso sem procedimento válido deve fazer migration falhar, não inventar EDA.

### R3. Readers/queries finais

Todo intake, pipeline, doctor, CHD, NIR e dashboard usa helpers/querysets por dimensão. Templates usam dados projetados. Nenhum filtro usa substring/label para inferir conjunto.

### R4. Prompt cutover

Novos jobs resolvem somente quatro nomes neutros. Seed/admin/fallback continuam idempotentes. Oito templates antigos não são deletados do banco/histórico; podem permanecer reconhecíveis apenas para leitura/rollback, nunca dispatch novo.

### R5. Fixtures e APIs explícitas

Factories/test helpers criam procedures explicitamente. Não esconder ausência com signal/default automático amplo. `Case` isolado inválido deve falhar no boundary de domínio adequado, respeitando migration/admin cases documentados.

### R6. Compatibilidade legítima

Schema JSON 1.1 e eventos/payloads históricos com chave `exam_type` continuam legíveis. A busca global pode encontrar essas referências apenas em adapters/testes/documentação histórica claramente identificados; isso não é reader da coluna removida.

### R7. No schema drift

`makemigrations --check --dry-run` sem mudanças após migration criada. Índices/constraints CaseProcedure adequados às queries verificadas. Nenhuma migration destrói CaseEvent/JSON/PDF/agenda.

## Arquivos esperados

Migration/model/service/query helper, consumers residuais identificados, prompt seed/admin/orchestrator e testes de migration/contrato. Cap 14; alteração puramente mecânica repetida deve ser consolidada, não escondida.

Proibido nova funcionalidade, UI redesign, FSM/roles, docs rollout (Slice008), CPRE, reset de banco.

## TDD RED mínimo

1. migration falha se Case não tem projeção válida;
2. migration remove coluna e preserva rows/dados;
3. Case combinado continua todos os fluxos após remoção;
4. nenhum query/form depende de exam_type;
5. novos jobs usam só prompts neutros;
6. prompts antigos preservados como histórico, não dispatch;
7. factories explícitas e boundary inválido;
8. legacy JSON/event payload renderiza;
9. filas/filtros/analytics regressam;
10. makemigrations check.

## Inspeções obrigatórias

```bash
rg -n "Case\.exam_type|case\.exam_type|self\.exam_type|get_exam_type_display|ExamType|exam_type=" apps config templates static tests
rg -n "colonoscopy_llm[12]_(system|user)|\bllm[12]_(system|user)\b" apps tests
rg -n "exam_llm[12]_(system|user)" apps tests
rg -n "eda_colonoscopy" apps templates static tests
rg -n "CaseProcedure|declared_by_nir|detection_status|doctor_disposition" apps
rg -n "schema_version.*1\.1|declared_exam_type|detected_exam_type|exam_type" apps/pipeline apps/doctor apps/intake tests
uv run python manage.py makemigrations --check --dry-run --settings=config.settings.test
openspec validate support-combined-eda-colonoscopy-workflow --strict
git diff --check

git diff --name-only "$BASE_REF"
```

Para cada ocorrência residual, listar path/linha/classificação. Ocorrência operacional não justificada = INCOMPLETO.

## Critérios/gates

- [ ] R1–R7 provados.
- [ ] Coluna/enum/dual-write removidos.
- [ ] Nenhum reader/query operacional residual.
- [ ] Prompts neutros exclusivos para novos jobs.
- [ ] Legacy JSON/eventos legíveis.
- [ ] Migration fail-closed/preservadora.
- [ ] makemigrations/OpenSpec/diff/gates verdes.
- [ ] ≤14 ou revisão prévia.

## Gates de autoavaliação

Responder no relatório:

1. Qual inventário antes/depois comprova remoção completa?
2. Qual teste torna migration fail-closed para projeção inválida?
3. Quais resíduos `exam_type` são históricos e por que são aceitos?
4. Como dispatch prova uso exclusivo de prompts neutros?
5. Como fixtures deixaram de depender de default silencioso?
6. Qual teste preserva JSON/eventos legados?
7. Como migration preserva todos os demais dados?
8. Quais arquivos mudaram e por quê?
9. Qual a comparação baseline-final com zero failures/errors?

### Condições automáticas de INCOMPLETO

Inventário ausente; qualquer reader/write/query residual da coluna; migration inventa EDA, perde dados ou permite Case sem rows; dual-write/default permanece; job novo usa prompt antigo; prompt histórico apagado; JSON 1.1 quebra; fixture oculta ausência; schema drift; cap excedido sem revisão; gate/teste falha; passed menor; relatório ausente.

## Relatório obrigatório

Criar `/tmp/support-combined-eda-colonoscopy-workflow-slice-007-report.md` com Status, inventário tabular antes/depois, matriz requisito→arquivo→teste, branch/BASE_REF/baseline, RED/GREEN/REFACTOR, snippets antes/depois de model/migration/dispatch/factory/adapter, todas as ocorrências residuais classificadas, inspeções, gates extras, diff/cap, comparação pytest e respostas aos gates.

Incluir **Handoff para verificador** com arquivos alterados, comandos exatos de rerun, riscos/limitações e checklist R1–R7.

## Prompt pronto

```text
Read all artifacts, accepted ADR-0004, approved reports 001-006 and perform the mandatory global inventory before editing. Implement ONLY Slice 007. Follow the DeepSeek4-Flash protocol and cap strictly; if footprint exceeds 14, stop for planner review rather than partial cutover.

Remove Case.exam_type and every operational dependency/dual-write only after fail-closed migration validation; make CaseProcedure authoritative across all readers/queries; use only four neutral prompts for new jobs while retaining old prompt history; make fixtures explicit; preserve schema 1.1/event payload readers. Run full gates plus makemigrations/OpenSpec/diff. Any unexplained residual or failing evidence means INCOMPLETE and no tasks/commit/push.

Create /tmp/support-combined-eda-colonoscopy-workflow-slice-007-report.md; if complete mark only Slice 007, commit, push, reply REPORT_PATH and STOP.
```
