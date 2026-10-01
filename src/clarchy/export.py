"""Static site export: the web UI as one self-contained HTML file.

    clarchy export-site -o site/                       # site/index.html, host anywhere
    clarchy export-site -o site/ --fragment            # body-only page for hosts that add
                                                           # their own <html>/<head> skeleton
    clarchy export-site -o site/ --api-base URL        # front end for a hosted API

The page plans in the visitor's browser: next to index.html goes clarchy-engine.zip,
this package, which the page runs with Pyodide (Python compiled to WebAssembly, loaded
from its CDN on first use). It also embeds every built-in pattern rendered on every
provider, the service catalog and a recorded rule-based run of each sample, so the
examples and samples appear instantly without loading the engine. --no-engine builds a
replay-only page. Fragment builds target sandboxed hosts that block downloads, so their
download buttons copy to the clipboard instead.

Official provider icons are never embedded: hosting them is a separate licensing question
(see docs/decisions/0002-no-bundled-provider-icons.md).
"""

from __future__ import annotations

import asyncio
import io
import json
import re
import zipfile
from importlib import resources
from pathlib import Path
from typing import Any

from clarchy import blog, catalog, payloads
from clarchy.icons import IconLibrary

SCRIPT_TAG = re.compile(r'<script src="/static/([\w-]+\.js)"></script>')
PYODIDE_VERSION = "314.0.7"
PYODIDE_BASE = f"https://cdn.jsdelivr.net/pyodide/v{PYODIDE_VERSION}/full/"
ENGINE_BUNDLE = "clarchy-engine.zip"


def engine_bundle() -> bytes:
    """This package as a zip for Pyodide: the Python modules and their data files."""
    root = Path(__file__).resolve().parent
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(root.rglob("*")):
            rel = path.relative_to(root)
            if path.is_dir() or rel.parts[0] == "static" or "__pycache__" in rel.parts:
                continue
            if path.suffix not in (".py", ".yaml", ".md"):
                continue
            archive.write(path, f"clarchy/{rel.as_posix()}")
    return buffer.getvalue()


def engine_config(base: str = PYODIDE_BASE) -> dict[str, Any]:
    base = base if base.endswith("/") else base + "/"
    return {
        "pyodide": f"{base}pyodide.js",
        "index_url": base,
        "bundle": ENGINE_BUNDLE,
        "packages": ["pydantic", "pyyaml"],
    }


STYLESHEET_TAG = '<link rel="stylesheet" href="/static/app.css">'


def _designs_for(key: str, spec_yaml: str) -> dict[str, Any]:
    designs = {}
    for provider in catalog.providers():
        status, body = payloads.design_payload(spec_yaml, provider)
        if status != 200:
            raise RuntimeError(f"{key} failed on {provider}: {body}")
        designs[f"{key}.{provider}"] = body
    return designs


def recorded_runs() -> dict[str, dict[str, Any]]:
    """Every pipeline event of a rule-based run of each sample, for the Plan page to replay."""
    from clarchy.ingest import from_text
    from clarchy.planner import PlanOptions, run_plan

    runs = {}
    for sample_id, _title, text in catalog.samples():
        events: list[dict[str, Any]] = []
        result = asyncio.run(
            run_plan(from_text(text), PlanOptions(mode="rules"), None, events.append)
        )
        runs[sample_id] = {"events": events, "spec_yaml": result.spec_yaml}
    return runs


def site_data(clipboard_only: bool = False, engine: dict[str, Any] | None = None) -> dict[str, Any]:
    no_icons = {p: IconLibrary(None) for p in catalog.providers()}
    pattern_yaml = {name: catalog.pattern_text(name) for name in catalog.pattern_names()}
    runs = recorded_runs()

    # The UI looks designs up by the exact spec text it holds.
    spec_index: dict[str, str] = {}
    designs: dict[str, Any] = {}
    for name, text in pattern_yaml.items():
        spec_index[text] = name
        designs.update(_designs_for(name, text))
    for sample_id, run in runs.items():
        key = f"sample:{sample_id}"
        spec_index[run["spec_yaml"]] = key
        designs.update(_designs_for(key, run["spec_yaml"]))

    return {
        "meta": payloads.meta_payload(no_icons),
        "samples": payloads.samples_payload(),
        "blog": blog.posts(),
        "patterns": payloads.patterns_payload(),
        "pattern_yaml": pattern_yaml,
        "catalog": payloads.catalog_payload(),
        "runs": {sample_id: {"events": run["events"]} for sample_id, run in runs.items()},
        "spec_index": spec_index,
        "designs": designs,
        "clipboard_only": clipboard_only,
        "engine": engine,
    }


def _between(text: str, start: str, end: str) -> str:
    i, j = text.index(start) + len(start), text.index(end)
    return text[i:j]


def _script_json(value: Any) -> str:
    # "<" never appears outside JSON strings, so escaping it keeps "</script>" inside
    # embedded SVG from ending the script element early.
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")


def build_site(
    fragment: bool = False, api_base: str | None = None, engine: dict[str, Any] | None = None
) -> str:
    static = resources.files("clarchy").joinpath("static")
    index = static.joinpath("index.html").read_text(encoding="utf-8")
    css = static.joinpath("app.css").read_text(encoding="utf-8")

    head = _between(index, "<head>", "</head>")
    body = _between(index, "<body>", "</body>")
    scripts = SCRIPT_TAG.findall(body)
    if not scripts or STYLESHEET_TAG not in head:
        raise ValueError("index.html no longer references its /static/ scripts and app.css")

    if api_base:
        config = f"window.CLARCHY_API_BASE = {_script_json(api_base.rstrip('/'))};"
    else:
        data = site_data(clipboard_only=fragment, engine=engine)
        config = f"window.CLARCHY_DATA = {_script_json(data)};"
    inlined = [f"<script>{config}</script>"]
    for name in scripts:
        js = static.joinpath(name).read_text(encoding="utf-8")
        if "</script" in js.lower():
            raise ValueError(f"{name} must not contain a closing script tag")
        inlined.append(f"<script>\n{js}</script>")
    first = body.index(f'<script src="/static/{scripts[0]}"></script>')
    body = body[:first] + "\n  ".join(inlined) + SCRIPT_TAG.sub("", body[first:]).rstrip() + "\n"

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


def export_site(
    out_dir: str | Path,
    fragment: bool = False,
    api_base: str | None = None,
    with_engine: bool = True,
    pyodide_base: str = PYODIDE_BASE,
) -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    engine = engine_config(pyodide_base) if with_engine and not api_base else None
    path = out / "index.html"
    path.write_text(build_site(fragment, api_base, engine), encoding="utf-8")
    if engine:
        (out / ENGINE_BUNDLE).write_bytes(engine_bundle())
    return path
