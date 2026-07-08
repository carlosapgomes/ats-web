# Slice 001: Extração estruturada LLM1 + exibição de comorbidades no relatório médico

## Status

- [x] Done

## Contexto zero para implementador

O ATS Web é um monolito Django SSR para triagem de EDA. PDFs de relatórios clínicos são processados por pipeline LLM:

```text
NIR faz upload do PDF
→ texto é extraído
→ LLM1 gera structured_data validado por Pydantic
→ LLM2/policy gera sugestão
→ médico abre a tela de decisão e vê relatório automático
```

O médico solicitou uma **lista de comorbidades**, não apenas flags internos usados para ASA/policy. Hoje existem flags como `diabetes_mellitus`, `explicit_obesity`, `cardiopathy_explicit` em:

```text
preop_screening.rulebook_signals.clinical_flags
```

Esses flags não satisfazem a solicitação porque não formam lista textual separada por vírgulas.

Leia antes de implementar:

- `AGENTS.md`
- `PROJECT_CONTEXT.md`
- `openspec/changes/structured-comorbidities-doctor-report/proposal.md`
- `openspec/changes/structured-comorbidities-doctor-report/design.md`
- `openspec/changes/structured-comorbidities-doctor-report/tasks.md`
- este slice

## Objetivo do slice

Entregar uma fatia vertical completa:

```text
LLM1 extrai comorbidades descritas
→ schema Pydantic aceita/persiste em Case.structured_data
→ presenter médico monta linha exclusiva
→ tela de decisão mostra lista separada por vírgula
```

Exemplos de exibição:

```text
Comorbidades descritas: hipertensão arterial sistêmica, diabetes mellitus tipo 2, doença renal crônica
```

Quando novo caso não tiver comorbidades descritas:

```text
Comorbidades descritas: sem comorbidades descritas no relatório
```

Quando caso antigo não tiver o campo no JSON:

```text
Comorbidades descritas: extração de comorbidades não disponível neste caso
```

## Arquivos esperados

Mantenha o mínimo necessário. Esperado tocar apenas:

1. `apps/pipeline/schemas/llm1.py`
2. `apps/pipeline/llm1_service.py`
3. `apps/pipeline/tests/test_llm1_service.py`
4. `apps/doctor/presenters.py`
5. `templates/doctor/decision.html`
6. `apps/doctor/tests/test_presenter.py`
7. `openspec/changes/structured-comorbidities-doctor-report/tasks.md` ao concluir

Se tocar arquivos adicionais, explique a necessidade no relatório temporário. Não criar migration.

## Requisitos funcionais

### R1. Schema LLM1 com lista estruturada

Em `apps/pipeline/schemas/llm1.py`, adicionar modelo pequeno:

```python
class Llm1Comorbidity(StrictModel):
    """Explicit comorbidity/clinical background described in the source report."""

    name: str = Field(min_length=1, max_length=120)
    source_text_hint: str | None = None
```

Adicionar em `Llm1PreopScreening`:

```python
comorbidities_described: list[Llm1Comorbidity] = Field(default_factory=list, max_length=20)
```

Observações:

- Manter `schema_version` como `"1.1"`.
- O campo deve ser backward-compatible.
- Não mexer em `Case` ou migrations.

### R2. Prompt LLM1 atualizado

Em `apps/pipeline/llm1_service.py`, atualizar:

- `LLM1_REQUIRED_SCHEMA_INSTRUCTIONS`
- `LLM1_DEFAULT_USER_PROMPT`
- `_render_user_prompt(...)`

O prompt deve deixar claro:

1. `preop_screening` agora inclui `comorbidities_described`.
2. Cada item é `{name, source_text_hint}`.
3. Extrair somente comorbidades/condições crônicas/antecedentes descritos explicitamente no relatório.
4. Se houver sigla clara, normalizar quando seguro:
   - `HAS` → `hipertensão arterial sistêmica`
   - `DM2` → `diabetes mellitus tipo 2`
   - `DRC` → `doença renal crônica`
5. Retornar lista vazia se o relatório disser `sem comorbidades`, `nega comorbidades` ou equivalente.
6. Não inferir comorbidade apenas por medicação, exame, idade, fator de risco ou sugestão clínica sem diagnóstico/antecedente explícito.
7. Não incluir sintomas, indicação da EDA, exames laboratoriais ou diagnóstico agudo isolado como comorbidade crônica.

Importante: atualizar `_render_user_prompt(...)` porque essa instrução é anexada mesmo quando o banco tem prompt ativo customizado.

### R3. Presenter monta linha exclusiva

