# Slice 004: Badges persistidos acompanham o caso no CHD

## Status

- [ ] Pendente

## Handoff para implementador LLM com contexto zero

Pré-condições: Slices 001–003 concluídos. O caso já persiste `priority_signals`; helper e partial compartilhados existem; fila e relatório médico mostram os sinais. Este slice deve propagar exatamente a mesma projeção ao CHD/agendador sem alterar workflow.

O app scheduler possui:

- fila pendente e processados/ciências em `templates/scheduler/_queue_content.html`;
- `_build_case_card()` e `_build_processed_card()`;
- confirmação em `templates/scheduler/confirm.html` via `_build_confirm_context()`;
- detalhe read-only/processado em `templates/scheduler/context_detail.html` via `_build_scheduler_detail_context()`;
- locks e formulários sensíveis que não podem ser alterados.

Leia todos os artefatos do change, relatórios anteriores, `apps/scheduler/views.py`, templates e `apps/scheduler/tests/test_views.py` antes de editar.

## Protocolo obrigatório para implementador DeepSeek4-Flash

Este slice será implementado por um modelo rápido e com tendência a concluir cedo demais. Portanto, siga este protocolo literalmente. **Se qualquer item abaixo falhar, o slice está INCOMPLETO**: não marque `tasks.md`, não faça commit/push e responda com bloqueio + evidência.

1. **Plano antes de editar**: escreva no relatório uma mini matriz `Requisito → arquivo(s) → teste(s)`. Não implemente requisito sem teste ou justificativa explícita.
2. **Baseline de pytest antes de editar**: registre `BASE_REF=$(git rev-parse HEAD)` e rode `uv run pytest` no estado inicial limpo. Cole no relatório o exit code e a linha de resumo. Se houver `failed/error` no baseline, pare e reporte INCOMPLETE/BLOQUEADO antes de codar.
3. **RED real**: crie/ajuste testes primeiro e rode o subconjunto alvo. Pelo menos um teste novo deve falhar pelo motivo esperado. Se o teste passar antes da implementação, ele não prova o comportamento; corrija o teste.
4. **GREEN mínimo**: implemente somente o necessário para os testes do slice passarem. Não faça refactor amplo, não toque em apps fora do escopo e não antecipe slices futuros.
5. **Verificação por inspeção**: além dos testes, rode buscas `rg`/inspeções descritas neste slice para comprovar os contratos críticos do slice.
6. **Quality gate completo e comparação pytest**: execute exatamente `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy .` e `uv run pytest`. O `uv run pytest` final deve ter exit code 0, zero failures/errors e contagem `passed` maior ou igual ao baseline. Se `failed > 0`, `errors > 0`, exit code != 0, ou `passed_final < passed_baseline`, o slice está INCOMPLETO.
7. **Relatório com evidência, não opinião**: cole comandos executados, exit codes, linhas de resumo do pytest baseline/final, testes RED/GREEN, snippets antes/depois e respostas objetivas aos gates. Inclua também `Handoff para verificador` com: arquivos alterados, comandos exatos para rerun, riscos/limitações e checklist dos requisitos R1..Rn. Inclua uma seção final `Status: COMPLETE` somente se todos os critérios estiverem comprovados.

## Objetivo do slice

```text
médico aceita caso sinalizado
→ caso entra na fila/ciência do CHD
→ card mostra os mesmos badges persistidos
→ confirmação mostra badges no topo
→ detalhe processado/read-only preserva badges
→ agenda/locks/decisão permanecem iguais
```

## Requisitos funcionais

### R1. Contextos usam somente persistência

Adicionar `priority_signal_badges` aos contextos scheduler reutilizando `build_priority_signal_badges(case.priority_signals)`.

Abrangência:

- `_build_case_card()`;
- `_build_processed_card()`;
- `_build_confirm_context()`;
- `_build_scheduler_detail_context()`.

Não redetectar `extracted_text`, não importar detector e não duplicar mapping.

### R2. Fila CHD

