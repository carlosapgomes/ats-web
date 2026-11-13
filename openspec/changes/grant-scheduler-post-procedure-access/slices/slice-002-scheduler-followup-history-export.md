# S2 — Histórico, resumos e exportação de Pós-Procedimento

## 1. Identity

- **Change:** `grant-scheduler-post-procedure-access`.
- **Slice:** 002 de 002; **task:** `tasks.md`, item 1.2; **estado:** não iniciado.
- **Dependência:** S1 aceito, com evidências R1–R6 e confirmação para continuar. Reconstruir a partir da revisão aceita e de `/tmp/sirhosp-slice-001-report.md`; se o relatório temporário não estiver disponível, obter as evidências equivalentes, sem presumir aceite.

## 2. Objective

Permitir ao Agendador consultar histórico, resumos e filtros e baixar CSV da mesma população corrente do supervisor, completando a jornada compartilhada sem ampliar acesso gerencial.

## 3. Read first

- `AGENTS.md`, `PROJECT_CONTEXT.md`, `openspec/config.yaml`.
- `openspec/changes/grant-scheduler-post-procedure-access/`: `proposal.md`, `design.md` (D1–D6 e riscos), `tasks.md`, as duas deltas em `specs/`, contrato S1 e suas evidências aceitas.
- `apps/dashboard/views.py`: `followup_history`, `followup_history_export` e helpers analíticos; `apps/dashboard/urls.py`.
- `templates/dashboard/followup_history.html`, `_followup_tabs.html`; navegação contextual já entregue nos templates de lista/form e em `templates/scheduler/_nav.html`.
- `apps/accounts/services.py::can_access_followup`, `decorators.py` e `middleware.py` para regressão, sem mudança esperada.
- `apps/cases/followup.py::current_follow_ups` e projeção de causas; `apps/dashboard/tests/test_followup_history.py`, arquivo integrado de S1 e testes focused abaixo; manual §§5–6.

## 4. Requirements → evidence

IDs locais deste slice: **S2.R1–R5**.

| ID | Comportamento verificável | Evidência planejada |
| --- | --- | --- |
| R1 | Scheduler-only autenticado/ativo e na intranet acessa histórico e CSV por link ou URL sem possuir manager. Supervisor CHD/admin mantêm acesso; doctor/nir ativos, manager sem CHD, anônimo/inativo/papel desconhecido continuam negados. | Integração positiva nas duas rotas; atualizar apenas a linha scheduler dos negativos de S1; manter/testar matriz dos outros papéis e política comum. |
| R2 | Duas sub-abas acessíveis e ativas corretamente na jornada do Agendador; histórico usa nav operacional sem links administrativos; retornar a Registrar mantém papel e fluxo S1. Condição transitória de S1 removida. | HTML/hrefs em lista/histórico e formulário; navegação real de ida/volta; menu anterior de supervisor/admin preservado; inspeção do partial/testes sem exclusão transitória. |
| R3 | Histórico/resumos/filtros/paginação/CSV têm paridade com supervisor sobre todos os elegíveis (terceiros e vinda imediata), com apenas a versão corrente e autor correto. Defaults/limites, legado e formato existentes não mudam; leitura/exportação não gravam dados ou eventos. | Mesma população/parâmetros nos dois papéis, período/busca e filtros de desfecho/causa/internação, dados acima de 25 linhas e versões antigas divergentes; comparar contexto e CSV parseado completo. Snapshot das rows/eventos antes/depois, regressão analítica/legado/formato. |
| R4 | Registro/atualização de S1 e bloqueio gerencial/rede permanecem. Scheduler-only externo recebe 403 também em histórico/CSV; bypass multi-role atual permite pós-procedimento, não dashboard com scheduler ativo. | Reexecutar integração S1 e negativas gerenciais; acrescentar duas rotas aos cenários de rede e multi-role. POST administrativo negado com payload válido após histórico/CSV. |
| R5 | Manual/contexto/testes descrevem acesso completo aprovado (duas sub-abas, resumos/CSV, global, sem dashboard) e deixam de declarar a indisponibilidade transitória. | Testes dos artefatos, inspeção das seções e ausência de condições/comentários/expectativas provisórias. Sem mudança de specs canônicas neste slice. |

