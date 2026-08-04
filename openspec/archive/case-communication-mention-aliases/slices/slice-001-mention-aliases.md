# Slice 001: Parser, notificações e microcopy para aliases pt-BR

## Contexto zero para implementador

Leia `AGENTS.md`, `PROJECT_CONTEXT.md`, `proposal.md`, `design.md`, `tasks.md` e este slice.

A comunicação operacional cria mensagens em `CaseCommunicationMessage`. Menções no corpo (`@doctor`, `@nir`, etc.) são parseadas por `apps/accounts/services.py::parse_mentions` e notificações in-app são criadas por `create_case_communication_notifications`.

Usuários querem usar aliases locais:

- `@medico` para médicos (`doctor`);
- `@chd` para agendamento (`scheduler`);
- `@supervisor` para supervisão (`manager`);
- `@nir` permanece igual.

## Objetivo

Entrega vertical:

```text
Usuário escreve @medico/@chd/@supervisor na comunicação operacional → parser resolve para papel canônico → UserNotification é criada para usuários ativos do papel → payload audita papel canônico → UI mostra exemplos
```

## Arquivos esperados

- `apps/accounts/services.py`
- `apps/accounts/tests/test_notifications.py`
- `templates/cases/_communication_thread.html`
- `openspec/changes/case-communication-mention-aliases/tasks.md`

## Requisitos

1. Criar mapa de aliases em `apps/accounts/services.py`:

```python
COMMUNICATION_MENTION_ROLE_ALIASES = {
    "nir": "nir",
    "doctor": "doctor",
    "medico": "doctor",
    "scheduler": "scheduler",
    "chd": "scheduler",
    "manager": "manager",
    "supervisor": "manager",
    "admin": "admin",
}
```

2. `parse_mentions()` deve:
   - ser case-insensitive;
   - retornar papéis canônicos em `role_tokens`;
   - manter usernames para tokens não reservados;
   - deduplicar aliases que apontam para o mesmo papel.

3. `create_case_communication_notifications()` deve funcionar sem mudança estrutural, usando `role_tokens` canônicos.

4. Payload de `CASE_COMMUNICATION_MESSAGE_POSTED` deve continuar usando `mentioned_roles` canônicos.

5. Atualizar microcopy em `templates/cases/_communication_thread.html` com exemplos:

```text
Use @nir, @medico, @chd ou @supervisor para notificar equipes.
```

Pode mencionar `@admin` também se couber.

## TDD obrigatório

Adicionar testes falhando antes da implementação:

1. Parser:
   - `@medico @chd @supervisor` retorna `{"doctor", "scheduler", "manager"}`.
   - aliases são case-insensitive: `@Medico @CHD @Supervisor`.
   - alias e canônico deduplicam: `@doctor @medico` retorna apenas `doctor`.

2. Serviço:
   - `@medico` cria notificação para usuário com papel `doctor`.
   - `@chd` cria notificação para usuário com papel `scheduler`.
   - `@supervisor` cria notificação para usuário com papel `manager`.

3. Integração/evento:
   - mensagem `@medico @chd @supervisor` gera payload com `mentioned_roles == ["doctor", "manager", "scheduler"]` ou comparação como set.

4. Template:
   - algum teste existente de tela com comunicação operacional deve verificar que aparecem `@medico`, `@chd` e `@supervisor`, ou documentar validação por render se não houver teste simples.

## Critérios de sucesso

- [ ] TDD seguido.
- [ ] Aliases resolvem para papéis canônicos.
- [ ] Notificações são criadas para destinatários corretos.
- [ ] Usernames não reservados continuam funcionando.
- [ ] Microcopy visível informa aliases.
- [ ] Sem migration.
- [ ] Quality gate passa.

## Gates de autoavaliação

Responder no relatório:

1. Qual mapa de aliases foi implementado?
2. O payload audita aliases ou papéis canônicos? Qual teste prova?
3. `@doctor @medico` gera duplicidade? Qual teste prova que não?
4. O que acontece com um username `medico`? Registrar que é token reservado de grupo.
5. Alguma migration foi criada? Esperado: não.
6. Quais comandos de validação foram executados?

## Relatório obrigatório

Criar `/tmp/case-communication-mention-aliases-slice-001-report.md` com:

- resumo;
- arquivos tocados;
- snippets antes/depois;
- evidência TDD;
- quality gate;
- respostas aos gates.

Responder com:

```text
REPORT_PATH=/tmp/case-communication-mention-aliases-slice-001-report.md
```

## Prompt pronto para implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md and openspec/changes/case-communication-mention-aliases/*.
Implement ONLY Slice 001.
Use TDD: add failing parser/service/integration/template tests first, then minimal implementation.
Keep it lean. Do not create migrations. Do not alter roles, permissions, FSM, notification model or communication endpoint.
Implement aliases @medico->doctor, @chd->scheduler, @supervisor->manager, keeping @nir/@doctor/@scheduler/@manager/@admin.
Run quality gate, update tasks.md, create /tmp/case-communication-mention-aliases-slice-001-report.md, commit and push, return REPORT_PATH and stop.
```
