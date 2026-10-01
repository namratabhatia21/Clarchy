import pytest

from clarchy import catalog
from clarchy.delivery import add_delivery
from clarchy.spec import ArchitectureSpec, load_pattern
from clarchy.workflows import generate_workflows, with_workflows


def generated(name: str):
    spec = load_pattern(name)
    return spec, generate_workflows(spec.model_copy(update={"workflows": []}))


@pytest.mark.parametrize("name", catalog.pattern_names())
def test_generated_workflows_reference_real_components(name):
    spec, workflows = generated(name)
    ids = {c.id for c in spec.components}
    assert workflows, "every pattern has at least one flow"
    assert len({w.id for w in workflows}) == len(workflows)
    for wf in workflows:
        assert wf.steps
        for step in wf.steps:
            assert set(step.components) <= ids
            assert "→" in step.text
    # The generated flows are valid parts of the spec.
    ArchitectureSpec.model_validate(
        spec.model_copy(update={"workflows": workflows}).model_dump(by_alias=True)
    )


@pytest.mark.parametrize("name", catalog.pattern_names())
def test_patterns_ship_with_their_workflows(name):
    assert load_pattern(name).workflows


def test_request_flow_starts_at_the_client_and_delivery_ends_with_a_rollout():
    _, workflows = generated("container-api")
    by_kind = {w.kind: w for w in workflows}
    assert by_kind["request"].steps[0].components[0] == "users"
    last = by_kind["delivery"].steps[-1]
    assert last.text.endswith("roll out the new version")
    assert "app" in last.components


def test_queue_workers_get_a_background_flow():
    _, workflows = generated("kubernetes-microservices")
    background = next(w for w in workflows if w.kind == "async")
    first = background.steps[0].text
    assert "process the queued jobs" in first


def test_with_workflows_keeps_existing_ones():
    spec = load_pattern("rag-chatbot")
    assert with_workflows(spec).workflows == spec.workflows
    bare = add_delivery(spec.model_copy(update={"workflows": []}))
    assert with_workflows(bare).workflows
