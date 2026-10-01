# Analytics data pipeline on Google Cloud

Streams application events into a data lake, transforms them on a schedule and serves dashboards from a warehouse.

> Google Cloud mappings have not yet been reviewed by a specialist. Check the service choices before relying on them.

## Requirements

- **Region:** Frankfurt (europe-west3)
- **Monthly active users:** 200
- **Peak requests/second:** 500
- **Data stored (GB):** 2000
- **Data growth (GB/month):** 300
- **Availability target:** 99.5%
- **Compliance:** none stated

## Services

| Component | Capability | Service | Fidelity | Why |
|---|---|---|---|---|
| Product apps | `client` | (outside the cloud) | - | _Generic: People or systems outside the cloud that use the application._ |
| Event collector | `api-gateway` | API Gateway | close | _Generic: Managed HTTP API front door with auth, throttling and routing._ |
| Event stream | `stream` | Pub/Sub | close | Ordered, replayable ingestion that absorbs peaks and lets several consumers read the same data. |
| Nightly transforms | `batch-etl` | Dataflow | close | Managed Spark jobs to clean and partition data without running a cluster. |
| Data lake (raw + curated) | `object-storage` | Cloud Storage | exact | Cheapest durable storage for large, growing data; lifecycle rules move old data to colder tiers. |
| Reporting warehouse | `data-warehouse` | BigQuery | exact | Fast SQL for dashboards; serverless billing suits a few analysts working office hours. |
| Pipeline monitoring | `monitoring` | Cloud Monitoring + Cloud Logging | exact | _Generic: Metrics, logs, dashboards and alarms._ |

## Trade-offs and alternatives

- **API Gateway** (Event collector): alternatives: Apigee; Lighter than Amazon API Gateway or Azure API Management; Apigee is the full-featured option.
- **Pub/Sub** (Event stream): alternatives: Google Cloud Managed Service for Apache Kafka; Supports ordering keys and replay by seeking, but is not a partitioned log like Kinesis or Kafka.
- **Dataflow** (Nightly transforms): alternatives: Dataproc Serverless, Cloud Data Fusion; Dataflow runs Apache Beam pipelines; Spark jobs fit Dataproc Serverless better.

## Sizing assumptions

- **Event collector:** requests_per_month=300000000
- **Event stream:** shards=4, ingest_gb_per_month=300
- **Nightly transforms:** dpu_hours_per_month=200
- **Data lake (raw + curated):** storage_gb=2000
- **Reporting warehouse:** rpu_hours_per_month=300, storage_gb=500
- **Pipeline monitoring:** log_ingest_gb_per_month=10

---
Cost estimates arrive in a later phase. Service names belong to their owners; CloudArchie is not affiliated with any cloud provider.
