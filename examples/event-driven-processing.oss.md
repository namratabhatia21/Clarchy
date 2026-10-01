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

| Component | Capability | Service | Fidelity | Why |
|---|---|---|---|---|
| Apps and partners | `client` | (outside the cloud) | - | _Generic: People or systems outside the cloud that use the application._ |
| Ingest API | `api-gateway` | Kong Gateway (OSS) | close | _Generic: Managed HTTP API front door with auth, throttling and routing._ |
| Validate + enqueue | `serverless-function` | Knative Serving | close | Short validation work per request; returns immediately and lets the queue absorb bursts. |
| Job queue | `message-queue` | RabbitMQ | exact | Buffers bursts, retries failures and sends poison messages to a dead-letter queue. |
| Domain events | `event-bus` | Knative Eventing | partial | Lets new consumers subscribe later without changing producers. |
| Processing steps | `workflow` | Temporal | close | Multi-step jobs with retries and visible state instead of hand-written orchestration. |
| Workers | `serverless-function` | Knative Serving | close | _Generic: Event-driven functions billed per invocation and duration._ |
| Raw + processed files | `object-storage` | Ceph Object Gateway | close | _Generic: Durable storage for files and blobs._ |
| Job status | `key-value-db` | Apache Cassandra | close | _Generic: Serverless key-value / document database with single-digit ms reads._ |
| Logs, metrics, alarms | `monitoring` | Prometheus + Grafana | close | _Generic: Metrics, logs, dashboards and alarms._ |

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
