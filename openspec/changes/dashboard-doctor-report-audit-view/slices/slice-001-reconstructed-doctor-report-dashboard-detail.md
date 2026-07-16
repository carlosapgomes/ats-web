<!-- markdownlint-disable MD013 -->

# Slice 001: Preparação compartilhada + relatório textual colapsável no detalhe do dashboard

## Handoff para implementador LLM com contexto zero

Leia completamente antes de editar:

- `AGENTS.md`
- `PROJECT_CONTEXT.md`
- `openspec/changes/dashboard-doctor-report-audit-view/proposal.md`
- `openspec/changes/dashboard-doctor-report-audit-view/design.md`
- `openspec/changes/dashboard-doctor-report-audit-view/tasks.md`
- `openspec/changes/dashboard-doctor-report-audit-view/specs/dashboard-case-audit-report/spec.md`
- este arquivo

Arquivos de código que devem ser inspecionados antes do RED:

- `apps/cases/models.py` — campos LLM e eventos do caso;
- `apps/pipeline/prior_case.py` — lookup e contrato de negativa anterior;
- `apps/doctor/presenters.py` — `DoctorReportPresenter`, `build_report()` e `build_text_report()`;
- `apps/doctor/views.py` — preparação atual do relatório médico;
- `apps/dashboard/views.py::dashboard_case_detail` — detalhe autorizado para manager/admin;
- `templates/doctor/decision.html` — relatório médico atual;
- `templates/intake/case_detail.html` — detalhe compartilhado pelo dashboard;
- `apps/dashboard/tests/test_dashboard.py` — helpers e regressões existentes.

Estado atual:

```text
Case já persiste structured_data, summary_text, suggested_action e extracted_text
→ doctor view prepara negativa anterior e instancia DoctorReportPresenter
→ doctor template mostra contexto + sete blocos
→ dashboard detail não prepara nem mostra esse relatório
```

Objetivo exato:

```text
Manager/admin abre no dashboard um caso com CASE_READY_FOR_DOCTOR
→ vê controle “Relatório automático apresentado ao médico (reconstruído)”
→ controle começa recolhido
→ ao expandir, lê o texto canônico do presenter médico
→ UI avisa que é reconstrução, não snapshot
→ casos sem handoff e contextos NIR não mostram o card
```

Limites de escopo:

- Implementar a reconstrução atual escolhida pelo solicitante; não criar snapshot.
- Não alterar models, migrations, FSM, eventos, prompts, schemas LLM, policy, permissões, URLs ou endpoints.
- Não mostrar JSON completo no dashboard.
- Não alterar o conteúdo/regras dos sete blocos do `DoctorReportPresenter` salvo correção mínima indispensável e previamente testada; a expectativa é apenas reutilizá-lo.
- Não adicionar JS customizado, HTMX, AJAX, API ou framework frontend.
- Não redesenhar o detalhe do caso nem mover ações existentes sem necessidade.

## Protocolo obrigatório para implementador DeepSeek4-Flash

Este slice será implementado por um modelo rápido e com tendência a concluir cedo demais. Portanto, siga este protocolo literalmente. **Se qualquer item abaixo falhar, o slice está INCOMPLETO**: não marque `tasks.md`, não faça commit/push e responda com bloqueio + evidência.

