# Design: Aliases pt-BR para menções de papéis

## Estado atual

`apps/accounts/services.py` define:

```python
COMMUNICATION_MENTION_ROLES = {"nir", "doctor", "scheduler", "manager", "admin"}
```

`parse_mentions()` captura `@token`, converte para lowercase e:

- se token está em `COMMUNICATION_MENTION_ROLES`, adiciona em `role_tokens`;
- caso contrário, trata como username.

`create_case_communication_notifications()` resolve `role_tokens` via `Role.name` e cria notificações para usuários ativos com esse papel.

## Decisão

Substituir o set simples por um mapa de aliases para papel canônico:

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

`parse_mentions()` deve adicionar o valor canônico ao conjunto `role_tokens`.

## Observações

- O parser continua sem acentos porque a regex atual não aceita caracteres unicode acentuados. Isso é aceitável neste slice: usar `@medico` sem acento.
- Aliases viram tokens reservados. Um usuário chamado `medico`, `chd` ou `supervisor` não será mencionado individualmente por esses tokens; o token será interpretado como grupo. Esse comportamento é igual ao já existente para `@nir`, `@doctor`, etc.
- Não há migration.
- Não há alteração em roles/permissões.

## Slice único

Implementar em um único slice vertical porque o escopo é pequeno e end-to-end:

- parser;
- serviço de notificação;
- payload via integração existente;
- microcopy da thread;
- testes.

Arquivos previstos:

- `apps/accounts/services.py`
- `apps/accounts/tests/test_notifications.py`
- `templates/cases/_communication_thread.html`
- `openspec/changes/case-communication-mention-aliases/tasks.md`

## Rollback

Reverter o mapa de aliases para o set anterior e a microcopy do template. Sem dados a migrar.
