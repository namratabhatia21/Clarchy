# AI agent platform on Azure

Tool-using AI agents behind a chat API, with an LLM gateway for model routing and budgets, retrieval over company documents, and tracing of every model call.

> Azure mappings have not yet been reviewed by a specialist. Check the service choices before relying on them.

## Requirements

- **Region:** Virginia (eastus)
- **Monthly active users:** 5000
- **Peak requests/second:** 10
- **Data stored (GB):** 100
- **Data growth (GB/month):** 5
- **Availability target:** 99.9%
- **Compliance:** none stated

## Services

| Stage | Component | Capability | Service | Fidelity | Why |
|---|---|---|---|---|---|
| Users | Employees (browser) | `client` | (outside the cloud) | - | _Generic: People or systems outside the cloud that use the application._ |
| Code | App and infrastructure code | `source-control` | Azure Repos | exact | Every change starts as a reviewed commit; the same repository holds the application, the agent graphs and the infrastructure code. |
| Code | Infrastructure as code | `iac` | Bicep | exact | Creates and updates the cloud resources from versioned templates, so every environment is reproducible. |
| Build | Build, test and evaluate | `ci-build` | Azure Pipelines | exact | Builds and tests each commit and runs the agent's evaluation set, then packages the services as container images and the functions as bundles. |
| Ship | Container images | `container-registry` | Azure Container Registry | exact | Keeps versioned, scanned images so every environment runs exactly what was tested. |
| Ship | Release pipeline | `cd-deploy` | Azure Pipelines (release stages) | exact | Promotes each build through test and production with approvals and rollback. |
| Serve | Web front end | `cdn` | Azure Front Door | exact | _Generic: Content delivery network that caches content close to users._ |
| Serve | HTTPS load balancer | `load-balancer` | Azure Application Gateway | exact | _Generic: Distributes HTTP traffic across healthy compute instances._ |
| Run | Chat API (streaming) | `container-service` | Azure Container Apps | exact | Streams agent progress and answers over long-lived connections, which suits containers better than short-lived functions. |
| Run | Agent runtime (LangGraph) | `agent-orchestration` | Foundry Agent Service | close | Runs LangGraph agents that plan, call tools and checkpoint their state, so long tasks survive restarts and can pause for a human to approve. |
| Run | Tool functions | `serverless-function` | Azure Functions | exact | Small functions the agent calls as tools, such as looking up a record or opening a ticket, each with least-privilege access to one system. |
| Run | Models + embeddings | `llm-inference` | Azure AI Foundry (incl. Azure OpenAI) | exact | Managed models behind the gateway; a larger model plans and a smaller one handles routine steps, billed per token. |
| Run | Chunk + embed documents | `serverless-function` | Azure Functions | exact | Runs only when documents change. |
| Integrate | LLM gateway (LiteLLM) | `llm-gateway` | Azure API Management (AI gateway) | close | One OpenAI-compatible API in front of every model, with per-team keys and budgets, fallbacks between providers and response caching. |
| Integrate | AI guardrails | `ai-guardrails` | Azure AI Content Safety (Prompt Shields) | exact | Screens prompts, tool results and answers for prompt injection, harmful content and personal data. |
| Store | Source documents | `object-storage` | Azure Blob Storage | exact | _Generic: Durable storage for files and blobs._ |
| Store | Knowledge index | `vector-search` | Azure AI Search | close | Lets the agent ground its answers in company documents with hybrid keyword and vector search. |
| Store | Agent state + history | `relational-db` | Azure Database for PostgreSQL (Flexible Server) | exact | Postgres holds the agent checkpoints, chat history and the gateway's spend log in one managed database. |
| Operate | Single sign-on | `identity` | Microsoft Entra External ID | exact | _Generic: User sign-up, sign-in and tokens._ |
| Operate | Model and tool credentials | `secrets` | Azure Key Vault | exact | _Generic: Stores and rotates credentials._ |
| Operate | LLM tracing (Langfuse) | `llm-observability` | Application Insights (Foundry tracing) | close | Traces every prompt, tool call, token and cost, and scores samples with evals, so regressions show up before users notice them. |
| Operate | Cloud access governance | `access-governance` | Microsoft Entra ID + Privileged Identity Management | exact | Staff sign in to the cloud with the company directory; the cloud architects approve least-privilege roles, and access is reviewed every quarter. |
| Operate | Audit trail | `audit-logging` | Azure Monitor activity log + Log Analytics | exact | Records every console change, data access and model call in a log nobody can edit. |
| Operate | Encryption keys | `key-management` | Azure Key Vault (keys) | exact | Customer-managed keys encrypt the database, documents and backups. |
| Operate | Logs, metrics, alarms | `monitoring` | Azure Monitor + Application Insights | exact | _Generic: Metrics, logs, dashboards and alarms._ |

