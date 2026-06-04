# Slice 004: NIR confirma ciência e encerra ciclo

## Handoff para implementador LLM com contexto zero

Este slice fecha o ciclo operacional após o agendador responder a intercorrência. O caso estará em `WAIT_R1_CLEANUP_THUMBS` com `post_schedule_issue_status="responded"` e deve aparecer para o NIR confirmar ciência, retornando a `CLEANED`.

Leia:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `openspec/changes/post-schedule-intercurrence/proposal.md`
4. `openspec/changes/post-schedule-intercurrence/design.md`
5. `openspec/changes/post-schedule-intercurrence/tasks.md`
6. Slices 001–003
7. Este arquivo
8. `apps/intake/views.py`, templates de detalhe/confirm receipt e testes de receipt/lease

Implemente **somente este slice** com TDD: RED → GREEN → REFACTOR.

## Objetivo do slice

Permitir que NIR veja a resposta do agendador a uma intercorrência, confirme ciência e encerre o ciclo:

```text
WAIT_R1_CLEANUP_THUMBS + issue responded
→ NIR abre detalhe operacional
→ vê resposta do agendador e estado atual do agendamento
→ confirma recebimento
→ serviço acknowledge limpa issue ativa
→ cleanup existente leva caso para CLEANED
```

## Escopo funcional

- Ajustar detalhe NIR para renderizar bloco específico de intercorrência respondida.
- Reusar confirmação de recebimento existente, chamando serviço de acknowledge quando houver issue `responded`.
- Preservar lock NIR de confirmação já existente.
- Após confirmação, caso retorna a `CLEANED` e `post_schedule_issue_status` fica vazio/none.
- Impedir abertura de nova intercorrência enquanto ainda estiver aguardando ciência.
- Mostrar resultado da ação do agendador:
  - cancelado;
  - reagendado com nova data/local;
  - mantido;
  - solicitação negada.

## Fora de escopo

- Busca/abertura NIR já feita no Slice 002.
- Resposta do agendador já feita no Slice 003.
- Timeline visual completa; isso fica no Slice 005.
- Dashboard avançado.

## Arquivos prováveis

1. `apps/intake/views.py`
2. `templates/intake/case_detail.html` ou include relacionado
3. `apps/intake/tests/test_post_schedule_issue_ack.py` ou testes existentes de receipt
4. talvez `apps/cases/services.py` para ajuste pequeno
5. `openspec/changes/post-schedule-intercurrence/tasks.md` ao final

## Plano TDD obrigatório

### RED

Criar testes:

1. Caso `WAIT_R1_CLEANUP_THUMBS` com issue `responded` aparece no detalhe NIR com bloco de intercorrência.
2. Bloco mostra motivo original do NIR e resposta do agendador.
3. Para `reschedule`, mostra nova data/local.
4. Para `cancel`, mostra que agendamento foi cancelado.
5. POST confirmar recebimento em issue `responded` chama acknowledge e retorna caso para `CLEANED`.
6. Evento `POST_SCHEDULE_ISSUE_ACKNOWLEDGED` é criado.
7. Após confirmação, `post_schedule_issue_status` fica vazio/none.
8. Enquanto issue está `responded`, a busca do Slice 002 não permite abrir nova intercorrência.
9. Confirmação normal de casos sem intercorrência continua funcionando.
10. POST sem lock NIR válido continua bloqueado, se o fluxo atual exigir lock.

## GREEN

- Integrar com o caminho existente de confirmação de recebimento em vez de criar endpoint duplicado.
- Chamar serviço de domínio para acknowledge.
- Manter mensagens e templates simples.

## REFACTOR

- Se o template ficar grande, extrair include pequeno para `_post_schedule_issue_result.html`.
- Não duplicar lógica de apresentação em múltiplas views; passe dados claros no contexto.

## Critérios de aceitação

- [ ] NIR vê resposta do agendador antes de confirmar.
- [ ] Confirmação de recebimento encerra issue ativa e retorna caso a `CLEANED`.
- [ ] Evento de ciência é registrado.
- [ ] Não é possível abrir nova intercorrência enquanto a anterior aguarda ciência.
- [ ] Fluxo sem intercorrência de confirmação NIR permanece coerente.
- [ ] Lock NIR existente continua respeitado.

## Gates de autoavaliação

Responder no relatório:

1. O endpoint de confirmação foi reutilizado ou duplicado? Justifique.
2. Como o template distingue resultado normal de resultado de intercorrência?
3. Como o código garante que nova intercorrência só é possível após ciência?
4. O fluxo sem intercorrência continuou verde?
5. Onde o evento de ciência é criado?

## Comandos de validação mínimos

```bash
uv run pytest apps/intake/tests -q
uv run pytest apps/cases/tests -q
uv run ruff check apps/intake apps/cases
uv run ruff format --check apps/intake apps/cases
uv run mypy apps/intake apps/cases
```

Quality gate completo, se possível:

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
```

## Relatório final obrigatório

Criar:

```text
/tmp/ats-web-slice-004-nir-acknowledge-issue-report.md
```

Incluir resumo, arquivos, snippets, testes, validações, riscos, atualização de `tasks.md`, commit hash e push.

Resposta final:

```text
REPORT_PATH=/tmp/ats-web-slice-004-nir-acknowledge-issue-report.md
```

Pare e peça confirmação antes do próximo slice.

## Prompt pronto para implementador

```text
Read AGENTS.md, PROJECT_CONTEXT.md and openspec/changes/post-schedule-intercurrence through Slice 004. Implement ONLY Slice 004 using TDD. Integrate post-schedule issue response into NIR case detail and existing confirm receipt flow: show scheduler response, require existing NIR lock behavior, acknowledge issue via domain service, clear active issue and return case to CLEANED, preserving normal confirmation flow. Keep code simple, DRY and YAGNI. Run validations, update tasks.md, create /tmp/ats-web-slice-004-nir-acknowledge-issue-report.md, commit and push, reply REPORT_PATH and stop.
```
