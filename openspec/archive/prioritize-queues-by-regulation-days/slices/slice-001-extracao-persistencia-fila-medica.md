# Slice 001: Extração persistida + fila médica priorizada

## Handoff para implementador LLM com contexto zero

Você está no projeto `/projects/dev/ats-web`, um monolito Django 5.2 SSR com templates Bootstrap, sem API REST e sem SPA.

Antes de codar, leia obrigatoriamente:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `openspec/changes/prioritize-queues-by-regulation-days/proposal.md`
4. `openspec/changes/prioritize-queues-by-regulation-days/design.md`
5. `openspec/changes/prioritize-queues-by-regulation-days/tasks.md`
6. Este arquivo de slice

Implemente **somente este slice**. Não altere a fila do agendador neste slice. Use TDD: RED → GREEN → REFACTOR. No refactor, aplique clean code, DRY e YAGNI: parser pequeno, nomes claros, sem abstrações genéricas, sem score de prioridade e sem LLM.

## Objetivo do slice

Entregar uma fatia vertical completa para a fila médica:

```text
PDF com “Dias em tela: N” -> extração persiste N no Case -> fila médica ordena por maior N -> médico vê N no card
```

## Escopo funcional

- Criar campo persistente opcional em `Case` para o número impresso em `Dias em tela`.
- Criar parser determinístico que extrai o número de `Dias em tela: N` do texto extraído.
- Se houver múltiplas ocorrências, usar o maior número.
- Se não houver ocorrência, salvar `NULL`.
- Persistir o campo durante a extração de PDF para casos novos.
- Backfill de casos existentes a partir de `extracted_text` via migration/data migration.
- Ordenar a fila médica `WAIT_DOCTOR` por maior `Dias em tela`, com `NULL` por último e `created_at` como desempate.
- Exibir `Dias em tela: N` nos cards pendentes da fila médica quando disponível.

## Fora de escopo neste slice

- Fila do agendador.
- Cards de vinda imediata.
- Somar dias desde upload.
- Criar score composto de prioridade.
- Alterar FSM/transições/eventos.
- Usar LLM para extração.
- Criar filtros ou dashboard.

## Arquivos prováveis

Mantenha as alterações mínimas por arquivo. Arquivos previstos:

1. `apps/cases/models.py`
2. nova migration em `apps/cases/migrations/`
3. `apps/intake/pdf_utils.py`
4. `apps/intake/tasks.py`
5. `apps/doctor/views.py`
6. `templates/doctor/_queue_content.html`
7. testes em `apps/intake/tests/` e `apps/doctor/tests/`
8. `openspec/changes/prioritize-queues-by-regulation-days/tasks.md`

Este slice toca mais de 5 arquivos porque é deliberadamente vertical: modelo + extração + UI médica. Não amplie além disso sem justificar no relatório.

## Estado técnico relevante

- `apps/intake/tasks.py::_do_extraction` já persiste `extracted_text` após `strip_watermark_and_extract_record`.
- `apps/intake/pdf_utils.py` já contém helpers determinísticos de PDF, incluindo extração de número de registro.
- `apps/doctor/views.py::_doctor_queue_context` hoje faz `.order_by("created_at")` para `WAIT_DOCTOR`.
- `apps/doctor/views.py::_build_case_card` centraliza dados dos cards médicos.
- `templates/doctor/_queue_content.html` renderiza os cards pendentes.

## Plano TDD obrigatório

### RED — testes primeiro

Crie/atualize testes antes da implementação.

#### 1. Parser determinístico

Em teste de `apps/intake/pdf_utils.py` ou arquivo existente apropriado:

- `Dias em tela: 0` → retorna `0`.
- `Dias em tela: 12` → retorna `12`.
- variação de espaços/caixa, por exemplo `DIAS EM TELA : 7` → retorna `7`.
- múltiplas ocorrências `3`, `5`, `4` → retorna `5`.
- texto sem ocorrência → retorna `None`.

#### 2. Extração persiste o valor

Em `apps/intake/tests/test_pdf_extraction_task.py` ou equivalente:

- monkeypatch de `extract_pdf_text` retornando relatório válido com `Dias em tela: 9`;
- executar `execute_pdf_extraction`;
- assert `case.regulation_days_on_screen == 9`.

Adicionar caso com múltiplas ocorrências se couber sem duplicação excessiva.

#### 3. Data migration/backfill

Cobertura mínima aceitável:

- teste indireto via migration é opcional se o projeto não tiver padrão para migration tests;
- se não houver teste de migration, registrar no relatório que a migration duplica a regra do parser e foi revisada.

Preferível: testar a função/helper usado na migration se ela for isolável sem acoplar migration a código runtime. Não criar arquitetura pesada só para isso.

#### 4. Fila médica ordena e exibe

Em `apps/doctor/tests/test_views.py` ou arquivo equivalente:

- criar usuário médico logado;
- criar três casos `WAIT_DOCTOR`:
  - A com `regulation_days_on_screen=2`;
  - B com `regulation_days_on_screen=10`;
  - C com `regulation_days_on_screen=None`;
- acessar `doctor:queue`;
- assert que B aparece antes de A, e A antes de C;
- assert que aparece texto/badge `Dias em tela: 10` e `Dias em tela: 2`;
- assert que o card sem dado não mostra `Dias em tela: None` nem badge vazia.

Adicionar teste de desempate por `created_at` se a suíte já tiver helper simples para controlar datas; se for custoso, cubra no teste de ordenação principal com dois casos empatados.

### GREEN — implementação mínima

#### 1. Modelo

Adicionar em `apps/cases/models.py::Case`:

```python
regulation_days_on_screen = models.PositiveIntegerField(null=True, blank=True, db_index=True)
```

