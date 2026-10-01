"""Turns an uploaded requirements document into plain text.

Supported: .txt .md .csv .json .yaml (as text), .docx (Word), .xlsx (Excel) and .pdf.
Word and Excel files are read with the standard library (they are zipped XML); PDFs need
the optional `pypdf` package (`pip install "cloudarchie[ingest]"`). Limits protect the
server from oversized or zip-bomb uploads, and long documents are refused with a clear
message rather than silently cut short.
"""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass, field
from pathlib import PurePath
from xml.etree import ElementTree as ET

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_UNZIPPED_BYTES = 60 * 1024 * 1024
MAX_TEXT_CHARS = 120_000

TEXT_TYPES = {".txt", ".md", ".markdown", ".csv", ".json", ".yaml", ".yml"}
SUPPORTED = sorted(TEXT_TYPES | {".docx", ".xlsx", ".pdf"})

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
S = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
R_ID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
PKG_REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"


class IngestError(ValueError):
    """The document can't be read; the message tells the user what to do."""


@dataclass
class Document:
    text: str
    kind: str
    name: str
    details: list[str] = field(default_factory=list)

    @property
    def words(self) -> int:
        return len(self.text.split())


def _count(n: int, word: str) -> str:
    return f"{n:,} {word}" + ("" if n == 1 else "s")


def _zip(data: bytes) -> zipfile.ZipFile:
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise IngestError("The file is not a valid Office document.") from exc
    if sum(info.file_size for info in archive.infolist()) > MAX_UNZIPPED_BYTES:
        raise IngestError("The document expands to more than 60 MB, which is too large.")
    return archive


def _xml(archive: zipfile.ZipFile, name: str) -> ET.Element | None:
    try:
        return ET.fromstring(archive.read(name))
    except KeyError:
        return None


def _docx(data: bytes) -> tuple[str, list[str]]:
    root = _xml(_zip(data), "word/document.xml")
    if root is None:
        raise IngestError("This .docx has no document body.")
    body = root.find(f"{W}body")
    lines, paragraphs, tables = [], 0, 0

    def paragraph_text(p: ET.Element) -> str:
        return "".join(t.text or "" for t in p.iter(f"{W}t")).strip()

    for child in list(body) if body is not None else []:
        if child.tag == f"{W}p":
            text = paragraph_text(child)
            if text:
                lines.append(text)
                paragraphs += 1
        elif child.tag == f"{W}tbl":
            tables += 1
            for row in child.iter(f"{W}tr"):
                cells = [
                    " ".join(paragraph_text(p) for p in cell.iter(f"{W}p")).strip()
                    for cell in row.iter(f"{W}tc")
                ]
                if any(cells):
                    lines.append(" | ".join(cells))
    details = [_count(paragraphs, "paragraph")] + ([_count(tables, "table")] if tables else [])
    return "\n".join(lines), details


def _xlsx(data: bytes) -> tuple[str, list[str]]:
    archive = _zip(data)
    shared: list[str] = []
    strings = _xml(archive, "xl/sharedStrings.xml")
    if strings is not None:
        for item in strings.iter(f"{S}si"):
            shared.append("".join(t.text or "" for t in item.iter(f"{S}t")))
    workbook = _xml(archive, "xl/workbook.xml")
    rels = _xml(archive, "xl/_rels/workbook.xml.rels")
    if workbook is None or rels is None:
        raise IngestError("This .xlsx has no workbook.")
    targets = {r.get("Id"): r.get("Target", "") for r in rels.iter(f"{PKG_REL}Relationship")}

    lines, sheets = [], 0
    for sheet in workbook.iter(f"{S}sheet"):
        target = targets.get(sheet.get(R_ID), "")
        path = target.lstrip("/") if target.startswith("/") else f"xl/{target}"
        root = _xml(archive, path)
        if root is None:
            continue
        sheets += 1
        lines.append(f"## {sheet.get('name', 'Sheet')}")
        for row in root.iter(f"{S}row"):
            values = []
            for cell in row.iter(f"{S}c"):
                kind, v = cell.get("t"), cell.find(f"{S}v")
                if kind == "s" and v is not None and v.text is not None:
                    index = int(v.text)
                    values.append(shared[index] if index < len(shared) else "")
                elif kind == "inlineStr":
                    values.append("".join(t.text or "" for t in cell.iter(f"{S}t")))
                elif v is not None and v.text is not None:
                    values.append(v.text)
            if any(x.strip() for x in values):
                lines.append(" | ".join(x.strip() for x in values))
    return "\n".join(lines), [_count(sheets, "sheet"), _count(len(lines) - sheets, "row")]


def _pdf(data: bytes) -> tuple[str, list[str]]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise IngestError(
            'Reading PDFs needs the optional pypdf package: pip install "cloudarchie[ingest]".'
        ) from exc
    try:
        reader = PdfReader(io.BytesIO(data))
        pages = [page.extract_text() or "" for page in reader.pages]
    except Exception as exc:  # pypdf raises many types for damaged files
        raise IngestError(f"The PDF could not be read ({exc.__class__.__name__}).") from exc
    text = "\n".join(p.strip() for p in pages if p.strip())
    if not text:
        raise IngestError(
            "This PDF has no text layer (it may be a scan). Paste the text or upload a Word file."
        )
    return text, [_count(len(pages), "page")]


def read_document(data: bytes, filename: str) -> Document:
    if len(data) > MAX_UPLOAD_BYTES:
        raise IngestError("The file is larger than 10 MB. Upload a smaller document.")
    suffix = PurePath(filename).suffix.lower()
    if suffix in TEXT_TYPES:
        text, details, kind = data.decode("utf-8", errors="replace"), [], "text"
    elif suffix == ".docx":
        (text, details), kind = _docx(data), "word"
    elif suffix == ".xlsx":
        (text, details), kind = _xlsx(data), "excel"
    elif suffix == ".pdf":
        (text, details), kind = _pdf(data), "pdf"
    else:
        raise IngestError(
            f"{suffix or 'This file type'} is not supported. Use one of: {', '.join(SUPPORTED)}."
        )
    return _checked(Document(text=text.strip(), kind=kind, name=filename, details=details))


def from_text(text: str) -> Document:
    return _checked(Document(text=text.strip(), kind="typed", name="typed requirements"))


def _checked(doc: Document) -> Document:
    if not doc.text:
        raise IngestError("The document is empty. Add a description of the app you want to build.")
    if len(doc.text) > MAX_TEXT_CHARS:
        raise IngestError(
            f"The document has {len(doc.text):,} characters; the limit is {MAX_TEXT_CHARS:,}. "
            "Upload the requirements section only."
        )
    return doc
