import json
import re

from clarchy import catalog
from clarchy.cli import main
from clarchy.export import SCRIPT_TAG, build_site, site_data

SAMPLE_IDS = [sample_id for sample_id, _title, _text in catalog.samples()]


def embedded_data(page: str) -> dict:
    match = re.search(r"window\.CLARCHY_DATA = (\{.*?\});</script>", page, re.S)
    assert match, "data script missing"
    return json.loads(match.group(1))


def test_site_data_covers_patterns_samples_and_providers():
    data = site_data()
    keys = [*catalog.pattern_names(), *(f"sample:{s}" for s in SAMPLE_IDS)]
    assert set(data["designs"]) == {f"{k}.{p}" for k in keys for p in catalog.providers()}
    assert set(data["spec_index"].values()) == set(keys)
    assert set(data["pattern_yaml"]) == set(catalog.pattern_names())
    services = [c for c in catalog.capabilities().values() if c["tier"] != "external"]
    assert len(data["catalog"]["capabilities"]) == len(services)
    assert [s["id"] for s in data["samples"]] == SAMPLE_IDS


def test_recorded_runs_replay_the_whole_pipeline():
    data = site_data()
    for sample_id in SAMPLE_IDS:
        events = data["runs"][sample_id]["events"]
        done = [e["stage"] for e in events if e["type"] == "stage" and e["status"] == "done"]
        assert done == ["read", "understand", "design", "toolchain", "workflows", "map"]
        result = events[-1]
        assert result["type"] == "result" and result["mode"] == "rules"
        # The front end finds the rendered design by the exact spec text of the run.
        assert data["spec_index"][result["spec_yaml"]] == f"sample:{sample_id}"


def test_full_page_is_self_contained():
    page = build_site()
    assert page.startswith("<!doctype html>")
    assert "/static/" not in page
    # One data script plus every app script, and embedded SVG never ends a script early.
    assert page.count("<script>") == page.count("</script>") == 11
    data = embedded_data(page)
    assert data["designs"]["rag-chatbot.aws"]["svg"].startswith("<svg")
    assert "official_icons" in data["meta"]
    assert data["clipboard_only"] is False  # GitHub Pages and similar allow downloads
    # Scripts keep their order: the data first, then core, workspace, pages and boot.
    order = [
        "window.CLARCHY_DATA",
        "const CA = ",
        "class Workspace",
        "const Plan = ",
        "(async function main()",
    ]
    positions = [page.index(marker) for marker in order]
    assert positions == sorted(positions)


def test_fragment_has_no_document_skeleton():
    page = build_site(fragment=True)
    assert page.startswith("<title>")
    for tag in ("<!doctype", "<html", "<head>", "<body>"):
        assert tag not in page.lower()
    assert embedded_data(page)["clipboard_only"] is True  # sandboxed hosts block downloads


def test_page_has_pricing_and_sign_up_with_the_consent_wording_the_api_stores():
    from pathlib import Path

    page = build_site()
    for part in ('id="page-pricing"', 'id="signup-dialog"', 'id="limit-dialog"'):
        assert part in page
    # The updates box is unticked by default, and its words are exactly what the Worker
    # records as consent (worker/consent.mjs).
    box = re.search(
        r'<label class="check"><input type="checkbox" name="updates"><span>(.*?)</span>', page
    )
    assert box, "the updates box must be present and unticked"
    consent = Path(__file__).resolve().parents[1] / "worker" / "consent.mjs"
    stored = re.search(r'CONSENT_TEXT = "(.*?)";', consent.read_text()).group(1)
    assert box.group(1) == stored


def test_fragment_export_keeps_drawings_inline(tmp_path):
    from clarchy.export import export_site

    # Fragment hosts can't serve extra files, so nothing is fetched separately.
    export_site(tmp_path, fragment=True, with_engine=False)
    data = embedded_data((tmp_path / "index.html").read_text())
    assert data["designs"] and "design_files" not in data
    assert not (tmp_path / "designs").exists() and not (tmp_path / "404.html").exists()


