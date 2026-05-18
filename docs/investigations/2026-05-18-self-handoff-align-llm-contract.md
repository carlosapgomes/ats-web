# Self-Handoff — Alinhamento Contrato LLM e Roteamento NIR → Médico

Data: 2026-05-18

## Contexto Geral

Projeto atual: `/home/carlos/projects/ats-web/`

Projeto legado referência: `/home/carlos/projects/augmented-triage-system/`

O projeto atual é uma reimplementação Django SSR/PWA do legado Matrix. A interface Matrix desaparece; o backend Django deve intermediar o fluxo entre NIR, médico, agendador e gestor, preservando workflow, máquina de estados e regras clínicas do legado.

O usuário pediu investigação antes de corrigir equívocos da implementação inicial, especialmente no fluxo NIR → médico.

## Documentos Criados

### 1. Revisão inicial da migração

Criado:

`docs/investigations/2026-05-18-migration-initial-review.md`

Resumo:

- compara legado Matrix e Django atual;
- lista possíveis equívocos iniciais;
- aponta divergências em immediate flow, scope gate, role guard, resultado final, auditoria e cleanup.

### 2. Investigação NIR → Médico

Criado:

`docs/investigations/2026-05-18-nir-to-doctor-flow-review.md`

Esse é o documento central da investigação. O usuário leu e respondeu às perguntas dentro dele.

Principais achados registrados:

- Prompts atuais estavam errados semanticamente: falavam de “relatório de endoscopia” em vez de relatório/encaminhamento clínico de regulação solicitando EDA.
- Nomes de prompts divergiam:
  - pipeline/seed usavam `llm1_system_prompt`, etc.;
  - admin UI usava `llm1_system`, etc.;
  - legado usa `llm1_system`, `llm1_user`, `llm2_system`, `llm2_user`.
- Serviços LLM atuais não validam schemas Pydantic legados.
- No legado, `non_eda` e `unknown` NÃO vão para médico; vão direto ao NIR como revisão manual obrigatória.
- No Django atual, `non_eda`/`unknown` iam para `WAIT_DOCTOR`.
- Tela médica atual não replica relatório técnico em 7 blocos do legado.
- Views médicas usavam apenas `login_required`, sem `role_required("doctor")`.

Respostas do usuário registradas no documento:

1. Manter nomes legados de prompts: **sim**.
2. Para `non_eda`/`unknown`, usar opção A: **direto para `WAIT_R1_CLEANUP_THUMBS` com resultado de revisão manual**.
3. Validação Pydantic: usuário prefere portar literalmente. Perguntou se há risco/conflito.
4. Presenter médico: pode criar presenter Django equivalente, sem acoplar Matrix.
5. Prompts defaults legados devem existir como fallback e seed inicial.
6. Estratégia: planejar slices para outro LLM com contexto zero, handoff+prompt, TDD, clean code, slices enxutos, gates claros e relatório markdown obrigatório.

Resposta dada ao usuário sobre Pydantic:

- Não há conflito relevante.
- O legado usa Pydantic v2, compatível com Python moderno.
- O `uv.lock` já contém `pydantic`, mas `pyproject.toml` não declara dependência direta.
- Recomendado adicionar `pydantic>=2` em `pyproject.toml` ao portar DTOs.
- Usar Pydantic apenas como DTO/schema LLM, persistindo em JSONField via `model_dump(mode="json")`.

## OpenSpec Change Criado

Criado change:

`openspec/changes/align-llm-contract-and-doctor-routing/`

Arquivos criados:

- `proposal.md`
- `design.md`
- `tasks.md`
- `slices/slice-001-canonical-prompts.md`
- `slices/slice-002-llm1-pydantic-contract.md`
- `slices/slice-003-llm2-pydantic-contract.md`
- `slices/slice-004-scope-gate-nir-final.md`
- `slices/slice-005-doctor-report-presenter.md`
- `slices/slice-006-doctor-role-guard.md`
- `slices/slice-007-quality-docs-closeout.md`

### Proposta/Design

Objetivo do change:

1. Restaurar nomes canônicos de prompts do legado:
   - `llm1_system`
   - `llm1_user`
   - `llm2_system`
   - `llm2_user`
2. Portar defaults e renderização final dos prompts do legado quase literalmente.
3. Portar validação Pydantic v2 dos schemas LLM1/LLM2.
4. Registrar auditoria via `CaseEvent`, sem tabela nova de interações LLM.
5. Corrigir `non_eda`/`unknown` para ir direto ao resultado NIR (`WAIT_R1_CLEANUP_THUMBS`) sem fila médica.
6. Apresentar ao médico relatório equivalente ao formato legado de 7 blocos.
7. Garantir `role_required("doctor")` nas views médicas.

