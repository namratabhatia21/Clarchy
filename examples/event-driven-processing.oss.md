# Event-driven processing on Open source

Uploads and events trigger asynchronous processing through a queue and a workflow, so slow jobs never block users.

> Open source mappings have not yet been reviewed by a specialist. Check the service choices before relying on them.

## Requirements

- **Region:** India (West)
- **Monthly active users:** 5000
- **Peak requests/second:** 20
- **Data stored (GB):** 500
- **Data growth (GB/month):** 60
- **Availability target:** 99.9%
- **Compliance:** none stated

## Services

| Stage | Component | Capability | Service | Fidelity | Why |
|---|---|---|---|---|---|
| Users | Apps and partners | `client` | (outside the cloud) | - | _Generic: People or systems outside the cloud that use the application._ |
| Code | App and infrastructure code | `source-control` | GitLab Community Edition | exact | Every change starts as a reviewed commit; the same repository holds the application and its infrastructure code. |
| Code | Infrastructure as code | `iac` | OpenTofu | exact | Creates and updates the cloud resources from versioned templates, so every environment is reproducible. |
| Build | Build and test | `ci-build` | Jenkins | exact | Builds and tests each commit, then packages the functions. |
| Ship | Release pipeline | `cd-deploy` | Argo CD | exact | Promotes each build through test and production with approvals and rollback. |
| Serve | Ingest API | `api-gateway` | Kong Gateway (OSS) | close | _Generic: Managed HTTP API front door with auth, throttling and routing._ |
| Run | Validate + enqueue | `serverless-function` | Knative Serving | close | Short validation work per request; returns immediately and lets the queue absorb bursts. |
| Run | Workers | `serverless-function` | Knative Serving | close | _Generic: Event-driven functions billed per invocation and duration._ |
| Integrate | Job queue | `message-queue` | RabbitMQ | exact | Buffers bursts, retries failures and sends poison messages to a dead-letter queue. |
| Integrate | Domain events | `event-bus` | Knative Eventing | partial | Lets new consumers subscribe later without changing producers. |
| Integrate | Processing steps | `workflow` | Temporal | close | Multi-step jobs with retries and visible state instead of hand-written orchestration. |
| Store | Raw + processed files | `object-storage` | Ceph Object Gateway | close | _Generic: Durable storage for files and blobs._ |
| Store | Job status | `key-value-db` | Apache Cassandra | close | _Generic: Serverless key-value / document database with single-digit ms reads._ |
| Operate | Logs, metrics, alarms | `monitoring` | Prometheus + Grafana | close | _Generic: Metrics, logs, dashboards and alarms._ |

## Workflows

### Serving a request

1. Apps and partners → Ingest API: authenticate, throttle and route the call
2. Ingest API → Validate + enqueue: run the function
3. Validate + enqueue → Raw + processed files: store the upload
4. Validate + enqueue → Job queue: queue the job
5. Every component → Logs, metrics, alarms: send logs and metrics

### Background processing

1. Job queue → Processing steps: process the queued jobs
2. Processing steps → Workers: run the function
3. Workers → Raw + processed files: store or read files
4. Workers → Job status: read and write items
5. Workers → Domain events: announce that the job is done

### Shipping a change

1. A developer → App and infrastructure code: push a reviewed change
2. App and infrastructure code → Build and test: start a build on every push
3. Build and test → Release pipeline: hand over the tested package
4. Release pipeline → Infrastructure as code: apply infrastructure changes
5. Release pipeline → Validate + enqueue, Workers: roll out the new version

## Trade-offs and alternatives

- **Kong Gateway (OSS)** (Ingest API): alternatives: Apache APISIX; Feature-rich, but you operate, scale and upgrade it.
- **Knative Serving** (Validate + enqueue): alternatives: OpenFaaS; Scale-to-zero on your Kubernetes cluster; the cluster itself keeps running and costing money.
- **RabbitMQ** (Job queue): alternatives: NATS JetStream
- **Knative Eventing** (Domain events): alternatives: NATS; Provides event routing on Kubernetes; rule-based routing across many sources needs more assembly than a managed event bus.
- **Temporal** (Processing steps): alternatives: Apache Airflow; Code-first durable workflows; Airflow suits scheduled data pipelines more than application workflows.
- **Knative Serving** (Workers): alternatives: OpenFaaS; Scale-to-zero on your Kubernetes cluster; the cluster itself keeps running and costing money.
- **Ceph Object Gateway** (Raw + processed files): alternatives: SeaweedFS, Garage, MinIO; S3-compatible API, but you operate durability, replication, capacity and upgrades.
- **Apache Cassandra** (Job status): alternatives: FerretDB; Scales well but needs careful data modelling and cluster operations.
- **Prometheus + Grafana** (Logs, metrics, alarms): alternatives: OpenTelemetry Collector, Grafana Loki; You store and retain metrics and logs yourself.
- **GitLab Community Edition** (App and infrastructure code): alternatives: Forgejo, Gitea; You run, back up and upgrade the Git server yourself.
- **Jenkins** (Build and test): alternatives: Tekton, GitLab CI/CD, Woodpecker CI; Build agents and plugins are yours to operate.
- **Argo CD** (Release pipeline): alternatives: Flux; GitOps deployment to Kubernetes from the Git repository.
- **OpenTofu** (Infrastructure as code): alternatives: Pulumi, Crossplane

## Sizing assumptions

- **Ingest API:** requests_per_month=2000000
- **Validate + enqueue:** invocations_per_month=2000000, avg_duration_ms=80, memory_mb=256
- **Job queue:** requests_per_month=6000000
- **Domain events:** events_per_month=2000000
- **Processing steps:** state_transitions_per_month=10000000
- **Workers:** invocations_per_month=8000000, avg_duration_ms=900, memory_mb=1024
- **Raw + processed files:** storage_gb=500, put_requests_per_month=2000000
- **Job status:** storage_gb=5, reads_per_month=10000000, writes_per_month=6000000
- **Logs, metrics, alarms:** log_ingest_gb_per_month=20

## Estimated cost

Open-source software has no licence fee: you pay for the machines it runs on and the people who operate it, which depends on where you host it. Open a cloud tab to see a managed-service estimate.

---
Estimates use list prices and the usage stated above; check them with the provider's calculator. Service names belong to their owners; Clarchy is not affiliated with any cloud provider.
