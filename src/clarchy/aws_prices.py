"""Latest AWS prices, straight from the AWS Price List API.

    clarchy prices update                 # refresh the AWS price book for this machine
    python -m clarchy.aws_prices --output src/clarchy/data/prices/aws.yaml

The Price List API is AWS's official, machine-readable source for the prices on its
pricing pages; it is public and needs no credentials. This module downloads the
US East (N. Virginia) offer files Clarchy prices from, picks every price below by
its attributes and writes a price book with AWS's SKU and description for each one, so
every number can be traced back. The EC2 and Compute Savings Plans files are about
450 MB each; --cache keeps downloads between runs. The GitHub Pages build runs this
before every deploy (and weekly), so the public site always shows current prices.

Commitment prices are effective hourly or unit rates: Compute Savings Plans (no upfront)
for Fargate, Lambda and EC2 nodes; reserved instances and nodes for RDS and ElastiCache
(1 year no upfront; 3 years no upfront where offered, otherwise partial upfront with the
upfront fee spread over the term); Redshift Serverless capacity reservations.

`lookup` searches any one service's current prices, for the MCP tool of the same name.
"""

from __future__ import annotations

import argparse
import json
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any

import yaml

BASE = "https://pricing.us-east-1.amazonaws.com"
BUNDLED = Path(__file__).resolve().parent / "data" / "prices" / "aws.yaml"
HOURS_3YR = 3 * 8760

