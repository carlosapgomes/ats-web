# S1 — Artefato não persistível termina em falha auditada ou job failure real

## 1. Identity

- Slice: S1 / 001.
- Change: `confirm-nir-procedure-review-and-harden-pipeline`.
- Task: `../tasks.md` 1.1. Primeiro slice; sem dependência de S2/autoridade humana.

## 2. Objective

Entregar o fluxo resultado LLM inválido → rejeição antes de writes → erro seguro visível/FAILED, ou exceção verdadeira no worker quando a auditoria também falhar, eliminando o órfão observado em 5074806.

## 3. Read first

- `AGENTS.md`, `PROJECT_CONTEXT.md`, `openspec/config.yaml`.
- Proposal, `evidence.md`, design D7–D9 e Migration Plan desta change.
- `specs/procedure-neutral-analysis/spec.md` desta change: os dois requisitos ADDED de persistibilidade/falha.
- `apps/pipeline/orchestrator.py`, `apps/pipeline/tasks.py`, `apps/cases/models.py` (FSM), `apps/cases/signals.py`.
- `apps/pipeline/tests/test_orchestrator.py`, `test_v4_existing_workflow.py`, `test_llm2_service_v4.py`.
- `openspec/changes/llm2-v4-echo-nonfatal-overwrite/specs/procedure-neutral-analysis/spec.md`: rc.10 existente, não regredir.

## 4. Requirements → evidence

| ID | Comportamento verificável | Evidência planejada |
| --- | --- | --- |
| R1 | Rejeitar U+0000 decodificado em strings/chaves/listas/dicts/summary, sem modificar string literal barra-u-0000 | Teste recursivo sintético positivo/negativo e erro técnico limitado |
| R2 | LLM1 verificado antes de projeção/artefato; LLM2 antes de recomendação/WAIT_DOCTOR | E2E clients fake com NUL nos dois estágios; asserts de ausência de writes indevidos |
| R3 | Falha real de save com objeto contaminado registra PIPELINE_FAILED seguro e transição FSM pelo estado persistido | Teste PostgreSQL/injeção no save e assertions do DB + timeline label; sem raw/excerpt |
| R4 | Se persistir o desfecho de falha também falha, exceção sai de run_pipeline e execute_pipeline | Fault-injection com pytest.raises na fronteira task; quando viável task sync real confirmando job failure |
| R5 | Estado já avançado não regride, não atribuir status diretamente; preservar artefatos/eventos válidos anteriores | Teste stale instance / estado persistido WAIT_DOCTOR ou CLEANED |
| R6 | Regressores rc.10 preservados; logs de erro não despejam SQL/raw clínico; sem novo retry LLM | caplog com marcador clínico sintético proibido e suítes existentes |

## 5. Expected blast radius

Prováveis: novo `apps/pipeline/persistability.py` (ou helper puro equivalente), `apps/pipeline/orchestrator.py`, novo `apps/pipeline/tests/test_persistable_pipeline_output.py`, testes de orchestrator/rc.10 e, somente se necessário para provar task failure, `apps/pipeline/tasks.py`/teste dedicado. `models.py`/signals são leitura, não previsão de mudança de FSM.

Superfícies sensíveis fora de escopo: NIR/card, autoridade humana, detector, schemas externos/prompts/seed, catálogo/matriz, Q_CLUSTER, migrations, estados FSM, operação de produção. Qualquer arquivo adicional deve ter motivo concreto no relatório; mudança de política/estado exige escalada.

## 6. Failing-before plan

TDD RED → GREEN → REFACTOR obrigatório.

Criar primeiro `test_persistable_pipeline_output.py` com fixtures LLM válidas contendo NUL aninhado e marcador clínico sintético. Executar contra baseline:

```sh
uv run pytest apps/pipeline/tests/test_persistable_pipeline_output.py -q
```

Falhas esperadas: guard ausente; save contaminado deixa LLM_STRUCT sem PIPELINE_FAILED; erro secundário é engolido e task retorna None; log pode conter CONTEXT rejeitado. Mostrar assertions do comportamento, não apenas ImportError de helper novo. Após teste comportamental falhar, adicionar testes unitários do helper.

Teste deve usar PostgreSQL do ambiente isolado definido no projeto. Nunca mockar o sucesso do save que é precisamente o alvo. Fault-injection separado pode modelar falha secundária; registrar qual cenário é real versus simulado.

## 7. Implementation constraints

