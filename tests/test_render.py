import base64
import os
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from clarchy import catalog
from clarchy.explain import explain_markdown
from clarchy.icons import IconLibrary, bundled_icon_dir, bundled_library, icon_library
from clarchy.mapping import map_to_provider
from clarchy.render import render_svg
from clarchy.spec import load_pattern

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
            if r.get("class") == "ca-node-box"
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


def test_every_aws_service_has_its_bundled_aws_icon():
    library = bundled_library("aws")
    services = catalog.provider_mapping("aws")["services"]
    # Icons are only for AWS services: KEDA and GitHub keep their lettered badges.
    no_icon = sorted(raw["service"] for raw in services.values() if "icon" not in raw)
    assert no_icon == ["GitHub or GitLab via AWS CodeConnections", "KEDA on Amazon EKS"]
    stems = [raw["icon"] for raw in services.values() if "icon" in raw]
    missing = [stem for stem in stems if library.find(stem) is None]
    assert not missing, f"no bundled icon for {missing}"
    root = bundled_icon_dir("aws")
    assert (root / "NOTICE.md").is_file(), "the icons travel with their terms"
    used = {library.find(stem).name for stem in stems}
    assert {p.name for p in root.glob("*.svg")} == used, "ship only the icons Clarchy draws"


def test_aws_diagrams_embed_the_icon_files_unchanged():
    a = arch("serverless-web-app")
    svg = render_svg(a, icon_library("aws"))
    bucket = bundled_library("aws").find("Amazon-Simple-Storage-Service")
    assert bucket.name == "Arch_Amazon-Simple-Storage-Service_64.svg"
    encoded = base64.b64encode(bucket.read_bytes()).decode("ascii")
    assert f'href="data:image/svg+xml;base64,{encoded}"' in svg
    assert "Service names and icons belong to their owners" in svg
    assert "not affiliated with AWS" in svg
    badges = sum(1 for m in a.components if m.choice and not m.choice.icon)
    assert svg.count('class="ca-badge"') == badges, "every AWS service drew its icon"


def test_every_drawn_azure_service_has_its_bundled_azure_icon():
    library = bundled_library("azure")
    services = catalog.provider_mapping("azure")["services"]
    stems = [raw["icon"] for raw in services.values() if "icon" in raw]
    assert len(stems) >= 30
    assert not [s for s in stems if library.find(s) is None]
    root = bundled_icon_dir("azure")
    assert (root / "NOTICE.md").is_file()
    used = {library.find(stem).name for stem in stems}
    assert {p.name for p in root.glob("*.svg")} == used, "ship only the icons Clarchy draws"
    # Not Azure's products, or not in this icon release: lettered badges.
    no_icon = {raw["service"] for raw in services.values() if "icon" not in raw}
    assert {"GitHub Copilot", "GitHub Codespaces", "KEDA add-on for AKS", "Bicep"} <= no_icon
    a = arch("serverless-web-app", "azure")
    svg = render_svg(a, icon_library("azure"))
    functions = library.find("10029-icon-service-Function-Apps")
    assert base64.b64encode(functions.read_bytes()).decode("ascii") in svg
    assert "not affiliated with Azure" in svg


@pytest.mark.parametrize("provider", catalog.providers())
def test_every_provider_ships_exactly_the_icons_it_draws(provider):
    library = bundled_library(provider)
    root = bundled_icon_dir(provider)
    assert (root / "NOTICE.md").is_file(), "the icons travel with their terms"
    services = catalog.provider_mapping(provider)["services"]
    stems = [raw["icon"] for raw in services.values() if "icon" in raw]
    assert not [s for s in stems if library.find(s) is None], "every named icon exists"
    own = {library.find(s).name for s in stems if not s.startswith("oss:")}
    files = {p.name for p in root.iterdir() if p.suffix in (".svg", ".png")}
    assert files == own, "ship only the icons Clarchy draws"


def test_gcp_and_open_source_diagrams_draw_their_icons():
    gcp = render_svg(arch("rag-chatbot", "gcp"), icon_library("gcp"))
    run = bundled_library("gcp").find("cloudrun-512-color-rgb")
    assert base64.b64encode(run.read_bytes()).decode("ascii") in gcp
    oss = render_svg(arch("rag-chatbot", "oss"), icon_library("oss"))
    postgres = bundled_library("oss").find("postgresql")
    assert base64.b64encode(postgres.read_bytes()).decode("ascii") in oss
    assert "not affiliated with these projects" in oss
    # A cloud diagram can borrow a project's logo: LiteLLM on Cloud Run.
    litellm = bundled_library("oss").find("litellm")
    assert icon_library("gcp").find("oss:litellm") == litellm
    # Without icons (golden files) nothing is borrowed either.
    assert IconLibrary(None).find("oss:litellm") is None


def test_an_icon_folder_given_by_the_user_wins(tmp_path, monkeypatch):
    monkeypatch.setenv("CLARCHY_ICONS_AWS", str(tmp_path))
    assert icon_library("aws").root == tmp_path
    monkeypatch.delenv("CLARCHY_ICONS_AWS")
    assert icon_library("aws").root == bundled_icon_dir("aws")


@pytest.mark.parametrize("provider", catalog.providers())
def test_styles_are_scoped_so_diagrams_can_share_a_page(provider):
    """Inline SVG <style> is global in HTML: every rule must be scoped to this provider's
    diagram, and nothing may rely on document-wide ids such as arrow markers."""
    svg = render_svg(arch("kubernetes-microservices", provider))
    root = ET.fromstring(svg)
    assert root.get("class") == f"ca-diagram ca-{provider}"
    style = root.find(f"{SVG_NS}style").text
    rules = [r.strip() for r in style.split("}") if r.strip()]
    for rule in rules:
        selectors = rule.split("{")[0].split(",")
        assert all(sel.strip().startswith(f".ca-{provider}") for sel in selectors), rule
    assert " id=" not in svg and "<marker" not in svg


def test_every_drawn_edge_has_an_arrowhead():
    root = ET.fromstring(render_svg(arch("kubernetes-microservices")))
    edges = [
        (e.get("data-from"), e.get("data-to"))
        for e in root.iter(f"{SVG_NS}path")
        if e.get("class") == "ca-edge"
    ]
    arrows = [
        (a.get("data-from"), a.get("data-to"))
        for a in root.iter(f"{SVG_NS}polygon")
        if a.get("class") == "ca-arrow"
    ]
    assert edges and sorted(edges) == sorted(arrows)


def test_build_and_deploy_lane_is_drawn_above_the_runtime():
    a = arch("kubernetes-microservices")
    root = ET.fromstring(render_svg(a))
    y = {
        g.get("data-id"): float(g.find(f"{SVG_NS}rect").get("y"))
        for g in root.iter(f"{SVG_NS}g")
        if g.get("class") == "node"
    }
    delivery = [m.component.id for m in a.components if m.component.tier == "delivery"]
    runtime = [m.component.id for m in a.components if m.component.tier in ("compute", "data")]
    assert max(y[d] for d in delivery) < min(y[r] for r in runtime)
