"""Prints what the providers' public product lists return, to choose the directory's sources.

Run by the Price discovery workflow (it needs the open internet): AWS's products directory
API, Azure's products page and Google Cloud's products page.
"""

import json
import re
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (clarchy directory probe)"}


def get(url: str) -> bytes:
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read()


def aws() -> None:
    url = (
        "https://aws.amazon.com/api/dirs/items/search?item.directoryId=aws-products"
        "&sort_by=item.additionalFields.productNameLowercase&sort_order=asc&size=500"
        "&item.locale=en_US&tags.id=!aws-products%23type%23feature"
        "&tags.id=!aws-products%23type%23variant"
    )
    data = json.loads(get(url))
    items = data.get("items", [])
    print(f"## aws: {data.get('metadata', {})} {len(items)} items")
    for entry in items[:3]:
        print(json.dumps(entry)[:1500])
    tags = {}
    for entry in items:
        for tag in entry.get("tags", []):
            tags[tag.get("tagNamespaceId")] = tags.get(tag.get("tagNamespaceId"), 0) + 1
    print("tag namespaces:", tags)


def azure() -> None:
    html = get("https://azure.microsoft.com/en-us/products/").decode("utf-8", "replace")
    links = sorted(set(re.findall(r'href="(/en-us/products/[a-z0-9-]+/?)"', html)))
    print(f"## azure products page: {len(html)} bytes, {len(links)} product links")
    print(links[:40])
    i = html.find("Azure Kubernetes Service")
    print(re.sub(r"\s+", " ", html[max(0, i - 800) : i + 800]))
    for path in ("https://azure.microsoft.com/en-us/products/kubernetes-service/",):
        page = get(path).decode("utf-8", "replace")
        desc = re.search(r'<meta name="description" content="([^"]+)"', page)
        print("##", path, desc.group(1) if desc else None)


def gcp() -> None:
    html = get("https://cloud.google.com/products/").decode("utf-8", "replace")
    print(f"## gcp products page: {len(html)} bytes")


for probe in (aws, azure, gcp):
    try:
        probe()
    except Exception as exc:  # noqa: BLE001 - report and carry on
        print(f"## {probe.__name__} failed: {exc!r}")
