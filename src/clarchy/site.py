"""The web UI's pages, each at its own address, rendered from static/index.html.

One template holds every page between <!-- page:KEY --> and <!-- /page:KEY --> markers.
A multi-page build renders one document per address (/, /examples/, /pricing/, ...) with
only that page's section, its own title, description, canonical link, breadcrumbs and
structured data, and with the lists that scripts used to fill in (samples, examples,
services, posts) already in the HTML, so search engines and the first paint see the real
page. The scripts then take over and switch pages without reloading (app.js). A
single-page build, for hosts that take one file, keeps every section and hash links
(#pricing), as before.

`clarchy serve` renders these pages per request (web.py); `clarchy export-site` writes
them as files with a sitemap and robots.txt (export.py).
"""

from __future__ import annotations

import html
import json
import math
import re
from dataclasses import dataclass
from datetime import date
from functools import cache
from importlib import resources
from typing import Any

SITE_URL = "https://clarchy.com"
EMAIL = "namrata.bhatia@clarchy.com"
FOUNDER = "Namrata Bhatia"

HOME_TITLE = "Clarchy · Cloud architecture from your requirements"
HOME_DESCRIPTION = (
    "Paste a requirements brief and get a cloud architecture: drawn for AWS, Azure, "
    "Google Cloud and open source, priced, and checked against AI and data rules."
)

# Where each page lives. The menu marks a sub-page's parent (an example under Examples).
PATHS = {
    "plan": "/",
    "examples": "/examples/",
    "services": "/services/",
    "pricing": "/pricing/",
    "howto": "/how-to/",
    "blog": "/blog/",
    "about": "/about/",
    "privacy": "/privacy/",
    "terms": "/terms/",
}
PARENT = {"example": "examples", "post": "blog"}
SHEETS = {
    "plan": "01 · Plan",
    "examples": "02 · Examples",
    "example": "02 · Examples",
    "services": "03 · Services",
    "pricing": "04 · Pricing",
    "howto": "05 · How to",
    "blog": "06 · Blog",
    "post": "06 · Blog",
    "about": "07 · About",
    "privacy": "Privacy",
    "terms": "Terms",
}

# The same values as STAGE_COLOURS, PROVIDER_COLOURS and FIDELITY_HELP in core.js, so the
# pre-rendered Services page matches what the script draws (tests compare them).
STAGE_COLOURS = {
    "code": "#3B48CC",
    "build": "#6D28D9",
    "ship": "#0E7490",
    "serve": "#8C4FFF",
    "run": "#ED7100",
    "integrate": "#E7157B",
    "store": "#1D7A02",
    "operate": "#DD344C",
}
GREY = "#64748b"
PROVIDER_COLOURS = {"aws": "#ff9900", "azure": "#0078d4", "gcp": "#1a73e8", "oss": "#0d9488"}
FIDELITY_HELP = {
    "exact": "Same concept with comparable features on this provider.",
    "close": "Does the same job, with differences worth knowing (see note).",
    "partial": "Covers part of the capability; something else is needed for the rest.",
}

# Filters on the Examples page: a tag applies when a pattern uses any of its capabilities.
EXAMPLE_TAGS = [
    ("Kubernetes", ["kubernetes", "event-autoscaling"]),
    ("AI", ["llm-inference", "vector-search", "agent-orchestration", "llm-gateway"]),
    ("Data", ["stream", "batch-etl", "data-warehouse"]),
    ("Event-driven", ["message-queue", "event-bus", "workflow"]),
    ("Serverless", ["serverless-function"]),
    ("Containers", ["container-service"]),
    ("Web", ["cdn"]),
]

NUMBER_WORDS = [
    "Zero",
    "One",
    "Two",
    "Three",
    "Four",
    "Five",
    "Six",
    "Seven",
    "Eight",
    "Nine",
    "Ten",
]

PAGE_BLOCK = re.compile(
    r"[ \t]*<!-- page:(?P<key>[\w-]+) -->\n(?P<body>.*?)[ \t]*<!-- /page:(?P=key) -->\n", re.S
)
RENDER = re.compile(r"<!-- render:([\w-]+) -->")
SCRIPT_TAG = re.compile(r'<script src="/static/([\w-]+\.js)"></script>')


@dataclass(frozen=True)
class Page:
    key: str  # the template section
    path: str
    title: str
    description: str
    crumbs: tuple[tuple[str, str], ...] = ()  # (name, path) after Home, ending with this page
    sub: str | None = None  # the example or post shown
    indexed: bool = True  # listed in the sitemap

    @property
    def url(self) -> str:
        return SITE_URL + self.path


@dataclass(frozen=True)
class Content:
    """What the pages show, from the same payloads the API and the scripts use."""

    meta: dict[str, Any]
    samples: list[dict[str, Any]]
    patterns: list[dict[str, Any]]
    catalog: dict[str, Any]
    posts: list[dict[str, Any]]
    model: dict[str, str] | None = None  # the home page's massing model: figure, kicker, facts
    example_meta: dict[str, str] | None = None  # each example's facts line, as HTML


@dataclass(frozen=True)
class Shell:
    """How a build delivers its styles and scripts, and what the page can do."""

    mode: str  # "static" (plans in the browser), "replay" (samples only), "server", "remote"
    style: str  # head HTML for the stylesheet: a <link> or an inline <style>
    scripts: str | None = None  # replaces the template's /static/ script tags; None keeps them
    root: str | None = "/"  # where fonts, brand files and designs sit; None keeps /static/
    single: bool = False  # one page with every section and hash links
    fragment: bool = False  # no document skeleton (the host adds its own)


