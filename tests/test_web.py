import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from cloudarchie import catalog  # noqa: E402
from cloudarchie.web import create_app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    return TestClient(create_app())


def design(client, yaml_text, provider="aws"):
    return client.post("/api/design", json={"spec_yaml": yaml_text, "provider": provider})


def test_index_and_assets_served(client):
    page = client.get("/")
    assert page.status_code == 200 and "<title>CloudArchie</title>" in page.text
    for asset in ("/static/app.js", "/static/app.css"):
        assert client.get(asset).status_code == 200


def test_meta_lists_providers(client):
    meta = client.get("/api/meta").json()
    enabled = {p["id"]: p["enabled"] for p in meta["providers"]}
    assert enabled["aws"] is True
    assert list(enabled) == ["aws", "azure", "gcp", "oss"]
    assert all(enabled.values())
    assert "object-storage" in meta["capabilities"]


def test_patterns_round_trip(client):
    listed = client.get("/api/patterns").json()
    assert [p["id"] for p in listed] == catalog.pattern_names()
    for p in listed:
        spec_yaml = client.get(f"/api/patterns/{p['id']}").json()["spec_yaml"]
        res = design(client, spec_yaml)
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["svg"].startswith("<svg")
        assert body["explanation_md"].startswith("# ")


def test_unknown_pattern_404(client):
    assert client.get("/api/patterns/nope").status_code == 404


def test_design_returns_explainable_components(client):
    spec_yaml = catalog.pattern_text("rag-chatbot")
    body = design(client, spec_yaml).json()
    comps = {c["id"]: c for c in body["components"]}
    vectors = comps["vectors"]
    assert vectors["fidelity"] == "close"
    assert vectors["note"] and vectors["alternatives"]
    assert vectors["rationale"]
    assert {"from": "app", "label": "retrieve"} in vectors["connections"]
    assert comps["users"]["service"] is None
    assert body["region"] == {"code": "us-west-2", "label": "Oregon"}


def test_validation_errors_are_readable(client):
    res = design(client, "name: X\ncomponents:\n  - {id: a, capability: teleporter}\n")
    assert res.status_code == 422
    errors = res.json()["errors"]
    assert errors[0]["where"] == "components.0.capability"
    assert "unknown capability" in errors[0]["message"]


def test_yaml_syntax_error_reports_line(client):
    res = design(client, "name: X\ncomponents: [\n")
    assert res.status_code == 422
    assert res.json()["errors"][0]["message"].startswith("YAML syntax")


def test_non_mapping_spec_rejected(client):
    res = design(client, "- just\n- a list\n")
    assert res.status_code == 422


def test_unknown_provider_rejected(client):
    res = design(client, catalog.pattern_text("container-api"), provider="ibm")
    assert res.status_code == 422
    assert "not available yet" in res.json()["errors"][0]["message"]


def test_other_providers_design_and_flag_review_status(client):
    body = design(client, catalog.pattern_text("container-api"), provider="gcp").json()
    assert body["reviewed"] is False
    services = {c["id"]: c["service"] for c in body["components"]}
    assert services["app"] == "Cloud Run"
    oss = design(client, catalog.pattern_text("container-api"), provider="oss").json()
    assert oss["region"]["code"] == ""


def test_oversized_spec_rejected(client):
    res = design(client, "x" * 200_000)
    assert res.status_code == 422


def test_catalog_lists_equivalents_across_providers(client):
    body = client.get("/api/catalog").json()
    assert [p["id"] for p in body["providers"]] == ["aws", "azure", "gcp", "oss"]
    caps = {c["id"]: c for c in body["capabilities"]}
    assert "client" not in caps  # not a service
    queue = caps["message-queue"]["services"]
    assert queue["aws"]["service"] == "Amazon SQS"
    assert queue["azure"]["service"].startswith("Azure Service Bus")
    assert queue["gcp"]["fidelity"] == "close" and queue["gcp"]["note"]
    assert queue["oss"]["service"] == "RabbitMQ"
    for cap in body["capabilities"]:
        assert set(cap["services"]) == {"aws", "azure", "gcp", "oss"}
