# AI agent platform on Google Cloud

Tool-using AI agents behind a chat API, with an LLM gateway for model routing and budgets, retrieval over company documents, and tracing of every model call.

> Google Cloud mappings have not yet been reviewed by a specialist. Check the service choices before relying on them.

## Requirements

- **Region:** N. Virginia (us-east4)
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
| Code | App and infrastructure code | `source-control` | Secure Source Manager | exact | Every change starts as a reviewed commit; the same repository holds the application, the agent graphs and the infrastructure code. |
| Code | Infrastructure as code | `iac` | Infrastructure Manager (Terraform) | exact | Creates and updates the cloud resources from versioned templates, so every environment is reproducible. |
| Build | Build, test and evaluate | `ci-build` | Cloud Build | exact | Builds and tests each commit and runs the agent's evaluation set, then packages the services as container images and the functions as bundles. |
| Ship | Container images | `container-registry` | Artifact Registry | exact | Keeps versioned, scanned images so every environment runs exactly what was tested. |
| Ship | Release pipeline | `cd-deploy` | Cloud Deploy | exact | Promotes each build through test and production with approvals and rollback. |
| Serve | Web front end | `cdn` | Cloud CDN | close | _Generic: Content delivery network that caches content close to users._ |
| Serve | HTTPS load balancer | `load-balancer` | Cloud Load Balancing (Application LB) | exact | _Generic: Distributes HTTP traffic across healthy compute instances._ |
| Run | Chat API (streaming) | `container-service` | Cloud Run | exact | Streams agent progress and answers over long-lived connections, which suits containers better than short-lived functions. |
| Run | Agent runtime (LangGraph) | `agent-orchestration` | Vertex AI Agent Engine | close | Runs LangGraph agents that plan, call tools and checkpoint their state, so long tasks survive restarts and can pause for a human to approve. |
| Run | Tool functions | `serverless-function` | Cloud Run functions | exact | Small functions the agent calls as tools, such as looking up a record or opening a ticket, each with least-privilege access to one system. |
| Run | Models + embeddings | `llm-inference` | Vertex AI | exact | Managed models behind the gateway; a larger model plans and a smaller one handles routine steps, billed per token. |
| Run | Chunk + embed documents | `serverless-function` | Cloud Run functions | exact | Runs only when documents change. |
| Integrate | LLM gateway (LiteLLM) | `llm-gateway` | LiteLLM on Cloud Run | close | One OpenAI-compatible API in front of every model, with per-team keys and budgets, fallbacks between providers and response caching. |
| Integrate | AI guardrails | `ai-guardrails` | Model Armor | exact | Screens prompts, tool results and answers for prompt injection, harmful content and personal data. |
| Store | Source documents | `object-storage` | Cloud Storage | exact | _Generic: Durable storage for files and blobs._ |
| Store | Knowledge index | `vector-search` | Vertex AI Vector Search | exact | Lets the agent ground its answers in company documents with hybrid keyword and vector search. |
| Store | Agent state + history | `relational-db` | Cloud SQL for PostgreSQL | exact | Postgres holds the agent checkpoints, chat history and the gateway's spend log in one managed database. |
| Operate | Single sign-on | `identity` | Identity Platform | exact | _Generic: User sign-up, sign-in and tokens._ |
| Operate | Model and tool credentials | `secrets` | Secret Manager | exact | _Generic: Stores and rotates credentials._ |
| Operate | LLM tracing (Langfuse) | `llm-observability` | Cloud Trace (Vertex AI agent tracing) | partial | Traces every prompt, tool call, token and cost, and scores samples with evals, so regressions show up before users notice them. |
| Operate | Cloud access governance | `access-governance` | Cloud IAM + Privileged Access Manager | exact | Staff sign in to the cloud with the company directory; the cloud architects approve least-privilege roles, and access is reviewed every quarter. |
| Operate | Audit trail | `audit-logging` | Cloud Audit Logs | exact | Records every console change, data access and model call in a log nobody can edit. |
| Operate | Encryption keys | `key-management` | Cloud KMS | exact | Customer-managed keys encrypt the database, documents and backups. |
| Operate | Logs, metrics, alarms | `monitoring` | Cloud Monitoring + Cloud Logging | exact | _Generic: Metrics, logs, dashboards and alarms._ |

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

- Chat API (streaming) → Identity Platform: verify token
- Agent runtime (LangGraph) → Secret Manager

## Trade-offs and alternatives

