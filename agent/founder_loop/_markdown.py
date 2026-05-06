"""
Tiny markdown → HTML converter. Handles the subset our docs use:

* H1/H2/H3 headers
* Paragraphs
* **bold**, *italic*, ``code`` (inline)
* Fenced code blocks (```...```)
* Bullet lists (`- ` or `* `)
* Ordered lists (`1. `, `2. ` …)
* Blockquotes (`> `)
* Links `[text](url)`
* Tables `| col | col |`
* Horizontal rules `---`

Not a full CommonMark implementation. Just enough for our four user-
facing docs and for any future doc we add at the daemon's /about /
/how etc. routes. Keeping it inline avoids adding a dependency.
"""
from __future__ import annotations

import html
import re
from typing import List, Tuple


def render_markdown(src: str) -> str:
    """Convert markdown ``src`` to an HTML body string (no <html> /
    <head> wrapper)."""
    lines = src.splitlines()
    out: List[str] = []
    i = 0
    in_list: str | None = None  # 'ul' | 'ol' | None
    in_blockquote = False

    def close_list() -> None:
        nonlocal in_list
        if in_list:
            out.append(f"</{in_list}>")
            in_list = None

    def close_blockquote() -> None:
        nonlocal in_blockquote
        if in_blockquote:
            out.append("</blockquote>")
            in_blockquote = False

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Fenced code block
        if stripped.startswith("```"):
            close_list(); close_blockquote()
            lang = stripped[3:].strip()
            i += 1
            buf = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            out.append(
                f'<pre><code class="lang-{html.escape(lang)}">'
                + html.escape("\n".join(buf))
                + "</code></pre>"
            )
            i += 1
            continue

        # Horizontal rule
        if re.match(r"^[-*_]{3,}\s*$", stripped):
            close_list(); close_blockquote()
            out.append("<hr>")
            i += 1
            continue

        # Headers
        m = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if m:
            close_list(); close_blockquote()
            level = len(m.group(1))
            out.append(f"<h{level}>{_inline(m.group(2))}</h{level}>")
            i += 1
            continue

        # Tables — detect a header row + separator row + body rows
        if stripped.startswith("|") and "|" in stripped[1:]:
            # Look ahead for separator
            if i + 1 < len(lines) and re.match(
                r"^\s*\|?\s*:?[-]+:?\s*(\|\s*:?[-]+:?\s*)+\|?\s*$",
                lines[i + 1],
            ):
                close_list(); close_blockquote()
                header = _split_table_row(stripped)
                i += 2  # skip separator
                rows = []
                while (
                    i < len(lines)
                    and lines[i].strip().startswith("|")
                    and lines[i].strip()
                ):
                    rows.append(_split_table_row(lines[i].strip()))
                    i += 1
                out.append("<table>")
                out.append("<thead><tr>" + "".join(
                    f"<th>{_inline(c)}</th>" for c in header
                ) + "</tr></thead>")
                out.append("<tbody>")
                for r in rows:
                    out.append("<tr>" + "".join(
                        f"<td>{_inline(c)}</td>" for c in r
                    ) + "</tr>")
                out.append("</tbody></table>")
                continue

        # Blockquote
        if stripped.startswith("> "):
            close_list()
            if not in_blockquote:
                out.append("<blockquote>")
                in_blockquote = True
            out.append(f"<p>{_inline(stripped[2:])}</p>")
            i += 1
            continue
        else:
            close_blockquote()

        # Bullet list
        m = re.match(r"^[-*]\s+(.+)$", stripped)
        if m:
            if in_list != "ul":
                close_list()
                out.append("<ul>")
                in_list = "ul"
            out.append(f"<li>{_inline(m.group(1))}</li>")
            i += 1
            continue

        # Ordered list
        m = re.match(r"^\d+\.\s+(.+)$", stripped)
        if m:
            if in_list != "ol":
                close_list()
                out.append("<ol>")
                in_list = "ol"
            out.append(f"<li>{_inline(m.group(1))}</li>")
            i += 1
            continue

        # Blank line
        if not stripped:
            close_list()
            i += 1
            continue

        # Paragraph (gather consecutive non-blank lines)
        close_list()
        buf = [stripped]
        i += 1
        while (
            i < len(lines)
            and lines[i].strip()
            and not _starts_block(lines[i].strip())
        ):
            buf.append(lines[i].strip())
            i += 1
        out.append(f"<p>{_inline(' '.join(buf))}</p>")

    close_list()
    close_blockquote()
    return "\n".join(out)


def _starts_block(stripped: str) -> bool:
    if stripped.startswith("#"):
        return True
    if stripped.startswith("```"):
        return True
    if stripped.startswith("> "):
        return True
    if stripped.startswith("|"):
        return True
    if re.match(r"^[-*]\s+", stripped):
        return True
    if re.match(r"^\d+\.\s+", stripped):
        return True
    if re.match(r"^[-*_]{3,}\s*$", stripped):
        return True
    return False


def _split_table_row(row: str) -> List[str]:
    row = row.strip()
    if row.startswith("|"):
        row = row[1:]
    if row.endswith("|"):
        row = row[:-1]
    return [c.strip() for c in row.split("|")]


# ---------------------------------------------------------------------------
# Inline rules
# ---------------------------------------------------------------------------


def _inline(text: str) -> str:
    """Apply inline rules. Order matters: extract code spans first so
    other rules don't touch their contents."""
    placeholders: List[str] = []

    def stash(html_str: str) -> str:
        placeholders.append(html_str)
        return f"\x00{len(placeholders) - 1}\x00"

    # Inline code
    text = re.sub(
        r"`([^`]+)`",
        lambda m: stash(f"<code>{html.escape(m.group(1))}</code>"),
        text,
    )

    # Escape any remaining special HTML chars *before* applying our
    # replacements that emit tags.
    text = html.escape(text, quote=False)

    # Links — [text](url). We escaped already so brackets become &lt; etc;
    # un-escape them for this pass since they were unescaped in the source.
    text = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        lambda m: stash(
            f'<a href="{html.escape(m.group(2))}" '
            f'target="_blank" rel="noopener">{m.group(1)}</a>'
        ),
        text,
    )

    # Bold: **text** or __text__
    text = re.sub(r"\*\*([^\*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"__([^_]+)__", r"<strong>\1</strong>", text)

    # Italic: *text* or _text_
    text = re.sub(r"(?<!\*)\*([^\*]+)\*(?!\*)", r"<em>\1</em>", text)
    text = re.sub(r"(?<!_)_([^_]+)_(?!_)", r"<em>\1</em>", text)

    # Restore placeholders
    def restore(m: re.Match) -> str:
        idx = int(m.group(1))
        return placeholders[idx]

    text = re.sub(r"\x00(\d+)\x00", restore, text)
    return text


__all__ = ["render_markdown"]
