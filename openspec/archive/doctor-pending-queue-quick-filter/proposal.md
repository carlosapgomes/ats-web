# Proposal: Busca rápida client-side na fila médica pendente

**Change ID**: `doctor-pending-queue-quick-filter`  
**Fase**: ajuste operacional/UX médico  
**Risco**: PROFISSIONAL (FEATURE)  
**Dependências**: `doctor-queue`, `doctor-decided-today-tab`, `prioritize-queues-by-regulation-days`

## Problema

Na aba médica **Pendentes**, o NIR pode liberar muitos relatórios em lote. Em cenários reais com 50–60 pacientes pendentes, o médico precisa localizar rapidamente um caso específico para reavaliar, discutir com o NIR ou dar feedback.

Hoje a fila não possui busca por paciente nem por número de ocorrência (`Case.agency_record_number`). Como não há paginação na fila médica atual, todos os cards pendentes já são renderizados na página, mas o médico precisa procurar visualmente.

## Objetivo

Adicionar uma busca rápida e dinâmica na aba **Pendentes** do painel médico, filtrando os cards já carregados no navegador por:

- nome do paciente;
- número de ocorrência (`agency_record_number`, exibido como `Reg.` no card).

A busca deve ser explícita e fácil de limpar, evitando que o médico fique preso em uma lista filtrada sem perceber.

## Escopo

### Funcionalidades

1. Campo de busca visível apenas na aba `Pendentes`.
2. Filtragem dinâmica client-side dos cards pendentes já renderizados.
3. Busca por nome case-insensitive e accent-insensitive.
4. Busca por ocorrência usando `agency_record_number`.
5. Indicação clara de filtro ativo, por exemplo: `Filtro ativo: 3 de 58 pacientes exibidos`.
6. Botão `Limpar` visível quando houver filtro ativo.
7. Tecla `Esc` limpa o filtro quando o campo está focado.
8. Ao apagar o texto ou clicar em `Limpar`, todos os pendentes voltam a aparecer.
9. Após auto-refresh HTMX da fila, o filtro atual deve ser reaplicado aos novos cards enquanto o usuário permanecer na página.
10. O filtro não deve ser persistido em URL, sessão, localStorage ou server-side; ao sair/voltar para a fila, ela abre sem filtro.

## Fora de escopo

- Busca server-side.
- Paginação.
- Histórico multi-dia.
- Filtro em `Decididos Hoje`.
- Alterar locks, reserva de caso, decisão médica ou FSM.
- Criar endpoint/API novo.
- Persistir preferências de busca.
- Destacar trechos encontrados dentro do card.

## Decisão de produto

Como a fila médica atual **não tem paginação**, a implementação client-side encontra todos os casos pendentes carregados. Essa solução é menor, mais rápida e menos arriscada do que uma busca server-side neste momento.

Se futuramente a fila médica passar a ter paginação ou volume grande suficiente para não renderizar todos os pendentes, será necessário criar novo change para busca server-side antes da paginação.

## Critérios de sucesso

- Médico vê campo `Buscar por nome ou ocorrência` na aba Pendentes.
- Digitar parte do nome do paciente filtra os cards visíveis.
- Digitar parte/exato do `agency_record_number` filtra os cards visíveis.
- Busca por nome ignora maiúsculas/minúsculas e acentos.
- Médico consegue limpar o filtro com botão `Limpar`, apagando o texto ou pressionando `Esc` no campo.
- UI deixa claro quando a lista está filtrada e quantos cards estão visíveis.
- Auto-refresh HTMX não remove silenciosamente o filtro enquanto o médico permanece na página.
- A aba `Decididos Hoje` não recebe o filtro neste slice.
- Quality gate do AGENTS.md passa na implementação.
