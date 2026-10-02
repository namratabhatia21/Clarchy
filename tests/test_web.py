import json

import pytest
import yaml
from helpers import make_docx

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from clarchy import catalog  # noqa: E402
from clarchy.web import create_app  # noqa: E402

SCRIPTS = (
    "core.js",
    "drafting.js",
    "workspace.js",
    "plan.js",
    "examples.js",
    "services.js",
    "howto.js",
    "access.js",
    "app.js",
)


@pytest.fixture(scope="module")
def client():
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("CLARCHY_LLM", "rules")  # never reach a real model from tests
        return TestClient(create_app())


def events(response) -> list[dict]:
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/event-stream")
    return [
        json.loads(line.removeprefix("data: "))
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]


def design(client, yaml_text, provider="aws"):
    return client.post("/api/design", json={"spec_yaml": yaml_text, "provider": provider})


def test_index_and_assets_served(client):
    page = client.get("/")
    assert (
        page.status_code == 200
        and "<title>Clarchy · Cloud architecture from your requirements</title>" in page.text
    )
    assets = (
        *(f"/static/{name}" for name in SCRIPTS),
        "/static/app.css",
        "/static/fonts/archivo.woff2",
        "/static/brand/apple-touch-icon.png",
    )
    for asset in assets:
        assert client.get(asset).status_code == 200, asset


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


def test_meta_describes_the_planning_engine(client):
    meta = client.get("/api/meta").json()
    assert meta["engine"] == {"mode": "rules", "reason": "no model configured"}
    assert list(meta["stages"]) == [
        "code",
        "build",
        "ship",
        "serve",
        "run",
        "integrate",
        "store",
        "operate",
    ]


def test_samples_are_listed(client):
    samples = client.get("/api/samples").json()
    assert [s["id"] for s in samples] == [sid for sid, _t, _x in catalog.samples()]
    assert all(s["text"] and s["title"] for s in samples)


def test_plan_streams_every_stage_then_a_design_that_renders(client):
    text = (
        "A booking app for 40 clinics in the UK. Patients sign in, book appointments and "
        "pay a deposit. The backend is already in Docker. Reminders go out by SMS."
    )
    stream = events(client.post("/api/plan", data={"text": text, "mode": "rules"}))
    done = [e["stage"] for e in stream if e["type"] == "stage" and e["status"] == "done"]
    assert done == ["read", "understand", "design", "toolchain", "workflows", "map"]
    result = stream[-1]
    assert result["type"] == "result" and result["mode"] == "rules"
    spec = yaml.safe_load(result["spec_yaml"])
    assert spec["requirements"]["region"] == "uk"
    caps = {c["capability"] for c in spec["components"]}
    assert {"container-service", "relational-db", "container-registry", "cd-deploy"} <= caps
    for provider in catalog.providers():
        res = design(client, result["spec_yaml"], provider)
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["workflows"] and body["provenance"]["mode"] == "rules"


def test_plan_reads_an_uploaded_word_document(client):
    docx = make_docx(
        ["Fleet tracking", "8,000 vans send telemetry to Kubernetes workers via a queue."]
    )
    files = {"file": ("brief.docx", docx, "application/octet-stream")}
    stream = events(
        client.post("/api/plan", data={"mode": "rules", "region": "sydney"}, files=files)
    )
    read = stream[0]
    assert read["stage"] == "read" and read["detail"].endswith("from brief.docx (2 paragraphs)")
    assert yaml.safe_load(stream[-1]["spec_yaml"])["requirements"]["region"] == "sydney"


@pytest.mark.parametrize(
    ("data", "files", "where"),
    [
        ({"text": "A booking app for clinics.", "mode": "magic"}, None, "mode"),
        ({"text": "A booking app for clinics.", "region": "mars"}, None, "region"),
        ({"text": "   "}, None, "document"),
        ({}, {"file": ("run.exe", b"MZ", "application/octet-stream")}, "document"),
    ],
)
def test_plan_rejects_bad_requests_before_streaming(client, data, files, where):
    res = client.post("/api/plan", data=data, files=files)
    assert res.status_code == 422
    assert res.json()["errors"][0]["where"] == where


def test_ai_mode_without_a_model_reports_an_error_event(client):
    stream = events(client.post("/api/plan", data={"text": "A to-do app.", "mode": "ai"}))
    assert stream[-1]["type"] == "error"
    assert "AI planning is not set up" in stream[-1]["message"]


def test_cors_is_off_by_default_and_configurable(monkeypatch, client):
    origin = {"Origin": "https://example.github.io"}
    assert "access-control-allow-origin" not in client.get("/api/meta", headers=origin).headers
    monkeypatch.setenv("CLARCHY_CORS_ORIGINS", "https://example.github.io")
    monkeypatch.setenv("CLARCHY_LLM", "rules")
    allowed = TestClient(create_app()).get("/api/meta", headers=origin)
    assert allowed.headers["access-control-allow-origin"] == "https://example.github.io"
