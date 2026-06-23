# Proposal: Header de notificações e badges operacionais

**Change ID**: `header-notifications-queue-badges`  
**Fase**: polish UX global pós-notificações in-app e abas operacionais  
**Risco**: PROFISSIONAL (altera header global, navegação de filas e testes de UI SSR)  
**Dependências**: `case-communication-mentions-notifications`, `doctor-decided-today-tab`, `scheduler-processed-today-tab`

## Problema

O canto superior direito do header autenticado combina conceitos diferentes de forma ambígua:

1. O acesso a notificações aparece como botão textual `Notificações`, ocupando espaço e competindo visualmente com avatar/nome.
2. O contador de notificações usa a classe `.notif-badge`, mas essa mesma classe também é reutilizada em abas operacionais.
3. O header mostra `queue_count` ao lado do nome/papel do usuário. Para médico e agendador, esse número representa fila operacional, não notificação pessoal, mas visualmente parece notificação do usuário.
4. A página `Minhas Notificações` não oferece botão de retorno quando aberta diretamente ou quando está vazia.
5. Em filas operacionais, contadores de itens concluídos (`Decididos Hoje`, `Processados Hoje`) não devem ter semântica visual de urgência vermelha.
6. A aba `Processados Hoje` do agendador já tem contador calculado em view (`processed_today_count`), mas ainda não o exibe na navegação.

## Objetivo

Separar visualmente:

- **notificações pessoais**: sino no header com badge vermelho de não lidas;
- **identidade/perfil**: avatar + nome + papel, sem contador operacional grudado;
- **fila operacional**: contadores nas abas de fila, com vermelho apenas para pendências e cor neutra para itens já concluídos.

Também garantir navegação de retorno clara em `Minhas Notificações`.

## Escopo

### Funcionalidades

1. **Header autenticado**
   - Trocar o botão textual `Notificações` por um botão/ícone de sino.
   - Manter polling Vanilla JS existente via `data-notifications-badge` e `data-unread-count-url`.
   - Manter contador vermelho apenas no sino quando houver notificações não lidas.
   - Remover o badge `queue_count` do nome/avatar.

2. **Página de notificações**
   - Adicionar botão `Voltar ao início` sempre visível.
   - Manter `Marcar todas como lidas` apenas quando houver não lidas.
   - Estado vazio continua explicativo e com saída clara.

3. **Badges operacionais de abas**
   - Não usar `.notif-badge` para abas operacionais.
   - Criar classes semânticas para contador de aba, por exemplo:
     - pendente/ação: vermelho;
     - concluído/histórico do dia: neutro.
   - Médico:
     - `Pendentes` mantém contador de ação;
     - `Decididos Hoje` mantém contador, mas com cor neutra.
   - Agendador:
     - `Pendentes` mantém contador de ação;
     - `Processados Hoje` passa a exibir `processed_today_count` com cor neutra.

4. **NIR**
   - Não adicionar contadores nas abas do NIR neste change.
   - Manter contador total dentro de `Meus Casos` como está.

## Fora de escopo

- Nova lógica de contagem ou alteração de queries de filas.
- Mudança no modelo `UserNotification`.
- Mudança em polling, periodicidade, endpoint ou comportamento de marcação de leitura.
- Dropdown de notificações, toasts, WebSocket/SSE, push, e-mail ou AJAX para a lista.
- Redesenho completo do header ou responsividade ampla além do necessário.
- Contador acionável para NIR.
- Histórico multi-dia de médico/agendador.

## Critérios de sucesso

- Header mostra ícone de sino para notificações, não botão textual grande `Notificações`.
- Sino preserva `data-notifications-badge`, URL de polling e `aria-label` acessível.
- Contador de notificações aparece apenas quando `notification_unread_count > 0`.
- Nome/avatar não exibe mais `queue_count`.
- Página `Minhas Notificações` tem botão `Voltar ao início` sempre visível.
- Abas médicas continuam com contadores em `Pendentes` e `Decididos Hoje`.
- Badge de `Decididos Hoje` usa classe/cor neutra, não vermelha de urgência.
- Aba `Processados Hoje` do agendador exibe contador neutro calculado por `processed_today_count`.
- Aba `Pendentes` do agendador mantém contador de ação.
- Abas do NIR permanecem sem novos contadores.
- Quality gate do AGENTS.md passa.
