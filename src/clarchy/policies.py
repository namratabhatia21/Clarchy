"""Which AI and data policies apply to a design, and how far the design meets them.

Policies, their obligations and the capabilities that help with each live in
data/policies.yaml. For a design, every applicable obligation is "covered" (a component
does the job), a "gap" (a capability that would help is missing) or an "action" (work for
the team, such as an impact assessment, that no diagram can provide).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import yaml

from clarchy import catalog
from clarchy.spec import ArchitectureSpec

AI_CAPS = {"llm-inference", "agent-orchestration", "llm-gateway"}


@lru_cache(maxsize=1)
def policy_list() -> list[dict[str, Any]]:
    with catalog.data_path("policies.yaml").open(encoding="utf-8") as f:
        return yaml.safe_load(f)["policies"]


def _applies(when: dict[str, Any], spec: ArchitectureSpec, caps: set[str]) -> bool:
    req = spec.requirements
    return bool(
        (when.get("ai") and caps & AI_CAPS)
        or req.region in when.get("regions", [])
        or set(req.compliance) & set(when.get("compliance", []))
    )


def check(spec: ArchitectureSpec) -> list[dict[str, Any]]:
    """The applicable policies, each obligation with its status in this design."""
    caps = {c.capability for c in spec.components}
    by_cap: dict[str, list[str]] = {}
    for c in spec.components:
        by_cap.setdefault(c.capability, []).append(c.display_label)
    known = catalog.capabilities()
    out = []
    for policy in policy_list():
        if not _applies(policy.get("when", {}), spec, caps):
            continue
        obligations = []
        for ob in policy["obligations"]:
            controls = ob.get("controls", [])
            present = [label for cap in controls for label in by_cap.get(cap, [])]
            if not controls:
                status = "action"
            elif present:
                status = "covered"
            else:
                status = "gap"
            obligations.append(
                {
                    "text": ob["text"],
                    "status": status,
                    "by": present,
                    "suggest": [
                        {"capability": cap, "description": known[cap]["description"]}
                        for cap in controls
                        if status == "gap" and cap in known
                    ][:1],
                }
            )
        out.append(
            {
                "id": policy["id"],
                "name": policy["name"],
                "kind": policy.get("kind"),
                "url": policy.get("url"),
                "summary": policy.get("summary"),
                "note": policy.get("note"),
                "obligations": obligations,
                "counts": {
                    s: sum(1 for o in obligations if o["status"] == s)
                    for s in ("covered", "gap", "action")
                },
            }
        )
    return out
