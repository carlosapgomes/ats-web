# QUICK bugfix: duração legível da espera na fila médica

## Status

- [x] Concluído

## Classificação e justificativa

- **Tipo:** QUICK bugfix simples e reversível.
- **Risco:** baixo; altera somente apresentação da duração já calculada.
- **Design separado:** dispensado pela exceção QUICK do `AGENTS.md`.
- **Sem alteração de regra temporal:** a espera deve continuar sendo calculada por `timezone.now() - Case.created_at`, com piso para minutos inteiros. Este bugfix não redefine quando o caso entrou na fila médica.

## Handoff para implementador LLM com contexto zero

Este projeto é um monolito Django SSR. Leia integralmente, antes de editar:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. este arquivo: `tasks/quick-bugfix-doctor-queue-wait-duration-format.md`
4. `apps/doctor/views.py`, especialmente:
   - `_build_case_card()`;
   - `_doctor_queue_context()`;
5. `templates/doctor/_queue_content.html`, especialmente:
   - o banner `Tempo médio de espera`;
   - o texto `Aguardando há` de cada card pendente;
6. `apps/doctor/tests/test_views.py`, especialmente os testes atuais de tempo de espera e média;
7. somente como referência de formato já aprovado no projeto, sem criar dependência entre apps: `apps/dashboard/views.py::_fmt_duration()` e os testes correspondentes em `apps/dashboard/tests/test_dashboard.py`.

### Estado técnico atual

A fila médica calcula corretamente minutos inteiros em `apps/doctor/views.py`:

```python
delta = now - case.created_at
wait_minutes = int(delta.total_seconds() // 60)
```

O valor numérico também é usado por regras existentes, por exemplo `is_urgent = wait_minutes <= 15`, e deve ser preservado.

O problema está na apresentação. O template imprime sempre minutos:

```django
Tempo médio de espera: {{ avg_wait_minutes }} min.
```

```django
⏱ Aguardando há {{ c.wait_minutes }} min
```

Assim, uma espera de 125 minutos aparece como `125 min`, em vez de `2 h 05 min`.

## Protocolo obrigatório para o implementador

**Se qualquer item obrigatório falhar ou não tiver evidência, o bugfix está INCOMPLETO. Não marque o status acima, não faça commit/push e reporte o bloqueio.**

1. Antes de editar, execute `git status --short`, registre a branch e `BASE_REF=$(git rev-parse HEAD)`. A árvore deve estar limpa; se houver alterações não relacionadas, pare e reporte bloqueio sem descartá-las.
2. Escreva no relatório uma matriz `Requisito → arquivo(s) → teste(s)`.
3. Rode o baseline completo `uv run pytest` antes de editar e registre exit code, quantidade de `passed`, `failed` e `errors`. Se o baseline falhar, pare antes de codar.
4. Faça **TDD real**: RED primeiro, GREEN mínimo depois e REFACTOR somente dentro do escopo.
5. Pelo menos um teste novo ou fortalecido deve falhar pelo motivo esperado antes da implementação. Registre comando, falha e motivo no relatório.
6. Preserve o número inteiro de minutos para cálculos e regras internas. Adicione uma projeção textual; não transforme `wait_minutes` em string.
7. Execute as inspeções obrigatórias e interprete os resultados no relatório.
8. Rode o quality gate completo, sem omitir comandos.
9. Compare pytest final com baseline: exit code final 0, zero failures/errors e `passed_final >= passed_baseline`.
10. Somente depois de todos os gates verdes: marque este arquivo como concluído, gere o relatório, faça commit claro, push da branch atual, acrescente hash/push ao relatório, responda com `REPORT_PATH` e pare.

## Objetivo vertical

```text
Caso WAIT_DOCTOR possui espera em minutos
→ view mantém o valor numérico para cálculos
→ view produz duração textual legível
→ card e média da fila usam a mesma apresentação
→ médico vê minutos quando curto e horas + minutos quando longo
```

## Requisitos funcionais

### R1. Formato canônico da duração

Criar em `apps/doctor/views.py` um helper pequeno, puro e testável que receba minutos inteiros e retorne:

