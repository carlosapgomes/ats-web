# Design: Substituição do rótulo "follow-up" por "Pós-Procedimento" na UI

## D1 — Regra tipográfica

- Títulos de página, pills de navegação e headers: **"Pós-Procedimento"**
  (ex.: pill da nav, h1 "Pós-Procedimento · Histórico & Exportação").
- Meio de frase: **"pós-procedimento"**
  (ex.: botão "Registrar pós-procedimento", flash "Pós-procedimento registrado
  (versão 2) para o caso …", badge "Pós-procedimento registrado/pendente",
  card "Casos elegíveis para pós-procedimento", painel "Versões do
  pós-procedimento").
- Não abreviar ("Pós-Proc." é proibido); manter o termo completo em todos os
  contextos, inclusive botões.
- Sub-aba "Histórico & Exportação" e demais rótulos sem "follow-up" ficam
  inalterados.

## D2 — Inventário de substituição (mapeado por scout; fonte única do slice 001)

| Onde | Ocorrências |
|---|---|
| `templates/dashboard/_nav.html:7` | pill "Follow-up" → "Pós-Procedimento" |
| `templates/dashboard/_followup_tabs.html:1,8` | aria-label "Sub-abas do pill Follow-up…" → "…Pós-Procedimento…" |
| `templates/dashboard/followup_list.html:4,5,18,67,73,77` | title/h1 "Follow-up de desfecho…", card "Casos elegíveis para follow-up", badges "Follow-up registrado/pendente", botões "Atualizar/Registrar follow-up" |
| `templates/dashboard/followup_form.html:4,5,47,62,93,98,180` | title/h1 "Follow-up · Caso…", painel "Versões do follow-up", empty "Nenhum follow-up registrado…", avisos, botão submit |
| `templates/dashboard/followup_history.html:5,78` | h1 "Follow-up · Histórico…", card "Casos com follow-up no período" |
| `apps/dashboard/views.py:~2008` | flash "Follow-up registrado (versão {n})…" |
| `apps/dashboard/tests/` (3 arquivos) | 9 asserções de texto com "Follow-up" |
| `docs/manual/manual-usuarios.md:15,1030-1140` | intro + §6 inteiro (slice 002) |

O worker deve re-executar `rg -in "follow.?up" templates/ apps/dashboard/views.py`
para capturar eventuais ocorrências novas desde o mapeamento (data do scout:
2026-09-06) — o inventário acima é o contrato mínimo, não o teto.

## D3 — Specs: delta MODIFIED apenas nos rótulos

- `supervisor-appointment-follow-up`: header "A aba Follow-up SHALL listar…"
  (linha ~45) → "A aba Pós-Procedimento SHALL listar…". O termo "follow-up"
  PERMANECE como termo de domínio no corpo das specs (ex.: "Registro de
  desfecho pós-exame", `CaseFollowUp`); só o rótulo da superfície muda.
- `supervisor-followup-history`: header "A aba Follow-up SHALL organizar-se…"
  (linha ~8) e o texto "A superfície Follow-up SHALL apresentar…" → rótulo
  "Pós-Procedimento"/"superfície Pós-Procedimento"; URLs citadas permanecem.
- Nota: este change DEPENDE de `followup-chd-access-guard` — além do manual
  (acesso CHD), os deltas são encadeados no requisito das sub-abas de
  `supervisor-followup-history`: o RENAMED FROM deste change referencia o
  header vigente (que o guard NÃO renomeia) e o MODIFIED carrega o cenário
  "Manager sem vínculo CHD não vê a aba" introduzido pelo guard. Executar e
  ARQUIVAR o guard primeiro é obrigatório; em ordem inversa os deltas deixam
  de casar (review P1).

## D4 — Manual §6 (slice 002): estrutura do rewrite

Seção "6. Ações do usuário Supervisor" passa a cobrir, com o rótulo novo:

1. **Quem accessa**: supervisores do **CHD** (usuários com perfis Supervisor e
   CHD/Agendador, papel ativo Supervisor) e Administradores; supervisores
   médicos e do NIR não veem a aba (referência ao comportamento vigente).
2. **Aba Pós-Procedimento — Registrar** (fluxo existente, renomeado): casos
   elegíveis por data de grupo, busca, badges, formulário de desfechos com
   causa estruturada, versões append-only, o que o registro NÃO faz
   (intercorrência/reagendamento/estado).
3. **Sub-aba Histórico & Exportação** (novo conteúdo): janela por data de
   grupo (default 7 dias, cap 31), versão corrente por caso, busca, cards do
   período, filtros de linha (desfecho/causa/internação; cards não mudam),
   exportação CSV fiel aos filtros (UTF-8/Excel, todas as linhas, ignora
   paginação).
4. Referência de introdução (~linha 15) atualizada com o novo rótulo.
5. Manter o tom/instruções passo-a-passo do manual existente; nada além de §6
   e intro é editado.

## D5 — Testes

- Slice 001 (UI): asserções existentes convertem para o rótulo novo; novo
  teste varredura (ex.: render das páginas-chave e `assert "follow-up" not in
  response` case-insensitive) para travar o não-regresso do anglicismo.
- Slice 002 (manual): estender `tests/test_user_manual_artifacts.py` — §6
  menciona "Pós-Procedimento", "Histórico & Exportação", acesso CHD; e
  `assert "follow-up" not in` manual (case-insensitive).
- Flash message testada onde já é testada hoje (mesma asserção, novo texto).

## D6 — Riscos

- Substituição mecânica ampla: mitigada pelo inventário D2 + grep de
  verificação como critério de aceite (nenhum "follow-up" visível).
- Dependência OBRIGATÓRIA de `followup-chd-access-guard` (ver D3): manual
  (acesso CHD) E deltas encadeados no requisito das sub-abas. O guard deve
  estar arquivado antes do preflight deste change.
- Zero risco de dados/FSM/migrations: change puramente textual.
