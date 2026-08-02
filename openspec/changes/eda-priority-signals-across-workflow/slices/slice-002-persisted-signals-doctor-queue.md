# Slice 002: Sinalizações canônicas persistidas, backfill de abertos e badges na fila médica

## Status

- [ ] Pendente

## Handoff para implementador LLM com contexto zero

Este slice começa somente após Slice 001 concluído, validado, commitado e enviado. O sistema já deve reconhecer `echoendoscopy` como EDA suportada, aplicar policy padrão e exibir nome canônico no relatório atual.

Agora é necessário criar a fonte canônica que acompanhará o caso. Hoje pediatria, corpo estranho, ingestão cáustica, dilatação e gastrostomia são detectados em lugares diferentes. O objetivo é persistir os sinais para novos casos, fazer backfill apenas dos casos abertos e mostrar badges já na fila médica, antes de o triador abrir o caso.

Leia completamente antes de editar:

- `AGENTS.md`
- `PROJECT_CONTEXT.md`
- todos os artefatos deste change
- relatório/veredito do Slice 001
- `apps/cases/models.py`
- migrations `0010`, `0012` e testes de migration existentes
- `apps/pipeline/orchestrator.py`
- `apps/pipeline/scope_detection.py`
- detector cáustico atual em `apps/doctor/presenters.py`
- `apps/doctor/views.py`
- `templates/doctor/_queue_content.html`
- testes correspondentes

Implemente somente persistência/resolução + fila médica. Não altere ainda o topo/corpo da tela de decisão, CHD ou NIR; esses são Slices 003–005.

## Protocolo obrigatório para implementador DeepSeek4-Flash

Este slice será implementado por um modelo rápido e com tendência a concluir cedo demais. Portanto, siga este protocolo literalmente. **Se qualquer item abaixo falhar, o slice está INCOMPLETO**: não marque `tasks.md`, não faça commit/push e responda com bloqueio + evidência.

1. **Plano antes de editar**: escreva no relatório uma mini matriz `Requisito → arquivo(s) → teste(s)`. Não implemente requisito sem teste ou justificativa explícita.
2. **Baseline de pytest antes de editar**: registre `BASE_REF=$(git rev-parse HEAD)` e rode `uv run pytest` no estado inicial limpo. Cole no relatório o exit code e a linha de resumo. Se houver `failed/error` no baseline, pare e reporte INCOMPLETE/BLOQUEADO antes de codar.
3. **RED real**: crie/ajuste testes primeiro e rode o subconjunto alvo. Pelo menos um teste novo deve falhar pelo motivo esperado. Se o teste passar antes da implementação, ele não prova o comportamento; corrija o teste.
4. **GREEN mínimo**: implemente somente o necessário para os testes do slice passarem. Não faça refactor amplo, não toque em apps fora do escopo e não antecipe slices futuros.
5. **Verificação por inspeção**: além dos testes, rode buscas `rg`/inspeções descritas neste slice para comprovar os contratos críticos do slice.
6. **Quality gate completo e comparação pytest**: execute exatamente `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy .` e `uv run pytest`. O `uv run pytest` final deve ter exit code 0, zero failures/errors e contagem `passed` maior ou igual ao baseline. Se `failed > 0`, `errors > 0`, exit code != 0, ou `passed_final < passed_baseline`, o slice está INCOMPLETO.
7. **Relatório com evidência, não opinião**: cole comandos executados, exit codes, linhas de resumo do pytest baseline/final, testes RED/GREEN, snippets antes/depois e respostas objetivas aos gates. Inclua também `Handoff para verificador` com: arquivos alterados, comandos exatos para rerun, riscos/limitações e checklist dos requisitos R1..Rn. Inclua uma seção final `Status: COMPLETE` somente se todos os critérios estiverem comprovados.

## Objetivo do slice

Entregar a fatia vertical:

```text
novo caso termina LLM1
→ resolvedor puro identifica todos os sinais
→ Case.priority_signals é persistido e auditado
→ casos abertos existentes recebem backfill sem LLM
→ fila médica projeta badges compartilhados
→ triador identifica o direcionamento antes de abrir
```

## Contexto técnico atual

- `Case` já persiste JSON de LLM e sugestão, mas não sinais derivados.
- `CaseEvent` é append-only; `LLM1_OK` já registra `summary_text`.
- O pipeline salva `structured_data` em `_run_llm1_step()` antes do scope.
- A fila médica usa dicionários criados em `_build_case_card()` e `templates/doctor/_queue_content.html`.
- A detecção cáustica está dentro do presenter médico; deve haver uma única implementação compartilhada ao final deste slice, sem regressão de negação/tempo.
- Migration de backfill deve usar historical models e ser testada de forma equivalente a `test_post_acceptance_issue_migration.py`.

## Requisitos funcionais

