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

| Component | Capability | Service | Fidelity | Why |
|---|---|---|---|---|
| Apps and partners | `client` | (outside the cloud) | - | _Generic: People or systems outside the cloud that use the application._ |
| Ingest API | `api-gateway` | API Gateway | close | _Generic: Managed HTTP API front door with auth, throttling and routing._ |
| Validate + enqueue | `serverless-function` | Cloud Run functions | exact | Short validation work per request; returns immediately and lets the queue absorb bursts. |
| Job queue | `message-queue` | Pub/Sub | close | Buffers bursts, retries failures and sends poison messages to a dead-letter queue. |
| Domain events | `event-bus` | Eventarc | close | Lets new consumers subscribe later without changing producers. |
| Processing steps | `workflow` | Workflows | exact | Multi-step jobs with retries and visible state instead of hand-written orchestration. |
| Workers | `serverless-function` | Cloud Run functions | exact | _Generic: Event-driven functions billed per invocation and duration._ |
| Raw + processed files | `object-storage` | Cloud Storage | exact | _Generic: Durable storage for files and blobs._ |
| Job status | `key-value-db` | Firestore | close | _Generic: Serverless key-value / document database with single-digit ms reads._ |
| Logs, metrics, alarms | `monitoring` | Cloud Monitoring + Cloud Logging | exact | _Generic: Metrics, logs, dashboards and alarms._ |

## Trade-offs and alternatives

- **API Gateway** (Ingest API): alternatives: Apigee; Lighter than Amazon API Gateway or Azure API Management; Apigee is the full-featured option.
- **Pub/Sub** (Job queue): alternatives: Cloud Tasks; Pub/Sub is publish/subscribe; a single subscription behaves like a queue. Cloud Tasks suits explicit task dispatch with rate limits.
- **Eventarc** (Domain events): Routes events to Cloud Run, functions and Workflows; filtering is simpler than EventBridge rules.
- **Firestore** (Job status): alternatives: Bigtable; A document database with a different query and pricing model from DynamoDB; Bigtable suits very high-throughput wide-column data.

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