| Minutos totais | Texto esperado |
| ---: | --- |
| `0` | `0 min` |
| `45` | `45 min` |
| `59` | `59 min` |
| `60` | `1 h` |
| `65` | `1 h 05 min` |
| `120` | `2 h` |
| `125` | `2 h 05 min` |
| `1100` | `18 h 20 min` |

Contrato:

- menos de 60 minutos permanece em `N min`;
- 60 minutos ou mais usa horas;
- quando houver resto, os minutos devem ter dois dígitos (`05 min`);
- múltiplos exatos de 60 não exibem `00 min`;
- não usar hora decimal (`1,08 h`);
- não alterar o arredondamento por piso já feito no cálculo da fila.

Nome sugerido, não obrigatório: `_format_wait_minutes(total_minutes: int) -> str`.

### R2. Cards pendentes usam a duração legível

`_build_case_card()` deve continuar expondo `wait_minutes` como `int` e adicionar um campo textual, por exemplo `wait_display`.

Em `templates/doctor/_queue_content.html`, trocar somente a projeção visual do card para algo equivalente a:

```django
⏱ Aguardando há {{ c.wait_display }}
```

Não deixar o sufixo fixo `min` no template.

### R3. Média da fila usa o mesmo formato

A média deve continuar sendo calculada em minutos inteiros como hoje. Adicionar ao contexto uma representação textual produzida pelo mesmo helper, por exemplo `avg_wait_display`, e renderizá-la no banner:

```django
Tempo médio de espera: {{ avg_wait_display }}.
```

Não duplicar no template a lógica de divisão por 60.

### R4. Preservar comportamento existente

Preservar integralmente:

- cálculo desde `Case.created_at`;
- piso para minutos inteiros;
- `wait_minutes` numérico;
- regra `is_urgent` e demais regras que consumam minutos;
- ordenação por `regulation_days_on_screen` e `created_at`;
- badge `Dias em tela`;
- abas Pendentes/Decididos Hoje;
- polling HTMX;
- locks, permissões, FSM e fluxo de decisão.

## Escopo esperado

Idealmente alterar somente:

1. `apps/doctor/views.py`
2. `templates/doctor/_queue_content.html`
3. `apps/doctor/tests/test_views.py`
4. este arquivo, apenas para marcar o status após todos os gates

Qualquer arquivo adicional exige justificativa objetiva no relatório.

## Fora de escopo / arquivos proibidos

Não alterar:

- models ou migrations;
- FSM, locks, permissões ou serviços de negócio;
- cálculo/base temporal da espera;
- fila do agendador (`apps/scheduler/` e `templates/scheduler/`);
- dashboard;
- extração ou badge de `Dias em tela`;
- CSS ou JavaScript;
- dependências do projeto;
- OpenSpec de features não relacionadas.

Não importar `apps.dashboard.views._fmt_duration`: é helper privado de outro app. Também não extrair agora uma abstração compartilhada envolvendo dashboard; isso ampliaria desnecessariamente um QUICK bugfix.

## TDD obrigatório

### RED

Antes da implementação, adicionar ou fortalecer testes em `apps/doctor/tests/test_views.py`.

Testes mínimos:

1. teste parametrizado do helper cobrindo pelo menos `0`, `59`, `60`, `65`, `120`, `125` e `1100`;
2. teste de renderização de um caso com espera determinística de 65 minutos, exigindo exatamente:
   - `Aguardando há 1 h 05 min`;
   - `Tempo médio de espera: 1 h 05 min.` quando esse for o único pendente;
3. regressão de duração curta, exigindo `Aguardando há 45 min`;
4. prova de que `wait_minutes` continua inteiro e `is_urgent` continua baseado no valor numérico, diretamente em `_build_case_card()` ou por teste equivalente.

Para testes baseados em `timezone.now()`, fixe/monkeypatch o instante de forma determinística. Não use asserts frouxos como `"65" in content or "min" in content`, pois eles não provam o contrato.

Execute o RED focado e registre a falha esperada:

```bash
uv run pytest apps/doctor/tests/test_views.py -q
```

### GREEN

Implemente somente R1–R4 e rode novamente:

```bash
uv run pytest apps/doctor/tests/test_views.py -q
```

