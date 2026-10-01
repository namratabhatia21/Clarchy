import pytest

from cloudarchie import catalog
from cloudarchie.mapping import FIDELITY_LEVELS, MappingError, map_to_provider, service_choice
from cloudarchie.spec import load_pattern, load_spec

PROVIDERS = catalog.providers()
MAPPABLE = [n for n, c in catalog.capabilities().items() if c["tier"] != "external"]


@pytest.mark.parametrize("provider", PROVIDERS)
def test_every_capability_is_mapped(provider):
    services = catalog.provider_mapping(provider)["services"]
    missing = sorted(set(MAPPABLE) - set(services))
    assert not missing, f"{provider} lacks mappings for {missing}"
    unknown = sorted(set(services) - set(MAPPABLE))
    assert not unknown, f"{provider} maps unknown capabilities {unknown}"


@pytest.mark.parametrize("provider", PROVIDERS)
@pytest.mark.parametrize("capability", MAPPABLE)
def test_mapping_entries_are_complete(provider, capability):
    choice = service_choice(provider, capability)
    assert choice.service and choice.short
    assert choice.fidelity in FIDELITY_LEVELS
    if choice.fidelity != "exact":
        assert choice.note, "non-exact mappings must explain the difference"
    assert choice.docs and choice.docs.startswith("https://")


@pytest.mark.parametrize("provider", PROVIDERS)
def test_every_region_is_mapped(provider):
    for key, region in catalog.regions().items():
        assert provider in region, f"region {key} has no {provider} code"


@pytest.mark.parametrize("name", catalog.pattern_names())
def test_patterns_map_to_aws(name):
    arch = map_to_provider(load_pattern(name), "aws")
    assert len(arch.components) == len(arch.spec.components)
    for m in arch.components:
        assert (m.choice is None) == (m.component.tier == "external")


def test_region_code_resolved():
    spec = load_spec(
        {
            "name": "t",
            "requirements": {"region": "india-mumbai"},
            "components": [{"id": "b", "capability": "object-storage"}],
        }
    )
    arch = map_to_provider(spec, "aws")
    assert arch.region_code == "ap-south-1"
    assert arch.by_id("b").choice.service == "Amazon S3"


def test_unknown_provider():
    spec = load_pattern("serverless-web-app")
    with pytest.raises(KeyError, match="unknown provider"):
        map_to_provider(spec, "mainframe")


def test_missing_capability_mapping_raises():
    with pytest.raises(MappingError, match="no mapping"):
        service_choice("aws", "client")
