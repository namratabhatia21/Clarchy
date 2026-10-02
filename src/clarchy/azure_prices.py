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
from datetime import date
from pathlib import Path
from typing import Any

import yaml

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
BUNDLED = Path(__file__).resolve().parent / "data" / "prices" / "azure.yaml"
REFERENCE = "eastus"
# Every Azure region in data/regions.yaml, with Azure's name for it. Front Door bills by
# the zone its visitors are in; Azure DNS is global and priced the same in every zone.
REGION_NAMES = {
    "eastus": "East US",
    "westus2": "West US 2",
    "northeurope": "North Europe",
    "germanywestcentral": "Germany West Central",
    "uksouth": "UK South",
    "centralindia": "Central India",
    "southeastasia": "Southeast Asia",
    "australiaeast": "Australia East",
}
FRONT_DOOR_ZONES = {
    "eastus": "Zone 1",
    "westus2": "Zone 1",
    "northeurope": "Zone 1",
    "germanywestcentral": "Zone 1",
    "uksouth": "Zone 1",
    "centralindia": "Zone 5",
    "southeastasia": "Zone 2",
    "australiaeast": "Zone 4",
}


@dataclass(frozen=True)
class Meter:
    """One price in the API, by name, and how to turn it into the book's unit: the API's
    price per its own unitOfMeasure, divided by that quantity, times `per` (to the book's
    unit) and `times` (how many are billed: a standby server, two cache nodes, 2 CU)."""

    service: str
    product: str
    sku: str
    meter: str
    unit: str
    per: float = 1.0
    times: float = 1.0
    commit: str | None = None  # "savings plan" or "reservation"
    zones: dict[str, str] | None = None  # priced by zone, not by region
    reserve: tuple[str, str, float] | None = None  # (sku, meter, units) of a per-unit reservation


DNS_ZONES = dict.fromkeys(REGION_NAMES, "Zone 1")
FD = "Azure Front Door Service"
PG = "Azure Database for PostgreSQL"
PG_BURST = "Azure Database for PostgreSQL Flexible Server Burstable BS Series Compute"
PG_GP = "Azure Database for PostgreSQL Flexible Server General Purpose Ddsv5 Series Compute"
PG_STORE = "Azure Database for PostgreSQL Flex Server Storage"
AMR = "Azure Managed Redis - Balanced"
GPT = "gpt-4o-mini-0718-{}-glbl"


