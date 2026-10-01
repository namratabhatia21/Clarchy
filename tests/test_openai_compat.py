"""Open-source models through OpenAI-compatible endpoints, with a scripted server."""

import asyncio
import json

import pytest
from helpers import POLICY_DOC, POLICY_SPEC, make_docx

from clarchy import browser
from clarchy.ingest import from_text
from clarchy.planner import PlanOptions, run_plan
from clarchy.planner.llm import LLMError, llm_from_env
from clarchy.planner.local_toolbox import LocalToolbox
from clarchy.planner.openai_compat import OpenAICompatLLM, from_chat, to_chat
from clarchy.tools import AGENT_TOOL_NAMES

DOC = POLICY_DOC


def call(id_, name, args):
    return {
        "id": id_,
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(args)},
    }


class ChatServer:
    """A fake chat-completions endpoint: understands, designs with tools, writes workflows."""

    def __init__(self, reject_schemas=False):
        self.requests = []
        self.reject_schemas = reject_schemas
        self.turns = [
            [call("c1", "list_patterns", {})],
            [call("c2", "submit_design", {"spec_yaml": POLICY_SPEC})],
        ]

    async def __call__(self, url, headers, body):
        self.requests.append((url, headers, json.loads(json.dumps(body))))
        fmt = body.get("response_format")
        if self.reject_schemas and fmt and fmt["type"] == "json_schema":
            return 400, {"error": {"message": "response_format json_schema is not supported"}}
        system = body["messages"][0]["content"]
        if "app_name" in system:
            data = {
                "app_name": "Policy assistant",
                "summary": "Answers policy questions.",
                "users": 2000,
                "peak_rps": None,
                "data_gb": None,
                "data_growth_gb_per_month": None,
                "availability_target": None,
                "region": "eu-west",
                "compliance": ["GDPR"],
                "monthly_budget_usd": 1500,
                "assumptions": [],
                "open_questions": [],
                "features": [
                    {
                        "need": "cited answers",
                        "quote": "answers must cite the policy documents they come from",
                    }
                ],
            }
            # Some models wrap JSON in a code fence; the agent copes.
            return 200, _reply(f"```json\n{json.dumps(data)}\n```")
        if "workflows" in system.lower() and "tools" not in body:
            data = {
                "workflows": [
                    {
                        "name": "Answering",
                        "kind": "request",
                        "steps": [{"text": "A question arrives.", "components": ["staff", "chat"]}],
                    }
                ]
            }
            return 200, _reply(json.dumps(data))
        calls = self.turns.pop(0) if self.turns else []
        return 200, _reply("<think>Start from the closest pattern.</think>", calls)


def _reply(content, tool_calls=None):
    message = {"role": "assistant", "content": content}
    if tool_calls:
        message["tool_calls"] = tool_calls
    return {
        "choices": [{"message": message, "finish_reason": "tool_calls" if tool_calls else "stop"}]
    }


def test_requests_translate_to_chat_completions():
    body = to_chat(
        {
            "max_tokens": 16000,
            "system": [
                {"type": "text", "text": "Be brief.", "cache_control": {"type": "ephemeral"}}
            ],
            "output_config": {"format": {"type": "json_schema", "schema": {"type": "object"}}},
            "tools": [
                {
                    "name": "get_pattern",
                    "description": "d",
                    "input_schema": {"type": "object"},
                    "strict": True,
                }
            ],
            "messages": [
                {"role": "user", "content": [{"type": "text", "text": "Design it."}]},
                {
                    "role": "assistant",
                    "content": [
                        {"type": "thinking", "thinking": "hmm", "signature": "s"},
                        {
                            "type": "tool_use",
                            "id": "t1",
                            "name": "get_pattern",
                            "input": {"pattern_id": "x"},
                        },
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "t1",
                            "content": "unknown pattern",
                            "is_error": True,
                        }
                    ],
                },
            ],
        },
        "open-model",
    )
    assert body["model"] == "open-model" and body["max_tokens"] == 6000
    system, user, assistant, tool = body["messages"]
    assert system["role"] == "system" and "JSON schema" in system["content"]
    assert user == {"role": "user", "content": "Design it."}
    assert assistant["tool_calls"][0]["function"] == {
        "name": "get_pattern",
        "arguments": '{"pattern_id": "x"}',
    }
    assert assistant["content"] is None, "thinking is not sent back"
    assert tool == {"role": "tool", "tool_call_id": "t1", "content": "Error: unknown pattern"}
    assert body["tools"][0]["function"]["parameters"] == {"type": "object"}
    assert body["response_format"]["type"] == "json_schema"


def test_replies_translate_back():
    reply = from_chat(
        _reply(
            "<think>plan</think>Done.",
            [
                call("c1", "validate_spec", {"spec_yaml": "x"}),
                {
                    "id": "c2",
                    "type": "function",
                    "function": {"name": "list_regions", "arguments": "{not json"},
                },
            ],
        )
    )
    assert [b["type"] for b in reply["content"]] == ["thinking", "text", "tool_use", "tool_use"]
    assert reply["content"][0]["thinking"] == "plan" and reply["content"][1]["text"] == "Done."
    assert reply["content"][3]["input"] == {}
    assert reply["stop_reason"] == "tool_use"
    cut = from_chat({"choices": [{"message": {"content": "partial"}, "finish_reason": "length"}]})
    assert cut["stop_reason"] == "max_tokens"