def content(meta: dict[str, Any]) -> Content:
    from clarchy import blog, catalog, payloads

    patterns = payloads.patterns_payload()
    designs = {}
    for p in patterns:
        status, design = payloads.design_payload(catalog.pattern_text(p["id"]), "aws")
        if status == 200:
            designs[p["id"]] = design
    return Content(
        meta=meta,
        samples=payloads.samples_payload(),
        patterns=patterns,
        catalog=payloads.catalog_payload(),
        posts=blog.posts(),
        model=_model("rag-chatbot") if "rag-chatbot" in designs else None,
        example_meta={pid: design_meta(d) for pid, d in designs.items()},
    )


def _poster_dial() -> str:
    """The poster's protractor: a full circle in degrees, with copy round its edge. It turns
    as the page scrolls (drafting.js)."""
    r, ticks, inner, nums = 182, [], [], []
    for d in range(0, 360, 2):
        a = math.radians(d - 90)
        r2 = r - (26 if d % 30 == 0 else 18 if d % 10 == 0 else 11)
        width = 1.6 if d % 10 == 0 else 0.9
        ticks.append(
            f'<line x1="{(r - 6) * math.cos(a):.1f}" y1="{(r - 6) * math.sin(a):.1f}" '
            f'x2="{r2 * math.cos(a):.1f}" y2="{r2 * math.sin(a):.1f}" stroke-width="{width}"/>'
        )
    for d in range(0, 360, 10):
        a = math.radians(d - 90)
        r2 = 74 if d % 30 == 0 else 80
        inner.append(
            f'<line x1="{88 * math.cos(a):.1f}" y1="{88 * math.sin(a):.1f}" '
            f'x2="{r2 * math.cos(a):.1f}" y2="{r2 * math.sin(a):.1f}"/>'
        )
    for d in range(0, 360, 30):
        a = math.radians(d - 90)
        x, y = (r - 42) * math.cos(a), (r - 42) * math.sin(a)
        turn = f"rotate({d} {x:.1f} {y:.1f})"
        nums.append(f'<text x="{x:.1f}" y="{y + 4:.1f}" transform="{turn}">{d}</text>')
    arc_r = 210
    a0, a1 = math.radians(152), math.radians(252)
    arc = (
        f"M{arc_r * math.cos(a0):.1f} {arc_r * math.sin(a0):.1f} "
        f"A{arc_r} {arc_r} 0 0 1 {arc_r * math.cos(a1):.1f} {arc_r * math.sin(a1):.1f}"
    )
    return (
        '<svg viewBox="-240 -240 480 480" class="dial-art">'
        f'<defs><path id="poster-arc" d="{arc}"/></defs>'
        f'<circle class="pd-shadow" cx="10" cy="12" r="{r}"/>'
        '<g class="pd-dial">'
        f'<circle class="pd-face" r="{r}"/><circle class="pd-ring" r="{r - 56}"/>'
        f'<g class="pd-ticks">{"".join(ticks)}{"".join(inner)}</g>'
        f'<g class="pd-nums">{"".join(nums)}</g>'
        f'<path class="pd-cross" d="M{-r + 8} 0H{r - 8}M0 {-r + 8}V{r - 8}"/></g>'
        '<line class="pd-needle" x1="0" y1="0" x2="-84.5" y2="134.8"/>'
        '<circle class="pd-needle-tip" cx="-84.5" cy="134.8" r="5"/>'
        '<circle class="pd-hub" r="22"/><circle class="pd-pin" r="6"/>'
        '<text class="pd-reading" y="62">212°</text>'
        '<text class="pd-arc"><textPath href="#poster-arc" textLength="345" lengthAdjust="spacing">'
        "FROM SOURCE CONTROL TO MONITORING</textPath></text></svg>"
    )


def _poster_art() -> str:
    """The poster's stamps, marks and pencil loops (on a 1440 x 820 sheet)."""

    def mark(x: float, y: float, r: float = 8) -> str:
        return (
            f'<g class="pa-mark"><circle cx="{x}" cy="{y}" r="{r}"/>'
            f'<path d="M{x - r - 6} {y}h{2 * r + 12}M{x} {y - r - 6}v{2 * r + 12}"/></g>'
        )

    cx, cy = 1190, 134
    return (
        '<svg class="poster-art" viewBox="0 0 1440 820" preserveAspectRatio="none" '
        'aria-hidden="true"><defs>'
        f'<path id="poster-ring" d="M{cx - 62} {cy}a62 62 0 1 1 124 0a62 62 0 1 1 -124 0"/></defs>'
        f'<g class="pa-stamp" transform="rotate(-14 {cx} {cy})">'
        f'<circle cx="{cx}" cy="{cy}" r="78" stroke-width="2.4"/>'
        f'<circle cx="{cx}" cy="{cy}" r="46" stroke-width="1.2"/>'
        '<text><textPath href="#poster-ring" textLength="384" lengthAdjust="spacing">'
        "FOUR CLOUDS · ONE BRIEF · PRICED ·</textPath></text>"
        f'<path d="M{cx - 18} {cy}h36M{cx} {cy - 18}v36" stroke-width="2"/></g>'
        '<path class="pa-loop" d="M812 70 c 26 -40, 54 -40, 40 -6 c -12 30, 30 30, 46 -2 '
        'c 14 -30, 44 -26, 34 4"/>'
        + mark(1350, 390, 7)
        + mark(1010, 480, 9)
        + mark(110, 440)
        + mark(150, 560, 7)
        + "</svg>"
    )


# The closing frame's pantograph (plate K of Bion's instruments): a fixed pivot, two long
# bars and a parallelogram, so the pencil always sits twice as far from the pivot as the
# tracer. drafting.js moves it with the same sums as the page scrolls.
PANTOGRAPH_PIVOT = (44.0, 206.0)
PANTOGRAPH_BAR = 190.0  # each long bar, pivot to elbow and elbow to pencil
# A small sketch of three services in a row, traced in one stroke (some lines twice).
_SKETCH = [
    (0, 6), (14, 6), (14, 11), (24, 11), (24, 0), (38, 0), (38, 11), (49, 11), (49, 6),
    (63, 6), (63, 17), (49, 17), (49, 11), (38, 11), (38, 22), (24, 22), (24, 11), (14, 11),
    (14, 17), (0, 17), (0, 6),
]  # fmt: skip
PANTOGRAPH_SKETCH = [(136 + 1.3 * x, 186 + 1.3 * y) for x, y in _SKETCH]


