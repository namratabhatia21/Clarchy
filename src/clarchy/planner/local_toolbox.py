"""The agent's tools called in-process, with the same definitions as the MCP server.

Used where the MCP SDK is not available (the browser engine) or not installed. The tool
functions, schemas and error messages are the ones the MCP server exposes, so the agent
behaves the same either way.
"""

from __future__ import annotations

import json
from typing import Any

from clarchy.tools import AGENT_TOOL_NAMES, TOOLS, ToolError


class LocalToolbox:
    def __init__(self, names: tuple[str, ...] = AGENT_TOOL_NAMES):
        self.names = names
        self.definitions = [
            {
                "name": name,
                "description": TOOLS[name].description,
                "input_schema": TOOLS[name].input_schema,
                "strict": True,
            }
            for name in names
        ]

    async def __aenter__(self) -> LocalToolbox:
        return self

    async def __aexit__(self, *exc: Any) -> None:
        return None

    async def call(self, name: str, args: dict[str, Any]) -> tuple[str, bool]:
        if name not in self.names:
            return f"Unknown tool {name!r}.", True
        try:
            result = TOOLS[name](args)
        except ToolError as exc:
            return str(exc), True
        except TypeError as exc:  # missing or unexpected arguments
            return f"Invalid arguments for {name}: {exc}", True
        return json.dumps(result, ensure_ascii=False), False
