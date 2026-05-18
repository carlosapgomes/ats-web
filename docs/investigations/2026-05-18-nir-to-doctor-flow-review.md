# Investigação do Fluxo NIR → Médico

Data: 2026-05-18

## Objetivo

Investigar o fluxo inicial do sistema atual Django, partindo da função do usuário NIR até a chegada da informação ao usuário médico, comparando com o comportamento do projeto legado Matrix em `/home/carlos/projects/augmented-triage-system/`.

Esta investigação não implementa correções. O objetivo é registrar achados e perguntas antes de propor slices.

## Escopo Investigado

1. Upload NIR e criação do caso.
2. Transições iniciais e eventos de auditoria.
3. Disparo da pipeline LLM.
4. Serviços LLM1/LLM2 e prompts.
5. Scope detection para `non_eda` e `unknown`.
6. Roteamento até fila médica.
7. Apresentação do caso para o médico.
8. Controle de acesso por papel ativo na área médica.

## Arquivos Consultados

### Projeto atual `ats-web`

- `apps/intake/views.py`
- `apps/intake/tests/test_upload.py`
- `apps/pipeline/tasks.py`
- `apps/pipeline/orchestrator.py`
- `apps/pipeline/llm1_service.py`
- `apps/pipeline/llm2_service.py`
- `apps/pipeline/scope_detection.py`
- `apps/pipeline/tests/test_orchestrator.py`
- `apps/pipeline/tests/test_scope_detection.py`
- `apps/pipeline/tests/test_llm1_service.py`
- `apps/pipeline/tests/test_llm2_service.py`
- `apps/llm/management/commands/seed_prompts.py`
- `apps/llm/models.py`
- `apps/admin_ui/forms.py`
- `apps/cases/models.py`
- `apps/cases/signals.py`
- `apps/doctor/views.py`
- `apps/doctor/forms.py`
- `apps/doctor/tests/test_views.py`
- `templates/doctor/queue.html`
- `templates/doctor/decision.html`

### Projeto legado `augmented-triage-system`

- `src/triage_automation/application/services/process_pdf_case_service.py`
- `src/triage_automation/application/services/llm1_service.py`
- `src/triage_automation/application/services/llm2_service.py`
- `src/triage_automation/application/dto/llm1_models.py`
- `src/triage_automation/application/dto/llm2_models.py`
- `src/triage_automation/application/services/post_room2_widget_service.py`
- `src/triage_automation/application/services/post_room1_final_service.py`
- `src/triage_automation/infrastructure/matrix/message_templates.py`
- `alembic/versions/0005_prompt_templates_ptbr_v3.py`
- `alembic/versions/0016_prompt_templates_llm1_ptbr_v5.py`
- `alembic/versions/0018_prompt_templates_llm1_ptbr_v6.py`
- `tests/integration/test_process_pdf_case_llm2.py`
- `tests/integration/test_post_room2_widget.py`

## Fluxo Atual Observado no Django

### 1. Upload NIR

Em `apps/intake/views.py::intake_home`:

1. Cria `Case` com `created_by=user`.
2. Salva o PDF em `case.pdf_file`.
3. Executa transições:
   - `NEW → R1_ACK_PROCESSING`
   - `R1_ACK_PROCESSING → EXTRACTING`
4. Extrai texto do PDF.
5. Remove marca d'água e extrai `agency_record_number`.
6. Persiste `extracted_text`, `agency_record_number`, `agency_record_extracted_at`.
7. Executa `extraction_complete(success=True)`, indo para `LLM_STRUCT`.
8. Chama `enqueue_pipeline(case.case_id)`.
9. Redireciona para detalhe do caso.

Cobertura em `apps/intake/tests/test_upload.py` confirma:

- criação do caso;
- extração do número de registro;
- persistência do PDF;
- status final `LLM_STRUCT` após upload;
- eventos `CASE_CREATED`, `CASE_START_PROCESSING`, `CASE_START_EXTRACTION`, `CASE_EXTRACTION_OK`.

### 2. Disparo da pipeline

Em `apps/pipeline/tasks.py`:

- `enqueue_pipeline(case_id)` chama `django_q.tasks.async_task("apps.pipeline.tasks.execute_pipeline", str(case_id))`.
- `execute_pipeline(case_id_str)` chama `run_pipeline(UUID(case_id_str))`.

Ou seja, o upload apenas enfileira a pipeline; o processamento real depende do worker `django-q2`.

### 3. Pipeline até fila médica