1. **Plano antes de editar**: escreva no relatório uma mini matriz `Requisito → arquivo(s) → teste(s)`. Não implemente requisito sem teste ou justificativa explícita.
2. **Baseline de pytest antes de editar**: confirme `git status --short` limpo, registre `BASE_REF=$(git rev-parse HEAD)` e rode `uv run pytest` no estado inicial. Cole no relatório o exit code e a linha de resumo. Se houver `failed/error` no baseline, pare e reporte INCOMPLETE/BLOQUEADO antes de codar.
3. **RED real**: crie/ajuste testes primeiro e rode o subconjunto alvo. Pelo menos um teste novo deve falhar pelo motivo esperado. Se o teste passar antes da implementação, ele não prova o comportamento; corrija o teste.
4. **GREEN mínimo**: implemente somente o necessário para os testes do slice passarem. Não faça refactor amplo, não toque em apps fora do escopo e não implemente snapshot/JSON/prompt versioning.
5. **Verificação por inspeção**: além dos testes, rode as buscas `rg` descritas neste slice para comprovar autorização, helper compartilhado, gate de handoff, collapse, escaping e ausência de persistência nova.
6. **Quality gate completo e comparação pytest**: execute exatamente `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy .` e `uv run pytest`. O pytest final deve ter exit code 0, zero failures/errors e contagem `passed` maior ou igual ao baseline. Se `failed > 0`, `errors > 0`, exit code != 0 ou `passed_final < passed_baseline`, o slice está INCOMPLETO.
7. **Relatório com evidência, não opinião**: cole comandos, exit codes, resumos baseline/final, RED/GREEN, snippets antes/depois, checks `rg` e respostas aos gates. Inclua `Handoff para verificador` com arquivos alterados, comandos exatos para rerun, riscos/limitações e checklist R1..R8. Inclua `Status: COMPLETE` somente se tudo estiver comprovado.

### Condições automáticas de INCOMPLETO

Marque como incompleto se ocorrer qualquer uma destas situações:

- baseline de pytest antes de editar não foi executado/registrado com exit code e resumo;
- teste planejado não foi escrito ou não foi executado;
- nenhum teste novo demonstrou RED pelo motivo esperado;
- quality gate completo não foi executado;
- qualquer teste, ruff ou mypy falhou;
- pytest final teve exit code diferente de 0, `failed > 0` ou `errors > 0`;
- contagem final de `passed` ficou menor que a contagem baseline;
- relatório informa somente `passed` sem declarar zero failures/errors e exit code 0;
- `tasks.md` foi marcado apesar de falha, pendência ou limitação não aceita;
- doctor e dashboard continuam preparando inputs do presenter por caminhos duplicados;
- o card aparece sem `CASE_READY_FOR_DOCTOR`;
- o card aparece no template compartilhado sem exigir `show_dashboard_nav`;
- decorators `login_required`/`role_required("manager", "admin")` foram removidos ou relaxados;
- foi adicionado `safe` ao texto reconstruído;
- foi criado model, migration, campo, snapshot, evento, endpoint ou transição FSM;
- JSON completo ou artefatos brutos foram expostos fora do escopo;
- comportamento antigo da tela médica foi removido sem teste/regressão;
- relatório temporário não foi criado no caminho exato exigido.

## Requisitos funcionais

### R1. Preparação compartilhada e canônica

Criar `apps/doctor/reporting.py` com helper pequeno que prepare `DoctorReportPresenter` para um `Case`.

O helper deve centralizar a lógica hoje presente em `apps/doctor/views.py`:

- `lookup_prior_case_context(case_id, agency_record_number)` quando houver registro;
- mapeamento `doctor_denied → deny_triage`;
- mapeamento `appointment_denied → deny_appointment`;
- construção de `recent_denial_context` com decisão, motivo, data e contagem;
- instanciação de `DoctorReportPresenter` com:
  - `case.structured_data or {}`;
  - `case.summary_text or ""`;
  - `case.suggested_action or {}`;
  - contexto de negativa recente;
  - `case.extracted_text or ""`.

A API exata pode usar dataclass/objeto preparado, mas deve disponibilizar sem nova consulta:

- o presenter ou relatório estruturado;
- `prior_context` usado pelo card de negativa anterior da tela médica;
- `prior_decision_display` usado pela tela médica.

Não importar `apps.doctor.views` no helper ou dashboard.

### R2. Tela médica preservada usando o helper

Refatorar `apps/doctor/views.py` para consumir o helper de R1 no lugar da preparação duplicada.

Preservar no context da tela médica:

