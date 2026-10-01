---
name: cloudarchie-architect
description: Design a cloud architecture for an app from requirements (typed, or a Word, PDF or Excel file) with the CloudArchie MCP tools, and explain it on AWS, Azure, Google Cloud or open source. Use when someone asks which cloud services to use, wants an architecture diagram, or wants to compare the same design across providers.
---

# CloudArchie architect

Design with the CloudArchie MCP server (`cloudarchie mcp`). Every design is a
cloud-neutral YAML spec of capabilities that CloudArchie maps to each provider, so never
write provider product names into the spec.

## Steps

1. **Read the requirements.** If you were given a file, read it. Note numbers (users,
   requests per second, data size and growth, availability), region, compliance and
   budget. Write down what is missing; those become `open_questions`.
2. **Start from a pattern.** Call `list_patterns`, then `get_pattern` for the closest one
   or two. Adapt rather than starting from nothing.
3. **Learn the vocabulary.** Call `list_capabilities` and `list_regions`. Use only those
   ids. `search_services` shows what a capability becomes on each provider, and finds a
   capability from a product name ("Lambda", "KEDA").
4. **Write the runtime spec.** Users (`client`), edge, entry, compute, integration, data
   and platform components. Each needs an `id`, `capability`, `label`, a one or two
   sentence `rationale` tied to the requirements, and `evidence`: exact short quotes from
   the requirements (empty when it is simply good practice). Add `sizing` hints. Connect
   components with `edges`. Fill `assumptions` and `open_questions`.
5. **Validate.** Call `validate_spec` and fix every error. Consider each warning.
6. **Add build and deploy.** Call `add_delivery_toolchain`. It adds source control, CI,
   a container registry when containers are used, a release pipeline, infrastructure as
   code, and KEDA autoscaling for Kubernetes workers fed by a queue or stream. Do not
   hand-write these.
7. **Show it.** Call `render_design` for the provider the user cares about (default
   `aws`); save the SVG and summarise the Markdown explanation. Offer the other providers.
8. **Price it.** Call `estimate_cost` for each provider the user is weighing. It returns
   the monthly cost per service and line item, totals for 1 month, 6 months, 1 year and
   3 years on demand and with commitments, and the month a 1-year commitment pays off.
   `aws_price_lookup` searches AWS's current list prices for any service when the user
   asks about something the estimate does not cover.

## Explaining the result

- Lead with the shape of the design in two or three sentences, then the key choices and
  their trade-offs.
- Point out services marked `close` or `partial` on the chosen provider and what differs.
- List the assumptions and the questions to confirm.
- Quote prices only from `estimate_cost` or `aws_price_lookup`, and say what usage they
  assume. AWS prices come from the AWS Price List API; Azure and Google Cloud prices are
  approximate. Estimates are list prices without data transfer, support or taxes.

## Quick draft

For a fast first draft, `draft_architecture` runs the rule-based planner on plain text and
returns a complete spec, including the toolchain and workflows. Review and improve it with
steps 4 to 7.
