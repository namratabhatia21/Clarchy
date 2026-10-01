# AI agent platform on Open source

Tool-using AI agents behind a chat API, with an LLM gateway for model routing and budgets, retrieval over company documents, and tracing of every model call.

> Open source mappings have not yet been reviewed by a specialist. Check the service choices before relying on them.

## Requirements

- **Region:** US East
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
| Code | App and infrastructure code | `source-control` | GitLab Community Edition | exact | Every change starts as a reviewed commit; the same repository holds the application, the agent graphs and the infrastructure code. |
| Code | Infrastructure as code | `iac` | OpenTofu | exact | Creates and updates the cloud resources from versioned templates, so every environment is reproducible. |
| Build | Build, test and evaluate | `ci-build` | Jenkins | exact | Builds and tests each commit and runs the agent's evaluation set, then packages the services as container images and the functions as bundles. |
| Ship | Container images | `container-registry` | Harbor | exact | Keeps versioned, scanned images so every environment runs exactly what was tested. |
| Ship | Release pipeline | `cd-deploy` | Argo CD | exact | Promotes each build through test and production with approvals and rollback. |
| Serve | Web front end | `cdn` | Varnish Cache | partial | _Generic: Content delivery network that caches content close to users._ |
| Serve | HTTPS load balancer | `load-balancer` | HAProxy | close | _Generic: Distributes HTTP traffic across healthy compute instances._ |
| Run | Chat API (streaming) | `container-service` | Kubernetes | close | Streams agent progress and answers over long-lived connections, which suits containers better than short-lived functions. |
| Run | Agent runtime (LangGraph) | `agent-orchestration` | LangGraph | exact | Runs LangGraph agents that plan, call tools and checkpoint their state, so long tasks survive restarts and can pause for a human to approve. |
| Run | Tool functions | `serverless-function` | Knative Serving | close | Small functions the agent calls as tools, such as looking up a record or opening a ticket, each with least-privilege access to one system. |
| Run | Models + embeddings | `llm-inference` | vLLM (open-weight models) | close | Managed models behind the gateway; a larger model plans and a smaller one handles routine steps, billed per token. |
| Run | Chunk + embed documents | `serverless-function` | Knative Serving | close | Runs only when documents change. |
| Integrate | LLM gateway (LiteLLM) | `llm-gateway` | LiteLLM Proxy | exact | One OpenAI-compatible API in front of every model, with per-team keys and budgets, fallbacks between providers and response caching. |
| Store | Source documents | `object-storage` | Ceph Object Gateway | close | _Generic: Durable storage for files and blobs._ |
| Store | Knowledge index | `vector-search` | pgvector (PostgreSQL) | exact | Lets the agent ground its answers in company documents with hybrid keyword and vector search. |
| Store | Agent state + history | `relational-db` | PostgreSQL | exact | Postgres holds the agent checkpoints, chat history and the gateway's spend log in one managed database. |
| Operate | Single sign-on | `identity` | Keycloak | exact | _Generic: User sign-up, sign-in and tokens._ |
| Operate | Model and tool credentials | `secrets` | OpenBao | exact | _Generic: Stores and rotates credentials._ |
| Operate | LLM tracing (Langfuse) | `llm-observability` | Langfuse | exact | Traces every prompt, tool call, token and cost, and scores samples with evals, so regressions show up before users notice them. |
| Operate | Logs, metrics, alarms | `monitoring` | Prometheus + Grafana | close | _Generic: Metrics, logs, dashboards and alarms._ |

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
11. LLM gateway (LiteLLM) → Models + embeddings: call the chosen model, falling back to another if it fails
12. Every model call → LLM tracing (Langfuse): record the prompt, tool calls, tokens and cost
13. Every component → Logs, metrics, alarms: send logs and metrics

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

- Chat API (streaming) → Keycloak: verify token
- Agent runtime (LangGraph) → OpenBao

## Trade-offs and alternatives

- **Varnish Cache** (Web front end): alternatives: NGINX caching; Caches at your own servers, not at a global edge network; a worldwide CDN is not practical to self-host.
- **HAProxy** (HTTPS load balancer): alternatives: NGINX, Envoy; Run at least two instances for availability and handle TLS certificates yourself.
- **Kubernetes** (Chat API (streaming)): alternatives: K3s, HashiCorp Nomad; You manage the cluster, nodes and upgrades; there is no per-second serverless billing.
- **LangGraph** (Agent runtime (LangGraph)): alternatives: CrewAI, LlamaIndex Workflows; A library that runs inside your own containers, with checkpoints in your database; LangGraph Platform is the hosted option.
- **Knative Serving** (Tool functions): alternatives: OpenFaaS; Scale-to-zero on your Kubernetes cluster; the cluster itself keeps running and costing money.
- **LiteLLM Proxy** (LLM gateway (LiteLLM)): alternatives: Portkey Gateway, Kong AI Gateway; Self-hosted proxy with an OpenAI-compatible API for more than 100 model providers, virtual keys, budgets, fallbacks and caching.
- **vLLM (open-weight models)** (Models + embeddings): alternatives: Ollama, Hugging Face TGI; Needs GPUs you provision; limited to open-weight models.
- **Ceph Object Gateway** (Source documents): alternatives: SeaweedFS, Garage, MinIO; S3-compatible API, but you operate durability, replication, capacity and upgrades.
- **Knative Serving** (Chunk + embed documents): alternatives: OpenFaaS; Scale-to-zero on your Kubernetes cluster; the cluster itself keeps running and costing money.
- **pgvector (PostgreSQL)** (Knowledge index): alternatives: Qdrant, Milvus, OpenSearch
- **PostgreSQL** (Agent state + history): Backups, failover and upgrades are yours to run (tools such as Patroni help).
- **OpenBao** (Model and tool credentials): alternatives: HashiCorp Vault
- **Langfuse** (LLM tracing (Langfuse)): alternatives: Arize Phoenix, OpenLLMetry; Self-hosting needs Postgres, ClickHouse, Redis and object storage; Langfuse Cloud is the hosted option.
- **Prometheus + Grafana** (Logs, metrics, alarms): alternatives: OpenTelemetry Collector, Grafana Loki; You store and retain metrics and logs yourself.
- **GitLab Community Edition** (App and infrastructure code): alternatives: Forgejo, Gitea; You run, back up and upgrade the Git server yourself.
- **Jenkins** (Build, test and evaluate): alternatives: Tekton, GitLab CI/CD, Woodpecker CI; Build agents and plugins are yours to operate.
- **Argo CD** (Release pipeline): alternatives: Flux; GitOps deployment to Kubernetes from the Git repository.
- **OpenTofu** (Infrastructure as code): alternatives: Pulumi, Crossplane

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

Open-source software has no licence fee: you pay for the machines it runs on and the people who operate it, which depends on where you host it. Open a cloud tab to see a managed-service estimate.

---
Estimates use list prices and the usage stated above; check them with the provider's calculator. Service names belong to their owners; Clarchy is not affiliated with any cloud provider.
