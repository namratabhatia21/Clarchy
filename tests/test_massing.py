"""The massing model: a design's running services as blocks, as tall as they cost."""

import re

import pytest

from clarchy import catalog, massing, pricing
from clarchy.icons import IconLibrary, bundled_library
from clarchy.mapping import map_to_provider
from clarchy.spec import load_pattern


def model(name="rag-chatbot", provider="aws", icons=None):
    arch = map_to_provider(load_pattern(name), provider)
    cost = pricing.estimate(arch)
    if not cost.get("available"):
        cost = {"lines": [], "price_region": arch.region_label}
    return arch, cost, massing.svg(arch, cost, icons or bundled_library(provider))


def test_every_running_service_is_a_block_as_tall_as_it_costs():
    arch, cost, _svg = model()
    blocks, width, depth = massing.layout(arch, cost)
    running = [
        m.component.id
        for m in arch.components
        if m.choice and m.component.stage in (*massing.COLUMNS, "operate")
    ]
    assert sorted(b.id for b in blocks) == sorted(running)
    by_cost = sorted(blocks, key=lambda b: b.monthly)
    assert [b.h for b in by_cost] == sorted(b.h for b in by_cost), "dearer is taller"
    assert by_cost[0].h == pytest.approx(massing.LOW) or by_cost[0].monthly > 0
    # Everything stands on the base; operate runs along the front edge.
    for b in blocks:
        assert b.x > 0 and b.x + massing.BLOCK < width, b.id
        assert b.y > 0 and b.y + massing.BLOCK < depth, b.id
    front = max(b.y for b in blocks)
    assert {b.id for b in blocks if b.y == front} == {
        m.component.id for m in arch.components if m.choice and m.component.stage == "operate"
    }


def test_callouts_name_the_costliest_services_without_crossing():
    arch, cost, svg = model()
    names = re.findall(r'class="m-name"[^>]*>([^<]+)<', svg)
    assert names[0].startswith("VECTOR SEARCH · $350") or "VECTOR SEARCH" in " ".join(names)
    assert 1 <= len(names) <= massing.CALLOUTS
    total = sum(line["monthly"] for line in cost["lines"])
    for name in names:
        value = float(name.rsplit("$", 1)[1].split("/")[0].replace(",", ""))
        assert value >= massing.SHARE * total * 0.99
    # No label sits across another callout's leader.
    callouts = re.findall(
        r'<path class="m-leader" d="M([\d.-]+) [\d.-]+V([\d.-]+)"/>.*?'
        r'<text class="m-name" x="([\d.-]+)" y="([\d.-]+)"[^>]*>([^<]+)<',
        svg,
    )
    for bx, _top, tx, ty, text in callouts:
        x0, x1, y = float(tx), float(tx) + len(text) * 7.7, float(ty)
        for other_bx, other_top, *_ in callouts:
            if other_bx != bx and float(other_top) < y:
                assert not (x0 - 2 < float(other_bx) < x1 + 2), (text, other_bx)


def test_it_reads_as_an_image_with_a_text_description():
    _arch, _cost, svg = model()
    assert svg.startswith('<svg class="massing"') and 'role="img"' in svg
    title = re.search(r"<title[^>]*>([^<]+)</title>", svg).group(1)
    desc = re.search(r"<desc[^>]*>([^<]+)</desc>", svg).group(1)
    assert title == "RAG chatbot on AWS as a massing model"
    assert "Block height is monthly cost" in desc and "Amazon OpenSearch Serverless" in desc
    assert re.search(r'style="--band:[\d.]+%"', svg), "phones trim the callouts by this much"


@pytest.mark.parametrize("provider", ["aws", "azure", "gcp", "oss"])
@pytest.mark.parametrize("name", catalog.pattern_names())
def test_every_example_can_be_modelled(name, provider):
    _arch, _cost, svg = model(name, provider)
    assert svg.count('<g class="m-blk"') >= 3
    assert not re.search(r"(?<![a-z])nan(?![a-z])", svg), "every coordinate is a number"


def test_official_icons_sit_on_the_blocks_and_badges_stand_in_without():
    _arch, _cost, svg = model()
    assert svg.count("<image ") == svg.count('<g class="m-blk"')
    _arch, _cost, plain = model(icons=IconLibrary(None))
    assert "<image " not in plain and plain.count('class="m-badge"') == plain.count("m-blk")
