import json
import re

from cloudarchie import catalog
from cloudarchie.cli import main
from cloudarchie.export import build_site, site_data


def embedded_data(page: str) -> dict:
    match = re.search(r"window\.CLOUDARCHIE_DATA = (\{.*?\});</script>", page, re.S)
    assert match, "data script missing"
    return json.loads(match.group(1))


def test_site_data_covers_every_pattern_and_provider():
    data = site_data()
    expected = {f"{n}.{p}" for n in catalog.pattern_names() for p in catalog.providers()}
    assert set(data["designs"]) == expected
    assert set(data["pattern_yaml"]) == set(catalog.pattern_names())
    assert len(data["catalog"]["capabilities"]) == 22


def test_full_page_is_self_contained():
    page = build_site()
    assert page.startswith("<!doctype html>")
    assert "/static/" not in page
    # Embedded SVG must not end the data script early.
    assert page.count("</script>") == 2
    data = embedded_data(page)
    assert data["designs"]["rag-chatbot.aws"]["svg"].startswith("<svg")
    assert "official_icons" in data["meta"]
    assert data["clipboard_only"] is False  # GitHub Pages and similar allow downloads


def test_fragment_has_no_document_skeleton():
    page = build_site(fragment=True)
    assert page.startswith("<title>")
    for tag in ("<!doctype", "<html", "<head>", "<body>"):
        assert tag not in page.lower()
    assert embedded_data(page)["clipboard_only"] is True  # sandboxed hosts block downloads


def test_export_site_cli(tmp_path):
    assert main(["export-site", "-o", str(tmp_path)]) == 0
    assert (tmp_path / "index.html").read_text().startswith("<!doctype html>")
