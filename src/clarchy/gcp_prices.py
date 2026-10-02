"""Google Cloud list prices for every region Clarchy offers, from the Cloud Billing Catalog API.

    GCP_API_KEY=... python -m clarchy.gcp_prices --discover     # list the SKUs per price

The Cloud Billing Catalog API (https://cloudbilling.googleapis.com/v1/services) is
Google's public list of every SKU and its list price. It needs an API key, which is free:
create one in a Google Cloud project with the Cloud Billing API enabled, and save it as
the repository secret GCP_API_KEY. `--discover` prints the candidate SKUs behind each price
Clarchy uses, which is how they are chosen; until then the Google Cloud book stays
hand-compiled and marked approximate.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from typing import Any

API = "https://cloudbilling.googleapis.com/v1"

# key: the service's display name in the catalog, and words its SKU description contains.
SPECS: dict[str, dict[str, Any]] = {
    "run.requests": {"service": "Cloud Run", "hints": ["request"]},
    "run.vcpu_seconds": {"service": "Cloud Run", "hints": ["cpu"]},
    "run.gib_seconds": {"service": "Cloud Run", "hints": ["memory"]},
    "apigw.calls": {"service": "API Gateway", "hints": ["call"]},
    "cdn.egress_gb": {"service": "Networking", "hints": ["cdn", "egress"]},
    "cdn.lookups": {"service": "Networking", "hints": ["cdn", "lookup"]},
    "dns.zones": {"service": "Cloud DNS", "hints": ["zone"]},
    "dns.queries": {"service": "Cloud DNS", "hints": ["queries"]},
    "armor.policies": {"service": "Networking", "hints": ["armor", "policy"]},
    "armor.rules": {"service": "Networking", "hints": ["armor", "rule"]},
    "armor.requests": {"service": "Networking", "hints": ["armor", "request"]},
    "lb.rule_hours": {"service": "Compute Engine", "hints": ["forwarding rule"]},
    "lb.data_gb": {"service": "Compute Engine", "hints": ["load balancer", "data processing"]},
    "gke.cluster_hours": {"service": "Kubernetes Engine", "hints": ["cluster management"]},
    "gce.node_hours": {"service": "Compute Engine", "hints": ["e2 instance"]},
    "vertex.input_tokens": {"service": "Vertex AI", "hints": ["flash lite", "input"]},
    "vertex.output_tokens": {"service": "Vertex AI", "hints": ["flash lite", "output"]},
    "vertex.embedding_tokens": {"service": "Vertex AI", "hints": ["embedding"]},
    "gcs.storage_gb": {"service": "Cloud Storage", "hints": ["standard storage"]},
    "gcs.archive_gb": {"service": "Cloud Storage", "hints": ["archive storage"]},
    "gcs.class_a": {"service": "Cloud Storage", "hints": ["class a"]},
    "gcs.class_b": {"service": "Cloud Storage", "hints": ["class b"]},
    "cloudsql.compute": {"service": "Cloud SQL", "hints": ["postgres", "vcpu"]},
    "cloudsql.memory": {"service": "Cloud SQL", "hints": ["postgres", "ram"]},
    "cloudsql.storage": {"service": "Cloud SQL", "hints": ["storage", "ssd"]},
    "firestore.reads": {"service": "Cloud Firestore", "hints": ["read"]},
    "firestore.writes": {"service": "Cloud Firestore", "hints": ["write"]},
    "firestore.storage_gb": {"service": "Cloud Firestore", "hints": ["storage"]},
    "memorystore.gb_hours": {"service": "Cloud Memorystore for Redis", "hints": ["standard"]},
    "bigquery.tib_scanned": {"service": "BigQuery", "hints": ["analysis"]},
    "bigquery.storage_gb": {"service": "BigQuery", "hints": ["active", "storage"]},
    "pubsub.tib": {"service": "Cloud Pub/Sub", "hints": ["message delivery"]},
    "secrets.versions": {"service": "Secret Manager", "hints": ["secret version"]},
    "secrets.access": {"service": "Secret Manager", "hints": ["access"]},
    "kms.key_versions": {"service": "Cloud Key Management Service (KMS)", "hints": ["key version"]},
    "logging.gb": {"service": "Cloud Logging", "hints": ["log", "storage"]},
    "artifacts.storage_gb": {"service": "Artifact Registry", "hints": ["storage"]},
    "build.minutes": {"service": "Cloud Build", "hints": ["build"]},
}


def _get(path: str, key: str, **params: str) -> dict[str, Any]:
    query = urllib.parse.urlencode({"key": key, **params})
    return json.load(urllib.request.urlopen(f"{API}/{path}?{query}", timeout=120))


def services(key: str) -> dict[str, str]:
    """Every service's display name and id."""
    out, token = {}, ""
    while True:
        page = _get("services", key, pageSize="5000", pageToken=token)
        out |= {s["displayName"]: s["serviceId"] for s in page.get("services", [])}
        token = page.get("nextPageToken", "")
        if not token:
            return out


def skus(key: str, service_id: str) -> list[dict[str, Any]]:
    out, token = [], ""
    while True:
        page = _get(
            f"services/{service_id}/skus", key, currencyCode="USD", pageSize="5000", pageToken=token
        )
        out += page.get("skus", [])
        token = page.get("nextPageToken", "")
        if not token:
            return out


def unit_price(sku: dict[str, Any]) -> tuple[float, str]:
    """The first paid tier's price, per the SKU's usage unit."""
    expr = sku["pricingInfo"][0]["pricingExpression"]
    rates = [r for r in expr.get("tieredRates", []) if _money(r["unitPrice"]) > 0]
    price = _money(rates[0]["unitPrice"]) if rates else 0.0
    return price, expr.get("usageUnitDescription") or expr.get("usageUnit", "")


def _money(m: dict[str, Any]) -> float:
    return int(m.get("units") or 0) + m.get("nanos", 0) / 1e9


def discover(key: str, region: str = "us-east4", keys: list[str] | None = None, out=sys.stdout):
    names = services(key)
    cache: dict[str, list[dict[str, Any]]] = {}
    for price, spec in SPECS.items():
        if keys and price not in keys:
            continue
        service_id = names.get(spec["service"])
        if not service_id:
            close = [n for n in names if spec["service"].split()[0].lower() in n.lower()][:8]
            print(f"## {price}: no service {spec['service']!r}; similar: {close}", file=out)
            continue
        if service_id not in cache:
            cache[service_id] = skus(key, service_id)
        found = [
            s
            for s in cache[service_id]
            if all(h in s["description"].lower() for h in spec["hints"])
            and (region in s.get("serviceRegions", []) or "global" in s.get("serviceRegions", []))
        ]
        print(f"## {price} ({spec['service']}, {len(found)} match in {region})", file=out)
        for s in found[:14]:
            amount, unit = unit_price(s)
            usage = s["category"].get("usageType")
            print(
                f"   {amount:>12.8f} /{unit:<22} {usage:<10} {s['skuId']} | {s['description']}",
                file=out,
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m clarchy.gcp_prices", description=__doc__)
    parser.add_argument("--discover", action="store_true", help="list candidate SKUs")
    parser.add_argument("--region", default="us-east4")
    parser.add_argument("--keys", help="comma-separated price keys (default: all)")
    args = parser.parse_args(argv)
    key = os.environ.get("GCP_API_KEY")
    if not key:
        parser.error("set GCP_API_KEY to a Google Cloud API key with the Cloud Billing API")
    if args.discover:
        discover(key, args.region, args.keys.split(",") if args.keys else None)
        return 0
    parser.error("only --discover is available until the SKUs are chosen")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