## 5. Expected blast radius

Justificativa prévia em `design.md`, D6:

- Três arquivos funcionais: somente guards de histórico/CSV em `apps/dashboard/views.py`; nav contextual de `templates/dashboard/followup_history.html`; remoção da condição transitória de `templates/dashboard/_followup_tabs.html`.
- Testes: `apps/dashboard/tests/test_followup_history.py` e integração de S1, preferencialmente `apps/dashboard/tests/test_scheduler_followup_access.py`.
- Documentação: `docs/manual/manual-usuarios.md`, `tests/test_user_manual_artifacts.py`, `PROJECT_CONTEXT.md`.

Mais de cinco arquivos por incluir testes e documentação da própria entrega, não refatoração. Justificar arquivos extras no relatório. Não expandir para uma camada de permissões nova ou refatoração analítica.

**Sensíveis / sem alteração esperada:** política central/context processor/decorator entregues em S1, lógica/guards de registro, navegação já funcional do Agendador, demais guards gerenciais, middleware, queries/filtros analíticos, taxonomia, models/migrations/FSM, URLs/CSV. As funções existentes já fornecem a paridade requerida; alterar sua semântica exige escalada.

## 6. Failing-before plan

Partir do estado aceito de S1, não do baseline original. **RED → GREEN → REFACTOR**:

1. Teste scheduler-only interno exige GET histórico e CSV com status 200/conteúdo correto; S1 retorna redirect por guard externo.
2. Teste exige link Histórico & Exportação visível e navegável no menu de sub-abas do Agendador; S1 o oculta.
3. Teste de paridade exige os mesmos resultados/CSV entre scheduler e supervisor; falha em S1 pelo acesso negado do scheduler.
4. Manter registro/negativas gerenciais e de rede verdes como caracterização. Não atribuir manager aos fixtures para obter RED/GREEN artificial.

Após registrar o RED, substituir os negativos transitórios de scheduler em histórico/CSV pelos positivos. Não eliminar negativas dos demais papéis, invariantes de S1 ou testes de formato/legado. O teste da condição transitória deve ser substituído pelo teste das duas sub-abas acessíveis, não simplesmente apagado.

## 7. Implementation constraints

- Follow the repository engineering policy in `AGENTS.md` and preserve existing conventions. Prefer the smallest correct change; avoid speculative abstraction and unrelated refactoring.
- Somente os dois endpoints remanescentes ganham scheduler no guard externo; reaproveitar política central e login/guard específico existentes. Não reabrir as decisões D1–D5.
- Remover a condição/comentário transitório de S1, sem feature flag, novos helpers de autorização ou novo namespace de URLs.
- Reutilizar o mesmo histórico, população/versões, filtros/resumos e writer CSV; sem ownership ou cópia por papel. As comparações de paridade devem ignorar diferenças legítimas da navegação e comparar dados, não o HTML inteiro.
- Regressão de defaults/limites: histórico 7 dias por padrão, máximo 31, 25 linhas/página e CSV sem paginação; não mudar esses valores. Preservar BOM, separador, header, projeção de legado e escaping existentes.

## 8. Validation

### Focused validation

```bash
uv run pytest \
  apps/dashboard/tests/test_followup_history.py \
  apps/dashboard/tests/test_scheduler_followup_access.py \
  apps/dashboard/tests/test_followup_list_view.py \
  apps/dashboard/tests/test_followup_form_view.py \
  apps/dashboard/tests/test_dashboard.py \
  apps/dashboard/tests/test_expanded_catalog_followup.py \
  apps/accounts/tests/test_access_policy.py \
  apps/accounts/tests/test_middleware.py \
  apps/cases/tests/test_followup_services.py \
  apps/scheduler/tests \
  tests/test_user_manual_artifacts.py
openspec validate grant-scheduler-post-procedure-access --strict --no-interactive
```

