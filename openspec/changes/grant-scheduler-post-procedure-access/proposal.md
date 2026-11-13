# Proposal — Pós-Procedimento para o Agendador sem acesso ao dashboard

**Change ID:** `grant-scheduler-post-procedure-access`
**Estado:** implementado; S1 e S2 aceitos; gates finais aprovados.
**BASE_REF:** `befc5c50c0499acd86ed0e3d29a97380ab95f70c`
**Risco:** PROFISSIONAL / FEATURE. Altera autorização e acesso a dados sensíveis; o alcance acima de cinco arquivos decorre da cobertura de segurança, templates e documentação, não de uma refatoração estrutural. Exige design, TDD e regressão negativa das rotas gerenciais.

## Why

O Agendador precisa acompanhar e registrar o desfecho dos procedimentos, mas hoje o recurso só está disponível a supervisores do CHD e administradores. Conceder o papel Supervisor para isso liberaria desnecessariamente outras funções do dashboard.

## What Changes

- Disponibilizar a aba **Pós-Procedimento** na navegação do Agendador, com as sub-abas **Registrar** e **Histórico & Exportação**.
- Permitir ao usuário autenticado e ativo com papel ativo `scheduler` pesquisar, registrar e atualizar o pós-procedimento de **todos os casos elegíveis**, inclusive agendados por outros usuários e de vinda imediata, sem filtro por autoria/agendador.
- Oferecer o mesmo histórico, resumos, filtros e CSV disponíveis ao supervisor, sobre os mesmos dados e versões.
- Reutilizar a implementação atual, adaptando a navegação ao papel ativo; não criar cópia das regras ou dos registros.
- Preservar a autorização de supervisor do CHD (`manager` ativo + vínculo `scheduler`) e `admin`, e manter `manager` sem vínculo CHD, `doctor` e `nir` sem acesso ao recurso.
- Manter o dashboard e as demais superfícies gerenciais bloqueados para `scheduler`, inclusive por URL direta. Não alterar o middleware de intranet nem seu bypass multi-role existente.

### Decisões confirmadas pelo solicitante

1. Acesso a todos os elegíveis, inclusive casos de outros agendadores e vinda imediata.
2. Acesso também a **Histórico & Exportação**, incluindo resumos e CSV.
3. Nenhum acesso adicional ao dashboard; nenhuma necessidade de trocar para Supervisor.

## Capabilities

### New Capabilities

Nenhuma. O recurso já existe; muda sua matriz de acesso e sua entrada de navegação.

### Modified Capabilities

- `supervisor-appointment-follow-up`: incluir Agendador na autorização e no registro global de elegíveis; garantir navegação operacional e isolamento do dashboard.
- `supervisor-followup-history`: incluir Agendador no histórico/exportação com os mesmos filtros e proteção de acesso.

Os nomes históricos das capabilities serão mantidos para evitar renomeação estrutural. As deltas substituem os requisitos que hoje excluem explicitamente `scheduler`.

## Impact

- `apps/accounts/services.py` e `decorators.py`: política central de pós-procedimento e documentação do guard.
- Apenas as quatro views de pós-procedimento em `apps/dashboard/views.py`: permitir o papel ativo adicional; nenhuma ampliação nas outras views.
- Templates de pós-procedimento e `templates/scheduler/_nav.html`: uma entrada operacional e navegação contextual, sem links administrativos para o Agendador.
- Testes unitários e de integração: matriz de permissões, fluxo compartilhado, exportação, intranet e bloqueio gerencial.
- Manual do usuário e contexto do projeto: documentar a nova jornada sem alegar liberação do dashboard.
- Sem migrations, dependências novas, mudança de FSM, taxonomia, schema LLM ou dados históricos. URLs existentes preservadas.

## Non-goals

- Novo papel, framework de permissões ou atribuição de `manager` ao Agendador.
- Novas rotas, novo app ou cópia dos handlers/templates por papel.
- Alterar as outras abas do Agendador, permissões de PDFs/anexos, detalhes de casos, notificações ou fluxos de agendamento/intercorrência.
- Alterar a elegibilidade, os limites de busca/período/paginação, o formato CSV ou a semântica append-only.
- Corrigir concorrência preexistente no versionamento de pós-procedimento neste change.

## Entrega

Dois slices verticais sequenciais, cada um com autorização, interface, testes e documentação do próprio fluxo:

1. **S1 — Pesquisar e registrar/atualizar:** entrada operacional → busca global de elegíveis → formulário → nova versão auditável, sem acesso gerencial. Contrato: `slices/slice-001-scheduler-post-procedure.md`.
2. **S2 — Consultar histórico e exportar:** entrada na sub-aba → janela/busca/filtros/resumos → CSV dos mesmos dados correntes, mantendo o isolamento estabelecido em S1. Contrato: `slices/slice-002-scheduler-followup-history-export.md`.

A revisão de dimensionamento identificou dois fluxos de usuário verificáveis que estavam agrupados no contrato único. O estado intermediário seguro está definido em `design.md`, D6: S1 não libera nem anuncia histórico/CSV ao Agendador; S2 conclui o acesso integral já aprovado. Não há mudança de escopo final ou de specs. Ver `tasks.md` para dependências e evidências por slice.