### Slices planejados

1. Slice 001 — Prompts canônicos legados.
2. Slice 002 — Contrato Pydantic LLM1.
3. Slice 003 — Contrato Pydantic LLM2.
4. Slice 004 — Scope gate direto para resultado NIR.
5. Slice 005 — Presenter médico em 7 blocos.
6. Slice 006 — Role guard médico.
7. Slice 007 — Quality gate e closeout.

## Slice 001 — Já Implementado por Outro LLM

Usuário informou conclusão:

Branch: `feat/slice-001-canonical-prompts`

Commit: `a2e9b23 — feat(slice-001): alinhar nomes canônicos de prompts ao legado`

Report:

`/tmp/ats-web-slice-001-canonical-prompts-report.md`

Quality gates informados:

- ruff check: ✅
- ruff format --check: ✅
- mypy: ✅
- pytest: ✅ `555 passed`

Arquivos alterados pelo implementador:

- `apps/llm/management/commands/seed_prompts.py`
- `apps/pipeline/orchestrator.py`
- `apps/llm/tests/test_seed_prompts.py`
- `apps/pipeline/tests/test_orchestrator.py`

Resumo do slice:

- `seed_prompts` agora cria nomes canônicos:
  - `llm1_system`
  - `llm1_user`
  - `llm2_system`
  - `llm2_user`
- Orchestrator busca nomes sem `_prompt`.
- Defaults de seed portados do legado: LLM1 v6 e LLM2 v3.
- Fallbacks legados adicionados no orchestrator.
- Nenhuma alteração de serviços LLM, Pydantic, scope gate, presenter ou role guard.

Após revisar o report, foi atualizado:

`openspec/changes/align-llm-contract-and-doctor-routing/tasks.md`

marcando Slice 001 como concluído:

```markdown
- [x] Slice 001 — Prompts canônicos legados (`slices/slice-001-canonical-prompts.md`) — commit `a2e9b23`, report `/tmp/ats-web-slice-001-canonical-prompts-report.md`
```

Observação feita ao usuário:

- Slice 001 aprovado para seguir.
- Fallback de `llm1_user` em `orchestrator.py` parecia mais curto que seed v6 completo.
- Isso deveria ser resolvido/centralizado no Slice 002.

## Ajuste Posterior Solicitado pelo Usuário

Usuário comentou que quer usar os prompts mais recentes/mais completos, não fallback simplificado.

Resposta dada:

- Concordância.
- Regra ideal:
  1. Banco primeiro.
  2. Fallback de código com conteúdo legado mais recente conhecido.
  3. Renderização final com instruções adicionais do service legado.
  4. Nunca voltar para fallback mínimo `{case_id}` para nomes canônicos.

Usuário pediu para ajustar Slice 002.

Arquivo ajustado:

`openspec/changes/align-llm-contract-and-doctor-routing/slices/slice-002-llm1-pydantic-contract.md`

Principais ajustes no Slice 002:

- Problema agora explicita que fallback de código pode estar menos completo que prompt legado recente.
- Objetivo agora inclui alinhar fallback/default LLM1 ao prompt legado mais recente e completo.
- Requisitos funcionais agora incluem:
  - centralizar defaults LLM1;
  - `llm1_system`: v6 da migration legada `0018_prompt_templates_llm1_ptbr_v6.py`;
  - `llm1_user`: v6 da mesma migration + renderização final do service legado (`_render_user_prompt`) quando enviado ao LLM;
  - fallback LLM1 não deve ser simplificado nem retornar apenas `{case_id}` para nomes canônicos conhecidos.
- TDD agora exige verificar instruções críticas:
  - `schema_version 1.1`;
  - `origin_context`;
  - `tracked_exams`;
  - `had_transfusion`;
  - `gastrostomia/GTT/PEG`;
  - `dilatacao esofagica`;
  - `corpo estranho`;
  - `CPRE` como `non_eda` na renderização final.
- Critério de sucesso agora inclui fallback/default LLM1 mais completo, não fallback mínimo.

## Estado Git/Branch Observado

Após Slice 001, comando observado:

```text
?? docs/investigations/
?? openspec/changes/
feat/slice-001-canonical-prompts
```

Ou seja:

