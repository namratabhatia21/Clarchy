# RAG chatbot on Azure

Chat assistant that answers from your own documents using retrieval-augmented generation with a managed LLM.

> Azure mappings have not yet been reviewed by a specialist. Check the service choices before relying on them.

## Requirements

- **Region:** Washington (westus2)
- **Monthly active users:** 2000
- **Peak requests/second:** 5
- **Data stored (GB):** 50
- **Data growth (GB/month):** 5
- **Availability target:** 99.9%
- **Compliance:** none stated

## Services

| Stage | Component | Capability | Service | Fidelity | Why |
|---|---|---|---|---|---|
| Users | Employees (browser) | `client` | (outside the cloud) | - | _Generic: People or systems outside the cloud that use the application._ |
| Code | App and infrastructure code | `source-control` | Azure Repos | exact | Every change starts as a reviewed commit; the same repository holds the application and its infrastructure code. |
| Code | Infrastructure as code | `iac` | Bicep | exact | Creates and updates the cloud resources from versioned templates, so every environment is reproducible. |
| Build | Build and test | `ci-build` | Azure Pipelines | exact | Builds and tests each commit, then packages the services as container images and the functions as bundles. |
| Ship | Container images | `container-registry` | Azure Container Registry | exact | Keeps versioned, scanned images so every environment runs exactly what was tested. |
| Ship | Release pipeline | `cd-deploy` | Azure Pipelines (release stages) | exact | Promotes each build through test and production with approvals and rollback. |
| Serve | Web front end | `cdn` | Azure Front Door | exact | _Generic: Content delivery network that caches content close to users._ |
| Serve | HTTPS load balancer | `load-balancer` | Azure Application Gateway | exact | _Generic: Distributes HTTP traffic across healthy compute instances._ |
| Run | Chat API (streaming) | `container-service` | Azure Container Apps | exact | Streaming responses hold connections for many seconds, which suits containers better than short-lived functions. |
| Run | LLM + embeddings | `llm-inference` | Azure AI Foundry (incl. Azure OpenAI) | exact | Managed models avoid hosting GPUs; pay per token. |
| Run | Chunk + embed documents | `serverless-function` | Azure Functions | exact | Runs only when documents change. |
| Store | Source documents | `object-storage` | Azure Blob Storage | exact | _Generic: Durable storage for files and blobs._ |
| Store | Embeddings index | `vector-search` | Azure AI Search | close | Similarity search over document chunks; hybrid keyword + vector improves recall. |
| Store | Chat history | `key-value-db` | Azure Cosmos DB | exact | _Generic: Serverless key-value / document database with single-digit ms reads._ |
| Operate | Single sign-on | `identity` | Microsoft Entra External ID | exact | _Generic: User sign-up, sign-in and tokens._ |
| Operate | Logs, traces, cost alarms | `monitoring` | Azure Monitor + Application Insights | exact | _Generic: Metrics, logs, dashboards and alarms._ |

## Workflows

### Serving a request

1. Employees (browser) → Web front end: load the app through the CDN (HTTPS)
2. Web front end → HTTPS load balancer: forward API calls
3. HTTPS load balancer → Chat API (streaming): run the business logic
4. Chat API (streaming) → Embeddings index: retrieve relevant passages
5. Chat API (streaming) → LLM + embeddings: generate the answer
6. Chat API (streaming) → Chat history: read and write items
7. Chat API (streaming) → Single sign-on: verify the user's sign-in token
8. Every component → Logs, traces, cost alarms: send logs and metrics

### Background processing

1. Source documents → Chunk + embed documents: start when a document is uploaded
2. Chunk + embed documents → LLM + embeddings: create embeddings
3. Chunk + embed documents → Embeddings index: index the new chunks

### Shipping a change

1. A developer → App and infrastructure code: push a reviewed change
2. App and infrastructure code → Build and test: start a build on every push
3. Build and test → Container images: publish the tested image
4. Container images → Release pipeline: start the release
5. Release pipeline → Infrastructure as code: apply infrastructure changes
6. Release pipeline → Chat API (streaming), Chunk + embed documents: roll out the new version