### R1. Campo persistido

Adicionar em `Case`:

```python
priority_signals = models.JSONField(default=list, blank=True)
```

Requisitos:

- default independente por instância;
- fixtures/casos antigos funcionam sem preencher explicitamente;
- sem index neste change;
- não modificar `structured_data` ou `suggested_action` para guardar sinais.

### R2. Contrato canônico versão 1

Criar `apps/cases/priority_signals.py` com constantes/tipos/helpers pequenos. Cada item persistido deve conter:

- `code` conhecido;
- `category` canônica;
- `detail` curto, possivelmente vazio;
- `version: 1`.

Códigos e ordem exatos:

```text
foreign_body
caustic_ingestion
pediatric
echoendoscopy
esophageal_dilation
gastrostomy
```

Categorias:

- alertas: `clinical_alert`;
- pediatria: `special_population`;
- procedimentos: `special_procedure`.

Deduplicar por código. Não persistir label traduzido ou CSS.

### R3. Resolvedor puro e conservador

API pública conceitual:

```python
resolve_priority_signals(
    *, structured_data: dict[str, object], source_text: str
) -> list[dict[str, object]]
```

Detectar:

1. `pediatric`: idade inteira `< 16`; fallback `eda.is_pediatric=True` somente quando idade indisponível. Detail com idade quando disponível.
2. `foreign_body`: subtipo solicitado/rulebook, `indication_category`, `foreign_body_suspected` e fallback textual positivo.
3. `caustic_ingestion`: preservar detector atual com proximidade, negação e tempo.
4. `echoendoscopy`: subtipo e termos aprovados; `EUS` somente contextual.
5. `esophageal_dilation`: subtipo/termos esofágicos conservadores; não aceitar `dilatação` isolada.
6. `gastrostomy`: subtipo e GTT/PEG/gastrostomia em contexto procedimental.

Negação mínima de corpo estranho:

- `sem corpo estranho`;
- `corpo estranho descartado`;
- `nega ingestão de corpo estranho`;
- `não há corpo estranho`.

Um sinal estruturado explicitamente positivo e validado pode prevalecer sobre fallback textual negado apenas se representar a solicitação atual; documentar precedência em código/testes. Não inventar sistema de confidence.

### R4. Projeção de badges compartilhada

No mesmo módulo, criar helper tolerante a payload:

```python
build_priority_signal_badges(priority_signals: object) -> list[dict[str, str]]
```

Deve:

- ignorar valor que não seja lista;
- ignorar itens não dict, código desconhecido, duplicado ou versão incompatível;
- ordenar canonicamente;
- projetar `code`, `label`, `css_class`, `emphasis`;
- usar mesma classe/ênfase `warning` para corpo estranho e cáustico;
- incluir detail de idade/tempo quando seguro;
- não executar detecção.

Criar partial SSR compartilhado:

```text
templates/cases/_priority_signals.html
```

Ele recebe `priority_signal_badges`, usa Bootstrap 5.3, permite wrap e não renderiza container vazio.

### R5. Persistência para novos casos e auditoria

Em `_run_llm1_step()`:

1. obter `structured_data` validado;
2. resolver sinais usando `case.extracted_text`;
3. salvar `structured_data`, `summary_text` e `priority_signals` juntos antes do scope;
4. incluir `priority_signal_codes` no payload de `LLM1_OK`.

Não registrar detail/texto clínico no evento. Não chamar resolvedor novamente em views.

### R6. Migration e backfill de casos abertos

Criar próxima migration real (confirmar leaf atual; esperado `0013`):

- `AddField priority_signals`;
- `RunPython` forward, reverso `noop`;
- somente `status != CLEANED`;
- somente lista ainda vazia;
- sem LLM, sem eventos e sem mudança de status/decisão/agenda;
- chunks razoáveis;
- idempotente;
- casos `CLEANED` permanecem `[]`.

A migration histórica precisa ser autocontida. Se copiar snapshot do detector v1 por estabilidade histórica, comentar claramente e manter cobertura de equivalência dos seis códigos; não importar `Case` runtime diretamente.

### R7. Fila médica

Adicionar `priority_signal_badges` a `_build_case_card()` usando exclusivamente `case.priority_signals` persistido.

Em `templates/doctor/_queue_content.html`, incluir o partial próximo ao nome/meta do paciente e antes do resumo principal tanto onde aplicável aos cards pendentes. Não redesenhar fila, não alterar ordenação, polling, links ou locks.

Casos sem sinais não mostram espaço/container vazio.

### R8. Não antecipar tela de decisão/downstream

Neste slice é proibido:

- alterar `templates/doctor/decision.html` para badges/corpo;
- alterar `DoctorReportPresenter` para consumir persistência (Slice 003);
- alterar scheduler ou intake;
- atribuição automática, agenda, filtros novos, FSM ou permissões.

