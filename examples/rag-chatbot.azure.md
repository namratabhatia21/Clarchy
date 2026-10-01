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

| Component | Capability | Service | Fidelity | Why |
|---|---|---|---|---|
| Employees (browser) | `client` | (outside the cloud) | - | _Generic: People or systems outside the cloud that use the application._ |
| Web front end | `cdn` | Azure Front Door | exact | _Generic: Content delivery network that caches content close to users._ |
| HTTPS load balancer | `load-balancer` | Azure Application Gateway | exact | _Generic: Distributes HTTP traffic across healthy compute instances._ |
| Chat API (streaming) | `container-service` | Azure Container Apps | exact | Streaming responses hold connections for many seconds, which suits containers better than short-lived functions. |
| LLM + embeddings | `llm-inference` | Azure AI Foundry (incl. Azure OpenAI) | exact | Managed models avoid hosting GPUs; pay per token. |
| Chunk + embed documents | `serverless-function` | Azure Functions | exact | Runs only when documents change. |
| Source documents | `object-storage` | Azure Blob Storage | exact | _Generic: Durable storage for files and blobs._ |
| Embeddings index | `vector-search` | Azure AI Search | close | Similarity search over document chunks; hybrid keyword + vector improves recall. |
| Chat history | `key-value-db` | Azure Cosmos DB | exact | _Generic: Serverless key-value / document database with single-digit ms reads._ |
| Single sign-on | `identity` | Microsoft Entra External ID | exact | _Generic: User sign-up, sign-in and tokens._ |
| Logs, traces, cost alarms | `monitoring` | Azure Monitor + Application Insights | exact | _Generic: Metrics, logs, dashboards and alarms._ |

## Shared services used

- Chat API (streaming) → Microsoft Entra External ID: verify token

## Trade-offs and alternatives

- **Azure Front Door** (Web front end): Front Door combines CDN, global HTTP load balancing and an optional WAF in one service.
- **Azure Container Apps** (Chat API (streaming)): alternatives: Azure Kubernetes Service
- **Azure AI Search** (Embeddings index): alternatives: Cosmos DB vector search, PostgreSQL with pgvector; Vector search is one feature of a full search service; small workloads may be cheaper in the database.
- **Azure Cosmos DB** (Chat history): alternatives: Azure Table Storage

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

---
Cost estimates arrive in a later phase. Service names belong to their owners; CloudArchie is not affiliated with any cloud provider.
