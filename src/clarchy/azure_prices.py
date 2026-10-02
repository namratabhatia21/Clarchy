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
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
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
        "service": ["Foundry Tools", "Cognitive Services", "Azure AI Content Safety"],
        "hints": ["content safety"],
    },
    "blob.archive_gb": {"service": "Storage", "hints": ["archive", "lrs", "data stored"]},
    "blob.storage_gb": {"service": "Storage", "hints": ["hot", "lrs", "data stored"]},
    "blob.writes": {"service": "Storage", "hints": ["general block blob v2", "hot lrs", "write"]},
    "blob.reads": {"service": "Storage", "hints": ["general block blob v2", "hot lrs", "read"]},
    "backup.storage_gb": {"service": "Backup", "hints": ["grs", "data stored"]},
    "backup.instances": {"service": "Backup", "hints": ["instance"]},
    "keyvault.hsm_keys": {"service": "Key Vault", "hints": ["hsm"]},
    "keyvault.operations": {"service": "Key Vault", "hints": ["operations"]},
    "entra.p2_users": {"family": "Security", "hints": ["p2"]},
    "entra.mau": {
        "service": "Azure Active Directory for External Identities",
        "hints": ["monthly active users"],
    },
    "frontdoor.base": {
        "service": "Azure Front Door Service",
        "product": "Azure Front Door",
        "zoned": True,
        "hints": ["standard", "base"],
    },
    "frontdoor.egress_gb": {
        "service": "Azure Front Door Service",
        "product": "Azure Front Door",
        "zoned": True,
        "hints": ["standard", "transfer out"],
    },
    "frontdoor.requests": {
        "service": "Azure Front Door Service",
        "product": "Azure Front Door",
        "zoned": True,
        "hints": ["standard", "request"],
    },
    "waf.policies": {
        "service": ["Azure Front Door Service", "Azure Front Door", "Web Application Firewall"],
        "zoned": True,
        "hints": ["polic"],
    },
    "waf.rules": {
        "service": "Azure Front Door Service",
        "product": "Azure Front Door Service",
        "zoned": True,
        "hints": ["custom"],
    },
    "waf.requests": {
        "service": "Azure Front Door Service",
        "product": "Azure Front Door Service",
        "zoned": True,
        "hints": ["standard", "request"],
    },
    "dns.zones": {"service": ["Azure DNS", "DNS"], "zoned": True, "hints": ["zone"]},
    "dns.queries": {"service": ["Azure DNS", "DNS"], "zoned": True, "hints": ["quer"]},
    "appgw.hours": {"service": "Application Gateway", "hints": ["standard", "fixed"]},
    "appgw.capacity_units": {
        "service": "Application Gateway",
        "hints": ["standard", "capacity unit"],
    },
    "containerapps.vcpu_hours": {"service": "Azure Container Apps", "hints": ["vcpu"]},
    "containerapps.gb_hours": {"service": "Azure Container Apps", "hints": ["memory"]},
    "aks.cluster_hours": {"service": "Azure Kubernetes Service", "hints": ["standard"]},
    "vm.node_hours": {"service": "Virtual Machines", "sku": "Standard_D2s_v5", "hints": ["d2s v5"]},
    "openai.input_tokens": {
        "service": ["Foundry Models", "Cognitive Services", "Azure OpenAI"],
        "hints": ["4o-mini"],
    },
    "openai.output_tokens": {
        "service": ["Foundry Models", "Cognitive Services", "Azure OpenAI"],
        "hints": ["4o", "mini", "out"],
    },
    "openai.embedding_tokens": {
        "service": ["Foundry Models", "Cognitive Services", "Azure OpenAI"],
        "hints": ["embedding"],
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
    "postgres.compute": {"service": "Azure Database for PostgreSQL", "hints": ["b2s"]},
    "postgres.storage": {"service": "Azure Database for PostgreSQL", "hints": ["storage"]},
    "cosmos.request_units": {"service": "Azure Cosmos DB", "hints": ["serverless"]},
    "cosmos.storage_gb": {"service": "Azure Cosmos DB", "hints": ["data stored"]},
    "redis": {"service": "Redis Cache", "hints": ["balanced"]},
    "search.unit_hours": {
        "service": ["Azure Cognitive Search", "Azure AI Search", "Search"],
        "hints": ["basic"],
    },
    "fabric.capacity_hours": {
        "service": ["Microsoft Fabric", "Fabric", "Power BI"],
        "hints": ["capacity"],
    },
    "fabric.storage_gb": {"service": "Microsoft Fabric", "hints": ["storage", "data stored"]},
    "monitor.logs_gb": {"service": "Log Analytics", "hints": ["ingestion"]},
    "monitor.alerts": {"service": "Azure Monitor", "hints": ["alert"]},
    "acr.registry": {"service": "Container Registry", "hints": ["basic"]},
    "postgres.gp": {"service": "Azure Database for PostgreSQL", "hints": ["ddsv5"]},
    "pipelines.parallel_jobs": {"family": "Developer Tools", "hints": ["parallel"]},
}