- **Cloud CDN** (Web front end): alternatives: Media CDN, Cloudflare; Cloud CDN is enabled on an external Application Load Balancer rather than deployed on its own.
- **Cloud Run** (Chat API (streaming)): alternatives: GKE Autopilot
- **Vertex AI Agent Engine** (Agent runtime (LangGraph)): alternatives: LangGraph on Cloud Run, Agent Development Kit; Deploys LangGraph, LangChain and ADK agents with managed sessions and memory, billed for the compute the agents use.
- **LiteLLM on Cloud Run** (LLM gateway (LiteLLM)): alternatives: Apigee (AI gateway policies); Google Cloud has no lightweight managed LLM gateway; Apigee adds token quotas and model routing at enterprise scale.
- **Vertex AI** (Models + embeddings): alternatives: OpenAI API, Anthropic API (Claude), Hugging Face Inference Endpoints
- **Vertex AI Vector Search** (Knowledge index): alternatives: AlloyDB or Cloud SQL with pgvector
- **Cloud SQL for PostgreSQL** (Agent state + history): alternatives: AlloyDB for PostgreSQL
- **Identity Platform** (Single sign-on): alternatives: Firebase Authentication
- **Cloud Trace (Vertex AI agent tracing)** (LLM tracing (Langfuse)): alternatives: Langfuse on Cloud Run; OpenTelemetry traces of agent steps and model calls; prompt management and evaluations are separate (Vertex AI evaluation service).
- **Model Armor** (AI guardrails): alternatives: Vertex AI safety filters, NeMo Guardrails; Screens prompts and responses for prompt injection, jailbreaks, harmful content and sensitive data, for any model.
- **Cloud IAM + Privileged Access Manager** (Cloud access governance): alternatives: Organization Policy; Workforce identity federation lets staff sign in with the company directory.
- **Cloud Audit Logs** (Audit trail): alternatives: Log buckets with locked retention; Admin activity logs are free; data access logs are billed as Cloud Logging ingestion.
- **Cloud KMS** (Encryption keys): alternatives: Cloud HSM
- **Secure Source Manager** (App and infrastructure code): alternatives: GitHub or GitLab via Developer Connect
- **Infrastructure Manager (Terraform)** (Infrastructure as code): alternatives: Terraform or OpenTofu; A managed service that runs Terraform configurations.

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

About **$714 a month** on demand (Iowa (us-central1) list prices as of 2026-10-01; Google Cloud pricing pages, compiled manually, approximate).

| Period | On demand | With commitments |
|---|---:|---:|
| 1 month | $714 | – |
| 6 months | $4,286 | – |
| 1 year | $8,575 | $7,737 |
| 3 years | $25,769 | $21,685 |

| Service | Per month |
|---|---:|
| Cloud SQL for PostgreSQL (Agent state + history) | $178 |
| Vertex AI (Models + embeddings) | $141 |
| Cloud Run (Chat API (streaming)) | $116 |
| Model Armor (AI guardrails) | $85.30 |
| Vertex AI Vector Search (Knowledge index) | $68.47 |
| LiteLLM on Cloud Run (LLM gateway (LiteLLM)) | $57.82 |
| Vertex AI Agent Engine (Agent runtime (LangGraph)) | $34.07 |
| Cloud Load Balancing (Application LB) (HTTPS load balancer) | $19.51 |
| Cloud KMS (Encryption keys) | $5.03 |
| Cloud CDN (Web front end) | $3.52 |
| Cloud Storage (Source documents) | $2.04 |
| Cloud Audit Logs (Audit trail) | $1.18 |
| Cloud Monitoring + Cloud Logging (Logs, metrics, alarms) | $1.00 |
| Artifact Registry (Container images) | $0.45 |
| Secret Manager (Model and tool credentials) | $0.21 |
| Cloud Run functions (Tool functions) | $0.00 |
| Cloud Run functions (Chunk + embed documents) | $0.00 |
| Identity Platform (Single sign-on) | $0.00 |
| Cloud Trace (Vertex AI agent tracing) (LLM tracing (Langfuse)) | $0.00 |
| Cloud Build (Build, test and evaluate) | $0.00 |
| Cloud Deploy (Release pipeline) | $0.00 |

- Committed use discounts: 1- or 3-year commitments; about 37% or 55% off GKE node VMs, 25% or 52% off Cloud SQL, 20% or 40% off Memorystore.
- Cloud Run committed use discounts: 17% off for a 1- or 3-year spend commitment.
- Usage comes from each component's sizing and the requirements; edit it in the Spec tab.
- 730 hours a month. Always-free allowances are deducted where shown; trials are not.
- Excludes tax, support plans, and data transfer not listed.
- Prices are for Iowa (us-central1); your region (N. Virginia (us-east4)) may differ.

---
Estimates use list prices and the usage stated above; check them with the provider's calculator. Service names belong to their owners; Clarchy is not affiliated with any cloud provider.
