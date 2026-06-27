# Slice 001: Detalhe único do scheduler + mensagem ao NIR em `Processados Hoje`

## Handoff para implementador LLM com contexto zero

Você está no projeto ATS Web, um monolito Django SSR. Antes de codar, leia integralmente:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `openspec/changes/fix-scheduler-processed-detail-and-history-tab/proposal.md`
4. `openspec/changes/fix-scheduler-processed-detail-and-history-tab/design.md`
5. `openspec/changes/fix-scheduler-processed-detail-and-history-tab/tasks.md`
6. Este arquivo
7. Código atual em:
   - `apps/scheduler/views.py`
   - `apps/scheduler/urls.py`
   - `templates/scheduler/context_detail.html`
   - `templates/scheduler/_queue_content.html`
   - `templates/intake/case_detail.html` apenas para entender o que NÃO deve ser renderizado pelo scheduler
   - `templates/cases/_communication_thread.html`
   - `apps/scheduler/tests/test_views.py`

Implemente **somente este slice**. Não faça a aba `Buscar caso antigo` neste slice; isso é Slice 002.

Use metodologia TDD obrigatória: **RED → GREEN → REFACTOR**. Primeiro escreva testes falhando para o comportamento alvo, depois implemente o mínimo necessário e só então refatore localmente.

Aplique clean code, DRY local e YAGNI:

- nomes claros;
- funções pequenas/coesas;
- sem duplicar regra de negócio de comunicação ou menções;
- sem refactor amplo de templates NIR/dashboard;
- sem migrations;
- sem novo model/tabela;
- sem alteração de FSM.

## Contexto do problema

Hoje, o agendador abre um caso da aba `Processados Hoje` por:

```text
/scheduler/processed/<case_id>/
```

A view `scheduler_processed_detail` renderiza `templates/intake/case_detail.html`, que é o detalhe operacional do NIR. Isso faz o scheduler ver linguagem/ações de NIR, como `Reenviar caso corrigido`, e não mostra de forma consistente o CTA `Comunicar NIR` que aparece no detalhe vindo da busca histórica.

Já existe um template mais adequado ao scheduler:

```text
templates/scheduler/context_detail.html
```

Ele é usado por `scheduler_context_detail` para contexto por notificação e busca histórica.

## Objetivo do slice

Entrega vertical:

```text
Agendador abre Processados Hoje
→ clica Ver detalhes
→ vê o mesmo detalhe read-only de scheduler usado na busca histórica/contextual
→ não vê ações do NIR
→ vê thread de comunicação
→ consegue enviar mensagem operacional ao NIR pelo CTA Comunicar NIR
→ mensagem cria CaseCommunicationMessage/notificação @nir
→ Case.status não muda
```

## Escopo funcional

### R1. `scheduler_processed_detail` usa detalhe do scheduler

Alterar `apps/scheduler/views.py::scheduler_processed_detail` para renderizar:

```text
templates/scheduler/context_detail.html
```

ou helper/template scheduler equivalente, mas **não** `templates/intake/case_detail.html`.

Manter autorização existente:

- login obrigatório;
- active role `scheduler`;
- `scheduler=request.user`;
- `appointment_status__in=["confirmed", "denied"]`.

Não restringir o detalhe ao dia atual.

### R2. Um único caminho de contexto para detalhe scheduler

Preferir criar helper interno em `apps/scheduler/views.py`, por exemplo:

```python
def _build_scheduler_detail_context(...):
    ...
```

O helper deve ser usado por:

- `scheduler_context_detail`, quando possível;
- `scheduler_processed_detail`.

Não precisa ser um helper perfeito/global. O objetivo é reduzir duplicação local, não refatorar o sistema inteiro.

### R3. `Comunicar NIR` aparece em caso processado hoje

No detalhe scheduler de caso em escopo histórico/processado, exibir o bloco:

```text
📩 Comunicar NIR
```

A regra deve cobrir casos aceitos para agendamento já processados:

