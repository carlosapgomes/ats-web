<!-- markdownlint-disable MD013 -->

# Slice 002: Detalhe do caso — Resultado Final mobile sem overflow

## Handoff para implementador LLM com contexto zero

Leia antes de editar:

- `AGENTS.md`
- `PROJECT_CONTEXT.md`
- `openspec/changes/dashboard-badge-progress-ux/proposal.md`
- `openspec/changes/dashboard-badge-progress-ux/design.md`
- `openspec/changes/dashboard-badge-progress-ux/tasks.md`
- `openspec/changes/dashboard-badge-progress-ux/slices/slice-001-dashboard-card-badges-next-step.md`
- este arquivo

Estado atual relevante:

- O detalhe do caso usa template compartilhado `templates/intake/case_detail.html`.
- O card `Resultado Final` renderiza badges em vários ramos de `result_info.type`.
- Para fluxo operacional aceito (`accepted_immediate` usado também para `pre_icu`, `ward_icu_backup`, `pediatric_em`), o badge vem de `result_info.badge`, populado por views (`apps/intake/views.py` e `apps/dashboard/views.py`) com `get_admission_flow_notice_copy()`.
- O texto `✓ Vinda para enfermaria com retaguarda em UTI` pode transbordar o limite direito do card no mobile.
- Slice 001 deve ter introduzido ou preparado padrão de badge compacto/quebrável para a lista do dashboard. Reutilize quando fizer sentido; não duplique sem necessidade.

Objetivo exato:

```text
Usuário abre detalhes do caso no mobile
→ card Resultado Final mostra badge sem transbordar o card
→ o chip pode usar texto compacto
→ texto completo/explicativo do fluxo permanece visível fora do chip quando aplicável
→ comportamento do fluxo, permissões e FSM permanecem inalterados
```

Limites de escopo:

- Não alterar labels das opções do médico.
- Não alterar FSM, models, migrations, permissões, filtros ou queries.
- Não mudar decisões médicas/agendamento/NIR.
- Não adicionar JS ou screenshot tests.
- Não reimplementar o sub-badge da lista do dashboard (Slice 001).

## Protocolo obrigatório para implementador DeepSeek4-Flash

Este slice será implementado por um modelo rápido e com tendência a concluir cedo demais. Portanto, siga este protocolo literalmente. **Se qualquer item abaixo falhar, o slice está INCOMPLETO**: não marque `tasks.md`, não faça commit/push e responda com bloqueio + evidência.

1. **Plano antes de editar**: escreva no relatório uma mini matriz `Requisito → arquivo(s) → teste(s)`. Não implemente requisito sem teste ou justificativa explícita.
2. **Baseline de pytest antes de editar**: registre `BASE_REF=$(git rev-parse HEAD)` e rode `uv run pytest` no estado inicial limpo. Cole no relatório o exit code e a linha de resumo. Se houver `failed/error` no baseline, pare e reporte INCOMPLETE/BLOQUEADO antes de codar.
3. **RED real**: crie/ajuste testes primeiro e rode o subconjunto alvo. Pelo menos um teste novo deve falhar pelo motivo esperado. Se o teste passar antes da implementação, ele não prova o comportamento; corrija o teste.
4. **GREEN mínimo**: implemente somente o necessário para os testes do slice passarem. Não faça refactor amplo, não toque em apps fora do escopo e não antecipe slices futuros.
5. **Verificação por inspeção**: além dos testes, rode buscas `rg`/inspeções descritas neste slice para comprovar os contratos críticos do slice.
6. **Quality gate completo e comparação pytest**: execute exatamente `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy .` e `uv run pytest`. O `uv run pytest` final deve ter exit code 0, zero failures/errors e contagem `passed` maior ou igual ao baseline. Se `failed > 0`, `errors > 0`, exit code != 0, ou `passed_final < passed_baseline`, o slice está INCOMPLETO.
7. **Relatório com evidência, não opinião**: cole comandos executados, exit codes, linhas de resumo do pytest baseline/final, testes RED/GREEN, snippets antes/depois e respostas objetivas aos gates. Inclua também `Handoff para verificador` com: arquivos alterados, comandos exatos para rerun, riscos/limitações e checklist dos requisitos R1..Rn. Inclua uma seção final `Status: COMPLETE` somente se todos os critérios estiverem comprovados.

### Condições automáticas de INCOMPLETO

Marque como incompleto se ocorrer qualquer uma destas situações:

