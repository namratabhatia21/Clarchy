"""Latest AWS prices for every region Clarchy offers, from the AWS Price List API.

    clarchy prices update                 # refresh the AWS price book for this machine
    python -m clarchy.aws_prices --output src/clarchy/data/prices/aws.yaml

The Price List API is AWS's official, machine-readable source for the prices on its
pricing pages; it is public and needs no credentials. This module downloads the offer
files Clarchy prices from, for each AWS region in data/regions.yaml, picks every price
below by its attributes and writes a price book with AWS's SKU for each one, so every
number can be traced back. US East (N. Virginia) is the reference region, with AWS's
description of each price; the other regions list what they offer, and an estimate falls
back to the reference price, saying so, for a service a region doesn't have.

EC2 and Compute Savings Plans are about 200 MB of CSV per region, read line by line as
they download; the other offers are small JSON files. --cache keeps downloads between
runs. A daily GitHub workflow (.github/workflows/prices.yml) runs this and commits the
book when a price has changed.

Commitment prices are effective hourly or unit rates: Compute Savings Plans (no upfront)
for Fargate, Lambda and EC2 nodes; reserved instances and nodes for RDS and ElastiCache
(1 year no upfront; 3 years no upfront where offered, otherwise partial upfront with the
upfront fee spread over the term); Redshift Serverless capacity reservations.

`lookup` searches any one service's current prices, for the MCP tool of the same name.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any

import yaml

BASE = "https://pricing.us-east-1.amazonaws.com"
BUNDLED = Path(__file__).resolve().parent / "data" / "prices" / "aws.yaml"
REFERENCE = "us-east-1"

# Every AWS region in data/regions.yaml, with the name AWS gives it and the prefix AWS puts
# on usage types there (US East has none on most). A test checks the two lists agree.
REGION_NAMES = {
    "us-east-1": "US East (N. Virginia)",
    "us-west-2": "US West (Oregon)",
    "eu-west-1": "Europe (Ireland)",
    "eu-central-1": "Europe (Frankfurt)",
    "eu-west-2": "Europe (London)",
    "ap-south-1": "Asia Pacific (Mumbai)",
    "ap-southeast-1": "Asia Pacific (Singapore)",
    "ap-southeast-2": "Asia Pacific (Sydney)",
}
USAGE_PREFIXES = {
    "us-east-1": "USE1",
    "us-west-2": "USW2",
    "eu-west-1": "EU",
    "eu-central-1": "EUC1",
    "eu-west-2": "EUW2",
    "ap-south-1": "APS3",
    "ap-southeast-1": "APS1",
    "ap-southeast-2": "APS2",
}
# CloudFront bills by the edge locations that serve visitors: those near each region.
EDGES = {
    "us-east-1": "US",
    "us-west-2": "US",
    "eu-west-1": "EU",
    "eu-central-1": "EU",
    "eu-west-2": "EU",
    "ap-south-1": "IN",
    "ap-southeast-1": "AP",
    "ap-southeast-2": "AU",
}

# key: (offer, scope, attribute filters, unit shown, multiplier to that unit). Scope is
# "region" (the design's region; usage types are given without AWS's region prefix, with
# alternatives where AWS names the same usage differently in some regions), "global" (one
# price everywhere) or "edge" (CloudFront, priced where its visitors are).
ON_DEMAND: dict[str, tuple[str, str, dict[str, Any], str, float]] = {
    "lambda.requests": ("AWSLambda", "region", {"usagetype": "Request"}, "1M requests", 1e6),
    "lambda.gb_seconds": (
        "AWSLambda",
        "region",
        {"usagetype": "Lambda-GB-Second"},
        "GB-second",
        1,
    ),
    "apigw.requests": (
        "AmazonApiGateway",
        "region",
        {"usagetype": "ApiGatewayRequest"},
        "1M requests",
        1e6,
    ),
    "cloudfront.egress_gb": (
        "AmazonCloudFront",
        "edge",
        {"usagetype": "{edge}-DataTransfer-Out-Bytes"},
        "GB",
        1,
    ),
    "cloudfront.requests": (
        "AmazonCloudFront",
        "edge",
        {"usagetype": "{edge}-Requests-Tier2-HTTPS"},
        "10K requests",
        1e4,
    ),
    "route53.zones": ("AmazonRoute53", "global", {"usagetype": "HostedZone"}, "hosted zone", 1),
    "route53.queries": (
        "AmazonRoute53",
        "global",
        {"usagetype": "DNS-Queries"},
        "1M queries",
        1e6,
    ),
    "waf.acls": ("awswaf", "global", {"usagetype": "WebACL"}, "web ACL", 1),
    "waf.rules": ("awswaf", "global", {"usagetype": "Rule"}, "rule", 1),
    "waf.requests": ("awswaf", "global", {"usagetype": "Request"}, "1M requests", 1e6),
    "alb.hours": (
        "AWSELB",
        "region",
        {"usagetype": "LoadBalancerUsage", "operation": "LoadBalancing:Application"},
        "hour",
        1,
    ),
    "alb.lcu_hours": (
        "AWSELB",
        "region",
        {"usagetype": "LCUUsage", "operation": "LoadBalancing:Application"},
        "LCU-hour",
        1,
    ),
    "fargate.vcpu_hours": (
        "AmazonECS",
        "region",
        {"usagetype": "Fargate-vCPU-Hours:perCPU"},
        "vCPU-hour",
        1,
    ),
    "fargate.gb_hours": (
        "AmazonECS",
        "region",
        {"usagetype": "Fargate-GB-Hours"},
        "GB-hour",
        1,
    ),
    "agentcore.vcpu_hours": (
        "AmazonBedrockAgentCore",
        "region",
        {"usagetype": "Runtime:Consumption-based:vCPU"},
        "vCPU-hour (active)",
        1,
    ),
    "agentcore.gb_hours": (
        "AmazonBedrockAgentCore",
        "region",
        {"usagetype": "Runtime:Consumption-based:Memory"},
        "GB-hour",
        1,
    ),
    "guardrails.content_units": (
        "AmazonBedrock",
        "region",
        {"usagetype": "Guardrail-ContentPolicyUnitsConsumed"},
        "1K text units",
        1e3,
    ),
    "guardrails.pii_units": (
        "AmazonBedrock",
        "region",
        {"usagetype": "Guardrail-SensitiveInformationPolicyPaidUnitsConsumed"},
        "1K text units",
        1e3,
    ),
    "glacier.deep_archive_gb": (
        "AmazonS3GlacierDeepArchive",
        "region",
        {"usagetype": "TimedStorage-GDA-ByteHrs"},
        "GB-month",
        1,
    ),
    "backup.rds_gb": (
        "AmazonRDS",
        "region",
        {"usagetype": "RDS:ChargedBackupUsage"},
        "GB-month (database backups)",
        1,
    ),
    "backup.s3_gb": (
        "AWSBackup",
        "region",
        {"usagetype": "WarmStorage-ByteHrs-S3"},
        "GB-month (S3 backups)",
        1,
    ),
    "kms.keys": (
        "awskms",
        "region",
        {"usagetype": "KMS-Keys"},
        "key-month",
        1,
    ),
    "kms.requests": (
        "awskms",
        "region",
        {"usagetype": "KMS-Requests"},
        "10K requests",
        1e4,
    ),
    "cloudtrail.data_events": (
        "AWSCloudTrail",
        "region",
        {"usagetype": "DataEventsRecorded"},
        "1M data events",
        1e6,
    ),
    "q.developer_seats": (
        "AmazonQ",
        "region",
        {"usagetype": "Amazon-Q-Developer-Pro-subscription-monthly"},
        "user-month (Pro)",
        1,
    ),
    "eks.cluster_hours": (
        "AmazonEKS",
        "region",
        {"usagetype": "AmazonEKS-Hours:perCluster"},
        "cluster-hour",
        1,
    ),
    "bedrock.input_tokens": (
        "AmazonBedrock",
        "region",
        {"usagetype": "NovaLite-input-tokens"},
        "1M tokens",
        1e3,
    ),
    "bedrock.output_tokens": (
        "AmazonBedrock",
        "region",
        {"usagetype": "NovaLite-output-tokens"},
        "1M tokens",
        1e3,
    ),
    "bedrock.embedding_tokens": (
        "AmazonBedrock",
        "region",
        {"usagetype": "TitanEmbeddingV2-Text-input-tokens"},
        "1M tokens",
        1e3,
    ),
    "sqs.requests": (
        "AWSQueueService",
        "region",
        {"usagetype": ("Requests-RBP", "Requests-Tier1")},
        "1M requests",
        1e6,
    ),
    "eventbridge.events": (
        "AWSEvents",
        "region",
        {"usagetype": "Event-64K-Chunks"},
        "1M events",
        1e6,
    ),
    "kinesis.shard_hours": (
        "AmazonKinesis",
        "region",
        {"usagetype": "Storage-ShardHour"},
        "shard-hour",
        1,
    ),
    "kinesis.put_units": (
        "AmazonKinesis",
        "region",
        {"usagetype": "PutRequestPayloadUnits"},
        "1M PUT units",
        1e6,
    ),
    "stepfunctions.transitions": (
        "AmazonStates",
        "region",
        {"usagetype": "StateTransition"},
        "1K transitions",
        1e3,
    ),
    "glue.dpu_hours": ("AWSGlue", "region", {"usagetype": "ETL-DPU-Hour"}, "DPU-hour", 1),
    "s3.storage_gb": (
        "AmazonS3",
        "region",
        {"usagetype": "TimedStorage-ByteHrs"},
        "GB-month",
        1,
    ),
    "s3.put_requests": (
        "AmazonS3",
        "region",
        {"usagetype": "Requests-Tier1"},
        "1K requests",
        1e3,
    ),
    "s3.get_requests": (
        "AmazonS3",
        "region",
        {"usagetype": "Requests-Tier2"},
        "1K requests",
        1e3,
    ),
    "rds.storage_gb.single": (
        "AmazonRDS",
        "region",
        {"usagetype": "RDS:GP3-Storage", "databaseEngine": "PostgreSQL"},
        "GB-month",
        1,
    ),
    "rds.storage_gb.multi": (
        "AmazonRDS",
        "region",
        {"usagetype": "RDS:Multi-AZ-GP3-Storage", "databaseEngine": "PostgreSQL"},
        "GB-month",
        1,
    ),
    "dynamodb.write_units": (
        "AmazonDynamoDB",
        "region",
        {"usagetype": "WriteRequestUnits"},
        "1M write units",
        1e6,
    ),
    "dynamodb.read_units": (
        "AmazonDynamoDB",
        "region",
        {"usagetype": "ReadRequestUnits"},
        "1M read units",
        1e6,
    ),
    "dynamodb.storage_gb": (
        "AmazonDynamoDB",
        "region",
        {"usagetype": "TimedStorage-ByteHrs"},
        "GB-month",
        1,
    ),
    "opensearch.ocu_hours": (
        "AmazonES",
        "region",
        {"usagetype": "SearchOCU"},
        "OCU-hour",
        1,
    ),
    "redshift.rpu_hours": (
        "AmazonRedshift",
        "region",
        {"usagetype": "Redshift:ServerlessUsage"},
        "RPU-hour",
        1,
    ),
    "redshift.storage_gb": (
        "AmazonRedshift",
        "region",
        {"usagetype": "RMS:Serverless"},
        "GB-month",
        1,
    ),
    "cognito.mau": (
        "AmazonCognito",
        "region",
        {"usagetype": "CognitoUserPoolsMAU"},
        "monthly active user",
        1,
    ),
    "secrets.secrets": (
        "AWSSecretsManager",
        "region",
        {"usagetype": ("AWSSecretsManager-Secrets", "AWSSecretsManager-Secret")},
        "secret",
        1,
    ),
    "secrets.api_calls": (
        "AWSSecretsManager",
        "region",
        {"usagetype": ("AWSSecretsManagerAPIRequest", "AWSSecretsManager-APIRequests")},
        "10K calls",
        1e4,
    ),
    "cloudwatch.logs_gb": (
        "AmazonCloudWatch",
        "region",
        {"usagetype": "DataProcessing-Bytes"},
        "GB ingested",
        1,
    ),
    "cloudwatch.alarms": (
        "AmazonCloudWatch",
        "region",
        {"usagetype": "CW:AlarmMonitorUsage"},
        "alarm",
        1,
    ),
    "ecr.storage_gb": (
        "AmazonECR",
        "region",
        {"usagetype": "TimedStorage-ByteHrs"},
        "GB-month",
        1,
    ),
    "codebuild.minutes": (
        "CodeBuild",
        "region",
        {"usagetype": "Build-Min:Linux:g1.small"},
        "build minute",
        1,
    ),
    "codepipeline.action_minutes": (
        "AWSCodePipeline",
        "region",
        {"usagetype": "actionExecutionMinute"},
        "action minute",
        1,
    ),
}


EC2_NODE = {
    "Instance Type": "m7g.large",
    "Operating System": "Linux",
    "Tenancy": "Shared",
    "Pre Installed S/W": "NA",
    "CapacityStatus": "Used",
}
RDS_CLASSES = {"small": "db.t4g.medium", "medium": "db.m7g.large", "large": "db.m7g.xlarge"}
CACHE_CLASSES = {"small": "cache.t4g.medium", "large": "cache.m7g.large"}
SAVINGS_PLAN_USAGE = {
    "fargate.vcpu_hours": "Fargate-vCPU-Hours:perCPU",
    "fargate.gb_hours": "Fargate-GB-Hours",
    "lambda.gb_seconds": "Lambda-GB-Second",
    "ec2.node_hours": "BoxUsage:m7g.large",
}
REDSHIFT_RESERVATION = "Redshift:ServerlessUsage-CR-1YR-NU"


def usage_names(usagetype: str, region: str) -> set[str]:
    """The ways AWS writes a usage type in `region`'s offer files: with the region's prefix
    (USW2-Fargate-GB-Hours), its code (us-west-2-KMS-Keys), or, in US East, bare."""
    names = {f"{USAGE_PREFIXES[region]}-{usagetype}", f"{region}-{usagetype}"}
    return names | {usagetype} if region == REFERENCE else names


class Offers:
    """Downloads offer files, once each; with a cache folder, keeps them between runs."""

    def __init__(self, cache: Path | None):
        self.cache = cache
        self.loaded: dict[str, Any] = {}
        self.indexes: dict[str, Any] = {}

    def _get(self, url: str, timeout: int = 120) -> Any:
        return json.load(urllib.request.urlopen(url, timeout=timeout))

    def _cached(self, name: str) -> Path | None:
        return self.cache / name if self.cache and (self.cache / name).exists() else None

    def _index(self, offer: str) -> dict[str, Any]:
        if offer not in self.indexes:
            if offer == "savingsplan":
                url = f"{BASE}/savingsPlan/v1.0/aws/AWSComputeSavingsPlan/current/region_index.json"
                regions = self._get(url)["regions"]
                self.indexes[offer] = {r["regionCode"]: r["versionUrl"] for r in regions}
            else:
                url = f"{BASE}/offers/v1.0/aws/{offer}/current/region_index.json"
                regions = self._get(url)["regions"]
                self.indexes[offer] = {k: r["currentVersionUrl"] for k, r in regions.items()}
        return self.indexes[offer]

    def offer(self, offer: str, region: str) -> Any | None:
        """One offer's JSON file for one region, or None if AWS doesn't offer it there."""
        key = f"{offer}-{region}"
        if key not in self.loaded:
            cached = self._cached(f"{key}.json")
            if cached:
                self.loaded[key] = json.loads(cached.read_bytes())
            elif region not in self._index(offer):
                self.loaded[key] = None
            else:
                url = BASE + self._index(offer)[region]
                print(f"downloading {url}")
                data = urllib.request.urlopen(url, timeout=900).read()
                if self.cache:
                    (self.cache / f"{key}.json").write_bytes(data)
                self.loaded[key] = json.loads(data)
        return self.loaded[key]

    def csv_rows(self, offer: str, region: str, needles: list[str]) -> tuple[str, list[dict]]:
        """The publication date and the rows of an offer's CSV file (AmazonEC2, or
        "savingsplan" for Compute Savings Plans) whose line contains any of `needles`,
        read as the file downloads, so the whole file is never held in memory."""
        tag = hashlib.sha1("|".join(sorted(needles)).encode()).hexdigest()[:8]
        key = f"{offer}-{region}-{tag}"
        if key not in self.loaded:
            cached = self._cached(f"{key}.rows.json")
            if cached:
                self.loaded[key] = tuple(json.loads(cached.read_bytes()))
            elif region not in self._index(offer):
                self.loaded[key] = ("", [])
            else:
                url = BASE + self._index(offer)[region].removesuffix(".json") + ".csv"
                print(f"reading {url}")
                self.loaded[key] = _filter_csv(urllib.request.urlopen(url, timeout=900), needles)
                if self.cache:
                    (self.cache / f"{key}.rows.json").write_text(json.dumps(self.loaded[key]))
        return self.loaded[key]


def _filter_csv(stream, needles: list[str]) -> tuple[str, list[dict]]:
    """AWS's offer CSVs start with five lines of metadata, then a header row."""
    lines = io.TextIOWrapper(stream, encoding="utf-8", newline="")
    meta = dict(next(csv.reader([lines.readline()])) for _ in range(5))
    header = next(csv.reader([lines.readline()]))
    rows = [
        dict(zip(header, next(csv.reader([line])), strict=False))
        for line in lines
        if any(n in line for n in needles)
    ]
    return meta.get("Publication Date", "")[:10], rows


