<!-- markdownlint-disable MD013 -->

# Slice 001: Cards do dashboard — badge compacto + próximo passo

## Handoff para implementador LLM com contexto zero

Leia antes de editar:

- `AGENTS.md`
- `PROJECT_CONTEXT.md`
- `openspec/changes/dashboard-badge-progress-ux/proposal.md`
- `openspec/changes/dashboard-badge-progress-ux/design.md`
- `openspec/changes/dashboard-badge-progress-ux/tasks.md`
- este arquivo

Estado atual relevante:

- A lista de cards do dashboard é renderizada por `templates/dashboard/_case_list.html`.
- Cada item vem de `_enrich_case()` em `apps/dashboard/views.py`.
- O badge principal usa `item.result_label` e `item.result_css`.
- `_compute_result(case)` usa `ADMISSION_FLOW_MAP`; para `ward_icu_backup`, o texto completo é longo e causa overflow/sobreposição em mobile.
- O template usa colunas Bootstrap `col-8` para badge e `col-4` para data/hora, o que deixa pouco espaço no mobile.

Objetivo exato:

```text
Manager/admin abre o dashboard no mobile
→ cards de pacientes mostram badge principal compacto sem sobrepor data/hora
→ cards também mostram sub-badge com próximo passo operacional pendente
→ desktop continua legível
→ filtros/queries/permissões/FSM permanecem inalterados
```

Limites de escopo:

- Não alterar models, migrations, FSM, permissões, queries ou filtros.
- Não alterar labels completos do formulário do médico (`ADMISSION_FLOW_CHOICES`/opções de decisão).
- Não implementar correção do card `Resultado Final`; isso é Slice 002.
- Não adicionar JS, framework frontend ou screenshot tests.

## Protocolo obrigatório para implementador DeepSeek4-Flash

Este slice será implementado por um modelo rápido e com tendência a concluir cedo demais. Portanto, siga este protocolo literalmente. **Se qualquer item abaixo falhar, o slice está INCOMPLETO**: não marque `tasks.md`, não faça commit/push e responda com bloqueio + evidência.

1. **Plano antes de editar**: escreva no relatório uma mini matriz `Requisito → arquivo(s) → teste(s)`. Não implemente requisito sem teste ou justificativa explícita.
2. **Baseline de pytest antes de editar**: registre `BASE_REF=$(git rev-parse HEAD)` e rode `uv run pytest` no estado inicial limpo. Cole no relatório o exit code e a linha de resumo. Se houver `failed/error` no baseline, pare e reporte INCOMPLETE/BLOQUEADO antes de codar.
3. **RED real**: crie/ajuste testes primeiro e rode o subconjunto alvo. Pelo menos um teste novo deve falhar pelo motivo esperado. Se o teste passar antes da implementação, ele não prova o comportamento; corrija o teste.
4. **GREEN mínimo**: implemente somente o necessário para os testes do slice passarem. Não faça refactor amplo, não toque em apps fora do escopo e não antecipe slices futuros.
5. **Verificação por inspeção**: além dos testes, rode buscas `rg`/inspeções descritas neste slice para comprovar os contratos críticos do slice.
6. **Quality gate completo e comparação pytest**: execute exatamente `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy .` e `uv run pytest`. O `uv run pytest` final deve ter exit code 0, zero failures/errors e contagem `passed` maior ou igual ao baseline. Se `failed > 0`, `errors > 0`, exit code != 0, ou `passed_final < passed_baseline`, o slice está INCOMPLETO.
7. **Relatório com evidência, não opinião**: cole comandos executados, exit codes, linhas de resumo do pytest baseline/final, testes RED/GREEN, snippets antes/depois e respostas objetivas aos gates. Inclua também `Handoff para verificador` com: arquivos alterados, comandos exatos para rerun, riscos/limitações e checklist dos requisitos R1..Rn. Inclua uma seção final `Status: COMPLETE` somente se todos os critérios estiverem comprovados.

### Condições automáticas de INCOMPLETO

Marque como incompleto se ocorrer qualquer uma destas situações:

- teste planejado não foi escrito ou não foi executado;
- baseline de pytest antes de editar não foi executado ou não foi registrado com exit code e resumo;
- quality gate completo não foi executado;
- qualquer teste/lint/mypy falhou;
- pytest final teve exit code diferente de 0, `failed > 0` ou `errors > 0`;
- contagem final de `passed` ficou menor que a contagem baseline;
- relatório cita apenas número de `passed` sem registrar explicitamente zero failures/errors e exit code 0;
- `tasks.md` foi marcado apesar de falha ou pendência;
- contrato crítico do slice não foi verificado por teste ou inspeção;
- comportamento antigo que deveria ser preservado foi removido sem teste de regressão;
- labels completos do médico foram alterados;
- models/migrations/FSM/permissões/queries/filtros foram alterados;
- relatório temporário não foi criado no caminho exigido.

