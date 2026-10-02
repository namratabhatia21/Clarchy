# 0014: Prices for every region, refreshed daily

**Status:** accepted · 2026-10-02 · updates [0007](0007-cost-estimates-from-price-lists.md)

## Context

ADR 0007 priced every design in one reference region per cloud and refreshed AWS prices on
each deploy and every Monday. A design in Mumbai or Frankfurt was priced at US East rates,
and prices could be a week old. The founder asked for the providers' official prices, per
region, every day. Clarchy stays on free services: Cloudflare's free Worker can't download
gigabytes of offer files, and the site builds on every push.

## Decision

- **A price book holds every region.** `prices` keeps the reference region (US East for
  AWS) with the provider's SKU and description for each price; `regions` holds the same
  prices for each other region in `data/regions.yaml`, with their SKUs. `pricing.price_book`
  returns a region's view, and an estimate uses the design's region.
- **A price a region doesn't have stands in from the reference region, said out loud:**
  the line is tagged "Other region" and the notes name the service.
- **AWS** comes from the Price List API: the small offers as JSON, EC2 and Compute Savings
  Plans as CSV read line by line while they download (about 200 MB each per region), so
  nothing large is held in memory. Usage types are matched without AWS's region prefix
  (`USW2-`, `APS3-`), with alternatives where AWS names the same usage differently in a
  region (SQS standard requests, Secrets Manager). CloudFront is priced at the edge
  locations near the region. Rebuilding US East alone reproduces the previous book exactly.
- **A daily GitHub workflow** (`prices.yml`) refreshes the books, regenerates the examples
  whose explanations show prices, runs the tests and commits as github-actions[bot] when a
  price has changed. Workers Builds deploys that commit. Days when only the publication
  date moved commit nothing. `make prices` refreshes only with `CLARCHY_REFRESH_PRICES=1`,
  so site builds use the committed books.
- **Azure** comes from the Azure Retail Prices API, which is public: 55 meters named by
  product, SKU and meter name (chosen with `azure_prices.py --discover`, run on GitHub
  Actions by the Price discovery workflow), in each of the eight regions. Pay-as-you-go
  prices use the first paid tier; Container Apps and VM nodes carry their savings plan
  rates, PostgreSQL its reservations per vCore (the standby server doubles both). Front
  Door bills by the zone its visitors are in, and Azure DNS is the same everywhere.
  Prices the API doesn't carry (Entra ID P2 licences, Azure DevOps parallel jobs, Front
  Door WAF custom rules and requests) keep their hand-compiled value, marked `manual`,
  and their lines are tagged approximate. A meter that disappears from the API keeps its
  last price, marked manual, and the run names it.
- **Google Cloud** will come from the Cloud Billing Catalog API, which needs a free API key
  saved as the repository secret `GCP_API_KEY`; `gcp_prices.py --discover` is ready for
  it. Until then the Google Cloud book stays hand-compiled for one region and approximate.

## Consequences

- Designs outside US East show their own region's prices; Mumbai and Singapore databases,
  for example, cost more than in Virginia, and Mumbai nodes less.
- The AWS book grows from 63 to about 500 prices (43 KB), which the in-browser engine
  carries too.
- The repository gains a bot commit on days AWS changes a price. The job takes a few
  minutes of the 2,000 free GitHub Actions minutes a private repository gets each month.
- Every run rebuilds every region in full. If a download fails, the run fails and
  commits nothing, so the site keeps the last good book.
