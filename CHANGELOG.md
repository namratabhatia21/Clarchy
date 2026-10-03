# Changelog

Notable changes to Clarchy, newest first. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/). Each release on GitHub takes its notes from
the version's section here.

## [0.1.0] - 2026-10-02

The first public release.

### Added

- A planning pipeline from a requirements brief (Word, PDF, Excel, Markdown or text) to
  a cloud-neutral spec: read, understand, design, build and deploy, workflows, and the
  mapping to every provider.
- An LLM design agent that works through Clarchy's own MCP server; its design is
  accepted only when `check_submission` passes it (schema, every provider's mapping,
  evidence found in the brief), and the run falls back to the rule-based planner if the
  model fails.
- Model backends: the Claude API, Claude on Amazon Bedrock, Hugging Face Inference
  Providers, Ollama and any OpenAI-compatible endpoint.
- A rule-based planner that needs no model or network.
- Diagrams for AWS, Azure, Google Cloud and open source, each in its provider's
  documentation style with official icons.
- Cost estimates for 1 month to 3 years, on demand and with commitments. AWS and Azure
  prices come from their price APIs for eight regions and are refreshed daily; Google
  Cloud prices are compiled by hand for Iowa and marked approximate.
- Policy checklists for the EU AI Act, GDPR, the OWASP Top 10 for LLM applications, the
  NIST AI RMF, ISO/IEC 42001, ISO/IEC 27001, HIPAA, PCI DSS, SOX and India's DPDP Act.
- A command-line tool (`clarchy plan`, `serve`, `mcp`, `export-site` and more) and an
  MCP server for Claude Code, Claude Desktop and other MCP clients.
- A static site that plans in the browser with Pyodide (clarchy.com), a single-file
  export for static hosts, and a mirror on Hugging Face Spaces.
- Privacy, cookie and terms pages, a feedback form, and accessibility checked with
  axe-core against WCAG 2.2 AA.

### Removed

- Sign-up, free-diagram credits, the Pro waitlist, the pricing page and the Worker
  accounts API, which Clarchy no longer needs as an open-source project.
