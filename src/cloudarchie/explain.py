"""Human-readable explanation of a mapped architecture: what was chosen and why."""

from __future__ import annotations

from cloudarchie import catalog
from cloudarchie.mapping import ProviderArchitecture


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

    lines += ["## Requirements", ""]
    facts = [
        ("Region", f"{arch.region_label} ({arch.region_code})"),
        ("Monthly active users", req.users),
        ("Peak requests/second", req.peak_rps),
        ("Data stored (GB)", req.data_gb),
        ("Data growth (GB/month)", req.data_growth_gb_per_month),
        ("Availability target", f"{req.availability_target}%"),
        ("Compliance", ", ".join(req.compliance) or "none stated"),
        ("Monthly budget (USD)", req.monthly_budget_usd),
    ]
    lines += [f"- **{k}:** {_num(v)}" for k, v in facts if v is not None]

    lines += [
        "",
        "## Services",
        "",
        "| Component | Capability | Service | Fidelity | Why |",
        "|---|---|---|---|---|",
    ]
    for m in arch.components:
        comp, choice = m.component, m.choice
        service = choice.service if choice else "(outside the cloud)"
        fidelity = choice.fidelity if choice else "-"
        why = (
            comp.rationale or f"_Generic: {catalog.capabilities()[comp.capability]['description']}_"
        )
        lines.append(
            f"| {_cell(comp.display_label)} | `{comp.capability}` | {_cell(service)} "
            f"| {fidelity} | {_cell(why)} |"
        )

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

    lines += [
        "",
        "---",
        "Cost estimates arrive in a later phase. Service names belong to their owners; "
        "CloudArchie is not affiliated with any cloud provider.",
    ]
    return "\n".join(lines) + "\n"