def pantograph(t: tuple[float, float]) -> dict[str, tuple[float, float]]:
    """The linkage's joints with the tracer at t: the pivot O, the elbow J above the line
    from O to the pencil P, the bars' midpoints C and D, and the tracer T."""
    (ox, oy), bar = PANTOGRAPH_PIVOT, PANTOGRAPH_BAR
    px, py = ox + 2 * (t[0] - ox), oy + 2 * (t[1] - oy)
    dx, dy = px - ox, py - oy
    d = math.hypot(dx, dy)
    h = math.sqrt(max(bar * bar - d * d / 4, 0.0))
    nx, ny = -dy / d, dx / d
    if ny > 0:  # take the elbow above the line, so the bars stand like an A
        nx, ny = -nx, -ny
    jx, jy = (ox + px) / 2 + h * nx, (oy + py) / 2 + h * ny
    return {
        "O": (ox, oy),
        "J": (jx, jy),
        "P": (px, py),
        "C": ((ox + jx) / 2, (oy + jy) / 2),
        "D": ((jx + px) / 2, (jy + py) / 2),
        "T": t,
    }


def _coda_pantograph() -> str:
    """The closing frame's instrument: a pantograph on a sheet, its tracer on a small
    sketch and its pencil drawing the same sketch at twice the size. It is drawn finished;
    drafting.js runs it from the start as the frame scrolls into view."""

    def pts(points) -> str:
        return " ".join(f"{x:g},{y:g}" for x, y in points)

    def path(points) -> str:
        return "M" + "L".join(f"{x:g} {y:g}" for x, y in points)

    ox, oy = PANTOGRAPH_PIVOT
    copy = [(ox + 2 * (x - ox), oy + 2 * (y - oy)) for x, y in PANTOGRAPH_SKETCH]
    j = pantograph(PANTOGRAPH_SKETCH[-1])

    def bar(name: str, a: str, b: str) -> str:
        (x1, y1), (x2, y2) = j[a], j[b]
        line = f'x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}"'
        return f'<line class="cg-bar {name}" {line}/><line class="cg-bar-in {name}" {line}/>'

    def joint(name: str, r: float) -> str:
        x, y = j[name]
        return (
            f'<g class="cg-joint cg-{name.lower()}" transform="translate({x:.1f} {y:.1f})">'
            f'<circle r="{r:g}"/><path d="M{-r * 0.55:g} 0H{r * 0.55:g}"/></g>'
        )

    tx, ty = j["T"]
    px, py = j["P"]
    return (
        '<svg class="coda-pantograph" viewBox="0 0 440 300" aria-hidden="true" '
        f'data-pivot="{pts([PANTOGRAPH_PIVOT])}" data-bar="{PANTOGRAPH_BAR:g}" '
        f'data-sketch="{pts(PANTOGRAPH_SKETCH)}">'
        '<rect class="cg-shadow" x="22" y="22" width="410" height="272"/>'
        '<rect class="cg-sheet" x="12" y="10" width="410" height="272"/>'
        '<text class="cg-mark" x="398" y="40">K</text>'
        '<text class="cg-note" x="30" y="262">PANTOGRAPH · COPIES AT 2 : 1</text>'
        f'<path class="cg-sketch" d="{path(PANTOGRAPH_SKETCH)}"/>'
        f'<path class="cg-copy" d="{path(copy)}" pathLength="1"/>'
        + bar("oj", "O", "J")
        + bar("jp", "J", "P")
        + bar("ct", "C", "T")
        + bar("dt", "D", "T")
        + f'<g class="cg-base"><circle cx="{ox:g}" cy="{oy:g}" r="12"/>'
        f'<circle cx="{ox:g}" cy="{oy:g}" r="4"/></g>'
        + joint("J", 7)
        + joint("C", 5.5)
        + joint("D", 5.5)
        + f'<g class="cg-tracer" transform="translate({tx:.1f} {ty:.1f})">'
        '<circle r="5"/><path d="M0 -5V-26M-4 -26H4"/></g>'
        f'<g class="cg-pencil" transform="translate({px:.1f} {py:.1f})">'
        '<path d="M0 0L-4 -12H4Z"/><path d="M-4 -12V-34H4V-12"/></g></svg>'
    )


def _coda_register(c: Content, shown: int = 4) -> str:
    """The first examples, listed like a drawing register, each linking to its page."""
    rows = "".join(
        f'<li><a href="{PATHS["examples"]}{_e(p["id"])}/"><span class="no">{i:02d}</span>'
        f'<span class="nm">{_e(p["name"])}</span>'
        f'<span class="sv">{_plural(int(p.get("components") or 0), "service")}</span></a></li>'
        for i, p in enumerate(c.patterns[:shown], 1)
    )
    return f'<ol class="coda-list">{rows}</ol>'