### REFACTOR

- manter um único helper de formatação dentro do app doctor;
- usar `divmod` ou lógica igualmente clara;
- evitar lógica aritmética no template;
- remover nomes/asserções frouxos tocados por este bugfix;
- não fazer refactor amplo da view ou dos testes.

## Checks de inspeção obrigatórios

Execute e cole resultado + interpretação no relatório:

```bash
rg -n "wait_minutes|wait_display|avg_wait_minutes|avg_wait_display|is_urgent" \
  apps/doctor/views.py templates/doctor/_queue_content.html apps/doctor/tests/test_views.py

rg -n "Aguardando há.*min|avg_wait_minutes.*min|c\.wait_minutes.*min" \
  templates/doctor/_queue_content.html || true

rg -n "regulation_days_on_screen|Dias em tela" \
  apps/doctor/views.py templates/doctor/_queue_content.html

git diff --check
git status --short
```

Interpretação esperada:

- `wait_minutes` permanece numérico na view e continua alimentando `is_urgent`;
- card e banner usam campos textuais formatados;
- não resta sufixo fixo `min` acoplado a `c.wait_minutes` ou `avg_wait_minutes` no template;
- badge e ordenação de `Dias em tela` continuam presentes;
- não há whitespace errors nem arquivos inesperados.

## Critérios de sucesso binários

- [ ] Baseline completo foi executado antes da edição, com exit code e resumo registrados.
- [ ] Existe RED real pelo motivo esperado.
- [ ] Durações abaixo de 60 minutos permanecem em minutos.
- [ ] `60` vira `1 h`.
- [ ] `65` vira `1 h 05 min`.
- [ ] Múltiplos exatos de hora não exibem `00 min`.
- [ ] Card pendente usa duração textual sem sufixo fixo no template.
- [ ] Média usa exatamente o mesmo helper/formato.
- [ ] `wait_minutes` continua sendo `int`.
- [ ] `is_urgent` continua sendo calculado com minutos numéricos.
- [ ] Base temporal, ordenação, badge, locks, FSM e permissões não mudaram.
- [ ] Nenhum model, migration, scheduler, dashboard, CSS, JS ou dependência foi alterado.
- [ ] Inspeções foram executadas e interpretadas.
- [ ] Quality gate completo passou.
- [ ] Pytest final tem exit code 0, zero failures/errors e total de passed maior ou igual ao baseline.
- [ ] Relatório contém evidências, snippets antes/depois e handoff para verificador.
- [ ] Commit e push foram concluídos somente após todos os gates.

## Gates de autoavaliação

Responder objetivamente no relatório:

1. Qual teste RED falhou antes da implementação e por quê?
2. Qual helper é a fonte única do formato no app doctor?
3. Quais são as saídas exatas para `59`, `60`, `65`, `120` e `125` minutos?
4. Onde está provado que `wait_minutes` permanece inteiro?
5. Onde está provado que `is_urgent` não passou a comparar string?
6. Card e média usam o mesmo helper? Indique as linhas/fluxo.
7. O cálculo ainda começa em `Case.created_at`? Mostre evidência.
8. A ordenação por `regulation_days_on_screen` foi preservada?
9. Houve alteração fora dos quatro arquivos esperados? Se sim, por quê?
10. O pytest final tem zero failures/errors e `passed_final >= passed_baseline`?
11. Qual commit foi criado e para qual remoto/branch o push foi feito?

### Condições automáticas de INCOMPLETO

Marque como incompleto se ocorrer qualquer situação abaixo:

- baseline completo não executado ou baseline com falha;
- ausência de RED real;
- teste novo passa antes da implementação sem comprovar mudança;
- teste usa assert frouxo que aceita o formato antigo;
- `wait_minutes` é convertido em string;
- `is_urgent` ou outra regra passa a depender do texto formatado;
- card ou média continua sempre em minutos;
- card e média usam formatadores divergentes;
- cálculo temporal ou ordenação é alterado;
- model, migration, scheduler, dashboard, CSS, JS, FSM, lock ou permissão é alterado;
- qualquer comando do quality gate falha;
- pytest final tem exit code diferente de zero, qualquer failure/error ou menos testes passando que o baseline;
- inspeção obrigatória ou resposta de gate fica ausente;
- status deste arquivo é marcado antes dos gates;
- relatório temporário, commit ou push fica ausente.