## Shared services used

- Chat API (streaming) → Microsoft Entra External ID: verify token

## Trade-offs and alternatives

- **Azure Front Door** (Web front end): alternatives: Cloudflare; Front Door combines CDN, global HTTP load balancing and an optional WAF in one service.
- **Azure Container Apps** (Chat API (streaming)): alternatives: Azure Kubernetes Service
- **Azure AI Foundry (incl. Azure OpenAI)** (LLM + embeddings): alternatives: OpenAI API, Anthropic API (Claude), Hugging Face Inference Endpoints
- **Azure AI Search** (Embeddings index): alternatives: Cosmos DB vector search, PostgreSQL with pgvector; Vector search is one feature of a full search service; small workloads may be cheaper in the database.
- **Azure Cosmos DB** (Chat history): alternatives: Azure Table Storage
- **Azure Repos** (App and infrastructure code): alternatives: GitHub
- **Azure Pipelines** (Build and test): alternatives: GitHub Actions
- **Azure Pipelines (release stages)** (Release pipeline): alternatives: GitHub Actions environments; The same Azure Pipelines definition usually builds and deploys.
- **Bicep** (Infrastructure as code): alternatives: ARM templates, Terraform or OpenTofu

## Sizing assumptions

- **Web front end:** egress_gb_per_month=20
- **Chat API (streaming):** vcpu=1, memory_gb=2, tasks=2, hours_per_month=730
- **LLM + embeddings:** input_tokens_per_month=60000000, output_tokens_per_month=8000000, embedding_tokens_per_month=20000000
- **Chunk + embed documents:** invocations_per_month=50000, avg_duration_ms=3000, memory_mb=1024
- **Source documents:** storage_gb=50
- **Embeddings index:** vectors=2000000, dimensions=1024
- **Chat history:** storage_gb=10, reads_per_month=2000000, writes_per_month=1000000
- **Single sign-on:** monthly_active_users=2000
- **Logs, traces, cost alarms:** log_ingest_gb_per_month=15

## Estimated cost

About **$537 a month** on demand (West US 2 list prices as of 2026-10-02; Azure Retail Prices API).

| Period | On demand | With commitments |
|---|---:|---:|
| 1 month | $537 | – |
| 6 months | $3,220 | – |
| 1 year | $6,444 | $6,047 |
| 3 years | $19,373 | $18,022 |

| Service | Per month |
|---|---:|
| Azure Container Apps (Chat API (streaming)) | $221 |
| Azure Application Gateway (HTTPS load balancer) | $152 |
| Azure AI Search (Embeddings index) | $73.73 |
| Azure Front Door (Web front end) | $37.19 |
| Azure Monitor + Application Insights (Logs, traces, cost alarms) | $24.00 |
| Azure AI Foundry (incl. Azure OpenAI) (LLM + embeddings) | $18.72 |
| Azure Container Registry (Container images) | $5.07 |
| Azure Cosmos DB (Chat history) | $4.25 |
| Azure Blob Storage (Source documents) | $0.96 |
| Azure Functions (Chunk + embed documents) | $0.00 |
| Microsoft Entra External ID (Single sign-on) | $0.00 |
| Azure Pipelines (Build and test) | $0.00 |

- Azure savings plan for compute: 1- or 3-year hourly spend commitment; about 15% (1 year) or 17% (3 years) off Container Apps.
- Usage comes from each component's sizing and the requirements; edit it in the Spec tab.
- 730 hours a month. Always-free allowances are deducted where shown; trials are not.
- Excludes tax, support plans, and data transfer not listed.
- Azure AI Foundry (incl. Azure OpenAI) has no list price in West US 2, so it is priced at East US rates.

---
Estimates use list prices and the usage stated above; check them with the provider's calculator. Service names belong to their owners; Clarchy is not affiliated with any cloud provider.
