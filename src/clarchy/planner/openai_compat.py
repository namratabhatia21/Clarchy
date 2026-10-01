"""Open-source models for the planner, through any OpenAI-compatible chat endpoint.

    Hugging Face Inference Providers   https://router.huggingface.co/v1   (HF_TOKEN)
    Ollama on your machine             http://localhost:11434/v1
    vLLM, LM Studio, llama.cpp server  their /v1 endpoint

The agent speaks the Messages API shape (system blocks, tool_use / tool_result blocks,
structured outputs); this adapter translates each request to chat completions and the
reply back, so the same agent loop and guardrails run on Claude or on an open model.
Structured outputs are requested as a JSON schema and fall back to plain JSON mode for
servers that do not support schemas. It works in a normal Python process and inside the
browser (Pyodide), where requests go through the browser's fetch.
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
import urllib.error
import urllib.request
import uuid
from typing import Any

from clarchy.planner.llm import LLMError

HUGGING_FACE_URL = "https://router.huggingface.co/v1"
HUGGING_FACE_MODEL = "Qwen/Qwen2.5-72B-Instruct"
OLLAMA_URL = "http://localhost:11434/v1"
OLLAMA_MODEL = "qwen2.5:7b"
MAX_OUTPUT_TOKENS = 6000
THINK = re.compile(r"<think>(.*?)</think>", re.S)


def _text_of(content: Any) -> str:
    if isinstance(content, str):
        return content
    return "".join(
        b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"
    )


def to_chat(params: dict[str, Any], model: str) -> dict[str, Any]:
    """Messages API parameters -> chat completions request body."""
    system = _text_of(params.get("system") or "")
    fmt = (params.get("output_config") or {}).get("format")
    if fmt:
        system += (
            "\n\nReply with one JSON object only, no other text, matching this JSON schema:\n"
            + json.dumps(fmt["schema"])
        )
    messages: list[dict[str, Any]] = [{"role": "system", "content": system}] if system else []
    for message in params["messages"]:
        content = message["content"]
        if message["role"] == "assistant":
            blocks = content if isinstance(content, list) else [{"type": "text", "text": content}]
            calls = [
                {
                    "id": b["id"],
                    "type": "function",
                    "function": {"name": b["name"], "arguments": json.dumps(b.get("input") or {})},
                }
                for b in blocks
                if b.get("type") == "tool_use"
            ]
            out: dict[str, Any] = {"role": "assistant", "content": _text_of(blocks) or None}
            if calls:
                out["tool_calls"] = calls
            messages.append(out)
            continue
        if isinstance(content, str):
            messages.append({"role": "user", "content": content})
            continue
        for block in content:
            if block.get("type") == "tool_result":
                text = block.get("content")
                text = text if isinstance(text, str) else _text_of(text or [])
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": block["tool_use_id"],
                        "content": ("Error: " if block.get("is_error") else "") + text,
                    }
                )
        text = _text_of(content)
        if text:
            messages.append({"role": "user", "content": text})
    body: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": min(int(params.get("max_tokens") or 4000), MAX_OUTPUT_TOKENS),
        "temperature": 0.2,
    }
    if params.get("tools"):
        body["tools"] = [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": t.get("input_schema") or {"type": "object", "properties": {}},
                },
            }
            for t in params["tools"]
        ]
    if fmt:
        body["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": "result", "schema": fmt["schema"], "strict": True},
        }
    return body


def from_chat(data: dict[str, Any]) -> dict[str, Any]:
    """Chat completions response -> Messages API shaped dict."""
    choice = (data.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    blocks: list[dict[str, Any]] = []
    reasoning = message.get("reasoning_content") or message.get("reasoning") or ""
    text = message.get("content") or ""
    thoughts = THINK.findall(text)
    text = THINK.sub("", text).strip()
    reasoning = "\n".join(filter(None, [reasoning.strip(), *[t.strip() for t in thoughts]]))
    if reasoning:
        blocks.append({"type": "thinking", "thinking": reasoning, "signature": ""})
    if text:
        blocks.append({"type": "text", "text": text})
    for call in message.get("tool_calls") or []:
        fn = call.get("function") or {}
        try:
            args = json.loads(fn.get("arguments") or "{}")
        except json.JSONDecodeError:
            args = {}
        blocks.append(
            {
                "type": "tool_use",
                "id": call.get("id") or f"call_{uuid.uuid4().hex[:12]}",
                "name": fn.get("name", ""),
                "input": args if isinstance(args, dict) else {},
            }
        )
    finish = choice.get("finish_reason")
    if any(b["type"] == "tool_use" for b in blocks):
        stop = "tool_use"
    else:
        stop = {"length": "max_tokens", "content_filter": "refusal"}.get(finish, "end_turn")
    return {"content": blocks, "stop_reason": stop}


class OpenAICompatLLM:
    """Implements the planner's LLM interface on an OpenAI-compatible endpoint."""

    def __init__(
        self,
        model: str,
        base_url: str,
        api_key: str | None = None,
        label: str | None = None,
        transport: Any = None,
    ):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.label = label or f"{model} ({self.base_url})"
        self._transport = transport or _default_transport()

    async def _post(self, body: dict[str, Any]) -> tuple[int, Any]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return await self._transport(f"{self.base_url}/chat/completions", headers, body)

    async def create(self, **params: Any) -> dict[str, Any]:
        body = to_chat(params, self.model)
        status, data = await self._post(body)
        if status in (400, 404, 422) and "response_format" in body:
            # Not every server supports JSON schemas: try JSON mode, then plain text.
            body["response_format"] = {"type": "json_object"}
            status, data = await self._post(body)
            if status in (400, 404, 422):
                body.pop("response_format")
                status, data = await self._post(body)
        if status == 401 or status == 403:
            raise LLMError("The model provider rejected the access token.")
        if status == 429:
            raise LLMError("The model provider's rate limit was reached; try again shortly.")
        if status >= 400 or not isinstance(data, dict):
            detail = data.get("error") if isinstance(data, dict) else data
            if isinstance(detail, dict):
                detail = detail.get("message")
            raise LLMError(f"The model provider returned an error ({status}): {str(detail)[:200]}")
        return from_chat(data)


def _default_transport():
    if sys.platform == "emscripten":  # Pyodide: use the browser's fetch
        return _fetch_transport
    return _urllib_transport


async def _urllib_transport(url: str, headers: dict[str, str], body: dict[str, Any]):
    def call() -> tuple[int, Any]:
        request = urllib.request.Request(url, json.dumps(body).encode(), headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                return response.status, json.loads(response.read() or b"null")
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            try:
                return exc.code, json.loads(raw)
            except ValueError:
                return exc.code, raw.decode(errors="replace")
        except (urllib.error.URLError, TimeoutError) as exc:
            raise LLMError(f"Could not reach the model provider at {url}: {exc}") from exc

    return await asyncio.to_thread(call)


async def _fetch_transport(url: str, headers: dict[str, str], body: dict[str, Any]):
    from pyodide.http import pyfetch  # only inside Pyodide

    try:
        response = await pyfetch(url, method="POST", headers=headers, body=json.dumps(body))
    except Exception as exc:  # the browser reports network and CORS failures alike
        raise LLMError(f"Could not reach the model provider: {exc}") from exc
    text = await response.string()
    try:
        return response.status, json.loads(text) if text else None
    except ValueError:
        return response.status, text
