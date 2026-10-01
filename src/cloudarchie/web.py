"""Web API and UI.

    pip install -e ".[web]"
    cloudarchie serve            # http://127.0.0.1:8000

The browser sends a YAML spec; the server validates it with the same models as the CLI and
returns the diagram, the explanation and structured data for every component, so the UI can
show exactly why each service was chosen.
"""

from __future__ import annotations

from importlib import resources
from typing import Any

import yaml
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError

from cloudarchie import __version__, catalog
from cloudarchie.explain import explain_markdown
from cloudarchie.icons import IconLibrary, icon_dir_from_env
from cloudarchie.mapping import MappingError, map_to_provider, service_choice
from cloudarchie.render import render_svg
from cloudarchie.spec import load_pattern, load_spec

MAX_SPEC_BYTES = 100_000


class DesignRequest(BaseModel):
    spec_yaml: str = Field(max_length=MAX_SPEC_BYTES)
    provider: str = "aws"


def _problem(errors: list[dict[str, str]], status: int = 422) -> JSONResponse:
    return JSONResponse({"errors": errors}, status_code=status)


def _validation_errors(exc: ValidationError) -> list[dict[str, str]]:
    out = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err["loc"])
        message = err["msg"].removeprefix("Value error, ")
        out.append({"where": loc or "spec", "message": message})
    return out


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

    def provider_info(provider: str) -> dict[str, Any]:
        meta = catalog.provider_mapping(provider)["provider"]
        return {
            "id": provider,
            "name": meta["name"],
            "kind": meta["kind"],
            "reviewed": bool(meta.get("reviewed", False)),
            "enabled": True,
        }

    @app.get("/api/meta")
    def meta() -> dict[str, Any]:
        return {
            "version": __version__,
            "providers": [provider_info(p) for p in catalog.providers_in_display_order()],
            "official_icons": {p: lib.root is not None for p, lib in icons.items()},
            "capabilities": {
                name: {"tier": cap["tier"], "description": cap["description"]}
                for name, cap in catalog.capabilities().items()
            },
            "regions": {k: v["label"] for k, v in catalog.regions().items()},
        }

    @app.get("/api/catalog")
    def service_catalog() -> dict[str, Any]:
        """Every capability with its equivalent service on each provider."""
        providers = catalog.providers_in_display_order()
        capabilities = []
        for name, cap in catalog.capabilities().items():
            if cap["tier"] == "external":
                continue
            services = {}
            for provider in providers:
                choice = service_choice(provider, name)
                services[provider] = {
                    "service": choice.service,
                    "short": choice.short,
                    "fidelity": choice.fidelity,
                    "note": choice.note.strip() if choice.note else None,
                    "alternatives": list(choice.alternatives),
                    "docs": choice.docs,
                }
            capabilities.append(
                {
                    "id": name,
                    "tier": cap["tier"],
                    "description": cap["description"],
                    "services": services,
                }
            )
        return {
            "providers": [provider_info(p) for p in providers],
            "capabilities": capabilities,
        }

    @app.get("/api/patterns")
    def patterns() -> list[dict[str, Any]]:
        out = []
        for name in catalog.pattern_names():
            spec = load_pattern(name)
            out.append({"id": name, "name": spec.name, "summary": spec.summary})
        return out

    @app.get("/api/patterns/{name}")
    def pattern(name: str) -> dict[str, str]:
        if name not in catalog.pattern_names():
            raise HTTPException(404, f"unknown pattern {name!r}")
        return {"id": name, "spec_yaml": catalog.pattern_text(name)}

    @app.post("/api/design")
    def design(req: DesignRequest):
        if req.provider not in catalog.providers():
            return _problem(
                [{"where": "provider", "message": f"{req.provider} is not available yet"}]
            )
        try:
            data = yaml.safe_load(req.spec_yaml)
        except yaml.YAMLError as exc:
            mark = getattr(exc, "problem_mark", None)
            where = f"line {mark.line + 1}" if mark else "yaml"
            return _problem([{"where": where, "message": f"YAML syntax: {exc}"}])
        if not isinstance(data, dict):
            return _problem([{"where": "spec", "message": "the spec must be a YAML mapping"}])
        try:
            arch = map_to_provider(load_spec(data), req.provider)
        except ValidationError as exc:
            return _problem(_validation_errors(exc))
        except MappingError as exc:
            return _problem([{"where": "mapping", "message": str(exc)}])

        spec = arch.spec
        components = []
        for m in arch.components:
            comp, choice = m.component, m.choice
            cap = catalog.capabilities()[comp.capability]
            components.append(
                {
                    "id": comp.id,
                    "label": comp.display_label,
                    "capability": comp.capability,
                    "capability_description": cap["description"],
                    "tier": comp.tier,
                    "rationale": comp.rationale,
                    "sizing": comp.sizing,
                    "service": choice.service if choice else None,
                    "fidelity": choice.fidelity if choice else None,
                    "note": choice.note.strip() if choice and choice.note else None,
                    "alternatives": list(choice.alternatives) if choice else [],
                    "docs": choice.docs if choice else None,
                    "connections": [
                        {"to": e.target, "label": e.label}
                        for e in spec.edges
                        if e.source == comp.id
                    ]
                    + [
                        {"from": e.source, "label": e.label}
                        for e in spec.edges
                        if e.target == comp.id
                    ],
                }
            )
        return {
            "name": spec.name,
            "summary": spec.summary,
            "provider": arch.provider,
            "provider_name": arch.provider_name,
            "region": {"code": arch.region_code, "label": arch.region_label},
            "requirements": spec.requirements.model_dump(),
            "components": components,
            "svg": render_svg(arch, icons[req.provider]),
            "explanation_md": explain_markdown(arch),
            "official_icons": icons[req.provider].root is not None,
            "reviewed": arch.reviewed,
            "kind": arch.kind,
        }

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return static.joinpath("index.html").read_text(encoding="utf-8")

    app.mount("/static", StaticFiles(directory=str(static)), name="static")
    return app


def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    import uvicorn

    uvicorn.run(create_app(), host=host, port=port)