Mover o detector cáustico para o módulo compartilhado é permitido/necessário; preservar API temporária do presenter ou adaptar import sem implementar a apresentação final do Slice 003.

## Arquivos esperados

Núcleo esperado:

1. `apps/cases/models.py`
2. `apps/cases/priority_signals.py` (novo)
3. `apps/cases/migrations/0013_*.py` (nome após inspeção)
4. `apps/pipeline/orchestrator.py`
5. `apps/doctor/views.py`
6. `templates/cases/_priority_signals.html` (novo)
7. `templates/doctor/_queue_content.html`
8. testes focados em `apps/cases/tests/`, `apps/pipeline/tests/test_orchestrator.py` e `apps/doctor/tests/`
9. `apps/doctor/presenters.py` apenas para mover/reusar detector cáustico sem regressão
10. `tasks.md` somente ao concluir

Este é o slice estrutural maior. Ainda assim, não tocar scheduler/intake, FSM, forms ou CSS global. No relatório, listar cada arquivo e associá-lo a requisito/teste; qualquer arquivo sem requisito é escopo indevido.

## TDD obrigatório

### RED 1 — resolvedor/projeção

Criar testes unitários antes do código para:

- cada código isolado;
- combinações e ordem canônica;
- deduplicação;
- pediatria idade 15 versus 16;
- fallback pediátrico sem idade;
- corpo estranho positivo e negações;
- cáustico positivo com tempo e negações já cobertas;
- eco sinônimos e EUS contextual/isolado;
- dilatação esofágica versus palavra genérica;
- gastrostomia/GTT/PEG;
- payload malformado/versão desconhecida na projeção;
- igualdade de `emphasis/css_class` entre corpo estranho e cáustico.

### RED 2 — pipeline

Adicionar teste provando:

- novos casos persistem múltiplos sinais após LLM1;
- `LLM1_OK.payload.priority_signal_codes` contém somente códigos ordenados;
- sinais existem antes de scope/LLM2;
- falha de pipeline não cria valor parcial enganoso.

### RED 3 — migration

Adicionar teste direto/forward com `MigrationExecutor` provando:

- aberto recebe sinais;
- `CLEANED` não recebe;
- lista existente não é sobrescrita;
- status/decisão permanecem;
- reexecução defensiva é idempotente.

### RED 4 — fila médica

Adicionar teste de view/template:

- caso `WAIT_DOCTOR` com sinais mostra labels na fila;
- ordem dos labels é canônica;
- caso vazio não renderiza container;
- nenhum texto bruto é usado para redetectar durante view.

Rodar subconjuntos RED e registrar falhas. Pelo menos um teste novo deve falhar antes da implementação.

### GREEN

Implementar R1–R8 minimamente. Rodar testes de casos, pipeline e doctor focados.

### REFACTOR

- Um resolvedor puro, sem ORM.
- Uma tabela/mapping de metadados de apresentação, sem ifs duplicados por app.
- Reusar normalização; não duplicar detector cáustico.
- Funções pequenas para sinais independentes.
- Não criar framework genérico de regras/confidence/plugins.
- Não consultar PDF/texto nas views.
- Remover código cáustico morto após mover, preservando regressões.

## Checks de inspeção obrigatórios antes de concluir

```bash
rg -n "priority_signals" apps/cases/models.py apps/cases/migrations apps/cases/priority_signals.py \
  apps/pipeline/orchestrator.py apps/doctor/views.py templates/cases templates/doctor/_queue_content.html

rg -n "foreign_body|caustic_ingestion|pediatric|echoendoscopy|esophageal_dilation|gastrostomy" \
  apps/cases/priority_signals.py apps/cases/migrations/0013_*.py

rg -n "CLEANED|RunPython|iterator|chunk_size" apps/cases/migrations/0013_*.py

rg -n "_detect_caustic_ingestion|_CAUSTIC_|resolve_priority_signals" apps/doctor/presenters.py apps/cases/priority_signals.py

rg -n "priority_signal_badges|cases/_priority_signals.html" apps/doctor/views.py templates/doctor/_queue_content.html

rg -n "priority_signals" apps/scheduler apps/intake templates/scheduler templates/intake || true

git diff --check
git status --short
```

Interpretar:

- os seis códigos existem no resolvedor e snapshot de backfill;
- migration exclui `CLEANED` e não chama LLM;
- não há duas implementações runtime do detector cáustico;
- fila médica usa partial compartilhado;
- scheduler/intake permanecem intocados;
- nenhum arquivo de migration anterior foi editado.

## Critérios de sucesso binários