def _model(example: str) -> dict[str, str]:
    """The home page's massing model of an example on AWS, at today's prices (ADR 0015):
    the figure, the line above the headline and the facts under the brief."""
    from clarchy import massing, pricing
    from clarchy.icons import bundled_library
    from clarchy.mapping import map_to_provider
    from clarchy.spec import load_pattern

    arch = map_to_provider(load_pattern(example), "aws")
    cost = pricing.estimate(arch)
    running = len(massing.layout(arch, cost)[0])
    as_of = _short_date(str(cost["as_of"]))
    figure = (
        '<figure class="hero-model" id="hero-model">'
        f"{massing.svg(arch, cost, bundled_library('aws'))}"
        '<figcaption><span class="legend">Scale 1:100 · block height is monthly cost<br>'
        "Dashed zones: serve · run · integrate · store · operate</span>"
        f'<a href="/examples/{example}/">Open it on every cloud</a></figcaption></figure>'
    )
    return {
        "figure": figure,
        "kicker": f"Model 01 · {_e(arch.spec.name)} on AWS",
        "facts": (
            f'<p class="model-facts"><i></i>{_e(cost["price_region"])} · '
            f"{_money(cost['monthly'])} a month · {_plural(running, 'running service')}<br>"
            f"AWS list prices of {_e(as_of)}, refreshed daily</p>"
        ),
    }


@cache
def template() -> str:
    return resources.files("clarchy").joinpath("static", "index.html").read_text(encoding="utf-8")


def _clip(text: str, limit: int = 160) -> str:
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rsplit(" ", 1)[0].rstrip(",;:") + "…"


def pages(c: Content) -> list[Page]:
    """Every address of the site, in menu order."""
    n = len(c.catalog["capabilities"])
    examples = (("Examples", PATHS["examples"]),)
    out = [
        Page("plan", "/", HOME_TITLE, HOME_DESCRIPTION),
        Page(
            "examples",
            PATHS["examples"],
            "Cloud architecture examples for AWS, Azure and GCP · Clarchy",
            _clip(
                f"{_count_word(len(c.patterns))} reference architectures, from a RAG chatbot to "
                "Kubernetes microservices, each drawn and priced on AWS, Azure, Google Cloud "
                "and open source."
            ),
            examples,
        ),
    ]
    for p in c.patterns:
        path = f"{PATHS['examples']}{p['id']}/"
        out.append(
            Page(
                "example",
                path,
                f"{p['name']} on AWS, Azure and GCP · Clarchy",
                _clip(f"{p['summary']} Drawn and priced on every cloud by Clarchy."),
                (*examples, (p["name"], path)),
                sub=p["id"],
            )
        )
    out += [
        Page(
            "services",
            PATHS["services"],
            "AWS, Azure and Google Cloud service equivalents · Clarchy",
            _clip(
                f"The service that does each of {n} jobs on AWS, Azure, Google Cloud and open "
                "source, side by side, with where they differ and links to the documentation."
            ),
            (("Services", PATHS["services"]),),
        ),
        Page(
            "pricing",
            PATHS["pricing"],
            "Pricing · Clarchy",
            "Start free: your first 3 diagrams from your own briefs, with unlimited samples "
            "and examples. Pro, with unlimited diagrams, is in early access.",
            (("Pricing", PATHS["pricing"]),),
        ),
        Page(
            "howto",
            PATHS["howto"],
            "How to use Clarchy: from a brief to a cloud architecture",
            "Write a brief, plan it, read the drawing, check costs, policies and workflows, "
            "answer open questions and share the design, step by step.",
            (("How to", PATHS["howto"]),),
        ),
        Page(
            "blog",
            PATHS["blog"],
            "Blog · Clarchy",
            "Worked examples and notes on planning cloud and AI systems, from Clarchy.",
            (("Blog", PATHS["blog"]),),
            indexed=bool(c.posts),
        ),
    ]
    for post in c.posts:
        path = f"{PATHS['blog']}{post['id']}/"
        out.append(
            Page(
                "post",
                path,
                f"{post['title']} · Clarchy",
                _clip(post["summary"]),
                (("Blog", PATHS["blog"]), (post["title"], path)),
                sub=post["id"],
            )
        )
    out += [
        Page(
            "about",
            PATHS["about"],
            "About Clarchy",
            "Clarchy turns a requirements brief into a cloud architecture you can question, "
            f"price and compare across clouds. Founded by {FOUNDER}.",
            (("About", PATHS["about"]),),
        ),
        Page(
            "privacy",
            PATHS["privacy"],
            "Privacy · Clarchy",
            "What Clarchy keeps about you, why, where, and how to have it deleted. Your briefs "
            "and documents are planned in your browser and never uploaded.",
            (("Privacy", PATHS["privacy"]),),
        ),
        Page(
            "terms",
            PATHS["terms"],
            "Terms of use · Clarchy",
            "The terms for using clarchy.com: free diagrams and the Pro waitlist, estimates "
            "that are not quotes, and designs as a starting point for your own review.",
            (("Terms", PATHS["terms"]),),
        ),
    ]
    return out


