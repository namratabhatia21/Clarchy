"""Derives step-by-step workflows from an architecture's graph.

Each step reads "Source -> Target: what happens" and names the components it involves, so
the UI can highlight them on the diagram. Workflows written by the AI agent replace these;
the generated ones are the fallback and the rule-based planner's output.

Flows produced, when the design has them:
- "Serving a request": from the users through the front door to compute and data.
- "Background processing" / "Data pipeline": everything the request path hands off.
- "Shipping a change": the build-and-deploy toolchain, ending at the runtime it deploys to.
"""

from __future__ import annotations

from collections import deque

from clarchy.spec import ArchitectureSpec, Component, Edge, Workflow, WorkflowStep

# What happens when work arrives at a component, by the target's capability.
ROLE = {
    "dns": "look up the app's address",
    "cdn": "load the app through the CDN",
    "waf": "filter malicious traffic",
    "load-balancer": "spread requests across healthy instances",
    "api-gateway": "authenticate, throttle and route the call",
    "container-service": "run the business logic",
    "kubernetes": "run the business logic",
    "serverless-function": "run the function",
    "llm-inference": "generate or embed text",
    "agent-orchestration": "plan the steps and call tools",
    "llm-gateway": "check the key and budget, then pick a model",
    "llm-observability": "record the prompt, tool calls, tokens and cost",
    "ai-guardrails": "screen the prompt and the answer",
    "archive-storage": "move records that have aged out",
    "backup": "back up the data",
    "key-management": "decrypt with the managed key",
    "audit-logging": "record who did what",
    "access-governance": "approve and grant access",
    "dev-environment": "open a ready-to-code environment",
    "ai-coding-assistant": "suggest code and review changes",
    "message-queue": "queue the job",
    "event-bus": "publish an event",
    "stream": "append to the event stream",
    "workflow": "start a multi-step workflow",
    "batch-etl": "run the transformations",
    "object-storage": "store or read files",
    "relational-db": "read and write records",
    "key-value-db": "read and write items",
    "cache": "read and refresh cached results",
    "vector-search": "search similar content",
    "data-warehouse": "load data for reporting",
    "event-autoscaling": "report the backlog",
    "identity": "verify the user's sign-in token",
    "secrets": "fetch credentials",
    "monitoring": "send logs and metrics",
    "source-control": "push a reviewed change",
    "ci-build": "build and test the change",
    "container-registry": "publish the tested image",
    "cd-deploy": "start the release",
    "iac": "apply infrastructure changes",
}
# A few transitions read better with their own phrase.
ROLE_FROM = {
    ("cdn", "object-storage"): "serve the site's files",
    ("event-autoscaling", "kubernetes"): "scale the workers",
    ("message-queue", "container-service"): "process the queued jobs",
    ("message-queue", "kubernetes"): "process the queued jobs",
    ("message-queue", "serverless-function"): "process the queued jobs",
    ("message-queue", "workflow"): "process the queued jobs",
    ("stream", "serverless-function"): "process events from the stream",
}

# Edge labels that already say what happens get their own phrasing.
LABEL_PHRASE = {
    "push": "start a build on every push",
    "image": "publish the tested image",
    "artifact": "hand over the tested package",
    "applies": "apply infrastructure changes",
    "store": "store the upload",
    "retrieve": "retrieve relevant passages",
    "generate": "generate the answer",
    "embed": "create embeddings",
    "index": "index the new chunks",
    "on upload": "start when a document is uploaded",
    "verify token": "verify the user's sign-in token",
    "job done": "announce that the job is done",
    "backlog": "report the backlog",
    "scales": "scale the workers",
    "load": "load curated data",
    "raw": "land the raw events",
    "read + write": "read and write curated data",
    "events": "send events",
    "/api/*": "forward API calls",
    "enqueue": "queue the job",
    "publish": "publish an event",
    "run": "hand the request to the agent",
    "screen": "screen the prompt and the answer",
    "age out": "move records that have aged out to the archive",
    "commit": "commit and push the change",
    "suggest code": "suggest code and review the change",
    "call tools": "call tools that look up or change data",
    "checkpoint": "save the agent's progress and the conversation",
    "prompt": "send the prompt through the gateway",
    "route": "call the chosen model, falling back to another if it fails",
}