Em `templates/scheduler/_queue_content.html`, incluir partial compartilhado nos cards que representam casos:

- pendentes `WAIT_APPT`;
- ciências operacionais quando houver sinais;
- intercorrências operacionais quando houver sinais;
- processados/ciências confirmadas quando o template renderizar esses cards.

Badges devem ficar próximos ao nome/meta e antes de diagnóstico/decisão, sem remover badges de dias em tela, orientação médica ou intercorrência.

### R3. Confirmação

Em `templates/scheduler/confirm.html`, exibir badges no topo do card “Dados do Caso”, antes da tabela ou imediatamente após o título.

Se `confirm_post_schedule_issue.html` reutiliza contexto e representa o mesmo caso, incluir ali somente se for necessário para manter continuidade; justificar/testar. Não alterar campos, token de lock, mensagens ou ação POST.

### R4. Detalhes

Em `templates/scheduler/context_detail.html`, exibir badges no card superior do caso. Deve funcionar para:

- detalhe processado hoje;
- detalhe histórico/read-only autorizado;
- detalhe contextual por notificação.

Não alterar autorização ou visibilidade de PDF/comunicação.

### R5. Consistência e vazio

- labels, ordem e classes devem vir do helper compartilhado;
- corpo estranho e cáustico mantêm mesma ênfase;
- caso vazio/malformado não mostra container nem quebra;
- detail com conteúdo malicioso continua escapado pelo template.

### R6. Nenhuma automação operacional

Proibido:

- reordenar fila por sinal;
- filtrar automaticamente eco/dilatação;
- atribuir scheduler/médico;
- validar turno/dia/local;
- alterar formulário, FSM, locks, permissões ou contadores;
- alterar modelos/migration/pipeline/doctor/intake.

## Arquivos esperados

1. `apps/scheduler/views.py`
2. `templates/scheduler/_queue_content.html`
3. `templates/scheduler/confirm.html`
4. `templates/scheduler/context_detail.html`
5. `apps/scheduler/tests/test_views.py`
6. opcional `templates/scheduler/confirm_post_schedule_issue.html` somente com justificativa/teste
7. `tasks.md` somente ao concluir

Não alterar partial compartilhado salvo bug comprovado por teste que afete todos os consumidores; se ocorrer, pare e peça decisão em vez de ampliar silenciosamente.

## TDD obrigatório

### RED

Criar testes antes de produção para:

1. card pendente mostra múltiplos labels na ordem canônica;
2. card processado/ciência aplicável preserva labels;
3. confirmação mostra badges antes dos dados/diagnóstico;
4. detalhe processado e contextual mostra badges no topo;
5. caso sem sinais não mostra container;
6. payload malformado não causa 500;
7. conteúdo malicioso é escapado;
8. lock token/form action/campos existentes permanecem;
9. permissões scheduler existentes continuam bloqueando papel indevido.

Rodar RED focado:

```bash
uv run pytest apps/scheduler/tests/test_views.py -q
```

Se o arquivo inteiro for muito demorado, rodar classe nova para RED/GREEN, mas o arquivo completo e full suite são obrigatórios antes de concluir.

### GREEN

Adicionar somente contexto e includes necessários.

### REFACTOR

- Um helper/import compartilhado, sem mapping local.
- Evitar repetir montagem em cada view se builders existentes resolvem.
- Não criar nova partial scheduler para badges.
- Não modificar lógica de locks/forms.
- Manter templates legíveis e includes próximos ao título.

## Checks de inspeção obrigatórios antes de concluir

```bash
rg -n "build_priority_signal_badges|priority_signal_badges" apps/scheduler/views.py

rg -n "cases/_priority_signals.html" templates/scheduler

rg -n "lock_token|work-lock-config|scheduler_confirm|role_required\(\"scheduler\"\)" \
  apps/scheduler/views.py templates/scheduler/confirm.html

rg -n "priority_signals|resolve_priority_signals|extracted_text" apps/scheduler/views.py templates/scheduler

rg -n "order_by\(|regulation_days_on_screen|pending_count|total_notice_count" apps/scheduler/views.py

git diff --check
git status --short
```

