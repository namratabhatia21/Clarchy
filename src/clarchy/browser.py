"""Entry points for the in-browser engine.

The static site loads Pyodide (Python compiled to WebAssembly) and this package, then
calls these functions from JavaScript, so the public site plans any typed text or
uploaded document with the same code as `clarchy serve`, without a server:

    plan(request_json, emit)      run the pipeline; emit(json) receives every event
    design(spec_yaml, provider)   one design on one provider, as the /api/design body

An open-source model on Hugging Face can do the AI steps with the visitor's own token;
requests then go straight from the browser to Hugging Face.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from clarchy import payloads
from clarchy.ingest import IngestError, from_text, read_document
from clarchy.planner import PlanError, PlanOptions, run_plan
from clarchy.planner.answers import AnswerError, parse_answers
from clarchy.planner.openai_compat import (
    HUGGING_FACE_MODEL,
    HUGGING_FACE_URL,
    OpenAICompatLLM,
)


async def plan(request_json: str, emit: Any) -> None:
    """request: {text | file_path + file_name, mode: "rules" | "hf", region,
    hf: {token, model, base_url}, answers: [{question, answer}]}"""
    request = json.loads(request_json)

    def send(event: dict[str, Any]) -> None:
        emit(json.dumps(event, ensure_ascii=False))

    try:
        answers = parse_answers(request.get("answers"))
        if request.get("file_path"):
            data = Path(request["file_path"]).read_bytes()
            doc = read_document(data, request.get("file_name") or "document")
        else:
            doc = from_text(request.get("text") or "")
    except (IngestError, AnswerError) as exc:
        send({"type": "error", "message": str(exc)})
        return

    llm = None
    if request.get("mode") == "hf":
        hf = request.get("hf") or {}
        model = (hf.get("model") or HUGGING_FACE_MODEL).strip()
        base_url = (hf.get("base_url") or HUGGING_FACE_URL).strip()
        where = "Hugging Face" if base_url == HUGGING_FACE_URL else urlsplit(base_url).netloc
        llm = OpenAICompatLLM(model, base_url, hf.get("token") or None, f"{model} ({where})")
    options = PlanOptions(
        mode="ai" if llm else "rules",
        region=request.get("region") or None,
        toolbox="local",
        answers=answers,
    )
    try:
        await run_plan(doc, options, llm, send)
    except PlanError as exc:
        send({"type": "error", "message": str(exc)})
    except Exception as exc:  # runs in the visitor's own browser; show what went wrong
        send({"type": "error", "message": f"Planning failed: {exc}"})


def design(spec_yaml: str, provider: str) -> str:
    status, body = payloads.design_payload(spec_yaml, provider)
    return json.dumps({"ok": status == 200, "body": body}, ensure_ascii=False)