def _match(attrs: dict, wanted: dict[str, Any], region: str, scope: str) -> bool:
    for name, value in wanted.items():
        if name == "usagetype" and scope == "region":
            options = (value,) if isinstance(value, str) else value
            if not any(attrs.get(name) in usage_names(v, region) for v in options):
                return False
        elif attrs.get(name) != value:
            return False
    return True


def on_demand(
    offers: Offers, offer: str, region: str, wanted: dict[str, Any], scope: str = "region"
) -> dict[str, Any] | None:
    """The first paid tier of the matching on-demand price, or None if there isn't one."""
    if scope == "edge":
        wanted = {k: v.format(edge=EDGES[region]) for k, v in wanted.items()}
    data = offers.offer(offer, region if scope == "region" else "aws-other")
    if data is None:
        return None
    found = []
    for sku, product in data["products"].items():
        if not _match(product.get("attributes", {}), wanted, region, scope):
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
        return None
    # The first paid tier; later volume tiers are cheaper and rarely reached.
    first = min(found, key=lambda item: item[0])[1]
    return first | {"published": data.get("publicationDate", "")[:10]}


def reserved(
    offers: Offers, offer: str, region: str, wanted: dict[str, str], years: int
) -> float | None:
    data = offers.offer(offer, region)
    if data is None:
        return None
    best = None
    for sku, product in data["products"].items():
        if not _match(product.get("attributes", {}), wanted, region, "region"):
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


