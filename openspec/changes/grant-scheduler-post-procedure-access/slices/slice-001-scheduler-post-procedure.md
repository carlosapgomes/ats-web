# S1 — Pesquisar, registrar e atualizar o Pós-Procedimento

## 1. Identity

- **Change:** `grant-scheduler-post-procedure-access`.
- **Slice:** 001 de 002; **task:** `tasks.md`, item 1.1; **estado:** não iniciado.
- **Dependência:** baseline verificado no preflight; não depende de S2.

## 2. Objective

Entregar ao Agendador a jornada menu → pesquisa global de elegíveis → registro/atualização auditável, sem acesso gerencial e sem antecipar a consulta analítica/CSV de S2.

## 3. Read first

- `AGENTS.md`, `PROJECT_CONTEXT.md`, `openspec/config.yaml`.
- `openspec/changes/grant-scheduler-post-procedure-access/`: `proposal.md`, `design.md` (D1–D6 e riscos), `tasks.md`, `specs/supervisor-appointment-follow-up/spec.md` e `specs/supervisor-followup-history/spec.md`. As deltas são o alvo **após S2**; D6 define o estado intermediário de S1.
- `apps/accounts/services.py::can_access_followup`, `decorators.py::followup_access_required`, `context_processors.py::role_context`, `middleware.py`.
- `apps/dashboard/views.py`: `followup_list`, `followup_form` e guards dos endpoints gerenciais; consultar histórico/CSV para comprovar bloqueio preservado. `apps/dashboard/urls.py`, `apps/admin_ui/urls.py` e decorators administrativos.
- `templates/dashboard/followup_list.html`, `followup_form.html`, `_followup_tabs.html`, `_nav.html`; `templates/scheduler/_nav.html`.
- `apps/cases/followup.py`, `apps/dashboard/forms.py`, testes focused abaixo, manual §§5–6.

## 4. Requirements → evidence

IDs locais deste slice: **S1.R1–R6**.

| ID | Comportamento verificável | Evidência planejada |
| --- | --- | --- |
| R1 | Scheduler ativo/autenticado/ativo acessa lista e GET/POST de formulário sem manager. Supervisor CHD/admin mantêm acesso; manager sem CHD, doctor/nir ativos (mesmo com scheduler atribuído), anônimo/inativo/papel desconhecido não ganham acesso. Histórico analítico/CSV continuam negados ao scheduler, inclusive multi-role com scheduler ativo. | Unitários da política/decorator/contexto; HTTP positivo de lista/form e negativo das rotas ainda fechadas, com papel/IP explícitos. Preservar os testes atuais de bloqueio de histórico/CSV. |
| R2 | Menu do Agendador → Pós-Procedimento → busca por nome/ocorrência/data lista todos os elegíveis, incluindo terceiro e vinda imediata, sem ownership. Lista/form usam nav operacional e aba ativa; cancelar/salvar/POST inválido mantêm papel e jornada. Histórico & Exportação não é anunciado ao scheduler; supervisor/admin mantêm as duas sub-abas e seu menu. | Integração com casos de autores distintos, filtros existentes e hrefs reais; HTML de lista/form válida e inválida; redirect de sucesso; guardas de menu e sub-abas para ambos os papéis. |
| R3 | Agendador registra v1, atualiza registro de supervisor e supervisor atualiza de volta; versões/atores/eventos preservados, visíveis pelo outro papel no formulário. Caso, decisão e agendamento não mudam. Inelegível/inexistente não exposto; validação atual rejeita causa/procedimento inválido ou ausência de autorizados, sem writes. | HTTP sequencial v1/v2/v3 com atores corretos, snapshots operacionais, GET/POST inelegível 404, POST inválido sem nova row/evento. Regressão do service e catálogo autorizado. |
| R4 | Nenhum acesso gerencial adicional, inclusive por URL e com manager atribuído mas scheduler ativo. | Parametrizar dashboard, summaries, detalhe, PDF/anexos/viewers e listagens de Prompts/Usuários; POST válido de encerramento administrativo negado. Recursos existentes, sem seguir redirects; exigir bloqueio do guard, não 404, e ausência de mutação/download. |
| R5 | Política de rede permanece: scheduler-only externo 403; interno acessa o fluxo; bypass multi-role atual não é removido nem vira liberação gerencial. | IP/range explícitos em lista/form GET/POST e rotas ainda fechadas; multi-role externo consegue lista/form mas continua sem histórico/CSV e dashboard com scheduler ativo. Middleware intacto. |
| R6 | Manual/contexto e seus testes descrevem a entrega real: pesquisa/registro globais e histórico de versões do formulário disponíveis, histórico analítico/CSV ainda indisponíveis ao Agendador. | Testes de artefatos e inspeção das seções, sem promessa de feature completa; diff sem mudança sensível não aprovada. |

