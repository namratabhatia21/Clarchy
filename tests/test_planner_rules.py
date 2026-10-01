import re

import pytest

from cloudarchie import catalog
from cloudarchie.mapping import map_to_provider
from cloudarchie.planner.rules import analyse, plan_with_rules

SAMPLES = {sample_id: text for sample_id, _title, text in catalog.samples()}


def compute(spec):
    return next(c.capability for c in spec.components if c.id == "app")


@pytest.mark.parametrize("sample_id", sorted(SAMPLES))
def test_samples_produce_complete_valid_designs(sample_id):
    text = SAMPLES[sample_id]
    spec = plan_with_rules(text, source="sample")
    assert spec.provenance.mode == "rules"
    tiers = {c.tier for c in spec.components}
    assert {"external", "delivery", "compute", "platform"} <= tiers
    assert spec.workflows
    for provider in catalog.providers():
        map_to_provider(spec, provider)
    for comp in spec.components:
        if comp.tier not in ("external", "delivery"):
            assert comp.rationale, comp.id
        for quote in comp.evidence:
            assert quote in text, f"{comp.id}: evidence must be quoted verbatim"


def test_each_sample_picks_the_right_compute():
    designs = {sid: plan_with_rules(text) for sid, text in SAMPLES.items()}
    assert compute(designs["clinic-booking"]) == "container-service"  # "already in Docker"
    assert compute(designs["fleet-telemetry"]) == "kubernetes"
    assert compute(designs["photo-sharing"]) == "serverless-function"  # spiky traffic
    policy = {c.capability for c in designs["policy-assistant"].components}
    assert {"llm-inference", "vector-search"} <= policy


def test_fleet_reads_numbers_region_and_scales_workers_with_keda():
    spec = plan_with_rules(SAMPLES["fleet-telemetry"])
    req = spec.requirements
    assert req.region == "eu-central"
    assert req.peak_rps == 800
    assert str(req.availability_target) == "99.9"
    caps = {c.capability for c in spec.components}
    assert {"stream", "data-warehouse", "event-autoscaling", "container-registry"} <= caps


def test_unknowns_become_assumptions_and_questions():
    spec = plan_with_rules("A small internal tool where staff upload receipts for approval.")
    assert any("10,000 monthly users" in a for a in spec.assumptions)
    assert any("budget" in q for q in spec.open_questions)
    assert spec.requirements.region == "us-east"


def test_untitled_text_is_named_from_its_first_sentence():
    plan = analyse("We want a simple photo sharing app where friends upload pictures.")
    assert plan.name == "Photo sharing app"
    assert analyse("Orders and payments for our bakery.").name == "Your application"
    assert analyse("# Clinic portal\n\nPatients book visits.").name == "Clinic portal"


def test_rationales_read_naturally():
    spec = plan_with_rules(
        "A photo sharing app. Traffic is spiky. Users upload photos and videos; thumbnails "
        "and notifications are made in the background. Orders, payments and invoices are "
        "stored, with shopping carts kept per session."
    )
    reasons = {c.id: c.rationale for c in spec.components}
    assert reasons["app"].endswith("which suits spiky traffic.")
    assert reasons["files"] == "Durable, low-cost storage for photos and videos."
    assert "while thumbnails and notifications run" in reasons["queue"]
    assert reasons["db"].startswith("Records such as orders, payments and invoices need")
    assert "shopping carts" in reasons["kv"] and "sessions" in reasons["kv"]
    # No raw matched words leaking into sentences ("storage for photo and upload").
    for text in reasons.values():
        assert not re.search(r"\b(upload|queue and|background run)\b", text or "")


def test_region_and_compliance_from_text():
    spec = plan_with_rules(
        "A clinic booking site for patients in Mumbai. HIPAA and GDPR apply. Budget is "
        "$24,000 per year."
    )
    assert spec.requirements.region == "india-mumbai"
    assert spec.requirements.compliance == ["HIPAA", "GDPR"]
    assert spec.requirements.monthly_budget_usd == 2000
