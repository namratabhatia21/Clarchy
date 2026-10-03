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
    assert {"plan", "examples", "example", "services", "howto", "blog"} <= keys
    assert "pricing" not in keys, "an open-source project has no pricing page"
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
        if menu in {"examples", "services", "howto"}:
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
            assert {"SoftwareSourceCode", "Person", "WebSite", "WebApplication"} <= set(graph)
            assert "Organization" not in graph
            person = graph["Person"]
            assert (person["name"], person["jobTitle"]) == ("Namrata Bhatia", "AI/ML engineer")
            assert "https://www.linkedin.com/in/namratabhatia21/" in person["sameAs"]
            code = graph["SoftwareSourceCode"]["codeRepository"]
            assert code == "https://github.com/namratabhatia21/Clarchy"
            assert not doc.crumbs
            continue
        trail = [item["name"] for item in graph["BreadcrumbList"]["itemListElement"]]
        assert trail == ["Home", *(name for name, _ in p.crumbs)]
        assert doc.crumbs == trail, f"{p.path}: the visible breadcrumbs match"
        assert graph["BreadcrumbList"]["itemListElement"][-1]["item"] == p.url


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
    assert "Disallow" not in robots
    headers = (out / "_headers").read_text()
    assert "/assets/*\n  Cache-Control: public, max-age=31536000, immutable" in headers
    assert "X-Robots-Tag: noindex" in headers and ".workers.dev/*" in headers
    redirects = (out / "_redirects").read_text().splitlines()
    rules = [line.split() for line in redirects if line and not line.startswith("#")]
    assert ["/how-to", "/how-to/", "301"] in rules
    assert ["/index.html", "/", "301"] in rules
    # Old links to the Pricing page land on the home page.
    assert ["/pricing/", "/", "301"] in rules and ["/pricing", "/", "301"] in rules
    sources = [r[0] for r in rules]
    assert len(sources) == len(set(sources))
    for _source, target, code in rules:
        assert code == "301" and target.endswith("/") and target not in sources, "one hop"


def test_pages_carry_their_lists_for_the_first_paint(built):
    out, content, _pages = built
    home = (out / "index.html").read_text()
    for sample in content.samples:
        assert f'data-sample="{sample["id"]}"' in home
    files, _designs = build_pages(engine=engine_config())
    assert "credit-line" not in home and "credit-line" not in files["index.html"]
    note = "Samples replay a recorded rule-based run; your own brief is planned live."
    assert note in files["index.html"], "the static site says its samples are recorded"
    assert note not in home, "a replay-only copy can't plan a brief live"
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
    # The pantograph is decoration, hidden from screen readers and drawn finished: its
    # tracer back at the start of the sketch, the pencil on the copy, twice as far out.
    svg = re.search(r'<svg class="coda-pantograph".*?</svg>', coda, re.S).group(0)
    assert 'aria-hidden="true"' in svg and 'class="cg-copy"' in svg
    (ox, oy), (tx, ty) = site.PANTOGRAPH_PIVOT, site.PANTOGRAPH_SKETCH[-1]
    assert f'class="cg-pencil" transform="translate({2 * tx - ox:.1f} {2 * ty - oy:.1f})"' in svg
    assert "proof" not in home, "the example drawing gave way to the examples frame"


def test_the_pantograph_keeps_its_bars_and_doubles_every_point():
    def dist(a, b):
        return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5

    for t in site.PANTOGRAPH_SKETCH:
        j = site.pantograph(t)
        assert abs(dist(j["O"], j["J"]) - site.PANTOGRAPH_BAR) < 1e-6
        assert abs(dist(j["J"], j["P"]) - site.PANTOGRAPH_BAR) < 1e-6
        assert abs(dist(j["C"], j["T"]) - dist(j["J"], j["D"])) < 1e-6, "C-J-D-T: a parallelogram"
        assert j["J"][1] < min(j["O"][1], j["P"][1]), "the bars stand like an A"


def test_about_credits_the_author_with_links(built):
    out, _content, pages = built
    about = (out / "about" / "index.html").read_text()
    assert "<h2>Built by Namrata Bhatia</h2>" in about
    assert "Namrata Bhatia is an AI/ML engineer who builds production GenAI systems" in about
    for link in (
        "https://github.com/namratabhatia21/Clarchy",
        "https://github.com/namratabhatia21",
        "https://www.linkedin.com/in/namratabhatia21/",
        "mailto:namratabhatia21@gmail.com",
    ):
        assert f'href="{link}"' in about
    for p in pages:
        text = _file(out, p.path).read_text()
        assert "ounder" not in text, f"{p.path}: no founder title"
        assert "<dt>Built by</dt>" in text


def test_hash_links_for_single_file_builds():
    assert site.to_hash("/") == "#plan"
    assert site.to_hash("/pricing/") is None, "no such page"
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
    """docs/VISUAL-DESIGN.md lists what makes a site look generated; these are checkable."""
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
    assert "--bg: #ffffff" not in css and "--bg: #fff;" not in css
    # Three sections and the code on GitHub in the header; the rest are in the footer.
    header = re.search(r'<nav class="main-nav".*?</nav>', template, re.S).group(0)
    assert header.count('class="main-link"') == 4
    assert 'href="https://github.com/namratabhatia21/Clarchy"' in header
    topbar = re.search(r'<header class="topbar">.*?</header>', template, re.S).group(0)
    assert "Start a plan" not in topbar and "account" not in topbar
    # Start a plan, on How to, opens the home page at the brief.
    assert re.findall(r'href="([^"]*)">Start a plan<', template) == ["/#brief"]
    footer = re.search(r'<p class="footer-links">.*?</p>', template, re.S).group(0)
    for path in ("/about/", "/privacy/", "/terms/", "https://github.com/namratabhatia21/Clarchy"):
        assert f'href="{path}"' in footer
    # Blog joins the footer once there are posts.
    assert "<!-- render:blog-link -->" in footer and "mailto:" not in footer
    # The Services page is a two-column grid; its breadcrumbs take a row of their own.
    assert ".catalog-layout > .crumbs { grid-column: 1 / -1;" in css


