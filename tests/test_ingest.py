import io
import zipfile

import pytest
from helpers import make_docx, make_pdf, make_xlsx

from clarchy.ingest import (
    MAX_TEXT_CHARS,
    MAX_UPLOAD_BYTES,
    IngestError,
    from_text,
    read_document,
)


def test_word_paragraphs_and_tables():
    data = make_docx(
        ["Clinic booking", "Patients book appointments and pay a deposit."],
        table=[["Users", "120,000"], ["Region", "United States"]],
    )
    doc = read_document(data, "Brief.DOCX")
    assert doc.kind == "word" and doc.name == "Brief.DOCX"
    assert doc.text.splitlines() == [
        "Clinic booking",
        "Patients book appointments and pay a deposit.",
        "Users | 120,000",
        "Region | United States",
    ]
    assert doc.details == ["2 paragraphs", "1 table"]


def test_excel_sheets_shared_and_inline_strings():
    data = make_xlsx([["Need", "Users"], ["Sign in", 5000]], sheet="Needs")
    doc = read_document(data, "needs.xlsx")
    assert doc.kind == "excel"
    assert doc.text.splitlines() == ["## Needs", "Need | Users", "Sign in | 5000", "Inline note"]
    assert doc.details == ["1 sheet", "3 rows"]


def test_pdf_text_layer():
    pytest.importorskip("pypdf")
    doc = read_document(make_pdf("Fleet tracking for 8000 vans"), "spec.pdf")
    assert doc.kind == "pdf"
    assert "Fleet tracking for 8000 vans" in doc.text
    assert doc.details == ["1 page"]


def test_text_and_markdown_files():
    doc = read_document(b"# App\n\nUsers upload photos.", "notes.md")
    assert doc.kind == "text" and doc.words == 5


def test_typed_text():
    doc = from_text("  A booking app for clinics.  ")
    assert doc.text == "A booking app for clinics." and doc.name == "typed requirements"


@pytest.mark.parametrize(
    ("data", "name", "message"),
    [
        (b"MZ...", "setup.exe", "not supported"),
        (b"not a zip", "brief.docx", "not a valid Office document"),
        (b"   \n ", "empty.txt", "empty"),
        (b"x" * (MAX_UPLOAD_BYTES + 1), "big.txt", "larger than 10 MB"),
        (b"y" * (MAX_TEXT_CHARS + 1), "long.txt", "the limit is"),
    ],
)
def test_rejections_are_readable(data, name, message):
    with pytest.raises(IngestError, match=message):
        read_document(data, name)


def test_docx_without_body_is_rejected():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("other.xml", "<x/>")
    with pytest.raises(IngestError, match="no document body"):
        read_document(buffer.getvalue(), "odd.docx")


def test_zip_bombs_are_refused():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", "<a>" + "0" * (61 * 1024 * 1024) + "</a>")
    assert len(buffer.getvalue()) < MAX_UPLOAD_BYTES  # small on the wire
    with pytest.raises(IngestError, match="more than 60 MB"):
        read_document(buffer.getvalue(), "bomb.docx")