- `report`;
- `prior_context`;
- `prior_decision_display`;
- `hide_prior_case_card` e sua comparação com correção explícita;
- todos os demais campos e comportamento de lock/formulário.

Não alterar `templates/doctor/decision.html` neste slice, salvo necessidade comprovada. Os testes médicos existentes devem continuar verdes.

### R3. Gate histórico por `CASE_READY_FOR_DOCTOR`

Em `dashboard_case_detail`, gerar `doctor_report_text` somente quando a timeline do caso contiver evento `CASE_READY_FOR_DOCTOR`.

Requisitos:

- não usar status atual como substituto do evento;
- não usar mera presença de `summary_text`/`suggested_action` como prova de handoff;
- preferir detectar o evento durante o loop já existente de `events`, sem query extra;
- caso sem handoff deve enviar texto vazio/ausente ao template.

### R4. Texto reconstruído pelo presenter canônico

Para caso elegível, `apps/dashboard/views.py` deve usar o helper de R1 e `DoctorReportPresenter.build_text_report()`.

O texto deve conter os labels canônicos:

```text
Resumo clínico
Achados críticos
Pendências críticas
Decisão sugerida
Suporte recomendado
ASA estimado
Motivo objetivo
```

Se houver negativa recente, seu bloco também deve vir do presenter compartilhado.

Não montar esses blocos manualmente na view/template.

### R5. Card textual colapsável e transparente

Em `templates/intake/case_detail.html`, adicionar card somente quando:

```django
show_dashboard_nav and doctor_report_text
```

O card deve:

- ter título visível `Relatório automático apresentado ao médico (reconstruído)`;
- incluir aviso de que o texto foi reconstruído a partir de artefatos armazenados e não é snapshot imutável;
- iniciar recolhido;
- usar Bootstrap Collapse existente;
- ter `aria-expanded="false"` e `aria-controls` coerente;
- exibir texto em `<pre>` responsivo com `white-space: pre-wrap` e scroll vertical razoável se necessário;
- não usar `safe`;
- não exigir JavaScript novo.

### R6. Autorização e template compartilhado preservados

Preservar exatamente o acesso de `dashboard_case_detail` para `manager` e `admin`.

O novo card não deve aparecer quando `templates/intake/case_detail.html` é usado pelo NIR, mesmo que o caso tenha handoff e artefatos. A condição `show_dashboard_nav` é obrigatória.

Não mudar decorators, URLs ou navegação existente.

### R7. Escaping obrigatório

Conteúdo como:

```text
<script>alert("audit")</script>
```

em `summary_text` ou outro campo narrativo deve aparecer escapado no HTML. Não aplicar `safe`, `mark_safe` ou interpolação HTML manual.

### R8. Read-only e escopo negativo

A abertura/expansão do relatório não pode:

- salvar `Case`;
- criar `CaseEvent`;
- alterar FSM;
- persistir relatório;
- expor JSON completo;
- alterar prompts/policy/LLM;
- mudar listagens, métricas, busca ou filtros do dashboard.

## Arquivos esperados

Idealmente tocar somente estes cinco arquivos de código/teste:

1. `apps/doctor/reporting.py` (novo)
2. `apps/doctor/views.py`
3. `apps/dashboard/views.py`
4. `templates/intake/case_detail.html`
5. `apps/dashboard/tests/test_dashboard.py`

E, somente após todos os gates:

1. `openspec/changes/dashboard-doctor-report-audit-view/tasks.md`

Permitido com justificativa no relatório:

- `apps/doctor/tests/test_views.py`, apenas se os testes existentes não permitirem provar preservação do refactor.

Arquivos proibidos:

- `apps/cases/models.py` e migrations;
- `apps/pipeline/orchestrator.py`, prompts, schemas e policy;
- URLs, settings e decorators de autorização;
- JavaScript/CSS novo, salvo impossibilidade comprovada de Bootstrap/utilitários existentes atenderem o layout;
- outros apps/templates não relacionados.

