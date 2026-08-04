# Slice 006: Correção de tipo e reprocessamento auditável

## Handoff contexto zero

Leia integralmente AGENTS/PROJECT_CONTEXT, change/ADR/spec `exam-type-correction`, este slice e:

- `apps/cases/models.py` FSM e eventos;
- `apps/cases/services.py` locks/transações como referência;
- `apps/intake/views.py` detalhes/manual review/confirm receipt;
- `apps/intake/tasks.py` recovery em LLM_STRUCT;
- `apps/pipeline/tasks.py`, `orchestrator.py`;
- templates de detalhe NIR;
- testes FSM/intake/tasks/scope.

### Estado e objetivo

Mismatch/mixed/unknown termina em `WAIT_R1_CLEANUP_THUMBS`. Hoje NIR só confirma resultado. Entregue:

```text
caso manual antes do médico
→ NIR vê declarado/detectado/evidência
→ corrige tipo no mesmo UUID
→ fontes PDF/anexos/texto ficam
→ derivados LLM são limpos
→ FSM volta de forma explícita a LLM_STRUCT
→ pipeline correto é enfileirado uma vez
→ timeline registra tudo
```

Interprete “antes de entrar na fila” de modo seguro: não mutar enquanto worker está em estado transitório. Estados/processamento concorrente devem ser recusados; manual review estável é o caminho principal.

## Protocolo DeepSeek4-Flash

**Qualquer falha = INCOMPLETO; não marque task/commit/push.**

1. Confirme branch `feature/colonoscopy-exam-workflow`, árvore limpa e registre `BASE_REF=$(git rev-parse HEAD)`.
2. Registre matriz `Requisito → arquivo(s) → teste(s)` e rode `uv run pytest` baseline antes de editar; pare com failure/error.
3. Escreva testes primeiro e prove RED real.
4. Faça GREEN mínimo sem antecipar slices.
5. Faça REFACTOR estreito com clean code, DRY, YAGNI, baixo acoplamento e sem código morto.
6. Execute/interprete todos os checks `rg`/diff.
7. Rode exatamente `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy .`, `uv run pytest`; final exit 0, zero failures/errors e `passed_final >= passed_baseline`.
8. Relatório deve conter comandos/exit codes, snippets, comparação e seção **Handoff para verificador**.
9. Só então marque Slice 006, commit/push, responda REPORT_PATH e PARE.

Mais de **8 arquivos produto/teste** (migration inexistente; tasks não conta) exige revisão do planner.

## Requisitos

### R1. Elegibilidade server-side

Serviço único, transacional, valida:

- papel/ator NIR passado explicitamente;
- caso ainda não alcançou `WAIT_DOCTOR` nem decisão posterior;
- resultado atual é manual review de exam mismatch/mixed/unknown, ou outro estado estável pré-médico explicitamente enumerado;
- novo tipo válido e diferente;
- caso sem lock/reserva incompatível;
- não tentar editar durante `R1_ACK_PROCESSING`, `EXTRACTING`, `LLM_STRUCT`, `LLM_SUGGEST`, `R2_POST_WIDGET` se worker puder persistir concorrente.

Não usar comparação textual frouxa de status. `select_for_update` e transação evitam atualização parcial.

### R2. FSM explícita sem novo estado

Adicionar transição nomeada de estado manual elegível para `LLM_STRUCT`, por exemplo `reprocess_after_exam_type_correction`. Preservar os 17 estados; não atribuir `status` diretamente nem desproteger FSM.

A transição registra evento, mas salvar eventos em ordem correta para não sobrescrever `_pending_event`.

### R3. Preservar fontes/inutilizar derivados

Preservar exatamente:

- `case_id`, `created_by`, timestamps originais;
- PDF e anexos;
- `extracted_text`, occurrence e dias em tela;
- correção linkage e mensagens/eventos anteriores.

Limpar:

- `structured_data`;
- `summary_text`;
- `suggested_action`;
- `priority_signals`;
- campos de prompt/projeção que futuramente existirem e forem comprovadamente derivados.

Nenhuma decisão médica/agendamento pode existir em caso elegível.

### R4. Enfileirar somente LLM

Após commit/transição, chamar `enqueue_pipeline(case_id)` uma vez. Não chamar extração PDF. Se enqueue falhar, estado `LLM_STRUCT` deve permitir recovery idempotente existente ou erro explícito sem segundo enqueue web concorrente.

### R5. Auditoria

Eventos append-only:

- mismatch já registrado pelo pipeline;
- `EXAM_TYPE_CORRECTED` com old/new/actor/reason_code;
- `CASE_REPROCESSING_REQUESTED` ou evento de transição equivalente.

Não incluir texto clínico integral/JSON/PDF. Timeline NIR tem labels/dots legíveis.

### R6. UI NIR

No manual review elegível, exibir card com tipo declarado/detectado, motivo e formulário de correção. POST protegido por NIR/CSRF, backend chama serviço e redireciona ao detalhe. Em inelegível, controle ausente e POST retorna 404/erro seguro. Confirm receipt não deve ocorrer simultaneamente com correção.