def _get(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "clarchy-prices"})
    for attempt in range(6):
        try:
            return json.load(urllib.request.urlopen(request, timeout=120))
        except urllib.error.HTTPError as exc:
            if exc.code != 429 or attempt == 5:
                raise
            time.sleep(2**attempt * 3)  # the API limits bursts of requests
    raise RuntimeError("unreachable")


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
        services = spec.get("service", [None])
        services = [services] if isinstance(services, str) else services
        items, filters = [], {}
        for service in services:  # the first name the API knows
            filters = {} if spec.get("zoned") else {"armRegionName": region}
            if service:
                filters["serviceName"] = service
            else:
                filters["serviceFamily"] = spec["family"]
            if "sku" in spec:
                filters["armSkuName"] = spec["sku"]
            ident = tuple(sorted(filters.items()))
            if ident not in cache:
                try:
                    cache[ident] = query(filters)
                except Exception as exc:  # noqa: BLE001 - report and carry on
                    print(f"## {key}: query {filters} failed: {exc}", file=out)
                    cache[ident] = []
            items = cache[ident]
            if items:
                break
        hits = [
            i
            for i in items
            if all(h in _text(i) for h in spec["hints"])
            and i.get("productName") == spec.get("product", i.get("productName"))
        ]
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
                f"{i.get('reservationTerm') or ''} {i.get('armRegionName') or '-'} | "
                f"{i.get('serviceName')} | "
                f"{i.get('productName')} | {i.get('skuName')} | {i.get('meterName')}"
                + (f" | SP {plan}" if plan else ""),
                file=out,
            )


# --- the price book ----------------------------------------------------------------------

HOURS_PER_MONTH = 730


@dataclass(frozen=True)
class Meter:
    """One price in the API, by name, and how to turn it into the book's unit: the API's
    price per its own unitOfMeasure, divided by that quantity, times `per`."""

    service: str
    product: str
    sku: str
    meter: str
    unit: str
    per: float = 1.0
    commit: str | None = None  # "savings plan" or "reservation"
    zoned: bool = False  # priced by zone (Front Door, DNS), not by region


