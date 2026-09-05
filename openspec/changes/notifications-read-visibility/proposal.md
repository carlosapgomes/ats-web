<!-- markdownlint-disable MD013 -->

# Proposal: Ocultar notificações lidas há mais de 48h da lista do usuário

**Change ID**: `notifications-read-visibility`  
**Risco**: PROFISSIONAL (altera a população visível de uma superfície de usuário, sem mutação de dados, FSM, migrations ou permissões)  
**Dependências**: `apps/accounts` (`UserNotification`, `notifications_list`), template `accounts/notifications.html`

## Problema

A lista de notificações in-app (`/accounts/notifications/`) exibe **todas** as `UserNotification` do destinatário, ordenadas por `created_at` descendente, sem qualquer janela de visibilidade. Notificações lidas nunca saem da lista: ela cresce indefinidamente e o usuário precisa rolar sobre dezenas de itens antigos para encontrar o que importa (não lidas e leituras recentes).

A reclamação operacional recebida: "a lista de mensagens está ficando muito longa". As notificações lidas há mais de dois dias não têm valor de consulta nessa superfície — o caso relacionado continua acessível pela thread de comunicação do caso e pela auditoria.

Decisão de produto registrada: **ocultar da UI**, não apagar. `UserNotification`, `CaseCommunicationMessage` e `CaseEvent` permanecem intactos no banco (auditoria append-only preservada; ocultação é reversível e sem risco de perda).

## Objetivo

1. A lista de notificações de um usuário deve exibir somente:
   - notificações **não lidas** (`read_at IS NULL`) — sempre visíveis, de qualquer idade; e
   - notificações **lidas há até 48 horas** (`read_at >= now - 48h`).
2. Notificações lidas há mais de 48 horas ficam ocultas **apenas da listagem**; nenhum registro é apagado.
3. A janela de 48h é medida a partir de `read_at` (momento da leitura), nunca de `created_at`.
4. Badge de não lidas, fluxos de abrir/marcar como lida/marcar todas e redirecionamento por notificação permanecem inalterados.

## Escopo incluído

- QuerySet customizado em `UserNotification` com método de visibilidade (`visible_for_list()`), conforme regra do `AGENTS.md` ("queries complexas em QuerySets customizados").
- `notifications_list` passa a consumir o QuerySet de visibilidade, preservando `select_related` e a contagem de não lidas existente.
- Nova constante de settings `NOTIFICATION_READ_RETENTION_HOURS = 48` em `config/settings/base.py` (seguindo o padrão das constantes `CASE_LOCK_*`).
- Testes de listagem: lida há 49h oculta; lida há 1h visível; não lida antiga visível; janela medida por `read_at` (não `created_at`).
- Nova spec de capacidade `user-notifications` com os requisitos de visibilidade (delta `ADDED`).

## Fora de escopo

- Apagar (fisicamente) qualquer notificação, mensagem ou evento — retenção de dados não muda.
- Paginar a lista, adicionar filtro "mostrar antigas" ou UI de limpeza manual.
- Alterar `CaseCommunicationMessage` (thread do caso, append-only), `CaseEvent`, `User` ou qualquer fluxo de menção/notificação.
- Alterar badge de não lidas, endpoints de marcar-como-lida, polling JS do badge ou templates de notificação.
- Tornar a janela configurável por env var (constante de settings basta neste change).
- Criar task django-q2 de purge (não há deleção).

## Dimensionamento em slices

O change terá **um único slice vertical**.

Backend (QuerySet + settings) e view compõem o mesmo comportamento observável — separá-los criaria um estado intermediário sem valor e testes duplicados. O slice prevê 4 arquivos funcionais, dentro da heurística de `<= 5` do `AGENTS.md`.

## Sucesso

- Usuário com lista longa de notificações lidas antigas abre `/accounts/notifications/` e vê apenas não lidas + leituras dos últimos 48h.
- Nenhum teste existente de notificações, menções ou comunicação de caso regrediu.
- `uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest` passam.