def ec2_node(offers: Offers, region: str) -> dict[str, Any] | None:
    """The on-demand price of the m7g.large Linux node Kubernetes designs run on."""
    published, rows = offers.csv_rows("AmazonEC2", region, [SAVINGS_PLAN_USAGE["ec2.node_hours"]])
    names = usage_names(SAVINGS_PLAN_USAGE["ec2.node_hours"], region)
    for row in rows:
        if (
            row.get("TermType") == "OnDemand"
            and row.get("usageType") in names
            and all(row.get(k) == v for k, v in EC2_NODE.items())
            and float(row.get("PricePerUnit") or 0) > 0
        ):
            return {
                "sku": row["SKU"],
                "price": float(row["PricePerUnit"]),
                "description": row["PriceDescription"],
                "published": published,
            }
    return None


def savings_plan_rates(offers: Offers, region: str) -> dict[str, dict[int, float]]:
    """Compute Savings Plans rates (no upfront, 1 and 3 years) for the usage they cover."""
    _published, rows = offers.csv_rows("savingsplan", region, list(SAVINGS_PLAN_USAGE.values()))
    wanted = {
        name: key
        for key, usage in SAVINGS_PLAN_USAGE.items()
        for name in usage_names(usage, region)
    }
    rates: dict[str, dict[int, float]] = {}
    for row in rows:
        if row.get("Product Family") != "ComputeSavingsPlans":
            continue
        if row.get("PurchaseOption") != "No Upfront":
            continue
        key = wanted.get(row.get("DiscountedUsageType", ""))
        if key and row.get("DiscountedOperation", "") in ("", "RunInstances", "Invoke"):
            years = int(row["LeaseContractLength"])
            rates.setdefault(key, {})[years] = float(row["DiscountedRate"])
    return rates


