# Slice 008: Operação ativa e reverte o fluxo combinado com segurança

## Handoff com contexto zero

Leia todos os artefatos/ADR/relatórios 001–007, runbook anterior `docs/deploy/introduce-colonoscopy-exam-workflow.md`, Compose/settings/migrations/prompts finais, manual oficial e `PROJECT_CONTEXT.md`.

### Fluxo entregue

```text
Operação faz backup verificado
→ drena estados LLM incompatíveis
→ para writers
→ aplica migrations com imagem nova
→ ativa quatro prompts neutros verificados
→ sobe imagem nova com flag inicialmente false
→ smoke EDA/Colon/Combinado
→ ativa flag no web
→ monitora upgrade/decisões/agendas
```

Rollback preferencial mantém imagem nova e desliga intake; imagem antiga exige bridge executável de `exam_type` a partir de CaseProcedure e nunca recebe combinado em voo.

## Protocolo obrigatório para implementador DeepSeek4-Flash

**Passo não executável, assert humano-only, alegação sem teste ou qualquer falha = INCOMPLETO; não marque task, não faça commit/push.**

1. Confirme branch, árvore limpa, ADR-0004 e registre BASE_REF.
2. Registre matriz requisito→arquivo→teste e rode pytest completo antes de editar; baseline falho bloqueia.
3. Escreva testes documentais/browserless primeiro e prove RED real.
4. Faça GREEN mínimo somente em docs/testes de contrato.
5. REFACTOR docs/testes com clean code, DRY, YAGNI e blocos shell autocontidos.
6. Execute/interprete inspeções e um verificador independente temporário.
7. Rode ruff check, format check, mypy, pytest, OpenSpec strict e diff check; exit 0, zero failures/errors e passed final >= baseline.
8. Gere relatório factual com comandos/exit codes, snippets antes/depois e Handoff para verificador.
9. Só então marque Slice 008/DoD verdadeiro, commit normal, push, responda REPORT_PATH e PARE.

**Cap: 8 arquivos produto/teste/docs.** Não alterar regras de negócio neste slice.

### Quality gate obrigatório

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
```

## Requisitos

### R1. Runbook CRITICAL e paths reais

Documentar risco, pré-requisitos, janela de manutenção/downtime, comandos Compose com `--project-directory`/arquivos absolutos conforme padrão e volume real `media_prod`. Não prometer zero downtime.

### R2. Backup fail-closed

Dump PostgreSQL com `set -euo pipefail`/falha propagada, marker + mínimo de conteúdo, gzip integrity. Tar media resolve volume real, valida arquivo e mínimo de entradas. Falha executa exit não zero antes de migrations.

### R3. Preflight de dados/estados

Queries machine-readable verificam: nenhum Case sem 1–2 CaseProcedure; nenhuma duplicata; combinações válidas; estados `LLM_STRUCT/LLM_SUGGEST` drenados ou listados para tratamento; quatro prompts neutros ativos exatamente uma versão; flag false. Assert mismatch termina não zero.

### R4. Deploy serializado

Build/pull imagem nova; parar `web worker pdf_worker`; migration/check/seed usando imagem nova; verificar ausência de coluna legada, constraints/rows/prompts; subir somente imagem nova `--force-recreate`; smoke com flag false; ativar flag apenas no web após EDA, Colon e combinado completos. Workers não recebem/consultam flag.

### R5. Smoke e monitoramento

Checklist prova: EDA simples, Colon simples, combinado declarado, auto-upgrade, combined→single volta NIR, decisão parcial/inclusão, uma agenda casada, resposta NIR, dashboard 1 case/2 components. Consultas/eventos sem expor texto clínico.

### R6. Rollback preferencial

Desligar flag/recriar web, manter imagem nova/schema, drenar casos e preservar prompts neutros enquanto houver v2 em voo. Não apagar CaseProcedure/JSON/prompt history.

### R7. Bridge para imagem antiga

Exceção exige writers parados, ausência comprovada de casos combinados/incompatíveis em voo e SQL/script fail-fast que recria `exam_type`, backfilla somente seleção única inequívoca, recusa `eda_colonoscopy`/ambiguidade e usa `psql -v ON_ERROR_STOP=1`, `-At` e asserts binários antes de subir old writers. Forward: build new → stop old → migrations/drop bridge → assert schema → up new. Cada bloco tem `set -euo pipefail` próprio.

### R8. Manual/contexto/ADR/specs

Atualizar manual com intake combinado, upgrade, decisão por componente, agendamento casado e resposta final; PROJECT_CONTEXT com schema v2/model/semântica de filtros; ADR-0003 superseded-in-part por ADR-0004; docs index. Não alterar OpenSpec para mascarar implementação divergente.

### R9. Contratos automatizados

Testes documentais provam comandos/ordem/asserts/volume/prompts/flag/bridge e ausência de claims inseguros. Verificador browserless ou parser independente temporário deve validar pelo menos ordem deploy, flag web-only, bridge fail-fast e smoke matrix.

## Arquivos esperados

- novo runbook ou evolução explícita em `docs/deploy/`;
- `docs/deploy/README.md`;
- `docs/manual/manual-usuarios.md`;
- `PROJECT_CONTEXT.md`;
- ADR-0003/ADR-0004 somente status/links se necessário;
- até dois testes de contrato documental.

Proibido apps/models/migrations/settings/Compose/pipeline/prompts/FSM/queries de dashboard. Se documentação revelar bug de código, PARE e reporte; não corrija escondido.

## TDD RED mínimo

Testes devem falhar antes por ausência de:

1. backup pipefail/content/tar asserts;
2. preflight rows/duplicates/states/prompts;
3. stop all writers before migration;
4. verify schema/prompts before up;
5. flag somente web e ativação pós-smoke;
6. smoke matrix completa;
7. preferred rollback preserves new image/data/prompts;
8. old-image bridge refuses combined/ambiguous and asserts binary;
9. safe forward ordering;
10. manual/context/ADR links.

## Inspeções obrigatórias

```bash
rg -n "set -euo pipefail|ON_ERROR_STOP=1|-At|exit 1|pipefail|gzip -t|tar -tzf" docs/deploy
rg -n "media_prod|--project-directory|docker compose|stop web worker pdf_worker|up -d --force-recreate" docs/deploy
rg -n "exam_llm1_system|exam_llm1_user|exam_llm2_system|exam_llm2_user" docs/deploy PROJECT_CONTEXT.md
rg -n "LLM_STRUCT|LLM_SUGGEST|CaseProcedure|duplic|1.*2|combined|eda_colonoscopy" docs/deploy
rg -n "COLONOSCOPY_INTAKE_ENABLED" docker-compose*.yml config apps docs/deploy
rg -n "Agendamento casado|upgrade automático|Solicitado|Detectado|Autorizado" docs/manual PROJECT_CONTEXT.md
rg -n "zero downtime|sem impacto|não há risco" docs/deploy || true
openspec validate support-combined-eda-colonoscopy-workflow --strict
git diff --check

