"""The cloud-neutral architecture spec.

A spec describes *capabilities* (object-storage, relational-db, ...) with sizing and a
rationale, never provider services. Providers are applied later by mapping.py, which is
what makes like-for-like comparison across clouds possible.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from clarchy import catalog

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
    developers: int | None = Field(
        default=None, ge=0, description="Engineers who build and run it (for per-seat tools)"
    )
    retention_years: float | None = Field(
        default=None, ge=0, description="How long records must be kept"
    )

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
    # Quotes from the requirements that led to this component (planner output).
    evidence: list[str] = Field(default_factory=list)

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
    def stage(self) -> str | None:
        return catalog.capabilities()[self.capability].get("stage")

    @property
    def category(self) -> str:
        return catalog.capabilities()[self.capability]["category"]

    @property
    def display_label(self) -> str:
        return self.label or self.id.replace("-", " ").capitalize()


class Edge(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    source: str = Field(alias="from")
    target: str = Field(alias="to")
    label: str | None = None


class WorkflowStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    components: list[str] = Field(default_factory=list)


class Workflow(BaseModel):
    """An ordered walk through the architecture, e.g. how a request or a release flows."""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    kind: Literal["request", "async", "data", "delivery", "other"] = "other"
    steps: list[WorkflowStep] = Field(min_length=1)

    @field_validator("id")
    @classmethod
    def _valid_id(cls, value: str) -> str:
        if not _ID.match(value):
            raise ValueError(f"workflow id {value!r} must be lowercase letters, digits, '-'")
        return value


class Provenance(BaseModel):
    """Who or what produced the spec: a person, the rule-based planner or an AI model."""

    model_config = ConfigDict(extra="forbid")

    mode: Literal["manual", "rules", "ai"] = "manual"
    model: str | None = None
    source: str | None = None


class ArchitectureSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    summary: str | None = None
    requirements: Requirements = Field(default_factory=Requirements)
    assumptions: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    components: list[Component]
    edges: list[Edge] = Field(default_factory=list)
    workflows: list[Workflow] = Field(default_factory=list)
    provenance: Provenance | None = None

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
        workflow_ids = [w.id for w in self.workflows]
        dupes = sorted({i for i in workflow_ids if workflow_ids.count(i) > 1})
        if dupes:
            raise ValueError(f"duplicate workflow ids: {', '.join(dupes)}")
        for wf in self.workflows:
            for n, step in enumerate(wf.steps, start=1):
                unknown = [c for c in step.components if c not in known]
                if unknown:
                    raise ValueError(
                        f"workflow {wf.id} step {n} names unknown components: {', '.join(unknown)}"
                    )
        return self

    def component(self, component_id: str) -> Component:
        return next(c for c in self.components if c.id == component_id)


def spec_to_yaml(spec: ArchitectureSpec) -> str:
    """Compact YAML: defaults are left out, except the region and availability target,
    which a reader should always see."""
    data = spec.model_dump(by_alias=True, exclude_none=True, exclude_defaults=True)
    requirements = data.setdefault("requirements", {})
    requirements["region"] = spec.requirements.region
    requirements["availability_target"] = spec.requirements.availability_target
    ordered = {key: data[key] for key in ("name", "summary", "requirements") if key in data}
    ordered.update({k: v for k, v in data.items() if k not in ordered})
    return yaml.safe_dump(ordered, sort_keys=False, allow_unicode=True, width=100)


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
