# Analytics data pipeline on Open source

Streams application events into a data lake, transforms them on a schedule and serves dashboards from a warehouse.

> Open source mappings have not yet been reviewed by a specialist. Check the service choices before relying on them.

## Requirements

- **Region:** Central Europe
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
| Event collector | `api-gateway` | Kong Gateway (OSS) | close | _Generic: Managed HTTP API front door with auth, throttling and routing._ |
| Event stream | `stream` | Apache Kafka | exact | Ordered, replayable ingestion that absorbs peaks and lets several consumers read the same data. |
| Nightly transforms | `batch-etl` | Apache Spark | close | Managed Spark jobs to clean and partition data without running a cluster. |
| Data lake (raw + curated) | `object-storage` | Ceph Object Gateway | close | Cheapest durable storage for large, growing data; lifecycle rules move old data to colder tiers. |
| Reporting warehouse | `data-warehouse` | ClickHouse | close | Fast SQL for dashboards; serverless billing suits a few analysts working office hours. |
| Pipeline monitoring | `monitoring` | Prometheus + Grafana | close | _Generic: Metrics, logs, dashboards and alarms._ |

## Trade-offs and alternatives

- **Kong Gateway (OSS)** (Event collector): alternatives: Apache APISIX; Feature-rich, but you operate, scale and upgrade it.
- **Apache Kafka** (Event stream): alternatives: Apache Pulsar
- **Apache Spark** (Nightly transforms): alternatives: Apache Airflow + dbt; You run the cluster and a scheduler; managed ETL services hide both.
- **Ceph Object Gateway** (Data lake (raw + curated)): alternatives: SeaweedFS, Garage, MinIO; S3-compatible API, but you operate durability, replication, capacity and upgrades.
- **ClickHouse** (Reporting warehouse): alternatives: Apache Doris, DuckDB; Very fast analytical queries, but you size and operate the cluster.
- **Prometheus + Grafana** (Pipeline monitoring): alternatives: OpenTelemetry Collector, Grafana Loki; You store and retain metrics and logs yourself.

## Sizing assumptions

- **Event collector:** requests_per_month=300000000
- **Event stream:** shards=4, ingest_gb_per_month=300
- **Nightly transforms:** dpu_hours_per_month=200
- **Data lake (raw + curated):** storage_gb=2000
- **Reporting warehouse:** rpu_hours_per_month=300, storage_gb=500
- **Pipeline monitoring:** log_ingest_gb_per_month=10

---
Cost estimates arrive in a later phase. Service names belong to their owners; CloudArchie is not affiliated with any cloud provider.
