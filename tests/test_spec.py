import pytest
from pydantic import ValidationError

from clarchy import catalog
from clarchy.spec import load_pattern, load_spec


def minimal(**overrides):
    data = {
        "name": "t",
        "components": [
            {"id": "users", "capability": "client"},
            {"id": "fn", "capability": "serverless-function"},
            {"id": "bucket", "capability": "object-storage"},
        ],
        "edges": [{"from": "users", "to": "fn"}, {"from": "fn", "to": "bucket"}],
    }
    data.update(overrides)
    return data


def test_minimal_spec_loads():
    spec = load_spec(minimal())
    assert [c.tier for c in spec.components] == ["external", "compute", "data"]
    assert spec.edges[0].source == "users"
    assert spec.requirements.region == "us-east"


@pytest.mark.parametrize("name", catalog.pattern_names())
def test_every_pattern_is_valid(name):
    spec = load_pattern(name)
    assert spec.summary, "patterns need a summary"
    in_cloud = [c for c in spec.components if c.tier != "external"]
    assert in_cloud


def test_there_are_five_starter_patterns():
    assert len(catalog.pattern_names()) >= 5


def test_duplicate_ids_rejected():
    data = minimal()
    data["components"].append({"id": "fn", "capability": "cache"})
    with pytest.raises(ValidationError, match="duplicate component ids: fn"):
        load_spec(data)


def test_unknown_capability_rejected():
    data = minimal()
    data["components"][1]["capability"] = "quantum-computer"
    with pytest.raises(ValidationError, match="unknown capability"):
        load_spec(data)


def test_edge_to_unknown_component_rejected():
    with pytest.raises(ValidationError, match="unknown id 'nope'"):
        load_spec(minimal(edges=[{"from": "fn", "to": "nope"}]))


def test_self_loop_rejected():
    with pytest.raises(ValidationError, match="self-loop"):
        load_spec(minimal(edges=[{"from": "fn", "to": "fn"}]))


def test_unknown_region_rejected():
    with pytest.raises(ValidationError, match="unknown region"):
        load_spec(minimal(requirements={"region": "moon-base"}))


def test_bad_component_id_rejected():
    data = minimal()
    data["components"][1]["id"] = "Bad Id"
    with pytest.raises(ValidationError, match="lowercase"):
        load_spec(data)


def test_unknown_fields_rejected():
    with pytest.raises(ValidationError):
        load_spec(minimal(colour="blue"))
