"""Derives the build-and-deploy toolchain from the runtime architecture.

This is deterministic on purpose: the same runtime design always gets the same toolchain,
whether a person, the rule-based planner or an AI agent produced it. The rules are simple
and visible:

- every design gets source control, a CI build, a release pipeline and infrastructure code;
- container workloads add a container registry between build and release;
- Kubernetes workloads fed by a queue, stream or event bus (an edge from the source to the
  cluster) get event-driven autoscaling (KEDA), so workers scale with the backlog.
"""

from __future__ import annotations

from clarchy.spec import ArchitectureSpec, Component, Edge

CONTAINER_CAPS = {"container-service", "kubernetes"}
EVENT_SOURCES = ("message-queue", "stream", "event-bus")


def _unique_id(wanted: str, taken: set[str]) -> str:
    candidate, n = wanted, 2
    while candidate in taken:
        candidate = f"{wanted}-{n}"
        n += 1
    taken.add(candidate)
    return candidate


def has_delivery(spec: ArchitectureSpec) -> bool:
    return any(c.tier == "delivery" for c in spec.components)


def add_delivery(spec: ArchitectureSpec) -> ArchitectureSpec:
    """Returns a copy of `spec` with the toolchain added. Specs that already describe a
    toolchain (any delivery-tier component) are returned unchanged."""
    if has_delivery(spec):
        return spec

    runtime = [c for c in spec.components if c.tier not in ("external", "delivery")]
    caps = {c.capability for c in runtime}
    taken = {c.id for c in spec.components}
    uses_containers = bool(caps & CONTAINER_CAPS)
    uses_functions = "serverless-function" in caps
    uses_kubernetes = "kubernetes" in caps

    if uses_containers and uses_functions:
        packaging = "packages the services as container images and the functions as bundles"
    elif uses_containers:
        packaging = "packages the app as a container image"
    elif uses_functions:
        packaging = "packages the functions"
    else:
        packaging = "packages the release"

    repo = _unique_id("repo", taken)
    build = _unique_id("build", taken)
    deploy = _unique_id("deploy", taken)
    infra = _unique_id("infra-code", taken)

    components = [
        Component(
            id=repo,
            capability="source-control",
            label="App and infrastructure code",
            rationale=(
                "Every change starts as a reviewed commit; the same repository holds the "
                "application and its infrastructure code."
            ),
        ),
        Component(
            id=build,
            capability="ci-build",
            label="Build and test",
            rationale=f"Builds and tests each commit, then {packaging}.",
        ),
    ]
    edges = [Edge(source=repo, target=build, label="push")]

    if uses_containers:
        registry = _unique_id("registry", taken)
        components.append(
            Component(
                id=registry,
                capability="container-registry",
                label="Container images",
                rationale=(
                    "Keeps versioned, scanned images so every environment runs exactly "
                    "what was tested."
                ),
            )
        )
        edges += [
            Edge(source=build, target=registry, label="image"),
            Edge(source=registry, target=deploy),
        ]
    else:
        edges.append(Edge(source=build, target=deploy, label="artifact"))

    components += [
        Component(
            id=deploy,
            capability="cd-deploy",
            label="GitOps release" if uses_kubernetes else "Release pipeline",
            rationale=(
                "Rolls new versions out to the cluster from Git, with health checks and "
                "automatic rollback."
                if uses_kubernetes
                else "Promotes each build through test and production with approvals and rollback."
            ),
        ),
        Component(
            id=infra,
            capability="iac",
            label="Infrastructure as code",
            rationale=(
                "Creates and updates the cloud resources from versioned templates, so "
                "every environment is reproducible."
            ),
        ),
    ]
    edges.append(Edge(source=deploy, target=infra, label="applies"))

    has_autoscaler = "event-autoscaling" in caps
    if uses_kubernetes and not has_autoscaler:
        # Only queues, streams and buses that feed a cluster, and only the clusters they
        # feed: a stream that lands in a data lake has nothing to do with pod counts.
        cluster_ids = {c.id for c in runtime if c.capability == "kubernetes"}
        source_caps = {c.id: c.capability for c in runtime}
        feeds = [
            e
            for e in spec.edges
            if source_caps.get(e.source) in EVENT_SOURCES and e.target in cluster_ids
        ]
        sources = [c for c in runtime if c.id in {e.source for e in feeds}]
        clusters = [c for c in runtime if c.id in {e.target for e in feeds}]
        if sources:
            scaler = _unique_id("autoscaler", taken)
            components.append(
                Component(
                    id=scaler,
                    capability="event-autoscaling",
                    label="Scale on backlog",
                    rationale=(
                        "Adds or removes workers as the backlog grows or shrinks, down to "
                        "zero when idle."
                    ),
                )
            )
            edges += [Edge(source=s.id, target=scaler, label="backlog") for s in sources]
            edges += [Edge(source=scaler, target=k.id, label="scales") for k in clusters]

    # Re-validate the whole graph rather than trusting a shallow copy.
    data = spec.model_dump(by_alias=True, exclude_none=True)
    data["components"] = [c.model_dump(exclude_none=True) for c in [*spec.components, *components]]
    data["edges"] = [e.model_dump(by_alias=True, exclude_none=True) for e in [*spec.edges, *edges]]
    return ArchitectureSpec.model_validate(data)
