"""The multi-page site: every address, its head, its links and the files beside it."""

import json
import re
from html.parser import HTMLParser
from importlib import resources
from pathlib import Path

import pytest

from clarchy import site
from clarchy.export import build_pages, engine_config, export_site


class Page(HTMLParser):
    """The parts of a page that search engines and visitors rely on."""

    def __init__(self, text: str):
        super().__init__()
        self.h1 = 0
        self.links: list[str] = []
        self.images: list[dict] = []
        self.json_ld: list[dict] = []
        self.crumbs: list[str] = []
        self._ld = False
        self._crumb = False
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "h1":
            self.h1 += 1
        if tag in ("a", "link") and a.get("href"):
            self.links.append(a["href"])
        if tag in ("script", "img") and a.get("src"):
            self.links.append(a["src"])
        if tag == "img":
            self.images.append(a)
        if tag == "script" and a.get("type") == "application/ld+json":
            self._ld = True
        if tag == "nav" and a.get("class") == "crumbs":
            self._crumb = True

    def handle_endtag(self, tag):
        if tag == "nav":
            self._crumb = False

    def handle_data(self, data):
        if self._ld:
            self.json_ld.append(json.loads(data))
            self._ld = False
        elif self._crumb and data.strip():
            self.crumbs.append(data.strip())


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    out = tmp_path_factory.mktemp("site")
    export_site(out, with_engine=False)
    content = site.content(json.loads(_data(out))["meta"])
    return out, content, site.pages(content)


def _data(out: Path) -> str:
    name = re.search(r'src="/(assets/data\.\w+\.js)"', (out / "index.html").read_text()).group(1)
    return (out / name).read_text().removeprefix("window.CLARCHY_DATA = ").rstrip().rstrip(";")


def _file(out: Path, path: str) -> Path:
    return out / path.lstrip("/") / "index.html" if path.endswith("/") else out / path.lstrip("/")


def test_every_address_is_its_own_page(built):
    out, _content, pages = built
    keys = {p.key for p in pages}
    assert {"plan", "examples", "example", "services", "pricing", "howto", "blog"} <= keys
    assert {"about", "privacy", "terms"} <= keys
    assert len({p.path for p in pages}) == len(pages)
    for p in pages:
        text = _file(out, p.path).read_text()
        doc = Page(text)
        assert doc.h1 == 1, f"{p.path}: one h1"
        assert text.count('<section class="page') == 1, f"{p.path}: only its own section"
        assert f"<title>{site._e(p.title)}</title>" in text
        assert f'<link rel="canonical" href="{p.url}">' in text
        assert f'<meta property="og:url" content="{p.url}">' in text
        assert 'name="robots"' not in text, "nothing is kept out of search"
        assert f'data-page="{p.key}" data-routing="path"' in text
        opening = re.search(r"<body[^>]*>", text)
        assert text[opening.end() :].lstrip().startswith('<a class="skip-link"'), p.path
        # The menu marks where the visitor is.
        menu = site.PARENT.get(p.key, p.key)
        if menu in {"examples", "services", "pricing", "howto"}:
            assert f'data-page="{menu}" aria-current="page"' in text


def test_titles_and_descriptions_are_unique_and_fit_search_results(built):
    _out, _content, pages = built
    assert len({p.title for p in pages}) == len(pages)
    assert len({p.description for p in pages}) == len(pages)
    for p in pages:
        assert 12 <= len(p.title) <= 65, p.title  # longer titles are cut short in results
        assert 70 <= len(p.description) <= 160, (p.path, len(p.description))


def test_structured_data_and_breadcrumbs(built):
    out, _content, pages = built
    for p in pages:
        doc = Page(_file(out, p.path).read_text())
        assert len(doc.json_ld) == 1
        graph = {item["@type"]: item for item in doc.json_ld[0]["@graph"]}
        if p.key == "plan":
            assert {"Organization", "Person", "WebSite", "WebApplication"} <= set(graph)
            assert graph["Person"]["name"] == "Namrata Bhatia"
            assert not doc.crumbs
            continue
        trail = [item["name"] for item in graph["BreadcrumbList"]["itemListElement"]]
        assert trail == ["Home", *(name for name, _ in p.crumbs)]
        assert doc.crumbs == trail, f"{p.path}: the visible breadcrumbs match"
        assert graph["BreadcrumbList"]["itemListElement"][-1]["item"] == p.url


