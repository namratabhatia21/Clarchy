import io
import json

import pytest

from clarchy import aws_prices, catalog, pricing
from clarchy.mapping import map_to_provider
from clarchy.spec import load_pattern, load_spec

CLOUDS = ("aws", "azure", "gcp")


def estimate(name, provider="aws"):
    return pricing.estimate(map_to_provider(load_pattern(name), provider))


@pytest.mark.parametrize("provider", CLOUDS)
@pytest.mark.parametrize("name", catalog.pattern_names())
def test_every_pattern_is_priced_on_every_cloud(name, provider):
    cost = estimate(name, provider)
    assert cost["available"]
    assert not cost["not_priced"], "every capability has a billing model or a reason it is free"
    assert cost["monthly"] > 0
    assert sum(line["monthly"] for line in cost["lines"]) == pytest.approx(
        cost["monthly"], abs=0.05
    )
    assert [t["months"] for t in cost["terms"]] == [1, 6, 12, 36]
    for line in cost["lines"]:
        for item in line["items"]:
            assert item["monthly"] == pytest.approx(
                item["quantity"] * item["unit_price"], rel=1e-3, abs=0.01
            )
            assert item["basis"]


def test_terms_grow_with_data_and_commitments_save():
    cost = estimate("data-pipeline")
    one, six, year, three = cost["terms"]
    assert one["on_demand"] == cost["monthly"]
    assert six["on_demand"] > 6 * one["on_demand"], "the data lake grows every month"
    assert year["committed"] < year["on_demand"] and three["committed"] < three["on_demand"]
    assert one["committed"] is None and six["committed"] is None


def test_aws_prices_come_from_the_price_list_with_skus():
    book = pricing.price_book("aws")
    assert book["verified"] is True and book["source"] == "AWS Price List API"
    for key, entry in book["prices"].items():
        assert entry["sku"] and entry["description"], key
    assert book["prices"]["lambda.requests"]["price"] == pytest.approx(0.20)
    fargate = book["prices"]["fargate.vcpu_hours"]
    assert fargate["commit_3yr"] < fargate["commit_1yr"] < fargate["price"]


def test_hand_compiled_books_say_so():
    for provider in ("azure", "gcp"):
        book = pricing.price_book(provider)
        assert book["verified"] is False
        assert all(entry["source"].startswith("https://") for entry in book["prices"].values())


def test_open_source_is_not_priced():
    cost = estimate("container-api", "oss")
    assert cost["available"] is False and "licence fee" in cost["message"]


def test_kubernetes_pays_for_one_control_plane():
    spec = load_spec(
        {
            "name": "K",
            "components": [
                {"id": "api", "capability": "kubernetes", "sizing": {"tasks": 4}},
                {"id": "workers", "capability": "kubernetes"},
            ],
        }
    )
    lines = {
        line["component"]: line for line in pricing.estimate(map_to_provider(spec, "aws"))["lines"]
    }
    names = lambda c: [i["name"] for i in lines[c]["items"]]  # noqa: E731
    assert "EKS cluster" in names("api") and "EKS cluster" not in names("workers")


def test_free_allowances_and_size_classes():
    spec = load_spec(
        {
            "name": "Small",
            "requirements": {"users": 1000, "availability_target": "99.5"},
            "components": [
                {"id": "fn", "capability": "serverless-function"},
                {"id": "db", "capability": "relational-db"},
            ],
        }
    )
    lines = {
        line["component"]: line for line in pricing.estimate(map_to_provider(spec, "aws"))["lines"]
    }
    assert lines["fn"]["monthly"] == 0, "600,000 calls fit in Lambda's free requests and compute"
    db_items = {i["name"]: i for i in lines["db"]["items"]}
    assert db_items["Database instance"]["unit"].startswith("db.t4g.medium Single-AZ")


def test_refreshed_price_books_win(tmp_path, monkeypatch):
    book = dict(pricing.price_book("aws"))
    book["prices"] = {
        **book["prices"],
        "lambda.requests": {**book["prices"]["lambda.requests"], "price": 9.0},
    }
    (tmp_path / "aws.yaml").write_text(json.dumps(book))  # JSON is valid YAML
    monkeypatch.setenv("CLARCHY_PRICES_DIR", str(tmp_path))
    assert pricing.price_book("aws")["prices"]["lambda.requests"]["price"] == 9.0


def test_explanations_include_the_cost():
    from clarchy.explain import explain_markdown

    text = explain_markdown(map_to_provider(load_pattern("serverless-web-app"), "aws"))
    assert "## Estimated cost" in text and "| 3 years |" in text


# --- the AWS Price List extraction -------------------------------------------------------


class FakeOffers(aws_prices.Offers):
    def __init__(self, offers, rows=None):
        super().__init__(None)
        self.offers = dict(offers)
        self.rows = rows or {}

    def offer(self, offer, region):
        return self.offers.get(f"{offer}-{region}")

    def csv_rows(self, offer, region, needles):
        return "2026-09-02", self.rows.get(f"{offer}-{region}", [])


