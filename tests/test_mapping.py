import pytest

from clarchy import catalog
from clarchy.mapping import FIDELITY_LEVELS, MappingError, map_to_provider, service_choice
from clarchy.spec import load_pattern, load_spec

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


CLOUDS = [p for p in PROVIDERS if catalog.provider_mapping(p)["provider"]["kind"] == "cloud"]


@pytest.mark.parametrize("provider", CLOUDS)
def test_every_region_is_mapped_for_clouds(provider):
    for key, region in catalog.regions().items():
        assert set(region[provider]) == {"code", "location"}, f"region {key} on {provider}"


@pytest.mark.parametrize("provider", PROVIDERS)
@pytest.mark.parametrize("name", catalog.pattern_names())
def test_patterns_map_to_every_provider(provider, name):
    arch = map_to_provider(load_pattern(name), provider)
    assert arch.reviewed in (True, False)
    if arch.kind == "self-hosted":
        assert arch.region_code == ""
    else:
        assert arch.region_code


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
    assert arch.region_text == "Mumbai (ap-south-1)"
    assert arch.by_id("b").choice.service == "Amazon S3"
    assert map_to_provider(spec, "azure").region_text == "Pune (centralindia)"
    assert map_to_provider(spec, "oss").region_text == "India (West)"


def test_display_order_puts_aws_first_and_self_hosted_last():
    order = catalog.providers_in_display_order()
    assert order[0] == "aws" and order[-1] == "oss"


def test_unknown_provider():
    spec = load_pattern("serverless-web-app")
    with pytest.raises(KeyError, match="unknown provider"):
        map_to_provider(spec, "mainframe")


def test_missing_capability_mapping_raises():
    with pytest.raises(MappingError, match="no mapping"):
        service_choice("aws", "client")
