"""Human-readable explanation of a mapped architecture: what was chosen and why."""

from __future__ import annotations

from clarchy import catalog, pricing
from clarchy.mapping import ProviderArchitecture


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def _num(value: object) -> object:
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def explain_markdown(arch: ProviderArchitecture) -> str:
    spec, req = arch.spec, arch.spec.requirements
    lines = [f"# {spec.name} on {arch.provider_name}", ""]
    if spec.summary:
        lines += [spec.summary, ""]

    if spec.provenance and spec.provenance.mode != "manual":
        who = (
            "the rule-based planner"
            if spec.provenance.mode == "rules"
            else (
                f"an AI agent ({spec.provenance.model})" if spec.provenance.model else "an AI agent"
            )
        )
        source = f" from {spec.provenance.source}" if spec.provenance.source else ""
        lines += [f"_Drafted by {who}{source}. Review it before building._", ""]
    if not arch.reviewed:
        lines += [
            f"> {arch.provider_name} mappings have not yet been reviewed by a specialist. "
            "Check the service choices before relying on them.",
            "",
        ]
    lines += ["## Requirements", ""]
    facts = [
        ("Region", arch.region_text),
        ("Monthly active users", req.users),
        ("Peak requests/second", req.peak_rps),
        ("Data stored (GB)", req.data_gb),
        ("Data growth (GB/month)", req.data_growth_gb_per_month),
        ("Availability target", f"{req.availability_target}%"),
        ("Compliance", ", ".join(req.compliance) or "none stated"),
        ("Monthly budget (USD)", req.monthly_budget_usd),
    ]
    lines += [f"- **{k}:** {_num(v)}" for k, v in facts if v is not None]
    if spec.assumptions:
        lines += ["", "## Assumptions", ""] + [f"- {a}" for a in spec.assumptions]
    if spec.open_questions:
        lines += ["", "## Questions to confirm", ""] + [f"- {q}" for q in spec.open_questions]

    lines += [
        "",
        "## Services",
        "",
        "| Stage | Component | Capability | Service | Fidelity | Why |",
        "|---|---|---|---|---|---|",
    ]
    stage_order = {key: n for n, key in enumerate(catalog.STAGES)}
    ordered = sorted(
        arch.components,
        key=lambda m: stage_order.get(m.component.stage or "", -1),
    )
    for m in ordered:
        comp, choice = m.component, m.choice
        service = choice.service if choice else "(outside the cloud)"
        fidelity = choice.fidelity if choice else "-"
        stage = catalog.STAGES.get(comp.stage or "", "Users")
        why = (
            comp.rationale or f"_Generic: {catalog.capabilities()[comp.capability]['description']}_"
        )
        if comp.evidence:
            why += " Evidence: " + "; ".join(f"“{q}”" for q in comp.evidence)
        lines.append(
            f"| {stage} | {_cell(comp.display_label)} | `{comp.capability}` | {_cell(service)} "
            f"| {fidelity} | {_cell(why)} |"
        )

    if spec.workflows:
        lines += ["", "## Workflows"]
        for wf in spec.workflows:
            lines += ["", f"### {wf.name}", ""]
            lines += [f"{n}. {step.text}" for n, step in enumerate(wf.steps, start=1)]

    platform_links = [
        e
        for e in spec.edges
        if "platform" in (spec.component(e.source).tier, spec.component(e.target).tier)
    ]
    if platform_links:
        lines += ["", "## Shared services used", ""]
        for e in platform_links:
            src, dst = arch.by_id(e.source), arch.by_id(e.target)
            name = lambda m: m.choice.service if m.choice else m.component.display_label  # noqa: E731
            suffix = f": {e.label}" if e.label else ""
            lines.append(f"- {src.component.display_label} → {name(dst)}{suffix}")

    notes = [m for m in arch.components if m.choice and (m.choice.note or m.choice.alternatives)]
    if notes:
        lines += ["", "## Trade-offs and alternatives", ""]
        for m in notes:
            choice = m.choice
            parts = []
            if choice.alternatives:
                parts.append("alternatives: " + ", ".join(choice.alternatives))
            if choice.note:
                parts.append(choice.note.strip())
            lines.append(
                f"- **{choice.service}** ({m.component.display_label}): " + "; ".join(parts)
            )

    sized = [m for m in arch.components if m.component.sizing]
    if sized:
        lines += ["", "## Sizing assumptions", ""]
        for m in sized:
            pairs = ", ".join(f"{k}={_num(v)}" for k, v in m.component.sizing.items())
            lines.append(f"- **{m.component.display_label}:** {pairs}")

    lines += ["", *pricing.summary_markdown(pricing.estimate(arch))]
    lines += [
        "---",
        "Estimates use list prices and the usage stated above; check them with the provider's "
        "calculator. Service names belong to their owners; Clarchy is not affiliated with "
        "any cloud provider.",
    ]
    return "\n".join(lines) + "\n"
