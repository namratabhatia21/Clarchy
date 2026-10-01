# Event-driven processing on AWS

Uploads and events trigger asynchronous processing through a queue and a workflow, so slow jobs never block users.

> AWS mappings have not yet been reviewed by a specialist. Check the service choices before relying on them.

## Requirements

- **Region:** Mumbai (ap-south-1)
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
| Ingest API | `api-gateway` | Amazon API Gateway | exact | _Generic: Managed HTTP API front door with auth, throttling and routing._ |
| Validate + enqueue | `serverless-function` | AWS Lambda | exact | Short validation work per request; returns immediately and lets the queue absorb bursts. |
| Job queue | `message-queue` | Amazon SQS | exact | Buffers bursts, retries failures and sends poison messages to a dead-letter queue. |
| Domain events | `event-bus` | Amazon EventBridge | exact | Lets new consumers subscribe later without changing producers. |
| Processing steps | `workflow` | AWS Step Functions | exact | Multi-step jobs with retries and visible state instead of hand-written orchestration. |
| Workers | `serverless-function` | AWS Lambda | exact | _Generic: Event-driven functions billed per invocation and duration._ |
| Raw + processed files | `object-storage` | Amazon S3 | exact | _Generic: Durable storage for files and blobs._ |
| Job status | `key-value-db` | Amazon DynamoDB | exact | _Generic: Serverless key-value / document database with single-digit ms reads._ |
| Logs, metrics, alarms | `monitoring` | Amazon CloudWatch | exact | _Generic: Metrics, logs, dashboards and alarms._ |

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
