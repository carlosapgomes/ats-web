# Design: Priorizar filas por “Dias em tela” do relatório de regulação

## Estado atual

### Extração de PDF

- `apps/intake/tasks.py::_do_extraction` chama:
  - `extract_pdf_text(case.pdf_file.path)`;
  - `strip_watermark_and_extract_record(extracted)`;
  - persiste `case.extracted_text`, `case.agency_record_number` e `case.agency_record_extracted_at`.
- `apps/intake/pdf_utils.py` concentra helpers determinísticos de texto de PDF.
- `apps/intake/regulation_gate.py` já usa `Dias em tela` como sinal operacional do relatório, mas não extrai o número.

### Modelo

`apps/cases/models.py::Case` não possui campo para `Dias em tela`. A ordenação default do modelo é `-created_at`.

### Fila médica

`apps/doctor/views.py::_doctor_queue_context` consulta pendentes com:

```python
Case.objects.filter(status=CaseStatus.WAIT_DOCTOR).select_related("locked_by").order_by("created_at")
```

O card recebe `wait_minutes`, calculado por `now - case.created_at`.

### Fila do agendador

`apps/scheduler/views.py::_scheduler_queue_context` consulta `WAIT_APPT` com:

```python
Case.objects.filter(status=CaseStatus.WAIT_APPT).select_related("doctor", "locked_by").order_by("created_at")
```

Cards de vinda imediata (`immediate_notice_cases`) já são renderizados antes de `pending_cases` no template `templates/scheduler/_queue_content.html`.

## Decisões de design

### D1: Campo persistente no `Case`

Adicionar campo:

```python
regulation_days_on_screen = models.PositiveIntegerField(null=True, blank=True, db_index=True)
```

Justificativa:

- é dado operacional estável no momento do upload;
- permite ordenar no banco sem parsear texto em runtime;
- `NULL` representa ausência real do dado;
- `db_index=True` ajuda consultas por fila/ordenação conforme o volume crescer.

Não usar `default=0`, pois `0` é valor válido diferente de “não encontrado”.

### D2: Parser determinístico, sem LLM

Adicionar helper puro em `apps/intake/pdf_utils.py`:

```python
def extract_regulation_days_on_screen(text: str) -> int | None:
    ...
```

Regra:

- aceitar variações simples de espaços e caixa;
- aceitar acentos já presentes no texto extraído;
- extrair números inteiros não negativos depois de `Dias em tela:`;
- se houver múltiplas ocorrências, retornar o maior número;
- se não houver ocorrência, retornar `None`.

Regex sugerida:

```python
r"\bDias\s+em\s+tela\s*:\s*(\d+)\b"
```

com `re.IGNORECASE`.

Não é necessário normalizar acentos porque a expressão esperada é `Dias em tela`, mas o implementador pode tornar o parser robusto a variações sem ampliar escopo.

### D3: Persistir durante extração do PDF

Em `apps/intake/tasks.py::_do_extraction`, depois de gerar `cleaned_text`, preencher:

```python
case.regulation_days_on_screen = extract_regulation_days_on_screen(cleaned_text)
```

Usar `cleaned_text`, pois é o texto efetivamente persistido e usado pelo gate.

### D4: Backfill por migration de dados

A migration que adiciona o campo deve incluir `RunPython` ou migration subsequente para preencher casos existentes a partir de `extracted_text`.

Motivos:

- há casos já processados que podem estar em filas ativas;
- não exige reprocessar PDFs;
- preserva rastreabilidade e evita comando manual obrigatório para ativar a feature.

A migration pode duplicar uma regex mínima em vez de importar `apps.intake.pdf_utils`, pois migrations devem ser estáveis no tempo.

Regra do backfill:

- iterar apenas casos com `extracted_text` não vazio e `regulation_days_on_screen IS NULL`;
- aplicar mesma regra “maior ocorrência”;
- salvar apenas o campo novo, preferencialmente em batches simples.