Em `apps/pipeline/orchestrator.py::run_pipeline`:

1. Busca o caso.
2. Executa LLM1 via `_run_llm1_step`.
3. Persiste `structured_data` e `summary_text`.
4. Executa `_run_scope_and_llm2`.
5. Para EDA:
   - `LLM_STRUCT → LLM_SUGGEST` via `llm1_complete(success=True)`.
   - aplica policy engine.
   - busca caso anterior.
   - executa LLM2.
   - aplica reconciliation.
   - aplica suporte/ASA.
   - persiste `suggested_action`.
   - `LLM_SUGGEST → R2_POST_WIDGET` via `llm2_complete(success=True)`.
   - `R2_POST_WIDGET → WAIT_DOCTOR` via `ready_for_doctor()`.

Cobertura em `apps/pipeline/tests/test_orchestrator.py` confirma que o happy path EDA termina em `WAIT_DOCTOR`.

## Achados Principais

### A1. Prompts atuais não correspondem aos prompts otimizados do legado

O comando atual `apps/llm/management/commands/seed_prompts.py` cria prompts com nomes:

- `llm1_system_prompt`
- `llm1_user_prompt`
- `llm2_system_prompt`
- `llm2_user_prompt`

Além disso, o conteúdo atual diz, por exemplo:

- “Analise o seguinte relatório de endoscopia...”
- campos como `exam_findings`, `clinical_indication`, `urgency`;
- LLM2 com `support_recommendation: none | partial | full` e `suggestion: scheduled | immediate`.

Isso diverge do objetivo correto informado pelo usuário:

- analisar relatório/encaminhamento de regulação solicitando EDA;
- reutilizar quase literalmente os prompts, schema estruturado e relatório médico do sistema legado.

No legado, os prompts e serviços usam nomes:

- `llm1_system`
- `llm1_user`
- `llm2_system`
- `llm2_user`

E o contrato esperado é schema `1.1`, com campos como:

- `patient`
- `eda`
- `preop_screening`
- `policy_precheck`
- `summary`
- `extraction_quality`
- `origin_context`
- `transfusion`
- `tracked_exams`

Para LLM2, o contrato esperado é schema `1.1` com:

- `case_id`
- `agency_record_number`
- `suggestion: accept | deny`
- `support_recommendation: none | anesthesist | anesthesist_icu | unknown`
- `rationale`
- `policy_alignment`
- `confidence`

Impacto provável: alto. Mesmo que o código de policy espere estruturas compatíveis com o legado, os prompts semeados no projeto atual podem induzir o LLM a produzir payload incompatível ou semanticamente errado.

### A2. Há inconsistência de nomes de prompts entre pipeline, seed e admin UI

Observado:

- `apps/pipeline/orchestrator.py` busca prompts:
  - `llm1_system_prompt`
  - `llm1_user_prompt`
  - `llm2_system_prompt`
  - `llm2_user_prompt`
- `apps/llm/management/commands/seed_prompts.py` cria esses mesmos nomes com sufixo `_prompt`.
- `apps/admin_ui/forms.py` permite criar/editar apenas:
  - `llm1_system`
  - `llm1_user`
  - `llm2_system`
  - `llm2_user`

No legado, os nomes canônicos são `llm1_system`, `llm1_user`, `llm2_system`, `llm2_user`.

Impacto provável: alto. O admin pode editar prompts que a pipeline atual não usa. A pipeline pode continuar usando os prompts errados sem que o admin perceba.

### A3. Serviços LLM atuais não validam o schema legado com Pydantic

No projeto atual:

- `Llm1Service` apenas decodifica JSON e extrai `summary.one_liner`.
- `Llm2Service` apenas decodifica JSON e valida opcionalmente `case_id`/`agency_record_number` se presentes.

No legado:

- `Llm1Service` valida `Llm1Response` com Pydantic.
- `Llm2Service` valida `Llm2Response` com Pydantic.
- Há rejeição de campos extras (`extra="forbid"`).
- Há validações de consistência, por exemplo pediatria e subtipo EDA.
- Há language guard pt-BR com retry.

Impacto provável: alto. O Django atual pode aceitar payloads incompletos ou incompatíveis e deixar erros aparecerem mais tarde na policy, template ou decisão médica.

### A4. Comportamento legado para `non_eda` e `unknown` NÃO envia para médico

Confirmação no legado:

