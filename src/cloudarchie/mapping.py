"""Maps a cloud-neutral spec onto one provider's services."""

from __future__ import annotations

from dataclasses import dataclass, field

from cloudarchie import catalog
from cloudarchie.spec import ArchitectureSpec, Component

FIDELITY_LEVELS = ("exact", "close", "partial")


class MappingError(ValueError):
    pass


@dataclass(frozen=True)
class ServiceChoice:
    service: str
    short: str
    fidelity: str
    icon: str | None = None
    note: str | None = None
    docs: str | None = None
    alternatives: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class MappedComponent:
    component: Component
    choice: ServiceChoice | None  # None for external components such as clients


@dataclass(frozen=True)
class ProviderArchitecture:
    provider: str
    provider_name: str
    cloud_label: str
    region_code: str
    region_label: str
    spec: ArchitectureSpec
    components: tuple[MappedComponent, ...]

    def by_id(self, component_id: str) -> MappedComponent:
        return next(m for m in self.components if m.component.id == component_id)


def service_choice(provider: str, capability: str) -> ServiceChoice:
    services = catalog.provider_mapping(provider)["services"]
    if capability not in services:
        raise MappingError(f"{provider} has no mapping for capability {capability!r}")
    raw = services[capability]
    if raw["fidelity"] not in FIDELITY_LEVELS:
        raise MappingError(f"{provider}/{capability}: invalid fidelity {raw['fidelity']!r}")
    return ServiceChoice(
        service=raw["service"],
        short=raw["short"],
        fidelity=raw["fidelity"],
        icon=raw.get("icon"),
        note=raw.get("note"),
        docs=raw.get("docs"),
        alternatives=tuple(raw.get("alternatives", ())),
    )


def map_to_provider(spec: ArchitectureSpec, provider: str) -> ProviderArchitecture:
    meta = catalog.provider_mapping(provider)["provider"]
    region = catalog.regions()[spec.requirements.region]
    if provider not in region:
        raise MappingError(f"region {spec.requirements.region!r} is not mapped for {provider}")

    mapped, missing = [], []
    for comp in spec.components:
        if comp.tier == "external":
            mapped.append(MappedComponent(comp, None))
            continue
        try:
            mapped.append(MappedComponent(comp, service_choice(provider, comp.capability)))
        except MappingError:
            missing.append(comp.capability)
    if missing:
        raise MappingError(f"{provider} has no mapping for: {', '.join(sorted(set(missing)))}")

    return ProviderArchitecture(
        provider=provider,
        provider_name=meta["name"],
        cloud_label=meta["cloud_label"],
        region_code=region[provider],
        region_label=region["label"],
        spec=spec,
        components=tuple(mapped),
    )
