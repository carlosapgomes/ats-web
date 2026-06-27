# Relatório: Follow-up Slice 001 — Microcopy e link de PDF no detalhe scheduler

## Resumo da mudança

Correção de duas observações pós-Slice 001:

1. **Microcopy neutra**: substituição do texto `"Este caso já está encerrado"` por texto neutro no bloco `Comunicar NIR` do template scheduler.
2. **Link de PDF restaurado**: adição de `pdf_url` ao contexto de `scheduler_processed_detail` apontando para `scheduler:processed_pdf`, com renderização condicional no template.

## Arquivos tocados

1. `apps/scheduler/views.py` — adicionado parâmetro `pdf_url` ao helper `_build_scheduler_detail_context`, passado por `scheduler_processed_detail`; contexto inclui `pdf_url`.
2. `templates/scheduler/context_detail.html` — microcopy corrigida + bloco condicional de PDF adicionado.
3. `apps/scheduler/tests/test_views.py` — 2 novos testes (PDF link + copy neutra).
4. `openspec/changes/fix-scheduler-processed-detail-and-history-tab/tasks.md` — marcado follow-up e DoD items como concluídos.

## TDD: RED → GREEN → REFACTOR

### RED

Testes escritos primeiro, ambos falhando:

```python
def test_scheduler_processed_detail_shows_processed_pdf_link(self, client) -> None:
    """Processados Hoje detail exibe link para PDF original."""
    scheduler_user = self._login_as(client, "scheduler")
    case = self._create_case(...)
    response = client.get(f"/scheduler/processed/{case.case_id}/")
    assert response.status_code == 200
    content = response.content.decode()
    assert f"processed/{case.case_id}/pdf/" in content
    assert "PDF original" in content or "Abrir PDF" in content
```
→ FAIL: `assert 'processed/.../pdf/' in '<!DOCTYPE html>...'`

```python
def test_scheduler_processed_detail_message_nir_copy_is_status_neutral(self, client) -> None:
    """Microcopy de Comunicar NIR é neutra, sem afirmar que caso está encerrado."""
    ...
    assert "mensagem operacional ao NIR sobre este caso" in content
    assert "Este caso já está encerrado" not in content
```
→ FAIL: `assert "mensagem operacional ao NIR sobre este caso" in content`

### GREEN

Implementações mínimas:

1. Views: adicionado `pdf_url: str | None = None` ao `_build_scheduler_detail_context` e passado `reverse("scheduler:processed_pdf", args=[case.case_id])` em `scheduler_processed_detail`. Context inclui `"pdf_url": pdf_url`.
2. Template: substituído texto de microcopy + adicionado bloco `{% if pdf_url %}...{% endif %}`.
3. Ambos os testes passaram.

### REFACTOR

Nenhum refactor necessário — mudança cirúrgica e local sem duplicação. Template DRY dentro do contexto existente.

## Snippets antes/depois

### Microcopy `Comunicar NIR`

**Antes:**
```html
<p class="text-muted small mb-3">
    Este caso já está encerrado. Use este formulário para enviar uma mensagem
    operacional ao NIR. O sistema adicionará automaticamente a menção
    <strong>@nir</strong> para notificar a equipe NIR.
  </p>
```

**Depois:**
```html
<p class="text-muted small mb-3">
    Use este formulário para enviar uma mensagem operacional ao NIR sobre este caso.
    O sistema adicionará automaticamente a menção <strong>@nir</strong> para
    notificar a equipe NIR.
  </p>
```

### Link de PDF (novo bloco no template)

**Adicionado entre "Doctor Decision" e "Scheduling Data":**
```django
{% if pdf_url %}
<div class="card p-4 mb-4">
  <h5 class="mb-3">📄 PDF original</h5>
  <a href="{{ pdf_url }}" class="btn btn-sm btn-hospital-outline" target="_blank" rel="noopener">
    Abrir PDF em nova aba
  </a>
</div>
{% endif %}
```

### Context helper (views.py)

**Antes:**
```python
def _build_scheduler_detail_context(
    *,
    request: HttpRequest,
    case: Case,
    back_url: str,
    back_label: str,
) -> dict[str, Any]:
```

**Depois:**
```python
def _build_scheduler_detail_context(
    *,
    request: HttpRequest,
    case: Case,
    back_url: str,
    back_label: str,
    pdf_url: str | None = None,
) -> dict[str, Any]:
```

**E no contexto retornado:**
```python
"pdf_url": pdf_url,
```

**Em `scheduler_processed_detail`:**
```python
context = _build_scheduler_detail_context(
    ...
    pdf_url=reverse("scheduler:processed_pdf", args=[case.case_id]),
)
```

## Resposta aos gates de autoavaliação

1. **Qual texto substituiu `Este caso já está encerrado`?**
   `"Use este formulário para enviar uma mensagem operacional ao NIR sobre este caso. O sistema adicionará automaticamente a menção @nir para notificar a equipe NIR."`

2. **Que teste prova que a copy agora é neutra?**
   `test_scheduler_processed_detail_message_nir_copy_is_status_neutral` — verifica que `"mensagem operacional ao NIR sobre este caso"` está presente e `"Este caso já está encerrado"` está ausente.

3. **Onde `pdf_url` é passado no contexto? Ele é passado apenas para `scheduler_processed_detail`?**
   Em `_build_scheduler_detail_context` como parâmetro opcional `pdf_url: str | None = None`. É passado apenas por `scheduler_processed_detail` via `reverse("scheduler:processed_pdf", args=[case.case_id])`. `scheduler_context_detail` não passa o argumento, então recebe `None`.

4. **Que teste prova que o link de PDF aparece no detalhe de `Processados Hoje`?**
   `test_scheduler_processed_detail_shows_processed_pdf_link` — verifica que o conteúdo contém o caminho `processed/<case_id>/pdf/` e o texto `"PDF original"` ou `"Abrir PDF"`.

5. **A autorização de `scheduler_processed_pdf` foi alterada?** Não. A view e a rota continuam idênticas, exigindo `scheduler=request.user`.

6. **A busca histórica institucional ganhou link de PDF?** Não. `scheduler_context_detail` não passa `pdf_url`, portanto o bloco não aparece no template de casos históricos.

7. **Alguma migration/FSM/model foi criado/alterado?** Não. Apenas views, template e testes.

8. **Quais comandos de validação foram executados?**
   - `uv run ruff check .` → All checks passed
   - `uv run ruff format --check .` → 171 files already formatted
   - `uv run mypy .` → Success: no issues found in 190 source files
   - `uv run pytest` → 1582 passed

## Riscos/observações

- Nenhum risco identificado. Mudança cirúrgica, sem alteração de permissões, FSM, models ou migrations.
- O link de PDF aparece apenas no contexto de `scheduler_processed_detail`, que já exige `scheduler=request.user` e `appointment_status__in=["confirmed", "denied"]` — mesmas credenciais da view de PDF.
- `scheduler_context_detail` (histórico/notificação) não recebe `pdf_url`, portanto o PDF não é exposto indevidamente para casos de outros schedulers na busca histórica.
