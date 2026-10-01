# Analytics data pipeline on AWS

Streams application events into a data lake, transforms them on a schedule and serves dashboards from a warehouse.

## Requirements

- **Region:** Europe (Frankfurt) (eu-central-1)
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
| Event collector | `api-gateway` | Amazon API Gateway | exact | _Generic: Managed HTTP API front door with auth, throttling and routing._ |
| Event stream | `stream` | Amazon Kinesis Data Streams | exact | Ordered, replayable ingestion that absorbs peaks and lets several consumers read the same data. |
| Nightly transforms | `batch-etl` | AWS Glue | exact | Managed Spark jobs to clean and partition data without running a cluster. |
| Data lake (raw + curated) | `object-storage` | Amazon S3 | exact | Cheapest durable storage for large, growing data; lifecycle rules move old data to colder tiers. |
| Reporting warehouse | `data-warehouse` | Amazon Redshift Serverless | exact | Fast SQL for dashboards; serverless billing suits a few analysts working office hours. |
| Pipeline monitoring | `monitoring` | Amazon CloudWatch | exact | _Generic: Metrics, logs, dashboards and alarms._ |

## Trade-offs and alternatives

- **Amazon Kinesis Data Streams** (Event stream): alternatives: Amazon MSK
- **Amazon Redshift Serverless** (Reporting warehouse): alternatives: Amazon Athena on S3

## Sizing assumptions

- **Event collector:** requests_per_month=300000000
- **Event stream:** shards=4, ingest_gb_per_month=300
- **Nightly transforms:** dpu_hours_per_month=200
- **Data lake (raw + curated):** storage_gb=2000
- **Reporting warehouse:** rpu_hours_per_month=300, storage_gb=500
- **Pipeline monitoring:** log_ingest_gb_per_month=10

---
Cost estimates arrive in a later phase. Service names belong to their owners; CloudArchie is not affiliated with any cloud provider.
