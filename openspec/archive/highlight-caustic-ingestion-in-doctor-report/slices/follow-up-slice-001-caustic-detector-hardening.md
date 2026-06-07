# Follow-up Slice 001: Hardening do detector de ingestão cáustica/corrosiva

## Contexto zero para implementador

O Slice 001 de `highlight-caustic-ingestion-in-doctor-report` implementou a ênfase documental de ingestão cáustica/corrosiva no relatório médico.

Arquivos principais envolvidos:

- `apps/doctor/presenters.py`
  - adicionou `source_text` ao `DoctorReportPresenter`;
  - adicionou helpers de detecção de ingestão cáustica/corrosiva;
  - adicionou `report.context.clinical_alert_lines`.
- `apps/doctor/views.py`
  - passa `source_text=case.extracted_text or ""` ao presenter.
- `templates/doctor/decision.html`
  - renderiza `clinical_alert_lines` no topo do relatório técnico.
- `apps/doctor/tests/test_presenter.py`
  - cobre casos positivos, tempo, fallback e negações simples.

O avaliador considerou o Slice 001 funcional, mas apontou hardenings não-bloqueantes. Este follow-up corrige dois pontos de robustez sem mudar escopo clínico nem fluxo.

## Problema a corrigir

A implementação atual tem limitações:

1. **Matching com acentos literais**
   - O design/proposal pedem suporte a variantes com e sem acento (`ingestao`, `caustico`, `soda caustica`, `acido`).
   - PDFs extraídos frequentemente perdem acentos.
   - O detector atual usa regex/keywords com acentos literais em alguns pontos.

2. **`soda cáustica` isolada implica ingestão**
   - A implementação atual aceita `soda cáustica` sozinha como positivo.
   - Isso pode gerar falso positivo em textos como:

```text
Contato com soda cáustica, sem ingestão.
```

```text
Queimadura por soda cáustica, sem relato de ingestão.
```

O alerta deve ser documental para ingestão, não para contato/queimadura/exposição sem ingestão.

## Objetivo do follow-up

Endurecer o detector para:

- normalizar texto para matching sem acento;
- reconhecer variantes sem acento em termos positivos e negações;
- exigir contexto de ingestão também para `soda cáustica` / `soda caustica`;
- manter o comportamento atual para casos positivos e negativos já cobertos;
- não alterar decisão, policy, FSM, filas, schema, prompts ou persistência.

## Arquivos esperados

Tocar idealmente apenas:

1. `apps/doctor/presenters.py`
2. `apps/doctor/tests/test_presenter.py`

Se tocar qualquer outro arquivo, justificar no relatório.

## Requisitos funcionais

### R1. Detectar variantes sem acento

Estes textos devem disparar alerta:

```text
Paciente ingeriu soda caustica ha 3 semanas.
```

```text
Historia de ingestao de substancia corrosiva ha cerca de 10 dias.
```

```text
Relata ingestao de acido em 12/05/2026.
```

O alerta pode continuar exibindo o tempo como texto literal encontrado no source original, mesmo sem acento:

```text
tempo desde a ingestão: ha 3 semanas
```

### R2. Negação sem acento também deve ser respeitada

Estes textos não devem disparar alerta:

```text
Paciente nega ingestao de caustico.
```

```text
Sem ingestao de corrosivos.
```

```text
Nao ingeriu soda caustica.
```

### R3. `soda cáustica` isolada não deve disparar alerta

Estes textos não devem disparar alerta:

```text
Contato com soda cáustica, sem ingestão.
```

```text
Queimadura por soda caustica em membro superior.
```

A presença de `soda cáustica` só deve disparar quando houver coocorrência com verbo/contexto de ingestão em janela próxima.

### R4. Manter positivos atuais

Os testes atuais do Slice 001 devem continuar passando, especialmente:

- `Paciente ingeriu soda cáustica há 3 semanas.`
- `História de ingestão de substância corrosiva há cerca de 10 dias.`
- `Relata ingestão de ácido em 12/05/2026.`
- `Paciente ingeriu produto corrosivo.`

### R5. Não mudar escopo clínico

Este hardening não deve:

- sugerir negativa automática;
- calcular intervalo clínico;
- alterar `case.suggested_action`;
- alterar policy/preop/FSM;
- criar campo persistido;
- alterar prompt LLM1.

## Estratégia técnica sugerida

### Normalização local

Adicionar helper local em `apps/doctor/presenters.py`, por exemplo:

```python
def _normalize_caustic_text(value: str) -> str:
    ...
```

Regras:

- usar `unicodedata.normalize("NFD", value)`;
- remover caracteres de categoria `Mn`;
- converter para lowercase;
- colapsar whitespace.

Será necessário importar `unicodedata`.

### Matching em texto normalizado

- Rodar detecção positiva e negação sobre texto normalizado.
- Converter keywords para forma sem acento:
  - `caustic`
  - `corrosiv`
  - `soda caustica`
  - `acido`