- teste planejado não foi escrito ou não foi executado;
- baseline de pytest antes de editar não foi executado ou não foi registrado com exit code e resumo;
- quality gate completo não foi executado;
- qualquer teste/lint/mypy falhou;
- pytest final teve exit code diferente de 0, `failed > 0` ou `errors > 0`;
- contagem final de `passed` ficou menor que a contagem baseline;
- relatório cita apenas número de `passed` sem registrar explicitamente zero failures/errors e exit code 0;
- `tasks.md` foi marcado apesar de falha ou pendência;
- contrato crítico do slice não foi verificado por teste ou inspeção;
- comportamento antigo que deveria ser preservado foi removido sem teste de regressão;
- labels completos do médico foram alterados;
- models/migrations/FSM/permissões/queries/filtros foram alterados;
- texto completo/explicativo do fluxo sumiu do detalhe sem justificativa e teste;
- relatório temporário não foi criado no caminho exigido.

## Requisitos funcionais

### R1. Badge do Resultado Final não transborda no mobile

No card `Resultado Final`, badges com texto longo devem ter classe/estrutura que permita quebra/limite:

- `max-width: 100%`;
- quebra de linha (`white-space: normal` ou equivalente em classe dedicada);
- `overflow-wrap` quando necessário;
- alinhamento legível em mobile.

Preferir classe dedicada (por exemplo `badge-wrap` ou `result-final-badge`) para não alterar todos os badges do sistema.

### R2. Label compacto para fluxo operacional longo no chip

Para `ward_icu_backup`, o chip/badge do `Resultado Final` deve usar label compacto, por exemplo:

```text
✓ Enfermaria + retaguarda UTI
```

ou outro texto curto equivalente. Não usar no chip o texto longo:

```text
✓ Vinda para enfermaria com retaguarda em UTI
```

### R3. Texto completo preservado fora do chip

A informação completa do fluxo deve continuar disponível no card, por exemplo:

- no corpo explicativo (`result_info.body`), e/ou
- no campo textual `Fluxo`, que já renderiza `ADMISSION_FLOW_MAP`.

Não reduzir o conteúdo que orienta NIR/médico/agendador fora do badge.

### R4. Aplicar a correção ao detalhe aberto pelo dashboard e pelo NIR

Como o template é compartilhado, a correção deve funcionar quando:

- manager/admin acessa `dashboard:case_detail`;
- NIR acessa `intake:case_detail` ou detalhe histórico aplicável, se o mesmo bloco for usado.

Preservar diferenças existentes de permissão e ações por papel.

### R5. Preservar outros badges de resultado

Não quebrar badges de:

- agendamento confirmado;
- agendamento negado;
- médico negou;
- falha;
- revisão manual;
- intercorrência pós-agendamento.

Se adicionar classe comum aos badges do Resultado Final, garantir que ela não altera semântica nem remove classes Bootstrap (`bg-success`, `bg-danger`, etc.).

## Arquivos esperados

Idealmente tocar apenas:

1. `templates/intake/case_detail.html`
2. `apps/dashboard/views.py` e/ou `apps/intake/views.py` se precisar passar label compacto para `result_info`
3. `static/css/app.css` se necessário para classe dedicada de badge quebrável
4. `apps/dashboard/tests/test_dashboard.py` e/ou `apps/intake/tests/test_case_detail.py`

Se Slice 001 já criou helper/classe reutilizável, reutilizar em vez de duplicar. Se tocar outro arquivo, justificar no relatório.

Arquivos proibidos neste slice:

- migrations;
- models;
- FSM/transições;
- permissões/decorators;
- templates de decisão médica/opções do médico, salvo teste de preservação por inspeção.

## TDD obrigatório

### RED

Adicionar testes antes da implementação.

Testes mínimos sugeridos:

1. Dashboard detail de caso aceito com `doctor_admission_flow="ward_icu_backup"` renderiza o card `Resultado Final` com badge compacto e classe quebrável (`badge-wrap`/equivalente).
2. O mesmo detalhe ainda contém o texto completo do fluxo em algum ponto fora do chip (`Vinda para enfermaria (para retaguarda em UTI)` ou corpo equivalente com `retaguarda em UTI`).
3. NIR detail para o mesmo fluxo também renderiza badge com classe quebrável/sem overflow.
4. Regressão: classes Bootstrap de cor (`bg-success` etc.) continuam presentes no badge.

Rodar subconjunto alvo e comprovar RED real.

### GREEN

Implementar o mínimo:

- adicionar label compacto ao `result_info` ou derivar no template de modo simples e testável;
- aplicar classe CSS dedicada aos badges de Resultado Final;
- preservar texto completo no corpo/fluxo.

### REFACTOR

Revisar:

