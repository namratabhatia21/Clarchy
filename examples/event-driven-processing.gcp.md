# Event-driven processing on Google Cloud

Uploads and events trigger asynchronous processing through a queue and a workflow, so slow jobs never block users.

> Google Cloud mappings have not yet been reviewed by a specialist. Check the service choices before relying on them.

## Requirements

- **Region:** Mumbai (asia-south1)
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
| Code | App and infrastructure code | `source-control` | Secure Source Manager | exact | Every change starts as a reviewed commit; the same repository holds the application and its infrastructure code. |
| Code | Infrastructure as code | `iac` | Infrastructure Manager (Terraform) | exact | Creates and updates the cloud resources from versioned templates, so every environment is reproducible. |
| Build | Build and test | `ci-build` | Cloud Build | exact | Builds and tests each commit, then packages the functions. |
| Ship | Release pipeline | `cd-deploy` | Cloud Deploy | exact | Promotes each build through test and production with approvals and rollback. |
| Serve | Ingest API | `api-gateway` | API Gateway | close | _Generic: Managed HTTP API front door with auth, throttling and routing._ |
| Run | Validate + enqueue | `serverless-function` | Cloud Run functions | exact | Short validation work per request; returns immediately and lets the queue absorb bursts. |
| Run | Workers | `serverless-function` | Cloud Run functions | exact | _Generic: Event-driven functions billed per invocation and duration._ |
| Integrate | Job queue | `message-queue` | Pub/Sub | close | Buffers bursts, retries failures and sends poison messages to a dead-letter queue. |
| Integrate | Domain events | `event-bus` | Eventarc | close | Lets new consumers subscribe later without changing producers. |
| Integrate | Processing steps | `workflow` | Workflows | exact | Multi-step jobs with retries and visible state instead of hand-written orchestration. |
| Store | Raw + processed files | `object-storage` | Cloud Storage | exact | _Generic: Durable storage for files and blobs._ |
| Store | Job status | `key-value-db` | Firestore | close | _Generic: Serverless key-value / document database with single-digit ms reads._ |
| Operate | Logs, metrics, alarms | `monitoring` | Cloud Monitoring + Cloud Logging | exact | _Generic: Metrics, logs, dashboards and alarms._ |

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

- **API Gateway** (Ingest API): alternatives: Apigee; Lighter than Amazon API Gateway or Azure API Management; Apigee is the full-featured option.
- **Pub/Sub** (Job queue): alternatives: Cloud Tasks; Pub/Sub is publish/subscribe; a single subscription behaves like a queue. Cloud Tasks suits explicit task dispatch with rate limits.
- **Eventarc** (Domain events): Routes events to Cloud Run, functions and Workflows; filtering is simpler than EventBridge rules.
- **Firestore** (Job status): alternatives: Bigtable; A document database with a different query and pricing model from DynamoDB; Bigtable suits very high-throughput wide-column data.
- **Secure Source Manager** (App and infrastructure code): alternatives: GitHub or GitLab via Developer Connect
- **Infrastructure Manager (Terraform)** (Infrastructure as code): alternatives: Terraform or OpenTofu; A managed service that runs Terraform configurations.

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

About **$160 a month** on demand (Iowa (us-central1) list prices as of 2026-10-01; Google Cloud pricing pages, compiled manually, approximate).

| Period | On demand | With commitments |
|---|---:|---:|
| 1 month | $160 | – |
| 6 months | $980 | – |
| 1 year | $2,003 | – |
| 3 years | $6,526 | – |

| Service | Per month |
|---|---:|
| Cloud Run functions (Workers) | $102 |
| Workflows (Processing steps) | $37.79 |
| Cloud Storage (Raw + processed files) | $10.54 |
| Firestore (Job status) | $9.00 |
| Cloud Monitoring + Cloud Logging (Logs, metrics, alarms) | $1.00 |
| Eventarc (Domain events) | $0.32 |
| Pub/Sub (Job queue) | $0.06 |
| API Gateway (Ingest API) | $0.00 |
| Cloud Run functions (Validate + enqueue) | $0.00 |
| Cloud Build (Build and test) | $0.00 |
| Cloud Deploy (Release pipeline) | $0.00 |

- Usage comes from each component's sizing and the requirements; edit it in the Spec tab.
- 730 hours a month. Always-free allowances are deducted where shown; trials are not.
- Excludes tax, support plans, and data transfer not listed.
- Prices are for Iowa (us-central1); your region (Mumbai (asia-south1)) may differ.

---
Estimates use list prices and the usage stated above; check them with the provider's calculator. Service names belong to their owners; CloudArchie is not affiliated with any cloud provider.
