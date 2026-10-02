"""Azure list prices for every region Clarchy offers, from the Azure Retail Prices API.

    python -m clarchy.azure_prices --output src/clarchy/data/prices/azure.yaml
    python -m clarchy.azure_prices --discover     # list the meters behind each price

The Retail Prices API (https://prices.azure.com/api/retail/prices) is Microsoft's public,
unauthenticated list of pay-as-you-go, reservation and savings plan prices, the same
prices as the pricing pages. Each price below names the meter it comes from (service,
product, SKU and meter name); `--discover` prints the candidate meters for each one, which
is how the names were chosen. Prices the API doesn't carry (Entra ID licences, Azure
DevOps parallel jobs) keep their hand-compiled value and are marked `manual`.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

API = "https://prices.azure.com/api/retail/prices"
VERSION = "2023-01-01-preview"  # the version that includes savings plan prices

# key: where the price is in the API. `service` is the API's serviceName (or `family`, its
# serviceFamily, when the service name is uncertain); `hints` are words that the meter's
# product, SKU and meter names contain, used by --discover; `sku` narrows the query to an
# armSkuName (for virtual machines, which have thousands of meters per region).
SPECS: dict[str, dict[str, Any]] = {
    "functions.executions": {"service": "Functions", "hints": ["execution"]},
    "functions.gb_seconds": {"service": "Functions", "hints": ["execution time"]},
    "apim.calls": {"service": "API Management", "hints": ["consumption"]},
    "apim.basicv2_hours": {"service": "API Management", "hints": ["basic v2"]},
    "contentsafety.text_records": {
        "family": "AI + Machine Learning",
        "hints": ["content safety", "text"],
    },
    "blob.archive_gb": {"service": "Storage", "hints": ["archive", "lrs", "data stored"]},
    "blob.storage_gb": {"service": "Storage", "hints": ["hot", "lrs", "data stored"]},
    "blob.writes": {"service": "Storage", "hints": ["hot", "write operations"]},
    "blob.reads": {"service": "Storage", "hints": ["hot", "read operations"]},
    "backup.storage_gb": {"service": "Backup", "hints": ["grs", "data stored"]},
    "backup.instances": {"service": "Backup", "hints": ["instance"]},
    "keyvault.hsm_keys": {"service": "Key Vault", "hints": ["hsm"]},
    "keyvault.operations": {"service": "Key Vault", "hints": ["operations"]},
    "entra.p2_users": {"family": "Security", "hints": ["p2"]},
    "entra.mau": {"family": "Security", "hints": ["active user"]},
    "frontdoor.base": {"service": "Azure Front Door Service", "hints": ["standard", "base"]},
    "frontdoor.egress_gb": {
        "service": "Azure Front Door Service",
        "hints": ["standard", "data transfer"],
    },
    "frontdoor.requests": {"service": "Azure Front Door Service", "hints": ["standard", "request"]},
    "waf.policies": {"service": "Azure Front Door Service", "hints": ["policy"]},
    "waf.rules": {"service": "Azure Front Door Service", "hints": ["rule"]},
    "waf.requests": {"service": "Azure Front Door Service", "hints": ["waf", "request"]},
    "dns.zones": {"service": "Azure DNS", "hints": ["zone"]},
    "dns.queries": {"service": "Azure DNS", "hints": ["queries"]},
    "appgw.hours": {"service": "Application Gateway", "hints": ["standard", "fixed"]},
    "appgw.capacity_units": {
        "service": "Application Gateway",
        "hints": ["standard", "capacity unit"],
    },
    "containerapps.vcpu_hours": {"service": "Azure Container Apps", "hints": ["vcpu"]},
    "containerapps.gb_hours": {"service": "Azure Container Apps", "hints": ["memory"]},
    "aks.cluster_hours": {"service": "Azure Kubernetes Service", "hints": ["standard"]},
    "vm.node_hours": {"service": "Virtual Machines", "sku": "Standard_D2s_v5", "hints": ["d2s v5"]},
    "openai.input_tokens": {"family": "AI + Machine Learning", "hints": ["4o-mini", "inp"]},
    "openai.output_tokens": {"family": "AI + Machine Learning", "hints": ["4o-mini", "outp"]},
    "openai.embedding_tokens": {
        "family": "AI + Machine Learning",
        "hints": ["embedding", "3-small"],
    },
    "servicebus.base": {"service": "Service Bus", "hints": ["standard", "base"]},
    "servicebus.operations": {"service": "Service Bus", "hints": ["standard", "operations"]},
    "eventgrid.operations": {"service": "Event Grid", "hints": ["operations"]},
    "eventhubs.tu_hours": {"service": "Event Hubs", "hints": ["standard", "throughput"]},
    "eventhubs.events": {"service": "Event Hubs", "hints": ["standard", "ingress"]},
    "logicapps.actions": {"service": "Logic Apps", "hints": ["action"]},
    "datafactory.vcore_hours": {
        "service": "Azure Data Factory v2",
        "hints": ["data flow", "general purpose"],
    },
    "datafactory.runs": {
        "service": "Azure Data Factory v2",
        "hints": ["orchestration", "activity"],
    },
    "postgres.compute": {
        "service": "Azure Database for PostgreSQL",
        "hints": ["flexible", "vcore"],
    },
    "postgres.storage": {
        "service": "Azure Database for PostgreSQL",
        "hints": ["flexible", "storage"],
    },
    "cosmos.request_units": {"service": "Azure Cosmos DB", "hints": ["serverless"]},
    "cosmos.storage_gb": {"service": "Azure Cosmos DB", "hints": ["data stored"]},
    "redis": {"service": "Redis Cache", "hints": ["balanced"]},
    "search.unit_hours": {"family": "AI + Machine Learning", "hints": ["search", "basic"]},
    "fabric.capacity_hours": {"family": "Analytics", "hints": ["fabric", "capacity"]},
    "fabric.storage_gb": {"family": "Analytics", "hints": ["onelake"]},
    "monitor.logs_gb": {"service": "Log Analytics", "hints": ["ingestion"]},
    "monitor.alerts": {"service": "Azure Monitor", "hints": ["alert"]},
    "acr.registry": {"service": "Container Registry", "hints": ["basic"]},
    "pipelines.parallel_jobs": {"family": "Developer Tools", "hints": ["parallel"]},
}


def _get(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "clarchy-prices"})
    return json.load(urllib.request.urlopen(request, timeout=120))


def query(filters: dict[str, str], limit_pages: int = 400) -> list[dict[str, Any]]:
    """Every item matching `filters` (field eq value, joined with and), across pages."""
    expr = " and ".join(f"{k} eq '{v}'" for k, v in filters.items())
    url = f"{API}?api-version={VERSION}&$filter={urllib.parse.quote(expr)}"
    items: list[dict[str, Any]] = []
    for _ in range(limit_pages):
        page = _get(url)
        items += page.get("Items", [])
        url = page.get("NextPageLink")
        if not url:
            break
    return items


def unit_quantity(unit: str) -> float:
    """How many base units a unitOfMeasure covers: "1 Hour" 1, "10K" 10,000, "1M" 1e6."""
    m = re.match(r"\s*(\d+(?:\.\d+)?)\s*([KM])?", unit or "")
    if not m:
        return 1.0
    return float(m.group(1)) * {"K": 1e3, "M": 1e6}.get(m.group(2) or "", 1.0)


def _text(item: dict[str, Any]) -> str:
    return " ".join(
        str(item.get(k, "")) for k in ("productName", "skuName", "meterName", "armSkuName")
    ).lower()


def discover(region: str = "eastus", keys: list[str] | None = None, out=sys.stdout) -> None:
    """Print the meters that could stand behind each price, to choose them by name."""
    cache: dict[tuple, list[dict[str, Any]]] = {}
    for key, spec in SPECS.items():
        if keys and key not in keys:
            continue
        filters = {"armRegionName": region}
        if "service" in spec:
            filters["serviceName"] = spec["service"]
        else:
            filters["serviceFamily"] = spec["family"]
        if "sku" in spec:
            filters["armSkuName"] = spec["sku"]
        ident = tuple(sorted(filters.items()))
        if ident not in cache:
            try:
                cache[ident] = query(filters)
            except Exception as exc:  # noqa: BLE001 - report and carry on
                print(f"## {key}: query failed: {exc}", file=out)
                cache[ident] = []
        items = cache[ident]
        hits = [i for i in items if all(h in _text(i) for h in spec["hints"])]
        names = sorted({i.get("serviceName", "") for i in items})
        print(f"## {key} ({len(items)} items in {dict(filters)}, {len(hits)} match)", file=out)
        if not items:
            continue
        if not hits:
            print(f"   services seen: {', '.join(names)[:300]}", file=out)
        for i in sorted(hits, key=lambda i: (i.get("type", ""), _text(i)))[:14]:
            plan = ";".join(f"{p['term']}={p['retailPrice']}" for p in i.get("savingsPlan") or [])
            print(
                f"   {i.get('retailPrice')!s:>10} /{i.get('unitOfMeasure')!s:<12} "
                f"{i.get('type')!s:<11} tier={i.get('tierMinimumUnits')} "
                f"{i.get('reservationTerm') or ''} | {i.get('serviceName')} | "
                f"{i.get('productName')} | {i.get('skuName')} | {i.get('meterName')}"
                + (f" | SP {plan}" if plan else ""),
                file=out,
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m clarchy.azure_prices", description=__doc__)
    parser.add_argument("--discover", action="store_true", help="list candidate meters")
    parser.add_argument("--region", default="eastus")
    parser.add_argument("--keys", help="comma-separated price keys (default: all)")
    parser.add_argument("--output", type=Path, help="price book to write")
    args = parser.parse_args(argv)
    keys = args.keys.split(",") if args.keys else None
    if args.discover:
        discover(args.region, keys)
        return 0
    parser.error("only --discover is available until the meters are chosen")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