# ---------- small helpers ----------
def _e(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _count_word(n: int) -> str:
    return NUMBER_WORDS[n] if 0 <= n < len(NUMBER_WORDS) else str(n)


def _plural(n: int, word: str, many: str | None = None) -> str:
    return f"{n:,} {word if n == 1 else (many or word + 's')}"


def _money(value: float) -> str:
    digits = 2 if abs(value) < 10 else 0
    return f"${value:,.{digits}f}"


def _number(value: Any) -> str:
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return f"{value:,}" if isinstance(value, int | float) else str(value)


def design_meta(d: dict[str, Any]) -> str:
    """A design's facts line, as workspace.js writes it under the title."""
    prov = d.get("provenance") or {}
    if prov.get("mode") == "ai":
        origin = f"AI design ({prov.get('model')})"
    elif prov.get("mode") == "rules":
        origin = "Rule-based draft"
    else:
        origin = "Reference architecture"
    region, r = d["region"], d["requirements"]
    items = [
        origin,
        f"{region['label']} ({region['code']})" if region.get("code") else region["label"],
    ]
    if r.get("users") is not None:
        items.append(f"{_number(r['users'])} users")
    if r.get("peak_rps") is not None:
        items.append(f"{_number(r['peak_rps'])} req/s peak")
    if r.get("data_gb") is not None:
        items.append(f"{_number(r['data_gb'])} GB data")
    items.append(f"{r['availability_target']}% availability")
    if r.get("compliance"):
        items.append(", ".join(r["compliance"]))
    out = "".join(f"<span>{_e(item)}</span>" for item in items)
    if d["cost"].get("available"):
        out += f"<span><b>≈ {_e(_money(d['cost']['monthly']))} a month</b></span>"
    return out


def _long_date(iso: str) -> str:
    try:
        d = date.fromisoformat(iso)
    except ValueError:
        return iso
    return f"{d.day} {d.strftime('%B')} {d.year}"


def _short_date(iso: str) -> str:
    try:
        d = date.fromisoformat(iso)
    except ValueError:
        return iso
    return f"{d.day} {d.strftime('%b')} {d.year}"


def example_tags(pattern: dict[str, Any]) -> list[str]:
    caps = set(pattern.get("capabilities") or [])
    return [tag for tag, wanted in EXAMPLE_TAGS if caps.intersection(wanted)]


def to_hash(path: str) -> str | None:
    """The single-page (#hash) form of a page address, or None for other links."""
    bare, _, anchor = path.partition("#")
    parts = [p for p in bare.split("/") if p]
    if not parts:
        return "#plan"
    keys = {v.strip("/"): k for k, v in PATHS.items() if v != "/"}
    key = keys.get(parts[0])
    if key is None or len(parts) > 2:
        return None
    if len(parts) == 2:
        return f"#{key}/{parts[1]}" if key in ("examples", "blog") else None
    if key == "howto" and anchor.startswith("howto-"):
        return f"#howto/{anchor.removeprefix('howto-')}"
    return f"#{key}"


# ---------- the pre-rendered parts ----------
def _engine_chip(shell: Shell, meta: dict[str, Any]) -> str:
    if shell.mode == "static":
        return (
            '<span class="engine-chip demo" id="engine-chip" '
            'title="Plans run on this device with Clarchy\'s Python engine (Pyodide)">'
            "Runs in your browser</span>"
        )
    if shell.mode == "replay":
        return '<span class="engine-chip demo" id="engine-chip">Demo</span>'
    if shell.mode == "server":
        engine = meta.get("engine") or {}
        if engine.get("mode") == "ai":
            label, model = _e(engine.get("label") or ""), _e(engine.get("model") or "")
            return (
                f'<span class="engine-chip ai" id="engine-chip" title="{label}">AI · {model}</span>'
            )
        return (
            f'<span class="engine-chip" id="engine-chip" title="{_e(engine.get("reason") or "")}">'
            "Rule-based planner</span>"
        )
    return '<span class="engine-chip" id="engine-chip" hidden></span>'


def _composer_foot(shell: Shell) -> str:
    if shell.mode == "static":
        text = (
            "Runs in your browser. The first plan downloads the planning engine (about "
            "15&nbsp;MB). Word, PDF, Excel, Markdown or text, up to 10&nbsp;MB."
        )
    else:
        text = (
            "Word, PDF, Excel, Markdown or text, up to 10&nbsp;MB · <kbd>Ctrl</kbd>+"
            "<kbd>Enter</kbd> to start"
        )
    hidden = " hidden" if shell.mode == "replay" else ""
    return f'<p class="composer-foot" id="composer-foot"{hidden}>{text}</p>'


def _credit_line(shell: Shell) -> str:
    # On clarchy.com the line appears once the account API answers (access.js); its space
    # is kept from the start so nothing below it moves.
    if shell.mode == "static":
        return (
            '<p class="credit-line pending" id="credit-line">Your first '
            '<span data-free-count>3</span> diagrams are free. <a href="/pricing/">Pricing</a></p>'
        )
    return '<p class="credit-line" id="credit-line" hidden></p>'


def _samples(c: Content) -> str:
    items = []
    for s in c.samples:
        hint = " ".join(s["text"].split("\n")[1:]).strip()[:220]
        items.append(
            f'<li><button type="button" class="chip sample" title="{_e(hint)}" '
            f'data-sample="{_e(s["id"])}">{_e(s["title"])}</button></li>'
        )
    return "".join(items)


def _regions(c: Content) -> str:
    return "".join(
        f'<option value="{_e(k)}">{_e(v)}</option>' for k, v in c.meta.get("regions", {}).items()
    )


def _example_filters(c: Content) -> str:
    present = [t for t, _ in EXAMPLE_TAGS if any(t in example_tags(p) for p in c.patterns)]
    return "".join(
        f'<button type="button" class="chip" aria-pressed="{str(t == "All").lower()}" '
        f'data-tag="{_e(t)}">{_e(t)}</button>'
        for t in ["All", *present]
    )


def _example_grid(c: Content) -> str:
    cards = []
    for i, p in enumerate(c.patterns, 1):
        tags = example_tags(p)
        pid, name, summary = _e(p["id"]), _e(p["name"]), _e(p.get("summary") or "")
        cards.append(
            f'<li data-tags="{_e("|".join(tags))}">'
            f'<a class="example-card" href="{PATHS["examples"]}{pid}/" data-id="{pid}">'
            f'<div class="example-thumb"><img alt="Architecture drawing of {name} on AWS"></div>'
            f'<div class="example-body"><h2>{name}</h2><p>{summary}</p></div>'
            '<dl class="card-block">'
            f"<div><dt>No.</dt><dd>{i:02d}</dd></div>"
            f"<div><dt>Type</dt><dd>{_e(' · '.join(tags[:2]) or 'General')}</dd></div>"
            f"<div><dt>Services</dt><dd>{int(p.get('components') or 0)}</dd></div>"
            "</dl></a></li>"
        )
    return "".join(cards)


def _example_head(c: Content, page: Page) -> str:
    pattern = next((p for p in c.patterns if p["id"] == page.sub), None)
    if not pattern:
        return ""
    summary = pattern.get("summary") or ""
    return (
        '<div class="ws-head"><div class="ws-title">'
        f'<h1 class="ws-name">{_e(pattern["name"])}</h1>'
        f'<p class="ws-summary"{"" if summary else " hidden"}>{_e(summary)}</p>'
        f'<p class="ws-meta">{(c.example_meta or {}).get(pattern["id"], "")}</p></div></div>'
    )


def _fidelity_tag(f: str | None) -> str:
    if not f or f == "exact":
        return "<span></span>"
    label = "Close" if f == "close" else "Partial"
    return f'<span class="tag {_e(f)}" title="{_e(FIDELITY_HELP[f])}">{label}</span>'


def _services(c: Content) -> dict[str, str]:
    stages = c.meta.get("stages", {})
    order = list(stages)
    providers = c.catalog["providers"]
    caps = sorted(c.catalog["capabilities"], key=lambda cap: order.index(cap["stage"]))
    counts = {s: sum(1 for cap in caps if cap["stage"] == s) for s in order}
    stage_buttons = "".join(
        '<button class="filter-item" type="button" aria-pressed="false">'
        f'<span class="dot" style="background:{STAGE_COLOURS.get(s, GREY)}"></span>{_e(name)}'
        f'<span class="n">{counts[s]}</span></button>'
        for s, name in stages.items()
    )
    provider_buttons = "".join(
        '<button class="filter-item" type="button" aria-pressed="true">'
        f'<span class="check" aria-hidden="true"></span>{_e(p["name"])}</button>'
        for p in providers
    )
    match = "".join(
        f'<button type="button" aria-pressed="{str(key == "all").lower()}">{label}</button>'
        for key, label in (("all", "All"), ("differences", "Differences"), ("exact", "Exact"))
    )
    cards = []
    for cap in caps:
        rows = "".join(
            '<span class="svc-prov">'
            f'<span class="dot" style="background:{PROVIDER_COLOURS.get(p["id"], GREY)}"></span>'
            f"{_e(p['name'])}</span>"
            f'<span class="svc-name" title="{_e(cap["services"][p["id"]]["service"])}">'
            f"{_e(cap['services'][p['id']]['service'])}</span>"
            f"{_fidelity_tag(cap['services'][p['id']]['fidelity'])}"
            for p in providers
        )
        cards.append(
            '<li class="cap-card"><button type="button" aria-expanded="false">'
            '<div class="cap-title">'
            f'<h2 title="{_e(cap["id"])}">{_e(cap["title"])}</h2>'
            '<span class="cap-stage">'
            f'<span class="dot" style="background:{STAGE_COLOURS.get(cap["stage"], GREY)}"></span>'
            f"{_e(stages.get(cap['stage'], ''))}</span></div>"
            f'<p class="cap-desc">{_e(cap["description"])}</p>'
            f'<div class="svc-rows">{rows}</div></button></li>'
        )
    unreviewed = [p["name"] for p in providers if not p.get("reviewed")]
    review = (
        f'<p id="catalog-review">The {_e(", ".join(unreviewed))} mappings are a draft that a '
        "specialist has not reviewed yet; each card links to the documentation.</p>"
        if unreviewed
        else '<p id="catalog-review" hidden></p>'
    )
    total = len(caps)
    return {
        "filter-stages": stage_buttons,
        "filter-providers": provider_buttons,
        "filter-match": match,
        "catalog-results": "".join(cards),
        "catalog-count": f"{total} of {total}",
        "catalog-review": review,
    }


def _post_list(c: Content) -> str:
    items = "".join(
        f'<li><a class="post-card" href="{PATHS["blog"]}{_e(p["id"])}/">'
        f"<h2>{_e(p['title'])}</h2><p>{_e(p['summary'])}</p>"
        f'<span class="post-meta">{_e(_long_date(p["date"]))} · {_e(p["author"])} · '
        f"{p['minutes']} min read</span></a></li>"
        for p in c.posts
    )
    empty = (
        '<p class="blog-empty" id="post-list-empty"'
        + (" hidden" if c.posts else "")
        + ">The first posts are coming soon. Until then, "
        f'<a href="{PATHS["howto"]}">How to use Clarchy</a> walks through planning a brief, and '
        f'<a href="{PATHS["examples"]}">Examples</a> shows reference architectures on every '
        "cloud.</p>"
    )
    hidden = "" if c.posts else " hidden"
    return f'<ul class="post-list" id="post-list"{hidden}>{items}</ul>\n      {empty}'


def post_html(post: dict[str, Any]) -> str:
    """One post's article, as blog.js also draws it. The body was rendered from the post's
    own Markdown with every piece of text escaped (blog.to_html)."""
    role = f", {_e(post['role'])}" if post.get("role") else ""
    return (
        f'<p class="post-date">{_e(_long_date(post["date"]))}</p>'
        f'<h1 class="post-title">{_e(post["title"])}</h1>'
        f'<p class="post-byline"><a href="{PATHS["about"]}#author">{_e(post["author"])}</a>'
        f"{role} · {post['minutes']} min read</p>"
        f'<div class="post-body">{post["html"]}</div>'
        f'<p class="post-author">{_e(post["author"])} is the founder of Clarchy.</p>'
        '<div class="post-foot">'
        f'<a class="btn btn-primary" href="{PATHS["plan"]}">Try it with your brief</a>'
        f'<a class="btn btn-ghost" href="{PATHS["blog"]}">More posts</a></div>'
    )


def _crumbs(page: Page | None, key: str) -> str:
    """Breadcrumbs for a section; the last one names the page and is updated by the
    scripts when they show another example or post in the same section."""
    if key == "plan":
        return ""
    if page is not None and page.key == key:
        trail = page.crumbs
    elif key in PARENT:
        parent = PARENT[key]
        trail = ((parent.capitalize(), PATHS[parent]), ("", ""))
    else:
        names = {"howto": "How to", "about": "About", "privacy": "Privacy", "terms": "Terms"}
        trail = ((names.get(key, key.capitalize()), PATHS[key]),)
    items = ['<li><a href="/">Home</a></li>']
    for i, (name, path) in enumerate(trail):
        if i == len(trail) - 1:
            items.append(f'<li><span aria-current="page" data-crumb>{_e(name)}</span></li>')
        else:
            items.append(f'<li><a href="{_e(path)}">{_e(name)}</a></li>')
    return f'<nav class="crumbs" aria-label="Breadcrumb"><ol>{"".join(items)}</ol></nav>'


# ---------- structured data ----------
def _organization() -> list[dict[str, Any]]:
    return [
        {
            "@type": "Organization",
            "@id": f"{SITE_URL}/#organization",
            "name": "Clarchy",
            "url": f"{SITE_URL}/",
            "logo": f"{SITE_URL}/apple-touch-icon.png",
            "email": EMAIL,
            "founder": {"@id": f"{SITE_URL}/about/#founder"},
        },
        {
            "@type": "Person",
            "@id": f"{SITE_URL}/about/#founder",
            "name": FOUNDER,
            "jobTitle": "Founder",
            "url": f"{SITE_URL}/about/#author",
            "worksFor": {"@id": f"{SITE_URL}/#organization"},
        },
    ]


def _faq(section: str) -> list[dict[str, Any]]:
    faq = re.search(r'class="prose-page faq".*?<dl>(.*?)</dl>', section, re.S)
    if not faq:
        return []

    def text(fragment: str) -> str:
        return html.unescape(re.sub(r"<[^>]+>", "", fragment)).strip()

    return [
        {
            "@type": "Question",
            "name": text(q),
            "acceptedAnswer": {"@type": "Answer", "text": text(a)},
        }
        for q, a in re.findall(r"<dt>(.*?)</dt>\s*<dd>(.*?)</dd>", faq.group(1), re.S)
    ]


def structured_data(page: Page, section: str = "") -> dict[str, Any]:
    graph: list[dict[str, Any]] = []
    if page.key == "plan":
        graph += _organization()
        graph += [
            {
                "@type": "WebSite",
                "@id": f"{SITE_URL}/#website",
                "name": "Clarchy",
                "url": f"{SITE_URL}/",
                "publisher": {"@id": f"{SITE_URL}/#organization"},
            },
            {
                "@type": "WebApplication",
                "name": "Clarchy",
                "url": f"{SITE_URL}/",
                "description": HOME_DESCRIPTION,
                "applicationCategory": "DeveloperApplication",
                "operatingSystem": "Any, in a web browser",
                "offers": {
                    "@type": "Offer",
                    "price": "0",
                    "priceCurrency": "USD",
                    "description": "Your first 3 diagrams are free",
                },
                "publisher": {"@id": f"{SITE_URL}/#organization"},
            },
        ]
    else:
        graph.append(
            {
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {"@type": "ListItem", "position": i, "name": name, "item": SITE_URL + path}
                    for i, (name, path) in enumerate((("Home", "/"), *page.crumbs), 1)
                ],
            }
        )
    if page.key == "pricing":
        questions = _faq(section)
        if questions:
            graph.append({"@type": "FAQPage", "mainEntity": questions})
    if page.key == "about":
        graph += _organization()
        graph.append(
            {
                "@type": "AboutPage",
                "url": page.url,
                "name": page.title,
                "mainEntity": {"@id": f"{SITE_URL}/#organization"},
            }
        )
    return {"@context": "https://schema.org", "@graph": graph}


