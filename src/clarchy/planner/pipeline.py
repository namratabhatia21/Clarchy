"""The planning pipeline: requirements document -> complete, explained architecture.

Stages (each streamed as events):
  read        the document's text
  understand  requirements, needs and gaps          (Claude, or rules)
  design      the runtime architecture              (Claude agent with MCP tools, or rules)
  toolchain   build and deploy, KEDA when needed    (deterministic)
  workflows   how requests, jobs and releases flow  (Claude, or generated)
  map         the design on every provider          (deterministic)

With a model configured the AI path runs; if it fails part-way, the run falls back to the
rule-based planner and says so, so the user always gets a design.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from clarchy import catalog
from clarchy.delivery import add_delivery
from clarchy.ingest import Document
from clarchy.mapping import map_to_provider
from clarchy.planner import agent
from clarchy.planner.events import EmitFn, Emitter
from clarchy.planner.llm import LLM, LLMError
from clarchy.planner.rules import analyse, build_spec
from clarchy.spec import ArchitectureSpec, Provenance, spec_to_yaml
from clarchy.workflows import generate_workflows

Mode = Literal["auto", "ai", "rules"]


class PlanError(RuntimeError):
    """The plan could not be produced; the message is for the user."""


@dataclass
class PlanOptions:
    mode: Mode = "auto"
    region: str | None = None
    extra_mcp_servers: list[str] = field(default_factory=list)
    # "mcp": the agent is an MCP client of Clarchy's server; "local": the same tools are
    # called in-process (the browser engine, or when the MCP SDK is not installed).
    toolbox: Literal["mcp", "local"] = "mcp"


def _toolbox(options: PlanOptions):
    from clarchy.planner.local_toolbox import LocalToolbox

    if options.toolbox == "local":
        return LocalToolbox()
    try:
        from clarchy.planner.toolbox import MCPToolbox  # needs the "agent" extra
    except ImportError:
        return LocalToolbox()
    return MCPToolbox(options.extra_mcp_servers)


@dataclass
class PlanResult:
    spec: ArchitectureSpec
    mode: str
    model: str | None

    @property
    def spec_yaml(self) -> str:
        return spec_to_yaml(self.spec)


def _with_region(spec: ArchitectureSpec, region: str | None) -> ArchitectureSpec:
    if not region or spec.requirements.region == region:
        return spec
    requirements = spec.requirements.model_copy(update={"region": region})
    return spec.model_copy(update={"requirements": requirements})


async def _rules_design(doc: Document, options: PlanOptions, emitter: Emitter) -> ArchitectureSpec:
    await emitter.stage("understand", "running")
    plan = analyse(doc.text)
    needs = [f"{need}: “{quotes[0][:80]}”" for need, quotes in plan.needs.items()]
    await emitter.stage(
        "understand",
        "done",
        f"Found {len(plan.found)} facts and {len(plan.needs)} needs",
        items=plan.found + needs,
    )
    await emitter.stage("design", "running")
    spec = _with_region(build_spec(plan, source=doc.name), options.region)
    await emitter.stage(
        "design",
        "done",
        f"{len(spec.components)} components, compute on {plan.decisions[0]}",
        items=[
            f"{c.display_label} ({c.capability})" for c in spec.components if c.tier != "external"
        ],
    )
    return spec


async def _ai_design(
    doc: Document, options: PlanOptions, llm: LLM, emitter: Emitter
) -> ArchitectureSpec:
    await emitter.stage("understand", "running", f"Asking {llm.model} to read the requirements")
    understood = await agent.understand(llm, doc.text, emitter)
    req = understood.requirements
    facts = [
        f"{label}: {value}"
        for label, value in (
            ("Users", f"{req.users:,}" if req.users else None),
            ("Peak", f"{req.peak_rps:g} requests/second" if req.peak_rps else None),
            ("Data", f"{req.data_gb:g} GB" if req.data_gb else None),
            ("Availability", f"{req.availability_target}%"),
            ("Region", catalog.regions()[req.region]["label"]),
            ("Compliance", ", ".join(req.compliance) or None),
        )
        if value
    ]
    await emitter.stage(
        "understand",
        "done",
        f"{len(understood.features)} needs, {len(understood.open_questions)} open questions",
        items=facts + [f"{f['need']}: “{f['quote']}”" for f in understood.features],
    )
    toolbox = _toolbox(options)
    how = "MCP tools" if type(toolbox).__name__ == "MCPToolbox" else "tools"
    await emitter.stage("design", "running", f"The agent is designing with Clarchy's {how}")
    async with toolbox:
        spec = await agent.design(llm, toolbox, doc.text, understood, emitter, options.region)
    spec = spec.model_copy(
        update={"provenance": Provenance(mode="ai", model=llm.model, source=doc.name)}
    )
    await emitter.stage(
        "design",
        "done",
        f"{len(spec.components)} components, validated",
        items=[
            f"{c.display_label} ({c.capability})" for c in spec.components if c.tier != "external"
        ],
    )
    return _with_region(spec, options.region)


async def run_plan(
    doc: Document,
    options: PlanOptions | None = None,
    llm: LLM | None = None,
    emit: EmitFn | None = None,
) -> PlanResult:
    options = options or PlanOptions()
    emitter = Emitter(emit)
    details = ", ".join(doc.details)
    await emitter.stage(
        "read",
        "done",
        f"{doc.words:,} words from {doc.name}" + (f" ({details})" if details else ""),
    )

    if options.mode == "ai" and llm is None:
        raise PlanError(
            "AI planning is not set up. Set ANTHROPIC_API_KEY (or CLARCHY_LLM=bedrock) "
            "and restart, or choose rule-based planning."
        )
    use_ai = llm is not None and options.mode != "rules"
    mode, model = "rules", None
    if use_ai:
        try:
            spec = await _ai_design(doc, options, llm, emitter)
            mode, model = "ai", llm.model
        except (LLMError, agent.AgentError) as exc:
            await emitter.emit(
                {
                    "type": "notice",
                    "text": f"The AI planner stopped: {exc} Showing the rule-based draft instead.",
                }
            )
            spec = await _rules_design(doc, options, emitter)
    else:
        spec = await _rules_design(doc, options, emitter)

    await emitter.stage("toolchain", "running")
    before = {c.id for c in spec.components}
    spec = add_delivery(spec)
    added = [c for c in spec.components if c.id not in before]
    await emitter.stage(
        "toolchain",
        "done",
        f"Added {len(added)} build, release and scaling components",
        items=[f"{c.display_label} ({c.capability})" for c in added],
    )

    await emitter.stage("workflows", "running")
    workflows = None
    if mode == "ai":
        try:
            workflows = await agent.describe_workflows(llm, spec)
        except (LLMError, agent.AgentError, ValueError) as exc:
            await emitter.emit({"type": "notice", "text": f"Using generated workflows: {exc}"})
    spec = spec.model_copy(update={"workflows": workflows or generate_workflows(spec)})
    spec = ArchitectureSpec.model_validate(spec.model_dump(by_alias=True))  # re-check refs
    await emitter.stage(
        "workflows",
        "done",
        f"{len(spec.workflows)} workflows",
        items=[f"{w.name}: {len(w.steps)} steps" for w in spec.workflows],
    )

    await emitter.stage("map", "running")
    items = []
    for provider in catalog.providers_in_display_order():
        arch = map_to_provider(spec, provider)
        services = {m.choice.service for m in arch.components if m.choice}
        close = sum(1 for m in arch.components if m.choice and m.choice.fidelity != "exact")
        items.append(
            f"{arch.provider_name}: {len(services)} services"
            + (f", {close} with differences" if close else "")
        )
    await emitter.stage("map", "done", "Ready on every provider", items=items)

    result = PlanResult(spec=spec, mode=mode, model=model)
    await emitter.emit(
        {"type": "result", "spec_yaml": result.spec_yaml, "mode": mode, "model": model}
    )
    return result
