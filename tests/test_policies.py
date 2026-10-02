from clarchy import blog, catalog, policies, pricing
from clarchy.mapping import map_to_provider
from clarchy.planner.rules import plan_with_rules
from clarchy.spec import load_spec

SAMPLES = {sample_id: text for sample_id, _title, text in catalog.samples()}


def by_id(spec):
    return {p["id"]: p for p in policies.check(spec)}


def test_enterprise_ai_design_covers_what_architecture_can():
    found = by_id(plan_with_rules(SAMPLES["field-service-assistant"]))
    assert {"eu-ai-act", "gdpr", "owasp-llm", "nist-ai-rmf", "iso-42001", "iso-27001"} <= set(found)
    assert all(p["counts"]["gap"] == 0 for p in found.values())
    eu = found["eu-ai-act"]["obligations"]
    assert any(o["status"] == "action" and "Article 50" in o["text"] for o in eu)
    logs = next(o for o in eu if "Article 12" in o["text"])
    assert logs["status"] == "covered" and "LLM tracing" in logs["by"]


def test_a_bare_ai_app_shows_gaps_with_suggestions():
    spec = load_spec(
        {
            "name": "Bare chatbot",
            "components": [
                {"id": "app", "capability": "container-service"},
                {"id": "llm", "capability": "llm-inference"},
            ],
        }
    )
    owasp = by_id(spec)["owasp-llm"]
    injection = owasp["obligations"][0]
    assert injection["status"] == "gap"
    assert injection["suggest"][0]["capability"] == "ai-guardrails"


def test_no_policies_for_a_plain_unregulated_design():
    spec = load_spec({"name": "Site", "components": [{"id": "cdn", "capability": "cdn"}]})
    assert policies.check(spec) == []


def test_every_policy_control_is_a_known_capability():
    known = set(catalog.capabilities())
    for policy in policies.policy_list():
        for ob in policy["obligations"]:
            assert set(ob.get("controls", [])) <= known, (policy["id"], ob["text"])


def test_third_party_prices_are_flagged_on_a_verified_bill():
    spec = plan_with_rules(SAMPLES["field-service-assistant"])
    cost = pricing.estimate(map_to_provider(spec, "aws"))
    lines = {line["component"]: line for line in cost["lines"]}
    assert lines["devenv"]["approximate"] and lines["devenv"]["service"] == "GitHub Codespaces"
    assert not lines["assistant"]["approximate"], "Amazon Q Developer is in the AWS price list"
    assert not any(line["approximate"] for c, line in lines.items() if c != "devenv")


def test_blog_posts_render_safely(tmp_path):
    html = blog.to_html(
        "## Heading\n\nSome **bold**, *italic* and `code` with a [link](https://example.com) "
        "and a [bad one](javascript:alert(1)).\n\n- one\n- two\n\n<script>x</script>"
    )
    assert "<h3>Heading</h3>" in html and "<strong>bold</strong>" in html
    assert 'href="https://example.com"' in html and "javascript:" not in html
    assert "<ul><li>one</li><li>two</li></ul>" in html
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert all(p["title"] and p["html"] and p["author"] for p in blog.posts())
    (tmp_path / "2026-10-01-a-post.md").write_text(
        "---\ntitle: A post\ndate: 2026-10-01\nauthor: Namrata Bhatia\nsummary: One line.\n"
        "---\nBody with **bold**.\n",
        encoding="utf-8",
    )
    [post] = blog.posts(tmp_path)
    assert (post["id"], post["title"], post["author"]) == (
        "2026-10-01-a-post",
        "A post",
        "Namrata Bhatia",
    )
    assert "<strong>bold</strong>" in post["html"]