Em `apps/doctor/presenters.py`, adicionar helper pequeno e coeso em `DoctorReportPresenter`, por exemplo:

```python
def _build_comorbidities_line(self) -> str:
    ...
```

Comportamento obrigatório:

- Se `preop_screening` ou a chave `comorbidities_described` estiver ausente:
  - `Comorbidades descritas: extração de comorbidades não disponível neste caso`
- Se a chave existir e a lista estiver vazia:
  - `Comorbidades descritas: sem comorbidades descritas no relatório`
- Se houver itens:
  - usar `name` de cada objeto;
  - ignorar itens inválidos/vazios;
  - deduplicar nomes preservando ordem;
  - renderizar separados por vírgula;
  - se todos os itens forem inválidos/vazios, usar fallback de lista vazia.

Adicionar ao contexto do relatório:

```python
"comorbidities_line": self._build_comorbidities_line(),
```

### R4. Template médico exibe item exclusivo

Em `templates/doctor/decision.html`, dentro de `report-meta`, renderizar a linha de comorbidades de modo visível, preferencialmente após `origin` e antes de transfusão/exames:

```django
<div>{{ report.context.comorbidities_line }}</div>
```

Não redesenhar o card inteiro. Não transformar o relatório em SPA/JS.

### R5. Sem alteração de comportamento decisório

Proibido neste slice:

- alterar LLM2;
- alterar `apps/pipeline/policy/*`;
- alterar ASA/suporte;
- alterar FSM/transições/status;
- alterar filas;
- criar migration;
- reprocessar casos antigos;
- sobrescrever prompts ativos no banco.

## TDD obrigatório

Use RED → GREEN → REFACTOR.

### RED 1 — schema/prompt em `apps/pipeline/tests/test_llm1_service.py`

Adicionar testes falhando antes da implementação.

Sugestões mínimas:

```python
def test_llm1_accepts_structured_comorbidities_described() -> None:
    payload = _valid_llm1_payload()
    payload["preop_screening"]["comorbidities_described"] = [
        {"name": "hipertensão arterial sistêmica", "source_text_hint": "HAS"},
        {"name": "diabetes mellitus tipo 2", "source_text_hint": "DM2"},
    ]
    service = _make_service(json.dumps(payload))

    result = service.run(...)

    preop = result.structured_data["preop_screening"]
    assert preop["comorbidities_described"][0]["name"] == "hipertensão arterial sistêmica"
```

```python
def test_llm1_defaults_missing_comorbidities_to_empty_list() -> None:
    payload = _valid_llm1_payload()
    payload["preop_screening"].pop("comorbidities_described", None)
    service = _make_service(json.dumps(payload))

    result = service.run(...)

    assert result.structured_data["preop_screening"]["comorbidities_described"] == []
```

```python
def test_render_user_prompt_instructs_structured_comorbidity_extraction() -> None:
    prompt = _render_user_prompt(...)
    lower = prompt.lower()
    assert "comorbidities_described" in prompt
    assert "comorbidades" in lower
    assert "source_text_hint" in prompt
    assert "não infer" in lower or "nao infer" in lower
```

Também ajustar/criar assert para `LLM1_DEFAULT_USER_PROMPT` conter `comorbidities_described` ou `comorbidades`.

### RED 2 — presenter em `apps/doctor/tests/test_presenter.py`

Adicionar testes falhando antes da implementação.

Casos mínimos:

1. Lista com múltiplas comorbidades:

```python
def test_comorbidities_line_lists_names_separated_by_comma(self):
    presenter = DoctorReportPresenter(
        structured_data={
            "preop_screening": {
                "comorbidities_described": [
                    {"name": "hipertensão arterial sistêmica", "source_text_hint": "HAS"},
                    {"name": "diabetes mellitus tipo 2", "source_text_hint": "DM2"},
                ]
            }
        },
        summary_text="",
        suggested_action={},
    )
    report = presenter.build_report()
    assert report["context"]["comorbidities_line"] == (
        "Comorbidades descritas: hipertensão arterial sistêmica, diabetes mellitus tipo 2"
    )
```

2. Lista vazia:

```python
def test_comorbidities_line_empty_list_uses_no_comorbidities_text(self):
    presenter = DoctorReportPresenter(
        structured_data={"preop_screening": {"comorbidities_described": []}},
        summary_text="",
        suggested_action={},
    )
    report = presenter.build_report()
    assert report["context"]["comorbidities_line"] == (
        "Comorbidades descritas: sem comorbidades descritas no relatório"
    )
```

3. Campo ausente:

