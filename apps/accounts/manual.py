"""Helper functions for reading and safely rendering the user manual Markdown."""

import re
import unicodedata
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
    - Headings (# through ######) with stable ASCII slug ids
    - An auto-generated table of contents (levels 1 and 2) at the top
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
    # Keep raw lines aligned with escaped lines so we can derive slugs
    # from the original (unescaped) heading text. Escaping never adds or
    # removes newlines, so indices stay aligned.
    raw_lines = markdown_text.split("\n")
    safe_text = _escape_html(markdown_text)
    body_html, toc_entries = _render_markdown_to_html(safe_text, raw_lines)
    toc_html = _build_toc_html(toc_entries)
    return toc_html + body_html


def _slugify(text: str) -> str:
    """Convert heading text to an ASCII, URL-safe slug."""
    # Strip Markdown inline markers before slugifying
    cleaned = re.sub(r"[`*_~\[\]()]", "", text).strip()
    # Remove accents: decompose and drop combining marks
    decomposed = unicodedata.normalize("NFKD", cleaned)
    ascii_only = "".join(c for c in decomposed if not unicodedata.combining(c))
    lowered = ascii_only.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    return slug or "secao"


def _build_toc_html(entries: list[tuple[int, str, str]]) -> str:
    """Build a collapsible table of contents from collected heading entries.

    Each entry is (level, slug, title_html_escaped).
    """
    if not entries:
        return ""
    items: list[str] = []
    for level, slug, title in entries:
        items.append(f'<li class="manual-toc__item manual-toc__item--l{level}"><a href="#{slug}">{title}</a></li>')
    return (
        '<details open class="manual-toc">'
        '<summary class="manual-toc__summary">Índice</summary>'
        '<ul class="manual-toc__list">' + "\n".join(items) + "</ul>"
        "</details>"
    )


def _render_markdown_to_html(
    safe_text: str, raw_lines: list[str] | None = None
) -> tuple[str, list[tuple[int, str, str]]]:
    """Render pre-escaped Markdown text to HTML.

    Returns (body_html, toc_entries) where toc_entries is a list of
    (level, slug, escaped_title) for headings of level <= 2.
    """
    if raw_lines is None:
        raw_lines = safe_text.split("\n")
    lines = safe_text.split("\n")
    html_parts: list[str] = []
    toc_entries: list[tuple[int, str, str]] = []
    used_slugs: set[str] = set()
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
            inline_text = _render_inline(heading_match.group(2))
            # Derive slug from the raw (unescaped) line for clean ASCII ids
            raw_heading = re.sub(r"^#{1,6}\s+", "", raw_lines[i])
            base_slug = _slugify(raw_heading)
            slug = base_slug
            counter = 2
            while slug in used_slugs:
                slug = f"{base_slug}-{counter}"
                counter += 1
            used_slugs.add(slug)
            if level <= 2:
                toc_entries.append((level, slug, heading_match.group(2)))
            html_parts.append(f'<h{level} id="{slug}">{inline_text}</h{level}>')
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

    return "\n".join(html_parts), toc_entries

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
