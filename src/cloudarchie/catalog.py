"""Loads the versioned YAML data that drives CloudArchie (capabilities, regions, mappings,
patterns). Everything an architect reviews lives in data/, not in code."""

from __future__ import annotations

from functools import cache
from importlib import resources
from typing import Any

import yaml

TIERS = ("external", "edge", "entry", "compute", "integration", "data", "platform")


def _data_file(*parts: str):
    return resources.files("cloudarchie").joinpath("data", *parts)


def _load_yaml(*parts: str) -> Any:
    return yaml.safe_load(_data_file(*parts).read_text(encoding="utf-8"))


@cache
def capabilities() -> dict[str, dict[str, Any]]:
    caps = _load_yaml("capabilities.yaml")
    for name, cap in caps.items():
        if cap.get("tier") not in TIERS:
            raise ValueError(f"capability {name!r} has unknown tier {cap.get('tier')!r}")
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