```python
def test_comorbidities_line_missing_field_uses_unavailable_text_for_old_cases(self):
    presenter = DoctorReportPresenter(
        structured_data={"preop_screening": {}},
        summary_text="",
        suggested_action={},
    )
    report = presenter.build_report()
    assert report["context"]["comorbidities_line"] == (
        "Comorbidades descritas: extração de comorbidades não disponível neste caso"
    )
```

4. Deduplicação/itens inválidos:

```python
def test_comorbidities_line_deduplicates_and_ignores_blank_items(self):
    ...
```

### GREEN

Implementar o mínimo para os testes passarem.

### REFACTOR

- Manter helper pequeno, legível e sem regex complexa.
- Evitar duplicação de strings se isso melhorar clareza, mas não criar abstração excessiva.
- Não criar módulo novo salvo se `presenters.py` ficar claramente pior; se criar, justificar.

## Critérios de aceitação do slice

- [ ] Testes novos falham antes da implementação e passam depois.
- [ ] `preop_screening.comorbidities_described` existe no schema e é backward-compatible.
- [ ] Prompt default e prompt renderizado final incluem instruções de comorbidades.
- [ ] Tela médica mostra `Comorbidades descritas`.
- [ ] Lista com múltiplas comorbidades aparece separada por vírgula.
- [ ] Lista vazia mostra `sem comorbidades descritas no relatório`.
- [ ] Campo ausente mostra `extração de comorbidades não disponível neste caso`.
- [ ] Não houve alteração de decision logic, policy, LLM2, FSM ou banco.
- [ ] Quality gate completo passa.
- [ ] `tasks.md` do change é atualizado ao concluir.
- [ ] Relatório markdown temporário é criado para revisão por terceiro LLM.
- [ ] Commit e push são realizados.

## Gates de autoavaliação obrigatórios

Responder no relatório temporário:

1. Quais arquivos foram alterados? Algum fora dos esperados? Por quê?
2. Onde o campo `comorbidities_described` foi definido e por que não exige migration?
3. O prompt renderizado final inclui instrução mesmo com prompt ativo customizado no banco?
4. Como o presenter diferencia campo ausente, lista vazia e lista preenchida?
5. A implementação alterou LLM2, policy, ASA/suporte, FSM, filas ou decisão automática? Deve ser “não”.
6. Testes foram criados antes do código de produção? Quais falharam no RED?
7. Quais comandos do quality gate foram executados e qual resultado?
8. Qual é o `REPORT_PATH` do relatório para auditoria por terceiro LLM?

## Relatório obrigatório

Criar um arquivo markdown temporário, por exemplo:

```text
tmp/structured-comorbidities-slice-001-report.md
```

O relatório deve conter:

- resumo do que foi implementado;
- snippets antes/depois dos trechos principais;
- evidência do RED/GREEN/REFACTOR;
- saída resumida dos comandos de validação;
- respostas aos gates de autoavaliação;
- riscos/limitações remanescentes.

A resposta final do implementador deve conter:

```text
REPORT_PATH=tmp/structured-comorbidities-slice-001-report.md
```

E deve parar, pedindo confirmação explícita para qualquer próximo passo.

## Prompt pronto para implementador LLM

```text
Read AGENTS.md and PROJECT_CONTEXT.md first.
Then read openspec/changes/structured-comorbidities-doctor-report/proposal.md, design.md, tasks.md and slices/slice-001-structured-comorbidities.md.
Implement ONLY Slice 001.
Use a vertical slice: LLM1 schema/prompt + persisted structured_data + doctor presenter + doctor template display.
Keep the slice lean. Touch only the expected files unless absolutely necessary, and justify any extra file.
Follow TDD strictly: write failing tests first (RED), implement minimal code (GREEN), then refactor for clean code, DRY and YAGNI.
Do not alter LLM2, policy, ASA/support synthesis, FSM, queues, models/migrations, notifications or decision logic. Do not overwrite active prompts in the database.
The new LLM1 field should be preop_screening.comorbidities_described, backward-compatible, with list items containing name and source_text_hint.
The doctor report must show an exclusive line: "Comorbidades descritas: ...". Use comma-separated names, "sem comorbidades descritas no relatório" for an empty list, and "extração de comorbidades não disponível neste caso" when the field is missing from older structured_data.
Run: uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
Update openspec/changes/structured-comorbidities-doctor-report/tasks.md only if all acceptance criteria pass.
Create a detailed temporary markdown report with before/after snippets, validation output and answers to the self-evaluation gates.
Commit and push.
Return REPORT_PATH=<temp-markdown-path> and stop.
```
