# Slice 007: Pipeline executa somente v2 e prompts neutros

## Handoff com contexto zero

Leia `AGENTS.md`, `PROJECT_CONTEXT.md`, todos os artefatos deste change, a ADR-0004, os relatórios aprovados 001–006 e o relatório bloqueado `/tmp/support-combined-eda-colonoscopy-workflow-slice-007-report.md`. Inspecione especialmente:

- `apps/pipeline/orchestrator.py` e testes de `run_pipeline`;
- `apps/cases/exam_profiles.py`;
- `apps/llm/management/commands/seed_prompts.py`;
- `apps/admin_ui/forms.py` e testes de prompts;
- serviços/schemas 1.1, apenas para separar execução nova de leitura histórica.

### Estado e fluxo entregue

O gate do plano anterior encontrou mais de 50 arquivos potenciais e bloqueou corretamente o cutover monolítico antes de editar. Este slice é a primeira parte do redimensionamento: entrega somente o corte executável de pipeline/prompts.

```text
Case com projeção declarada explícita
→ run_pipeline sempre usa LLM1/LLM2 v2
→ resolve somente exam_llm1/2_system/user
→ seed mantém exatamente os quatro nomes neutros ativos
→ oito nomes antigos ficam inativos e preservados no histórico
```

A coluna `Case.exam_type`, o dual-write e fallbacks de filas permanecem temporariamente para os Slices 008–011. Não os remova aqui.

## Protocolo obrigatório para implementador DeepSeek4-Flash

**Se qualquer item falhar, marque INCOMPLETO: não atualize `tasks.md`, não faça commit/push e reporte bloqueio com evidência.**

1. Confirme branch exata, árvore limpa e ADR-0004 aceita; registre `BASE_REF`.
2. Registre matriz requisito → arquivo(s) → teste(s) e rode `uv run pytest` antes de editar. Baseline com failure/error bloqueia.
3. Faça inventário dos oito nomes antigos e do branch 1.1 do orchestrator; classifique módulos 1.1 de leitura histórica versus dispatch executável.
4. Escreva testes primeiro e prove RED real.
5. Faça GREEN mínimo somente para R1–R5; não migre filas, coluna ou documentação operacional.
6. REFACTOR local com clean code, DRY e YAGNI; remova imports/funções mortos do orchestrator, não artefatos históricos necessários.
7. Execute todas as inspeções e o quality gate completo; pytest final deve ter exit 0, zero failures/errors e `passed_final >= passed_baseline`.
8. Gere relatório factual, marque apenas o Slice 007, commit/push e PARE.

**Cap: 12 arquivos produto/teste.** Acima do cap, pare antes de editar e peça revisão. Exclusões de arquivos mortos contam no cap.

## Requisitos

### R1. Pipeline novo é exclusivamente v2 e fail-closed

`run_pipeline` não escolhe mais entre 1.1 e 2.0 por presença de rows. Todo job novo usa `_run_v2_pipeline`. Caso sem 1–2 procedimentos declarados válidos falha de modo explícito/auditável; nunca cai em EDA, prompt 1.1 ou perfil singular.

### R2. Dispatch legado sai do caminho executável

Remover do orchestrator imports, branch, helpers e fallback que executam LLM1/LLM2 1.1 ou resolvem os oito nomes antigos. `exam_profiles` mantém somente diferenças de policy/presenter realmente usadas; campos de nomes de prompts antigos saem.

Serviços/schemas/adapters 1.1 podem permanecer para testes unitários, leitura histórica e bridge excepcional, mas nenhum deles pode ser importado/chamado pelo orchestrator de novos jobs. Não reescrever JSON 1.1.

### R3. Quatro prompts neutros são canônicos

Seed/admin aceitam somente:

- `exam_llm1_system`;
- `exam_llm1_user`;
- `exam_llm2_system`;
- `exam_llm2_user`.

Fallback do orchestrator também contém somente esses quatro nomes. O seed é idempotente e garante exatamente uma versão ativa por nome neutro.

### R4. Prompts antigos ficam inativos, não apagados

Ao rodar o seed final, toda versão ativa dos oito nomes antigos é desativada. Linhas e versões históricas permanecem consultáveis. Rodar o comando novamente não cria versões extras nem reativa nome antigo.

### R5. Regressão do pipeline v2

EDA, Colonoscopia e combinado continuam com uma chamada por estágio, reconciliação/policy por componente e chegada ao médico. Testes antigos de `run_pipeline` devem criar `CaseProcedure` explicitamente e validar v2; não preservar o branch 1.1 apenas para manter fixture verde.

## Arquivos esperados

Produto esperado:

- `apps/pipeline/orchestrator.py`;
- `apps/cases/exam_profiles.py`;
- `apps/llm/management/commands/seed_prompts.py`;
- `apps/admin_ui/forms.py`.

Testes esperados, somente os necessários: `test_orchestrator.py`, `test_colonoscopy_pipeline.py`, testes Slice 002 de pipeline/contrato, `test_seed_prompts.py` e teste de admin de prompts. Justifique qualquer extra.