# key: (offer, region file, attribute filters, unit shown, multiplier to that unit)
ON_DEMAND: dict[str, tuple[str, str, dict[str, str], str, float]] = {
    "lambda.requests": ("AWSLambda", "us-east-1", {"usagetype": "Request"}, "1M requests", 1e6),
    "lambda.gb_seconds": (
        "AWSLambda",
        "us-east-1",
        {"usagetype": "Lambda-GB-Second"},
        "GB-second",
        1,
    ),
    "apigw.requests": (
        "AmazonApiGateway",
        "us-east-1",
        {"usagetype": "USE1-ApiGatewayRequest"},
        "1M requests",
        1e6,
    ),
    "cloudfront.egress_gb": (
        "AmazonCloudFront",
        "aws-other",
        {"usagetype": "US-DataTransfer-Out-Bytes"},
        "GB",
        1,
    ),
    "cloudfront.requests": (
        "AmazonCloudFront",
        "aws-other",
        {"usagetype": "US-Requests-Tier2-HTTPS"},
        "10K requests",
        1e4,
    ),
    "route53.zones": ("AmazonRoute53", "aws-other", {"usagetype": "HostedZone"}, "hosted zone", 1),
    "route53.queries": (
        "AmazonRoute53",
        "aws-other",
        {"usagetype": "DNS-Queries"},
        "1M queries",
        1e6,
    ),
    "waf.acls": ("awswaf", "aws-other", {"usagetype": "WebACL"}, "web ACL", 1),
    "waf.rules": ("awswaf", "aws-other", {"usagetype": "Rule"}, "rule", 1),
    "waf.requests": ("awswaf", "aws-other", {"usagetype": "Request"}, "1M requests", 1e6),
    "alb.hours": (
        "AWSELB",
        "us-east-1",
        {"usagetype": "LoadBalancerUsage", "operation": "LoadBalancing:Application"},
        "hour",
        1,
    ),
    "alb.lcu_hours": (
        "AWSELB",
        "us-east-1",
        {"usagetype": "LCUUsage", "operation": "LoadBalancing:Application"},
        "LCU-hour",
        1,
    ),
    "fargate.vcpu_hours": (
        "AmazonECS",
        "us-east-1",
        {"usagetype": "USE1-Fargate-vCPU-Hours:perCPU"},
        "vCPU-hour",
        1,
    ),
    "fargate.gb_hours": (
        "AmazonECS",
        "us-east-1",
        {"usagetype": "USE1-Fargate-GB-Hours"},
        "GB-hour",
        1,
    ),
    "eks.cluster_hours": (
        "AmazonEKS",
        "us-east-1",
        {"usagetype": "USE1-AmazonEKS-Hours:perCluster"},
        "cluster-hour",
        1,
    ),
    "ec2.node_hours": (
        "AmazonEC2",
        "us-east-1",
        {
            "usagetype": "BoxUsage:m7g.large",
            "operatingSystem": "Linux",
            "tenancy": "Shared",
            "preInstalledSw": "NA",
            "capacitystatus": "Used",
        },
        "m7g.large node-hour",
        1,
    ),
    "bedrock.input_tokens": (
        "AmazonBedrock",
        "us-east-1",
        {"usagetype": "USE1-NovaLite-input-tokens"},
        "1M tokens",
        1e3,
    ),
    "bedrock.output_tokens": (
        "AmazonBedrock",
        "us-east-1",
        {"usagetype": "USE1-NovaLite-output-tokens"},
        "1M tokens",
        1e3,
    ),
    "bedrock.embedding_tokens": (
        "AmazonBedrock",
        "us-east-1",
        {"usagetype": "USE1-TitanEmbeddingV2-Text-input-tokens"},
        "1M tokens",
        1e3,
    ),
    "sqs.requests": (
        "AWSQueueService",
        "us-east-1",
        {"usagetype": "Requests-RBP"},
        "1M requests",
        1e6,
    ),
    "eventbridge.events": (
        "AWSEvents",
        "us-east-1",
        {"usagetype": "USE1-Event-64K-Chunks"},
        "1M events",
        1e6,
    ),
    "kinesis.shard_hours": (
        "AmazonKinesis",
        "us-east-1",
        {"usagetype": "Storage-ShardHour"},
        "shard-hour",
        1,
    ),
    "kinesis.put_units": (
        "AmazonKinesis",
        "us-east-1",
        {"usagetype": "PutRequestPayloadUnits"},
        "1M PUT units",
        1e6,
    ),
    "stepfunctions.transitions": (
        "AmazonStates",
        "us-east-1",
        {"usagetype": "USE1-StateTransition"},
        "1K transitions",
        1e3,
    ),
    "glue.dpu_hours": ("AWSGlue", "us-east-1", {"usagetype": "USE1-ETL-DPU-Hour"}, "DPU-hour", 1),
    "s3.storage_gb": (
        "AmazonS3",
        "us-east-1",
        {"usagetype": "TimedStorage-ByteHrs"},
        "GB-month",
        1,
    ),
    "s3.put_requests": (
        "AmazonS3",
        "us-east-1",
        {"usagetype": "Requests-Tier1"},
        "1K requests",
        1e3,
    ),
    "s3.get_requests": (
        "AmazonS3",
        "us-east-1",
        {"usagetype": "Requests-Tier2"},
        "1K requests",
        1e3,
    ),
    "rds.storage_gb.single": (
        "AmazonRDS",
        "us-east-1",
        {"usagetype": "RDS:GP3-Storage", "databaseEngine": "PostgreSQL"},
        "GB-month",
        1,
    ),
    "rds.storage_gb.multi": (
        "AmazonRDS",
        "us-east-1",
        {"usagetype": "RDS:Multi-AZ-GP3-Storage", "databaseEngine": "PostgreSQL"},
        "GB-month",
        1,
    ),
    "dynamodb.write_units": (
        "AmazonDynamoDB",
        "us-east-1",
        {"usagetype": "WriteRequestUnits"},
        "1M write units",
        1e6,
    ),
    "dynamodb.read_units": (
        "AmazonDynamoDB",
        "us-east-1",
        {"usagetype": "ReadRequestUnits"},
        "1M read units",
        1e6,
    ),
    "dynamodb.storage_gb": (
        "AmazonDynamoDB",
        "us-east-1",
        {"usagetype": "TimedStorage-ByteHrs"},
        "GB-month",
        1,
    ),
    "opensearch.ocu_hours": (
        "AmazonES",
        "us-east-1",
        {"usagetype": "USE1-SearchOCU"},
        "OCU-hour",
        1,
    ),
    "redshift.rpu_hours": (
        "AmazonRedshift",
        "us-east-1",
        {"usagetype": "USE1-Redshift:ServerlessUsage"},
        "RPU-hour",
        1,
    ),
    "redshift.storage_gb": (
        "AmazonRedshift",
        "us-east-1",
        {"usagetype": "USE1-RMS:Serverless"},
        "GB-month",
        1,
    ),
    "cognito.mau": (
        "AmazonCognito",
        "us-east-1",
        {"usagetype": "USE1-CognitoUserPoolsMAU"},
        "monthly active user",
        1,
    ),
    "secrets.secrets": (
        "AWSSecretsManager",
        "us-east-1",
        {"usagetype": "USE1-AWSSecretsManager-Secrets"},
        "secret",
        1,
    ),
    "secrets.api_calls": (
        "AWSSecretsManager",
        "us-east-1",
        {"usagetype": "USE1-AWSSecretsManagerAPIRequest"},
        "10K calls",
        1e4,
    ),
    "cloudwatch.logs_gb": (
        "AmazonCloudWatch",
        "us-east-1",
        {"usagetype": "USE1-DataProcessing-Bytes"},
        "GB ingested",
        1,
    ),
    "cloudwatch.alarms": (
        "AmazonCloudWatch",
        "us-east-1",
        {"usagetype": "CW:AlarmMonitorUsage"},
        "alarm",
        1,
    ),
    "ecr.storage_gb": (
        "AmazonECR",
        "us-east-1",
        {"usagetype": "TimedStorage-ByteHrs"},
        "GB-month",
        1,
    ),
    "codebuild.minutes": (
        "CodeBuild",
        "us-east-1",
        {"usagetype": "USE1-Build-Min:Linux:g1.small"},
        "build minute",
        1,
    ),
    "codepipeline.action_minutes": (
        "AWSCodePipeline",
        "us-east-1",
        {"usagetype": "USE1-actionExecutionMinute"},
        "action minute",
        1,
    ),
}

