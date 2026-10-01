# CloudArchie

**Describe your app. Get the architecture.** Type your requirements or upload a Word, PDF
or Excel document. An agent turns them into a cloud-neutral spec and designs everything
the app needs, from source control, builds and container images to compute, autoscaling,
databases, storage and monitoring. It then shows the design on **AWS, Azure, Google Cloud
or open source**, each in its own look, and explains every choice.

**Live demo:** https://namratabhatia21.github.io/CloudArchie/ replays recorded planning
runs of four sample apps and includes every example and the full service catalog. To plan
your own app, [run it yourself](#run-it-yourself).

![Microservices on Kubernetes, on AWS](examples/kubernetes-microservices.aws.svg)

## What you get

| Page | What it does |
|---|---|
| **Plan** | Type or drop in a requirements document (.docx, .pdf, .xlsx, .md, .txt). Watch the pipeline work stage by stage, including the agent's tool calls, then explore the result: an architecture diagram per provider, every service grouped by lifecycle stage, step-by-step workflows that light up the diagram, and the editable YAML spec. |
| **Examples** | Six reference architectures (serverless web app, containerised API, event-driven processing, data pipeline, RAG chatbot, microservices on Kubernetes) on every provider. |
| **Services** | A catalog of every capability with the equivalent service on each provider side by side. Filter by lifecycle stage, provider and how close the match is, or search by any service name ("KEDA", "BigQuery", "Lambda"). |

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
3. **Design**: Claude works as an **agent**. It is an MCP client of CloudArchie's own
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

Without an API key the same pipeline runs with a **rule-based planner** that reads the
text with patterns, so the app always works offline. If the AI path fails part-way, the
run falls back to the rule-based draft and says so.

The model never draws the diagram or invents services. Layout is deterministic code, and
the model can only use capabilities from the catalog (see
[ADR 0004](docs/decisions/0004-agent-designs-with-mcp-tools.md)).

## Run it yourself

```bash
git clone https://github.com/namratabhatia21/CloudArchie && cd CloudArchie
python -m venv .venv && . .venv/bin/activate
pip install -e ".[all]"

cloudarchie serve                       # http://127.0.0.1:8000, rule-based planner
```

### Turn on the AI agent

```bash
export ANTHROPIC_API_KEY=sk-ant-...     # Claude API
cloudarchie serve                        # the top bar now shows the AI agent

# or Claude on Amazon Bedrock, with your usual AWS credentials
export CLOUDARCHIE_LLM=bedrock AWS_REGION=us-east-1
cloudarchie serve
```

| Variable | Meaning |
|---|---|
| `ANTHROPIC_API_KEY` | Enables the AI agent through the Claude API. |
| `CLOUDARCHIE_LLM` | `anthropic`, `bedrock` or `rules` (default: `anthropic` when an API key is set, otherwise `rules`). |
| `CLOUDARCHIE_MODEL` | Override the Claude model id (the default is in `src/cloudarchie/planner/llm.py`). |
| `AWS_REGION` | Region for Amazon Bedrock. |
| `CLOUDARCHIE_CORS_ORIGINS` | Comma-separated origins allowed to call the API, for a front end hosted elsewhere. |
| `CLOUDARCHIE_ICONS_AWS` (and `_AZURE`, `_GCP`) | Folder of a provider's official icon package; see below. |

### From the command line

```bash
cloudarchie plan requirements.docx              # AI agent if configured, otherwise rules
cloudarchie plan "A booking app for 40 clinics in the UK..." --rules -o plan/
cloudarchie plan brief.pdf --region eu-central --mcp "<command that starts an MCP server>"
```

`plan` writes `spec.yaml` plus a diagram (`.svg`) and an explanation (`.md`) for every
provider. `--mcp` attaches extra MCP servers (a pricing or documentation server, say)
whose tools the agent may also use.

Other commands: `patterns`, `validate <spec>`, `render <spec> --provider azure`,
`explain <spec>`, `export-site`, `mcp`. Run `cloudarchie --help` for details.

## Use CloudArchie from Claude

CloudArchie is an MCP server, so Claude Code, Claude Desktop or any MCP client can design
with it directly:

```bash
claude mcp add cloudarchie -- cloudarchie mcp                     # Claude Code
```

```json
{ "mcpServers": { "cloudarchie": { "command": "cloudarchie", "args": ["mcp"] } } }
```

(Claude Desktop: add that to `claude_desktop_config.json`, using the full path to
`cloudarchie` inside your virtual environment.)

| Tool | What it does |
|---|---|
| `list_capabilities`, `list_regions`, `list_patterns`, `get_pattern` | The vocabulary and the reference designs. |
| `search_services` | Equivalent services across providers for a capability or service name. |
| `validate_spec` | Errors to fix and warnings worth considering, against every provider. |
| `add_delivery_toolchain` | Adds CI/CD, registry, infrastructure as code and KEDA where needed. |
| `render_design` | SVG diagram and Markdown explanation on one provider. |
| `draft_architecture` | A rule-based first draft from requirements text. |

The server also offers each pattern as a resource (`cloudarchie://patterns/{id}`) and a
`design_architecture` prompt. For Claude Code there is an Agent Skill in
[skills/cloudarchie-architect](skills/cloudarchie-architect/SKILL.md) that walks through a
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
[`data/capabilities.yaml`](src/cloudarchie/data/capabilities.yaml); each provider's
services and diagram theme are in [`data/mappings/`](src/cloudarchie/data/mappings/).

## Code map

| Module | Role |
|---|---|
| `ingest.py` | Word, Excel, PDF and text to plain text, with limits |
| `planner/` | `pipeline.py` (stages and events), `agent.py` (Claude: understand, design loop, workflows), `toolbox.py` (MCP client), `rules.py` (offline planner), `llm.py` (Claude API or Bedrock), `prompts.py` |
| `tools.py`, `mcp_server.py` | The tool functions and the MCP server that exposes them |
| `delivery.py`, `workflows.py` | Deterministic build-and-deploy toolchain and generated workflows |
| `spec.py`, `catalog.py`, `mapping.py` | The neutral spec, its data and the provider mapping |
| `render.py`, `explain.py` | Themed SVG diagrams and Markdown explanations |
| `web.py`, `payloads.py`, `static/` | FastAPI app (with a server-sent events `/api/plan` stream) and a no-build front end |
| `export.py` | The static site for GitHub Pages |

Design decisions are recorded in [docs/decisions/](docs/decisions/).

## Static site

```bash
cloudarchie export-site -o site/                          # one self-contained index.html
cloudarchie export-site -o site/ --api-base https://...   # a front end for a hosted API
```

A static page cannot run the planner, so it embeds recorded rule-based runs of the samples
and replays them stage by stage, plus every example on every provider and the catalog
([ADR 0005](docs/decisions/0005-static-demo-replays-recorded-runs.md)). The `Pages`
workflow publishes it on every push to the default branch. With `--api-base` the page
talks to a CloudArchie server instead, which needs `CLOUDARCHIE_CORS_ORIGINS` set.

## Official provider icons

CloudArchie never ships provider icons
([ADR 0002](docs/decisions/0002-no-bundled-provider-icons.md)); diagrams use lettered
badges coloured by service category. To use the official AWS set, download the
[AWS Architecture Icons](https://aws.amazon.com/architecture/icons/) package, read its
terms, and point CloudArchie at it:

```bash
export CLOUDARCHIE_ICONS_AWS=~/Downloads/Asset-Package
cloudarchie icons --provider aws              # shows which icons were found
```

## Development

```bash
make check       # ruff + pytest (the agent is tested with a scripted model, no API key needed)
make examples    # regenerate examples/, which double as golden test files
```

> **Review status:** no provider's mappings have been checked by a specialist yet. The UI
> and the explanations say so. Set `reviewed: true` in
> `src/cloudarchie/data/mappings/<provider>.yaml` once someone has.

## Roadmap

| Phase | What |
|---|---|
| ✅ 1 | Neutral spec, patterns, AWS/Azure/GCP/OSS mappings, SVG renderer, CLI, web UI and service catalog |
| ✅ 2 | Requirements documents in, agentic planning with MCP tools, build-and-deploy toolchain, workflows, provider-themed results |
| 3 | AWS cost engine: Price List data, usage model, low/expected/high ranges, checked against the AWS Pricing Calculator |
| 4 | Savings Plans, Reserved Instances and Spot with break-even; Well-Architected checks; PDF report |
| 5 | Hosted backend on AWS so the public site can plan new documents |
| 6+ | Azure, Google Cloud and open-source pricing; specialist review of every mapping |

## Known limitations

- The AI agent has been tested with a scripted model; real-model quality depends on the
  prompts in `planner/prompts.py` and is worth reviewing on your own documents.
- Scanned PDFs without a text layer cannot be read; paste the text instead.
- Long edges in large diagrams can cross other lines; links to shared services
  (identity, secrets, monitoring) are listed in the explanation rather than drawn.
- Costs are not estimated yet (phase 3).

## Licence

Not chosen yet; until a licence is added, all rights are reserved.

AWS, Azure, Google Cloud and all service names are trademarks of their owners.
CloudArchie is an independent project, not affiliated with or endorsed by any cloud
provider.