## Workflows

### Serving a request

1. Employees (browser) → Web front end: load the app through the CDN (HTTPS)
2. Web front end → HTTPS load balancer: forward API calls
3. HTTPS load balancer → Chat API (streaming): run the business logic
4. Chat API (streaming) → Agent runtime (LangGraph): hand the request to the agent
5. Chat API (streaming) → Single sign-on: verify the user's sign-in token
6. Agent runtime (LangGraph) → LLM gateway (LiteLLM): send the prompt through the gateway
7. Agent runtime (LangGraph) → Knowledge index: retrieve relevant passages
8. Agent runtime (LangGraph) → Tool functions: call tools that look up or change data
9. Agent runtime (LangGraph) → Agent state + history: save the agent's progress and the conversation
10. Agent runtime (LangGraph) → Model and tool credentials: fetch credentials
11. Agent runtime (LangGraph) → AI guardrails: screen the prompt and the answer
12. LLM gateway (LiteLLM) → Models + embeddings: call the chosen model, falling back to another if it fails
13. Every model call → LLM tracing (Langfuse): record the prompt, tool calls, tokens and cost
14. Every component → Logs, metrics, alarms: send logs and metrics

### Background processing

1. Source documents → Chunk + embed documents: start when a document is uploaded
2. Chunk + embed documents → LLM gateway (LiteLLM): create embeddings
3. Chunk + embed documents → Knowledge index: index the new chunks

### Shipping a change

1. A developer → App and infrastructure code: push a reviewed change
2. App and infrastructure code → Build, test and evaluate: start a build on every push
3. Build, test and evaluate → Container images: publish the tested image
4. Container images → Release pipeline: start the release
5. Release pipeline → Infrastructure as code: apply infrastructure changes
6. Release pipeline → Chat API (streaming), Agent runtime (LangGraph), Tool functions, LLM gateway (LiteLLM), Chunk + embed documents: roll out the new version

## Shared services used

- Chat API (streaming) → Microsoft Entra External ID: verify token
- Agent runtime (LangGraph) → Azure Key Vault

## Trade-offs and alternatives

- **Azure Front Door** (Web front end): alternatives: Cloudflare; Front Door combines CDN, global HTTP load balancing and an optional WAF in one service.
- **Azure Container Apps** (Chat API (streaming)): alternatives: Azure Kubernetes Service
- **Foundry Agent Service** (Agent runtime (LangGraph)): alternatives: LangGraph on Azure Container Apps, Semantic Kernel; Managed agents with threads, tools and evaluations in Microsoft Foundry; LangGraph agents can run as hosted agents or on Container Apps.
- **Azure API Management (AI gateway)** (LLM gateway (LiteLLM)): alternatives: LiteLLM on Azure Container Apps; Gateway policies for Azure OpenAI and other models, such as token limits, load balancing across deployments, semantic caching and token metrics. Teams that also call non-Azure models often run LiteLLM instead.
- **Azure AI Foundry (incl. Azure OpenAI)** (Models + embeddings): alternatives: OpenAI API, Anthropic API (Claude), Hugging Face Inference Endpoints
- **Azure AI Search** (Knowledge index): alternatives: Cosmos DB vector search, PostgreSQL with pgvector; Vector search is one feature of a full search service; small workloads may be cheaper in the database.
- **Application Insights (Foundry tracing)** (LLM tracing (Langfuse)): alternatives: Langfuse on Azure; OpenTelemetry traces of agent runs and model calls, viewed in Foundry next to its evaluations.
- **Azure AI Content Safety (Prompt Shields)** (AI guardrails): alternatives: NeMo Guardrails; Harm categories, prompt-injection shields and groundedness checks; Azure OpenAI deployments also apply default content filters.
- **Microsoft Entra ID + Privileged Identity Management** (Cloud access governance): alternatives: Azure Policy, Management groups; Just-in-time role activation with approval and access reviews need Entra ID P2 licences for the people who use them.
- **Azure Monitor activity log + Log Analytics** (Audit trail): alternatives: Microsoft Sentinel; The activity log is kept 90 days for free; longer retention goes to a Log Analytics workspace or storage.
- **Azure Key Vault (keys)** (Encryption keys): alternatives: Azure Managed HSM
- **Azure Repos** (App and infrastructure code): alternatives: GitHub
- **Azure Pipelines** (Build, test and evaluate): alternatives: GitHub Actions
- **Azure Pipelines (release stages)** (Release pipeline): alternatives: GitHub Actions environments; The same Azure Pipelines definition usually builds and deploys.
- **Bicep** (Infrastructure as code): alternatives: ARM templates, Terraform or OpenTofu