Proibido: models/migrations, intake/doctor/scheduler/dashboard, templates/JS, FSM/roles, docs/runbook e remoção da coluna.

## TDD obrigatório

### RED

Adicionar/ajustar testes que falhem porque: caso sem projeção ainda entra em 1.1; orchestrator ainda importa/resolve nomes antigos; seed mantém 12 nomes ativos; admin oferece nomes antigos; fixtures de `run_pipeline` ainda dependem da coluna.

### GREEN

Implementar o menor corte que torne v2 único, desative prompts antigos preservando histórico e mantenha os três fluxos v2 verdes.

### REFACTOR

Remover código morto apenas do dispatch executável, dar nomes explícitos à validação da projeção e evitar duplicar listas de nomes neutros/legados sem necessidade. Não apagar parser/schema 1.1.

## Checks de inspeção obrigatórios

```bash
rg -n "_uses_v2_pipeline|_run_llm1_step|_run_scope_and_llm2|Llm1Service|Llm2Service|classify_exam_scope" apps/pipeline/orchestrator.py apps/pipeline/tests
rg -n "colonoscopy_llm[12]_(system|user)|\bllm[12]_(system|user)\b" apps/cases/exam_profiles.py apps/pipeline/orchestrator.py apps/llm/management/commands/seed_prompts.py apps/admin_ui/forms.py
rg -n "exam_llm[12]_(system|user)" apps/pipeline/orchestrator.py apps/llm/management/commands/seed_prompts.py apps/admin_ui/forms.py apps/**/tests
rg -n "schema_version.*1\.1|preop_screening|structured_data" apps/pipeline/schemas apps/pipeline/json_parser.py apps/doctor/presenters.py
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
openspec validate support-combined-eda-colonoscopy-workflow --strict
git diff --check
git diff --name-only "$BASE_REF"
```

Interprete cada ocorrência antiga: caminho executável é erro; módulo/adaptador histórico sem import no orchestrator pode ser legítimo.

## Critérios binários e gates

- [ ] R1–R5 comprovados por testes e inspeção.
- [ ] Nenhum branch 1.1 no `run_pipeline`.
- [ ] Caso sem projeção falha sem default EDA.
- [ ] Somente quatro nomes neutros em seed/admin/fallback novo.
- [ ] Oito nomes antigos inativos e histórico preservado.
- [ ] EDA/Colon/combinado v2 regressam.
- [ ] Nenhuma alteração de coluna/fila/docs.
- [ ] Cap e todos os gates passam.

Responder no relatório:

1. Qual teste prova que `run_pipeline` nunca cai em 1.1?
2. Como caso sem rows falha?
3. Quais referências 1.1 restaram e por que são apenas históricas?
4. Como seed prova uma ativa por nome neutro e zero ativa por nome antigo?
5. Como histórico de prompt foi preservado?
6. Quais fixtures de pipeline passaram a criar rows?
7. Quais arquivos mudaram e por quê?
8. Qual foi a comparação baseline-final?

### Condições automáticas de INCOMPLETO

Branch 1.1 ainda executável; fallback EDA; nome antigo em dispatch/profile/seed/admin; prompt antigo ativo ou apagado; mais de uma versão neutra ativa; fixture mascara ausência com signal/default; JSON 1.1 quebrado; coluna/fila/docs alteradas; cap excedido sem revisão; teste/gate falha; pytest final menor que baseline; relatório ausente.

## Relatório obrigatório

Criar `/tmp/support-combined-eda-colonoscopy-workflow-slice-007-report.md` com Status, matriz, branch/BASE_REF, baseline, RED/GREEN/REFACTOR, snippets antes/depois, inventário de nomes/dispatch, inspeções interpretadas, diff/cap, quality gate, comparação pytest e respostas aos gates.

Incluir **Handoff para verificador**: arquivos alterados, comandos de rerun, riscos/limitações e checklist R1–R5.

## Prompt pronto

```text
Read AGENTS.md, PROJECT_CONTEXT.md, all change artifacts, accepted ADR-0004, approved reports 001-006 and the blocked Slice 007 report. Implement ONLY the resized Slice 007 on the required branch. Follow its DeepSeek4-Flash protocol: clean baseline, real RED, minimal GREEN, local REFACTOR, inspections, full quality gate and evidence report.

Make run_pipeline exclusively procedure-neutral v2 and fail closed without explicit declared CaseProcedure rows. Remove legacy 1.1 execution and old prompt-name dispatch from orchestrator/profiles. Keep only four neutral names in seed/admin/fallback; deactivate all active legacy versions idempotently without deleting history. Preserve 1.1 readers/schemas strictly for historical compatibility. Do not touch models/migrations, operational queue consumers or rollout docs. If cap >12 or any gate fails, report INCOMPLETE without task/commit/push.

Create /tmp/support-combined-eda-colonoscopy-workflow-slice-007-report.md; if complete mark only Slice 007, commit, push, reply REPORT_PATH and STOP.
```