def test_contrast_and_focus_fixes_hold():
    """Fixes from an axe-core audit (WCAG 2.2 AA) that a later change could quietly undo."""
    static = resources.files("clarchy").joinpath("static")
    css = static.joinpath("app.css").read_text()
    html = static.joinpath("index.html").read_text()
    js = static.joinpath("workspace.js").read_text()
    # Small text on the orange poster is black: navy there is 3.8:1, under AA's 4.5:1.
    assert "--poster-ink-small: #000000" in css
    assert ".topbar.on-poster .main-link { color: var(--poster-ink-small); }" in css
    # Keyboard focus on Attach shows on the button, not on the hidden file input.
    assert ".attach-btn:has(+ #file-input:focus-visible)" in css
    # Steps of How it works not yet reached stay readable (4.5:1 needs 0.82 or more).
    opacity = float(re.search(r"\.story-step \{[^}]*opacity: ([.\d]+)", css).group(1))
    assert opacity >= 0.82
    # A result's title becomes the page's h1 when it fills the plan page; its sections are h2.
    assert '<h2 class="ws-name"></h2>' in html and 'createElement("h1")' in js
    assert 'el("h3"' not in js
    # A diagram whose services are buttons is announced as a group, not a single image.
    assert 'svg.setAttribute("role", "group")' in js


def test_the_cookie_policy_lists_everything_the_scripts_store(built):
    """The Privacy page's storage table must cover every key the front end keeps, and the
    site must set no cookies and load no third-party scripts of its own."""
    out, _content, _pages = built
    static = resources.files("clarchy").joinpath("static")
    scripts = {f.name: f.read_text() for f in static.iterdir() if f.name.endswith(".js")}
    privacy = (out / "privacy" / "index.html").read_text()
    policy = privacy[privacy.index('id="cookies"') :]
    keys = set()
    for js in scripts.values():
        keys |= set(re.findall(r'const \w+_KEY = "([^"]+)"', js))
        keys |= set(re.findall(r'CA\.store\("([^"]+)", (?!null)', js))
    assert keys, "the scripts keep something in storage"
    for key in keys:
        assert f"<code>{key}</code>" in policy, f"{key} is stored but not in the cookie policy"
    assert not any("document.cookie" in js for js in scripts.values())
    # The draft of a brief is kept for the tab only; local storage only sees old drafts removed.
    assert re.findall(r"CA\.store\(DRAFT_KEY, ([^)]+)\)", scripts["plan.js"]) == ["null"]
    assert "sessionStorage.setItem(DRAFT_KEY" in scripts["plan.js"]
    for page in out.rglob("*.html"):
        text = page.read_text()
        assert not re.search(r'<script[^>]+src="https?://', text), f"{page}: third-party script"
        assert "<iframe" not in text, f"{page}: embedded third-party content"
        assert 'href="/privacy/#cookies"' in text or page.name == "404.html"


def test_no_claim_says_more_than_the_site_does(built):
    """Open source has no price estimate and Google Cloud's prices are compiled by hand, so
    nothing may say every design is priced on four clouds or that all prices update daily."""
    out, _content, _pages = built
    text = "\n".join(p.read_text() for p in out.rglob("*.html")).lower()
    for claim in (
        "priced on four clouds",
        "priced on every cloud",
        "four clouds ·",
        "drawn and priced on aws, azure, google cloud and open source",
    ):
        assert claim not in text, claim
    home = (out / "index.html").read_text()
    assert "with the rule-based planner nothing leaves your browser" in home


def test_feedback_opens_the_visitors_email_app(built):
    """Feedback goes from the visitor's own email app to Namrata: no form service, no
    server, nothing stored. Without scripts the form's own mailto submission still works."""
    out, _content, _pages = built
    about = (out / "about" / "index.html").read_text()
    form = re.search(r'<form class="feedback-form".*?</form>', about, re.S).group(0)
    assert 'action="mailto:namratabhatia21@gmail.com" method="get"' in form
    assert re.search(r'<select name="subject">', form)
    assert re.search(r'<textarea name="body"[^>]*required', form)
    assert ">Open in your email app<" in form, "the button says what it does"
    assert re.findall(r"<label class=\"field\"><span>([^<]+)</span>", form) == [
        "About",
        "Your message",
    ]
    for page in out.rglob("index.html"):
        assert 'href="/about/#feedback"' in page.read_text(), page
    privacy = (out / "privacy" / "index.html").read_text()
    assert "goes from your own email app to namratabhatia21@gmail.com" in privacy
    app = resources.files("clarchy").joinpath("static", "app.js").read_text()
    assert 'closest("#feedback-form")' in app and "encodeURIComponent(body)" in app


def test_one_contact_address_everywhere(built):
    """Every page that gives an email address gives the same one."""
    out, _content, _pages = built
    found = set()
    for page in out.rglob("*.html"):
        found |= set(re.findall(r'href="mailto:([^"?]+)', page.read_text()))
    assert found == {"namratabhatia21@gmail.com"}, found