def expected_keys() -> set[str]:
    """Every price the reference region must have."""
    sizes = {f"rds.{s}.{az}" for s in RDS_CLASSES for az in ("single", "multi")}
    return set(ON_DEMAND) | {"ec2.node_hours"} | sizes | {f"elasticache.{s}" for s in CACHE_CLASSES}


def region_prices(offers: Offers, region: str) -> tuple[dict[str, Any], set[str]]:
    """Every price Clarchy uses that AWS offers in `region`, and the offers' dates."""
    prices: dict[str, Any] = {}
    published: set[str] = set()

    def put(key: str, unit: str, multiplier: float, found: dict[str, Any] | None) -> None:
        if found is None:
            return
        published.add(found.pop("published"))
        price = round(found.pop("price") * multiplier, 8)
        prices[key] = {"price": price, "unit": unit, **found}

    for key, (offer, scope, wanted, unit, multiplier) in ON_DEMAND.items():
        put(key, unit, multiplier, on_demand(offers, offer, region, wanted, scope))
    put("ec2.node_hours", "m7g.large node-hour", 1, ec2_node(offers, region))

    for size, instance in RDS_CLASSES.items():
        for az, option in (("single", "Single-AZ"), ("multi", "Multi-AZ")):
            wanted = {
                "instanceType": instance,
                "databaseEngine": "PostgreSQL",
                "deploymentOption": option,
            }
            key = f"rds.{size}.{az}"
            unit = f"{instance} {option} hour"
            put(key, unit, 1, on_demand(offers, "AmazonRDS", region, wanted))
            for years in (1, 3):
                rate = reserved(offers, "AmazonRDS", region, wanted, years)
                if rate is not None and key in prices:
                    prices[key][f"commit_{years}yr"] = rate

    for size, node in CACHE_CLASSES.items():
        wanted = {"instanceType": node, "cacheEngine": "Valkey", "usagetype": f"NodeUsage:{node}"}
        key = f"elasticache.{size}"
        put(key, f"{node} node-hour", 1, on_demand(offers, "AmazonElastiCache", region, wanted))
        for years in (1, 3):
            rate = reserved(offers, "AmazonElastiCache", region, wanted, years)
            if rate is not None and key in prices:
                prices[key][f"commit_{years}yr"] = rate

    for key, by_years in savings_plan_rates(offers, region).items():
        multiplier = ON_DEMAND[key][4] if key in ON_DEMAND else 1
        for years, rate in by_years.items():
            if key in prices:
                prices[key][f"commit_{years}yr"] = round(rate * multiplier, 8)

    # Redshift Serverless capacity reservations (1 year, no upfront).
    reservation = on_demand(offers, "AmazonRedshift", region, {"usagetype": REDSHIFT_RESERVATION})
    if reservation and "redshift.rpu_hours" in prices:
        prices["redshift.rpu_hours"]["commit_1yr"] = reservation["price"]

    return dict(sorted(prices.items())), published


