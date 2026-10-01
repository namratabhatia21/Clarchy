import json

import pytest
import yaml

from clarchy import catalog
from clarchy.tools import AGENT_TOOL_NAMES, TOOLS, ToolError


def call(name, **args):
    return TOOLS[name](args)


def test_every_tool_has_a_strict_schema_and_a_description():
    for tool in TOOLS.values():
        schema = tool.input_schema
        assert schema["type"] == "object" and schema["additionalProperties"] is False
        assert schema["required"] == list(schema["properties"])
        assert len(tool.description) > 20
    assert set(AGENT_TOOL_NAMES) <= set(TOOLS)


def test_capabilities_include_the_delivery_toolchain_and_kubernetes():
    caps = {c["id"]: c for c in call("list_capabilities")}
    assert caps["kubernetes"]["stage"] == "run"
    assert caps["event-autoscaling"]["category"] == "containers"
    for cap in ("source-control", "ci-build", "container-registry", "cd-deploy", "iac"):
        assert caps[cap]["tier"] == "delivery"


def test_patterns_and_regions():
    ids = [p["id"] for p in call("list_patterns")]
    assert ids == catalog.pattern_names()
    assert (
        "kubernetes"
        in next(p for p in call("list_patterns") if p["id"] == "kubernetes-microservices")[
            "capabilities"
        ]
    )
    assert yaml.safe_load(call("get_pattern", pattern_id="rag-chatbot")["spec_yaml"])["name"]
    with pytest.raises(ToolError, match="unknown pattern"):
        call("get_pattern", pattern_id="nope")
    assert call("list_regions")["eu-central"]


def test_search_finds_equivalents_by_service_name():
    hits = call("search_services", query="keda", provider="all")
    assert {h["provider"] for h in hits} == {"aws", "azure", "gcp", "oss"}
    assert all(h["capability"] == "event-autoscaling" for h in hits)
    assert call("search_services", query="argo", provider="oss")[0]["service"] == "Argo CD"
    with pytest.raises(ToolError, match="unknown provider"):
        call("search_services", query="queue", provider="ibm")


def test_validate_reports_errors_and_warnings():
    bad = call("validate_spec", spec_yaml="name: X\ncomponents: [{id: a, capability: teleporter}]")
    assert bad["valid"] is False and "unknown capability" in bad["errors"][0]["message"]
    assert call("validate_spec", spec_yaml="name: [")["errors"][0]["where"] == "yaml"
    loose = call(
        "validate_spec",
        spec_yaml="name: X\ncomponents:\n  - {id: users, capability: client}\n"
        "  - {id: app, capability: container-service}\n",
    )
    assert loose["valid"] is True
    assert "app: add a rationale explaining why it is needed" in loose["warnings"]
    assert "no monitoring component" in loose["warnings"]


def test_toolchain_render_and_draft():
    spec = "name: X\ncomponents: [{id: app, capability: kubernetes}]\n"
    with_toolchain = yaml.safe_load(call("add_delivery_toolchain", spec_yaml=spec)["spec_yaml"])
    assert {"repo", "build", "registry", "deploy", "infra-code"} <= {
        c["id"] for c in with_toolchain["components"]
    }
    rendered = call("render_design", spec_yaml=spec, provider="azure")
    assert rendered["svg"].startswith("<svg") and "Azure Kubernetes" in rendered["svg"]
    assert "Azure Kubernetes Service (AKS)" in rendered["explanation_md"]
    draft = call("draft_architecture", requirements="A booking app for 40 clinics in the UK.")
    assert draft["components"] > 5
    assert yaml.safe_load(draft["spec_yaml"])["requirements"]["region"] == "uk"


def test_results_are_json_serialisable():
    for name in ("list_capabilities", "list_regions", "list_patterns"):
        json.dumps(call(name))
