# Event-driven processing on Azure

Uploads and events trigger asynchronous processing through a queue and a workflow, so slow jobs never block users.

> Azure mappings have not yet been reviewed by a specialist. Check the service choices before relying on them.

## Requirements

- **Region:** Pune (centralindia)
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
| Code | App and infrastructure code | `source-control` | Azure Repos | exact | Every change starts as a reviewed commit; the same repository holds the application and its infrastructure code. |
| Code | Infrastructure as code | `iac` | Bicep | exact | Creates and updates the cloud resources from versioned templates, so every environment is reproducible. |
| Build | Build and test | `ci-build` | Azure Pipelines | exact | Builds and tests each commit, then packages the functions. |
| Ship | Release pipeline | `cd-deploy` | Azure Pipelines (release stages) | exact | Promotes each build through test and production with approvals and rollback. |
| Serve | Ingest API | `api-gateway` | Azure API Management | exact | _Generic: Managed HTTP API front door with auth, throttling and routing._ |
| Run | Validate + enqueue | `serverless-function` | Azure Functions | exact | Short validation work per request; returns immediately and lets the queue absorb bursts. |
| Run | Workers | `serverless-function` | Azure Functions | exact | _Generic: Event-driven functions billed per invocation and duration._ |
| Integrate | Job queue | `message-queue` | Azure Service Bus (queues) | exact | Buffers bursts, retries failures and sends poison messages to a dead-letter queue. |
| Integrate | Domain events | `event-bus` | Azure Event Grid | exact | Lets new consumers subscribe later without changing producers. |
| Integrate | Processing steps | `workflow` | Azure Logic Apps | close | Multi-step jobs with retries and visible state instead of hand-written orchestration. |
| Store | Raw + processed files | `object-storage` | Azure Blob Storage | exact | _Generic: Durable storage for files and blobs._ |
| Store | Job status | `key-value-db` | Azure Cosmos DB | exact | _Generic: Serverless key-value / document database with single-digit ms reads._ |
| Operate | Logs, metrics, alarms | `monitoring` | Azure Monitor + Application Insights | exact | _Generic: Metrics, logs, dashboards and alarms._ |

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

- **Azure Service Bus (queues)** (Job queue): alternatives: Azure Queue Storage
- **Azure Logic Apps** (Processing steps): alternatives: Durable Functions; Logic Apps is low-code; Durable Functions is the code-first option closer to writing Step Functions logic in code.
- **Azure Cosmos DB** (Job status): alternatives: Azure Table Storage
- **Azure Repos** (App and infrastructure code): alternatives: GitHub
- **Azure Pipelines** (Build and test): alternatives: GitHub Actions
- **Azure Pipelines (release stages)** (Release pipeline): alternatives: GitHub Actions environments; The same Azure Pipelines definition usually builds and deploys.
- **Bicep** (Infrastructure as code): alternatives: ARM templates, Terraform or OpenTofu

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

---
Cost estimates arrive in a later phase. Service names belong to their owners; CloudArchie is not affiliated with any cloud provider.
