"""Every service each cloud offers, from the provider's own product list.

    python -m clarchy.directory --provider aws     # writes data/directory/aws.yaml

The Services page lists Clarchy's building blocks; the directory lists everything else
too, so a reader can find any AWS, Azure or Google Cloud service, see what it is for and
open the provider's own page for it. Each list is read from the provider's public product
list and keeps the provider's names, categories and one-line descriptions:

- AWS: the products directory behind aws.amazon.com/products (name, category, summary,
  product and pricing pages);
- Azure: the product directory of the Azure documentation hub (learn.microsoft.com/azure),
  from its public source on GitHub;
- Google Cloud: the product menu of cloud.google.com/products.

The daily Prices workflow refreshes them, and keeps the last good copy when a list comes
back much shorter than before (a page that changed shape, not services withdrawn).
"""

from __future__ import annotations

import argparse
import html as html_lib
import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import date
from functools import cache
from pathlib import Path
from typing import Any

import yaml

UA = {"User-Agent": "Mozilla/5.0 (compatible; clarchy-directory)"}
DATA = Path(__file__).resolve().parent / "data" / "directory"
PROVIDERS = ("aws", "azure", "gcp")
NAMES = {"aws": "AWS", "azure": "Azure", "gcp": "Google Cloud"}
# A refreshed list shorter than this share of the last one is not trusted.
KEEP_SHARE = 0.8

AWS_API = (
    "https://aws.amazon.com/api/dirs/items/search?item.directoryId=aws-products"
    "&sort_by=item.additionalFields.productNameLowercase&sort_order=asc&size=500"
    "&item.locale=en_US&tags.id=!aws-products%23type%23feature"
    "&tags.id=!aws-products%23type%23variant"
)
AWS_PAGE = "https://aws.amazon.com/products/"

AZURE_SOURCE = "https://raw.githubusercontent.com/MicrosoftDocs/azure-docs/main/articles/index.yml"
AZURE_PAGE = "https://learn.microsoft.com/en-us/azure/"
# The documentation hub's category ids, with the names Azure gives them.
AZURE_CATEGORIES = {
    "ai-machine-learning": "AI + machine learning",
    "analytics": "Analytics",
    "compute": "Compute",
    "containers": "Containers",
    "databases": "Databases",
    "developer-tools": "Developer tools",
    "devops": "DevOps",
    "hybrid": "Hybrid + multicloud",
    "identity": "Identity",
    "integration": "Integration",
    "iot": "Internet of Things",
    "management-and-governance": "Management and governance",
    "media": "Media",
    "migration": "Migration",
    "mixed-reality": "Mixed reality",
    "mobile": "Mobile",
    "networking": "Networking",
    "security": "Security",
    "storage": "Storage",
    "web": "Web",
    "azure-virtual-desktop": "Virtual desktop infrastructure",
}

GCP_PAGE = "https://cloud.google.com/products/"
# The product menu on Google's page lists each product under a category heading; entries
# outside a heading are solutions, industries and marketing pages, not products.
_GCP_ENTRY = re.compile(
    r'\["([^"\]]{2,80})","(https://cloud\.google\.com/[^"]+)",null,(?:"([^"]{10,400})"|null)'
)


def _get(url: str) -> str:
    request = urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(request, timeout=90).read().decode("utf-8", "replace")


def _clean_url(url: str) -> str:
    """A provider link without tracking parameters or fragments."""
    return url.split("?")[0].split("#")[0]


def _text(value: Any) -> str:
    return " ".join(html_lib.unescape(re.sub(r"<[^>]+>", " ", str(value or ""))).split())