## 5. Expected blast radius

Conforme justificativa prévia em `design.md`, D6:

- Sete arquivos funcionais: `apps/accounts/services.py`, `decorators.py`; somente guards de lista/form em `apps/dashboard/views.py`; `templates/dashboard/followup_list.html`, `followup_form.html`, `_followup_tabs.html`; `templates/scheduler/_nav.html`.
- Testes: `apps/accounts/tests/test_access_policy.py`, expectativas de lista/form nos arquivos existentes, e integração preferencialmente em `apps/dashboard/tests/test_scheduler_followup_access.py`.
- Docs do próprio fluxo: `docs/manual/manual-usuarios.md`, `tests/test_user_manual_artifacts.py`, `PROJECT_CONTEXT.md`.

O alcance supera cinco arquivos porque a entrada, autorização, apresentação e prova de isolamento precisam sair juntas; não é autorização para refatoração. Arquivos extras exigem justificativa no relatório.

**Não alterar:** guards de histórico/CSV, `followup_history.html`, regras analíticas, demais guards gerenciais, rede/sessão, URLs, forms/service/models/FSM ou taxonomia. Não desenvolver infraestrutura para S2; sua única preparação é a fronteira transitória indispensável ao menu coerente de S1.

## 6. Failing-before plan

**RED → GREEN → REFACTOR**:

1. Unitário de scheduler-only com papel ativo scheduler deve exigir política verdadeira; no baseline recebe falso.
2. HTTP na intranet exige lista/form 200 e POST válido com versão/evento corretos; baseline redireciona por autorização, sem gravar.
3. Menu exige href Pós-Procedimento para Agendador; baseline não o oferece.
4. Caracterizar antes da mudança as negativas gerenciais, rede, histórico e CSV: devem estar verdes e permanecer verdes. Guardar comandos/exit codes, sem usar um 403 de rede como RED de papel.

Atualizar as expectativas antigas de scheduler proibido **somente em política/lista/form**. Não retirar scheduler das negativas de histórico/CSV em S1; não remover os demais casos negativos.

## 7. Implementation constraints

- Follow the repository engineering policy in `AGENTS.md` and preserve existing conventions. Prefer the smallest correct change; avoid speculative abstraction and unrelated refactoring.
- D1–D4 descrevem o alvo; seguir **D6** para a etapa: ampliar política central e somente dois guards externos. Histórico/CSV continuam com o `role_required` anterior.
- Ocultar transitoriamente o link de histórico no partial para scheduler, com comentário referenciando S2; não criar nova função de permissão, flag de deploy ou contexto global. A condição é apresentação; proteção real continua nos endpoints.
- Compartilhar URLs, templates, forms e service atuais; nenhuma cópia por papel, filtro de ownership, concessão de manager ou alteração do versionamento concorrente.
- Fixtures de scheduler-only não podem receber manager/admin para contornar middleware. Conta multi-role é cenário distinto, com seus papéis reais.

## 8. Validation

### Focused validation