- Implementar somente D7; não preparar infraestrutura de confirmação S2.
- Rejeitar, não remover/sanitizar conteúdo clínico silenciosamente.
- Guard na fronteira orchestrator também com cliente injetado; não depender só de provider/JSON parser.
- Recarregar estado limpo, sem refresh_from_db do FSM protegido; usar transições existentes/estado persistido, nunca save completo do dado inválido.
- Mensagem/código técnicos seguros e limitados; não stringificar exceção DB com texto clínico como payload/log.
- Task cujo desfecho técnico é FAILED auditado pode manter retorno atual; se o desfecho não persiste, erro deve sair. Não aumentar retries, não recuperar FAILED automaticamente.
- Follow the repository engineering policy in AGENTS.md and preserve existing conventions. Prefer the smallest correct change; avoid speculative abstraction and unrelated refactoring.

## 8. Validation

**Focused:**
```sh
uv run pytest apps/pipeline/tests/test_persistable_pipeline_output.py apps/pipeline/tests/test_orchestrator.py apps/pipeline/tests/test_v4_existing_workflow.py apps/pipeline/tests/test_llm2_service_v4.py -q
uv run pytest apps/pipeline/tests/ -q
```

Usar env da base de teste realmente disponível (porta definida pelo owner/config; não assumir produção). Guardar comandos exatos.

**Project-required gates:** AGENTS.md §2/DoD; exceção/falha de infra é BLOCKED com evidência, não teste aprovado.

**Runtime/verification:** fixture sintética via pipeline em banco de teste gera evento PIPELINE_FAILED e Case FAILED; render SSR do detalhe autorizado reconhece label de falha. Job fronteira propaga fault-injection. Sem chamadas LLM/recovery em eon. Se template não exibir stage/código, não ampliar para UX de falhas geral; evento técnico é obrigatório e label atual deve funcionar.

## 9. Acceptance criteria

- [ ] R1 e R2: NUL detectado antes dos writes; literal preservado; dois estágios cobertos.
- [ ] R3: persistência defeituosa não impede desfecho auditável com instância limpa.
- [ ] R4: falha no handler não retorna sucesso na fronteira task.
- [ ] R5: estado avançado não regredido e histórico não reescrito.
- [ ] R6: log seguro, rc.10/retries existentes preservados.
- [ ] Evidência RED e GREEN, gates e relatório disponíveis; sem código de S2.

## 10. Escalation conditions

Retornar **BLOCKED_NEEDS_DECISION** se precisar de migration/FSM nova, normalização clínica destrutiva, provider retry adicional, redesign global de jobs ou mudança de contrato fora de D7. Também escalar contradição spec/design, impossibilidade de provar falha secundária, implicação de segurança/privacidade nova ou expansão material não justificada. Falta de PostgreSQL de teste bloqueia evidência de persistência; não usar banco de produção como substituto.

## 11. Evidence report

`/tmp/sirhosp-slice-001-report.md` (path canônico do skill solicitado).

Status READY_FOR_REVIEW ou BLOCKED_NEEDS_DECISION; R1–R6 → evidência; arquivos; RED/GREEN; comandos/exit status; runtime real versus simulado; expansão de escopo; riscos e decisões humanas. Incluir snippets pequenos antes/depois conforme AGENTS.md, sem duplicar diff completo nem dados clínicos.

## 12. Worker handoff / prompt fresh

```text
Read AGENTS.md and PROJECT_CONTEXT.md first.
Implement ONLY S1 from openspec/changes/confirm-nir-procedure-review-and-harden-pipeline/slices/slice-001-persistable-output-and-auditable-failure.md.
Reconstruct context from Read first; treat this slice and referenced proposal/spec/design as the contract.
Produce behavioral RED evidence, implement the smallest safe change, REFACTOR, run focused/project-required validation and write /tmp/sirhosp-slice-001-report.md.
Do not update tasks.md, commit, push, merge, archive or start S2; owner/controller handles these steps under AGENTS.md after review.
Do not access/mutate production or call live LLMs to test.
If a new decision is needed, return BLOCKED_NEEDS_DECISION with evidence. Otherwise return READY_FOR_REVIEW and REPORT_PATH.
```

Handoff ao owner/reviewer: conferir sobretudo R3/R4 no código e testes, não aceitar só helper de detecção como entrega. Após aceite, owner cumpre controle/commit/push e pede confirmação explícita para S2.