RDS_CLASSES = {"small": "db.t4g.medium", "medium": "db.m7g.large", "large": "db.m7g.xlarge"}
CACHE_CLASSES = {"small": "cache.t4g.medium", "large": "cache.m7g.large"}
SAVINGS_PLAN_USAGE = {
    "fargate.vcpu_hours": "USE1-Fargate-vCPU-Hours:perCPU",
    "fargate.gb_hours": "USE1-Fargate-GB-Hours",
    "lambda.gb_seconds": "Lambda-GB-Second",
    "ec2.node_hours": "BoxUsage:m7g.large",
}


class Offers:
    def __init__(self, cache: Path | None):
        self.cache = cache
        self.loaded: dict[str, Any] = {}

    def _download(self, url: str, name: str) -> Any:
        path = self.cache / name if self.cache else None
        if path and path.exists():
            return json.loads(path.read_bytes())
        print(f"downloading {url}")
        data = urllib.request.urlopen(url, timeout=900).read()
        if path:
            path.write_bytes(data)
        return json.loads(data)

    def _cached(self, name: str) -> bool:
        return bool(self.cache and (self.cache / name).exists())

    def offer(self, offer: str, region: str) -> Any:
        key = f"{offer}-{region}"
        if key not in self.loaded:
            url = ""
            if not self._cached(f"{key}.json"):
                index_url = f"{BASE}/offers/v1.0/aws/{offer}/current/region_index.json"
                index = json.load(urllib.request.urlopen(index_url, timeout=120))
                url = BASE + index["regions"][region]["currentVersionUrl"]
            self.loaded[key] = self._download(url, f"{key}.json")
        return self.loaded[key]

    def savings_plans(self) -> Any:
        key = "savingsplan-AWSComputeSavingsPlan-us-east-1"
        if key not in self.loaded:
            url = ""
            if not self._cached(f"{key}.json"):
                index_url = (
                    f"{BASE}/savingsPlan/v1.0/aws/AWSComputeSavingsPlan/current/region_index.json"
                )
                index = json.load(urllib.request.urlopen(index_url, timeout=120))
                region = next(r for r in index["regions"] if r["regionCode"] == "us-east-1")
                url = BASE + region["versionUrl"]
            self.loaded[key] = self._download(url, f"{key}.json")
        return self.loaded[key]


def _match(product: dict, wanted: dict[str, str]) -> bool:
    attrs = product.get("attributes", {})
    return all(attrs.get(k) == v for k, v in wanted.items())