Se tocar mais de cinco arquivos de código/teste, justificar por requisito e explicar por que o slice continua vertical e enxuto.

## TDD obrigatório

### RED

Antes de código de produção, adicionar testes em `apps/dashboard/tests/test_dashboard.py`.

Testes mínimos:

1. **Manager vê relatório após handoff**
   - criar caso com artefatos conhecidos;
   - criar `CaseEvent(event_type="CASE_READY_FOR_DOCTOR")`;
   - GET `dashboard:case_detail`;
   - assert título, `summary_text` e labels dos sete blocos.

2. **Admin vê relatório após handoff**
   - parametrizar papel ou criar teste específico;
   - assert status 200 e card presente.

3. **Collapse fechado e acessível**
   - assert `data-bs-toggle="collapse"`;
   - assert target/ID estável;
   - assert `aria-expanded="false"`;
   - assert body tem `class="collapse"` sem `show` inicial.

4. **Aviso de reconstrução**
   - assert microcopy menciona artefatos armazenados e `não é um snapshot imutável` ou equivalente inequívoco.

5. **Caso sem handoff não mostra card**
   - criar caso com `summary_text` e `suggested_action`, mas sem `CASE_READY_FOR_DOCTOR`;
   - assert título ausente.

6. **Paridade com helper/presenter**
   - para o mesmo caso, comparar `response.context["doctor_report_text"]` com `prepare_doctor_case_report(case).presenter.build_text_report()` ou API equivalente;
   - isso deve provar que o dashboard não montou texto paralelo.

7. **Escaping**
   - usar conteúdo `<script>alert("audit")</script>`;
   - assert string bruta não aparece como tag executável;
   - assert versão escapada aparece.

8. **Preservação de acesso**
   - manter/usar testes existentes que bloqueiam NIR no dashboard;
   - inspecionar que o template exige `show_dashboard_nav`.

Pelo menos um desses testes deve falhar antes da implementação porque o relatório ainda não existe. Registrar comando, nomes e motivo do RED.

Comando alvo sugerido:

```bash
uv run pytest apps/dashboard/tests/test_dashboard.py -k "DoctorReportAudit or doctor_report" -q
```

Ajuste o seletor ao nome real da nova classe/testes.

### GREEN

Implementar somente:

- helper canônico em `apps/doctor/reporting.py`;
- refactor mínimo de `apps/doctor/views.py`;
- preparação condicional em `dashboard_case_detail`;
- card colapsável no template compartilhado;
- testes necessários.

### REFACTOR

Depois dos testes alvo verdes:

- remover preparação duplicada e imports mortos de `apps/doctor/views.py`;
- usar nomes claros e tipos coerentes;
- manter helper coeso;
- evitar dataclass/abstrações além do necessário;
- confirmar DRY, YAGNI e ausência de código morto;
- rodar testes médicos direcionados para preservar a tela atual.

Comandos direcionados mínimos após GREEN:

```bash
uv run pytest apps/dashboard/tests/test_dashboard.py -k "DoctorReportAudit or doctor_report" -q
uv run pytest apps/doctor/tests/test_presenter.py apps/doctor/tests/test_views.py -q
```

## Checks de inspeção obrigatórios antes de concluir

Execute e cole os resultados relevantes no relatório:

```bash
rg -n "prepare_doctor_case_report|DoctorReportPresenter|build_text_report|prior_decision_display|prior_context" apps/doctor/reporting.py apps/doctor/views.py apps/dashboard/views.py
rg -n "CASE_READY_FOR_DOCTOR|doctor_report_text" apps/dashboard/views.py apps/dashboard/tests/test_dashboard.py
rg -n "Relatório automático apresentado ao médico|reconstruído|snapshot imutável|data-bs-toggle=\"collapse\"|aria-expanded=\"false\"|show_dashboard_nav and doctor_report_text" templates/intake/case_detail.html apps/dashboard/tests/test_dashboard.py
rg -n "doctor_report_text.*safe|safe.*doctor_report_text|mark_safe" templates/intake/case_detail.html apps/dashboard apps/doctor
rg -n "@login_required|@role_required\(\"manager\", \"admin\"\)|def dashboard_case_detail" apps/dashboard/views.py
rg -n "class Case\(|structured_data =|summary_text =|suggested_action =|CASE_READY_FOR_DOCTOR" apps/cases/models.py apps/pipeline/orchestrator.py
```

