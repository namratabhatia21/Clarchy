# Clarchy

**Describe your app. Get the architecture.** Type your requirements or upload a Word, PDF
or Excel document. An agent turns them into a cloud-neutral spec and designs everything
the app needs, from source control, builds and container images to compute, autoscaling,
databases, storage and monitoring. It then shows the design on **AWS, Azure, Google Cloud
or open source**, each in its own look, explains every choice and estimates the **cost for
1 month, 6 months, 1 year and 3 years**, on demand and with commitments.

**Live site:** https://clarchy.com plans your own requirements
right in your browser, with no server: the page runs Clarchy's Python engine with
[Pyodide](https://pyodide.org). Planning is rule-based by default; for the AI agent, use an
open-source model on Hugging Face with your own free token, or a model on your machine
through Ollama. AWS prices are refreshed from the AWS Price List API on every deploy and
every week.

The site looks like an architect's drawing set: trace paper by day, a drafting table at
night, redline orange for what matters, sheet numbers, title blocks and dimension lines. A
protractor turns as you scroll the home page and a detail drawing assembles stage by stage
([ADR 0009](docs/decisions/0009-a-drawing-set-identity.md)).

![Microservices on Kubernetes, on AWS](examples/kubernetes-microservices.aws.svg)

## What you get

| Page | What it does |
|---|---|
| **Plan** | Type or drop in a requirements document (.docx, .pdf, .xlsx, .md, .txt), or start from a realistic sample (a field service agent for wind turbine technicians, a claims triage agent, clinic booking under HIPAA, fleet telemetry, supplier invoice processing). Watch the pipeline work stage by stage, then explore the result: a diagram per provider, every service grouped by lifecycle stage, the cost over time with prepaid credits, the AI and data policies that apply, step-by-step workflows that light up the diagram, and the editable YAML spec. Answer the open questions and plan again. |
| **Examples** | Seven reference architectures (serverless web app, containerised API, event-driven processing, data pipeline, RAG chatbot, microservices on Kubernetes, AI agent platform) on every provider. |
| **Services** | A catalog of every capability with the equivalent service on each provider side by side. Filter by lifecycle stage, provider and how close the match is, or search by any service name ("KEDA", "LangGraph", "Glacier", "Copilot"). |
| **Pricing** | Free: 3 diagrams from your own briefs (samples, examples and re-planning are free). Pro: unlimited, in early access through a waitlist. On clarchy.com the first action on the home page asks for name, company, email and whether to send product updates. |
| **How to** | A step-by-step guide: what to put in a brief and what each fact changes, reading the drawing and its tabs, answering questions, downloading, and using an AI model. Its example brief plans in one click. |
| **Blog** and **About** | Why Clarchy exists, worked examples and AI regulations for architects; and what Clarchy stands for, with a contact address. |

Every component carries a **rationale**, the **sentences from your document** that led to
it, how close each provider's service is (**exact, close or partial**) and the
**alternatives**. What the planner had to assume, and what you should confirm, is listed
at the top.

Diagrams follow each provider's visual language (AWS dark frame and category colours,
Azure blue, Google Cloud's palette, a neutral style for open source) without using any
provider logos or icons.

## How the agent works

```
document ─► read ─► understand ─► design ─────────► toolchain ─► workflows ─► map
 .docx       text    requirements   Claude + MCP      CI/CD,       request,     AWS, Azure,
 .pdf                needs, gaps    tools, validated  registry,    background,  Google Cloud,
 .xlsx                              loop              KEDA         delivery     open source
```

1. **Read**: Word, Excel and PDF files are parsed locally (zip and XML for Office files,
   [pypdf](https://pypi.org/project/pypdf/) for PDFs), with size and zip-bomb limits.
2. **Understand**: Claude extracts users, peak load, data size, availability, region,
   compliance and budget as **structured output** (a JSON schema), plus each need with a
   quote from the document. Quotes that are not in the document are dropped.
3. **Design**: Claude works as an **agent**. It is an MCP client of Clarchy's own
   **MCP server**, so it can list capabilities, regions and reference patterns, search
   equivalent services and validate drafts. It must finish by calling `submit_design`,
   whose input is checked against the schema and every provider mapping. Errors go back
   to the model to fix. Evidence quotes that cannot be found in the document are removed.
4. **Toolchain**: deterministic code adds source control, CI build, container registry
   (for containers), release pipeline and infrastructure as code, plus **KEDA**
   event-driven autoscaling when Kubernetes workers consume a queue or stream.
5. **Workflows**: Claude describes how a request is served, how background or data work
   flows and how a change is shipped. Each step is limited to the real component ids.
6. **Map**: every capability becomes a concrete service on each provider.

The agent runs on **Claude** (Claude API or Amazon Bedrock) or on an **open-source model**
through any OpenAI-compatible endpoint: Hugging Face Inference Providers, Ollama, vLLM or
LM Studio. Requests and replies are translated, so the same loop and guardrails apply.

Without a model the same pipeline runs with a **rule-based planner** that reads the text
with patterns, so the app always works offline. If the AI path fails part-way, the run
falls back to the rule-based draft and says so.

The model never draws the diagram or invents services. Layout is deterministic code, and
the model can only use capabilities from the catalog (see
[ADR 0004](docs/decisions/0004-agent-designs-with-mcp-tools.md)).

## Security, records and AI policies

Designs include what reviews ask about, not just the app:

- **AI building blocks**: agent orchestration (LangGraph, Bedrock AgentCore, Foundry Agent
  Service, Vertex AI Agent Engine), an LLM gateway (LiteLLM, Azure API Management),
  guardrails (Bedrock Guardrails, Azure AI Content Safety, Model Armor, NeMo Guardrails)
  and LLM tracing (Langfuse, CloudWatch, Application Insights, Cloud Trace).
- **Security and access**: access governance (who may change the cloud, approved by the
  cloud architects), customer-managed keys and an audit trail.
- **Records**: backups, and an archive tier (S3 Glacier Deep Archive, Azure Archive,
  Cloud Storage Archive) for records kept for years; the planner reads retention periods
  such as "audit logs are kept for 7 years".
- **Developer tools** in the build lane: cloud dev environments (GitHub Codespaces, Cloud
  Workstations, Coder) and AI coding assistants (Amazon Q Developer, GitHub Copilot, Gemini
  Code Assist), priced per developer. Cloudflare and the OpenAI, Anthropic and Hugging Face
  APIs appear as alternatives.

The **Policies** view checks each design against the EU AI Act, GDPR, the OWASP Top 10
for LLM applications, the NIST AI RMF, ISO/IEC 42001, model provider terms, HIPAA,
PCI DSS, SOX, ISO/IEC 27001 and India's DPDP Act, as they apply
([data/policies.yaml](src/clarchy/data/policies.yaml)). Each obligation is covered by a
component, a gap with a suggested capability, or an action for the team. It is a design
checklist, not legal advice.

## Cost estimates

Every design is priced on each cloud, per service and per line item (quantity × unit
price), for **1 month, 6 months, 1 year and 3 years**, on demand and with **1- or 3-year
commitments** (Savings Plans, reserved instances, committed use discounts), with the month
when a 1-year commitment pays off. Storage grows with the stated data growth, so longer
periods cost more than a multiple of the first month.

- **AWS prices come from the [AWS Price List API](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/price-changes.html)**,
  AWS's official machine-readable source behind its pricing pages, with the SKU and AWS's
  description for every price, including Savings Plans and reserved-instance rates.
  `clarchy prices update` refreshes them; the public site refreshes them on every
  deploy and every Monday. `clarchy prices lookup AmazonS3 storage` searches any
  service's current prices live.
- Azure and Google Cloud prices are compiled by hand from their pricing pages and marked
  **approximate** in the UI until they are read from those providers' price APIs too.
  Services from outside the three clouds, such as GitHub Codespaces and Copilot, come from
  a third-party price book and are tagged approximate line by line.
- **Prepaid credits** (cloud credits for the whole bill, model credits from OpenAI, Hugging
  Face or Anthropic for model spend) can be entered on the cost view to see what you
  actually pay and how many months they cover.
- Usage comes from each component's `sizing` and the requirements, and every line says
  what it assumed. Edit the spec to see the effect. See
  [ADR 0007](docs/decisions/0007-cost-estimates-from-price-lists.md).

## Run it yourself

```bash
git clone https://github.com/namratabhatia21/Clarchy && cd Clarchy
python -m venv .venv && . .venv/bin/activate
pip install -e ".[all]"

clarchy serve                       # http://127.0.0.1:8000, rule-based planner
```

### Turn on the AI agent

```bash
export ANTHROPIC_API_KEY=sk-ant-...     # Claude API
clarchy serve                        # the top bar now shows the AI agent

# or Claude on Amazon Bedrock, with your usual AWS credentials
export CLARCHY_LLM=bedrock AWS_REGION=us-east-1

# or an open-source model on Hugging Face (free token: huggingface.co/settings/tokens)
export HF_TOKEN=hf_...                   # default model: Qwen/Qwen2.5-72B-Instruct

# or an open-source model on your own machine
ollama pull qwen2.5:7b
export CLARCHY_LLM=ollama CLARCHY_MODEL=qwen2.5:7b
```

| Variable | Meaning |
|---|---|
| `ANTHROPIC_API_KEY` | Enables the AI agent through the Claude API. |
| `HF_TOKEN` | Enables the AI agent on open-source models through Hugging Face Inference Providers. |
| `CLARCHY_LLM` | `anthropic`, `bedrock`, `huggingface`, `ollama`, `openai-compatible` or `rules` (default: `anthropic` with an Anthropic key, `huggingface` with `HF_TOKEN`, otherwise `rules`). |
| `CLARCHY_MODEL` | The model id (defaults are in `src/clarchy/planner/`). |
| `CLARCHY_LLM_BASE_URL`, `CLARCHY_LLM_API_KEY` | Endpoint and key for `ollama` (optional) or `openai-compatible`. |
| `AWS_REGION` | Region for Amazon Bedrock. |
| `CLARCHY_PRICES_DIR` | Folder of refreshed price books (default: `~/.cache/clarchy/prices`, written by `clarchy prices update`). |
| `CLARCHY_CORS_ORIGINS` | Comma-separated origins allowed to call the API, for a front end hosted elsewhere. |
| `CLARCHY_ICONS_AWS` (and `_AZURE`, `_GCP`) | Folder of a provider's official icon package; see below. |

### From the command line

```bash
clarchy plan requirements.docx              # AI agent if configured, otherwise rules
clarchy plan "A booking app for 40 clinics in the UK..." --rules -o plan/
clarchy plan brief.pdf --region eu-central --mcp "<command that starts an MCP server>"
```

`plan` writes `spec.yaml` plus a diagram (`.svg`) and an explanation (`.md`) for every
provider. `--mcp` attaches extra MCP servers (a pricing or documentation server, say)
whose tools the agent may also use.

Other commands: `patterns`, `validate <spec>`, `render <spec> --provider azure`,
`explain <spec>`, `prices update`, `prices lookup <AWS service> <words>`, `export-site`,
`mcp`. Run `clarchy --help` for details.

## Use Clarchy from Claude

Clarchy is an MCP server, so Claude Code, Claude Desktop or any MCP client can design
with it directly:

```bash
claude mcp add clarchy -- clarchy mcp                     # Claude Code
```

```json
{ "mcpServers": { "clarchy": { "command": "clarchy", "args": ["mcp"] } } }
```

(Claude Desktop: add that to `claude_desktop_config.json`, using the full path to
`clarchy` inside your virtual environment.)

| Tool | What it does |
|---|---|
| `list_capabilities`, `list_regions`, `list_patterns`, `get_pattern` | The vocabulary and the reference designs. |
| `search_services` | Equivalent services across providers for a capability or service name. |
| `validate_spec` | Errors to fix and warnings worth considering, against every provider. |
| `add_delivery_toolchain` | Adds CI/CD, registry, infrastructure as code and KEDA where needed. |
| `render_design` | SVG diagram and Markdown explanation on one provider. |
| `estimate_cost` | Monthly cost and 1-month to 3-year totals, on demand and with commitments. |
| `aws_price_lookup` | Search the latest AWS prices of one service, live from the AWS Price List API. |
| `draft_architecture` | A rule-based first draft from requirements text. |

The server also offers each pattern as a resource (`clarchy://patterns/{id}`) and a
`design_architecture` prompt. For Claude Code there is an Agent Skill in
[skills/clarchy-architect](skills/clarchy-architect/SKILL.md) that walks through a
complete design; copy the folder to `~/.claude/skills/`.

## The spec

Designs are YAML built from **capabilities** (`object-storage`, `kubernetes`,
`message-queue`, ...) rather than product names, so one design maps to every provider:

```yaml
name: Photo sharing
summary: Upload photos, generate thumbnails, share albums.
requirements: {users: 50000, peak_rps: 40, region: india-mumbai}
components:
  - {id: users, capability: client}
  - {id: api, capability: api-gateway}
  - id: thumbs
    capability: serverless-function
    rationale: Thumbnails are short bursty jobs; pay only when photos arrive.
    evidence: ["Thumbnails should be ready within a few seconds"]
    sizing: {invocations_per_month: 2000000, avg_duration_ms: 400, memory_mb: 1024}
  - {id: photos, capability: object-storage, sizing: {storage_gb: 800}}
edges:
  - {from: users, to: api}
  - {from: api, to: thumbs}
  - {from: thumbs, to: photos}
```

Optional sections: `assumptions`, `open_questions` and `workflows` (named, ordered steps
that reference component ids). Capabilities, with their tier, lifecycle stage and
category, are in
[`data/capabilities.yaml`](src/clarchy/data/capabilities.yaml); each provider's
services and diagram theme are in [`data/mappings/`](src/clarchy/data/mappings/).

## Code map

| Module | Role |
|---|---|
| `ingest.py` | Word, Excel, PDF and text to plain text, with limits |
| `planner/` | `pipeline.py` (stages and events), `agent.py` (understand, design loop, workflows), `toolbox.py` (MCP client) and `local_toolbox.py` (the same tools in-process), `rules.py` (offline planner), `llm.py` (Claude API or Bedrock), `openai_compat.py` (open-source models), `prompts.py` |
| `pricing.py`, `aws_prices.py`, `data/prices/` | Usage model, price books and billing models; AWS prices from the Price List API |
| `browser.py` | Entry points for the in-browser engine (Pyodide) |
| `tools.py`, `mcp_server.py` | The tool functions and the MCP server that exposes them |
| `delivery.py`, `workflows.py` | Deterministic build-and-deploy toolchain and generated workflows |
| `spec.py`, `catalog.py`, `mapping.py` | The neutral spec, its data and the provider mapping |
| `render.py`, `explain.py` | Themed SVG diagrams and Markdown explanations |
| `web.py`, `payloads.py`, `static/` | FastAPI app (with a server-sent events `/api/plan` stream) and a no-build front end |
| `planner/answers.py` | Answers to open questions turned into requirement statements for a re-plan |
| `policies.py`, `data/policies.yaml` | AI and data regulations checked against a design |
| `blog.py`, `data/blog/` | Blog posts in Markdown, rendered without dependencies |
| `export.py` | The static site for GitHub Pages or Cloudflare Pages, with the in-browser engine bundle |
| `worker/` | The Cloudflare Worker API on clarchy.com: sign-ups, free diagrams and the Pro waitlist in D1 (`index.mjs`, `migrations/`, tests) |

Design decisions are recorded in [docs/decisions/](docs/decisions/).

## Static site

```bash
clarchy export-site -o site/                          # the whole site (see below)
clarchy export-site -o site/ --no-engine              # replay-only page
clarchy export-site -o site/ --api-base https://...   # a front end for a hosted API
```

The page plans in the visitor's browser: it loads Pyodide from its CDN on first use (about
15 MB, then cached) and runs this package from `clarchy-engine.zip` next to the page.
The catalog and recorded runs of the samples are embedded; the pre-drawn examples sit in
`designs/` and load when shown
([ADR 0008](docs/decisions/0008-plans-run-in-the-browser.md)). The folder also holds the
fonts (`fonts/`, served with the site under the SIL Open Font License), the sharing
image (`og.png`), the touch icon and `404.html`, so serve it over HTTP rather than opening
`index.html` from disk. The `Pages`
workflow refreshes the AWS prices and publishes the site on every push to the default
branch and every Monday. With `--api-base` the page talks to a Clarchy server instead,
which needs `CLARCHY_CORS_ORIGINS` set.

The live site is served at **clarchy.com** from GitHub Pages: the domain's DNS points at
GitHub Pages (four `A` and four `AAAA` records for `clarchy.com`, and a `CNAME` from
`www` to `namratabhatia21.github.io`), and the custom domain is set in the repository's
Settings → Pages. The page uses only relative links, so the same build works on a custom
domain or under a `github.io` path.

**Hosting on Cloudflare.** A Cloudflare Worker named `clarchy` serves the built files as
static assets (`wrangler.jsonc`). `make prices site` builds them into `site/`. Deploy it
one of two ways, not both:

- **Cloudflare builds it (Workers Builds).** Connect the Worker to this repository
  (Worker → Settings → Build). Set the build command to `make prices site`, keep the
  deploy command `npx wrangler deploy`, and pick the branch the site is built from. Every
  push to that branch deploys.
- **GitHub builds it.** Create an API token with the *Workers Scripts: Edit* permission
  (the "Edit Cloudflare Workers" template), and add the repository secrets
  `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID`. The `Pages` workflow then deploys
  on every push and every Monday, with fresh AWS prices.

The site is then live at `clarchy.<your-subdomain>.workers.dev`. To move clarchy.com:

1. In the Worker's Settings → Domains & Routes, add the custom domains `clarchy.com` and
   `www.clarchy.com` (the domain must be on Cloudflare DNS; remove old records that
   point to GitHub).
2. Remove the custom domain from GitHub's Settings → Pages and set the repository variable
   `GITHUB_PAGES` to `off`, so only Cloudflare serves the site.

**Sign-ups, free diagrams and the Pro waitlist** ([ADR 0011](docs/decisions/0011-accounts-and-credits-on-the-edge.md)).
The Worker also answers `/api/*` from `worker/index.mjs`, with the D1 database `clarchy`
(binding `DB`, id in `wrangler.jsonc`). Everything fits Cloudflare's free plan. The free
allowance is `FREE_DIAGRAMS` in `wrangler.jsonc`.

- **See who signed up:** Cloudflare dashboard → Storage & Databases → D1 → `clarchy` →
  Console, then for example
  `SELECT created_at, name, company, email, updates_opt_in, plan, pro_requested_at FROM leads ORDER BY created_at DESC;`
  Only email people about product updates where `updates_opt_in = 1`.
- **Turn on Pro for someone:** `UPDATE leads SET plan = 'pro' WHERE email = 'name@company.com';`
- **Delete someone's data on request:** `DELETE FROM leads WHERE email = 'name@company.com';`
  (their usage rows go with it).
- **Download a CSV:** add a secret `ADMIN_TOKEN` (Worker → Settings → Variables and
  Secrets), then
  `curl -H "Authorization: Bearer <token>" https://clarchy.com/api/admin/leads.csv -o leads.csv`.
- **Change the schema:** add a numbered file to `worker/migrations/` and run
  `npx wrangler d1 migrations apply clarchy --remote`.
- **Run it locally:** `make site`, then `npx wrangler d1 migrations apply clarchy --local`
  and `npx wrangler dev`.

## Official provider icons

Clarchy never ships provider icons
([ADR 0002](docs/decisions/0002-no-bundled-provider-icons.md)); diagrams use lettered
badges coloured by service category. To use the official AWS set, download the
[AWS Architecture Icons](https://aws.amazon.com/architecture/icons/) package, read its
terms, and point Clarchy at it:

```bash
export CLARCHY_ICONS_AWS=~/Downloads/Asset-Package
clarchy icons --provider aws              # shows which icons were found
```

## Development

```bash
make check       # ruff + pytest (the agent is tested with a scripted model, no API key needed)
node --no-warnings --test "worker/*.test.mjs"   # the Worker API, against Node's built-in SQLite
make examples    # regenerate examples/, which double as golden test files
```

> **Review status:** no provider's mappings have been checked by a specialist yet. The UI
> and the explanations say so. Set `reviewed: true` in
> `src/clarchy/data/mappings/<provider>.yaml` once someone has.

## Roadmap

| Phase | What |
|---|---|
| ✅ 1 | Neutral spec, patterns, AWS/Azure/GCP/OSS mappings, SVG renderer, CLI, web UI and service catalog |
| ✅ 2 | Requirements documents in, agentic planning with MCP tools, build-and-deploy toolchain, workflows, provider-themed results |
| ✅ 3 | Cost estimates for 1 month to 3 years with commitments; AWS from the Price List API; plans in the browser; open-source models |
| 4 | Azure and Google Cloud prices from their price APIs; prices for the design's own region; low/expected/high ranges checked against the official calculators |
| 5 | Spot and data-transfer costs; Well-Architected checks; PDF report |
| 6+ | Open-source cost model including operations effort; specialist review of every mapping |

## Known limitations

- The AI agent has been tested with scripted models (Claude-style and OpenAI-style), not
  against live Claude or Hugging Face here; real-model quality depends on the model and
  the prompts in `planner/prompts.py`. Smaller open models follow tool calls less
  reliably; when they fail, the run falls back to the rule-based draft.
- Prices are for one reference region per cloud (US East, East US, Iowa); the cost view
  says so when your design is elsewhere. Azure and Google Cloud prices are approximate.
- Scanned PDFs without a text layer cannot be read; paste the text instead.
- Long edges in large diagrams can cross other lines; links to shared services
  (identity, secrets, monitoring) are listed in the explanation rather than drawn.

## Licence

Not chosen yet; until a licence is added, all rights are reserved.

AWS, Azure, Google Cloud and all service names are trademarks of their owners.
Clarchy is an independent project, not affiliated with or endorsed by any cloud
provider.