def on_demand(offers: Offers, offer: str, region: str, wanted: dict[str, str]) -> dict[str, Any]:
    data = offers.offer(offer, region)
    found = []
    for sku, product in data["products"].items():
        if not _match(product, wanted):
            continue
        for term in data["terms"]["OnDemand"].get(sku, {}).values():
            for dim in term["priceDimensions"].values():
                price = float(dim["pricePerUnit"]["USD"])
                if price > 0:  # free-tier rows have a price of zero
                    begin = float(dim.get("beginRange") or 0)
                    found.append(
                        (begin, {"sku": sku, "price": price, "description": dim["description"]})
                    )
    if not found:
        raise SystemExit(f"no price for {offer} {region} {wanted}")
    # The first paid tier; later volume tiers are cheaper and rarely reached.
    first = min(found, key=lambda item: item[0])[1]
    return first | {"published": data.get("publicationDate", "")[:10]}


def reserved(offers: Offers, offer: str, wanted: dict[str, str], years: int) -> float | None:
    data = offers.offer(offer, "us-east-1")
    best = None
    for sku, product in data["products"].items():
        if not _match(product, wanted):
            continue
        for term in data["terms"].get("Reserved", {}).get(sku, {}).values():
            attrs = term["termAttributes"]
            if attrs.get("LeaseContractLength") != f"{years}yr":
                continue
            hourly = upfront = 0.0
            for dim in term["priceDimensions"].values():
                if dim["unit"] == "Quantity":
                    upfront = float(dim["pricePerUnit"]["USD"])
                else:
                    hourly = float(dim["pricePerUnit"]["USD"])
            option = attrs.get("PurchaseOption")
            if option == "No Upfront":
                return round(hourly, 6)
            if option == "Partial Upfront":
                best = round(hourly + upfront / (years * 8760), 6)
    return best


def savings_plan_rates(offers: Offers) -> dict[str, dict[int, float]]:
    data = offers.savings_plans()
    plans = {p["sku"]: p for p in data["products"]}
    rates: dict[str, dict[int, float]] = {}
    wanted = {usage: key for key, usage in SAVINGS_PLAN_USAGE.items()}
    for term in data["terms"]["savingsPlan"]:
        plan = plans.get(term["sku"], {})
        if plan.get("productFamily") != "ComputeSavingsPlans":
            continue
        if plan.get("attributes", {}).get("purchaseOption") != "No Upfront":
            continue
        years = term["leaseContractLength"]["duration"]
        for rate in term["rates"]:
            key = wanted.get(rate["discountedUsageType"])
            if key and rate.get("discountedOperation", "") in ("", "RunInstances", "Invoke"):
                rates.setdefault(key, {})[years] = float(rate["discountedRate"]["price"])
    return rates


def build(offers: Offers) -> dict[str, Any]:
    prices: dict[str, Any] = {}
    published = set()

    def put(key: str, unit: str, multiplier: float, found: dict[str, Any]) -> None:
        published.add(found.pop("published"))
        price = round(found.pop("price") * multiplier, 8)
        prices[key] = {"price": price, "unit": unit, **found}

    for key, (offer, region, wanted, unit, multiplier) in ON_DEMAND.items():
        put(key, unit, multiplier, on_demand(offers, offer, region, wanted))

    for size, instance in RDS_CLASSES.items():
        for az, option in (("single", "Single-AZ"), ("multi", "Multi-AZ")):
            wanted = {
                "instanceType": instance,
                "databaseEngine": "PostgreSQL",
                "deploymentOption": option,
            }
            key = f"rds.{size}.{az}"
            put(
                key,
                f"{instance} {option} hour",
                1,
                on_demand(offers, "AmazonRDS", "us-east-1", wanted),
            )
            for years in (1, 3):
                rate = reserved(offers, "AmazonRDS", wanted, years)
                if rate is not None:
                    prices[key][f"commit_{years}yr"] = rate

    for size, node in CACHE_CLASSES.items():
        wanted = {"instanceType": node, "cacheEngine": "Valkey", "usagetype": f"NodeUsage:{node}"}
        key = f"elasticache.{size}"
        put(
            key, f"{node} node-hour", 1, on_demand(offers, "AmazonElastiCache", "us-east-1", wanted)
        )
        for years in (1, 3):
            rate = reserved(offers, "AmazonElastiCache", wanted, years)
            if rate is not None:
                prices[key][f"commit_{years}yr"] = rate

    for key, by_years in savings_plan_rates(offers).items():
        multiplier = ON_DEMAND[key][4]
        for years, rate in by_years.items():
            prices[key][f"commit_{years}yr"] = round(rate * multiplier, 8)

    # Redshift Serverless capacity reservations (1 year, no upfront).
    redshift = offers.offer("AmazonRedshift", "us-east-1")
    for sku, product in redshift["products"].items():
        if product["attributes"].get("usagetype") == "USE1-Redshift:ServerlessUsage-CR-1YR-NU":
            for term in redshift["terms"]["OnDemand"][sku].values():
                for dim in term["priceDimensions"].values():
                    prices["redshift.rpu_hours"]["commit_1yr"] = float(dim["pricePerUnit"]["USD"])

    return {
        "provider": "aws",
        "currency": "USD",
        "price_region": "US East (N. Virginia)",
        "region_code": "us-east-1",
        "as_of": max(published) if published else date.today().isoformat(),
        "source": "AWS Price List API",
        "verified": True,
        "calculator": "https://calculator.aws/",
        "prices": dict(sorted(prices.items())),
    }