def build(offers: Offers, regions: list[str] | None = None) -> dict[str, Any]:
    regions = regions or list(REGION_NAMES)
    reference, published = region_prices(offers, REFERENCE)
    missing = expected_keys() - set(reference)
    if missing:
        raise SystemExit(f"no {REFERENCE} price for: {', '.join(sorted(missing))}")
    elsewhere: dict[str, Any] = {}
    for region in regions:
        if region == REFERENCE:
            continue
        prices, dates = region_prices(offers, region)
        published |= dates
        # The reference region keeps AWS's descriptions; the others keep what differs.
        elsewhere[region] = {
            "price_region": REGION_NAMES[region],
            "prices": {
                key: {k: v for k, v in entry.items() if k not in ("unit", "description")}
                for key, entry in prices.items()
            },
        }
    return {
        "provider": "aws",
        "currency": "USD",
        "price_region": REGION_NAMES[REFERENCE],
        "region_code": REFERENCE,
        "as_of": max(published - {""}) if published - {""} else date.today().isoformat(),
        "source": "AWS Price List API",
        "verified": True,
        "calculator": "https://calculator.aws/",
        "prices": reference,
        "regions": elsewhere,
    }


def user_price_dir() -> Path:
    """Where `clarchy prices update` keeps refreshed price books for this machine."""
    return Path.home() / ".cache" / "clarchy" / "prices"