DATA_CAPS = {"stream", "batch-etl", "data-warehouse"}
# Calls a request waits for, so the request flow follows them even outside compute.
SYNC_CAPS = {"llm-gateway", "llm-inference", "ai-guardrails"}
ASYNC_CAPS = {"message-queue", "event-bus", "workflow"}
# What a release pipeline rolls out to.
RUNTIME_COMPUTE = {
    "container-service",
    "kubernetes",
    "serverless-function",
    "batch-etl",
    "agent-orchestration",
    "llm-gateway",
}


def _phrase(src: Component, dst: Component, label: str | None) -> str:
    if label and label.lower() in LABEL_PHRASE:
        return LABEL_PHRASE[label.lower()]
    role = ROLE_FROM.get((src.capability, dst.capability)) or ROLE.get(dst.capability, "use it")
    return f"{role} ({label})" if label else role


def _step(by_id: dict[str, Component], edge: Edge) -> WorkflowStep:
    src, dst = by_id[edge.source], by_id[edge.target]
    return WorkflowStep(
        text=f"{src.display_label} → {dst.display_label}: {_phrase(src, dst, edge.label)}",
        components=[src.id, dst.id],
    )


def _walk(
    starts: list[str],
    edges_from: dict[str, list[Edge]],
    used: set[int],
    edge_index: dict[int, int],
    expand,
) -> list[Edge]:
    """Breadth-first walk from `starts`, returning unused edges in visiting order."""
    seen, queue, out = set(starts), deque(starts), []
    while queue:
        node = queue.popleft()
        for edge in edges_from.get(node, []):
            key = edge_index[id(edge)]
            if key in used:
                continue
            used.add(key)
            out.append(edge)
            if edge.target not in seen and expand(edge.target):
                seen.add(edge.target)
                queue.append(edge.target)
    return out


