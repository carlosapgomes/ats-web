# Proposal: Histórico e exportação de follow-ups do supervisor

**Change ID:** `supervisor-followup-history-export`

## Why

O registro de follow-up (`supervisor-appointment-follow-up`, em produção desde
v0.6.0-rc.1) acumula desfechos versionados por caso, mas o supervisor só enxerga
a janela operacional de hoje+ontem. Não há como: revisar desfechos de um período
anterior, ver agregados (taxa de realizado, causas de não realização,
internações) nem exportar os dados para prestação de contas — hoje isso exigiria
consulta ao banco. A validação em produção deixou 6 registros reais/teste que
demonstram a necessidade (e servem de fixture natural).

## What Changes

- **Sub-abas** no pill Follow-up: **Registrar** (fluxo atual, URL inalterada) e
  **Histórico & Exportação** (nova `/dashboard/follow-ups/history/`) — decisão
  de IA aprovada pelo owner (coesão de domínio; dashboard segue cabine
  operacional; sem pill nova).
- **Página Histórico** (SSR): população = casos com follow-up registrado, cada
  caso **1x pela versão corrente**; janela de datas por **data de grupo**
  (agendamento/decisão — mesma semântica da aba Registrar; default últimos 7
  dias, máximo 31); busca por ocorrência/paciente dentro da janela;
  cards-resumo do período (casos, taxa de realizado por procedimento, causas
  com submotivos, internações); tabela paginada (1 linha por desfecho de
  procedimento).
- **Exportação CSV**: `GET /dashboard/follow-ups/history/export/` com os mesmos
  filtros; UTF-8 com BOM + `;` (Excel pt-BR); 1 linha por desfecho de
  procedimento; header em português; nenhum `CaseEvent` (leitura pura).
- **Filtros de linha** (desfecho / causa / internação) aplicados à tabela e ao
  CSV; cards sempre resumem o período.

### Impact

- Apps: `cases` (+helper de leitura no service), `dashboard` (view/urls/templates).
- Sem migrations, sem FSM, sem env vars, sem JS novo (SSR puro).
- Spec nova `supervisor-followup-history`; spec existente
  `supervisor-appointment-follow-up` inalterada.
- Manual do usuário (§6): atualização fica como mini-change posterior (padrão
  `supervisor-followup-user-manual`).

## Sucesso

Supervisor com papel `manager`/`admin`: abre a sub-aba Histórico e vê, para a
janela de datas escolhida, agregados e a lista de desfechos (versão corrente por
caso); busca por ocorrência/nome; exporta CSV fiel aos filtros exibidos. Outros
papéis/anônimos sem acesso. Agregados não distorcem com versões antigas.
