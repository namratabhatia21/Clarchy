"""Test helpers: tiny Office/PDF files built in memory, and a scripted model."""

from __future__ import annotations

import io
import json
import zipfile
from typing import Any

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
S_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


def _zip(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, text in files.items():
            archive.writestr(name, text)
    return buffer.getvalue()


def make_docx(paragraphs: list[str], table: list[list[str]] | None = None) -> bytes:
    def para(text: str) -> str:
        return f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>"

    body = "".join(para(p) for p in paragraphs)
    if table:
        rows = "".join(
            "<w:tr>" + "".join(f"<w:tc>{para(cell)}</w:tc>" for cell in row) + "</w:tr>"
            for row in table
        )
        body += f"<w:tbl>{rows}</w:tbl>"
    return _zip(
        {"word/document.xml": f'<w:document xmlns:w="{W_NS}"><w:body>{body}</w:body></w:document>'}
    )


def make_xlsx(rows: list[list[str | int]], sheet: str = "Requirements") -> bytes:
    shared: list[str] = []
    cells_xml = []
    for row in rows:
        cells = []
        for value in row:
            if isinstance(value, int):
                cells.append(f"<c><v>{value}</v></c>")
            else:
                shared.append(value)
                cells.append(f'<c t="s"><v>{len(shared) - 1}</v></c>')
        cells_xml.append(f"<row>{''.join(cells)}</row>")
    cells_xml.append('<row><c t="inlineStr"><is><t>Inline note</t></is></c></row>')
    return _zip(
        {
            "xl/workbook.xml": f'<workbook xmlns="{S_NS}" xmlns:r="{R_NS}"><sheets>'
            f'<sheet name="{sheet}" sheetId="1" r:id="rId1"/></sheets></workbook>',
            "xl/_rels/workbook.xml.rels": f'<Relationships xmlns="{PKG_NS}">'
            '<Relationship Id="rId1" Target="worksheets/sheet1.xml" Type="worksheet"/>'
            "</Relationships>",
            "xl/sharedStrings.xml": f'<sst xmlns="{S_NS}">'
            + "".join(f"<si><t>{s}</t></si>" for s in shared)
            + "</sst>",
            "xl/worksheets/sheet1.xml": f'<worksheet xmlns="{S_NS}"><sheetData>'
            + "".join(cells_xml)
            + "</sheetData></worksheet>",
        }
    )


def make_pdf(line: str) -> bytes:
    """A one-page PDF with a real text layer."""
    stream = f"BT /F1 12 Tf 72 720 Td ({line}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    for offset in offsets:
        out += b"%010d 00000 n \n" % offset
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        xref,
    )
    return bytes(out)


# --- a scripted model -----------------------------------------------------------------

POLICY_SPEC = """
name: Policy assistant
summary: Answers employee policy questions with cited sources.
requirements: {users: 2000, region: eu-west, compliance: [GDPR], monthly_budget_usd: 1500}
components:
  - {id: staff, capability: client, label: Employees (browser)}
  - id: chat
    capability: container-service
    label: Chat API
    rationale: Streams answers to the browser.
    evidence:
      - Responses should stream back to the browser as they are generated
      - an invented quote that is not in the document
  - {id: model, capability: llm-inference, label: Language model, rationale: Writes answers.}
  - {id: index, capability: vector-search, label: Policy index, rationale: Finds passages.}
  - {id: logs, capability: monitoring, label: Logs, rationale: Visibility.}
  - {id: build-it, capability: ci-build, label: A toolchain step the model should not add}
edges:
  - {from: staff, to: chat}
  - {from: chat, to: model, label: generate}
  - {from: chat, to: index, label: retrieve}
  - {from: build-it, to: chat}
"""


def tool_use(id_: str, name: str, args: dict[str, Any]) -> dict[str, Any]:
    return {"type": "tool_use", "id": id_, "name": name, "input": args}


class ScriptedLLM:
    """Plays back canned Messages API responses and records every request."""

    model = "scripted-model"
    label = "scripted model"

    def __init__(self, design_turns: list[list[dict[str, Any]]] | None = None, stop_reason=None):
        self.design_turns = (
            design_turns
            if design_turns is not None
            else [
                [tool_use("t1", "list_patterns", {})],
                [
                    tool_use("t2", "get_pattern", {"pattern_id": "rag-chatbot"}),
                    tool_use("t3", "search_services", {"query": "vector", "provider": "aws"}),
                ],
                [
                    tool_use(
                        "t4",
                        "submit_design",
                        {"spec_yaml": "name: x\ncomponents: [{id: a, capability: teleporter}]"},
                    )
                ],
                [tool_use("t5", "submit_design", {"spec_yaml": POLICY_SPEC})],
            ]
        )
        self.stop_reason = stop_reason
        self.calls: list[dict[str, Any]] = []

    async def create(self, **params: Any) -> dict[str, Any]:
        self.calls.append(json.loads(json.dumps(params)))  # a snapshot, not a live reference
        fmt = (params.get("output_config") or {}).get("format")
        if self.stop_reason:
            return {"content": [], "stop_reason": self.stop_reason}
        if fmt and "app_name" in fmt["schema"]["properties"]:
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
                "features": [
                    {
                        "need": "cited answers",
                        "quote": "answers must cite the policy documents they come from",
                    },
                    {"need": "made up", "quote": "this sentence is not in the document"},
                ],
                "assumptions": ["One region is enough."],
                "open_questions": ["Which single sign-on provider?"],
            }
            return {
                "content": [{"type": "text", "text": json.dumps(data)}],
                "stop_reason": "end_turn",
            }
        if fmt:
            data = {
                "workflows": [
                    {
                        "name": "Answering a question",
                        "kind": "request",
                        "steps": [
                            {
                                "text": "An employee asks a question.",
                                "components": ["staff", "chat"],
                            },
                            {"text": "The API finds passages.", "components": ["chat", "index"]},
                        ],
                    }
                ]
            }
            return {
                "content": [{"type": "text", "text": json.dumps(data)}],
                "stop_reason": "end_turn",
            }
        blocks = self.design_turns.pop(0) if self.design_turns else []
        thinking = {
            "type": "thinking",
            "thinking": "Checking the closest pattern.",
            "signature": "s",
        }
        return {
            "content": [thinking, *blocks],
            "stop_reason": "tool_use" if blocks else "end_turn",
        }
