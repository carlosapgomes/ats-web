# Proposal: Substituição do rótulo "follow-up" por "Pós-Procedimento" na UI

## Problema

"Follow-up" é anglicismo técnico que gera atrito para os usuários brasileiros
do hospital. A UI deve se comunicar em português claro. Paralelamente, o manual
do usuário (seção 6) ainda não documenta a sub-aba "Histórico & Exportação"
entregue em `v0.6.0-rc.3` (pendência registrada no DoD do change
`supervisor-followup-history-export`).

## Decisão do dono (2026-09-06)

Rótulo na UI: **"Pós-Procedimento"** — título/pill em Title Case
("Pós-Procedimento"), o mesmo termo em minúsculas no meio de frases
("pós-procedimento").

## Regras de substituição

1. **Só o que o usuário lê**: templates, flash messages e manual. Todo rótulo
   "Follow-up"/"follow-up" visível passa a "Pós-Procedimento"/"pós-procedimento",
   mantendo a capitalização do contexto (inventário no design D2).
2. **Identificadores técnicos NÃO mudam** (não-goals): nomes de código
   (`CaseFollowUp`, `followup_list`), URLs (`/dashboard/follow-ups/`), nome do
   arquivo CSV (`followups_<start>_<end>.csv`, travado pela spec
   `supervisor-followup-history` D5), keys de sessão, seletores de teste que
   não sejam asserção de texto visível.
3. **Specs**: "follow-up" permanece como termo de domínio, MAS os pontos em que
   as specs nomeiam o **rótulo da aba** ("aba Follow-up", "superfície
   Follow-up") recebem delta MODIFIED renomeando o rótulo — mantendo
   artefatos consistentes com a UI.
4. **Manual §6 é reescrito uma única vez**: renomeação + documentação da sub-aba
   "Histórico & Exportação" (janela por data de grupo, versão corrente, busca,
   cards, filtros de linha, exportação CSV fiel aos filtros) + acesso restrito
   a supervisores do CHD e admin (vigente após o change `followup-chd-access-guard`).
   Isso absorve a mini-change de manual pendente.

## Escopo

- 5 templates do dashboard (`_nav`, `_followup_tabs`, `followup_list`,
  `followup_form`, `followup_history`) + 1 flash message em
  `apps/dashboard/views.py`.
- **Timeline do caso**: `EVENT_LABELS` em `apps/intake/views.py` (labels
  render-time de `FOLLOWUP_RECORDED`/`FOLLOWUP_UPDATED`, exibidos na timeline
  de `case_detail` consumida também pelo dashboard; fonte única — nenhum outro
  app define labels visíveis de follow-up).
- Manual `docs/manual/manual-usuarios.md`: §6 completo + referência de
  introdução (~linha 15) + termos dispersos na seção.
- Deltas de spec (MODIFIED/RENAMED) renomeando o rótulo nas duas capabilities.
- Atualização dos asserts de texto nos testes afetados (5 asserts em
  `apps/dashboard/tests/` — incl. `test_followup_history.py:450`) + testes do
  manual (`tests/test_user_manual_artifacts.py`); demais ocorrências
  (docstrings, comentários, fixtures) tratadas conforme design D5.

## Não-goals

- Renomear código, URLs, filename do CSV ou qualquer identificador.
- Mudar comportamento, guard de acesso, layout ou estilos (só texto).
- Traduzir "CSV", "Dashboard" ou outros termos já estabelecidos.

## Sucesso

- Nenhuma string "follow-up"/"Follow-up" visível ao usuário na UI ou no manual
  (verificação por teste de varredura sobre texto visível — design D5 — e
  classificação de grep conforme D5; identificadores/URLs permanecem).
- Manual §6 documenta registro, histórico e exportação com o novo rótulo e o
  acesso CHD.
- Suíte completa verde no gate final; specs validadas.