- Converter verbos/contextos para forma sem acento:
  - `ingeriu`
  - `ingestao`
  - `ingerir`
  - `ingerido`
  - `ingerida`

### Tempo

Pode manter extração do tempo sobre o texto original, desde que passe nos casos sem acento (`ha 3 semanas`). Se o regex atual só cobre `há`, ajustar para `h[aá]` ou usar busca em texto normalizado com recuperação simples do match.

Não é necessário fazer extração perfeita de tempo neste hardening; apenas garantir os casos novos de teste.

### Remover fallback perigoso

Remover ou endurecer o trecho equivalente a:

```python
if "soda cáustica" in text_lower:
    return True
```

`Soda cáustica` deve seguir a mesma regra de proximidade com ingestão.

## TDD obrigatório

Adicionar testes falhando antes da implementação.

### Testes mínimos em `apps/doctor/tests/test_presenter.py`

1. `test_alert_detects_unaccented_soda_caustica_with_time`
   - `source_text="Paciente ingeriu soda caustica ha 3 semanas."`
   - assert alerta existe e contém `ha 3 semanas`.

2. `test_alert_detects_unaccented_ingestao_corrosiva_with_time`
   - `source_text="Historia de ingestao de substancia corrosiva ha cerca de 10 dias."`
   - assert alerta existe e contém `ha cerca de 10 dias`.

3. `test_alert_detects_unaccented_acid_ingestion_with_date`
   - `source_text="Relata ingestao de acido em 12/05/2026."`
   - assert alerta existe e contém `em 12/05/2026`.

4. `test_alert_ignores_unaccented_negation`
   - `source_text="Paciente nega ingestao de caustico."`
   - assert `clinical_alert_lines == []`.

5. `test_alert_ignores_unaccented_nao_ingeriu_soda_caustica`
   - `source_text="Nao ingeriu soda caustica."`
   - assert `clinical_alert_lines == []`.

6. `test_alert_ignores_soda_caustica_contact_without_ingestion`
   - `source_text="Contato com soda cáustica, sem ingestão."`
   - assert `clinical_alert_lines == []`.

7. `test_alert_ignores_soda_caustica_burn_without_ingestion`
   - `source_text="Queimadura por soda caustica em membro superior."`
   - assert `clinical_alert_lines == []`.

## Validação focada recomendada

Rodar primeiro:

```bash
uv run pytest apps/doctor/tests/test_presenter.py -k "Caustic or caustic or alert" -q
```

Depois rodar quality gate completo do projeto:

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
```

## Critérios de sucesso

- [ ] Testes novos falham antes e passam depois.
- [ ] Detector reconhece variantes sem acento.
- [ ] Negações sem acento não disparam alerta.
- [ ] `soda cáustica` isolada/contato/queimadura sem ingestão não dispara alerta.
- [ ] Testes antigos do Slice 001 continuam passando.
- [ ] Nenhuma decisão, policy, FSM, fila, prompt, schema ou persistência foi alterada.
- [ ] Quality gate completo passa.

## Gates de autoavaliação para relatório

Responder no relatório do follow-up:

1. Qual helper normaliza texto e como remove acentos?
2. A detecção positiva e as negações usam texto normalizado?
3. `soda cáustica` ainda dispara alerta sem contexto de ingestão? Se sim, está errado.
4. Quais testes provam suporte a texto sem acento?
5. Quais testes provam que contato/queimadura por soda cáustica não dispara alerta?
6. O código alterou decisão, policy, FSM, schema, prompt ou persistência? Se sim, está errado.
7. Algum arquivo fora dos esperados foi alterado? Se sim, por quê?

## Prompt pronto para implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md, openspec/changes/highlight-caustic-ingestion-in-doctor-report/proposal.md, design.md, tasks.md, slices/slice-001-detector-e-relatorio-medico.md and this follow-up slice.
Implement ONLY the hardening described in follow-up-slice-001-caustic-detector-hardening.md.
Use TDD strictly: first add failing tests in apps/doctor/tests/test_presenter.py for unaccented positives, unaccented negations, and soda caustica contact/burn without ingestion. Then minimally update apps/doctor/presenters.py.
Goal: caustic/corrosive ingestion detection must work with and without accents, negations must work with and without accents, and soda cáustica/soda caustica alone must not imply ingestion. It must still show time expressions like “ha 3 semanas”, “ha cerca de 10 dias” and “em 12/05/2026” when available.
Do not change prompts, LLM services, schemas, database, FSM, policy, support recommendation, queues, notifications or decision logic. Do not calculate clinical intervals. Do not start Slice 002.
Run focused tests first, then: uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
Update tasks/report artifacts only if your workflow requires it; otherwise create a detailed temporary markdown report with before/after snippets and answers to the self-evaluation gates.
Commit and push.
Return REPORT_PATH=<path> and stop.
```