```text
doctor_decision == "accept"
doctor_admission_flow == "scheduled"
appointment_status in {"confirmed", "denied", "cancelled"}
```

O helper existente `_is_scheduler_historical_case(case)` já representa esse escopo. Reutilize-o.

Se hoje o bloco só aparece quando `case.status == CLEANED`, ampliar para aparecer quando `_is_scheduler_historical_case(case)` for verdadeiro.

### R4. Evitar formulário duplicado/confuso

Quando o CTA específico `Comunicar NIR` estiver visível, preferir não mostrar o formulário genérico da thread de comunicação.

Comportamento sugerido:

```python
can_message_nir = _is_scheduler_historical_case(case)
can_post_communication = case.status != CaseStatus.CLEANED and not can_message_nir
show_historical_message_nir = can_message_nir
```

Para casos contextuais por notificação que ainda não são históricos, manter a resposta genérica se `case.status != CLEANED`.

### R5. Reusar endpoint de mensagem ao NIR

Reusar a rota existente:

```text
scheduler:historical_message_nir
```

Ela deve continuar:

- aceitando apenas POST;
- validando escopo histórico scheduler;
- garantindo `@nir`;
- preservando menções adicionais;
- chamando `post_case_communication_message(..., allow_cleaned=True)`;
- não alterando `Case.status`.

Se for necessário ajustar alguma validação para suportar casos processados hoje ainda não `CLEANED`, faça o mínimo e cubra com testes.

### R6. Ações NIR não aparecem

O detalhe scheduler aberto por `Processados Hoje` não deve conter:

- `Reenviar caso corrigido`;
- `Confirmar Recebimento`;
- `Novo Encaminhamento` como ação principal de NIR;
- `Registrar intercorrência`;
- formulários de anexo/supressão/complemento do NIR;
- `scheduler:submit` ou formulário de confirmar/negar agendamento.

## Fora de escopo

Não implementar neste slice:

- terceira aba `Buscar caso antigo`;
- renome de `context_detail.html`;
- novo template grande;
- alterações em views/templates do NIR;
- novo endpoint de comunicação;
- novo model/tabela;
- migrations;
- alterações de FSM;
- busca avançada/paginação/export.

## Arquivos esperados

Idealmente tocar apenas:

1. `apps/scheduler/views.py`
2. `templates/scheduler/context_detail.html` se necessário
3. `apps/scheduler/tests/test_views.py`
4. `openspec/changes/fix-scheduler-processed-detail-and-history-tab/tasks.md`

Se precisar tocar mais arquivos, justificar no relatório antes/depois.

## TDD obrigatório

Adicione testes falhando antes da implementação.

### Testes mínimos sugeridos

1. `test_scheduler_processed_detail_uses_scheduler_template_not_nir_actions`
   - cria caso processado pelo scheduler logado;
   - GET `/scheduler/processed/<case_id>/` retorna 200;
   - conteúdo contém elementos do detalhe scheduler, por exemplo `Contexto do caso` ou `Comunicação operacional`;
   - conteúdo **não** contém `Reenviar caso corrigido`;
   - conteúdo **não** contém `Confirmar Recebimento`.

2. `test_scheduler_processed_detail_shows_message_nir_cta`
   - caso em escopo histórico scheduler/processado hoje;
   - GET detalhe;
   - assert contém `Comunicar NIR` e `Enviar mensagem ao NIR`.

3. `test_scheduler_processed_detail_message_nir_creates_message_without_status_change`
   - abre caso processado hoje, preferencialmente ainda `WAIT_R1_CLEANUP_THUMBS` ou status final não `CLEANED` se fixture permitir;
   - POST em `scheduler:historical_message_nir` com body sem `@nir`;
   - assert cria `CaseCommunicationMessage`;
   - assert corpo contém `@nir`;
   - assert `Case.status` permanece igual.

4. `test_scheduler_processed_detail_message_nir_preserves_additional_mentions`
   - body com `@medico`/`@doctor` ou `@username` adicional;
   - assert menção adicional permanece no corpo salvo.

