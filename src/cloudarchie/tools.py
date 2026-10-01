"""CloudArchie's tools: one implementation for the planning agent and the MCP server.

Every tool takes plain JSON arguments and returns JSON-serialisable data, so it can be
served over MCP (`cloudarchie mcp`), called by the built-in agent, or used from Python.
Tools raise ToolError for problems the caller can fix (unknown id, invalid YAML); the
agent passes that message back to the model as an error result.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import yaml
from pydantic import ValidationError

from cloudarchie import catalog, pricing
from cloudarchie.delivery import add_delivery
from cloudarchie.explain import explain_markdown
from cloudarchie.mapping import MappingError, map_to_provider, service_choice
from cloudarchie.render import render_svg
from cloudarchie.spec import ArchitectureSpec, load_pattern, load_spec, spec_to_yaml


class ToolError(ValueError):
    """A problem the caller can fix; the message is shown to them."""


def _parse_spec(spec_yaml: str) -> ArchitectureSpec:
    try:
        data = yaml.safe_load(spec_yaml)
    except yaml.YAMLError as exc:
        raise ToolError(f"YAML syntax error: {exc}") from exc
    if not isinstance(data, dict):
        raise ToolError("the spec must be a YAML mapping with name, components and edges")
    try:
        return load_spec(data)
    except ValidationError as exc:
        raise ToolError(_format_errors(exc)) from exc


def _validation_errors(exc: ValidationError) -> list[dict[str, str]]:
    out = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err["loc"]) or "spec"
        out.append({"where": loc, "message": err["msg"].removeprefix("Value error, ")})
    return out


def _format_errors(exc: ValidationError) -> str:
    return "; ".join(f"{e['where']}: {e['message']}" for e in _validation_errors(exc))


def _dump(spec: ArchitectureSpec) -> str:
    return spec_to_yaml(spec)


# --- tool functions -----------------------------------------------------------------


def list_capabilities() -> list[dict[str, Any]]:
    """Every capability a design can use, with its tier, lifecycle stage and purpose."""
    return [
        {
            "id": name,
            "tier": cap["tier"],
            "stage": cap.get("stage"),
            "category": cap["category"],
            "description": cap["description"],
        }
        for name, cap in catalog.capabilities().items()
    ]


def list_regions() -> dict[str, str]:
    """Region keys a design can use, with a human-readable label."""
    return {key: value["label"] for key, value in catalog.regions().items()}


def list_patterns() -> list[dict[str, Any]]:
    """Reviewed reference architectures to start a design from."""
    out = []
    for name in catalog.pattern_names():
        spec = load_pattern(name)
        caps = sorted({c.capability for c in spec.components if c.tier != "external"})
        out.append({"id": name, "name": spec.name, "summary": spec.summary, "capabilities": caps})
    return out


def get_pattern(pattern_id: str) -> dict[str, str]:
    """The full YAML spec of one reference architecture."""
    if pattern_id not in catalog.pattern_names():
        raise ToolError(
            f"unknown pattern {pattern_id!r}; available: {', '.join(catalog.pattern_names())}"
        )
    return {"id": pattern_id, "spec_yaml": catalog.pattern_text(pattern_id)}


def search_services(query: str, provider: str) -> list[dict[str, Any]]:
    """Find capabilities and the equivalent service on each provider. `provider` is a
    provider id (aws, azure, gcp, oss) or "all"."""
    providers = catalog.providers_in_display_order()
    if provider != "all":
        if provider not in providers:
            raise ToolError(f"unknown provider {provider!r}; use one of {providers} or 'all'")
        providers = [provider]
    terms = query.lower().split()
    results = []
    for name, cap in catalog.capabilities().items():
        if cap["tier"] == "external":
            continue
        for prov in providers:
            choice = service_choice(prov, name)
            haystack = " ".join(
                [
                    name,
                    name.replace("-", " "),
                    cap["description"],
                    choice.service,
                    *choice.alternatives,
                ]
            ).lower()
            if all(t in haystack for t in terms):
                results.append(
                    {
                        "capability": name,
                        "provider": prov,
                        "service": choice.service,
                        "fidelity": choice.fidelity,
                        "note": choice.note,
                        "alternatives": list(choice.alternatives),
                    }
                )
    return results[:40]


def validate_spec(spec_yaml: str) -> dict[str, Any]:
    """Check a spec against the schema and every provider mapping. Returns errors to fix
    and warnings worth considering."""
    try:
        data = yaml.safe_load(spec_yaml)
    except yaml.YAMLError as exc:
        return {"valid": False, "errors": [{"where": "yaml", "message": str(exc)}], "warnings": []}
    if not isinstance(data, dict):
        return {
            "valid": False,
            "errors": [{"where": "spec", "message": "the spec must be a YAML mapping"}],
            "warnings": [],
        }
    try:
        spec = load_spec(data)
    except ValidationError as exc:
        return {"valid": False, "errors": _validation_errors(exc), "warnings": []}
    errors = []
    for prov in catalog.providers():
        try:
            map_to_provider(spec, prov)
        except MappingError as exc:
            errors.append({"where": f"mapping.{prov}", "message": str(exc)})
    warnings = []
    for comp in spec.components:
        if comp.tier != "external" and not comp.rationale:
            warnings.append(f"{comp.id}: add a rationale explaining why it is needed")
    connected = {e.source for e in spec.edges} | {e.target for e in spec.edges}
    for comp in spec.components:
        if comp.tier not in ("platform",) and comp.id not in connected:
            warnings.append(f"{comp.id}: not connected to anything")
    if not any(c.capability == "monitoring" for c in spec.components):
        warnings.append("no monitoring component")
    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "components": len(spec.components),
        "edges": len(spec.edges),
    }


def add_delivery_toolchain(spec_yaml: str) -> dict[str, str]:
    """Add the build-and-deploy toolchain (source control, CI, registry, release,
    infrastructure as code and, for Kubernetes queue workers, KEDA) to a spec."""
    return {"spec_yaml": _dump(add_delivery(_parse_spec(spec_yaml)))}


def render_design(spec_yaml: str, provider: str) -> dict[str, str]:
    """Render a spec on one provider: an SVG diagram plus a Markdown explanation."""
    spec = _parse_spec(spec_yaml)
    try:
        arch = map_to_provider(spec, provider)
    except (MappingError, KeyError) as exc:
        raise ToolError(str(exc)) from exc
    return {"svg": render_svg(arch), "explanation_md": explain_markdown(arch)}


def estimate_cost(spec_yaml: str, provider: str) -> dict[str, Any]:
    """Monthly cost of a spec on one provider, with totals for 1 month, 6 months, 1 year and
    3 years on demand and with 1- or 3-year commitments, and the cost of each service."""
    spec = _parse_spec(spec_yaml)
    try:
        arch = map_to_provider(spec, provider)
    except (MappingError, KeyError) as exc:
        raise ToolError(str(exc)) from exc
    cost = pricing.estimate(arch)
    if not cost["available"]:
        return {"available": False, "message": cost["message"]}
    return {
        "available": True,
        "monthly_usd": cost["monthly"],
        "prices": f"{cost['price_region']} list prices as of {cost['as_of']} ({cost['source']})",
        "terms": cost["terms"],
        "services": [
            {
                "component": line["component"],
                "service": line["service"],
                "monthly_usd": line["monthly"],
            }
            for line in sorted(cost["lines"], key=lambda line: -line["monthly"])
        ],
    }


def aws_price_lookup(service: str, search: str) -> list[dict[str, Any]]:
    """Search the latest AWS prices, live from the AWS Price List API, for one service in
    US East (N. Virginia). `service` is an AWS service code such as AWSLambda, AmazonS3,
    AmazonRDS or AmazonDynamoDB; `search` holds words to find in the usage type or
    description, e.g. "gp3 storage" or "requests"."""
    from cloudarchie import aws_prices

    try:
        return aws_prices.lookup(service, search)
    except ValueError as exc:
        raise ToolError(str(exc)) from exc


def draft_architecture(requirements: str) -> dict[str, Any]:
    """Draft a complete design from plain-text requirements with the rule-based planner
    (no AI). Returns the spec YAML and the evidence for each component."""
    from cloudarchie.planner.rules import plan_with_rules  # local import: planner uses tools

    spec = plan_with_rules(requirements, source="text")
    return {"spec_yaml": _dump(spec), "components": len(spec.components)}


@dataclass(frozen=True)
class Tool:
    name: str
    func: Callable[..., Any]
    input_schema: dict[str, Any]

    @property
    def description(self) -> str:
        return " ".join((self.func.__doc__ or "").split())

    def __call__(self, args: dict[str, Any]) -> Any:
        return self.func(**args)


def _schema(**props: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": props,
        "required": list(props),
        "additionalProperties": False,
    }


_STRING = {"type": "string"}
TOOLS: dict[str, Tool] = {
    t.name: t
    for t in (
        Tool("list_capabilities", list_capabilities, _schema()),
        Tool("list_regions", list_regions, _schema()),
        Tool("list_patterns", list_patterns, _schema()),
        Tool("get_pattern", get_pattern, _schema(pattern_id=_STRING)),
        Tool(
            "search_services",
            search_services,
            _schema(
                query=_STRING,
                provider={"type": "string", "enum": [*catalog.providers(), "all"]},
            ),
        ),
        Tool("validate_spec", validate_spec, _schema(spec_yaml=_STRING)),
        Tool("add_delivery_toolchain", add_delivery_toolchain, _schema(spec_yaml=_STRING)),
        Tool(
            "render_design",
            render_design,
            _schema(spec_yaml=_STRING, provider={"type": "string", "enum": catalog.providers()}),
        ),
        Tool(
            "estimate_cost",
            estimate_cost,
            _schema(spec_yaml=_STRING, provider={"type": "string", "enum": catalog.providers()}),
        ),
        Tool("aws_price_lookup", aws_price_lookup, _schema(service=_STRING, search=_STRING)),
        Tool("draft_architecture", draft_architecture, _schema(requirements=_STRING)),
    )
}

# The design agent needs research and validation, not rendering or drafting.
AGENT_TOOL_NAMES = (
    "list_capabilities",
    "list_regions",
    "list_patterns",
    "get_pattern",
    "search_services",
    "validate_spec",
    "estimate_cost",
)
