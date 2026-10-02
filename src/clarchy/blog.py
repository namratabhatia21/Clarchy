"""Blog posts: Markdown files in data/blog with a small front matter block. Posts being
rewritten wait in drafts/blog/ at the repository root, which is not published.

    ---
    title: Why architecture needs a drawing
    date: 2026-10-01
    author: Namrata Bhatia
    summary: One or two sentences for the list.
    ---
    Body in Markdown.

Only the Markdown the posts use is supported, so there is no dependency: headings,
paragraphs, bulleted and numbered lists, block quotes, **bold**, *italic*, `code` and
[links](https://...). Everything is HTML-escaped first, and only http(s) links and
relative links survive.
"""

from __future__ import annotations

import html
import re
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import Any

from clarchy import catalog

INLINE = [
    (re.compile(r"`([^`]+)`"), r"<code>\1</code>"),
    (re.compile(r"\*\*([^*]+)\*\*"), r"<strong>\1</strong>"),
    (re.compile(r"(?<![*\w])\*([^*\n]+)\*(?![*\w])"), r"<em>\1</em>"),
]
LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")


def _inline(text: str) -> str:
    out = html.escape(text, quote=False)
    for pattern, repl in INLINE:
        out = pattern.sub(repl, out)

    def link(m: re.Match) -> str:
        label, url = m.group(1), html.unescape(m.group(2))
        if not re.match(r"^(https?://|#|/)", url):
            return label
        external = url.startswith("http")
        attrs = ' target="_blank" rel="noopener noreferrer"' if external else ""
        return f'<a href="{html.escape(url)}"{attrs}>{label}</a>'

    return LINK.sub(link, out)


def to_html(markdown: str) -> str:
    blocks: list[str] = []
    lines = markdown.strip("\n").split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        heading = re.match(r"^(#{1,3})\s+(.*)$", line)
        if heading:
            level = len(heading.group(1)) + 1  # the post title is the h1
            blocks.append(f"<h{level}>{_inline(heading.group(2))}</h{level}>")
            i += 1
            continue
        for marker, tag in ((r"^[-*]\s+", "ul"), (r"^\d+\.\s+", "ol")):
            if re.match(marker, line):
                items = []
                while i < len(lines) and re.match(marker, lines[i]):
                    item = re.sub(marker, "", lines[i])
                    i += 1
                    while i < len(lines) and lines[i].startswith("  ") and lines[i].strip():
                        item += " " + lines[i].strip()
                        i += 1
                    items.append(f"<li>{_inline(item)}</li>")
                blocks.append(f"<{tag}>{''.join(items)}</{tag}>")
                break
        else:
            if line.startswith(">"):
                quote = []
                while i < len(lines) and lines[i].startswith(">"):
                    quote.append(lines[i].lstrip("> ").strip())
                    i += 1
                blocks.append(f"<blockquote><p>{_inline(' '.join(quote))}</p></blockquote>")
                continue
            para = []
            while (
                i < len(lines)
                and lines[i].strip()
                and not re.match(r"^(#{1,3}\s|[-*]\s|\d+\.\s|>)", lines[i])
            ):
                para.append(lines[i].strip())
                i += 1
            blocks.append(f"<p>{_inline(' '.join(para))}</p>")
    return "\n".join(blocks)


def _front_matter(text: str) -> tuple[dict[str, str], str]:
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return {}, text
    meta = {}
    for line in m.group(1).splitlines():
        key, _, value = line.partition(":")
        if key.strip():
            meta[key.strip()] = value.strip().strip('"')
    return meta, text[m.end() :]


def posts(folder: Path | Traversable | None = None) -> list[dict[str, Any]]:
    """Every published post (or every post in `folder`), newest first, with its body
    rendered to HTML. No posts is fine: the Blog page says the first ones are coming."""
    out = []
    folder = folder or catalog.data_path("blog")
    if not folder.is_dir():
        return []
    for entry in sorted(folder.iterdir(), key=lambda p: p.name):
        if not entry.name.endswith(".md"):
            continue
        meta, body = _front_matter(entry.read_text(encoding="utf-8"))
        words = len(re.findall(r"\w+", body))
        out.append(
            {
                "id": entry.name.removesuffix(".md"),
                "title": meta.get("title", entry.name),
                "date": meta.get("date", ""),
                "author": meta.get("author", ""),
                "role": meta.get("role", ""),
                "summary": meta.get("summary", ""),
                "minutes": max(1, round(words / 220)),
                "html": to_html(body),
            }
        )
    return sorted(out, key=lambda p: (p["date"], p["id"]), reverse=True)