## Sizing assumptions

- **Web front end:** egress_gb_per_month=30
- **Chat API (streaming):** vcpu=1, memory_gb=2, tasks=2
- **Agent runtime (LangGraph):** requests_per_month=150000
- **Tool functions:** invocations_per_month=400000, avg_duration_ms=300, memory_mb=512
- **LLM gateway (LiteLLM):** vcpu=0.5, memory_gb=1, tasks=2
- **Models + embeddings:** requests_per_month=450000
- **Source documents:** storage_gb=100
- **Chunk + embed documents:** invocations_per_month=50000, avg_duration_ms=3000, memory_mb=1024
- **Agent state + history:** storage_gb=50
- **Single sign-on:** monthly_active_users=5000
- **LLM tracing (Langfuse):** requests_per_month=150000
- **Logs, metrics, alarms:** log_ingest_gb_per_month=20

## Estimated cost

About **$1,572 a month** on demand (East US list prices as of 2026-10-01; Azure pricing pages, compiled manually, approximate).

| Period | On demand | With commitments |
|---|---:|---:|
| 1 month | $1,572 | – |
| 6 months | $9,434 | – |
| 1 year | $18,871 | $18,588 |
| 3 years | $56,654 | $55,689 |

| Service | Per month |
|---|---:|
| Azure AI Content Safety (Prompt Shields) (AI guardrails) | $513 |
| Azure AI Foundry (incl. Azure OpenAI) (Models + embeddings) | $210 |
| Azure Application Gateway (HTTPS load balancer) | $185 |
| Azure Container Apps (Chat API (streaming)) | $158 |
| Azure API Management (AI gateway) (LLM gateway (LiteLLM)) | $150 |
| Azure Database for PostgreSQL (Flexible Server) (Agent state + history) | $132 |
| Azure AI Search (Knowledge index) | $73.73 |
| Microsoft Entra ID + Privileged Identity Management (Cloud access governance) | $45.00 |
| Azure Front Door (Web front end) | $38.84 |
| Azure Monitor + Application Insights (Logs, metrics, alarms) | $35.50 |
| Azure Key Vault (keys) (Encryption keys) | $9.73 |
| Application Insights (Foundry tracing) (LLM tracing (Langfuse)) | $8.62 |
| Azure Monitor activity log + Log Analytics (Audit trail) | $5.44 |
| Azure Container Registry (Container images) | $5.00 |
| Azure Blob Storage (Source documents) | $1.88 |
| Azure Key Vault (Model and tool credentials) | $0.24 |
| Azure Functions (Tool functions) | $0.00 |
| Azure Functions (Chunk + embed documents) | $0.00 |
| Microsoft Entra External ID (Single sign-on) | $0.00 |
| Azure Pipelines (Build, test and evaluate) | $0.00 |

- Azure savings plan for compute: 1- or 3-year hourly spend commitment; about 15% (1 year) or 17% (3 years) off Container Apps.
- Usage comes from each component's sizing and the requirements; edit it in the Spec tab.
- 730 hours a month. Always-free allowances are deducted where shown; trials are not.
- Excludes tax, support plans, and data transfer not listed.

---
Estimates use list prices and the usage stated above; check them with the provider's calculator. Service names belong to their owners; Clarchy is not affiliated with any cloud provider.
