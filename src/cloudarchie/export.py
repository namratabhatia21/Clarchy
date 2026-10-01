"""Static site export: the web UI as one self-contained HTML file.

    cloudarchie export-site -o site/              # site/index.html, host anywhere
    cloudarchie export-site -o site/ --fragment   # body-only page for hosts that add
                                                  # their own <html>/<head> skeleton

The page embeds every built-in pattern rendered on every provider plus the service catalog,
so it works without a server. Live spec editing needs the server (`cloudarchie serve`);
the exported page shows specs read-only and says so.

Official provider icons are never embedded: hosting them is a separate licensing question
(see docs/decisions/0002-no-bundled-provider-icons.md).
"""

from __future__ import annotations

import json
import re
from importlib import resources
from pathlib import Path
from typing import Any

from cloudarchie import catalog, payloads
from cloudarchie.icons import IconLibrary

APP_SCRIPT_TAG = '<script src="/static/app.js"></script>'
STYLESHEET_TAG = '<link rel="stylesheet" href="/static/app.css">'


def site_data() -> dict[str, Any]:
    no_icons = {p: IconLibrary(None) for p in catalog.providers()}
    designs = {}
    for name in catalog.pattern_names():
        for provider in catalog.providers():
            status, body = payloads.design_payload(catalog.pattern_text(name), provider)
            if status != 200:
                raise RuntimeError(f"pattern {name} failed on {provider}: {body}")
            designs[f"{name}.{provider}"] = body
    return {
        "meta": payloads.meta_payload(no_icons),
        "patterns": payloads.patterns_payload(),
        "pattern_yaml": {name: catalog.pattern_text(name) for name in catalog.pattern_names()},
        "catalog": payloads.catalog_payload(),
        "designs": designs,
    }


def _between(text: str, start: str, end: str) -> str:
    i, j = text.index(start) + len(start), text.index(end)
    return text[i:j]


def build_site(fragment: bool = False) -> str:
    static = resources.files("cloudarchie").joinpath("static")
    index = static.joinpath("index.html").read_text(encoding="utf-8")
    css = static.joinpath("app.css").read_text(encoding="utf-8")
    js = static.joinpath("app.js").read_text(encoding="utf-8")
    if "</script" in js.lower():
        raise ValueError("app.js must not contain a closing script tag")

    # "<" never appears outside JSON strings, so escaping it keeps "</script>" inside
    # embedded SVG from ending the script element early.
    data = json.dumps(site_data(), ensure_ascii=False, separators=(",", ":")).replace(
        "<", "\\u003c"
    )

    head = _between(index, "<head>", "</head>")
    body = _between(index, "<body>", "</body>")
    if APP_SCRIPT_TAG not in body or STYLESHEET_TAG not in head:
        raise ValueError("index.html no longer references /static/app.js and /static/app.css")
    body = body.replace(
        APP_SCRIPT_TAG,
        f"<script>window.CLOUDARCHIE_DATA = {data};</script>\n  <script>\n{js}</script>",
    )

    title = re.search(r"<title>.*?</title>", head, re.S).group(0)
    links = [
        line.strip()
        for line in head.splitlines()
        if line.strip().startswith("<link") and STYLESHEET_TAG not in line
    ]
    if fragment:
        links = [link for link in links if 'rel="icon"' not in link]
        page = "\n".join([title, *links, f"<style>\n{css}</style>", body.strip()]) + "\n"
    else:
        page = "\n".join(
            [
                "<!doctype html>",
                '<html lang="en">',
                "<head>",
                '<meta charset="utf-8">',
                '<meta name="viewport" content="width=device-width, initial-scale=1">',
                title,
                *links,
                f"<style>\n{css}</style>",
                "</head>",
                "<body>",
                body.strip(),
                "</body>",
                "</html>",
            ]
        )
    if "/static/" in page:
        raise ValueError("exported page still references /static/ assets")
    return page


def export_site(out_dir: str | Path, fragment: bool = False) -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "index.html"
    path.write_text(build_site(fragment), encoding="utf-8")
    return path