def _sorted(services: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(services, key=lambda s: (s["category"].lower(), s["name"].lower()))


# ---------- the providers' lists ----------
def aws_services(data: dict[str, Any]) -> list[dict[str, str]]:
    """AWS's products, from its products directory."""
    found: dict[str, dict[str, str]] = {}
    for entry in data.get("items", []):
        fields = entry.get("item", {}).get("additionalFields", {})
        name, url = _text(fields.get("productName")), _clean_url(fields.get("productUrl") or "")
        if not name or not url.startswith("https://"):
            continue
        service = {
            "name": name,
            "category": _text(fields.get("productCategory")) or "Other",
            "summary": _text(fields.get("productSummary")),
            "url": url,
        }
        pricing = _clean_url(fields.get("pricingUrl") or "")
        if pricing.startswith("https://"):
            service["pricing"] = pricing
        found.setdefault(name.lower(), service)
    return _sorted(list(found.values()))


def _azure_url(url: str) -> str:
    if url.startswith("http"):
        return url
    if not url.startswith("/"):
        url = "/azure/" + url
    url = re.sub(r"(index)?\.(yml|md)$", "", url)
    return "https://learn.microsoft.com/en-us" + url


def azure_services(source: dict[str, Any]) -> list[dict[str, str]]:
    """Azure's products, from the documentation hub's product directory."""
    found: dict[str, dict[str, str]] = {}
    for item in source.get("productDirectory", {}).get("items", []):
        name = _text(item.get("title"))
        if not name or not item.get("url"):
            continue
        categories = [c for c in item.get("azureCategories", []) if c in AZURE_CATEGORIES]
        found.setdefault(
            name.lower(),
            {
                "name": name,
                "category": AZURE_CATEGORIES[categories[0]] if categories else "Other",
                "summary": _text(item.get("summary")),
                "url": _azure_url(str(item["url"])),
            },
        )
    return _sorted(list(found.values()))


def gcp_services(page: str) -> list[dict[str, str]]:
    """Google Cloud's products, by category, from its products page."""
    text = html_lib.unescape(page)
    heading: str | None = None
    found: dict[str, dict[str, str]] = {}
    for m in _GCP_ENTRY.finditer(text):
        name, url, summary = m.groups()
        if summary is None and "cloud-dropdown-menu-heading" in text[m.end() : m.end() + 250]:
            heading = name
            continue
        if not summary or heading is None or heading.startswith("See all"):
            continue
        url = _clean_url(url)
        if url.rstrip("/").endswith("/products"):
            continue
        found.setdefault(
            url, {"name": name, "category": heading, "summary": _text(summary), "url": url}
        )
    return _sorted(list(found.values()))


def build(provider: str) -> dict[str, Any]:
    if provider == "aws":
        services, source = aws_services(json.loads(_get(AWS_API))), AWS_PAGE
    elif provider == "azure":
        services, source = azure_services(yaml.safe_load(_get(AZURE_SOURCE))), AZURE_PAGE
    else:
        services, source = gcp_services(_get(GCP_PAGE)), GCP_PAGE
    return {
        "provider": provider,
        "source": source,
        "as_of": date.today().isoformat(),
        "services": services,
    }


# ---------- reading the lists ----------
@cache
def book(provider: str) -> dict[str, Any] | None:
    """A provider's list as last written, or None before the first refresh."""
    path = DATA / f"{provider}.yaml"
    if not path.exists():
        return None
    return yaml.safe_load(path.read_text("utf-8"))


_PREFIXES = re.compile(r"^(amazon|aws|azure|microsoft|google cloud|google|cloud)\s+")


def _names(name: str) -> set[str]:
    """Ways to write a service's name: "Amazon Simple Storage Service (S3)" is also
    "simple storage service" and "s3"."""
    out = set()
    whole = name.lower().replace("&", "and")
    for part in [re.sub(r"\(.*?\)", "", whole), *re.findall(r"\((.*?)\)", whole)]:
        part = " ".join(re.sub(r"[^a-z0-9.+ ]", " ", part).split())
        while part:
            out.add(part)
            shorter = _PREFIXES.sub("", part)
            if shorter == part:
                break
            part = shorter
    return {n for n in out if n}


_GENERIC = {"en-us", "products", "docs", "latest", "documentation", "overview", "index"}


def _path(provider: str, url: str) -> tuple[str, ...]:
    """Where a product lives on its provider's site, without the site's own prefixes:
    aws.amazon.com/lambda/ and docs.aws.amazon.com/lambda/ are both ("lambda",);
    learn.microsoft.com/en-us/azure/frontdoor/ is ("frontdoor",); cloud.google.com/run/docs
    is ("run",)."""
    parts = [
        re.sub(r"\.(html|md|yml)$", "", p)
        for p in urllib.parse.urlparse(url).path.lower().split("/")
    ]
    parts = [p for p in parts if p]
    while parts and (parts[0] in _GENERIC or (provider == "azure" and parts[0] == "azure")):
        parts = parts[1:]
    while parts and parts[-1] in _GENERIC:
        parts = parts[:-1]
    if parts:
        parts[0] = re.sub(r"^(amazon|aws)-?", "", parts[0])
    return tuple(p for p in parts if p)


def _site(url: str) -> str:
    """The provider site a link is on, counting its docs. subdomain as the same site."""
    return re.sub(r"^docs\.", "", urllib.parse.urlparse(url).netloc.lower())


def used_in_designs(provider: str, services: list[dict[str, str]], capabilities) -> dict:
    """For each listed service (by its link), the Clarchy capabilities drawn with it: the
    services named like the one Clarchy maps, or else the most specific product whose
    page holds that service's documentation."""
    by_name: dict[str, list[str]] = {}
    for s in services:
        for n in _names(s["name"]):
            by_name.setdefault(n, []).append(s["url"])
    paths = {s["url"]: _path(provider, s["url"]) for s in services}
    out: dict[str, list[str]] = {}
    for cap in capabilities:
        mapped = cap["services"].get(provider)
        if not mapped:
            continue
        hits: set[str] = set()
        for part in mapped["service"].split(" + "):
            for n in _names(part):
                hits.update(by_name.get(n, []))
        if not hits and _site(mapped.get("docs") or "") in {_site(u) for u in paths}:
            doc = _path(provider, mapped["docs"])
            under = {u: p for u, p in paths.items() if p and doc[: len(p)] == p}
            longest = max(map(len, under.values()), default=0)
            hits = {u for u, p in under.items() if len(p) == longest}
        for url in hits:
            out.setdefault(url, []).append(cap["title"])
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m clarchy.directory", description=__doc__)
    parser.add_argument("--provider", required=True, choices=PROVIDERS)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    new = build(args.provider)
    output = args.output or DATA / f"{args.provider}.yaml"
    if output.exists():
        old = yaml.safe_load(output.read_text("utf-8")) or {}
        before = len(old.get("services", []))
        if len(new["services"]) < KEEP_SHARE * before:
            print(
                f"{args.provider}: {len(new['services'])} services against {before} last time; "
                "keeping the last list",
                file=sys.stderr,
            )
            return 1
    output.parent.mkdir(parents=True, exist_ok=True)
    header = (
        f"# Generated by clarchy.directory from {new['source']}. Do not edit; the daily\n"
        "# Prices workflow refreshes it. Names, categories and summaries are the provider's.\n"
    )
    output.write_text(header + yaml.safe_dump(new, sort_keys=False, width=100), "utf-8")
    print(f"wrote {output} ({len(new['services'])} services)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