## Requisitos funcionais

### R1. Badge principal compacto para fluxo longo

Para casos aceitos com `doctor_admission_flow="ward_icu_backup"`, o card do dashboard deve renderizar um badge principal compacto, por exemplo:

```text
✓ Enfermaria + retaguarda UTI
```

Não deve renderizar no badge da lista o texto longo:

```text
✓ Vinda para enfermaria (para retaguarda em UTI)
```

O texto completo pode continuar existindo em outros contextos e não deve ser removido das opções do médico.

### R2. Próximo passo operacional como sub-badge

Adicionar ao item enriquecido um indicador secundário curto, por exemplo `next_step_label` e `next_step_css`, e renderizá-lo no card quando aplicável.

Cobrir no mínimo:

- `WAIT_DOCTOR` → `Pendente: médico`;
- `WAIT_APPT` ou preparação de agendamento (`DOCTOR_ACCEPTED`/`R3_POST_REQUEST`) com fluxo agendado → `Pendente: agendador`;
- `APPT_CONFIRMED`, `APPT_DENIED`, `R1_FINAL_REPLY_POSTED`, `WAIT_R1_CLEANUP_THUMBS` → `Pendente: NIR`;
- `CLEANED` → `Encerrado` ou sem sub-badge, desde que testado/justificado;
- `FAILED` → `Pendente: suporte` ou equivalente.

### R3. Layout mobile sem sobreposição de data/hora

Alterar `templates/dashboard/_case_list.html` para que a área de badges possa quebrar linha e não compartilhe largura crítica com a data/hora no mobile.

Aceitável:

- separar badges e data em colunas/linhas diferentes no mobile;
- usar `d-flex flex-wrap gap-1` para badges;
- aplicar classe dedicada de badge quebrável, por exemplo `badge-wrap`.

### R4. Desktop preservado

No desktop, o card deve continuar com leitura compacta e botão `Ver detalhes` alinhado à direita. Não remover dados existentes: paciente, registro, unidade, idade/gênero, data/hora, atenção necessária, botão.

### R5. Sem alteração de comportamento backend

Não alterar filtros, paginação, busca dinâmica, permissões ou queries. A mudança é de apresentação/presenter.

## Arquivos esperados

Idealmente tocar apenas:

1. `apps/dashboard/views.py`
2. `templates/dashboard/_case_list.html`
3. `apps/dashboard/tests/test_dashboard.py`
4. `static/css/app.css` se necessário para `badge-wrap`/layout mobile

Se tocar outros arquivos, justificar no relatório.

Arquivos proibidos neste slice:

- migrations;
- models;
- apps de doctor/intake/scheduler fora de testes estritamente necessários;
- templates de detalhe do caso (`templates/intake/case_detail.html`) — fica para Slice 002.

## TDD obrigatório

### RED

Adicionar testes antes da implementação, em `apps/dashboard/tests/test_dashboard.py`.

Testes mínimos sugeridos:

1. Caso com `doctor_decision="accept"` e `doctor_admission_flow="ward_icu_backup"` renderiza label compacto no card do dashboard e não renderiza o label longo como badge principal.
2. Caso `WAIT_APPT` com fluxo agendado renderiza sub-badge `Pendente: agendador`.
3. Caso `WAIT_R1_CLEANUP_THUMBS` renderiza sub-badge `Pendente: NIR`.
4. HTML da lista possui classe/estrutura de badges responsiva (`dashboard-case-badges` ou equivalente, `flex-wrap`/`badge-wrap`) e a data/hora fica fora do mesmo container estreito do badge principal.
5. Regressão: botão `Ver detalhes`, data/hora e badge `Atenção necessária` continuam presentes quando aplicável.

Rodar o subconjunto alvo e comprovar falha esperada antes de implementar.

### GREEN

Implementar o mínimo:

- helper de label compacto e/ou ajuste em `_compute_result()`;
- helper de próximo passo e inclusão em `_enrich_case()`;
- template renderizando badge principal e sub-badge com layout responsivo;
- CSS dedicado se Bootstrap puro não for suficiente.

### REFACTOR

Após testes passarem, revisar:

