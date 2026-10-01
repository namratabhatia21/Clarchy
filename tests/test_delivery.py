from cloudarchie.delivery import add_delivery, has_delivery
from cloudarchie.spec import load_pattern, load_spec


def spec(components, edges=()):
    return load_spec(
        {
            "name": "Test",
            "components": [{"id": i, "capability": c} for i, c in components],
            "edges": [{"from": a, "to": b} for a, b in edges],
        }
    )


def caps(s):
    return {c.capability: c.id for c in s.components}


def test_every_design_gets_source_build_release_and_infra():
    out = add_delivery(
        spec([("users", "client"), ("fn", "serverless-function")], [("users", "fn")])
    )
    found = caps(out)
    for cap in ("source-control", "ci-build", "cd-deploy", "iac"):
        assert cap in found
    assert "container-registry" not in found  # nothing runs in containers
    assert "event-autoscaling" not in found
    labels = {(e.source, e.target): e.label for e in out.edges}
    assert labels[("repo", "build")] == "push"
    assert labels[("build", "deploy")] == "artifact"
    assert labels[("deploy", "infra-code")] == "applies"


def test_containers_add_a_registry_between_build_and_release():
    out = add_delivery(spec([("app", "container-service")]))
    edges = {(e.source, e.target) for e in out.edges}
    assert {("build", "registry"), ("registry", "deploy")} <= edges
    assert ("build", "deploy") not in edges


def test_keda_scales_only_the_kubernetes_consumers_of_a_backlog():
    out = add_delivery(
        spec(
            [
                ("api", "kubernetes"),
                ("queue", "message-queue"),
                ("workers", "kubernetes"),
                ("stream", "stream"),
                ("lake", "object-storage"),
            ],
            [("api", "queue"), ("queue", "workers"), ("api", "stream"), ("stream", "lake")],
        )
    )
    scaler = caps(out)["event-autoscaling"]
    into = {e.source for e in out.edges if e.target == scaler}
    out_of = {e.target for e in out.edges if e.source == scaler}
    assert into == {"queue"}, "the stream only feeds the data lake"
    assert out_of == {"workers"}, "the API only produces work"


def test_no_keda_when_kubernetes_reads_no_backlog():
    out = add_delivery(
        spec([("api", "kubernetes"), ("queue", "message-queue")], [("api", "queue")])
    )
    assert "event-autoscaling" not in caps(out)


def test_ids_never_collide_and_toolchain_is_added_once():
    base = spec([("repo", "object-storage"), ("build", "kubernetes")])
    out = add_delivery(base)
    assert caps(out)["source-control"] == "repo-2"
    assert caps(out)["ci-build"] == "build-2"
    assert has_delivery(out)
    assert add_delivery(out) == out


def test_patterns_already_describe_their_toolchain():
    for name in ("kubernetes-microservices", "rag-chatbot"):
        pattern = load_pattern(name)
        assert has_delivery(pattern)
        assert add_delivery(pattern) == pattern