def _json_ld(data: dict[str, Any]) -> str:
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    return f'<script type="application/ld+json">{text}</script>'


# ---------- assembling a document ----------
def _split(template_text: str) -> tuple[str, str]:
    head = template_text[template_text.index("<head>") + 6 : template_text.index("</head>")]
    opening = re.search(r"<body(?:<!-- render:body-attrs -->)?[^>]*>", template_text)
    body = template_text[opening.end() : template_text.index("</body>")]
    return head, body


def _set_meta(head: str, page: Page) -> str:
    def attr(pattern: str, value: str) -> None:
        nonlocal head
        head, n = re.subn(pattern, lambda m: m.group(1) + _e(value) + m.group(2), head)
        if n != 1:
            raise ValueError(f"index.html head: expected one match for {pattern}")

    head = re.sub(r"<title>.*?</title>", f"<title>{_e(page.title)}</title>", head, count=1)
    attr(r'(<meta name="description" content=")[^"]*(">)', page.description)
    attr(r'(<meta property="og:title" content=")[^"]*(">)', page.title)
    attr(r'(<meta property="og:description" content=")[^"]*(">)', page.description)
    attr(r'(<meta property="og:url" content=")[^"]*(">)', page.url)
    attr(r'(<link rel="canonical" href=")[^"]*(">)', page.url)
    return head