- `ProcessPdfCaseService` cria `scope_gate_payload` via `build_scope_gated_manual_review_payload`.
- Quando esse payload existe:
  - persiste `suggested_action_json` com `decision/suggestion = manual_review_required`;
  - registra `EDA_SCOPE_GATED_MANUAL_REVIEW`;
  - enfileira `post_room1_final_scope_manual_review`;
  - NÃO enfileira `post_room2_widget`.
- `PostRoom2WidgetService` também tem proteção: se receber caso scope-gated, registra `ROOM2_WIDGET_SKIPPED_SCOPE_GATED_MANUAL_REVIEW` e não posta nada na Room 2.
- Testes legados confirmam:
  - `room2_jobs == 0`;
  - `room1_manual_review_jobs == 1`;
  - `len(llm2_client.calls) == 0`.

Portanto, a condução real no sistema original é: `non_eda`/`unknown` vão para resultado/revisão manual no NIR, sem passar pelo médico.

### A5. Django atual envia `non_eda`/`unknown` para `WAIT_DOCTOR`

No projeto atual:

- `apps/pipeline/scope_detection.py` porta corretamente a classificação e retorna `manual_review_required`.
- Porém `apps/pipeline/orchestrator.py`, ao detectar scope gate, chama `case.scope_gate_bypass(...)`.
- `apps/cases/models.py::scope_gate_bypass()` faz `LLM_STRUCT → WAIT_DOCTOR`.
- O teste atual `TestPipelineScopeGated` espera explicitamente `case.status == WAIT_DOCTOR` para non-EDA.

Isso diverge do legado e provavelmente é um equívoco de implementação.

Correção provável futura: ajustar o roteamento para não entrar na fila médica. Mas a transição exata no Django precisa ser desenhada com cuidado, porque o legado mantinha o status `LLM_SUGGEST` até o job de resposta final exigir esse estado; no Django talvez seja mais apropriado transitar diretamente para `WAIT_R1_CLEANUP_THUMBS` após preparar o resultado final.

### A6. Relatório apresentado ao médico no Django não replica o formato otimizado do legado

No legado, `message_templates.py::build_room2_case_summary_message` monta um relatório técnico com blocos fixos:

1. `Resumo clínico`
2. `Achados críticos`
3. `Pendências críticas`
4. `Decisão sugerida`
5. `Suporte recomendado`
6. `ASA estimado`
7. `Motivo objetivo`

Além de contexto como:

- procedimento solicitado canônico;
- origem;
- transfusão;
- exames rastreados;
- marcador pediátrico;
- histórico de negativa recente.

No Django atual, `templates/doctor/decision.html` mostra:

- dados básicos do paciente;
- `summary_text`;
- `suggested_action.reasoning`, se existir;
- badges de suporte/fluxo;
- JSON completo colapsável.

Isso não replica literalmente o formato otimizado do legado.

Impacto provável: alto para usabilidade e para aderência ao feedback médico real já incorporado no projeto original.

### A7. Fila médica não exige papel ativo `doctor`

Em `apps/doctor/views.py`, as views usam apenas `@login_required`.

Não há `@role_required("doctor")` nas views:

- `doctor_queue`
- `doctor_decision`
- `doctor_submit`

Os testes existentes verificam login, mas não há teste de bloqueio para papel ativo incorreto.

Impacto: segurança/autorização. Um usuário autenticado com outro papel ativo pode acessar as URLs do médico se souber o caminho.

### A8. Testes atuais codificam alguns comportamentos divergentes

Exemplos:

- `apps/pipeline/tests/test_orchestrator.py::TestPipelineScopeGated` espera `WAIT_DOCTOR` para `non_eda`.
- `apps/doctor/tests/test_views.py` usa textos como “fratura de fêmur”, “hérnia inguinal”, “cirurgia eletiva”, que não representam bem o domínio EDA/regulação.
- `apps/pipeline/tests/test_llm1_service.py` e `test_llm2_service.py` aceitam schemas simplificados, inclusive `schema_version: 1.0` e payloads sem campos obrigatórios do legado.

Esses testes precisariam ser revisados junto com as correções para não manter o comportamento errado como contrato.

## Comparação Resumida: Legado vs Django Atual

