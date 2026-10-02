"""Reading Azure prices from the Retail Prices API, by meter name, for every region."""

import pytest

from clarchy import azure_prices as az
from clarchy import catalog, pricing


def item(product, sku, meter, price, unit="1 Hour", tier=0, kind="Consumption", **extra):
    return {
        "productName": product,
        "skuName": sku,
        "meterName": meter,
        "retailPrice": price,
        "unitOfMeasure": unit,
        "tierMinimumUnits": tier,
        "type": kind,
        **extra,
    }


def test_units_of_measure():
    assert az.unit_quantity("10K") == 1e4 and az.unit_quantity("1M") == 1e6
    assert az.unit_quantity("100 Hours") == 100 and az.unit_quantity("1/Month") == 1
    assert az.unit_quantity("1 GB/Month") == 1


def test_first_paid_tier_and_unit_conversion():
    m = az.METERS["functions.executions"]
    items = [
        item("Functions", "Standard", "Standard Total Executions", 0.0, "10"),
        item("Functions", "Standard", "Standard Total Executions", 2e-06, "10", tier=100000),
        item("Functions", "Standard", "Other", 9.0, "10"),
    ]
    assert az.price_in(items, m)["price"] == pytest.approx(0.20)  # per 1M executions


def test_savings_plans_per_second_become_hourly_rates():
    m = az.METERS["containerapps.vcpu_hours"]
    plan = [
        {"term": "1 Year", "retailPrice": 2.04e-05},
        {"term": "3 Years", "retailPrice": 1.992e-05},
    ]
    items = [
        item(
            "Azure Container Apps",
            "Standard",
            "Standard vCPU Active Usage",
            2.4e-05,
            "1 Second",
            savingsPlan=plan,
        )
    ]
    entry = az.price_in(items, m)
    assert entry["price"] == pytest.approx(0.0864)
    assert entry["commit_1yr"] == pytest.approx(0.07344)
    assert entry["commit_3yr"] == pytest.approx(0.071712)


def test_database_reservations_are_per_vcore_and_standby_doubles():
    m = az.METERS["postgres.medium.multi"]
    product = az.PG_GP
    items = [
        item(product, "2 vCore", "vCore", 0.178),
        item(product, "vCore", "vCore", 468.0, kind="Reservation", reservationTerm="1 Year"),
        item(product, "vCore", "vCore", 936.0, kind="Reservation", reservationTerm="3 Years"),
    ]
    entry = az.price_in(items, m)
    assert entry["price"] == pytest.approx(0.356)
    assert entry["commit_1yr"] == pytest.approx(468 / 8760 * 2 * 2)
    assert entry["commit_3yr"] == pytest.approx(936 / 26280 * 2 * 2)


def test_zone_priced_meters_take_the_zone_of_the_region():
    m = az.METERS["frontdoor.requests"]
    items = [
        item(
            "Azure Front Door",
            "Standard",
            "Standard Requests",
            0.009,
            "10K",
            armRegionName="Zone 1",
        ),
        item(
            "Azure Front Door",
            "Standard",
            "Standard Requests",
            0.0108,
            "10K",
            armRegionName="Zone 2",
        ),
    ]
    assert az.price_in(items, m, az.FRONT_DOOR_ZONES["eastus"])["price"] == pytest.approx(0.009)
    singapore = az.price_in(items, m, az.FRONT_DOOR_ZONES["southeastasia"])
    assert singapore["price"] == pytest.approx(0.0108)


class FakeCatalog(az.Catalog):
    """Every meter priced at 1 per unit, a little dearer outside East US, except one meter
    that has gone from the API."""

    def items(self, m, region):
        if m.meter == "Standard Uptime SLA":
            return []
        price = 1.0 if region == az.REFERENCE else 1.1
        zone = m.zones[region] if m.zones else None
        reserve = []
        if m.reserve:
            sku, meter, _units = m.reserve
            reserve = [
                item(m.product, sku, meter, 8760.0, kind="Reservation", reservationTerm="1 Year")
            ]
        return [
            item(m.product, m.sku, m.meter, price, "1", armRegionName=zone or region),
            *reserve,
        ]


def test_the_book_has_every_region_and_keeps_what_the_api_lacks():
    manual = {
        "entra.p2_users": {"price": 9.0, "unit": "user-month", "source": "https://example.com/p2"},
        "aks.cluster_hours": {"price": 0.1, "unit": "cluster-hour", "source": "https://e.com"},
    }
    result = az.build(FakeCatalog(), manual)
    book = result["book"]
    assert book["verified"] is True and book["region_code"] == "eastus"
    assert set(book["regions"]) == set(az.REGION_NAMES) - {"eastus"}
    assert book["prices"]["functions.gb_seconds"]["meter"].endswith("Standard Execution Time")
    # Not in the API: kept as it was, marked manual, the same everywhere.
    assert book["prices"]["entra.p2_users"] == {**manual["entra.p2_users"], "manual": True}
    assert result["missing"] == ["aks.cluster_hours"]
    assert book["prices"]["aks.cluster_hours"]["manual"] is True
    india = book["regions"]["centralindia"]["prices"]
    assert india["functions.gb_seconds"]["price"] == pytest.approx(1.1)
    assert india["entra.p2_users"]["manual"] is True
    assert (
        "unit" not in india["functions.gb_seconds"] and "meter" not in india["functions.gb_seconds"]
    )


def test_every_azure_price_clarchy_uses_is_read_from_the_api_or_known_to_be_manual():
    models = pricing.billing_models()["azure"]
    used = {
        item_["price"]
        for model in models["capabilities"].values()
        for item_ in model.get("items", [])
    }
    expanded = set()
    for key in used:
        if "{db_size}" in key:
            expanded |= {
                key.format(db_size=s, db_az=a)
                for s in ("small", "medium", "large")
                for a in ("single", "multi")
            }
        elif "{db_az}" in key:
            expanded |= {key.format(db_az=a) for a in ("single", "multi")}
        elif "{cache_size}" in key:
            expanded |= {key.format(cache_size=s) for s in ("small", "large")}
        else:
            expanded.add(key)
    third_party = set(pricing.price_book("thirdparty")["prices"])
    manual = {"entra.p2_users", "pipelines.parallel_jobs", "waf.rules", "waf.requests"}
    assert expanded - third_party - manual <= set(az.METERS)
    assert {r["azure"]["code"] for r in catalog.regions().values()} == set(az.REGION_NAMES)
    assert set(az.FRONT_DOOR_ZONES) == set(az.REGION_NAMES)
