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

| Stage | Component | Capability | Service | Fidelity | Why |
|---|---|---|---|---|---|
| Users | Employees (browser) | `client` | (outside the cloud) | - | _Generic: People or systems outside the cloud that use the application._ |
| Code | App and infrastructure code | `source-control` | GitLab Community Edition | exact | Every change starts as a reviewed commit; the same repository holds the application and its infrastructure code. |
| Code | Infrastructure as code | `iac` | OpenTofu | exact | Creates and updates the cloud resources from versioned templates, so every environment is reproducible. |
| Build | Build and test | `ci-build` | Jenkins | exact | Builds and tests each commit, then packages the services as container images and the functions as bundles. |
| Ship | Container images | `container-registry` | Harbor | exact | Keeps versioned, scanned images so every environment runs exactly what was tested. |
| Ship | Release pipeline | `cd-deploy` | Argo CD | exact | Promotes each build through test and production with approvals and rollback. |
| Serve | Web front end | `cdn` | Varnish Cache | partial | _Generic: Content delivery network that caches content close to users._ |
| Serve | HTTPS load balancer | `load-balancer` | HAProxy | close | _Generic: Distributes HTTP traffic across healthy compute instances._ |
| Run | Chat API (streaming) | `container-service` | Kubernetes | close | Streaming responses hold connections for many seconds, which suits containers better than short-lived functions. |
| Run | LLM + embeddings | `llm-inference` | vLLM (open-weight models) | close | Managed models avoid hosting GPUs; pay per token. |
| Run | Chunk + embed documents | `serverless-function` | Knative Serving | close | Runs only when documents change. |
| Store | Source documents | `object-storage` | Ceph Object Gateway | close | _Generic: Durable storage for files and blobs._ |
| Store | Embeddings index | `vector-search` | pgvector (PostgreSQL) | exact | Similarity search over document chunks; hybrid keyword + vector improves recall. |
| Store | Chat history | `key-value-db` | Apache Cassandra | close | _Generic: Serverless key-value / document database with single-digit ms reads._ |
| Operate | Single sign-on | `identity` | Keycloak | exact | _Generic: User sign-up, sign-in and tokens._ |
| Operate | Logs, traces, cost alarms | `monitoring` | Prometheus + Grafana | close | _Generic: Metrics, logs, dashboards and alarms._ |

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

- Chat API (streaming) → Keycloak: verify token

## Trade-offs and alternatives

- **Varnish Cache** (Web front end): alternatives: NGINX caching, Cloudflare; Caches at your own servers, not at a global edge network; a worldwide CDN is not practical to self-host.
- **HAProxy** (HTTPS load balancer): alternatives: NGINX, Envoy; Run at least two instances for availability and handle TLS certificates yourself.
- **Kubernetes** (Chat API (streaming)): alternatives: K3s, HashiCorp Nomad; You manage the cluster, nodes and upgrades; there is no per-second serverless billing.
- **vLLM (open-weight models)** (LLM + embeddings): alternatives: Ollama, Hugging Face TGI, OpenAI API, Anthropic API (Claude), Hugging Face Inference Endpoints; Needs GPUs you provision; limited to open-weight models.
- **Knative Serving** (Chunk + embed documents): alternatives: OpenFaaS; Scale-to-zero on your Kubernetes cluster; the cluster itself keeps running and costing money.
- **Ceph Object Gateway** (Source documents): alternatives: SeaweedFS, Garage, MinIO; S3-compatible API, but you operate durability, replication, capacity and upgrades.
- **pgvector (PostgreSQL)** (Embeddings index): alternatives: Qdrant, Milvus, OpenSearch
- **Apache Cassandra** (Chat history): alternatives: FerretDB; Scales well but needs careful data modelling and cluster operations.
- **Prometheus + Grafana** (Logs, traces, cost alarms): alternatives: OpenTelemetry Collector, Grafana Loki; You store and retain metrics and logs yourself.
- **GitLab Community Edition** (App and infrastructure code): alternatives: Forgejo, Gitea; You run, back up and upgrade the Git server yourself.
- **Jenkins** (Build and test): alternatives: Tekton, GitLab CI/CD, Woodpecker CI; Build agents and plugins are yours to operate.
- **Argo CD** (Release pipeline): alternatives: Flux; GitOps deployment to Kubernetes from the Git repository.
- **OpenTofu** (Infrastructure as code): alternatives: Pulumi, Crossplane

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

Open-source software has no licence fee: you pay for the machines it runs on and the people who operate it, which depends on where you host it. Open a cloud tab to see a managed-service estimate.

---
Estimates use list prices and the usage stated above; check them with the provider's calculator. Service names belong to their owners; Clarchy is not affiliated with any cloud provider.
