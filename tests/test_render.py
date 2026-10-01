import os
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from cloudarchie import catalog
from cloudarchie.explain import explain_markdown
from cloudarchie.icons import IconLibrary
from cloudarchie.mapping import map_to_provider
from cloudarchie.render import render_svg
from cloudarchie.spec import load_pattern

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
UPDATE = os.environ.get("UPDATE_GOLDEN") == "1"
SVG_NS = "{http://www.w3.org/2000/svg}"


def arch(name, provider="aws"):
    return map_to_provider(load_pattern(name), provider)


def check_golden(path: Path, actual: str):
    if UPDATE:
        path.parent.mkdir(exist_ok=True)
        path.write_text(actual, encoding="utf-8")
    assert path.exists(), f"missing golden file {path}; run `make examples`"
    assert actual == path.read_text(encoding="utf-8"), (
        f"{path.name} changed; review the diff and run `make examples` if intended"
    )


@pytest.mark.parametrize("name", catalog.pattern_names())
def test_svg_is_well_formed_and_complete(name):
    a = arch(name)
    root = ET.fromstring(render_svg(a))
    assert root.tag == f"{SVG_NS}svg"
    text = " ".join("".join(t.itertext()) for t in root.iter(f"{SVG_NS}text"))
    for m in a.components:
        if m.choice:
            # Long names wrap, so check the first word of each service name.
            assert m.choice.service.split()[0] in text
    nodes = [g for g in root.iter(f"{SVG_NS}g") if g.get("class") == "node"]
    assert {g.get("data-id") for g in nodes} == {c.id for c in a.spec.components}


@pytest.mark.parametrize("name", catalog.pattern_names())
def test_render_is_deterministic(name):
    assert render_svg(arch(name)) == render_svg(arch(name))


@pytest.mark.parametrize("provider", catalog.providers())
@pytest.mark.parametrize("name", catalog.pattern_names())
def test_golden_svg(name, provider):
    check_golden(EXAMPLES / f"{name}.{provider}.svg", render_svg(arch(name, provider)))


@pytest.mark.parametrize("provider", catalog.providers())
@pytest.mark.parametrize("name", catalog.pattern_names())
def test_golden_explain(name, provider):
    check_golden(EXAMPLES / f"{name}.{provider}.md", explain_markdown(arch(name, provider)))


@pytest.mark.parametrize("provider", catalog.providers())
def test_nodes_do_not_overlap(provider):
    for name in catalog.pattern_names():
        root = ET.fromstring(render_svg(arch(name, provider)))
        rects = [
            tuple(float(r.get(k)) for k in ("x", "y", "width", "height"))
            for r in root.iter(f"{SVG_NS}rect")
            if r.get("class") == "node-box"
        ]
        for i, (x1, y1, w1, h1) in enumerate(rects):
            for x2, y2, w2, h2 in rects[i + 1 :]:
                apart = x1 + w1 <= x2 or x2 + w2 <= x1 or y1 + h1 <= y2 or y2 + h2 <= y1
                assert apart, f"{name}: overlapping nodes"


def test_platform_links_are_not_drawn_but_explained():
    a = arch("rag-chatbot")
    svg = render_svg(a)
    assert "verify token" not in svg
    assert "Chat API (streaming) → Amazon Cognito: verify token" in explain_markdown(a)


def test_official_icons_are_embedded_when_available(tmp_path):
    pkg = tmp_path / "Asset-Package" / "Arch_Storage" / "48"
    pkg.mkdir(parents=True)
    (pkg / "Arch_Amazon-Simple-Storage-Service_48.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg"/>'
    )
    (pkg / "Arch_Amazon-Simple-Storage-Service_16.svg").write_text("<svg/>")
    library = IconLibrary(tmp_path)

    found = library.find("Amazon-Simple-Storage-Service")
    assert found.name.endswith("_48.svg"), "prefers the 48px variant"
    assert library.find("Amazon-Simple-Storage") is None, "stems match whole segments only"

    a = arch("serverless-web-app")
    buckets = [m for m in a.components if m.component.capability == "object-storage"]
    svg = render_svg(a, library)
    assert svg.count("data:image/svg+xml;base64,") == len(buckets) == 1
    # Services without an installed icon fall back to lettered badges.
    assert ">CF</text>" in svg
