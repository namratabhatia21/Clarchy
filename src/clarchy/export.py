"""Static site export: the web UI as a set of pages and the files they load.

    clarchy export-site -o site/                       # a page per address, host anywhere
    clarchy export-site -o site/ --fragment            # one body-only page for hosts that
                                                           # add their own <html>/<head>
    clarchy export-site -o site/ --api-base URL        # front end for a hosted API

Every page has its own address (/, /examples/, /examples/<id>/, /services/, /pricing/,
/how-to/, /blog/, /about/, /privacy/, /terms/), rendered by site.py with its content in
the HTML, plus sitemap.xml, robots.txt and a _headers file for Cloudflare. The scripts
and the embedded data sit in assets/ with a content hash in their names, so browsers keep
them. Pages plan in the visitor's browser: beside them goes clarchy-engine.zip, this
package, which the page runs with Pyodide (Python compiled to WebAssembly, loaded from its
CDN on first use). The data holds the service catalog and a recorded rule-based run of
each sample, so samples and examples appear without loading the engine, and every
built-in pattern is pre-rendered on every provider in designs/<key>.<provider>.json,
fetched when shown. The site also gets its fonts (fonts/), sharing images and a 404 page.
--no-engine builds a replay-only site. Fragment builds are one file with every page and
#hash links, for sandboxed hosts that block downloads, so their download buttons copy to
the clipboard instead and they keep the drawings inline.

AWS designs use the AWS Architecture Icons that ship with the package (ADR 0012); the
other clouds keep lettered badges.
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import json
import zipfile
from importlib import resources
from pathlib import Path
from typing import Any

from clarchy import blog, catalog, payloads, site
from clarchy.icons import bundled_library

SCRIPT_TAG = site.SCRIPT_TAG
PYODIDE_VERSION = "314.0.7"
PYODIDE_BASE = f"https://cdn.jsdelivr.net/pyodide/v{PYODIDE_VERSION}/full/"
ENGINE_BUNDLE = "clarchy-engine.zip"


def engine_bundle() -> bytes:
    """This package as a zip for Pyodide: the Python modules and their data files, including
    the bundled AWS icons."""
    root = Path(__file__).resolve().parent
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(root.rglob("*")):
            rel = path.relative_to(root)
            if path.is_dir() or rel.parts[0] == "static" or "__pycache__" in rel.parts:
                continue
            if path.suffix not in (".py", ".yaml", ".md", ".svg"):
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


def _designs_for(key: str, spec_yaml: str) -> dict[str, Any]:
    designs = {}
    for provider in catalog.providers():
        status, body = payloads.design_payload(spec_yaml, provider, bundled_library(provider))
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
    icons = {p: bundled_library(p) for p in catalog.providers()}
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
        "meta": payloads.meta_payload(icons),
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


def _script_json(value: Any) -> str:
    # "<" never appears outside JSON strings, so escaping it keeps "</script>" inside
    # embedded SVG from ending the script element early.
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")


def design_file(key: str) -> str:
    """The file name of one pre-rendered design: "sample:x.aws" -> "sample-x.aws.json"."""
    return key.replace(":", "-") + ".json"


def _static(name: str) -> str:
    return resources.files("clarchy").joinpath("static", name).read_text(encoding="utf-8")


def app_scripts() -> list[str]:
    """The page's scripts, in the order index.html loads them."""
    names = SCRIPT_TAG.findall(site.template())
    if not names:
        raise ValueError("index.html no longer references its /static/ scripts")
    scripts = []
    for name in names:
        js = _static(name)
        if "</script" in js.lower():
            raise ValueError(f"{name} must not contain a closing script tag")
        scripts.append(js)
    return scripts


def _inline_style() -> str:
    return f"<style>\n{_static('app.css')}</style>"


def _content(data: dict[str, Any] | None) -> site.Content:
    if data is not None:
        return site.content(data["meta"])
    icons = {p: bundled_library(p) for p in catalog.providers()}
    return site.content(payloads.meta_payload(icons))