### D5: Ordenação com `NULLS LAST`

Usar ordenação explícita por expressão, por exemplo:

```python
from django.db.models import F

.order_by(F("regulation_days_on_screen").desc(nulls_last=True), "created_at")
```

Critérios:

1. maior `regulation_days_on_screen` primeiro;
2. `NULL` por último;
3. empate por `created_at` crescente.

### D6: Exibição nos cards sem confundir com tempo no ATS

Manter `wait_minutes` atual, pois ele representa tempo interno do ATS e já é usado nos cards. Adicionar um campo separado no card:

```python
"regulation_days_on_screen": case.regulation_days_on_screen,
```

Nos templates, exibir quando disponível:

```django
{% if c.regulation_days_on_screen is not None %}
<span class="badge bg-warning text-dark">Dias em tela: {{ c.regulation_days_on_screen }}</span>
{% endif %}
```

Não substituir automaticamente `Aguardando há X min`, para não misturar conceitos. Se a UI ficar carregada, preferir badge curta.

### D7: Vinda imediata do agendador permanece no topo absoluto

Não alterar a query nem ordenação de `immediate_notice_qs` neste change. A estrutura atual do template já renderiza a seção de vinda imediata antes dos cards `WAIT_APPT`.

Se o implementador tocar essa área no slice do agendador, deve provar por teste que a expressão “Vinda imediata autorizada” aparece antes do card `WAIT_APPT` quando ambos existem.

## Divisão em slices verticais

Para manter slices enxutos e com valor end-to-end, dividir em 2 slices:

### Slice 001 — Extração persistida + fila médica priorizada

Entrega vertical para o médico:

```text
PDF com Dias em tela -> Case persiste número -> médico vê card com Dias em tela -> fila médica ordena por maior número
```

Arquivos previstos:

- `apps/cases/models.py`
- nova migration em `apps/cases/migrations/`
- `apps/intake/pdf_utils.py`
- `apps/intake/tasks.py`
- `apps/doctor/views.py`
- `templates/doctor/_queue_content.html`
- testes em `apps/intake/tests/` e `apps/doctor/tests/`

Justificativa para mais de 5 arquivos: é uma fatia vertical real que atravessa extração, persistência e primeira UI consumidora. Evita criar slice horizontal só de modelo/parser sem valor operacional.

### Slice 002 — Fila do agendador priorizada

Entrega vertical para o agendador:

```text
Case com Dias em tela persistido -> WAIT_APPT ordena por maior número -> agendador vê Dias em tela no card -> vinda imediata continua no topo
```

Arquivos previstos:

- `apps/scheduler/views.py`
- `templates/scheduler/_queue_content.html`
- testes em `apps/scheduler/tests/`
- `openspec/changes/prioritize-queues-by-regulation-days/tasks.md`

## Riscos e mitigação

| Risco | Mitigação |
|---|---|
| Regex falhar por variação leve de espaços/caixa | Usar regex com `\s*`, `\s+` e `re.IGNORECASE` |
| Cabeçalho repetido em várias páginas com divergência | Usar maior número conforme decisão do usuário |
| Casos sem dado subirem indevidamente | Campo `NULL` + `nulls_last=True` |
| Confundir “Dias em tela” com “Aguardando há X min” | Exibir como badge separada e manter textos distintos |
| Data migration lenta | Iterar apenas casos com `extracted_text` e campo `NULL`; volume atual esperado é manejável |
| Slice 001 tocar muitos arquivos | Justificado por verticalidade; manter alterações mínimas por arquivo |

## Rollback

Rollback funcional:

1. Reverter ordenações/templates das filas.
2. Reverter persistência em `apps/intake/tasks.py`.
3. Reverter campo/migration se necessário.

Como o campo é derivado de `extracted_text` e não altera FSM, perda do campo não compromete histórico clínico ou auditoria.