def dump_book(book: dict[str, Any], header: str) -> str:
    """The reference prices one field per line; each other region's prices one per line."""
    top = {k: v for k, v in book.items() if k != "regions"}
    text = header + yaml.safe_dump(top, sort_keys=False, width=100)
    if book.get("regions"):
        regions = yaml.safe_dump(
            {"regions": book["regions"]}, sort_keys=False, width=200, default_flow_style=None
        )
        text += regions
    return text


def write_book(
    output: Path, cache: Path | None = None, regions: list[str] | None = None
) -> dict[str, Any]:
    book = build(Offers(cache), regions)
    header = (
        "# Generated by clarchy.aws_prices from the AWS Price List API. Do not edit; rerun\n"
        "# `clarchy prices update` to refresh. Prices are per `unit`; commit_1yr /\n"
        "# commit_3yr are effective rates with Savings Plans or reservations. `regions` has\n"
        "# the same prices in each other region Clarchy offers, where AWS sells them.\n"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dump_book(book, header), encoding="utf-8")
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
    parser.add_argument(
        "--regions",
        help=f"comma-separated region codes (default: all {len(REGION_NAMES)})",
    )
    args = parser.parse_args(argv)
    if args.cache:
        args.cache.mkdir(parents=True, exist_ok=True)
    regions = args.regions.split(",") if args.regions else None
    unknown = set(regions or ()) - set(REGION_NAMES)
    if unknown:
        parser.error(f"unknown region(s): {', '.join(sorted(unknown))}")
    output = args.output or user_price_dir() / "aws.yaml"
    book = write_book(output, args.cache, regions)
    count = len(book["prices"]) + sum(len(r["prices"]) for r in book["regions"].values())
    print(
        f"wrote {output} ({count} prices in {1 + len(book['regions'])} regions, "
        f"AWS data published {book['as_of']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
