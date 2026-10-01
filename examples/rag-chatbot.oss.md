# RAG chatbot on Open source

Chat assistant that answers from your own documents using retrieval-augmented generation with a managed LLM.

> Open source mappings have not yet been reviewed by a specialist. Check the service choices before relying on them.

## Requirements

- **Region:** US West
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
| Web front end | `cdn` | Varnish Cache | partial | _Generic: Content delivery network that caches content close to users._ |
| HTTPS load balancer | `load-balancer` | HAProxy | close | _Generic: Distributes HTTP traffic across healthy compute instances._ |
| Chat API (streaming) | `container-service` | Kubernetes | close | Streaming responses hold connections for many seconds, which suits containers better than short-lived functions. |
| LLM + embeddings | `llm-inference` | vLLM (open-weight models) | close | Managed models avoid hosting GPUs; pay per token. |
| Chunk + embed documents | `serverless-function` | Knative Serving | close | Runs only when documents change. |
| Source documents | `object-storage` | Ceph Object Gateway | close | _Generic: Durable storage for files and blobs._ |
| Embeddings index | `vector-search` | pgvector (PostgreSQL) | exact | Similarity search over document chunks; hybrid keyword + vector improves recall. |
| Chat history | `key-value-db` | Apache Cassandra | close | _Generic: Serverless key-value / document database with single-digit ms reads._ |
| Single sign-on | `identity` | Keycloak | exact | _Generic: User sign-up, sign-in and tokens._ |
| Logs, traces, cost alarms | `monitoring` | Prometheus + Grafana | close | _Generic: Metrics, logs, dashboards and alarms._ |

## Shared services used

- Chat API (streaming) → Keycloak: verify token

## Trade-offs and alternatives

- **Varnish Cache** (Web front end): alternatives: NGINX caching; Caches at your own servers, not at a global edge network; a worldwide CDN is not practical to self-host.
- **HAProxy** (HTTPS load balancer): alternatives: NGINX, Envoy; Run at least two instances for availability and handle TLS certificates yourself.
- **Kubernetes** (Chat API (streaming)): alternatives: K3s, HashiCorp Nomad; You manage the cluster, nodes and upgrades; there is no per-second serverless billing.
- **vLLM (open-weight models)** (LLM + embeddings): alternatives: Ollama, Hugging Face TGI; Needs GPUs you provision; limited to open-weight models.
- **Knative Serving** (Chunk + embed documents): alternatives: OpenFaaS; Scale-to-zero on your Kubernetes cluster; the cluster itself keeps running and costing money.
- **Ceph Object Gateway** (Source documents): alternatives: SeaweedFS, Garage, MinIO; S3-compatible API, but you operate durability, replication, capacity and upgrades.
- **pgvector (PostgreSQL)** (Embeddings index): alternatives: Qdrant, Milvus, OpenSearch
- **Apache Cassandra** (Chat history): alternatives: FerretDB; Scales well but needs careful data modelling and cluster operations.
- **Prometheus + Grafana** (Logs, traces, cost alarms): alternatives: OpenTelemetry Collector, Grafana Loki; You store and retain metrics and logs yourself.

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
