"""The AI planner, driven by a scripted model so it runs without a network or API key."""

import asyncio

import pytest
from helpers import ScriptedLLM, tool_use

from cloudarchie import catalog
from cloudarchie.ingest import from_text
from cloudarchie.planner import PlanError, PlanOptions, run_plan
from cloudarchie.planner.agent import check_submission
from cloudarchie.planner.llm import LLMError

pytest.importorskip("mcp")

DOC = next(text for sid, _, text in catalog.samples() if sid == "policy-assistant")


def plan(llm, mode="auto", region=None):
    events = []
    result = asyncio.run(
        run_plan(from_text(DOC), PlanOptions(mode=mode, region=region), llm, events.append)
    )
    return result, events


def test_agent_designs_over_mcp_and_its_output_is_checked():
    llm = ScriptedLLM()
    result, events = plan(llm)
    spec = result.spec

    assert (result.mode, result.model) == ("ai", "scripted-model")
    assert spec.provenance.mode == "ai" and spec.provenance.model == "scripted-model"
    ids = {c.id for c in spec.components}
    assert "build-it" not in ids, "toolchain components from the model are dropped"
    assert {"repo", "build", "registry", "deploy", "infra-code"} <= ids, "and added properly"
    chat = next(c for c in spec.components if c.id == "chat")
    assert chat.evidence == ["Responses should stream back to the browser as they are generated"]
    assert [w.name for w in spec.workflows] == ["Answering a question"]
    assert spec.workflows[0].id == "request"

    calls = [(e["name"], e.get("ok")) for e in events if e["type"] in ("tool_call", "tool_result")]
    assert calls == [
        ("list_patterns", None),
        ("list_patterns", True),
        ("get_pattern", None),
        ("get_pattern", True),
        ("search_services", None),
        ("search_services", True),
        ("submit_design", None),
        ("submit_design", False),
        ("submit_design", None),
        ("submit_design", True),
    ]
    notes = [e["text"] for e in events if e["type"] == "note"]
    assert "Checking the closest pattern." in notes
    assert "Removed 1 evidence quote that did not appear in the document." in notes
    understood = next(
        e
        for e in events
        if e["type"] == "stage" and e["stage"] == "understand" and e["status"] == "done"
    )
    assert any("cited answers" in item for item in understood["items"])
    assert not any("made up" in item for item in understood["items"]), "unquotable features dropped"
    assert events[-1]["type"] == "result" and events[-1]["mode"] == "ai"


def test_design_requests_are_cached_append_only_and_think_adaptively():
    llm = ScriptedLLM()
    plan(llm)
    design = [c for c in llm.calls if "tools" in c]
    assert len(design) == 4
    for earlier, later in zip(design, design[1:], strict=False):
        assert later["messages"][: len(earlier["messages"])] == earlier["messages"]
    first = design[0]
    assert first["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert first["messages"][0]["content"][0]["cache_control"] == {"type": "ephemeral"}
    assert "<document>" in first["messages"][0]["content"][0]["text"]
    assert first["thinking"] == {"type": "adaptive", "display": "summarized"}
    assert first["output_config"] == {"effort": "high"}
    names = [t["name"] for t in first["tools"]]
    assert names[-1] == "submit_design" and "validate_spec" in names
    assert all(t.get("strict") for t in first["tools"])
    # Thinking blocks go back to the model unchanged.
    assert design[1]["messages"][1]["content"][0]["type"] == "thinking"
    # The bad submission came back as an error result the model could fix.
    rejected = design[3]["messages"][-1]["content"][0]
    assert rejected["is_error"] is True and "unknown capability" in rejected["content"]


def test_understand_and_workflows_use_structured_outputs():
    llm = ScriptedLLM()
    plan(llm)
    structured = [c for c in llm.calls if "format" in (c.get("output_config") or {})]
    assert len(structured) == 2
    understand, workflows = structured
    assert understand["output_config"]["effort"] == "low"
    assert workflows["output_config"]["effort"] == "medium"
    schema = workflows["output_config"]["format"]["schema"]
    step_ids = schema["properties"]["workflows"]["items"]["properties"]["steps"]["items"]
    assert "chat" in step_ids["properties"]["components"]["items"]["enum"]


def test_failures_fall_back_to_the_rule_based_draft():
    class Broken(ScriptedLLM):
        async def create(self, **params):
            raise LLMError("The Anthropic API rate limit was reached; try again shortly.")

    result, events = plan(Broken())
    assert result.mode == "rules"
    notice = next(e for e in events if e["type"] == "notice")
    assert "rate limit" in notice["text"] and "rule-based draft" in notice["text"]


def test_refusals_and_silent_agents_fall_back_too():
    refused, events = plan(ScriptedLLM(stop_reason="refusal"))
    assert refused.mode == "rules"
    assert any("declined" in e.get("text", "") for e in events if e["type"] == "notice")

    silent, events = plan(ScriptedLLM(design_turns=[[], []]))
    assert silent.mode == "rules"
    assert any("without submitting" in e.get("text", "") for e in events if e["type"] == "notice")


def test_ai_mode_without_a_model_is_an_error_and_rules_mode_skips_the_model():
    with pytest.raises(PlanError, match="AI planning is not set up"):
        plan(None, mode="ai")
    llm = ScriptedLLM()
    result, _ = plan(llm, mode="rules", region="uk")
    assert result.mode == "rules" and not llm.calls
    assert result.spec.requirements.region == "uk"


def test_check_submission_rejects_specs_that_do_not_map():
    spec, message, _ = check_submission("name: X\ncomponents: [{id: a, capability: nope}]", DOC)
    assert spec is None and "unknown capability" in message
    spec, message, _ = check_submission("- a list", DOC)
    assert spec is None and "mapping" in message
    spec, message, _ = check_submission("name: [", DOC)
    assert spec is None and message.startswith("YAML syntax error")


def test_tool_errors_reach_the_model_as_error_results():
    llm = ScriptedLLM(
        design_turns=[
            [tool_use("t1", "get_pattern", {"pattern_id": "no-such-pattern"})],
            [tool_use("t2", "submit_design", {"spec_yaml": catalog.pattern_text("rag-chatbot")})],
        ]
    )
    result, events = plan(llm)
    assert result.mode == "ai"
    failed = next(e for e in events if e["type"] == "tool_result" and e["name"] == "get_pattern")
    assert failed["ok"] is False and "unknown pattern" in failed["summary"]