- nomes claros (`_compute_next_step`, `_compact_result_label` etc.);
- sem duplicação de mapas desnecessária;
- sem tocar regras de negócio;
- sem CSS global que quebre badges de outras telas.

## Checks de inspeção obrigatórios antes de concluir

Execute e cole resultado/resumo no relatório:

```bash
rg -n "ward_icu_backup|Enfermaria|retaguarda|Pendente: agendador|Pendente: NIR|next_step" apps/dashboard/views.py apps/dashboard/tests/test_dashboard.py templates/dashboard/_case_list.html
rg -n "dashboard-case-badges|badge-wrap|flex-wrap" templates/dashboard/_case_list.html static/css/app.css
rg -n "Vinda para enfermaria \(para retaguarda em UTI\)" apps/cases/admission.py apps/dashboard/views.py templates/dashboard/_case_list.html
```

Interpretação esperada:

- O texto completo ainda pode aparecer em `apps/cases/admission.py`.
- O texto completo não deve ser usado como badge principal no template da lista.
- Deve haver evidência de sub-badge/next step e layout responsivo.

## Critérios de sucesso binários

- [ ] Baseline `uv run pytest` registrado antes de editar.
- [ ] Pelo menos um teste novo falhou no RED pelo motivo esperado.
- [ ] Badge compacto é usado para `ward_icu_backup` na lista do dashboard.
- [ ] Texto completo das opções do médico foi preservado.
- [ ] Sub-badge de próximo passo aparece para agendador e NIR.
- [ ] Layout mobile evita badge/data na mesma largura crítica.
- [ ] Dados existentes do card foram preservados.
- [ ] Nenhum model/migration/FSM/permissão/query/filtro foi alterado.
- [ ] Checks `rg` foram executados e interpretados.
- [ ] Quality gate completo passou.
- [ ] `tasks.md` marcou somente este slice após todos os gates.
- [ ] Relatório temporário foi criado em `/tmp/dashboard-badge-progress-ux-slice-001-report.md`.
- [ ] Commit e push realizados após gates verdes.

## Gates de autoavaliação

Responder no relatório:

1. Qual helper/trecho gera o label compacto e como preserva o label completo do médico?
2. Qual helper/trecho gera o próximo passo?
3. Quais status foram cobertos para `Pendente: agendador` e `Pendente: NIR`?
4. Qual teste prova que o badge longo não aparece na lista como badge principal?
5. Qual teste prova que o sub-badge aparece?
6. Qual classe/estrutura impede sobreposição com data/hora em mobile?
7. Alguma query, migration, model, FSM ou permissão mudou? Se sim, por quê?
8. O relatório contém evidência RED, GREEN, baseline/final e checks `rg`?

## Relatório obrigatório

Criar exatamente:

```text
/tmp/dashboard-badge-progress-ux-slice-001-report.md
```

O relatório deve conter:

- Status: COMPLETE ou INCOMPLETE;
- matriz requisito → arquivo(s) → teste(s);
- baseline de pytest antes de editar;
- evidência RED;
- evidência GREEN;
- snippets antes/depois;
- checks de inspeção `rg` e interpretação;
- comparação pytest baseline vs final;
- quality gate completo;
- respostas aos gates de autoavaliação;
- handoff para verificador.

## Prompt pronto para implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md and openspec/changes/dashboard-badge-progress-ux/{proposal.md,design.md,tasks.md,slices/slice-001-dashboard-card-badges-next-step.md} first.
Implement ONLY Slice 001. Follow the DeepSeek4-Flash protocol in this file: plan, pytest baseline before editing, RED real, GREEN mínimo, inspection checks, full quality gate, pytest baseline-vs-final comparison and evidence report. If any required test/check/gate is missing or failing, if pytest final has any failure/error, or if passed_final < passed_baseline, report INCOMPLETE and do not update tasks.md or commit.
Use vertical slicing; avoid horizontal slicing by layer. Keep the slice lean and justify any extra file in the report.
Goal: dashboard mobile cards must use compact result badge for long ward/ICU-backup flow, must not overlap date/time, and must show a secondary next-step badge such as Pendente: agendador or Pendente: NIR.
Do not touch models, migrations, FSM, permissions, filters, dashboard queries, doctor decision labels, or templates for the case detail. Preserve existing card information and behavior.
Run quality gate exactly: uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
Update tasks.md only if all checks pass. Create /tmp/dashboard-badge-progress-ux-slice-001-report.md, commit and push, reply with REPORT_PATH and STOP for planner review.
```