## Quality gate obrigatório

Executar separadamente e registrar comando, exit code e resumo:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
```

Também registrar:

```bash
git diff --check
git status --short
```

## Relatório de implementação obrigatório

Criar:

```text
/tmp/doctor-queue-wait-duration-quick-bugfix-report.md
```

O relatório deve conter:

1. `Status: COMPLETE` ou `Status: INCOMPLETE`;
2. branch e `BASE_REF`;
3. matriz `R1–R4 → arquivos → testes/inspeções`;
4. baseline pytest com comando, exit code, passed, failed e errors;
5. RED com comando, falha e motivo esperado;
6. GREEN e REFACTOR;
7. arquivos alterados;
8. snippets antes/depois de:
   - helper/contexto da view;
   - card;
   - banner de média;
   - testes;
9. tabela demonstrativa das saídas `0`, `45`, `59`, `60`, `65`, `120`, `125`, `1100`;
10. saídas e interpretação dos checks de inspeção;
11. quality gate completo com exit codes;
12. comparação `passed_final >= passed_baseline` e confirmação explícita de zero failures/errors;
13. respostas aos gates de autoavaliação;
14. riscos/limitações, incluindo que a espera continua baseada em `created_at`;
15. hash do commit e evidência do push;
16. `Handoff para verificador` com arquivos alterados, comandos exatos para rerun e checklist R1–R4.

Somente use `Status: COMPLETE` se todos os critérios estiverem comprovados.

## Commit, push e parada obrigatória

Se e somente se estiver COMPLETE:

1. marque `Status` deste arquivo como concluído;
2. faça commit rastreável, sugestão:

```text
fix(doctor): format queue wait duration in hours
```

3. faça push da branch atual;
4. atualize o relatório temporário com hash e evidência do push;
5. responda exatamente:

```text
REPORT_PATH=/tmp/doctor-queue-wait-duration-quick-bugfix-report.md
```

6. **PARE**. Não inicie outro slice ou refactor sem confirmação explícita.

## Prompt pronto para entregar ao implementador LLM

```text
Read AGENTS.md and PROJECT_CONTEXT.md completely, then read tasks/quick-bugfix-doctor-queue-wait-duration-format.md and every source/test file listed in its zero-context handoff.

Implement ONLY this QUICK bugfix. Follow the protocol literally: clean-tree check, full pytest baseline before editing, requirement-to-test plan, real TDD RED, minimal GREEN, scoped REFACTOR, mandatory rg inspections, full quality gate, baseline-vs-final comparison, evidence report, commit and push. If any required evidence is absent/failing, report INCOMPLETE and do not mark status or commit/push.

Keep wait_minutes numeric and preserve calculation from Case.created_at, floor rounding, is_urgent, queue ordering, Dias em tela, tabs, polling, locks, permissions and FSM. Add one pure doctor-side formatter: <60 remains N min; >=60 becomes H h with a two-digit minute remainder when nonzero. Expose formatted values for both each pending card and the average banner. Required examples: 60 -> 1 h, 65 -> 1 h 05 min, 120 -> 2 h, 125 -> 2 h 05 min. Do not import the dashboard private helper and do not touch dashboard, scheduler, models, migrations, CSS, JS, dependencies or unrelated OpenSpec artifacts.

Add deterministic strict tests first in apps/doctor/tests/test_views.py, prove RED, then implement minimally in apps/doctor/views.py and templates/doctor/_queue_content.html. Run exactly: uv run ruff check .; uv run ruff format --check .; uv run mypy .; uv run pytest. Require final exit code 0, zero failures/errors and passed_final >= passed_baseline.

Only when COMPLETE, mark the status in the task file, create /tmp/doctor-queue-wait-duration-quick-bugfix-report.md with all required evidence and Handoff para verificador, commit, push the current branch, reply REPORT_PATH=/tmp/doctor-queue-wait-duration-quick-bugfix-report.md, and STOP.
```