```bash
uv run pytest \
  apps/accounts/tests/test_access_policy.py \
  apps/accounts/tests/test_middleware.py \
  apps/dashboard/tests/test_followup_list_view.py \
  apps/dashboard/tests/test_followup_form_view.py \
  apps/dashboard/tests/test_followup_history.py \
  apps/dashboard/tests/test_scheduler_followup_access.py \
  apps/dashboard/tests/test_dashboard.py \
  apps/dashboard/tests/test_expanded_catalog_followup.py \
  apps/cases/tests/test_followup_services.py \
  apps/scheduler/tests \
  tests/test_user_manual_artifacts.py
openspec validate grant-scheduler-post-procedure-access --strict --no-interactive
```

O arquivo integrado é esperado após criação; se a mesma cobertura ficar nos existentes, ajustar o comando e justificar. `test_followup_history.py` entra como regressão da fronteira fechada e do comportamento anterior do supervisor/admin, não como autorização para implementar S2.

### Project-required gates

Executar seção 2 de `AGENTS.md`; registrar baseline versus resultado e falhas preexistentes sem enfraquecer assertions.

### Runtime / verification evidence

Client real do Django: scheduler-only na intranet segue menu → pesquisa terceiro e vinda imediata → registra/atualiza → supervisor vê versão pelo formulário. Depois comprovar negativa de histórico/CSV, GET gerencial e POST administrativo e 403 externo. Smoke visual desktop/mobile se houver ambiente; do contrário registrar limitação, sem alegar execução. Usar dados sintéticos; nenhum deploy autorizado.

## 9. Acceptance criteria / self-eval gates

- [ ] R1: lista/form acessíveis ao scheduler; matriz anterior preservada; histórico/CSV ainda negados.
- [ ] R2: busca global e jornada de lista/form operacionais; histórico não anunciado ao scheduler; menu anterior preservado.
- [ ] R3: versões cruzadas e autores/eventos corretos; nenhuma mudança operacional ou write inválido.
- [ ] R4: todos os endpoints gerenciais listados bloqueados por guard com recursos/payload válidos.
- [ ] R5: positivos internos, 403 externo e bypass multi-role caracterizados sem mudança de rede.
- [ ] R6: docs/testes correspondem ao estado parcial; código de S2 não antecipado.
- [ ] RED/GREEN, focused e gates reportados; OpenSpec estrito aprovado; relatório pronto para revisão, sem declarar o change completo.

## 10. Escalation conditions

Retornar `BLOCKED_NEEDS_DECISION` se houver contradição com o estado intermediário D6, nova decisão de produto/segurança/arquitetura, mudança de URL/CSV, persistência/migration/FSM, rede, integridade clínica ou expansão material de escopo. Não resolver isso silenciosamente para caber no slice. Arquivos adicionais legítimos devem ser justificados no relatório.

## 11. Evidence report

`REPORT_PATH=/tmp/sirhosp-slice-001-report.md`.

Status `READY_FOR_REVIEW` ou `BLOCKED_NEEDS_DECISION`; S1.R1–R6 → evidência; arquivos; RED/GREEN; comandos/exit codes; runtime/smoke e limitações; expansão de escopo; riscos/decisões. Snippets antes/depois conforme `AGENTS.md`, sem copiar todo o diff. Registrar expressamente o bloqueio e a condição transitória de histórico/CSV para o sucessor S2.

## 12. Worker handoff — contexto zero

```text
Read AGENTS.md and PROJECT_CONTEXT.md first.
Implement ONLY S1 from openspec/changes/grant-scheduler-post-procedure-access/tasks.md.
Read this slice and its Read first references; do not rely on prior conversation.
Deliver menu -> global eligible-case search -> audited register/update, preserving manager/admin behavior.
The final change includes History & Export, but S1 MUST keep those endpoints denied to scheduler
and hide their link per design D6. No dashboard/admin access, ownership filter or network change.
Produce RED evidence, implement the smallest correct change, REFACTOR, and verify S1.R1–R6
with focused tests and the repository gates. Follow repository engineering and delivery policy.
Report READY_FOR_REVIEW or BLOCKED_NEEDS_DECISION, with evidence and
REPORT_PATH=/tmp/sirhosp-slice-001-report.md.
Do not merge, archive, deploy, or start S2/another change. Stop for review and explicit continuation.
```