def _fill(body: str, values: dict[str, str]) -> str:
    def repl(m: re.Match) -> str:
        name = m.group(1)
        if name not in values:
            raise ValueError(f"index.html: nothing renders <!-- render:{name} -->")
        return values[name]

    return RENDER.sub(repl, body)


def _hash_links(text: str) -> str:
    def repl(m: re.Match) -> str:
        target = to_hash(m.group(1))
        return f'href="{target}"' if target else m.group(0)

    return re.sub(r'href="(/(?!static/)[^"]*)"', repl, text)


def page_index(c: Content) -> dict[str, list[str]]:
    """Title and description of every address, for the scripts to update the head when
    they switch pages without reloading."""
    return {p.path: [p.title, p.description] for p in pages(c)}


def render(page: Page | None, c: Content, shell: Shell) -> str:
    """One page (multi-page builds), or with page=None and shell.single, every page."""
    head, body = _split(template())
    key = page.key if page else "plan"

    def section(m: re.Match) -> str:
        k = m.group("key")
        if not shell.single and k != key:
            return ""
        block = m.group("body").replace("<!-- crumbs -->", _crumbs(page, k))
        if not shell.single:
            block = re.sub(r'(<section class="page[^>]*?) hidden>', r"\1>", block, count=1)
        return block

    body = PAGE_BLOCK.sub(section, body)
    if not shell.single and f'id="page-{key}"' not in body:
        raise ValueError(f"index.html has no page:{key} section")
    nav = PARENT.get(key, key)
    body = body.replace(
        f'class="main-link" data-page="{nav}"',
        f'class="main-link" data-page="{nav}" aria-current="page"',
    )
    as_of = c.meta.get("prices_as_of")
    attrs = f' data-page="{key}" data-routing="{"hash" if shell.single else "path"}"'
    if shell.root is not None:
        attrs += f' data-root="{_e(shell.root)}"'
    values = {
        "body-attrs": attrs,
        "engine-chip": _engine_chip(shell, c.meta),
        "composer-foot": _composer_foot(shell),
        "credit-line": _credit_line(shell),
        "static-note-hidden": "" if shell.mode == "replay" else " hidden",
        "regions": _regions(c),
        "samples": _samples(c),
        "hero-model": c.model["figure"] if c.model else "",
        "model-kicker": c.model["kicker"] if c.model else "",
        "model-facts": c.model["facts"] if c.model else "",
        "poster-dial": _poster_dial(),
        "poster-art": _poster_art(),
        "coda-pantograph": _coda_pantograph(),
        "coda-register": _coda_register(c),
        "example-count": _count_word(len(c.patterns)),
        "example-filters": _example_filters(c),
        "example-grid": _example_grid(c),
        "example-head": _example_head(c, page) if page and page.key == "example" else "",
        "post-list": _post_list(c),
        "post": post_html(next(p for p in c.posts if p["id"] == page.sub))
        if page and page.key == "post"
        else "",
        "sheet": SHEETS[key],
        "prices-as-of": f"AWS, {_short_date(as_of)}" if as_of else "–",
        "copyright": f"© {date.today().year} Clarchy",
        "version-title": f' title="Clarchy {_e(c.meta.get("version", ""))}"',
        **_services(c),
    }
    body = _fill(body, values)
    if shell.single:
        body = _hash_links(body)
    if shell.scripts is not None:
        tags = SCRIPT_TAG.findall(body)
        if not tags:
            raise ValueError("index.html no longer references its /static/ scripts")
        first = body.index(f'<script src="/static/{tags[0]}"></script>')
        body = body[:first] + shell.scripts + SCRIPT_TAG.sub("", body[first:])
        body = re.sub(r"(\n[ \t]*)+\n", "\n", body)

    head = re.sub(r'[ \t]*<link rel="stylesheet" href="/static/app.css">\n', "", head)
    if page is not None:
        head = _set_meta(head, page)
        sect = re.search(rf'<section class="page[^>]*id="page-{key}".*', body, re.S)
        head += f"  {_json_ld(structured_data(page, sect.group(0) if sect else ''))}\n"
        if not shell.single:
            index = json.dumps(page_index(c), ensure_ascii=False, separators=(",", ":"))
            index = index.replace("<", "\\u003c")
            head += f'  <script type="application/json" id="site-pages">{index}</script>\n'
    head += f"  {shell.style}\n"

    if shell.fragment:
        title = re.search(r"<title>.*?</title>", head, re.S).group(0)
        page_only = ('rel="icon"', 'rel="apple-touch-icon"', 'rel="canonical"', 'rel="preload"')
        links = [
            line.strip()
            for line in head.splitlines()
            if line.strip().startswith("<link") and not any(r in line for r in page_only)
        ]
        out = "\n".join([title, *links, shell.style, body.strip()]) + "\n"
    else:
        out = (
            '<!doctype html>\n<html lang="en">\n<head>'
            + head
            + f"</head>\n<body{values['body-attrs']}>\n"
            + body.strip()
            + "\n</body>\n</html>\n"
        )
    if shell.root is not None:
        out = out.replace("/static/fonts/", f"{shell.root}fonts/").replace(
            "/static/brand/", shell.root
        )
        if "/static/" in out:
            raise ValueError("the page still references /static/ files")
    return out