5. `test_scheduler_processed_detail_still_404_for_other_scheduler_case`
   - preservar teste existente/ajustar se necessário.

6. `test_scheduler_context_detail_for_notification_still_allows_generic_reply_when_not_historical`
   - se já houver teste equivalente, mantenha-o passando;
   - garante que o ajuste para esconder formulário genérico não quebrou casos contextuais não históricos.

### Regressões importantes

- Não remover testes existentes de busca histórica/mensagem NIR.
- Não relaxar autorização por UUID.
- Não permitir mensagem histórica em caso fora do escopo scheduler.

## Critérios de aceitação do slice

- [ ] TDD RED → GREEN → REFACTOR documentado no relatório.
- [ ] `scheduler_processed_detail` não renderiza `templates/intake/case_detail.html`.
- [ ] Detalhe de `Processados Hoje` usa o template scheduler.
- [ ] Detalhe de `Processados Hoje` não mostra ações do NIR.
- [ ] Detalhe de `Processados Hoje` mostra `Comunicar NIR` para caso em escopo.
- [ ] POST de mensagem ao NIR funciona a partir de caso processado hoje.
- [ ] Mensagem garante `@nir`, preserva menções adicionais e não muda status.
- [ ] Detalhe contextual por notificação continua funcionando.
- [ ] Nenhuma migration criada.
- [ ] Sem novo estado FSM.
- [ ] `tasks.md` atualizado marcando este slice ao concluir.
- [ ] Quality gate executado.
- [ ] Relatório temporário criado e informado via `REPORT_PATH`.

## Gates de autoavaliação

Responder no relatório:

1. Qual template `scheduler_processed_detail` renderiza depois da mudança?
2. Que teste prova que `Reenviar caso corrigido` não aparece para scheduler?
3. Que teste prova que `Comunicar NIR` aparece em caso de `Processados Hoje`?
4. Que teste prova que a mensagem ao NIR não altera `Case.status`?
5. O formulário genérico de comunicação aparece junto com `Comunicar NIR`? Se sim, por quê? Se não, qual regra controla?
6. Alguma autorização foi relaxada? Esperado: não.
7. Alguma migration/FSM/model foi criado/alterado? Esperado: não.
8. Quais comandos de validação foram executados?

## Relatório obrigatório

Criar relatório markdown temporário em:

```text
/tmp/fix-scheduler-processed-detail-and-history-tab-slice-001-report.md
```

O relatório deve conter:

- resumo da mudança;
- arquivos tocados;
- evidência TDD RED/GREEN/REFACTOR;
- snippets antes/depois dos pontos principais;
- resposta aos gates de autoavaliação;
- comandos de validação e resultados;
- riscos/observações.

Responder ao planner com:

```text
REPORT_PATH=/tmp/fix-scheduler-processed-detail-and-history-tab-slice-001-report.md
```

## Prompt pronto para implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md and openspec/changes/fix-scheduler-processed-detail-and-history-tab/{proposal.md,design.md,tasks.md,slices/slice-001-unified-scheduler-detail-message-nir.md}.
Implement ONLY Slice 001.
Use TDD: write failing tests first for scheduler_processed_detail using the scheduler template, hiding NIR actions, showing Comunicar NIR, and posting message to NIR without status change. Then implement the minimum change.
Keep it lean: prefer apps/scheduler/views.py, templates/scheduler/context_detail.html if needed, apps/scheduler/tests/test_views.py, and tasks.md only.
Do not implement the historical search tab UI; that is Slice 002.
Do not create migrations, models, FSM states, new endpoints or broad refactors.
Apply clean code, DRY local helper if useful, and YAGNI.
Run quality gate from AGENTS.md, update tasks.md, create /tmp/fix-scheduler-processed-detail-and-history-tab-slice-001-report.md with before/after snippets and gate answers, commit and push, then reply only with REPORT_PATH and stop.
```
