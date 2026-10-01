"""Web API and UI.

    pip install -e ".[web]"
    cloudarchie serve            # http://127.0.0.1:8000

The browser sends a YAML spec; the server validates it with the same models as the CLI and
returns the diagram, the explanation and structured data for every component, so the UI can
show exactly why each service was chosen. Payloads are built in payloads.py, which the
static site export reuses.
"""

from __future__ import annotations

from importlib import resources
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from cloudarchie import __version__, catalog, payloads
from cloudarchie.icons import IconLibrary, icon_dir_from_env

MAX_SPEC_BYTES = 100_000


class DesignRequest(BaseModel):
    spec_yaml: str = Field(max_length=MAX_SPEC_BYTES)
    provider: str = "aws"


def _icon_libraries() -> dict[str, IconLibrary]:
    libraries = {}
    for provider in catalog.providers():
        try:
            libraries[provider] = IconLibrary(icon_dir_from_env(provider))
        except FileNotFoundError:
            libraries[provider] = IconLibrary(None)
    return libraries


def create_app() -> FastAPI:
    app = FastAPI(title="CloudArchie", version=__version__)
    icons = _icon_libraries()
    static = resources.files("cloudarchie").joinpath("static")

    @app.get("/api/meta")
    def meta() -> dict[str, Any]:
        return payloads.meta_payload(icons)

    @app.get("/api/catalog")
    def service_catalog() -> dict[str, Any]:
        return payloads.catalog_payload()

    @app.get("/api/patterns")
    def patterns() -> list[dict[str, Any]]:
        return payloads.patterns_payload()

    @app.get("/api/patterns/{name}")
    def pattern(name: str) -> dict[str, str]:
        body = payloads.pattern_payload(name)
        if body is None:
            raise HTTPException(404, f"unknown pattern {name!r}")
        return body

    @app.post("/api/design")
    def design(req: DesignRequest):
        status, body = payloads.design_payload(req.spec_yaml, req.provider, icons.get(req.provider))
        return body if status == 200 else JSONResponse(body, status_code=status)

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return static.joinpath("index.html").read_text(encoding="utf-8")

    app.mount("/static", StaticFiles(directory=str(static)), name="static")
    return app


def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    import uvicorn

    uvicorn.run(create_app(), host=host, port=port)