def test_pricing_questions_are_marked_up_as_shown(built):
    out, _content, _pages = built
    text = (out / "pricing" / "index.html").read_text()
    faq = next(item for item in Page(text).json_ld[0]["@graph"] if item["@type"] == "FAQPage")
    questions = [q["name"] for q in faq["mainEntity"]]
    assert questions[0] == "What counts as a diagram?" and len(questions) == 4
    for q in faq["mainEntity"]:
        assert f"<dt>{q['name']}</dt>" in text
        assert q["acceptedAnswer"]["text"].split(".")[0] in text


def test_no_link_on_any_page_leads_nowhere(built):
    out, _content, pages = built
    files = [_file(out, p.path) for p in pages] + [out / "404.html"]
    for page in files:
        for link in Page(page.read_text()).links:
            if not link.startswith("/") or link.startswith("//"):
                continue
            path = link.split("#")[0].split("?")[0]
            target = _file(out, path)
            assert target.exists(), f"{page.relative_to(out)} links to {link}"


def test_every_image_has_a_text_alternative(built):
    out, _content, pages = built
    for p in pages:
        for img in Page(_file(out, p.path).read_text()).images:
            assert img.get("alt"), f"{p.path}: image without alt text"


def test_sitemap_robots_and_cloudflare_files(built):
    out, _content, pages = built
    sitemap = (out / "sitemap.xml").read_text()
    listed = re.findall(r"<loc>(.*?)</loc>", sitemap)
    assert listed == [p.url for p in pages if p.indexed]
    assert "https://clarchy.com/blog/" not in listed, "an empty blog waits for its posts"
    robots = (out / "robots.txt").read_text()
    assert "Sitemap: https://clarchy.com/sitemap.xml" in robots
    assert re.findall(r"^Disallow: (.*)$", robots, re.M) == ["/api/"]
    headers = (out / "_headers").read_text()
    assert "/assets/*\n  Cache-Control: public, max-age=31536000, immutable" in headers
    assert "X-Robots-Tag: noindex" in headers and ".workers.dev/*" in headers
    redirects = (out / "_redirects").read_text().splitlines()
    rules = [line.split() for line in redirects if line and not line.startswith("#")]
    assert ["/pricing", "/pricing/", "301"] in rules
    assert ["/index.html", "/", "301"] in rules
    sources = [r[0] for r in rules]
    assert len(sources) == len(set(sources))
    for _source, target, code in rules:
        assert code == "301" and target.endswith("/") and target not in sources, "one hop"


def test_pages_carry_their_lists_for_the_first_paint(built):
    out, content, _pages = built
    home = (out / "index.html").read_text()
    for sample in content.samples:
        assert f'data-sample="{sample["id"]}"' in home
    # A replay-only copy has no accounts; a site that plans keeps the credit line's space.
    assert '<p class="credit-line" id="credit-line" hidden></p>' in home
    files, _designs = build_pages(engine=engine_config())
    assert '<p class="credit-line pending" id="credit-line">' in files["index.html"]
    examples = (out / "examples" / "index.html").read_text()
    for pattern in content.patterns:
        assert f'href="/examples/{pattern["id"]}/"' in examples
    services = (out / "services" / "index.html").read_text()
    total = len(content.catalog["capabilities"])
    assert services.count('<li class="cap-card">') == total
    assert f'id="catalog-count">{total} of {total}<' in services
    detail = (out / "examples" / "rag-chatbot" / "index.html").read_text()
    assert '<h1 class="ws-name">RAG chatbot</h1>' in detail
    blog = (out / "blog" / "index.html").read_text()
    assert "The first posts are coming soon." in blog


def test_the_home_page_shows_a_priced_massing_model(built):
    out, _content, _pages = built
    home = (out / "index.html").read_text()
    figure = re.search(r'<figure class="hero-model" id="hero-model">.*?</figure>', home, re.S)
    assert figure, "the hero's model is rendered with the page"
    assert '<svg class="massing"' in figure.group(0) and 'role="img"' in figure.group(0)
    assert re.search(r"about \$[\d,]+ a month", figure.group(0))
    assert 'href="/examples/rag-chatbot/"' in figure.group(0)
    # Three frames: the poster with the page's one headline, the brief beside the model,
    # then how it works; the page closes on the examples, in the poster's orange.
    order = [home.index(s) for s in ('class="poster"', 'id="brief"', 'id="story"', 'id="coda"')]
    assert order == sorted(order)
    poster = home[order[0] : order[1]]
    assert home.count("<h1") == 1 and '<h1 class="poster-title' in poster
    assert 'class="dial-art"' in poster and "data-to-brief" in poster
    assert "<em>priced</em>" in home[order[1] : order[2]]


