"""Progress events streamed to the UI while a plan runs.

Every event is a small JSON-serialisable dict with a "type":
  stage        {stage, status: running|done|error|skipped, title, detail, items?}
  tool_call    {stage, name, summary}
  tool_result  {stage, name, ok, summary}
  note         {stage, text}              the agent's summarised reasoning
  result       {spec_yaml, mode, model}
  error        {message}
"""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from typing import Any

Event = dict[str, Any]
EmitFn = Callable[[Event], Awaitable[None] | None]

STAGES = {
    "read": "Read the requirements",
    "understand": "Understand what's needed",
    "design": "Design the architecture",
    "toolchain": "Add build and deploy",
    "workflows": "Describe the workflows",
    "map": "Map to every cloud",
}


class Emitter:
    def __init__(self, fn: EmitFn | None = None):
        self._fn = fn
        self.events: list[Event] = []

    async def emit(self, event: Event) -> None:
        self.events.append(event)
        if self._fn is not None:
            result = self._fn(event)
            if inspect.isawaitable(result):
                await result

    async def stage(
        self,
        stage: str,
        status: str,
        detail: str = "",
        items: list[str] | None = None,
    ) -> None:
        event: Event = {"type": "stage", "stage": stage, "status": status, "title": STAGES[stage]}
        if detail:
            event["detail"] = detail
        if items:
            event["items"] = items
        await self.emit(event)

    async def tool_call(self, stage: str, name: str, summary: str) -> None:
        await self.emit({"type": "tool_call", "stage": stage, "name": name, "summary": summary})

    async def tool_result(self, stage: str, name: str, ok: bool, summary: str) -> None:
        await self.emit(
            {"type": "tool_result", "stage": stage, "name": name, "ok": ok, "summary": summary}
        )

    async def note(self, stage: str, text: str) -> None:
        await self.emit({"type": "note", "stage": stage, "text": text})
