# Slice 001: Detector documental e renderização no relatório médico

## Contexto zero para implementador

O relatório técnico exibido para o médico em `templates/doctor/decision.html` é gerado por `DoctorReportPresenter` em `apps/doctor/presenters.py`.

Hoje o presenter recebe:

```python
DoctorReportPresenter(
    structured_data=case.structured_data or {},
    summary_text=case.summary_text or "",
    suggested_action=case.suggested_action or {},
    recent_denial_context=...,  # opcional
)
```

A view médica (`apps/doctor/views.py`) já tem acesso a `case.extracted_text`, mas esse texto não é passado ao presenter. Para detectar ingestão cáustica/corrosiva de forma determinística, este slice deve passar o texto extraído para o presenter e renderizar uma linha de alerta no relatório.

## Objetivo do slice

Implementar, de ponta a ponta, a ênfase documental no relatório médico:

```text
texto extraído com ingestão cáustica/corrosiva
→ DoctorReportPresenter detecta evento e tempo quando possível
→ templates/doctor/decision.html exibe alerta no Relatório Técnico da Triagem
```

Este slice não altera prompts, LLM services, schemas, policy, FSM, banco, filas ou decisão automática.

## Arquivos esperados

Tocar idealmente apenas:

1. `apps/doctor/presenters.py` ou módulo pequeno novo `apps/doctor/caustic_ingestion.py` se a extração ficar grande demais;
2. `apps/doctor/views.py`;
3. `templates/doctor/decision.html`;
4. `apps/doctor/tests/test_presenter.py`;
5. `apps/doctor/tests/test_views.py` se necessário para validar renderização end-to-end.

Se tocar qualquer outro arquivo, justificar no relatório do slice.

## Requisitos funcionais

### R1. Detectar ingestão cáustica/corrosiva

Quando `case.extracted_text` contiver contexto positivo, o relatório deve exibir alerta.

Exemplos positivos:

```text
Paciente ingeriu soda cáustica há 3 semanas.
```

```text
História de ingestão de substância corrosiva há cerca de 10 dias.
```

```text
Relata ingestão de ácido em 12/05/2026.
```

A primeira linha do alerta deve ser equivalente a:

```text
⚠️ ingestão cáustica/corrosiva relatada: sim
```

### R2. Identificar tempo desde ingestão quando disponível

Quando houver expressão temporal próxima ao evento, o alerta deve incluir o texto literal identificado.

Exemplos aceitos:

```text
tempo desde a ingestão: há 3 semanas
```

```text
tempo desde a ingestão: há cerca de 10 dias
```

```text
tempo desde a ingestão: em 12/05/2026
```

Não calcular intervalo em dias/semanas. Não comparar com data atual.

### R3. Fallback quando tempo não estiver claro

Quando houver ingestão detectada, mas sem expressão temporal clara, exibir:

```text
tempo desde a ingestão: não informado no relatório
```

### R4. Não exibir alerta em caso negativo

Casos sem termos de ingestão cáustica/corrosiva não devem mostrar alerta.

### R5. Não disparar em negação explícita simples

Não exibir alerta quando a mesma sentença/janela indicar negação clara, por exemplo:

```text
Paciente nega ingestão de cáustico.
```

```text
Sem ingestão de corrosivos.
```

```text
Não ingeriu soda cáustica.
```

### R6. Renderização médica

O alerta deve aparecer no topo do `Relatório Técnico da Triagem`, próximo às linhas de contexto já existentes.

Pode ser uma linha com `⚠️` no `report-meta` ou um `alert alert-warning` discreto. Deve ser visível sem abrir o JSON completo nem o texto extraído.

### R7. Sem impacto em decisão/fluxo

Este slice não deve alterar:

- `case.suggested_action`;
- `support_recommendation`;
- `preop_gate`;
- `doctor_decision`;
- FSM/status;
- fila médica/scheduler/NIR;
- eventos de auditoria;
- dados persistidos.

## Estratégia técnica recomendada

### Presenter

Adicionar campo opcional ao dataclass:

```python
source_text: str = ""
```

Manter compatibilidade com testes existentes, usando default vazio.

Adicionar em `_build_context()` chave nova:

```python
"clinical_alert_lines": self._build_clinical_alert_lines(),
```

Implementar helper local:

```python
def _build_clinical_alert_lines(self) -> list[str]:
    ...
```

Se a lógica ficar longa, extrair para módulo `apps/doctor/caustic_ingestion.py` com função pura testável.

### View

Em `apps/doctor/views.py`, ao criar o presenter, passar:

```python
source_text=case.extracted_text or ""
```

### Template

Renderizar:

```django
{% for line in report.context.clinical_alert_lines %}
  <div class="alert alert-warning py-1 px-2 mb-1 small">{{ line }}</div>
{% endfor %}
```

ou forma equivalente.

## TDD obrigatório

Antes de implementar, adicionar testes falhando.

### Testes mínimos em `apps/doctor/tests/test_presenter.py`

1. `test_caustic_ingestion_alert_detects_soda_caustica_with_relative_time`
   - `source_text="Paciente ingeriu soda cáustica há 3 semanas."`
   - assert contém `ingestão cáustica/corrosiva` e `há 3 semanas`.

2. `test_caustic_ingestion_alert_detects_corrosive_substance_with_approximate_time`
   - `source_text="História de ingestão de substância corrosiva há cerca de 10 dias."`
   - assert contém `substância` ou `cáustica/corrosiva` e `há cerca de 10 dias`.

3. `test_caustic_ingestion_alert_detects_acid_ingestion_with_date`
   - `source_text="Relata ingestão de ácido em 12/05/2026."`
   - assert contém `em 12/05/2026`.

4. `test_caustic_ingestion_alert_without_time_uses_fallback`
   - `source_text="Paciente ingeriu produto corrosivo."`
   - assert contém `não informado no relatório`.

5. `test_caustic_ingestion_alert_absent_when_no_event`
   - texto sem ingestão;
   - assert `clinical_alert_lines == []`.

6. `test_caustic_ingestion_alert_ignores_explicit_negation`
   - `source_text="Paciente nega ingestão de cáustico."`
   - assert `clinical_alert_lines == []`.

### Teste recomendado em `apps/doctor/tests/test_views.py`

Adicionar ou ajustar teste de renderização da tela de decisão médica para garantir que o HTML contém o alerta quando `case.extracted_text` tem ingestão cáustica/corrosiva.

Se esse teste ficar excessivamente caro/frágil, documentar no relatório e manter cobertura de presenter + inspeção de template.

## Restrições estritas

- Não alterar prompt LLM1 neste slice.
- Não alterar schema Pydantic.
- Não alterar LLM2.
- Não alterar policy EDA, reconciliação, suporte ou preop gate.
- Não alterar FSM, modelos ou migrations.
- Não persistir nova estrutura em `Case`.
- Não fazer cálculo clínico do tempo.
- Não transformar tempo desde ingestão em motivo de negativa.
- Não criar dependência externa.

## Critérios de sucesso

- [ ] Testes novos falham antes da implementação e passam depois.
- [ ] Relatório médico exibe alerta para ingestão cáustica/corrosiva.
- [ ] Tempo desde ingestão aparece quando detectado.
- [ ] Fallback sem tempo é claro.
- [ ] Negação explícita simples não dispara alerta.
- [ ] Nenhuma decisão/fluxo/policy/FSM é alterado.
- [ ] Quality gate completo passa.

## Gates de autoavaliação

Responder no relatório do slice:

1. Onde o detector lê o texto fonte?
2. Quais termos positivos são cobertos?
3. Quais padrões de tempo são cobertos?
4. Como negações simples são evitadas?
5. O código alterou `suggested_action`, policy, FSM ou persistência? Se sim, está errado.
6. O alerta aparece sem abrir JSON/texto extraído?
7. Algum arquivo fora dos esperados foi alterado? Se sim, por quê?

## Prompt pronto para implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md, openspec/changes/highlight-caustic-ingestion-in-doctor-report/proposal.md, design.md, tasks.md and slices/slice-001-detector-e-relatorio-medico.md.
Implement ONLY Slice 001.
Use TDD strictly: first add failing tests for caustic/corrosive ingestion detection and time extraction, then implement the minimal presenter/view/template change.
Goal: the doctor technical report must show a visible documentary alert when case.extracted_text mentions ingestion of caustic/corrosive substance, and must show the literal time since ingestion when nearby text contains it; otherwise show “tempo desde a ingestão: não informado no relatório”. Do not compute clinical intervals.
Do not change prompts, LLM services, schemas, database, FSM, policy, support recommendation, queues, notifications or decision logic.
Run: uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
Update openspec/changes/highlight-caustic-ingestion-in-doctor-report/tasks.md marking Slice 001 complete only if all gates pass.
Create a detailed temporary markdown report with before/after snippets and answers to the self-evaluation gates.
Commit and push.
Return REPORT_PATH=<path> and stop. Do not start Slice 002 without explicit user confirmation.
```