- Os documentos de investigação e OpenSpec criados pelo planner ainda aparecem como untracked no working tree local, a menos que tenham sido adicionados em outro commit fora do contexto.
- Branch atual depois do implementador: `feat/slice-001-canonical-prompts`.
- Últimos commits observados:
  - `a2e9b23 feat(slice-001): alinhar nomes canônicos de prompts ao legado`
  - `c312da5 fix: mostrar relatório completo da IA na decisão médica`
  - `1b15c6a fix: 4 correções do pipeline de upload e decisão médica`

## Arquivos/locais importantes no legado

### Prompts e DTOs

- `/home/carlos/projects/augmented-triage-system/alembic/versions/0018_prompt_templates_llm1_ptbr_v6.py`
  - LLM1 prompts mais recentes v6, com `origin_context`, `tracked_exams`, `had_transfusion`.
- `/home/carlos/projects/augmented-triage-system/alembic/versions/0005_prompt_templates_ptbr_v3.py`
  - LLM2 prompts v3.
- `/home/carlos/projects/augmented-triage-system/src/triage_automation/application/dto/llm1_models.py`
  - Pydantic `Llm1Response` e modelos auxiliares.
- `/home/carlos/projects/augmented-triage-system/src/triage_automation/application/dto/llm2_models.py`
  - Pydantic `Llm2Response`.
- `/home/carlos/projects/augmented-triage-system/src/triage_automation/application/services/llm1_service.py`
  - Renderização final do prompt LLM1, validação Pydantic, agency_record guard, language guard.
- `/home/carlos/projects/augmented-triage-system/src/triage_automation/application/services/llm2_service.py`
  - Renderização final do prompt LLM2 e validação Pydantic.

### Scope gate

- `/home/carlos/projects/augmented-triage-system/src/triage_automation/application/services/process_pdf_case_service.py`
  - `build_scope_gated_manual_review_payload`.
  - Para `non_eda`/`unknown`, enfileira `post_room1_final_scope_manual_review`, não `post_room2_widget`.
- `/home/carlos/projects/augmented-triage-system/tests/integration/test_process_pdf_case_llm2.py`
  - Testes confirmando `room2_jobs == 0`, `room1_manual_review_jobs == 1`, `len(llm2_client.calls) == 0`.
- `/home/carlos/projects/augmented-triage-system/src/triage_automation/application/services/post_room1_final_service.py`
  - Mensagem final scope manual review.

### Relatório Médico

- `/home/carlos/projects/augmented-triage-system/src/triage_automation/infrastructure/matrix/message_templates.py`
  - `build_room2_case_summary_message`
  - `build_room2_case_summary_formatted_html`
  - helpers `_build_room2_*`
  - 7 blocos do relatório médico:
    1. Resumo clínico
    2. Achados críticos
    3. Pendências críticas
    4. Decisão sugerida
    5. Suporte recomendado
    6. ASA estimado
    7. Motivo objetivo

## Próximo Passo Recomendado

Aguardar implementador executar:

`openspec/changes/align-llm-contract-and-doctor-routing/slices/slice-002-llm1-pydantic-contract.md`

Quando o usuário trouxer o report do Slice 002:

1. Ler o report em `/tmp/...`.
2. Inspecionar arquivos alterados.
3. Verificar se `pyproject.toml` inclui `pydantic>=2`.
4. Verificar se schemas LLM1 foram portados literalmente ou com diferenças justificadas.
5. Verificar se fallback/default LLM1 está completo e centralizado.
6. Verificar se testes cobrem schema 1.1, extra forbid, agency_record mismatch, pediatria, subtipo e instruções críticas do prompt.
7. Atualizar `tasks.md` marcando Slice 002 como concluído se aprovado.
8. Autorizar Slice 003.

## Cuidado Importante

Não implementar código sem design/slice. Seguir Stop Rule do projeto:

- uma slice vertical por vez;
- TDD;
- relatório markdown temporário;
- commit e push;
- parar e pedir confirmação.

## Resposta curta se retomando após compactação

Se estiver retomando depois de compactar contexto, leia primeiro:

1. `docs/investigations/2026-05-18-self-handoff-align-llm-contract.md` (este arquivo)
2. `docs/investigations/2026-05-18-nir-to-doctor-flow-review.md`
3. `openspec/changes/align-llm-contract-and-doctor-routing/tasks.md`
4. `openspec/changes/align-llm-contract-and-doctor-routing/slices/slice-002-llm1-pydantic-contract.md`

Estado esperado: Slice 001 concluído, Slice 002 é o próximo.