# ---------- files beside the pages ----------
def sitemap(c: Content) -> str:
    urls = "".join(f"  <url><loc>{_e(p.url)}</loc></url>\n" for p in pages(c) if p.indexed)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{urls}</urlset>\n"
    )


def redirects(c: Content) -> str:
    """Cloudflare's _redirects: an address typed without its final slash, or as index.html,
    moves permanently to the one the canonical links use, in a single hop."""
    lines = [
        "# Every page's address ends in a slash; these send the other spellings there.",
        "/index.html / 301",
    ]
    for p in pages(c):
        if p.path != "/":
            lines.append(f"{p.path.rstrip('/')} {p.path} 301")
            lines.append(f"{p.path}index.html {p.path} 301")
    return "\n".join(lines) + "\n"


ROBOTS = f"""# Every page of Clarchy may be crawled; /api/ only serves sign-ups and credits.
User-agent: *
Allow: /
Disallow: /api/

Sitemap: {SITE_URL}/sitemap.xml
"""

# Cloudflare applies these to the static files (wrangler.jsonc serves site/).
HEADERS = """# Scripts and data have a content hash in their names, so they can be kept for a year.
/assets/*
  Cache-Control: public, max-age=31536000, immutable

/fonts/*
  Cache-Control: public, max-age=2592000

# The workers.dev copy of the site stays out of search results; clarchy.com is the one.
https://:version.:subdomain.workers.dev/*
  X-Robots-Tag: noindex
"""
