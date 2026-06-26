"""Helper functions for reading and safely rendering the user manual Markdown."""

import re
from pathlib import Path

from django.conf import settings

USER_MANUAL_PATH = Path(settings.BASE_DIR) / "docs" / "manual" / "manual-usuarios.md"


def read_user_manual_markdown(path: Path = USER_MANUAL_PATH) -> str:
    """Read the user manual Markdown file and return its content as string.

    Raises FileNotFoundError if the file does not exist.
    """
    if not path.exists():
        raise FileNotFoundError(f"Manual não encontrado em: {path}")
    return path.read_text(encoding="utf-8")


def _escape_html(text: str) -> str:
    """Escape HTML special characters to prevent XSS."""
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    text = text.replace('"', "&quot;")
    text = text.replace("'", "&#x27;")
    return text


def render_manual_markdown_to_html(markdown_text: str) -> str:
    """Render Markdown text to safe HTML.

    Supports:
    - Headings (# through ######)
    - Paragraphs
    - Unordered lists (- / *)
    - Ordered lists (1. / 2. ...)
    - Blockquotes (>)
    - Inline code (`code`)
    - Code blocks (```\n...\n```)
    - Horizontal rules (---)
    - Tables (simple pipe-based)
    - Bold (**text**), italic (*text*), links ([text](url))

    All raw HTML in the input is escaped before rendering Markdown
    constructs, ensuring XSS safety.
    """
    # First, escape all raw HTML in the input
    safe_text = _escape_html(markdown_text)
    return _render_markdown_to_html(safe_text)


def _render_markdown_to_html(safe_text: str) -> str:
    """Render pre-escaped Markdown text to HTML."""
    lines = safe_text.split("\n")
    html_parts: list[str] = []
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]

        # Code block (``` ... ```)
        if line.strip().startswith("```"):
            code_lines: list[str] = []
            i += 1
            while i < n and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            code_content = "\n".join(code_lines)
            html_parts.append(f"<pre><code>{code_content}</code></pre>")
            i += 1  # skip closing ```
            continue

        # Horizontal rule
        if re.match(r"^\s*---+\s*$", line):
            html_parts.append("<hr>")
            i += 1
            continue

        # Blockquote
        if line.strip().startswith("&gt;"):
            # Collect all consecutive blockquote lines
            bq_lines: list[str] = []
            while i < n and lines[i].strip().startswith("&gt;"):
                bq_text = re.sub(r"^&gt;\s*", "", lines[i])
                bq_lines.append(bq_text)
                i += 1
            bq_content = "\n".join(bq_lines).strip()
            html_parts.append(f"<blockquote><p>{bq_content}</p></blockquote>")
            continue

        # Table detection (starts with | and second line contains ---)
        if line.strip().startswith("|") and i + 1 < n and "---" in lines[i + 1]:
            table_html = _render_table(lines, i)
            html_parts.append(table_html)
            # Skip past the table rows
            while i < n and lines[i].strip().startswith("|"):
                i += 1
            continue

        # Unordered list (- or *)
        if re.match(r"^\s*[-*]\s", line):
            ul_html = _render_unordered_list(lines, i)
            html_parts.append(ul_html)
            # Skip past list items
            while i < n and re.match(r"^\s*[-*]\s", lines[i]):
                i += 1
            continue

        # Ordered list (1. 2. etc)
        if re.match(r"^\s*\d+\.\s", line):
            ol_html = _render_ordered_list(lines, i)
            html_parts.append(ol_html)
            while i < n and re.match(r"^\s*\d+\.\s", lines[i]):
                i += 1
            continue

        # Heading
        heading_match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading_match:
            level = len(heading_match.group(1))
            text = _render_inline(heading_match.group(2))
            html_parts.append(f"<h{level}>{text}</h{level}>")
            i += 1
            continue

        # Empty line
        if not line.strip():
            i += 1
            continue

        # Regular paragraph
        para_lines: list[str] = [line]
        i += 1
        while (
            i < n
            and lines[i].strip()
            and not re.match(r"^(#{1,6}\s|[-*]\s|\d+\.\s|---)", lines[i])
            and not lines[i].strip().startswith("```")
            and not lines[i].strip().startswith("|")
        ):
            para_lines.append(lines[i])
            i += 1
        para_text = "<br>\n".join(_render_inline(pl) for pl in para_lines if pl.strip())
        if para_text:
            html_parts.append(f"<p>{para_text}</p>")
        continue

    return "\n".join(html_parts)


def _render_inline(text: str) -> str:
    """Render inline Markdown: bold, italic, code, links."""
    # Bold (**text**)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    # Italic (*text*)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", text)
    # Inline code (`code`)
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
    # Links [text](url)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    return text


def _render_unordered_list(lines: list[str], start: int) -> str:
    """Render an unordered list from lines starting at start index."""
    items: list[str] = []
    i = start
    while i < len(lines) and re.match(r"^\s*[-*]\s", lines[i]):
        item_text = re.sub(r"^\s*[-*]\s+", "", lines[i])
        items.append(f"<li>{_render_inline(item_text)}</li>")
        i += 1
    return "<ul>\n" + "\n".join(items) + "\n</ul>"


def _render_ordered_list(lines: list[str], start: int) -> str:
    """Render an ordered list from lines starting at start index."""
    items: list[str] = []
    i = start
    while i < len(lines) and re.match(r"^\s*\d+\.\s", lines[i]):
        item_text = re.sub(r"^\s*\d+\.\s+", "", lines[i])
        items.append(f"<li>{_render_inline(item_text)}</li>")
        i += 1
    return "<ol>\n" + "\n".join(items) + "\n</ol>"


def _render_table(lines: list[str], start: int) -> str:
    """Render a simple pipe-based table from lines starting at start index."""
    rows: list[list[str]] = []
    i = start

    while i < len(lines) and lines[i].strip().startswith("|"):
        cells = [cell.strip() for cell in lines[i].strip().split("|")]
        # Remove first and last empty cells from leading/trailing |
        if cells and cells[0] == "":
            cells = cells[1:]
        if cells and cells[-1] == "":
            cells = cells[:-1]
        rows.append(cells)
        i += 1

    if len(rows) < 2:
        return ""  # Need at least header + separator

    # Skip the separator row (second row with ---)
    header_cells = rows[0]
    table_html = ['<table class="table table-bordered table-sm">', "<thead><tr>"]
    for cell in header_cells:
        table_html.append(f"<th>{_render_inline(cell)}</th>")
    table_html.append("</tr></thead><tbody>")

    for row in rows[2:]:
        table_html.append("<tr>")
        for i, cell in enumerate(row):
            tag = "th" if i == 0 else "td"  # treat first column as header if looks like a header
            table_html.append(f"<{tag}>{_render_inline(cell)}</{tag}>")
        table_html.append("</tr>")
    table_html.append("</tbody></table>")

    return "\n".join(table_html)
