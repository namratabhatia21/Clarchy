# 0007: Cost estimates come from price lists, not from the model

**Status:** accepted · 2026-10-01 · applies [0003](0003-llm-proposes-code-calculates.md)

## Context

People choosing a design want to know what it costs over the period they will run it,
and how much a longer commitment saves. Prices quoted by a language model are plausible
but unverifiable and go out of date. Prices must be traceable to the provider's own
published price and kept current without hand editing.

## Decision

- Code calculates every cost. A neutral usage model (`pricing.usage`) turns each
  component's `sizing` and the requirements into quantities (requests, GB-months,
  instance hours, active users), each with the assumption it rests on. Provider billing
  models (`data/prices/models.yaml`) say which priced items a capability bills for, and
  price books (`data/prices/<provider>.yaml`) hold the unit prices.
- Estimates cover 1, 6, 12 and 36 months. Stored data grows by the stated monthly
  growth, so longer terms are not a simple multiple of the first month. Free allowances
  are subtracted.
- Commitments use the provider's own rates: Compute Savings Plans (no upfront) for AWS
  Lambda, Fargate and EC2, reserved instances or nodes for databases and caches, and
  reserved capacity where a service has one. A 3-year rate falls back to the 1-year rate
  when there is none. The break-even month compares only the items a commitment covers.
- The AWS price book is generated from the **AWS Price List API** bulk offer files
  (`clarchy prices update`), the machine-readable source behind AWS's pricing pages.
  Each price records its SKU, AWS's description and the publication date. The Pages
  workflow regenerates it on every deploy and every Monday; when AWS cannot be reached it
  publishes the committed book and warns. `clarchy prices lookup` searches one
  service's current prices live, and MCP clients such as Claude have the same search as
  the `aws_price_lookup` tool. The design agent uses `estimate_cost` only.
- Azure and Google Cloud price books are compiled by hand from their pricing pages, with
  a source link per price, and are marked `verified: false`; the UI labels them
  approximate. Open-source designs are not priced: there is no list price for running
  software yourself.
- Prices are for one reference region per cloud (US East, East US, Iowa). The cost view
  says so when the design is in another region.

## Consequences

- Every number on the cost view can be traced to a quantity, a unit price and, on AWS, a
  SKU, and changing the spec changes the estimate immediately.
- Estimates are list prices only: no data transfer, support plans, taxes, Spot or
  negotiated discounts, and the usage model is a heuristic, not a measurement.
- Regenerating the AWS book downloads about 1 GB of offer files (EC2 and Savings Plans
  are the largest), so it runs in CI rather than in the browser.
- Azure and Google Cloud prices can drift until they are read from those providers'
  price APIs (roadmap phase 4).
