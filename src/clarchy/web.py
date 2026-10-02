"""Web API and UI.

    pip install -e ".[web,agent,ingest]"
    clarchy serve            # http://127.0.0.1:8000

Pages: /, /examples/, /examples/<id>/, /services/, /pricing/, /how-to/, /blog/, /about/,
/privacy/ and /terms/ (site.py), with their files under /static/.

Endpoints:
  GET  /api/meta            providers, capabilities, regions, the planning engine in use
  GET  /api/samples         example requirements documents
  GET  /api/blog            blog posts, rendered
  POST /api/plan            upload or text -> Server-Sent Events stream of the pipeline
  POST /api/design          spec YAML + provider -> diagram, explanation, components
  GET  /api/patterns[/id]   reference architectures
  GET  /api/catalog         equivalent services across providers

Planning uses Claude when configured (see planner/llm.py) and the rule-based planner
otherwise. Set CLARCHY_CORS_ORIGINS (comma-separated) to let a front end hosted
elsewhere, such as GitHub Pages, call this API.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from importlib import resources
from typing import Annotated, Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from clarchy import __version__, catalog, payloads, site
from clarchy.icons import IconLibrary, bundled_library, icon_library
from clarchy.ingest import MAX_UPLOAD_BYTES, IngestError, from_text, read_document

MAX_SPEC_BYTES = 100_000
HEARTBEAT_SECONDS = 15
log = logging.getLogger("clarchy.web")


class DesignRequest(BaseModel):
    spec_yaml: str = Field(max_length=MAX_SPEC_BYTES)
    provider: str = "aws"


def _icon_libraries() -> dict[str, IconLibrary]:
    libraries = {}
    for provider in catalog.providers():
        try:
            libraries[provider] = icon_library(provider)
        except FileNotFoundError:
            libraries[provider] = bundled_library(provider)
    return libraries


def _engine() -> tuple[Any, dict[str, Any]]:
    """The configured model (or None) and a description for the UI."""
    try:
        from clarchy.planner.llm import LLMError, llm_from_env
    except ImportError:
        return None, {"mode": "rules", "reason": "AI packages not installed"}
    try:
        llm = llm_from_env()
    except (LLMError, ImportError) as exc:
        return None, {"mode": "rules", "reason": str(exc)}
    if llm is None:
        return None, {"mode": "rules", "reason": "no model configured"}
    return llm, {"mode": "ai", "model": llm.model, "label": llm.label}


def _sse(event: dict[str, Any]) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


def _page_route(page: site.Page, content: site.Content, shell: site.Shell):
    rendered: list[str] = []

    def show() -> str:
        if not rendered:
            rendered.append(site.render(page, content, shell))
        return rendered[0]

    return show


def create_app() -> FastAPI:
    app = FastAPI(title="Clarchy", version=__version__)
    icons = _icon_libraries()
    llm, engine = _engine()
    static = resources.files("clarchy").joinpath("static")

    origins = [
        o.strip() for o in os.environ.get("CLARCHY_CORS_ORIGINS", "").split(",") if o.strip()
    ]
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_methods=["GET", "POST"],
            allow_headers=["*"],
        )

    @app.get("/api/meta")
    def meta() -> dict[str, Any]:
        return payloads.meta_payload(icons, engine)

    @app.get("/api/samples")
    def samples() -> list[dict[str, str]]:
        return payloads.samples_payload()

    @app.get("/api/blog")
    def blog_posts() -> list[dict[str, Any]]:
        from clarchy import blog

        return blog.posts()

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

    @app.post("/api/plan")
    async def plan(
        text: Annotated[str | None, Form()] = None,
        mode: Annotated[str, Form()] = "auto",
        region: Annotated[str | None, Form()] = None,
        answers: Annotated[str | None, Form()] = None,
        file: Annotated[UploadFile | None, File()] = None,
    ):
        from clarchy.planner import PlanError, PlanOptions, run_plan
        from clarchy.planner.answers import AnswerError, parse_answers

        if mode not in ("auto", "ai", "rules"):
            return JSONResponse(
                {"errors": [{"where": "mode", "message": "use auto, ai or rules"}]}, 422
            )
        if region and region not in catalog.regions():
            return JSONResponse({"errors": [{"where": "region", "message": "unknown region"}]}, 422)
        try:
            answered = parse_answers(answers)
        except AnswerError as exc:
            return JSONResponse({"errors": [{"where": "answers", "message": str(exc)}]}, 422)
        try:
            if file is not None and file.filename:
                data = await file.read(MAX_UPLOAD_BYTES + 1)
                doc = read_document(data, file.filename)
            else:
                doc = from_text(text or "")
        except IngestError as exc:
            return JSONResponse({"errors": [{"where": "document", "message": str(exc)}]}, 422)

        queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()

        async def run() -> None:
            try:
                await run_plan(
                    doc,
                    PlanOptions(mode=mode, region=region or None, answers=answered),
                    llm=llm,
                    emit=queue.put,
                )
            except PlanError as exc:
                await queue.put({"type": "error", "message": str(exc)})
            except Exception:  # report, don't hang the stream; details stay in the server log
                log.exception("planning failed")
                await queue.put(
                    {"type": "error", "message": "Planning failed unexpectedly. Please try again."}
                )
            finally:
                await queue.put(None)

        async def stream():
            task = asyncio.create_task(run())
            try:
                while True:
                    try:
                        event = await asyncio.wait_for(queue.get(), HEARTBEAT_SECONDS)
                    except TimeoutError:
                        yield ": still working\n\n"
                        continue
                    if event is None:
                        break
                    yield _sse(event)
            finally:
                if not task.done():
                    task.cancel()

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # The pages, each at its own address, rendered from static/index.html (site.py).
    shell = site.Shell(
        mode="server", style='<link rel="stylesheet" href="/static/app.css">', root=None
    )
    content = site.content(payloads.meta_payload(icons, engine))
    for page in site.pages(content):
        app.add_api_route(
            page.path,
            _page_route(page, content, shell),
            methods=["GET"],
            response_class=HTMLResponse,
            include_in_schema=False,
        )

    app.mount("/static", StaticFiles(directory=str(static)), name="static")
    return app


def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    import uvicorn

    uvicorn.run(create_app(), host=host, port=port)