METERS: dict[str, Meter] = {
    "functions.executions": Meter(
        "Functions", "Functions", "Standard", "Standard Total Executions", "1M executions", 1e6
    ),
    "functions.gb_seconds": Meter(
        "Functions", "Functions", "Standard", "Standard Execution Time", "GB-second"
    ),
    "apim.calls": Meter(
        "API Management", "API Management", "Consumption", "Consumption Calls", "1M calls", 1e6
    ),
    "apim.basicv2_hours": Meter(
        "API Management", "API Management", "Basic v2", "Basic v2 Unit", "Basic v2 unit-hour"
    ),
    "blob.archive_gb": Meter(
        "Storage",
        "General Block Blob v2",
        "Archive LRS",
        "Archive LRS Data Stored",
        "GB-month (Archive, LRS)",
    ),
    "blob.storage_gb": Meter(
        "Storage", "General Block Blob v2", "Hot LRS", "Hot LRS Data Stored", "GB-month (Hot, LRS)"
    ),
    "backup.storage_gb": Meter(
        "Backup", "Backup", "Standard", "Standard GRS Data Stored", "GB-month (backup storage, GRS)"
    ),
    "backup.instances": Meter(
        "Backup",
        "Backup",
        "Azure VM",
        "Azure VM Protected Instance",
        "protected instance-month (50 to 500 GB)",
    ),
    "keyvault.hsm_keys": Meter(
        "Key Vault",
        "Key Vault",
        "Premium",
        "Premium HSM-protected RSA 2048-bit key",
        "HSM-protected key-month (Premium)",
    ),
    "keyvault.operations": Meter(
        "Key Vault", "Key Vault", "Standard", "Operations", "10K operations", 1e4
    ),
    "appgw.hours": Meter(
        "Application Gateway",
        "Application Gateway Standard v2",
        "Standard",
        "Standard Fixed Cost",
        "gateway-hour",
    ),
    "appgw.capacity_units": Meter(
        "Application Gateway",
        "Application Gateway Standard v2",
        "Standard",
        "Standard Capacity Units",
        "capacity unit-hour",
    ),
    "containerapps.vcpu_hours": Meter(
        "Azure Container Apps",
        "Azure Container Apps",
        "Standard",
        "Standard vCPU Active Usage",
        "vCPU-hour",
        3600,
        "savings plan",
    ),
    "containerapps.gb_hours": Meter(
        "Azure Container Apps",
        "Azure Container Apps",
        "Standard",
        "Standard Memory Active Usage",
        "GiB-hour",
        3600,
        "savings plan",
    ),
    "aks.cluster_hours": Meter(
        "Azure Kubernetes Service",
        "Azure Kubernetes Service",
        "Standard",
        "Standard Uptime SLA",
        "cluster-hour (Standard tier)",
    ),
    "vm.node_hours": Meter(
        "Virtual Machines",
        "Virtual Machines Dsv5 Series",
        "Standard_D2s_v5",
        "D2s v5",
        "D2s v5 node-hour",
        1,
        "savings plan",
    ),
    "servicebus.base": Meter(
        "Service Bus",
        "Service Bus",
        "Standard",
        "Standard Base Unit",
        "namespace-month (Standard)",
    ),
    "servicebus.operations": Meter(
        "Service Bus",
        "Service Bus",
        "Standard",
        "Standard Messaging Operations",
        "1M operations",
        1e6,
    ),
    "eventgrid.operations": Meter(
        "Event Grid", "Event Grid", "Standard", "Standard Operations", "1M operations", 1e6
    ),
    "eventhubs.tu_hours": Meter(
        "Event Hubs",
        "Event Hubs",
        "Standard",
        "Standard Throughput Unit",
        "throughput unit-hour",
    ),
    "eventhubs.events": Meter(
        "Event Hubs", "Event Hubs", "Standard", "Standard Ingress Events", "1M events", 1e6
    ),
    "logicapps.actions": Meter(
        "Logic Apps",
        "Logic Apps",
        "Consumption",
        "Consumption Standard Connector Actions",
        "1K actions",
        1e3,
    ),
    "datafactory.vcore_hours": Meter(
        "Azure Data Factory v2",
        "Azure Data Factory v2 Data Flow - General Purpose",
        "vCore",
        "vCore",
        "vCore-hour (data flow)",
    ),
    "datafactory.runs": Meter(
        "Azure Data Factory v2",
        "Azure Data Factory v2",
        "Cloud",
        "Cloud Orchestration Activity Run",
        "1K activity runs",
        1e3,
    ),
    "cosmos.request_units": Meter(
        "Azure Cosmos DB",
        "Azure Cosmos DB serverless",
        "RUs",
        "1M RUs",
        "1M request units (serverless)",
        1e6,
    ),
    "cosmos.storage_gb": Meter(
        "Azure Cosmos DB", "Azure Cosmos DB", "RUs", "Data Stored", "GB-month"
    ),
    "monitor.logs_gb": Meter(
        "Log Analytics",
        "Log Analytics",
        "Analytics Logs",
        "Analytics Logs Data Ingestion",
        "GB ingested",
    ),
    "monitor.alerts": Meter(
        "Azure Monitor", "Azure Monitor", "Alerts", "Alerts Metric Monitored", "alert rule"
    ),
    "acr.registry": Meter(
        "Container Registry",
        "Container Registry",
        "Basic",
        "Basic Registry Unit",
        "registry-month (Basic)",
        HOURS_PER_MONTH / 24,
    ),
}
# Prices made of another: a database with a standby in another zone bills both servers.
DERIVED: dict[str, tuple[str, float, str]] = {}


def _first_paid(items: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The first paid tier; later tiers are cheaper and rarely reached."""
    paid = [i for i in items if float(i.get("retailPrice") or 0) > 0]
    return min(paid, key=lambda i: float(i.get("tierMinimumUnits") or 0)) if paid else None


def _matches(item: dict[str, Any], m: Meter) -> bool:
    return (
        item.get("productName") == m.product
        and item.get("skuName") == m.sku
        and item.get("meterName") == m.meter
    )


def price_in(items: list[dict[str, Any]], m: Meter) -> dict[str, Any] | None:
    """A book entry from the region's items for one meter, or None if it isn't sold there."""
    found = [i for i in items if _matches(i, m)]
    item = _first_paid([i for i in found if i.get("type") == "Consumption"])
    if item is None:
        return None
    per = m.per / unit_quantity(item.get("unitOfMeasure", "1"))
    entry: dict[str, Any] = {"price": round(float(item["retailPrice"]) * per, 8)}
    if m.commit == "savings plan":
        for plan in item.get("savingsPlan") or []:
            years = 1 if plan.get("term", "").startswith("1") else 3
            entry[f"commit_{years}yr"] = round(float(plan["retailPrice"]) * per, 8)
    elif m.commit == "reservation":
        for r in found:
            if r.get("type") == "Reservation" and r.get("reservationTerm"):
                years = 1 if r["reservationTerm"].startswith("1") else 3
                hourly = float(r["retailPrice"]) / (years * 8760)
                entry[f"commit_{years}yr"] = round(hourly * m.per, 8)
    entry["meter"] = f"{m.product} / {m.sku} / {m.meter}"
    return entry


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
