"""Tools the planning agent can call, served over MCP.

The agent is an MCP client: it connects to Clarchy's own MCP server (in memory, no
subprocess) and, optionally, to extra MCP servers you name, such as a pricing server.
Whatever those servers expose becomes available to the model.
"""

from __future__ import annotations

import json
import shlex
from contextlib import AsyncExitStack
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.shared.memory import create_connected_server_and_client_session

from clarchy.mcp_server import build_server
from clarchy.tools import AGENT_TOOL_NAMES


def strict_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Normalise a JSON schema for strict tool use: no titles, every property required,
    no additional properties."""
    if not isinstance(schema, dict):
        return schema
    out = {k: strict_schema(v) for k, v in schema.items() if k != "title"}
    if out.get("type") == "object":
        props = out.get("properties", {})
        out["properties"] = {k: strict_schema(v) for k, v in props.items()}
        out["required"] = list(out["properties"])
        out["additionalProperties"] = False
    return out


class MCPToolbox:
    """Async context manager: `async with MCPToolbox() as tools: ...`."""

    def __init__(self, extra_servers: list[str] | None = None):
        self.extra_servers = extra_servers or []
        self._stack = AsyncExitStack()
        self._routes: dict[str, ClientSession] = {}
        self.definitions: list[dict[str, Any]] = []

    async def __aenter__(self) -> MCPToolbox:
        own = await self._stack.enter_async_context(
            create_connected_server_and_client_session(build_server())
        )
        await self._add(own, allowed=set(AGENT_TOOL_NAMES), strict=True, prefix="")
        for n, command in enumerate(self.extra_servers, start=1):
            argv = shlex.split(command)
            params = StdioServerParameters(command=argv[0], args=argv[1:])
            read, write = await self._stack.enter_async_context(stdio_client(params))
            session = await self._stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            await self._add(session, allowed=None, strict=False, prefix=f"ext{n}_")
        return self

    async def __aexit__(self, *exc) -> None:
        await self._stack.aclose()

    async def _add(self, session: ClientSession, allowed, strict: bool, prefix: str) -> None:
        listed = await session.list_tools()
        for tool in listed.tools:
            if allowed is not None and tool.name not in allowed:
                continue
            name = f"{prefix}{tool.name}"[:64]
            schema = tool.inputSchema or {"type": "object", "properties": {}}
            definition = {
                "name": name,
                "description": tool.description or tool.name,
                "input_schema": strict_schema(schema) if strict else schema,
            }
            if strict:
                definition["strict"] = True
            self.definitions.append(definition)
            self._routes[name] = (session, tool.name)

    async def call(self, name: str, args: dict[str, Any]) -> tuple[str, bool]:
        """Run a tool; returns (text result, is_error)."""
        if name not in self._routes:
            return f"Unknown tool {name!r}.", True
        session, remote_name = self._routes[name]
        result = await session.call_tool(remote_name, args)
        if result.structuredContent is not None and not result.isError:
            data = result.structuredContent
            if set(data) == {"result"}:  # FastMCP wraps non-object return values
                data = data["result"]
            return json.dumps(data, ensure_ascii=False), False
        text = "\n".join(getattr(c, "text", "") for c in result.content)
        return text, bool(result.isError)