| Tema | Legado | Django atual | Status |
| --- | --- | --- | --- |
| Prompt names | `llm1_system`, `llm1_user`, `llm2_system`, `llm2_user` | pipeline usa nomes com `_prompt`; admin usa nomes sem `_prompt` | Divergente |
| Conteúdo dos prompts | Triagem de solicitação/relatório clínico para EDA | fala em relatório de endoscopia e achados endoscópicos | Divergente |
| Schema LLM1 | Pydantic `Llm1Response` schema 1.1 | JSON livre, sem validação forte | Divergente |
| Schema LLM2 | Pydantic `Llm2Response` schema 1.1 | JSON livre, validação parcial de identidade | Divergente |
| `non_eda`/`unknown` | pula Room 2, vai para Room 1 final manual review | vai para `WAIT_DOCTOR` | Divergente |
| Relatório médico | 7 blocos técnicos otimizados | cards simples + JSON colapsável | Divergente |
| Acesso médico | papel/rota de Room 2 controlado pelo runtime | somente `login_required` nas views Django | Divergente |

## Pontos Críticos a Corrigir Primeiro

### Prioridade 1 — Prompts, nomes e schemas LLM

Este parece ser o ponto mais crítico antes de avaliar qualidade clínica do fluxo, porque todo o restante depende do payload gerado pelo LLM.

Correção futura provavelmente deve:

1. alinhar nomes canônicos de prompts com o legado;
2. migrar/copiar conteúdo otimizado dos prompts legados;
3. ajustar seed/admin/orchestrator para usar os mesmos nomes;
4. portar validação Pydantic dos schemas LLM1/LLM2 ou equivalente;
5. revisar testes que aceitam payloads simplificados.

### Prioridade 2 — Scope gate `non_eda`/`unknown`

Depois de alinhar contratos LLM, corrigir o roteamento para que `non_eda`/`unknown` não chegue à fila médica, conforme comportamento real do legado.

### Prioridade 3 — Relatório apresentado ao médico

Portar/adaptar o formato otimizado do legado para a tela Django do médico, em vez de exibir apenas resumo simples e JSON.

### Prioridade 4 — Controle de acesso médico

Adicionar/verificar `role_required("doctor")` nas views médicas e testes de bloqueio para papéis incorretos.

## Perguntas em Aberto

1. Devemos manter exatamente os nomes legados `llm1_system`, `llm1_user`, `llm2_system`, `llm2_user` como canônicos no Django, corrigindo o orchestrator e o seed?
Resposta: Sim, vamos manter os nomes legados

2. Para `non_eda`/`unknown` no Django, qual estado final intermediário desejado?
   - Opção A: mimetizar semanticamente o legado e ir direto para `WAIT_R1_CLEANUP_THUMBS` com resultado de revisão manual.
   - Opção B: preservar um estado intermediário como `LLM_SUGGEST`/`R1_FINAL_REPLY_POSTED` antes de `WAIT_R1_CLEANUP_THUMBS`.
   - Não assumir sem decisão explícita.
Resposta: opção A

3. A validação Pydantic deve ser portada literalmente para o Django, ou devemos implementar validação equivalente sem Pydantic?
Resposta: prefiro portar a validação literalmente. Há algum risco/conflito para usar pydantic no novo stack?

4. O relatório médico da tela Django deve reutilizar diretamente funções portadas do `message_templates.py`, ou devemos criar um presenter Django equivalente com a mesma saída sem acoplar a nomes Room/Matrix?
Resposta: podemos criar um presenter, desde que o resultado final seja equivalente

5. Os prompts devem ser carregados apenas do banco, ou os defaults legados também devem existir como fallback de código para segurança operacional?
Resposta: os prompts defaults legados devem existir como fallback e seed inicial

## Recomendação de Próximos Slices de Investigação/Correção

1. Slice de alinhamento de prompts e nomes canônicos.
2. Slice de schema validation LLM1/LLM2 com testes baseados nos DTOs legados.
3. Slice de scope gate: `non_eda`/`unknown` não entra na fila médica.
4. Slice de presenter/relatório médico baseado nos 7 blocos do legado.
5. Slice de autorização por papel ativo em `doctor`.

Cada slice deve começar com teste RED e confirmar comportamento legado quando aplicável.


Planeje os slices para serem executados por outro LLM que vai receber o arquivo do slice com contexto zero. Por isso o arquivo do slice precisa ser um handoff+prompt para dar contexto ao implementador. A implementação deve seguir os requisitos de clean code, dry, you-aint-gonna-need-it, com slices verticais enxutos, tocando poucos arquivos, implementados com TDD. No arquivo do slice devem ser definidos claramente os gates e critérios de sucesso da implementação, e o implementador deve criar um relatório detalhado em markdown do que foi implementado e passar o caminho do relatório para voce verificar a implementação.


