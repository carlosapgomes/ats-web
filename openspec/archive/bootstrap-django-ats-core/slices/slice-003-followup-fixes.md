# Follow-up: Correções pós Slice 3

> **Prioridade**: antes do Slice 4
> **Motivo**: revisão do planner identificou 3 pontos a corrigir

---

## Correção 1: Eliminar duplicação de `_advance_to`

O helper `_advance_to` está idêntico em dois arquivos:
- `apps/cases/tests/test_fsm.py`
- `apps/cases/tests/test_audit.py`

**Ação**: mover para `apps/cases/tests/conftest.py` como fixture, e remover das cópias locais.

```python
# apps/cases/tests/conftest.py — adicionar fixture
@pytest.fixture
def advance_to():
    """Retorna função helper que avança um Case até o estado alvo."""
    def _advance(case: Case, target: str) -> Case:
        # ... lógica existente (mesmo body)
    return _advance
```

Nos testes, trocar `_advance_to(case, ...)` por `advance_to(case, ...)`:

```python
# Antes (topo do arquivo):
def _advance_to(case, target): ...

# Depois (usar fixture do conftest):
case = advance_to(case_factory(user), CaseStatus.WAIT_DOCTOR)
```

Também mover `case_factory` para o conftest como fixture (já está lá o `user`).

---

## Correção 2: Evento de auditoria faltando em `extraction_complete(success=True)`

**Problema**: quando `extraction_complete(success=True)`, nenhum evento é registrado. O evento `LLM1_OK` só aparece na transição seguinte. Isso cria um gap na auditoria — o caso vai de `EXTRACTING` → `LLM_STRUCT` sem nenhum registro.

**Arquivo**: `apps/cases/models.py`

**Ação**: adicionar `_record_event` para o caso de sucesso também:

```python
@transition(
    field=status,
    source=CaseStatus.EXTRACTING,
    target=ReturnState(),
)
def extraction_complete(self, success: bool, user=None):
    if not success:
        self._record_event("CASE_EXTRACTION_FAILED", user=user)
    else:
        self._record_event("CASE_EXTRACTION_OK", user=user)
    return CaseStatus.FAILED if not success else CaseStatus.LLM_STRUCT
```

**Arquivo**: `apps/cases/tests/test_audit.py`

Atualizar `test_full_lifecycle_events` — o `expected` ganha `"CASE_EXTRACTION_OK"`:

```python
expected = [
    "CASE_CREATED",
    "CASE_START_PROCESSING",
    "CASE_START_EXTRACTION",
    "CASE_EXTRACTION_OK",    # ← NOVO
    "LLM1_OK",
    "LLM2_OK",
    ...
]
```

Adicionar teste unitário:

```python
def test_extraction_success_generates_event(self, user) -> None:
    """EXTRACTING → LLM_STRUCT deve gerar CASE_EXTRACTION_OK."""
    case = Case.objects.create(created_by=user)
    case.start_processing(user=user)
    case.save()
    case.start_extraction(user=user)
    case.save()
    case.extraction_complete(success=True, user=user)
    case.save()

    event = CaseEvent.objects.filter(case=case, event_type="CASE_EXTRACTION_OK").first()
    assert event is not None
    assert event.actor == user
```

---

## Correção 3: Push para branch remota

O DoD do relatório marca push como não feito.

```bash
git push origin main
```

Confirmar que o remote está atualizado.

---

## Gates

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest -v
```

Esperado: testes passando com o novo evento e sem duplicação de código.

## Relatório

Gere `/tmp/slice-003-followup-report.md`.
Informe `REPORT_PATH=/tmp/slice-003-followup-report.md`.
