"""Tests for the auto-generated table of contents in the user manual renderer."""

from __future__ import annotations

from apps.accounts.manual import render_manual_markdown_to_html


class TestManualToc:
    def test_renderer_adds_heading_ids(self) -> None:
        md = "# Título Principal\n\nTexto."
        html = render_manual_markdown_to_html(md)
        assert 'id="titulo-principal"' in html
        assert "<h1" in html

    def test_renderer_generates_toc_with_links(self) -> None:
        md = "# Seção Um\n\nTexto.\n\n## Subseção\n\nMais texto.\n\n# Seção Dois\n\nFim."
        html = render_manual_markdown_to_html(md)
        # TOC block present
        assert "manual-toc" in html
        # Links point to generated slugs
        assert 'href="#secao-um"' in html
        assert 'href="#secao-dois"' in html
        assert 'href="#subsecao"' in html

    def test_heading_ids_are_unique(self) -> None:
        md = "# Duplicado\n\nTexto.\n\n# Duplicado\n\nMais."
        html = render_manual_markdown_to_html(md)
        assert 'id="duplicado"' in html
        assert 'id="duplicado-2"' in html

    def test_slug_is_ascii_without_accents(self) -> None:
        md = "# Ações do usuário NIR\n\nTexto."
        html = render_manual_markdown_to_html(md)
        # No accents/cedilla in the generated id
        assert 'id="acoes-do-usuario-nir"' in html