def test_the_home_page_closes_on_the_examples(built):
    out, content, _pages = built
    home = (out / "index.html").read_text()
    coda = re.search(r'<section class="coda".*?</section>', home, re.S).group(0)
    assert 'href="/examples/"' in coda
    # A register of real examples, each linking to its page with its size.
    for i, p in enumerate(content.patterns[:4], 1):
        assert f'href="/examples/{p["id"]}/"><span class="no">{i:02d}</span>' in coda
        assert f'<span class="nm">{site._e(p["name"])}</span>' in coda
    assert f"{site._count_word(len(content.patterns))} designs" in coda
    # The protractor is decoration: hidden from screen readers, its arm drawn at the reading
    # drafting.js opens it to.
    svg = re.search(r'<svg class="coda-protractor".*?</svg>', coda, re.S).group(0)
    assert 'aria-hidden="true"' in svg and f'data-sweep="{site.CODA_SWEEP}"' in svg
    assert f"rotate({-site.CODA_SWEEP} 270 262)" in svg
    assert "proof" not in home, "the example drawing gave way to the examples frame"


def test_about_names_the_founder(built):
    out, _content, _pages = built
    about = (out / "about" / "index.html").read_text()
    assert "Namrata Bhatia is the founder of Clarchy." in about
    assert 'href="mailto:namrata.bhatia@clarchy.com"' in about


def test_hash_links_for_single_file_builds():
    assert site.to_hash("/") == "#plan"
    assert site.to_hash("/pricing/") == "#pricing"
    assert site.to_hash("/how-to/") == "#howto"
    assert site.to_hash("/how-to/#howto-answers") == "#howto/answers"
    assert site.to_hash("/examples/rag-chatbot/") == "#examples/rag-chatbot"
    assert site.to_hash("/about/#author") == "#about"
    assert site.to_hash("/fonts/archivo.woff2") is None


def test_pre_rendered_colours_and_labels_match_the_scripts():
    core = resources.files("clarchy").joinpath("static", "core.js").read_text()

    def table(name: str) -> dict[str, str]:
        body = re.search(rf"const {name} = \{{(.*?)\}};", core, re.S).group(1)
        return dict(re.findall(r'(\w+): "([^"]*)"', body))

    assert table("STAGE_COLOURS") == site.STAGE_COLOURS
    assert table("PROVIDER_COLOURS") == site.PROVIDER_COLOURS
    assert table("FIDELITY_HELP") == site.FIDELITY_HELP


def test_design_rules_that_can_be_checked(built):
    """DESIGN.md lists what makes a site look generated; these are the checkable ones."""
    out, _content, _pages = built
    static = resources.files("clarchy").joinpath("static")
    css = static.joinpath("app.css").read_text()
    template = static.joinpath("index.html").read_text()
    assert "—" not in template, "no em dashes in the copy"
    assert not re.search(r"\b(Inter|Geist|Space Grotesk)\b", css)
    assert not re.search(r":hover[^{]*\{[^}]*transform", css), "hover never moves things"
    loops = [line for line in css.splitlines() if "infinite" in line]
    progress = ("pipeline-status", "running", "drafting-loader")
    assert all(any(p in line for p in progress) for line in loops), "only progress loops"
    assert "radial-gradient" not in css, "no orbs or dot grids"
    # No grid paper behind pages or cards; only the diagram viewer keeps one.
    grids = re.findall(r"([^{}]+)\{[^}]*linear-gradient\(90deg", css)
    assert [g.strip() for g in grids] == [".canvas"], grids
    pricing = (out / "pricing" / "index.html").read_text()
    assert pricing.count('<article class="plan-card') == 2, "two plans, not three tiers"
    assert "--bg: #ffffff" not in css and "--bg: #fff;" not in css
    # Four sections in the header; the rest are in the footer.
    header = re.search(r'<nav class="main-nav".*?</nav>', template, re.S).group(0)
    assert header.count('class="main-link"') == 4
    # Then one button: Log in / Sign up, which opens the sign-up form with a log-in mode.
    topbar = re.search(r'<header class="topbar">.*?</header>', template, re.S).group(0)
    assert 'id="account-button"' in topbar and "Log in / Sign up" in topbar
    assert "Start a plan" not in topbar
    assert 'data-mode="login"' in template and template.count("data-signup-only") == 3
    # Start a plan, from Pricing and How to, opens the home page at the brief.
    assert re.findall(r'href="([^"]*)">Start a plan<', template) == ["/#brief", "/#brief"]
    footer = re.search(r'<p class="footer-links">.*?</p>', template, re.S).group(0)
    for path in ("/about/", "/blog/", "/privacy/", "/terms/"):
        assert f'href="{path}"' in footer
    # The Services page is a two-column grid; its breadcrumbs take a row of their own.
    assert ".catalog-layout > .crumbs { grid-column: 1 / -1;" in css