Posição sugerida: perto de `extracted_text`/`agency_record_number`, pois é metadado extraído do relatório.

Criar migration nova após `0009_system_notices.py`.

#### 2. Migration/data backfill

Na migration, adicionar o campo e preencher casos existentes com `extracted_text`.

Regra do backfill:

```python
matches = [int(value) for value in pattern.findall(text or "")]
value = max(matches) if matches else None
```

Não importar `apps.intake.pdf_utils` dentro da migration. Use regex local simples para estabilidade histórica.

#### 3. Parser em `apps/intake/pdf_utils.py`

Adicionar helper puro:

```python
def extract_regulation_days_on_screen(text: str) -> int | None:
    ...
```

Mantenha pequeno e testável.

#### 4. Persistência em `apps/intake/tasks.py`

Importar/chamar o novo helper em `_do_extraction` e persistir antes de `case.save()`:

```python
case.regulation_days_on_screen = extract_regulation_days_on_screen(cleaned_text)
```

#### 5. Fila médica

Em `apps/doctor/views.py`:

- importar `F` de `django.db.models`;
- trocar ordenação dos pendentes para:

```python
.order_by(F("regulation_days_on_screen").desc(nulls_last=True), "created_at")
```

- adicionar ao card:

```python
"regulation_days_on_screen": case.regulation_days_on_screen,
```

#### 6. Template médico

Em `templates/doctor/_queue_content.html`, exibir badge curta quando o dado existir:

```django
{% if c.regulation_days_on_screen is not None %}
<span class="badge bg-warning text-dark mb-2">Dias em tela: {{ c.regulation_days_on_screen }}</span>
{% endif %}
```

Escolha local discreto perto dos metadados do caso. Não remova `Aguardando há {{ c.wait_minutes }} min`.

## Critérios de aceitação do slice

- [ ] Campo `Case.regulation_days_on_screen` existe, é opcional e indexado.
- [ ] Parser retorna `0`, inteiros positivos, maior ocorrência e `None` corretamente.
- [ ] Extração de PDF persiste `regulation_days_on_screen` em casos novos.
- [ ] Casos existentes são preenchidos por data migration/backfill a partir de `extracted_text`.
- [ ] Fila médica ordena por maior `regulation_days_on_screen`.
- [ ] Casos médicos sem dado ficam depois dos casos com dado.
- [ ] Empate usa `created_at` mais antigo primeiro.
- [ ] Card médico exibe `Dias em tela: N` quando disponível.
- [ ] Card médico não exibe badge vazia quando o campo é `NULL`.
- [ ] Nenhuma alteração foi feita na fila do agendador.

## Gates de autoavaliação

Antes de finalizar, responda no relatório:

1. O parser é determinístico e independente de LLM?
2. O parser usa o maior valor quando o cabeçalho aparece em várias páginas?
3. `0` é tratado como valor válido e diferente de `NULL`?
4. A ordenação médica usa `NULLS LAST`?
5. O texto do card diferencia `Dias em tela` de `Aguardando há X min`?
6. Quantos arquivos foram tocados e por que cada um era necessário?
7. Houve alguma alteração fora do escopo, especialmente no scheduler?

## Comandos de validação

Rode no mínimo:

```bash
uv run pytest apps/intake/tests apps/doctor/tests -q
uv run ruff check apps/cases apps/intake apps/doctor
uv run ruff format --check apps/cases apps/intake apps/doctor
uv run mypy apps/cases apps/intake apps/doctor
```

Se possível, rode o quality gate completo do `AGENTS.md`:

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
```

Se algum comando não puder ser executado, registre motivo e saída relevante no relatório.

## Atualização de artefatos

Ao concluir:

- marcar este slice como concluído em `openspec/changes/prioritize-queues-by-regulation-days/tasks.md`;
- marcar apenas os itens de DoD já satisfeitos;
- não marcar itens do agendador como concluídos neste slice.

## Relatório final obrigatório

Crie relatório temporário em:

```text
/tmp/ats-web-slice-001-regulation-days-doctor-report.md
```

O relatório deve conter:

- resumo do que foi implementado;
- lista de arquivos alterados;
- snippets antes/depois dos pontos principais;
- testes adicionados/alterados;
- comandos executados e resultados;
- riscos/observações;
- confirmação de atualização de `tasks.md`;
- commit hash e push, quando realizados.

Na resposta final, informe exatamente:

```text
REPORT_PATH=/tmp/ats-web-slice-001-regulation-days-doctor-report.md
```

Depois pare e peça confirmação explícita antes de iniciar qualquer próximo slice.

## Prompt pronto para o implementador

```text
Read AGENTS.md and PROJECT_CONTEXT.md first. Then read openspec/changes/prioritize-queues-by-regulation-days/proposal.md, design.md, tasks.md, and slices/slice-001-extracao-persistencia-fila-medica.md.

Implement ONLY Slice 001. Use TDD: write failing tests first for parser, PDF extraction persistence, and doctor queue ordering/display. Then implement the minimal code to pass. Keep clean code, DRY, and YAGNI: no LLM extraction, no priority score, no scheduler changes, no FSM changes.

Add Case.regulation_days_on_screen as optional indexed PositiveIntegerField with migration and data backfill from extracted_text. Add deterministic parser extract_regulation_days_on_screen(text) returning the largest Dias em tela value or None. Persist it during PDF extraction. Order WAIT_DOCTOR by regulation_days_on_screen DESC NULLS LAST then created_at ASC, and show Dias em tela on doctor pending cards when available.

Run the validation commands from the slice. Update tasks.md. Generate /tmp/ats-web-slice-001-regulation-days-doctor-report.md with summary, files, before/after snippets, tests, commands/results, risks, tasks update, commit hash and push status. Reply with REPORT_PATH only plus a short stop/confirmation request.
```
