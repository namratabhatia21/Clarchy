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

| Stage | Component | Capability | Service | Fidelity | Why |
|---|---|---|---|---|---|
| Users | Employees (browser) | `client` | (outside the cloud) | - | _Generic: People or systems outside the cloud that use the application._ |
| Code | App and infrastructure code | `source-control` | Secure Source Manager | exact | Every change starts as a reviewed commit; the same repository holds the application and its infrastructure code. |
| Code | Infrastructure as code | `iac` | Infrastructure Manager (Terraform) | exact | Creates and updates the cloud resources from versioned templates, so every environment is reproducible. |
| Build | Build and test | `ci-build` | Cloud Build | exact | Builds and tests each commit, then packages the services as container images and the functions as bundles. |
| Ship | Container images | `container-registry` | Artifact Registry | exact | Keeps versioned, scanned images so every environment runs exactly what was tested. |
| Ship | Release pipeline | `cd-deploy` | Cloud Deploy | exact | Promotes each build through test and production with approvals and rollback. |
| Serve | Web front end | `cdn` | Cloud CDN | close | _Generic: Content delivery network that caches content close to users._ |
| Serve | HTTPS load balancer | `load-balancer` | Cloud Load Balancing (Application LB) | exact | _Generic: Distributes HTTP traffic across healthy compute instances._ |
| Run | Chat API (streaming) | `container-service` | Cloud Run | exact | Streaming responses hold connections for many seconds, which suits containers better than short-lived functions. |
| Run | LLM + embeddings | `llm-inference` | Vertex AI | exact | Managed models avoid hosting GPUs; pay per token. |
| Run | Chunk + embed documents | `serverless-function` | Cloud Run functions | exact | Runs only when documents change. |
| Store | Source documents | `object-storage` | Cloud Storage | exact | _Generic: Durable storage for files and blobs._ |
| Store | Embeddings index | `vector-search` | Vertex AI Vector Search | exact | Similarity search over document chunks; hybrid keyword + vector improves recall. |
| Store | Chat history | `key-value-db` | Firestore | close | _Generic: Serverless key-value / document database with single-digit ms reads._ |
| Operate | Single sign-on | `identity` | Identity Platform | exact | _Generic: User sign-up, sign-in and tokens._ |
| Operate | Logs, traces, cost alarms | `monitoring` | Cloud Monitoring + Cloud Logging | exact | _Generic: Metrics, logs, dashboards and alarms._ |

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

- Chat API (streaming) → Identity Platform: verify token

## Trade-offs and alternatives

- **Cloud CDN** (Web front end): alternatives: Media CDN; Cloud CDN is enabled on an external Application Load Balancer rather than deployed on its own.
- **Cloud Run** (Chat API (streaming)): alternatives: GKE Autopilot
- **Vertex AI Vector Search** (Embeddings index): alternatives: AlloyDB or Cloud SQL with pgvector
- **Firestore** (Chat history): alternatives: Bigtable; A document database with a different query and pricing model from DynamoDB; Bigtable suits very high-throughput wide-column data.
- **Identity Platform** (Single sign-on): alternatives: Firebase Authentication
- **Secure Source Manager** (App and infrastructure code): alternatives: GitHub or GitLab via Developer Connect
- **Infrastructure Manager (Terraform)** (Infrastructure as code): alternatives: Terraform or OpenTofu; A managed service that runs Terraform configurations.

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

About **$223 a month** on demand (Iowa (us-central1) list prices as of 2026-10-01; Google Cloud pricing pages, compiled manually, approximate).

| Period | On demand | With commitments |
|---|---:|---:|
| 1 month | $223 | – |
| 6 months | $1,342 | – |
| 1 year | $2,687 | $2,452 |
| 3 years | $8,105 | $7,398 |

| Service | Per month |
|---|---:|
| Cloud Run (Chat API (streaming)) | $116 |
| Vertex AI Vector Search (Embeddings index) | $68.47 |
| Cloud Load Balancing (Application LB) (HTTPS load balancer) | $18.88 |
| Vertex AI (LLM + embeddings) | $13.02 |
| Firestore (Chat history) | $2.85 |
| Cloud CDN (Web front end) | $2.05 |
| Cloud Storage (Source documents) | $1.04 |
| Cloud Monitoring + Cloud Logging (Logs, traces, cost alarms) | $1.00 |
| Artifact Registry (Container images) | $0.45 |
| Cloud Run functions (Chunk + embed documents) | $0.00 |
| Identity Platform (Single sign-on) | $0.00 |
| Cloud Build (Build and test) | $0.00 |
| Cloud Deploy (Release pipeline) | $0.00 |

- Cloud Run committed use discounts: 17% off for a 1- or 3-year spend commitment.
- Usage comes from each component's sizing and the requirements; edit it in the Spec tab.
- 730 hours a month. Always-free allowances are deducted where shown; trials are not.
- Excludes tax, support plans, and data transfer not listed.
- Prices are for Iowa (us-central1); your region (Oregon (us-west1)) may differ.

---
Estimates use list prices and the usage stated above; check them with the provider's calculator. Service names belong to their owners; Clarchy is not affiliated with any cloud provider.