def test_the_agent_runs_on_an_open_model_with_local_tools():
    server = ChatServer()
    llm = OpenAICompatLLM(
        "Qwen/Qwen2.5-72B-Instruct", "https://example.test/v1", "hf_x", transport=server
    )
    events = []
    result = asyncio.run(run_plan(from_text(DOC), PlanOptions(toolbox="local"), llm, events.append))
    assert result.mode == "ai" and result.model == "Qwen/Qwen2.5-72B-Instruct"
    assert any(e["type"] == "note" and "closest pattern" in e["text"] for e in events)
    assert [e["name"] for e in events if e["type"] == "tool_call"] == [
        "list_patterns",
        "submit_design",
    ]
    assert [w.name for w in result.spec.workflows] == ["Answering"]
    url, headers, _ = server.requests[0]
    assert url == "https://example.test/v1/chat/completions"
    assert headers["Authorization"] == "Bearer hf_x"


def test_servers_without_json_schemas_fall_back_to_json_mode():
    server = ChatServer(reject_schemas=True)
    llm = OpenAICompatLLM("m", "http://localhost:11434/v1", transport=server)
    result = asyncio.run(run_plan(from_text(DOC), PlanOptions(toolbox="local"), llm))
    assert result.mode == "ai"
    formats = [body.get("response_format", {}).get("type") for _, _, body in server.requests]
    assert formats[:2] == ["json_schema", "json_object"]
    assert "Authorization" not in server.requests[0][1]


def test_provider_errors_are_readable():
    async def unauthorized(url, headers, body):
        return 401, {"error": {"message": "bad token"}}

    llm = OpenAICompatLLM("m", "https://example.test/v1", "x", transport=unauthorized)
    with pytest.raises(LLMError, match="rejected the access token"):
        asyncio.run(llm.create(messages=[{"role": "user", "content": "hi"}]))


def test_environment_picks_open_models(monkeypatch):
    for key in (
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_AUTH_TOKEN",
        "CLARCHY_LLM",
        "CLARCHY_MODEL",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("HF_TOKEN", "hf_abc")
    llm = llm_from_env()
    assert llm.base_url == "https://router.huggingface.co/v1" and llm.label.endswith(
        "(Hugging Face)"
    )
    monkeypatch.setenv("CLARCHY_LLM", "ollama")
    monkeypatch.setenv("CLARCHY_MODEL", "llama3.1:8b")
    llm = llm_from_env()
    assert llm.base_url == "http://localhost:11434/v1" and llm.model == "llama3.1:8b"
    monkeypatch.setenv("CLARCHY_LLM", "openai-compatible")
    monkeypatch.delenv("CLARCHY_MODEL")
    with pytest.raises(LLMError, match="CLARCHY_LLM_BASE_URL"):
        llm_from_env()


def test_local_toolbox_matches_the_agent_tools():
    async def scenario():
        async with LocalToolbox() as box:
            ok = await box.call("get_pattern", {"pattern_id": "rag-chatbot"})
            missing = await box.call("get_pattern", {"pattern_id": "nope"})
            wrong = await box.call("get_pattern", {"id": "x"})
            outside = await box.call("render_design", {})
            return box.definitions, ok, missing, wrong, outside

    definitions, ok, missing, wrong, outside = asyncio.run(scenario())
    assert [d["name"] for d in definitions] == list(AGENT_TOOL_NAMES)
    assert ok[1] is False and json.loads(ok[0])["id"] == "rag-chatbot"
    assert missing[1] is True and "unknown pattern" in missing[0]
    assert wrong[1] is True and "Invalid arguments" in wrong[0]
    assert outside == ("Unknown tool 'render_design'.", True)


def test_browser_entry_points(tmp_path):
    events = []
    upload = tmp_path / "upload"
    upload.write_bytes(
        make_docx(["Tutor marketplace", "Students in India book tutors and pay online."])
    )
    request = {"file_path": str(upload), "file_name": "brief.docx", "mode": "rules", "region": None}
    asyncio.run(browser.plan(json.dumps(request), lambda e: events.append(json.loads(e))))
    assert events[0]["detail"].endswith("from brief.docx (2 paragraphs)")
    result = events[-1]
    assert result["type"] == "result" and result["mode"] == "rules"
    design = json.loads(browser.design(result["spec_yaml"], "azure"))
    assert design["ok"] and design["body"]["cost"]["available"]
    bad = []
    asyncio.run(browser.plan(json.dumps({"text": "  "}), lambda e: bad.append(json.loads(e))))
    assert bad == [
        {
            "type": "error",
            "message": "The document is empty. Add a description of the app you want to build.",
        }
    ]