Também execute:

```bash
git diff --name-only "$BASE_REF"...HEAD
git status --short
```

Interpretação obrigatória no relatório:

- doctor e dashboard importam o helper, não duplicam preparação;
- dashboard chama `build_text_report()` pelo caminho canônico;
- `CASE_READY_FOR_DOCTOR` controla elegibilidade;
- template exige simultaneamente `show_dashboard_nav` e texto;
- collapse inicia fechado;
- nenhuma ocorrência de `safe`/`mark_safe` para o relatório;
- decorators manager/admin continuam presentes;
- nenhum model/migration/pipeline foi alterado;
- arquivos alterados correspondem ao escopo esperado.

## Critérios de sucesso binários

- [ ] `git status --short` inicial estava limpo.
- [ ] Baseline `uv run pytest` registrado antes de editar com exit code e resumo.
- [ ] Pelo menos um teste novo falhou no RED pelo motivo esperado.
- [ ] Helper compartilhado prepara o presenter e contexto de negativa anterior.
- [ ] Tela médica usa o helper sem regressão visível/funcional.
- [ ] Dashboard só gera relatório quando existe `CASE_READY_FOR_DOCTOR`.
- [ ] Manager e admin veem o card elegível.
- [ ] Card inicia recolhido com ARIA/target coerentes.
- [ ] Texto contém contexto e sete blocos canônicos.
- [ ] Aviso informa reconstrução e ausência de snapshot imutável.
- [ ] Template exige `show_dashboard_nav and doctor_report_text`.
- [ ] Conteúdo HTML-like é escapado e nenhum `safe` foi adicionado.
- [ ] NIR continua sem acesso ao dashboard/card.
- [ ] Nenhum model, migration, FSM, evento, prompt, policy, permissão, rota ou endpoint mudou.
- [ ] Nenhum snapshot ou JSON completo foi implementado.
- [ ] Checks `rg` foram executados e interpretados.
- [ ] Testes dashboard e doctor direcionados passam.
- [ ] Quality gate completo passa.
- [ ] Pytest final tem exit code 0, zero failures/errors e `passed_final >= passed_baseline`.
- [ ] `tasks.md` foi marcado somente após todos os gates.
- [ ] Relatório foi criado em `/tmp/dashboard-doctor-report-audit-view-slice-001-report.md`.
- [ ] Commit e push foram realizados somente após gates verdes.

## Gates de autoavaliação

Responder objetivamente no relatório:

1. Qual helper passou a ser a fonte única para preparar o presenter em doctor e dashboard?
2. Quais cinco entradas do `Case`/contexto alimentam o presenter?
3. Como `prior_context` e `prior_decision_display` da tela médica foram preservados?
4. Qual teste prova paridade entre `doctor_report_text` e `build_text_report()` canônico?
5. Por que o gate usa `CASE_READY_FOR_DOCTOR` em vez de status ou presença de artefatos?
6. Qual teste prova que caso com artefatos, mas sem handoff, não mostra o card?
7. O collapse inicia realmente fechado? Quais atributos/classes provam isso?
8. Onde a UI declara que o relatório é reconstruído e não snapshot imutável?
9. Como o template compartilhado impede exibição no contexto NIR?
10. Qual teste prova escaping de HTML/script-like text?
11. Os decorators `manager`/`admin` e testes de acesso foram preservados?
12. Algum model, migration, FSM, evento, prompt, policy, URL ou endpoint mudou? A resposta esperada é não.
13. Algum JSON completo ou snapshot foi implementado? A resposta esperada é não.
14. Quais arquivos foram alterados? Algum fora da lista esperada? Por quê?
15. Quais foram os resumos e exit codes do pytest baseline e final? `passed_final >= passed_baseline`?

