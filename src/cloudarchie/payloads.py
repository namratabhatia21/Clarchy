"""JSON payloads shared by the web API (web.py) and the static site export (export.py).

Keeping them here, free of any web framework, means the hosted demo shows exactly what the
live server would return.
"""

from __future__ import annotations

from typing import Any

import yaml
from pydantic import ValidationError

from cloudarchie import __version__, catalog, pricing
from cloudarchie.explain import explain_markdown
from cloudarchie.icons import IconLibrary
from cloudarchie.mapping import MappingError, map_to_provider, service_choice
from cloudarchie.render import render_svg
from cloudarchie.spec import load_pattern, load_spec

Errors = list[dict[str, str]]


def provider_info(provider: str) -> dict[str, Any]:
    meta = catalog.provider_mapping(provider)["provider"]
    return {
        "id": provider,
        "name": meta["name"],
        "kind": meta["kind"],
        "reviewed": bool(meta.get("reviewed", False)),
        "enabled": True,
    }


def meta_payload(
    icons: dict[str, IconLibrary], engine: dict[str, Any] | None = None
) -> dict[str, Any]:
    return {
        "version": __version__,
        "providers": [provider_info(p) for p in catalog.providers_in_display_order()],
        "official_icons": {p: lib.root is not None for p, lib in icons.items()},
        "capabilities": {
            name: {
                "tier": cap["tier"],
                "stage": cap.get("stage"),
                "category": cap["category"],
                "description": cap["description"],
            }
            for name, cap in catalog.capabilities().items()
        },
        "stages": catalog.STAGES,
        "regions": {k: v["label"] for k, v in catalog.regions().items()},
        # How /api/plan works on this server: "ai" (Claude), "rules" or "none" (static site).
        "engine": engine or {"mode": "none"},
    }


def samples_payload() -> list[dict[str, str]]:
    """Example requirements documents for the "try a sample" buttons."""
    return [
        {"id": sample_id, "title": title, "text": text}
        for sample_id, title, text in catalog.samples()
    ]


def catalog_payload() -> dict[str, Any]:
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
                "stage": cap.get("stage"),
                "category": cap["category"],
                "description": cap["description"],
                "services": services,
            }
        )
    return {"providers": [provider_info(p) for p in providers], "capabilities": capabilities}


def patterns_payload() -> list[dict[str, Any]]:
    out = []
    for name in catalog.pattern_names():
        spec = load_pattern(name)
        caps = sorted({c.capability for c in spec.components if c.tier != "external"})
        out.append(
            {
                "id": name,
                "name": spec.name,
                "summary": spec.summary,
                "capabilities": caps,
                "components": len(spec.components),
            }
        )
    return out


def pattern_payload(name: str) -> dict[str, str] | None:
    if name not in catalog.pattern_names():
        return None
    return {"id": name, "spec_yaml": catalog.pattern_text(name)}


def _validation_errors(exc: ValidationError) -> Errors:
    out = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err["loc"])
        message = err["msg"].removeprefix("Value error, ")
        out.append({"where": loc or "spec", "message": message})
    return out


def design_payload(
    spec_yaml: str, provider: str, icons: IconLibrary | None = None
) -> tuple[int, dict[str, Any]]:
    """Returns (HTTP status, body). Errors come back as {"errors": [{where, message}]}."""
    if provider not in catalog.providers():
        return 422, {
            "errors": [{"where": "provider", "message": f"{provider} is not available yet"}]
        }
    try:
        data = yaml.safe_load(spec_yaml)
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        where = f"line {mark.line + 1}" if mark else "yaml"
        return 422, {"errors": [{"where": where, "message": f"YAML syntax: {exc}"}]}
    if not isinstance(data, dict):
        return 422, {"errors": [{"where": "spec", "message": "the spec must be a YAML mapping"}]}
    try:
        arch = map_to_provider(load_spec(data), provider)
    except ValidationError as exc:
        return 422, {"errors": _validation_errors(exc)}
    except MappingError as exc:
        return 422, {"errors": [{"where": "mapping", "message": str(exc)}]}

    icons = icons or IconLibrary(None)
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
                "stage": comp.stage,
                "category": comp.category,
                "rationale": comp.rationale,
                "evidence": comp.evidence,
                "sizing": comp.sizing,
                "service": choice.service if choice else None,
                "fidelity": choice.fidelity if choice else None,
                "note": choice.note.strip() if choice and choice.note else None,
                "alternatives": list(choice.alternatives) if choice else [],
                "docs": choice.docs if choice else None,
                "connections": [
                    {"to": e.target, "label": e.label} for e in spec.edges if e.source == comp.id
                ]
                + [{"from": e.source, "label": e.label} for e in spec.edges if e.target == comp.id],
            }
        )
    return 200, {
        "name": spec.name,
        "summary": spec.summary,
        "provider": arch.provider,
        "provider_name": arch.provider_name,
        "region": {"code": arch.region_code, "label": arch.region_label},
        "requirements": spec.requirements.model_dump(),
        "assumptions": spec.assumptions,
        "open_questions": spec.open_questions,
        "provenance": spec.provenance.model_dump() if spec.provenance else None,
        "workflows": [w.model_dump() for w in spec.workflows],
        "components": components,
        "svg": render_svg(arch, icons),
        "explanation_md": explain_markdown(arch),
        "cost": pricing.estimate(arch),
        "official_icons": icons.root is not None,
        "reviewed": arch.reviewed,
        "kind": arch.kind,
    }