def _pg(size: str, sku: str, product: str, vcores: float | None, standby: bool) -> Meter:
    name = {"small": "B2s", "medium": "D2ds v5", "large": "D4ds v5"}[size]
    unit = f"{name} server-hour" + (" with standby" if standby else "")
    return Meter(
        PG,
        product,
        sku,
        sku if product == PG_BURST else "vCore",
        unit,
        times=2 if standby else 1,
        commit="reservation" if vcores else "savings plan",
        reserve=("vCore", "vCore", vcores) if vcores else None,
    )


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
    "contentsafety.text_records": Meter(
        "Foundry Tools",
        "Content Safety",
        "Standard",
        "Standard Text Records",
        "1K text records",
        1e3,
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
    "blob.writes": Meter(
        "Storage", "General Block Blob v2", "Hot LRS", "Hot LRS Write Operations", "1K writes", 1e3
    ),
    "blob.reads": Meter(
        "Storage", "General Block Blob v2", "Hot LRS", "Hot Read Operations", "1K reads", 1e3
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
    "entra.mau": Meter(
        "Azure Active Directory for External Identities",
        "Azure Active Directory B2X",
        "P1",
        "P1 Monthly Active Users",
        "monthly active user",
    ),
    "frontdoor.base": Meter(
        FD,
        "Azure Front Door",
        "Standard",
        "Standard Base Fees",
        "profile-month",
        zones=FRONT_DOOR_ZONES,
    ),
    "frontdoor.egress_gb": Meter(
        FD,
        "Azure Front Door",
        "Standard",
        "Standard Data Transfer Out",
        "GB",
        zones=FRONT_DOOR_ZONES,
    ),
    "frontdoor.requests": Meter(
        FD,
        "Azure Front Door",
        "Standard",
        "Standard Requests",
        "10K requests",
        1e4,
        zones=FRONT_DOOR_ZONES,
    ),
    "waf.policies": Meter(FD, FD, "Standard", "Standard Policy", "policy", zones=FRONT_DOOR_ZONES),
    "dns.zones": Meter("Azure DNS", "Azure DNS", "Public", "Public Zone", "zone", zones=DNS_ZONES),
    "dns.queries": Meter(
        "Azure DNS", "Azure DNS", "Public", "Public Queries", "1M queries", 1e6, zones=DNS_ZONES
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
        commit="savings plan",
    ),
    "containerapps.gb_hours": Meter(
        "Azure Container Apps",
        "Azure Container Apps",
        "Standard",
        "Standard Memory Active Usage",
        "GiB-hour",
        3600,
        commit="savings plan",
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
        commit="savings plan",
    ),
    "openai.input_tokens": Meter(
        "Foundry Models",
        "Azure OpenAI",
        GPT.format("Inp"),
        GPT.format("Inp") + " Tokens",
        "1M tokens (gpt-4o-mini)",
        1e6,
    ),
    "openai.output_tokens": Meter(
        "Foundry Models",
        "Azure OpenAI",
        GPT.format("Outp"),
        GPT.format("Outp") + " Tokens",
        "1M tokens (gpt-4o-mini)",
        1e6,
    ),
    "openai.embedding_tokens": Meter(
        "Foundry Models",
        "Azure OpenAI",
        "text-embedding-3-small-glbl",
        "text-embedding-3-small-glbl Tokens",
        "1M tokens",
        1e6,
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
    "postgres.small.single": _pg("small", "B2S", PG_BURST, None, False),
    "postgres.small.multi": _pg("small", "B2S", PG_BURST, None, True),
    "postgres.medium.single": _pg("medium", "2 vCore", PG_GP, 2, False),
    "postgres.medium.multi": _pg("medium", "2 vCore", PG_GP, 2, True),
    "postgres.large.single": _pg("large", "4 vCore", PG_GP, 4, False),
    "postgres.large.multi": _pg("large", "4 vCore", PG_GP, 4, True),
    "postgres.storage_gb.single": Meter(PG, PG_STORE, "Storage", "Storage Data Stored", "GB-month"),
    "postgres.storage_gb.multi": Meter(
        PG, PG_STORE, "Storage", "Storage Data Stored", "GB-month (with standby)", times=2
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
    "redis.small": Meter(
        "Redis Cache",
        AMR,
        "B1",
        "B1 Cache Instance",
        "cache-hour (B1, 1 GB, high availability)",
        times=2,
    ),
    "redis.large": Meter(
        "Redis Cache",
        AMR,
        "B5",
        "B5 Cache Instance",
        "cache-hour (B5, 6 GB, high availability)",
        times=2,
    ),
    "search.unit_hours": Meter(
        "Azure Cognitive Search",
        "Azure AI Search",
        "Basic",
        "Basic Unit",
        "search unit-hour (Basic)",
    ),
    "fabric.capacity_hours": Meter(
        "Microsoft Fabric",
        "Fabric Capacity",
        "Compute Pool Capacity Usage",
        "Compute Pool Capacity Usage CU",
        "F2 capacity-hour (2 CU)",
        times=2,
    ),
    "fabric.storage_gb": Meter(
        "Microsoft Fabric",
        "OneLake",
        "OneLake Storage Hot",
        "OneLake Storage Hot Data Stored",
        "GB-month (OneLake)",
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


def _first_paid(items: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The first paid tier; later tiers are cheaper and rarely reached."""
    paid = [i for i in items if float(i.get("retailPrice") or 0) > 0]
    return min(paid, key=lambda i: float(i.get("tierMinimumUnits") or 0)) if paid else None


def price_in(items: list[dict[str, Any]], m: Meter, zone: str | None = None) -> dict | None:
    """A book entry for one meter from a region's (or a zone's) items, or None if it isn't
    sold there."""

    def named(i: dict[str, Any], sku: str, meter: str) -> bool:
        return (
            i.get("productName") == m.product
            and i.get("skuName") == sku
            and i.get("meterName") == meter
            and (zone is None or i.get("armRegionName") == zone)
        )

    found = [i for i in items if named(i, m.sku, m.meter)]
    item = _first_paid([i for i in found if i.get("type") == "Consumption"])
    if item is None:
        return None
    scale = m.per * m.times / unit_quantity(item.get("unitOfMeasure", "1"))
    entry: dict[str, Any] = {"price": round(float(item["retailPrice"]) * scale, 8)}
    if m.commit == "savings plan":
        for plan in item.get("savingsPlan") or []:
            years = 1 if str(plan.get("term", "")).startswith("1") else 3
            entry[f"commit_{years}yr"] = round(float(plan["retailPrice"]) * scale, 8)
    elif m.commit == "reservation":
        sku, meter, units = m.reserve or (m.sku, m.meter, 1.0)
        for r in items:
            if named(r, sku, meter) and r.get("type") == "Reservation" and r.get("reservationTerm"):
                years = 1 if r["reservationTerm"].startswith("1") else 3
                hourly = float(r["retailPrice"]) / (years * 8760)
                entry[f"commit_{years}yr"] = round(hourly * units * m.times, 8)
        if "commit_1yr" not in entry:  # no reservation: the savings plan, where there is one
            for plan in item.get("savingsPlan") or []:
                years = 1 if str(plan.get("term", "")).startswith("1") else 3
                entry[f"commit_{years}yr"] = round(float(plan["retailPrice"]) * scale, 8)
    entry["meter"] = f"{m.product} / {m.sku} / {m.meter}"
    return entry


class Catalog:
    """Downloads each (service, product) once per region, or once for zone-priced ones."""

    def __init__(self) -> None:
        self.cache: dict[tuple, list[dict[str, Any]]] = {}

    def items(self, m: Meter, region: str) -> list[dict[str, Any]]:
        filters = {"serviceName": m.service, "productName": m.product}
        if m.zones is None:
            filters["armRegionName"] = region
        key = tuple(sorted(filters.items()))
        if key not in self.cache:
            self.cache[key] = query(filters)
        return self.cache[key]


def build(catalog: Catalog, manual: dict[str, Any], regions: list[str] | None = None) -> dict:
    """The Azure price book: every meter in every region, and the hand-compiled prices the
    API doesn't carry (kept as they are, marked manual)."""
    regions = regions or list(REGION_NAMES)
    per_region: dict[str, dict[str, Any]] = {}
    for region in regions:
        prices = {}
        for key, m in METERS.items():
            zone = m.zones[region] if m.zones else None
            entry = price_in(catalog.items(m, region), m, zone)
            if entry is not None:
                prices[key] = {"price": entry.pop("price"), "unit": m.unit, **entry}
        per_region[region] = prices
    reference = per_region[REFERENCE]
    kept = {
        key: {**entry, "manual": True}
        for key, entry in manual.items()
        if key not in reference and (key not in METERS or entry.get("manual"))
    }
    missing = sorted(k for k in METERS if k not in reference)
    for key in missing:  # a meter that has gone: keep the last known price, flagged
        if key in manual:
            kept[key] = {**manual[key], "manual": True}
    book = {
        "provider": "azure",
        "currency": "USD",
        "price_region": REGION_NAMES[REFERENCE],
        "region_code": REFERENCE,
        "as_of": date.today().isoformat(),
        "source": "Azure Retail Prices API",
        "verified": True,
        "calculator": "https://azure.microsoft.com/pricing/calculator/",
        "prices": dict(sorted({**reference, **kept}.items())),
        "regions": {
            region: {
                "price_region": REGION_NAMES[region],
                "prices": {
                    key: {k: v for k, v in entry.items() if k not in ("unit", "meter")}
                    for key, entry in sorted({**per_region[region], **kept}.items())
                },
            }
            for region in regions
            if region != REFERENCE
        },
    }
    return {"book": book, "missing": missing}


def write_book(output: Path, regions: list[str] | None = None) -> dict[str, Any]:
    from clarchy.aws_prices import dump_book

    current = yaml.safe_load(BUNDLED.read_text(encoding="utf-8")) if BUNDLED.exists() else {}
    result = build(Catalog(), (current or {}).get("prices", {}), regions)
    header = (
        "# Generated by clarchy.azure_prices from the Azure Retail Prices API. Do not edit;\n"
        "# rerun to refresh. Prices are per `unit`, and `meter` names the API's product, SKU\n"
        "# and meter. Entries marked `manual` are not in the API (licences, Azure DevOps)\n"
        "# and keep their hand-compiled price and source.\n"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dump_book(result["book"], header), encoding="utf-8")
    return result


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
    output = args.output or BUNDLED
    result = write_book(output)
    book = result["book"]
    count = len(book["prices"]) + sum(len(r["prices"]) for r in book["regions"].values())
    manual = sum(1 for e in book["prices"].values() if e.get("manual"))
    print(f"wrote {output} ({count} prices in {1 + len(book['regions'])} regions; {manual} manual)")
    if result["missing"]:
        print(f"warning: not in the API today: {', '.join(result['missing'])}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