def generate_workflows(spec: ArchitectureSpec) -> list[Workflow]:
    by_id = {c.id: c for c in spec.components}
    tier = {c.id: c.tier for c in spec.components}
    edges_from: dict[str, list[Edge]] = {}
    for edge in spec.edges:
        edges_from.setdefault(edge.source, []).append(edge)
    edge_index = {id(e): n for n, e in enumerate(spec.edges)}
    used: set[int] = set()
    # Delivery edges are narrated only in the delivery flow.
    for edge in spec.edges:
        if tier[edge.source] == "delivery" or tier[edge.target] == "delivery":
            used.add(edge_index[id(edge)])

    workflows: list[Workflow] = []

    # 1. Serving a request: expand through the front door into compute and data, but
    #    stop at integration nodes (their work is the next flow) and at platform services.
    clients = [c.id for c in spec.components if c.tier == "external"]
    request_edges = _walk(
        clients,
        edges_from,
        used,
        edge_index,
        expand=lambda n: (
            tier[n] in ("edge", "entry", "compute", "data") or by_id[n].capability in SYNC_CAPS
        ),
    )
    request_steps = [_step(by_id, e) for e in request_edges]
    tracers = [c for c in spec.components if c.capability == "llm-observability"]
    model_callers = {e.source for e in request_edges if by_id[e.target].capability in SYNC_CAPS}
    if request_steps and tracers and model_callers:
        request_steps.append(
            WorkflowStep(
                text=f"Every model call → {tracers[0].display_label}: {ROLE['llm-observability']}",
                components=[tracers[0].id, *sorted(model_callers)],
            )
        )
    monitors = [c for c in spec.components if c.capability == "monitoring"]
    if request_steps and monitors:
        request_steps.append(
            WorkflowStep(
                text=f"Every component → {monitors[0].display_label}: {ROLE['monitoring']}",
                components=[monitors[0].id],
            )
        )
    if request_steps:
        workflows.append(
            Workflow(id="request", name="Serving a request", kind="request", steps=request_steps)
        )

    # 2. Everything else at runtime as one flow, walked from where work is handed off.
    handed_off = {e.target for e in request_edges}
    background: list[Edge] = []
    remaining = [e for e in spec.edges if edge_index[id(e)] not in used]
    while remaining:
        targets = {e.target for e in remaining}
        sources = [e.source for e in remaining]
        # Prefer nodes the request path handed work to, then nodes nothing points at.
        start = next((s for s in sources if s in handed_off), None)
        if start is None:
            start = next((s for s in sources if s not in targets), sources[0])
        walked = _walk(
            [start],
            edges_from,
            used,
            edge_index,
            expand=lambda n: tier[n] not in ("external", "delivery"),
        )
        if not walked:
            break
        background += walked
        remaining = [e for e in spec.edges if edge_index[id(e)] not in used]
    if background:
        caps = {by_id[n].capability for e in background for n in (e.source, e.target)}
        has_data = bool(caps & DATA_CAPS)
        has_jobs = bool(caps & ASYNC_CAPS)
        if has_data and has_jobs:
            wf_id, name, kind = "background", "Background and data processing", "async"
        elif has_data:
            wf_id, name, kind = "data", "Data pipeline", "data"
        else:
            wf_id, name, kind = "background", "Background processing", "async"
        workflows.append(
            Workflow(id=wf_id, name=name, kind=kind, steps=[_step(by_id, e) for e in background])
        )

    # 3. Shipping a change: the toolchain, then the hand-over to the runtime.
    delivery = [c for c in spec.components if c.tier == "delivery"]
    if delivery:
        delivery_ids = {c.id for c in delivery}
        delivery_edges = [
            e for e in spec.edges if e.source in delivery_ids and e.target in delivery_ids
        ]
        entry_points = [c.id for c in delivery if not any(e.target == c.id for e in delivery_edges)]
        steps = []
        repos = [c for c in delivery if c.capability == "source-control"]
        devenvs = [c for c in delivery if c.capability == "dev-environment"]
        if devenvs:
            steps.append(
                WorkflowStep(
                    text=f"A developer → {devenvs[0].display_label}: {ROLE['dev-environment']}",
                    components=[devenvs[0].id],
                )
            )
        elif repos:
            steps.append(
                WorkflowStep(
                    text=f"A developer → {repos[0].display_label}: {ROLE['source-control']}",
                    components=[repos[0].id],
                )
            )
        seen_edges: set[int] = set()
        queue, seen = deque(entry_points), set(entry_points)
        while queue:
            node = queue.popleft()
            for edge in delivery_edges:
                if edge.source != node or id(edge) in seen_edges:
                    continue
                seen_edges.add(id(edge))
                steps.append(_step(by_id, edge))
                if edge.target not in seen:
                    seen.add(edge.target)
                    queue.append(edge.target)
        releases = [c for c in delivery if c.capability == "cd-deploy"]
        runtime = [c for c in spec.components if c.capability in RUNTIME_COMPUTE]
        if releases and runtime:
            names = ", ".join(c.display_label for c in runtime)
            steps.append(
                WorkflowStep(
                    text=f"{releases[0].display_label} → {names}: roll out the new version",
                    components=[releases[0].id, *(c.id for c in runtime)],
                )
            )
        if steps:
            workflows.append(
                Workflow(id="delivery", name="Shipping a change", kind="delivery", steps=steps)
            )

    return workflows


def with_workflows(spec: ArchitectureSpec) -> ArchitectureSpec:
    """Adds generated workflows when the spec has none."""
    if spec.workflows:
        return spec
    return spec.model_copy(update={"workflows": generate_workflows(spec)})