def offer(sku, attributes, tiers, reserved=None, published="2026-09-01T00:00:00Z"):
    dims = {
        f"{sku}.{i}": {
            "unit": "Hrs",
            "pricePerUnit": {"USD": str(price)},
            "beginRange": str(begin),
            "description": f"${price} tier {i}",
        }
        for i, (begin, price) in enumerate(tiers)
    }
    terms = {"OnDemand": {sku: {"t": {"priceDimensions": dims}}}}
    if reserved:
        terms["Reserved"] = {
            sku: {
                f"r{i}": {
                    "termAttributes": {"LeaseContractLength": lease, "PurchaseOption": option},
                    "priceDimensions": {
                        f"d{j}": {"unit": unit, "pricePerUnit": {"USD": str(v)}}
                        for j, (unit, v) in enumerate(dims_)
                    },
                }
                for i, (lease, option, dims_) in enumerate(reserved)
            }
        }
    return {
        "publicationDate": published,
        "products": {sku: {"attributes": attributes}},
        "terms": terms,
    }


def test_extraction_picks_the_first_paid_tier_and_reservations():
    data = offer(
        "SKU1",
        {"usagetype": "Storage", "instanceType": "db.x"},
        [(0, 0), (25, 0.25), (500, 0.2)],
        reserved=[
            ("1yr", "No Upfront", [("Hrs", 0.1)]),
            ("3yr", "Partial Upfront", [("Hrs", 0.05), ("Quantity", 876)]),
        ],
    )
    offers = FakeOffers({"AmazonX-us-east-1": data})
    found = aws_prices.on_demand(offers, "AmazonX", "us-east-1", {"usagetype": "Storage"})
    assert found["price"] == 0.25 and found["sku"] == "SKU1" and found["published"] == "2026-09-01"
    wanted = {"instanceType": "db.x"}
    assert aws_prices.reserved(offers, "AmazonX", "us-east-1", wanted, 1) == 0.1
    assert aws_prices.reserved(offers, "AmazonX", "us-east-1", wanted, 3) == round(
        0.05 + 876 / 26280, 6
    )
    assert aws_prices.on_demand(offers, "AmazonX", "us-east-1", {"usagetype": "Missing"}) is None
    # A service AWS doesn't sell in a region has no offer file there.
    assert aws_prices.on_demand(offers, "AmazonX", "ap-south-1", {"usagetype": "Storage"}) is None


def test_usage_types_are_matched_without_the_region_prefix():
    assert aws_prices.usage_names("Fargate-GB-Hours", "us-east-1") == {
        "Fargate-GB-Hours",
        "USE1-Fargate-GB-Hours",
        "us-east-1-Fargate-GB-Hours",
    }
    assert "APS3-Fargate-GB-Hours" in aws_prices.usage_names("Fargate-GB-Hours", "ap-south-1")
    assert "Fargate-GB-Hours" not in aws_prices.usage_names("Fargate-GB-Hours", "ap-south-1")
    sqs = offer("Q", {"usagetype": "EU-Requests-Tier1"}, [(0, 0.0000004)])
    offers = FakeOffers({"AWSQueueService-eu-west-1": sqs})
    wanted = aws_prices.ON_DEMAND["sqs.requests"][2]
    assert aws_prices.on_demand(offers, "AWSQueueService", "eu-west-1", wanted)["sku"] == "Q"
    # CloudFront is priced at the edge locations near the region: India for Mumbai.
    edge = offer("CF", {"usagetype": "IN-DataTransfer-Out-Bytes"}, [(0, 0.109)])
    offers = FakeOffers({"AmazonCloudFront-aws-other": edge})
    _offer, scope, wanted, *_ = aws_prices.ON_DEMAND["cloudfront.egress_gb"]
    found = aws_prices.on_demand(offers, "AmazonCloudFront", "ap-south-1", wanted, scope)
    assert scope == "edge" and found["price"] == 0.109


def test_every_offered_region_has_a_name_a_prefix_and_an_edge():
    codes = {r["aws"]["code"] for r in catalog.regions().values()}
    assert codes == set(aws_prices.REGION_NAMES)
    assert codes == set(aws_prices.USAGE_PREFIXES) == set(aws_prices.EDGES)


