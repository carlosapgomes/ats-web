# Proposal: Aliases pt-BR para menções de papéis na comunicação operacional

**Change ID**: `case-communication-mention-aliases`  
**Risco**: ESSENCIAL (parser de menções + microcopy; sem migration, sem FSM)  
**Dependências**: `case-communication-mentions-notifications`

## Problema

A comunicação operacional permite mencionar papéis com tokens em inglês:

- `@nir`
- `@doctor`
- `@scheduler`
- `@manager`
- `@admin`

Na operação hospitalar, alguns termos naturais são em português ou siglas locais. Usuários tendem a escrever `@medico`, `@chd` e `@supervisor`, mas esses tokens hoje são tratados como usernames, não como grupos/papéis.

## Objetivo

Permitir aliases de grupo em português/uso local sem alterar os papéis internos do sistema.

Mapeamento desejado:

| Alias digitado | Papel canônico notificado |
|---|---|
| `@nir` | `nir` |
| `@doctor` | `doctor` |
| `@medico` | `doctor` |
| `@scheduler` | `scheduler` |
| `@chd` | `scheduler` |
| `@manager` | `manager` |
| `@supervisor` | `manager` |
| `@admin` | `admin` |

Tokens devem continuar case-insensitive.

## Escopo

- Atualizar parser de menções para normalizar aliases para papéis canônicos.
- Garantir que criação de `UserNotification` funciona com aliases.
- Atualizar payload de evento para registrar papéis canônicos em `mentioned_roles`.
- Atualizar microcopy da thread de comunicação operacional com exemplos de menções.
- Adicionar/ajustar testes.

## Fora de escopo

- Suporte a acentos em menções, como `@médico`.
- Autocomplete de menções.
- Configuração dinâmica de aliases por banco/admin.
- Novos papéis ou alteração de permissões.
- Notificações por email/push/WebSocket.

## Critérios de sucesso

- `@medico` notifica usuários ativos com papel `doctor`.
- `@chd` notifica usuários ativos com papel `scheduler`.
- `@supervisor` notifica usuários ativos com papel `manager`.
- Tokens canônicos em inglês continuam funcionando.
- `@nir` e `@admin` continuam funcionando.
- Usernames continuam funcionando para tokens que não são aliases reservados.
- Payload do evento registra papéis canônicos, não aliases.
- UI informa exemplos de menção compreensíveis para usuários.
- Quality gate do `AGENTS.md` passa.
