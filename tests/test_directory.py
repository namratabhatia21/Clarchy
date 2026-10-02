"""Each cloud's full service list, read from the provider's own product list."""

from clarchy import directory, payloads

AWS = {
    "items": [
        {
            "item": {
                "additionalFields": {
                    "productName": "AWS Lambda",
                    "productCategory": "Compute",
                    "productSummary": "Run code without thinking about servers",
                    "productUrl": "https://aws.amazon.com/lambda/?did=ap_card&trk=ap_card",
                    "pricingUrl": "https://aws.amazon.com/lambda/pricing/?did=ap_card",
                }
            }
        },
        {"item": {"additionalFields": {"productName": "No page", "productUrl": ""}}},
    ]
}

AZURE = {
    "productDirectory": {
        "items": [
            {
                "title": "Azure Front Door",
                "summary": "Modern cloud CDN",
                "azureCategories": ["featured", "networking"],
                "url": "frontdoor/index.yml",
            },
            {
                "title": "Microsoft Entra ID",
                "summary": "Identity",
                "azureCategories": ["identity"],
                "url": "/entra/fundamentals/",
            },
        ]
    }
}

GCP = (
    '["Compute","https://cloud.google.com/products/compute",null,null] '
    'class="cloud-dropdown-menu-heading" '
    '["Cloud Run","https://cloud.google.com/run?hl=en",null,"Fully managed serverless apps"] '
    '["See all products","https://cloud.google.com/products",null,"Every product we offer"]'
)


def test_aws_list_keeps_names_categories_and_clean_links():
    [lam] = directory.aws_services(AWS)
    assert lam == {
        "name": "AWS Lambda",
        "category": "Compute",
        "summary": "Run code without thinking about servers",
        "url": "https://aws.amazon.com/lambda/",
        "pricing": "https://aws.amazon.com/lambda/pricing/",
    }


def test_azure_list_takes_the_first_real_category_and_full_links():
    found = {s["name"]: s for s in directory.azure_services(AZURE)}
    front, entra = found["Azure Front Door"], found["Microsoft Entra ID"]
    assert front["category"] == "Networking"
    assert front["url"] == "https://learn.microsoft.com/en-us/azure/frontdoor/"
    assert entra["url"] == "https://learn.microsoft.com/en-us/entra/fundamentals/"


def test_gcp_list_reads_products_under_their_category():
    assert directory.gcp_services(GCP) == [
        {
            "name": "Cloud Run",
            "category": "Compute",
            "summary": "Fully managed serverless apps",
            "url": "https://cloud.google.com/run",
        }
    ]


def test_services_clarchy_draws_are_found_by_name_or_documentation_page():
    caps = payloads.catalog_payload()["capabilities"]
    services = [
        {
            "name": "AWS Lambda",
            "category": "Compute",
            "summary": "",
            "url": "https://aws.amazon.com/lambda/",
        },
        {
            "name": "Amazon Kinesis",
            "category": "Analytics",
            "summary": "",
            "url": "https://aws.amazon.com/kinesis/",
        },
    ]
    used = directory.used_in_designs("aws", services, caps)
    assert used["https://aws.amazon.com/lambda/"] == ["Serverless function"]
    # A docs page on another site never ties a product to a capability.
    azure = [
        {
            "name": "Azure Copilot",
            "category": "Management",
            "summary": "",
            "url": "https://learn.microsoft.com/en-us/azure/copilot",
        }
    ]
    assert directory.used_in_designs("azure", azure, caps) == {}


def test_bundled_lists_are_complete_enough_to_show():
    for provider, least in (("azure", 150), ("gcp", 120)):
        book = directory.book(provider)
        assert book["provider"] == provider and len(book["services"]) >= least
        assert all(s["name"] and s["url"].startswith("https://") for s in book["services"])