Interpretar:

- projeção compartilhada é usada;
- includes cobrem fila/confirm/detalhe;
- `resolve_priority_signals` não aparece no scheduler;
- decorators, lock token, ordenação e contadores permanecem;
- nenhuma lógica de turno foi adicionada.

## Critérios de sucesso binários

- [ ] Baseline e RED real registrados.
- [ ] Todos os contextos exigidos recebem badges do campo persistido.
- [ ] Fila pendente e cards posteriores aplicáveis mostram sinais.
- [ ] Confirmação mostra badges no topo.
- [ ] Detalhe processado/contextual mostra badges.
- [ ] Ordem/classes são compartilhadas; alertas mantêm igualdade.
- [ ] Vazio/malformado não quebra/não renderiza container.
- [ ] Escaping testado.
- [ ] Locks, forms, permissões, ordenação e contadores preservados.
- [ ] Nenhuma automação de direcionamento/agenda foi criada.
- [ ] Nenhum app fora do scheduler foi alterado indevidamente.
- [ ] Inspeções e full quality gate verdes; final >= baseline.
- [ ] Relatório/task/commit/push completos.

## Gates de autoavaliação

1. Quais tipos de card scheduler mostram os badges?
2. Fila, confirmação e detalhe usam exatamente o mesmo helper/partial?
3. Alguma tela redetecta texto? Deve ser “não”.
4. Qual teste prova vazio/malformado?
5. Qual teste prova escaping?
6. Lock token e formulário permanecem intactos?
7. Ordenação/contadores mudaram? Deve ser “não”.
8. Foi adicionada regra de turno/atribuição/filtro? Deve ser “não”.
9. Algum arquivo extra foi tocado? Justifique.
10. O NIR foi antecipado? Deve ser “não”.

### Condições automáticas de INCOMPLETO

- protocolo/baseline/RED/quality gate sem evidência;
- qualquer tela exigida sem badge;
- scheduler redetectar texto ou duplicar mapping;
- caso vazio gerar markup vazio visível ou 500;
- lock, token, formulário, permissão, ordenação ou contador mudar;
- regra de turno/atribuição/filtro ser criada;
- doctor/intake/model/pipeline ser alterado sem blocker aprovado;
- teste/lint/mypy falhar ou final < baseline;
- relatório/handoff ausente;
- task/commit/push antes de todos os critérios.

## Relatório obrigatório

Criar:

```text
/tmp/eda-priority-signals-slice-004-report.md
```

Incluir matriz R1–R6, baseline, RED/GREEN/REFACTOR, snippets dos builders/includes, evidência HTML de fila/confirm/detalhe, regressão de lock/permissão, inspeções, full gate, rerun e handoff para verificador.

## Prompt pronto para implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md, all eda-priority-signals-across-workflow artifacts and completed Slice 001–003 reports. Inspect scheduler views, queue/confirm/context-detail templates and tests. Implement ONLY Slice 004.

Follow the DeepSeek4-Flash protocol literally: clean full pytest baseline, real RED, minimal GREEN, clean DRY/YAGNI refactor, mandatory rg inspections, full quality gate and passed_final >= passed_baseline. Missing/failing evidence means INCOMPLETE; do not update tasks.md or commit/push.

Propagate the persisted priority signals to scheduler/CHD queue cards, confirmation and read-only/processed details using only the shared badge projection and partial. Preserve empty/malformed safety and escaping. Do not redetect extracted text or duplicate mappings. Do not change locks, forms, permissions, FSM, queue ordering, counters, routing, assignment or schedule/shift validation. Do not touch NIR yet.

Run uv run ruff check .; uv run ruff format --check .; uv run mypy .; uv run pytest. Mark only Slice 004 after all criteria pass. Create /tmp/eda-priority-signals-slice-004-report.md with evidence and Handoff para verificador. Commit/push only if COMPLETE. Reply REPORT_PATH=/tmp/eda-priority-signals-slice-004-report.md and STOP.
```
