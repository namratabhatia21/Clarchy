"""The cloud-neutral architecture spec.

A spec describes *capabilities* (object-storage, relational-db, ...) with sizing and a
rationale, never provider services. Providers are applied later by mapping.py, which is
what makes like-for-like comparison across clouds possible.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from cloudarchie import catalog

_ID = re.compile(r"^[a-z][a-z0-9-]*$")

# Sizing values stay loosely typed until the cost engine (phase 2) defines a usage
# model per capability. See docs/decisions/0001-cloud-neutral-spec.md.
SizingValue = int | float | str | bool


class Requirements(BaseModel):
    model_config = ConfigDict(extra="forbid")

    users: int | None = Field(default=None, ge=0, description="Monthly active users")
    peak_rps: float | None = Field(default=None, ge=0, description="Peak requests per second")
    data_gb: float | None = Field(default=None, ge=0, description="Stored data today")
    data_growth_gb_per_month: float | None = Field(default=None, ge=0)
    availability_target: str = Field(default="99.9", description="Percent, e.g. 99.9")
    region: str = "us-east"
    compliance: list[str] = Field(default_factory=list)
    monthly_budget_usd: float | None = Field(default=None, ge=0)

    @field_validator("region")
    @classmethod
    def _known_region(cls, value: str) -> str:
        if value not in catalog.regions():
            known = ", ".join(sorted(catalog.regions()))
            raise ValueError(f"unknown region {value!r}; known regions: {known}")
        return value


class Component(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    capability: str
    label: str | None = None
    sizing: dict[str, SizingValue] = Field(default_factory=dict)
    rationale: str | None = None

    @field_validator("id")
    @classmethod
    def _valid_id(cls, value: str) -> str:
        if not _ID.match(value):
            raise ValueError(f"component id {value!r} must be lowercase letters, digits, '-'")
        return value

    @field_validator("capability")
    @classmethod
    def _known_capability(cls, value: str) -> str:
        if value not in catalog.capabilities():
            raise ValueError(f"unknown capability {value!r}")
        return value

    @property
    def tier(self) -> str:
        return catalog.capabilities()[self.capability]["tier"]

    @property
    def display_label(self) -> str:
        return self.label or self.id.replace("-", " ").capitalize()


class Edge(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    source: str = Field(alias="from")
    target: str = Field(alias="to")
    label: str | None = None


class ArchitectureSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    summary: str | None = None
    requirements: Requirements = Field(default_factory=Requirements)
    components: list[Component]
    edges: list[Edge] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_graph(self) -> ArchitectureSpec:
        ids = [c.id for c in self.components]
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        if dupes:
            raise ValueError(f"duplicate component ids: {', '.join(dupes)}")
        known = set(ids)
        for edge in self.edges:
            for end in (edge.source, edge.target):
                if end not in known:
                    raise ValueError(f"edge {edge.source} -> {edge.target}: unknown id {end!r}")
            if edge.source == edge.target:
                raise ValueError(f"edge {edge.source} -> {edge.target} is a self-loop")
        return self

    def component(self, component_id: str) -> Component:
        return next(c for c in self.components if c.id == component_id)


def load_spec(data: dict[str, Any]) -> ArchitectureSpec:
    return ArchitectureSpec.model_validate(data)


def load_spec_text(text: str) -> ArchitectureSpec:
    return load_spec(yaml.safe_load(text))


def load_spec_file(path: str | Path) -> ArchitectureSpec:
    return load_spec_text(Path(path).read_text(encoding="utf-8"))


def load_pattern(name: str) -> ArchitectureSpec:
    return load_spec_text(catalog.pattern_text(name))


def load_spec_or_pattern(ref: str) -> ArchitectureSpec:
    """`ref` is a pattern name or a path to a YAML spec file."""
    if ref in catalog.pattern_names():
        return load_pattern(ref)
    return load_spec_file(ref)
