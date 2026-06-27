# Design: Índice navegável no manual

## Estado atual

- `apps/accounts/manual.py` renderiza Markdown → HTML seguro (escape-first).
- Headings viram `<hN>` sem `id`.
- `scripts/build_user_manual_pdf.py` renderiza Markdown → PDF via `pymupdf`.
- Manual tem numeração limpa (`# 3. ...`, `## 3.1 ...`).

## Decisões técnicas

### Web (apps/accounts/manual.py)

Manter a abordagem escape-first (preserva o teste de XSS). Para obter slugs do texto original:

- `raw_lines = markdown_text.split("\n")` alinhado com `safe_lines = _escape_html(markdown_text).split("\n")` (escape não adiciona/remove newlines, então os índices casam).
- Ao detectar um heading em `safe_lines[i]`, slugificar `raw_lines[i]` (sem acento).

Funções:

- `_slugify(text: str) -> str`: lowercase, `unicodedata.normalize("NFKD")` para remover acentos, não-alfanum → `-`, colapsar, strip.
- `_render_markdown_to_html` retorna `(html, toc_entries)` ou, mais simples, coleta `toc_entries` em closure e expõe via `render_manual_markdown_to_html` que monta o bloco TOC e o prepõe.

TOC HTML: `<details open class="manual-toc"><summary>Índice</summary><ul>...</ul></details>` com `<a href="#slug">título</a>`.

### CSS (static/css/app.css)

- `.manual-toc { scroll-margin-top / background }`.
- `html { scroll-behavior: smooth }` ou `scroll-margin-top` nos headings para compensar header fixo.

### PDF (scripts/build_user_manual_pdf.py)

- Pré-varre o Markdown extraindo `(level, text)` para níveis 1 e 2.
- Antes de renderizar o corpo, renderiza um "Índice" (heading H1 + lista indentada por nível).
- Sem links clicáveis entre páginas neste slice (two-pass page-number = fora de escopo).

## Testes (TDD)

Web (`apps/accounts/tests/test_user_manual_view.py` ou novo `test_user_manual_toc.py`):

1. `test_renderer_adds_heading_ids` — heading recebe `id="..."`.
2. `test_renderer_generates_toc_with_links` — TOC com `<a href="#slug">`.
3. `test_heading_ids_are_unique` — headings duplicados ganham sufixo.
4. `test_slug_is_ascii_without_accents` — "Ações" → slug sem `ç`/`ã`.

PDF (`tests/test_user_manual_artifacts.py`):

5. `test_pdf_contains_toc_section` — texto do PDF contém "Índice" e títulos de seção.

## Arquivos esperados

1. `apps/accounts/manual.py` — slugs, ids, TOC.
2. `scripts/build_user_manual_pdf.py` — índice PDF.
3. `static/css/app.css` — estilo do TOC/scroll.
4. `apps/accounts/tests/test_user_manual_toc.py` — novos testes.
5. `tests/test_user_manual_artifacts.py` — teste de índice PDF.
6. `openspec/changes/user-manual-toc/tasks.md` — marcar ao concluir.

## Rollback

Reverter os arquivos acima. Sem migração/impacto operacional.
