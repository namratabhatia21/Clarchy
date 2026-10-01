"""Clarchy as an MCP server, and the agent's MCP client toolbox."""

import asyncio
import json

import pytest

pytest.importorskip("mcp")

from mcp.shared.memory import create_connected_server_and_client_session  # noqa: E402

from clarchy import catalog  # noqa: E402
from clarchy.mcp_server import build_server  # noqa: E402
from clarchy.planner.toolbox import MCPToolbox, strict_schema  # noqa: E402
from clarchy.tools import AGENT_TOOL_NAMES, TOOLS  # noqa: E402


def run(coro):
    return asyncio.run(coro)


def test_server_exposes_tools_resources_and_prompt():
    async def scenario():
        async with create_connected_server_and_client_session(build_server()) as client:
            tools = {t.name for t in (await client.list_tools()).tools}
            templates = (await client.list_resource_templates()).resourceTemplates
            prompts = {p.name for p in (await client.list_prompts()).prompts}
            pattern = await client.read_resource("clarchy://patterns/rag-chatbot")
            result = await client.call_tool("search_services", {"query": "keda", "provider": "aws"})
            bad = await client.call_tool("get_pattern", {"pattern_id": "nope"})
            return tools, templates, prompts, pattern, result, bad

    tools, templates, prompts, pattern, result, bad = run(scenario())
    assert tools == set(TOOLS)
    assert templates[0].uriTemplate == "clarchy://patterns/{pattern_id}"
    assert "design_architecture" in prompts
    assert pattern.contents[0].text == catalog.pattern_text("rag-chatbot")
    assert not result.isError
    hits = result.structuredContent["result"]  # FastMCP wraps lists; content has one per item
    assert hits[0]["service"] == "KEDA on Amazon EKS"
    assert json.loads(result.content[0].text) == hits[0]
    assert bad.isError and "unknown pattern" in bad.content[0].text


def test_toolbox_offers_the_agent_tools_with_strict_schemas():
    async def scenario():
        async with MCPToolbox() as box:
            text, is_error = await box.call("validate_spec", {"spec_yaml": "name: ["})
            missing = await box.call("render_design", {"spec_yaml": "", "provider": "aws"})
            return box.definitions, json.loads(text), is_error, missing

    definitions, validation, is_error, missing = run(scenario())
    assert [d["name"] for d in definitions] == list(AGENT_TOOL_NAMES)
    for d in definitions:
        assert d["strict"] is True
        assert d["input_schema"]["additionalProperties"] is False
    assert is_error is False and validation["valid"] is False
    assert missing[1] is True  # rendering is not one of the agent's tools


def test_strict_schema_requires_every_property():
    schema = strict_schema(
        {
            "title": "Args",
            "type": "object",
            "properties": {"a": {"type": "string", "title": "A"}, "b": {"type": "integer"}},
            "required": ["a"],
        }
    )
    assert schema == {
        "type": "object",
        "properties": {"a": {"type": "string"}, "b": {"type": "integer"}},
        "required": ["a", "b"],
        "additionalProperties": False,
    }