- [ ] Baseline full pytest verde registrado.
- [ ] RED real registrado antes de produção.
- [ ] Campo JSON usa `default=list` e migration nova.
- [ ] Seis códigos canônicos são resolvidos, deduplicados e ordenados.
- [ ] Negação de corpo estranho e cáustico está coberta.
- [ ] EUS/dilatação genérica não criam falso positivo.
- [ ] Projeção tolera payload malformado.
- [ ] Corpo estranho e cáustico têm mesma ênfase.
- [ ] Novos casos persistem antes do scope e auditam códigos.
- [ ] Backfill afeta somente abertos e não sobrescreve valores.
- [ ] Casos `CLEANED` preexistentes permanecem vazios.
- [ ] Fila médica mostra badges do valor persistido.
- [ ] Caso vazio não mostra container.
- [ ] Scheduler/intake e tela de decisão não foram antecipados.
- [ ] Inspeções executadas e interpretadas.
- [ ] Quality gate completo verde; final >= baseline.
- [ ] Relatório/handoff, task, commit e push corretos.

## Gates de autoavaliação

1. Por que os sinais ficam fora de `structured_data` e `suggested_action`?
2. Qual é o formato persistido exato e como a versão desconhecida é tratada?
3. Qual teste prova coexistência e ordem?
4. Qual teste prova que `CLEANED` não sofre backfill?
5. Qual teste prova idempotência e preservação de decisão/status?
6. Há alguma chamada LLM na migration? Deve ser “não”.
7. Views detectam sinais do texto bruto? Deve ser “não”.
8. Onde ficou a única implementação runtime de cáustico?
9. Como o evento evita copiar texto clínico adicional?
10. Algum arquivo extra foi necessário? Por quê?
11. O que permanece para Slices 003–005?

### Condições automáticas de INCOMPLETO

Marque INCOMPLETO se:

- qualquer regra do protocolo DeepSeek não tiver evidência;
- teste de migration/backfill não existir ou não rodar;
- caso `CLEANED` for alterado;
- migration chamar LLM, alterar status/decisão/agenda ou criar eventos em massa;
- campo for colocado em `structured_data` em vez de `Case.priority_signals`;
- views redetectarem texto em vez de usar persistência;
- coexistência for implementada por enum combinatório;
- corpo estranho/cáustico tiverem ênfase divergente;
- payload malformado causar exceção;
- código cáustico runtime ficar duplicado;
- fila médica não mostrar badges ou mostrar container vazio;
- scheduler/intake/tela de decisão forem alterados;
- migration antiga for editada;
- qualquer lint/mypy/teste falhar ou final ficar abaixo do baseline;
- task for marcada, commit/push feito ou Status COMPLETE sem todos os gates;
- relatório exigido estiver ausente.

## Relatório obrigatório

Criar exatamente:

```text
/tmp/eda-priority-signals-slice-002-report.md
```

Incluir:

- `Status: COMPLETE|INCOMPLETE`;
- matriz R1–R8 → arquivos → testes;
- baseline e `BASE_REF`;
- RED/GREEN/REFACTOR;
- snippets antes/depois do model, resolvedor, pipeline, migration e fila;
- evidência direta da migration;
- inspeções e interpretação;
- baseline versus final;
- quality gate;
- respostas aos gates;
- justificativa arquivo a arquivo;
- handoff para verificador com rerun exato e checklist R1–R8.

## Prompt pronto para implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md, all artifacts of openspec/changes/eda-priority-signals-across-workflow, the completed Slice 001 report/verdict, and the current model/migrations, pipeline orchestrator, doctor queue builder/template, caustic detector and tests. Implement ONLY Slice 002.

Follow the DeepSeek4-Flash protocol literally: matrix plan, clean full-pytest baseline before editing, real RED, minimal GREEN, clean REFACTOR, mandatory rg inspections, complete quality gate and passed_final >= passed_baseline. Any missing/failing evidence means INCOMPLETE: do not update tasks.md, commit or push.

Create Case.priority_signals as a versioned JSON projection, a pure shared resolver/projection for the six canonical codes, pipeline persistence immediately after LLM1 with code-only audit payload, an idempotent migration/backfill only for status != CLEANED, and shared SSR badges in the doctor queue. Preserve caustic negation/time behavior while removing runtime duplication. Use persisted values in views; never redetect PDF text there.

Use clean code, DRY, YAGNI, small cohesive functions, explicit names and no speculative confidence/plugin framework. Do not alter doctor decision report yet, scheduler, intake, FSM, permissions, locks, forms, agenda or colonoscopy support.

Run exactly uv run ruff check .; uv run ruff format --check .; uv run mypy .; uv run pytest. Mark only Slice 002 after every criterion passes. Create /tmp/eda-priority-signals-slice-002-report.md with RED/GREEN, migration evidence, before/after snippets, inspections, quality gate, exact rerun commands and Handoff para verificador. Commit/push only if COMPLETE. Reply REPORT_PATH=/tmp/eda-priority-signals-slice-002-report.md and STOP.
```