def test_api_base_build_embeds_no_demo_data():
    page = build_site(api_base="https://api.example.org/")
    assert 'window.CLARCHY_API_BASE = "https://api.example.org";' in page
    assert "CLARCHY_DATA" not in page.split("<script>", 2)[1].split("</script>")[0]
    assert len(page) < 400_000


def test_index_scripts_are_all_found():
    from importlib import resources

    index = resources.files("clarchy").joinpath("static", "index.html").read_text()
    assert SCRIPT_TAG.findall(index) == [
        "core.js",
        "drafting.js",
        "workspace.js",
        "plan.js",
        "examples.js",
        "services.js",
        "blog.js",
        "howto.js",
        "access.js",
        "app.js",
    ]


def test_export_site_cli(tmp_path):
    assert main(["export-site", "-o", str(tmp_path)]) == 0
    assert (tmp_path / "index.html").read_text().startswith("<!doctype html>")


def test_site_ships_the_in_browser_engine(tmp_path):
    import subprocess
    import sys
    import zipfile

    from clarchy.export import ENGINE_BUNDLE, PYODIDE_VERSION, export_site

    export_site(tmp_path)
    data = embedded_data((tmp_path / "index.html").read_text())
    engine = data["engine"]
    assert engine["bundle"] == ENGINE_BUNDLE
    assert (
        engine["pyodide"] == f"https://cdn.jsdelivr.net/pyodide/v{PYODIDE_VERSION}/full/pyodide.js"
    )
    names = zipfile.ZipFile(tmp_path / ENGINE_BUNDLE).namelist()
    assert "clarchy/browser.py" in names and "clarchy/data/prices/aws.yaml" in names
    assert not any("/static/" in n or "__pycache__" in n for n in names)

    # The bundle alone is enough to run the engine (as Pyodide will).
    unpacked = tmp_path / "engine"
    zipfile.ZipFile(tmp_path / ENGINE_BUNDLE).extractall(unpacked)
    code = (
        "import sys, json; sys.path.insert(0, sys.argv[1]);"
        "import clarchy, clarchy.browser as b;"
        "assert clarchy.__file__.startswith(sys.argv[1]);"
        "from clarchy import catalog;"
        "r = json.loads(b.design(catalog.pattern_text('rag-chatbot'), 'gcp'));"
        "print(r['ok'], r['body']['cost']['available'])"
    )
    out = subprocess.run(
        [sys.executable, "-c", code, str(unpacked)], capture_output=True, text=True
    )
    assert out.stdout.strip() == "True True", out.stderr


def test_full_site_keeps_designs_fonts_and_sharing_files_beside_the_page(tmp_path):
    from clarchy.export import design_file, export_site

    export_site(tmp_path, with_engine=False)
    page = (tmp_path / "index.html").read_text()
    data = embedded_data(page)
    # The drawings load on demand, so the page stays small.
    assert "designs" not in data and data["design_files"] is True
    assert len(page) < 700_000
    for key in data["spec_index"].values():
        for provider in catalog.providers():
            body = json.loads((tmp_path / "designs" / design_file(f"{key}.{provider}")).read_text())
            assert body["svg"].startswith("<svg")
    # Fonts are served with the site, under their licences.
    assert "fonts.googleapis" not in page and 'url("fonts/archivo.woff2")' in page
    assert (tmp_path / "fonts" / "archivo.woff2").exists()
    assert (tmp_path / "fonts" / "LICENSE-archivo.txt").exists()
    # Search and link previews: the head keeps its description and sharing tags.
    assert '<meta name="description"' in page
    assert '<meta property="og:image" content="https://clarchy.com/og.png">' in page
    assert 'href="apple-touch-icon.png"' in page
    assert (tmp_path / "og.png").exists() and (tmp_path / "apple-touch-icon.png").exists()
    assert (tmp_path / "404.html").read_text().startswith("<!doctype html>")


def test_replay_only_build(tmp_path):
    from clarchy.export import ENGINE_BUNDLE, export_site

    export_site(tmp_path, with_engine=False)
    assert embedded_data((tmp_path / "index.html").read_text())["engine"] is None
    assert not (tmp_path / ENGINE_BUNDLE).exists()
