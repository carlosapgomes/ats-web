#!/usr/bin/env python3
"""Generate a PDF version of the official user manual from Markdown.

Usage:
    uv run python scripts/build_user_manual_pdf.py
    uv run python scripts/build_user_manual_pdf.py --input PATH --output PATH
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import fitz  # type: ignore[import-untyped]  # pymupdf

# ── Font constants for pymupdf ────────────────────────────────────────────

FONT_REGULAR = "Helvetica"
FONT_BOLD = "Helvetica-Bold"
FONT_ITALIC = "Helvetica-Oblique"
FONT_MONO = "Courier"
FONT_SIZE_BODY = 11
FONT_SIZE_H1 = 20
FONT_SIZE_H2 = 16
FONT_SIZE_H3 = 13
FONT_SIZE_SMALL = 9

MARGIN_LEFT = 50
MARGIN_RIGHT = 50
MARGIN_TOP = 50
MARGIN_BOTTOM = 50
PAGE_WIDTH = 595
PAGE_HEIGHT = 842


# ── Markdown → fitz helpers ────────────────────────────────────────────────


def _resolve_bold(text: str) -> list[tuple[str, str]]:
    """Split text into (segment, fontname) pairs for mixed bold rendering."""
    parts = re.split(r"(\*\*.*?\*\*)", text)
    result: list[tuple[str, str]] = []
    for part in parts:
        if part.startswith("**") and part.endswith("**"):
            result.append((part[2:-2], FONT_BOLD))
        elif part:
            result.append((part, FONT_REGULAR))
    return result


def _get_mixed_text_length(text: str, fontsize: float) -> float:
    """Measure text width, ignoring **bold** markers."""
    return fitz.get_text_length(text.replace("**", ""), fontname=FONT_REGULAR, fontsize=fontsize)


def _render_mixed_line(
    page: fitz.Page,
    text: str,
    x: float,
    y: float,
    font_size: float = FONT_SIZE_BODY,
    color: tuple[float, float, float] = (0, 0, 0),
) -> float:
    """Render a line, stripping **bold** markers to avoid kerning overlap.

    fitz.get_text_length and page.insert_text disagree by ~16% on
    rendered width due to kerning differences.  Splitting text into
    per-font segments and accumulating cursor_x creates cumulative
    positioning errors that cause visible overlap between adjacent
    bold / regular runs.  Rendering as a single plain-text call
    eliminates this entirely at the cost of bold formatting in the
    PDF (the Markdown source remains canonical).
    """
    line_height = font_size * 1.4
    plain = text.replace("**", "")
    page.insert_text(
        fitz.Point(x, y), plain, fontname=FONT_REGULAR, fontsize=font_size, color=color
    )
    return y + line_height


# ── Page bookkeeping ───────────────────────────────────────────────────────


class PdfDocument:
    """Manages pages, margins and line overflow for a fitz document."""

    def __init__(self) -> None:
        self.doc = fitz.open()
        self._page: fitz.Page | None = None
        self._y: float = MARGIN_TOP

    def _ensure_page(self) -> fitz.Page:
        if self._page is None:
            self._page = self.doc.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            self._y = MARGIN_TOP
        return self._page

    def _new_page(self) -> fitz.Page:
        self._page = self.doc.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
        self._y = MARGIN_TOP
        return self._page

    def _check_overflow(self, needed: float) -> None:
        available = PAGE_HEIGHT - MARGIN_BOTTOM
        if self._y + needed > available:
            self._new_page()

    def _word_wrap_render(
        self,
        text: str,
        font_size: float,
        x_start: float,
        width: float,
        fontname: str = FONT_REGULAR,
    ) -> float:
        """Word-wrap and render text, return final y position.

        Renders starting from the current self._y position.
        After each wrapped line, self._y is updated so that a
        page break mid-paragraph resets the rendering origin.
        """
        line_height = font_size * 1.4
        page = self._ensure_page()
        y = self._y + font_size
        first_line = True

        words = text.split()
        line_parts: list[str] = []
        for word in words:
            candidate = " ".join(line_parts + [word])
            w = _get_mixed_text_length(candidate, font_size)
            if w <= width:
                line_parts.append(word)
            else:
                line_text = " ".join(line_parts)
                y = _render_mixed_line(page, line_text, x_start, y, font_size)
                line_parts = [word]
                line_advance = y - self._y
                self._y += line_advance
                self._check_overflow(line_height)
                page = self._ensure_page()
                y = self._y + font_size
                first_line = False

        if line_parts:
            y = _render_mixed_line(page, " ".join(line_parts), x_start, y, font_size)
            if first_line:
                self._y = y - font_size * 0.5

        return y + font_size * 0.5  # bottom padding

    def add_heading(self, level: int, text: str) -> None:
        size = {1: FONT_SIZE_H1, 2: FONT_SIZE_H2, 3: FONT_SIZE_H3}.get(level, FONT_SIZE_H3)
        spacing = size * 1.5

        self._check_overflow(spacing + size * 0.5)
        page = self._ensure_page()
        y = self._y + size * 0.5

        page.insert_text(
            fitz.Point(MARGIN_LEFT, y),
            text,
            fontname=FONT_BOLD,
            fontsize=size,
            color=(0, 0, 0),
        )
        self._y = y + spacing

    def add_paragraph(self, text: str) -> None:
        content_width = PAGE_WIDTH - MARGIN_LEFT - MARGIN_RIGHT
        self._y = self._word_wrap_render(text, FONT_SIZE_BODY, MARGIN_LEFT, content_width)

    def add_empty_line(self) -> None:
        self._y += FONT_SIZE_BODY * 0.6
        self._check_overflow(0)

    def add_blockquote(self, text: str) -> None:
        """Render blockquote with indent, italic, and vertical bar."""
        indent = MARGIN_LEFT + 20
        width = PAGE_WIDTH - indent - MARGIN_RIGHT
        line_height = FONT_SIZE_BODY * 1.4

        self._check_overflow(line_height * 2)
        page = self._ensure_page()
        y = self._y + FONT_SIZE_BODY

        # Vertical bar
        page.draw_line(
            fitz.Point(MARGIN_LEFT + 10, y - FONT_SIZE_BODY + 2),
            fitz.Point(MARGIN_LEFT + 10, y + 2),
            color=(0.5, 0.5, 0.5),
            width=2,
        )

        y = self._word_wrap_render(text, FONT_SIZE_BODY, indent, width, fontname=FONT_ITALIC)
        self._y = y

    def add_code_block(self, text: str) -> None:
        """Render a code block in monospace with light background."""
        lines = text.split("\n")
        line_height = FONT_SIZE_SMALL * 1.4
        block_height = len(lines) * line_height + 8

        self._check_overflow(block_height)
        page = self._ensure_page()
        bg_top = self._y
        bg_bottom = self._y + block_height

        page.draw_rect(
            fitz.Rect(
                MARGIN_LEFT - 5,
                bg_top,
                PAGE_WIDTH - MARGIN_RIGHT + 5,
                bg_bottom,
            ),
            color=(0.92, 0.92, 0.92),
            fill=(0.92, 0.92, 0.92),
        )

        y = self._y + FONT_SIZE_SMALL + 4
        for line in lines:
            page.insert_text(
                fitz.Point(MARGIN_LEFT, y),
                line,
                fontname=FONT_MONO,
                fontsize=FONT_SIZE_SMALL,
                color=(0.15, 0.15, 0.15),
            )
            y += line_height
        self._y = bg_bottom + 4

    def add_bullet_list(self, items: list[str]) -> None:
        indent = MARGIN_LEFT + 10
        width = PAGE_WIDTH - indent - MARGIN_RIGHT
        line_height = FONT_SIZE_BODY * 1.4

        for item in items:
            self._check_overflow(line_height)
            bullet_text = f"• {item}"
            self._y = self._word_wrap_render(bullet_text, FONT_SIZE_BODY, indent, width)

    def add_numbered_list(self, items: list[str]) -> None:
        """Render numbered list items (each with prefix like '1. ')."""
        indent = MARGIN_LEFT + 10
        width = PAGE_WIDTH - indent - MARGIN_RIGHT

        for item in items:
            self._check_overflow(FONT_SIZE_BODY * 1.4)
            self._y = self._word_wrap_render(item, FONT_SIZE_BODY, indent, width)

    def add_toc(self, entries: list[tuple[int, str]]) -> None:
        """Render an 'Índice' section listing headings (level 1 and 2)."""
        self.add_heading(1, "Índice")
        indent_base = MARGIN_LEFT + 10
        for level, text in entries:
            indent = indent_base + (level - 1) * 16
            width = PAGE_WIDTH - indent - MARGIN_RIGHT
            # Strip Markdown bold markers for cleaner TOC text
            clean = re.sub(r"\*\*", "", text)
            self._y = self._word_wrap_render(clean, FONT_SIZE_BODY, indent, width, fontname=FONT_REGULAR)
        # Spacing after TOC
        self._check_overflow(FONT_SIZE_BODY * 1.4)
        self._y += FONT_SIZE_BODY

    def add_table(self, headers: list[str], rows: list[list[str]]) -> None:
        """Render a simple table with word-wrap and column clipping."""
        col_count = len(headers)
        col_width = (PAGE_WIDTH - MARGIN_LEFT - MARGIN_RIGHT) / col_count
        line_height = FONT_SIZE_BODY * 1.4
        row_count = len(rows) + 1  # +1 header row
        table_height = row_count * (line_height + 4) + 4
        font_size = FONT_SIZE_BODY - 1
        cell_padding = 2
        max_cell_text_width = col_width - cell_padding * 2

        def _strip_bold(text: str) -> str:
            """Remove ** markers for plain table cell rendering."""
            return text.replace("**", "")

        def _clip_text(text: str, max_width: float) -> str:
            """Clip text to fit width, measuring without ** markers."""
            plain = _strip_bold(text)
            if fitz.get_text_length(plain, fontname=FONT_REGULAR, fontsize=font_size) <= max_width:
                return plain
            lo, hi = 0, len(plain)
            while lo < hi:
                mid = (lo + hi + 1) // 2
                if fitz.get_text_length(plain[:mid] + "...", fontname=FONT_REGULAR, fontsize=font_size) <= max_width:
                    lo = mid
                else:
                    hi = mid - 1
            return plain[:lo] + "..." if lo > 0 else "..."

        self._check_overflow(table_height)
        page = self._ensure_page()
        y = self._y + 4 + FONT_SIZE_BODY

        # Header row
        for i, header in enumerate(headers):
            x = MARGIN_LEFT + i * col_width
            clipped = _clip_text(header, max_cell_text_width)
            page.insert_text(
                fitz.Point(x + cell_padding, y),
                clipped,
                fontname=FONT_BOLD,
                fontsize=font_size,
                color=(0, 0, 0),
            )
        # Header underline
        page.draw_line(
            fitz.Point(MARGIN_LEFT, y + 2),
            fitz.Point(PAGE_WIDTH - MARGIN_RIGHT, y + 2),
            color=(0, 0, 0),
        )
        y += line_height + 4

        # Data rows
        for row in rows:
            for i, cell in enumerate(row):
                x = MARGIN_LEFT + i * col_width
                clipped = _clip_text(cell, max_cell_text_width)
                page.insert_text(
                    fitz.Point(x + cell_padding, y),
                    clipped,
                    fontname=FONT_REGULAR,
                    fontsize=font_size,
                    color=(0, 0, 0),
                )
            y += line_height + 2

        self._y = y + 4

    def save(self, path: Path) -> None:
        self.doc.save(str(path))


# ── Markdown parsing ───────────────────────────────────────────────────────


def _parse_and_render(pdf: PdfDocument, markdown: str) -> None:
    """Parse Markdown text and render into PdfDocument."""
    lines = markdown.split("\n")
    n = len(lines)

    # Accumulators
    code_buffer: list[str] = []
    in_code_block = False
    table_headers: list[str] = []
    table_rows: list[list[str]] = []
    in_table = False
    bullet_items: list[str] = []
    numbered_items: list[str] = []

    def _flush_bullets() -> None:
        nonlocal bullet_items
        if bullet_items:
            pdf.add_bullet_list(bullet_items)
            bullet_items = []

    def _flush_numbered() -> None:
        nonlocal numbered_items
        if numbered_items:
            pdf.add_numbered_list(numbered_items)
            numbered_items = []

    def _flush_table() -> None:
        nonlocal table_headers, table_rows, in_table
        if table_headers:
            pdf.add_table(table_headers, table_rows)
            table_headers = []
            table_rows = []
        in_table = False

    i = 0
    while i < n:
        line = lines[i]
        i += 1

        # ── Code block ──────────────────────────────────────────────
        if line.strip().startswith("```"):
            if in_code_block:
                _flush_bullets()
                _flush_numbered()
                _flush_table()
                pdf.add_code_block("\n".join(code_buffer))
                code_buffer = []
                in_code_block = False
            else:
                in_code_block = True
                code_buffer = []
            continue

        if in_code_block:
            code_buffer.append(line)
            continue

        # ── Empty line ──────────────────────────────────────────────
        stripped = line.strip()
        if not stripped:
            _flush_bullets()
            _flush_numbered()
            _flush_table()
            pdf.add_empty_line()
            continue

        # ── Heading ─────────────────────────────────────────────────
        heading_match = re.match(r"^(#{1,3})\s+(.+?)(?:\s+#+)?$", stripped)
        if heading_match:
            _flush_bullets()
            _flush_numbered()
            _flush_table()
            level = len(heading_match.group(1))
            text = heading_match.group(2)
            pdf.add_heading(level, text)
            continue

        # ── Separator ───────────────────────────────────────────────
        if re.match(r"^-{3,}$", stripped):
            _flush_bullets()
            _flush_numbered()
            _flush_table()
            pdf.add_empty_line()
            continue

        # ── Blockquote ──────────────────────────────────────────────
        if stripped.startswith(">"):
            _flush_bullets()
            _flush_numbered()
            _flush_table()
            q_lines: list[str] = []
            q_lines.append(re.sub(r"^>+\s?", "", stripped))
            while i < n:
                next_stripped = lines[i].strip()
                if not next_stripped.startswith(">"):
                    break
                q_lines.append(re.sub(r"^>+\s?", "", next_stripped))
                i += 1
            pdf.add_blockquote(" ".join(q_lines))
            continue

        # ── Table ───────────────────────────────────────────────────
        if "|" in stripped and stripped.strip().startswith("|"):
            _flush_bullets()
            _flush_numbered()
            cells = [c.strip() for c in stripped.strip().strip("|").split("|")]
            # Skip separator rows like |---|---|
            if re.match(r"^[\s\-:|]+$", stripped):
                continue
            if not in_table:
                table_headers = cells
                in_table = True
            else:
                table_rows.append(cells)
            continue
        else:
            if in_table:
                _flush_table()

        # ── Bullet list ─────────────────────────────────────────────
        bullet_match = re.match(r"^\s*[-*+]\s+(.*)", stripped)
        if bullet_match:
            _flush_numbered()
            bullet_items.append(bullet_match.group(1))
            continue
        else:
            _flush_bullets()

        # ── Numbered list ───────────────────────────────────────────
        numbered_match = re.match(r"^\s*(\d+\.)\s+(.*)", stripped)
        if numbered_match:
            _flush_bullets()
            numbered_items.append(f"{numbered_match.group(1)} {numbered_match.group(2)}")
            continue
        else:
            _flush_numbered()

        # ── Regular paragraph ───────────────────────────────────────
        _flush_bullets()
        _flush_numbered()
        _flush_table()
        pdf.add_paragraph(stripped)

    # Flush remaining accumulators
    if in_code_block:
        pdf.add_code_block("\n".join(code_buffer))
    _flush_bullets()
    _flush_numbered()
    _flush_table()


# ── CLI ────────────────────────────────────────────────────────────────────


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate PDF from the official user manual Markdown.",
    )
    parser.add_argument(
        "--input",
        default="docs/manual/manual-usuarios.md",
        help="Path to the input Markdown file (default: docs/manual/manual-usuarios.md)",
    )
    parser.add_argument(
        "--output",
        default="docs/manual/dist/manual-usuarios.pdf",
        help="Path for the generated PDF (default: docs/manual/dist/manual-usuarios.pdf)",
    )
    return parser.parse_args(argv)


def read_markdown(path: Path) -> str:
    """Read and return the content of a Markdown file."""
    if not path.is_file():
        raise FileNotFoundError(f"Input file not found: {path}\nEnsure the file exists at the specified path.")
    return path.read_text(encoding="utf-8")


def build_pdf(markdown_content: str, output_path: Path) -> None:
    """Generate a PDF from Markdown content."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    pdf = PdfDocument()
    headings = _extract_toc_headings(markdown_content)
    if headings:
        pdf.add_toc(headings)
    _parse_and_render(pdf, markdown_content)
    pdf.save(output_path)


def _extract_toc_headings(markdown: str) -> list[tuple[int, str]]:
    """Extract (level, text) for headings of level 1 and 2, skipping code blocks."""
    entries: list[tuple[int, str]] = []
    in_code_block = False
    for line in markdown.split("\n"):
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        m = re.match(r"^(#{1,2})\s+(.+?)(?:\s+#+)?$", line)
        if m:
            entries.append((len(m.group(1)), m.group(2).strip()))
    return entries


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    input_path = Path(args.input)
    output_path = Path(args.output)

    markdown = read_markdown(input_path)
    build_pdf(markdown, output_path)

    print(f"PDF generated successfully: {output_path.resolve()}")


if __name__ == "__main__":
    main()