git diff --name-only "$BASE_REF"
git diff -- apps config docker-compose.yml docker-compose.*.yml
```

## Critérios/gates

- [ ] R1–R9 provados.
- [ ] Runbook executável/fail-fast, não comentários esperados.
- [ ] Deploy/rollback/forward serializados.
- [ ] Bridge recusa combinado e ambiguidade.
- [ ] Flag web-only e prompts preservados em voo.
- [ ] Manual/contexto/ADRs alinhados.
- [ ] Apps/infra sem diff.
- [ ] ≤8 arquivos, gates e relatório completos.

## Gates de autoavaliação

Responder no relatório:

1. Quais asserts tornam backup DB/media fail-closed?
2. Como preflight prova rows, duplicatas, estados e prompts?
3. Qual é a ordem executável do deploy e onde writers param?
4. Qual smoke cobre todos os fluxos críticos?
5. Como rollback preferencial preserva imagem/dados/prompts?
6. Como bridge recusa combinado/ambiguidade e falha binariamente?
7. Qual é a ordem segura do forward?
8. Como lifecycle da flag/prompts trata casos em voo?
9. Quais links/manual/contexto/ADRs foram alinhados?
10. Quais arquivos mudaram e qual a comparação baseline-final?

### Condições automáticas de INCOMPLETO

Protocolo ausente; comando depende de shell anterior; pipeline backup fail-open; assert é só comentário/SELECT visual; writer antigo ativo em migration/bridge; flag em worker; prompt v2 desativado com caso em voo; rollback destrutivo; bridge converte combinado silenciosamente; old image sobe antes de assert; forward drop antes de stop; zero-downtime claim; bug de código corrigido fora de escopo; app/Compose/settings alterado; >8 sem revisão; gate falha/passed menor; relatório ausente.

## Relatório obrigatório

Criar `/tmp/support-combined-eda-colonoscopy-workflow-slice-008-report.md` com Status, matriz requisito→arquivo→teste, branch/BASE_REF/baseline, RED/GREEN/REFACTOR, snippets antes/depois de cada bloco crítico, inspeções interpretadas, parser/verificador independente e comandos de rerun, diff/cap, quality gate completo, comparação pytest e respostas aos gates.

Incluir **Handoff para verificador** com arquivos alterados, comandos exatos de rerun, riscos/limitações e checklist R1–R9.

## Prompt pronto

```text
Read all artifacts, accepted ADR-0004, approved reports 001-007, final code/schema/prompts and the prior colonoscopy runbook. Implement ONLY Slice 008 documentation/contracts on the required branch. Follow the DeepSeek4-Flash protocol exactly. Any non-executable/human-only assert, unsafe order, missing test, code/infra diff, failing gate or cap violation means INCOMPLETE and no tasks/commit/push.

Produce a CRITICAL fail-closed rollout: verified DB/media backups, machine-readable projection/state/prompt preflight, new-image serialized migration with all writers stopped, flag-false smoke matrix then web-only activation, monitoring, preferred new-image rollback, and an exceptional old-image bridge that refuses combined/ambiguous rows and uses independent fail-fast binary asserts in rollback and forward. Align manual, context and ADR links; add adversarial doc tests and independent verifier. Do not change business code, models, migrations, settings, Compose, pipeline, prompts or dashboard formulas.

Create /tmp/support-combined-eda-colonoscopy-workflow-slice-008-report.md; if complete mark only Slice 008/true DoD items, commit, push, reply REPORT_PATH and STOP.
```