def user_price_dir() -> Path:
    """Where `clarchy prices update` keeps refreshed price books for this machine."""
    return Path.home() / ".cache" / "clarchy" / "prices"


def write_book(output: Path, cache: Path | None = None) -> dict[str, Any]:
    book = build(Offers(cache))
    header = (
        "# Generated by clarchy.aws_prices from the AWS Price List API. Do not edit; rerun\n"
        "# `clarchy prices update` to refresh. Prices are per `unit`; commit_1yr /\n"
        "# commit_3yr are effective rates with Savings Plans or reservations.\n"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(header + yaml.safe_dump(book, sort_keys=False, width=100), encoding="utf-8")
    return book


# --- live lookup -----------------------------------------------------------------------

LOOKUP_LIMIT_BYTES = 60 * 1024 * 1024  # EC2 and the Savings Plans files are too big to search live


def lookup(
    service: str, search: str = "", region: str = "us-east-1", limit: int = 25
) -> list[dict[str, Any]]:
    """Current on-demand prices of one AWS service in one region whose usage type or
    description contains every word of `search`."""
    index_url = f"{BASE}/offers/v1.0/aws/{service}/current/region_index.json"
    try:
        index = json.load(urllib.request.urlopen(index_url, timeout=60))
    except Exception as exc:  # noqa: BLE001 - urllib raises many types
        raise ValueError(
            f"unknown AWS service code {service!r} or the Price List API is unreachable"
        ) from exc
    if region not in index["regions"]:
        raise ValueError(f"{service} has no prices for region {region!r}")
    url = BASE + index["regions"][region]["currentVersionUrl"]
    head = urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=60)
    if int(head.headers.get("Content-Length") or 0) > LOOKUP_LIMIT_BYTES:
        raise ValueError(
            f"{service} prices are too large to search live; use the price book instead"
        )
    data = json.load(urllib.request.urlopen(url, timeout=300))
    words = search.lower().split()
    out = []
    for sku, product in data["products"].items():
        attrs = product.get("attributes", {})
        for term in data["terms"].get("OnDemand", {}).get(sku, {}).values():
            for dim in term["priceDimensions"].values():
                text = f"{attrs.get('usagetype', '')} {dim['description']}".lower()
                if all(w in text for w in words) and float(dim["pricePerUnit"].get("USD", 0)) > 0:
                    out.append(
                        {
                            "sku": sku,
                            "usage_type": attrs.get("usagetype"),
                            "price_usd": float(dim["pricePerUnit"]["USD"]),
                            "unit": dim["unit"],
                            "description": dim["description"],
                        }
                    )
    out.sort(key=lambda r: r["description"])
    return out[:limit]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="clarchy prices update", description=__doc__.splitlines()[0]
    )
    parser.add_argument(
        "--output",
        type=Path,
        help=f"price book to write (default: {user_price_dir() / 'aws.yaml'})",
    )
    parser.add_argument("--cache", type=Path, help="folder to keep downloaded offer files")
    args = parser.parse_args(argv)
    if args.cache:
        args.cache.mkdir(parents=True, exist_ok=True)
    output = args.output or user_price_dir() / "aws.yaml"
    book = write_book(output, args.cache)
    print(f"wrote {output} ({len(book['prices'])} prices, AWS data published {book['as_of']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