Se S1 concentrou a integração em outro arquivo, usar o caminho real e registrar essa evidência. Não recriar suite paralela desnecessária.

### Project-required gates

Executar seção 2 de `AGENTS.md`; comparar com o baseline aceito de S1. Este slice deve conter todos os testes/docs de histórico/CSV; o gate final do change apenas integra as evidências, não substitui esta validação.

### Runtime / verification evidence

Client real do Django: menu do Agendador → Registrar → Histórico & Exportação → período/busca/filtros → CSV completo → retorno a Registrar. Dados incluem caso de terceiro e vinda imediata, com versões de autores distintos. Após o percurso, comprovar negativa gerencial e 403 externo; supervisor/admin acessam normalmente. Smoke visual desktop/mobile se disponível; registrar limitação se não houver ambiente, sem alegar execução. Dados sintéticos, sem deploy.

## 9. Acceptance criteria / self-eval gates

- [ ] R1: histórico/CSV acessíveis ao scheduler sem manager, com matriz negativa preservada.
- [ ] R2: duas sub-abas operacionais e nav contextual correta; condição transitória removida; ida/volta preserva S1.
- [ ] R3: paridade de dados/resumos/CSV filtrados, corrente apenas, paginação correta e zero writes de leitura/exportação.
- [ ] R4: S1 segue funcional; fronteira gerencial e rede comprovadas também nas novas rotas.
- [ ] R5: manual/contexto/testes descrevem alvo completo, sem exclusão transitória do scheduler ou alteração canônica antecipada.
- [ ] RED/GREEN sobre S1 aceito e focused/gates reportados, OpenSpec estrito aprovado e relatório pronto para revisão.

## 10. Escalation conditions

Retornar `BLOCKED_NEEDS_DECISION` se S1 não estiver aceito, os contratos divergirem, ou surgir decisão nova de produto/segurança/arquitetura, alteração de URL/CSV, persistência/migration/FSM, rede, integridade clínica ou expansão material de escopo. Não corrigir dívida analítica/concorrência incidentalmente. Justificar qualquer arquivo adicional no relatório.

## 11. Evidence report

`REPORT_PATH=/tmp/sirhosp-slice-002-report.md`.

Status `READY_FOR_REVIEW` ou `BLOCKED_NEEDS_DECISION`; S2.R1–R5 → evidência; base/evidências aceitas de S1; arquivos; RED/GREEN; comandos/exit codes; runtime/smoke e limitações; expansão de escopo; riscos/decisões. Snippets antes/depois conforme `AGENTS.md`, com foco nos guards, nav e remoção da condição transitória. Não alegar aceitação final, publicação ou deploy pelo simples término deste relatório.

## 12. Worker handoff — contexto zero

```text
Read AGENTS.md and PROJECT_CONTEXT.md first.
Implement ONLY S2 from openspec/changes/grant-scheduler-post-procedure-access/tasks.md.
Reconstruct context from this slice's Read first references and accepted S1 evidence.
If S1 acceptance cannot be established, return BLOCKED_NEEDS_DECISION.
Deliver scheduler History & Export using the existing shared handlers/data/URLs and contextual menu.
Remove S1's temporary hidden-history condition and replace its negative tests with positive coverage;
retain every other role/network/dashboard denial and the complete registration flow.
Produce RED on the accepted S1 state, implement the smallest correct change, REFACTOR,
and validate S2.R1–R5 plus repository gates. Follow repository engineering and delivery policy.
Report READY_FOR_REVIEW or BLOCKED_NEEDS_DECISION, with evidence and
REPORT_PATH=/tmp/sirhosp-slice-002-report.md.
Do not merge, archive, deploy, or start another change/slice. Stop for review.
```