### R7. Idempotência/concorrência

Segundo POST com estado já movido não enfileira novamente. Caso reservado/processando ou que alcançou WAIT_DOCTOR é rejeitado sem limpar dados. Testar rollback transacional se enqueue/service falhar no ponto controlável.

## Arquivos esperados/proibidos

1. `apps/cases/models.py`
2. `apps/intake/services.py` ou serviço coeso novo (um)
3. `apps/intake/views.py`
4. `apps/intake/urls.py` se rota dedicada necessária
5. `templates/intake/case_detail.html` ou partial novo (um)
6. `apps/intake/views.py` maps de eventos já incluído
7. até dois arquivos de testes focados
8. `apps/pipeline/tasks.py`/`apps/intake/tasks.py` somente se teste provar recovery incompatível; substituir outro extra, justificar

Proibido: migration/novo campo/estado, doctor/scheduler/dashboard/prompts/policy, copiar Case, reextrair PDF, alterar locks globais, permitir pós-WAIT_DOCTOR.

## TDD

RED mínimo:

1. manual mismatch corrige mesmo UUID e status LLM_STRUCT;
2. old/new/event payload;
3. derivados limpos/fontes preservadas;
4. enqueue_pipeline uma vez e PDF extraction zero;
5. mixed/unknown elegíveis;
6. mesmo tipo inválido;
7. WAIT_DOCTOR e posterior rejeitados;
8. estado worker transitório rejeitado sem mutação;
9. segundo POST idempotente;
10. lock incompatível rejeita;
11. GET/POST NIR role, controle apenas elegível;
12. confirm receipt não é executado junto;
13. timeline labels;
14. recovery LLM_STRUCT continua.

## Inspeções

```bash
rg -n "reprocess.*exam|EXAM_TYPE_CORRECTED|CASE_REPROCESSING_REQUESTED|select_for_update|atomic" apps/cases apps/intake
rg -n "enqueue_pipeline|enqueue_pdf_extraction" apps/intake apps/pipeline apps/*/tests | grep -E "exam|reprocess|correc|intake" || true
rg -n "WAIT_DOCTOR|LLM_STRUCT|manual_review_required|mixed_exam_request" apps/intake apps/cases
rg -n "structured_data|summary_text|suggested_action|priority_signals|pdf_file|extracted_text" apps/intake/services.py apps/*/tests/*exam* 2>/dev/null || true

git diff --name-only "$BASE_REF"
git diff -- apps/cases/migrations apps/doctor apps/scheduler apps/dashboard apps/pipeline/policy apps/llm
```

Interpretar: migration/proibidos vazios; um enqueue LLM por correção; nenhum enqueue PDF.

## Critérios/gates

- [ ] R1–R7; same UUID; FSM explícita; fontes preservadas/derivados limpos; um LLM enqueue/zero PDF; eventos; UI role-safe; concorrência/idempotência; ≤8 arquivos; baseline/gate/report.

## Gates de autoavaliação

Responder no relatório: estados elegíveis/recusados; prova same UUID; prova fontes vs derivados; por que não race; enqueue count; evento ordering; rollback/segunda tentativa; extras; pytest compare.

### Condições automáticas de INCOMPLETO

Baseline/RED/gate/report ausentes; status atribuído diretamente; novo estado/migration; alteração pós-WAIT_DOCTOR; worker transitório mutado; PDF/anexo/texto apagado; derivado antigo mantido; PDF reextraído; múltiplos enqueue; novo Case criado; eventos sem old/new; texto clínico em payload; role relaxada; partial update; requisito sem prova; >8 sem revisão; final falha/passed menor; commit prematuro.

## Relatório obrigatório

`/tmp/introduce-colonoscopy-exam-workflow-slice-006-report.md` com matriz, baseline, RED/GREEN/REFACTOR, snippets service/FSM/UI/events, tabela campos preservados/limpos, inspeções, gate, baseline-final, gates, diff, comandos rerun e Handoff R1–R7.

## Prompt pronto

```text
Read the complete handoff in slice-006-exam-type-correction-reprocess.md. Implement ONLY Slice 006 on feature/colonoscopy-exam-workflow. Follow mandatory DeepSeek protocol: clean BASE_REF, full pytest baseline first, real RED, minimal GREEN, narrow clean/DRY/YAGNI refactor, inspections, exact full gate and passed comparison. Any failure means INCOMPLETE with no tasks update/commit/push.

Deliver safe same-Case exam type correction only for stable pre-doctor/manual-review cases: transactional eligibility, explicit FSM transition back to LLM_STRUCT without a new state, preserve PDF/attachments/extracted text/events, clear derived LLM/signals, enqueue only LLM exactly once, append audit events, and expose a NIR-only UI. Reject active workers, locks, repeat submissions and WAIT_DOCTOR/later. Do not create a new Case, migration or PDF re-extraction.

Create /tmp/introduce-colonoscopy-exam-workflow-slice-006-report.md with all evidence and verifier handoff. If complete mark only Slice 006, commit, push, reply REPORT_PATH=... and STOP.
```
