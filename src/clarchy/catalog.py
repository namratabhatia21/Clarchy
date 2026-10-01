"""Loads the versioned YAML data that drives Clarchy (capabilities, regions, mappings,
patterns). Everything an architect reviews lives in data/, not in code."""

from __future__ import annotations

from functools import cache
from importlib import resources
from typing import Any

import yaml

TIERS = ("external", "delivery", "edge", "entry", "compute", "integration", "data", "platform")

# Lifecycle stages, in order, with the label shown in the bill of services.
STAGES = {
    "code": "Code",
    "build": "Build",
    "ship": "Ship",
    "serve": "Serve",
    "run": "Run",
    "integrate": "Integrate",
    "store": "Store",
    "operate": "Operate",
}

# Design families; each provider theme assigns them colours.
CATEGORIES = (
    "external",
    "networking",
    "security",
    "compute",
    "containers",
    "ai",
    "integration",
    "analytics",
    "database",
    "storage",
    "devtools",
    "management",
)


def _data_file(*parts: str):
    return resources.files("clarchy").joinpath("data", *parts)


data_path = _data_file  # public: other modules read their own data files through this


def _load_yaml(*parts: str) -> Any:
    return yaml.safe_load(_data_file(*parts).read_text(encoding="utf-8"))


@cache
def capabilities() -> dict[str, dict[str, Any]]:
    caps = _load_yaml("capabilities.yaml")
    for name, cap in caps.items():
        if cap.get("tier") not in TIERS:
            raise ValueError(f"capability {name!r} has unknown tier {cap.get('tier')!r}")
        if cap.get("category") not in CATEGORIES:
            raise ValueError(f"capability {name!r} has unknown category {cap.get('category')!r}")
        if cap["tier"] != "external" and cap.get("stage") not in STAGES:
            raise ValueError(f"capability {name!r} has unknown stage {cap.get('stage')!r}")
    return caps


@cache
def regions() -> dict[str, dict[str, str]]:
    return _load_yaml("regions.yaml")


def providers() -> list[str]:
    return sorted(
        p.name.removesuffix(".yaml")
        for p in _data_file("mappings").iterdir()
        if p.name.endswith(".yaml")
    )


PROVIDER_KINDS = ("cloud", "self-hosted")


@cache
def provider_mapping(provider: str) -> dict[str, Any]:
    if provider not in providers():
        raise KeyError(f"unknown provider {provider!r}; available: {', '.join(providers())}")
    data = _load_yaml("mappings", f"{provider}.yaml")
    if data["provider"].get("kind") not in PROVIDER_KINDS:
        raise ValueError(f"{provider}: provider.kind must be one of {PROVIDER_KINDS}")
    return data


def providers_in_display_order() -> list[str]:
    """Clouds first (AWS, then alphabetical), self-hosted last."""
    order = {"aws": 0}
    return sorted(
        providers(),
        key=lambda p: (
            provider_mapping(p)["provider"]["kind"] != "cloud",
            order.get(p, 1),
            provider_mapping(p)["provider"]["name"],
        ),
    )


def samples() -> list[tuple[str, str, str]]:
    """(id, title, text) of the example requirements documents."""
    out = []
    folder = _data_file("samples")
    for entry in sorted(folder.iterdir(), key=lambda p: p.name):
        if entry.name.endswith(".md"):
            text = entry.read_text(encoding="utf-8")
            title = text.splitlines()[0].lstrip("#").strip() if text else entry.name
            out.append((entry.name.removesuffix(".md"), title, text))
    return out


def pattern_names() -> list[str]:
    return sorted(
        p.name.removesuffix(".yaml")
        for p in _data_file("patterns").iterdir()
        if p.name.endswith(".yaml")
    )


def pattern_text(name: str) -> str:
    if name not in pattern_names():
        raise KeyError(f"unknown pattern {name!r}; available: {', '.join(pattern_names())}")
    return _data_file("patterns", f"{name}.yaml").read_text(encoding="utf-8")
