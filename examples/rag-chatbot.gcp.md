# RAG chatbot on Google Cloud

Chat assistant that answers from your own documents using retrieval-augmented generation with a managed LLM.

> Google Cloud mappings have not yet been reviewed by a specialist. Check the service choices before relying on them.

## Requirements

- **Region:** Oregon (us-west1)
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
| Web front end | `cdn` | Cloud CDN | close | _Generic: Content delivery network that caches content close to users._ |
| HTTPS load balancer | `load-balancer` | Cloud Load Balancing (Application LB) | exact | _Generic: Distributes HTTP traffic across healthy compute instances._ |
| Chat API (streaming) | `container-service` | Cloud Run | exact | Streaming responses hold connections for many seconds, which suits containers better than short-lived functions. |
| LLM + embeddings | `llm-inference` | Vertex AI | exact | Managed models avoid hosting GPUs; pay per token. |
| Chunk + embed documents | `serverless-function` | Cloud Run functions | exact | Runs only when documents change. |
| Source documents | `object-storage` | Cloud Storage | exact | _Generic: Durable storage for files and blobs._ |
| Embeddings index | `vector-search` | Vertex AI Vector Search | exact | Similarity search over document chunks; hybrid keyword + vector improves recall. |
| Chat history | `key-value-db` | Firestore | close | _Generic: Serverless key-value / document database with single-digit ms reads._ |
| Single sign-on | `identity` | Identity Platform | exact | _Generic: User sign-up, sign-in and tokens._ |
| Logs, traces, cost alarms | `monitoring` | Cloud Monitoring + Cloud Logging | exact | _Generic: Metrics, logs, dashboards and alarms._ |

## Shared services used

- Chat API (streaming) → Identity Platform: verify token

## Trade-offs and alternatives

- **Cloud CDN** (Web front end): alternatives: Media CDN; Cloud CDN is enabled on an external Application Load Balancer rather than deployed on its own.
- **Cloud Run** (Chat API (streaming)): alternatives: GKE Autopilot
- **Vertex AI Vector Search** (Embeddings index): alternatives: AlloyDB or Cloud SQL with pgvector
- **Firestore** (Chat history): alternatives: Bigtable; A document database with a different query and pricing model from DynamoDB; Bigtable suits very high-throughput wide-column data.
- **Identity Platform** (Single sign-on): alternatives: Firebase Authentication

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