def _mode(api_base: str | None, engine: dict[str, Any] | None) -> str:
    return "remote" if api_base else "static" if engine else "replay"


def build_site(
    fragment: bool = False,
    api_base: str | None = None,
    engine: dict[str, Any] | None = None,
) -> str:
    """Every page in one file with #hash links and the scripts and data inline, for hosts
    that take a single file. fragment=True drops the document skeleton the host adds."""
    data = None
    if api_base:
        config = f"window.CLARCHY_API_BASE = {_script_json(api_base.rstrip('/'))};"
    else:
        data = site_data(clipboard_only=fragment, engine=engine)
        config = f"window.CLARCHY_DATA = {_script_json(data)};"
    scripts = "\n  ".join(
        [f"<script>{config}</script>", *(f"<script>\n{js}</script>" for js in app_scripts())]
    )
    shell = site.Shell(
        mode=_mode(api_base, engine),
        style=_inline_style(),
        scripts=scripts + "\n",
        root="",
        single=True,
        fragment=fragment,
    )
    return site.render(None, _content(data), shell)


def _hashed(stem: str, text: str) -> str:
    return f"assets/{stem}.{hashlib.sha256(text.encode('utf-8')).hexdigest()[:10]}.js"


def build_pages(
    api_base: str | None = None, engine: dict[str, Any] | None = None
) -> tuple[dict[str, str], dict[str, Any]]:
    """The multi-page site: every page at its own address (pricing/index.html, ...), the
    scripts and data as long-cached files in assets/, robots.txt, sitemap.xml and the
    Cloudflare _headers and _redirects files. Returns (file texts by path, designs for designs/)."""
    files: dict[str, str] = {}
    designs: dict[str, Any] = {}
    data = None
    scripts = ""
    if api_base:
        config = f"window.CLARCHY_API_BASE = {_script_json(api_base.rstrip('/'))};"
        scripts += f"<script>{config}</script>\n  "
    else:
        data = site_data(engine=engine)
        designs = data.pop("designs")
        data["design_files"] = True
        data_js = f"window.CLARCHY_DATA = {_script_json(data)};\n"
        data_path = _hashed("data", data_js)
        files[data_path] = data_js
        scripts += f'<script src="/{data_path}" defer></script>\n  '
    app_js = "\n".join(app_scripts())
    app_path = _hashed("app", app_js)
    files[app_path] = app_js
    scripts += f'<script src="/{app_path}" defer></script>\n'
    shell = site.Shell(mode=_mode(api_base, engine), style=_inline_style(), scripts=scripts)
    content = _content(data)
    for page in site.pages(content):
        files[f"{page.path.strip('/')}/index.html".lstrip("/")] = site.render(page, content, shell)
    files["sitemap.xml"] = site.sitemap(content)
    files["robots.txt"] = site.ROBOTS
    files["_headers"] = site.HEADERS
    files["_redirects"] = site.redirects(content)
    return files, designs


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
    if fragment:
        path.write_text(build_site(True, api_base, engine), encoding="utf-8")
    else:
        files, designs = build_pages(api_base, engine)
        for name, text in files.items():
            target = out / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        if designs:
            folder = out / "designs"
            folder.mkdir(exist_ok=True)
            for key, body in designs.items():
                text = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
                (folder / design_file(key)).write_text(text, encoding="utf-8")
    if engine:
        (out / ENGINE_BUNDLE).write_bytes(engine_bundle())
    static = resources.files("clarchy").joinpath("static")
    fonts = out / "fonts"
    fonts.mkdir(exist_ok=True)
    for item in static.joinpath("fonts").iterdir():
        (fonts / item.name).write_bytes(item.read_bytes())
    for item in static.joinpath("brand").iterdir():
        (out / item.name).write_bytes(item.read_bytes())
    if not fragment:
        (out / "404.html").write_bytes(static.joinpath("404.html").read_bytes())
    return path