def test_ec2_and_savings_plans_are_read_from_csv_rows():
    node = {
        "SKU": "N1",
        "TermType": "OnDemand",
        "usageType": "APS3-BoxUsage:m7g.large",
        "PricePerUnit": "0.0578",
        "PriceDescription": "$0.0578 per On Demand Linux m7g.large Instance Hour",
        **aws_prices.EC2_NODE,
    }
    windows = node | {"SKU": "N2", "Operating System": "Windows", "PricePerUnit": "0.15"}
    plan = {
        "Product Family": "ComputeSavingsPlans",
        "PurchaseOption": "No Upfront",
        "DiscountedUsageType": "APS3-Fargate-GB-Hours",
        "DiscountedOperation": "",
        "LeaseContractLength": "1",
        "DiscountedRate": "0.0035",
    }
    upfront = plan | {"PurchaseOption": "All Upfront", "DiscountedRate": "0.001"}
    offers = FakeOffers(
        {},
        {
            "AmazonEC2-ap-south-1": [windows, node],
            "savingsplan-ap-south-1": [upfront, plan, plan | {"LeaseContractLength": "3"}],
        },
    )
    found = aws_prices.ec2_node(offers, "ap-south-1")
    assert found["sku"] == "N1" and found["price"] == 0.0578 and found["published"] == "2026-09-02"
    rates = aws_prices.savings_plan_rates(offers, "ap-south-1")
    assert rates == {"fargate.gb_hours": {1: 0.0035, 3: 0.0035}}


def test_offer_csvs_are_filtered_as_they_stream():
    text = (
        '"FormatVersion","v1.0"\n"Disclaimer","x"\n"Publication Date","2026-09-25T17:45:21Z"\n'
        '"Version","1"\n"OfferCode","AmazonEC2"\n"SKU","usageType","PricePerUnit"\n'
        '"A","BoxUsage:m7g.large","0.08"\n"B","BoxUsage:c7g.large","0.07"\n'
    )
    published, rows = aws_prices._filter_csv(io.BytesIO(text.encode()), ["m7g.large"])
    assert published == "2026-09-25"
    assert rows == [{"SKU": "A", "usageType": "BoxUsage:m7g.large", "PricePerUnit": "0.08"}]


def test_each_region_has_its_own_prices():
    book = pricing.price_book("aws")
    assert set(book["regions"]) == set(aws_prices.REGION_NAMES) - {"us-east-1"}
    for code, regional in book["regions"].items():
        assert regional["price_region"] == aws_prices.REGION_NAMES[code]
        for key, entry in regional["prices"].items():
            assert key in book["prices"] and entry["sku"] and entry["price"] > 0, (code, key)
    mumbai = pricing.price_book("aws", "ap-south-1")
    assert mumbai["price_region"] == "Asia Pacific (Mumbai)"
    assert mumbai["reference_region"] == "US East (N. Virginia)"
    assert mumbai["prices"]["ec2.node_hours"]["unit"] == book["prices"]["ec2.node_hours"]["unit"]
    assert pricing.price_book("aws", "us-east-1") is book
    assert pricing.price_book("aws", "mars-1") is book


def test_estimates_use_the_design_region(monkeypatch):
    arch = map_to_provider(load_pattern("event-driven-processing"), "aws")
    assert arch.region_code == "ap-south-1"
    cost = pricing.estimate(arch)
    assert cost["price_region"] == "Asia Pacific (Mumbai)"
    assert not any("may differ" in note for note in cost["assumptions"])
    # A service with no price in the region keeps the reference price, and says so.
    book = pricing.price_book("aws")
    mumbai = {**book["regions"]["ap-south-1"]}
    mumbai["prices"] = {k: v for k, v in mumbai["prices"].items() if not k.startswith("sqs.")}
    patched = {**book, "regions": {**book["regions"], "ap-south-1": mumbai}}
    load = pricing._load_yaml
    monkeypatch.setattr(pricing, "_LOADED", {})
    monkeypatch.setattr(
        pricing, "_load_yaml", lambda source: patched if source.name == "aws.yaml" else load(source)
    )
    cost = pricing.estimate(arch)
    sqs = [line for line in cost["lines"] if line["service"] == "Amazon SQS"]
    assert sqs and all(line["elsewhere"] for line in sqs)
    assert "Amazon SQS has no list price in Asia Pacific (Mumbai)" in " ".join(cost["assumptions"])


def test_live_lookup_searches_one_service(monkeypatch):
    index = {"regions": {"us-east-1": {"currentVersionUrl": "/offers/x.json"}}}
    data = offer("S1", {"usagetype": "TimedStorage-ByteHrs"}, [(0, 0.023)])

    class Response(io.BytesIO):
        headers = {"Content-Length": "100"}

    def fake_urlopen(request, timeout=0):
        url = request if isinstance(request, str) else request.full_url
        return Response(json.dumps(index if url.endswith("region_index.json") else data).encode())

    monkeypatch.setattr(aws_prices.urllib.request, "urlopen", fake_urlopen)
    rows = aws_prices.lookup("AmazonS3", "storage")
    assert rows == [
        {
            "sku": "S1",
            "usage_type": "TimedStorage-ByteHrs",
            "price_usd": 0.023,
            "unit": "Hrs",
            "description": "$0.023 tier 0",
        }
    ]
    assert aws_prices.lookup("AmazonS3", "glacier") == []
    with pytest.raises(ValueError, match="no prices for region"):
        aws_prices.lookup("AmazonS3", "", region="mars-1")