- reutilização de helper/constante criada no Slice 001 quando existir;
- sem duplicação ampla de strings;
- sem mexer em views não necessárias;
- CSS escopado.

## Checks de inspeção obrigatórios antes de concluir

Execute e cole resultado/resumo no relatório:

```bash
rg -n "badge-wrap|result-final-badge|accepted_immediate|result_info.badge|badge_compact|retaguarda" templates/intake/case_detail.html apps/dashboard/views.py apps/intake/views.py static/css/app.css
rg -n "Vinda para enfermaria \(para retaguarda em UTI\)|Vinda para enfermaria com retaguarda em UTI|Enfermaria \+ retaguarda UTI" apps/cases/admission.py apps/dashboard/views.py apps/intake/views.py templates/intake/case_detail.html apps/*/tests -S
rg -n "ADMISSION_FLOW_CHOICES|ward_icu_backup" apps/cases/admission.py templates/doctor apps/doctor -S
```

Interpretação esperada:

- Opções completas do médico permanecem em `apps/cases/admission.py`.
- Badge do Resultado Final tem classe/label compacto ou quebra segura.
- Texto completo/explicativo ainda aparece fora do chip ou nos dados de fluxo.

## Critérios de sucesso binários

- [ ] Baseline `uv run pytest` registrado antes de editar.
- [ ] Pelo menos um teste novo falhou no RED pelo motivo esperado.
- [ ] Badge do Resultado Final não usa texto longo como chip para `ward_icu_backup`.
- [ ] Badge do Resultado Final tem classe/estrutura anti-overflow.
- [ ] Texto completo/explicativo do fluxo permanece visível no detalhe.
- [ ] Detalhe dashboard e detalhe NIR continuam funcionando.
- [ ] Outros tipos de resultado mantêm classes/semântica.
- [ ] Nenhum model/migration/FSM/permissão/query/filtro foi alterado.
- [ ] Checks `rg` foram executados e interpretados.
- [ ] Quality gate completo passou.
- [ ] `tasks.md` marcou somente este slice após todos os gates.
- [ ] Relatório temporário foi criado em `/tmp/dashboard-badge-progress-ux-slice-002-report.md`.
- [ ] Commit e push realizados após gates verdes.

## Gates de autoavaliação

Responder no relatório:

1. Onde o badge do Resultado Final recebeu proteção contra overflow?
2. Qual label compacto foi usado para `ward_icu_backup`?
3. Onde o texto completo/explicativo continua disponível?
4. Qual teste cobre detalhe dashboard?
5. Qual teste cobre detalhe NIR ou justifica por template compartilhado?
6. Quais outros badges foram preservados?
7. Alguma opção do médico, model, migration, FSM, permissão ou query mudou?
8. O relatório contém evidência RED, GREEN, baseline/final e checks `rg`?

## Relatório obrigatório

Criar exatamente:

```text
/tmp/dashboard-badge-progress-ux-slice-002-report.md
```

O relatório deve conter:

- Status: COMPLETE ou INCOMPLETE;
- matriz requisito → arquivo(s) → teste(s);
- baseline de pytest antes de editar;
- evidência RED;
- evidência GREEN;
- snippets antes/depois;
- checks de inspeção `rg` e interpretação;
- comparação pytest baseline vs final;
- quality gate completo;
- respostas aos gates de autoavaliação;
- handoff para verificador.

## Prompt pronto para implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md and openspec/changes/dashboard-badge-progress-ux/{proposal.md,design.md,tasks.md,slices/slice-001-dashboard-card-badges-next-step.md,slices/slice-002-result-final-badge-mobile.md} first.
Implement ONLY Slice 002. Follow the DeepSeek4-Flash protocol in this file: plan, pytest baseline before editing, RED real, GREEN mínimo, inspection checks, full quality gate, pytest baseline-vs-final comparison and evidence report. If any required test/check/gate is missing or failing, if pytest final has any failure/error, or if passed_final < passed_baseline, report INCOMPLETE and do not update tasks.md or commit.
Assume Slice 001 may already have introduced reusable compact badge helpers/classes; reuse them if present. Goal: in the case detail card Resultado Final, long operational-flow badges must not overflow on mobile, and ward_icu_backup should use a compact chip while preserving full explanatory text elsewhere.
Do not touch models, migrations, FSM, permissions, filters, queries or doctor decision option labels. Do not implement dashboard list next-step behavior; that belongs to Slice 001.
Run quality gate exactly: uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
Update tasks.md only if all checks pass. Create /tmp/dashboard-badge-progress-ux-slice-002-report.md, commit and push, reply with REPORT_PATH and STOP for planner review.
```