## Relatório obrigatório

Criar exatamente:

```text
/tmp/dashboard-doctor-report-audit-view-slice-001-report.md
```

Estrutura mínima obrigatória:

```markdown
# Relatório do slice

## Status
Status: COMPLETE | INCOMPLETE

## Matriz requisito → arquivo(s) → teste(s)

## BASE_REF e árvore inicial

## RED
- comando, exit code, testes falhando e motivo esperado

## GREEN
- comandos e resultados

## REFACTOR

## Snippets antes/depois

## Checks de inspeção
- comandos `rg`, resultados e interpretação

## Pytest baseline vs final
- baseline: exit code, passed, failed, errors
- final: exit code, passed, failed, errors
- comparação passed_final >= passed_baseline

## Quality gate completo

## Gates de autoavaliação

## Riscos/limitações
- declarar explicitamente que é reconstrução atual, não snapshot

## Handoff para verificador
- arquivos alterados
- comandos exatos para rerun
- checklist R1..R8
- riscos/limitações
```

A resposta final do implementador deve conter:

```text
REPORT_PATH=/tmp/dashboard-doctor-report-audit-view-slice-001-report.md
```

E deve parar para revisão do planner.

## Prompt pronto para implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md and openspec/changes/dashboard-doctor-report-audit-view/{proposal.md,design.md,tasks.md,specs/dashboard-case-audit-report/spec.md,slices/slice-001-reconstructed-doctor-report-dashboard-detail.md} completely before editing. Also inspect apps/cases/models.py, apps/pipeline/prior_case.py, apps/doctor/presenters.py, apps/doctor/views.py, apps/dashboard/views.py, templates/doctor/decision.html, templates/intake/case_detail.html and apps/dashboard/tests/test_dashboard.py.

Implement ONLY Slice 001. Follow the DeepSeek4-Flash protocol literally: clean initial tree, BASE_REF, full pytest baseline before edits, RED real, GREEN mínimo, REFACTOR, inspection checks, complete quality gate and pytest baseline-vs-final comparison. If any required test/check/gate is absent or failing, if final pytest has any failure/error or nonzero exit code, or if passed_final < passed_baseline, report INCOMPLETE; do not update tasks.md and do not commit/push.

Deliver one lean vertical flow: shared canonical report preparation in apps/doctor/reporting.py; doctor view refactored to use it without behavior change; dashboard case detail reconstructs DoctorReportPresenter.build_text_report() only when CASE_READY_FOR_DOCTOR exists; shared intake template shows a manager/admin-only Bootstrap Collapse titled “Relatório automático apresentado ao médico (reconstruído)”, closed by default, with disclosure that it is reconstructed from stored artifacts and is not an immutable snapshot.

Use TDD and enforce clean code, DRY and YAGNI. Do not duplicate the seven report rules. Do not alter models, migrations, FSM, events, prompts, schemas, pipeline, policy, permissions, URLs, endpoints, dashboard list/search/metrics or doctor decision behavior. Do not persist snapshots and do not expose full JSON. Preserve Django autoescaping; never use safe/mark_safe for report text. Preserve @login_required and @role_required("manager", "admin").

Prefer touching only apps/doctor/reporting.py, apps/doctor/views.py, apps/dashboard/views.py, templates/intake/case_detail.html and apps/dashboard/tests/test_dashboard.py; justify every extra code/test file in the report.

Run exactly: uv run ruff check ., uv run ruff format --check ., uv run mypy ., uv run pytest. The full final pytest must have exit code 0, zero failures/errors and passed count >= baseline. Update tasks.md only after every criterion passes. Create /tmp/dashboard-doctor-report-audit-view-slice-001-report.md with evidence, commit and push, reply with REPORT_PATH, then STOP for planner review.
```
