# Analytics data pipeline on Azure

Streams application events into a data lake, transforms them on a schedule and serves dashboards from a warehouse.

> Azure mappings have not yet been reviewed by a specialist. Check the service choices before relying on them.

## Requirements

- **Region:** Frankfurt (germanywestcentral)
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
| Event collector | `api-gateway` | Azure API Management | exact | _Generic: Managed HTTP API front door with auth, throttling and routing._ |
| Event stream | `stream` | Azure Event Hubs | exact | Ordered, replayable ingestion that absorbs peaks and lets several consumers read the same data. |
| Nightly transforms | `batch-etl` | Azure Data Factory | close | Managed Spark jobs to clean and partition data without running a cluster. |
| Data lake (raw + curated) | `object-storage` | Azure Blob Storage | exact | Cheapest durable storage for large, growing data; lifecycle rules move old data to colder tiers. |
| Reporting warehouse | `data-warehouse` | Microsoft Fabric Data Warehouse | close | Fast SQL for dashboards; serverless billing suits a few analysts working office hours. |
| Pipeline monitoring | `monitoring` | Azure Monitor + Application Insights | exact | _Generic: Metrics, logs, dashboards and alarms._ |

## Trade-offs and alternatives

- **Azure Data Factory** (Nightly transforms): alternatives: Azure Databricks, Microsoft Fabric; Data Factory orchestrates and moves data; heavy transformations usually run in Databricks or Fabric Spark.
- **Microsoft Fabric Data Warehouse** (Reporting warehouse): alternatives: Azure Synapse Analytics; Fabric is an analytics platform billed by reserved capacity, not per query or per compute-second.

## Sizing assumptions

- **Event collector:** requests_per_month=300000000
- **Event stream:** shards=4, ingest_gb_per_month=300
- **Nightly transforms:** dpu_hours_per_month=200
- **Data lake (raw + curated):** storage_gb=2000
- **Reporting warehouse:** rpu_hours_per_month=300, storage_gb=500
- **Pipeline monitoring:** log_ingest_gb_per_month=10

---
Cost estimates arrive in a later phase. Service names belong to their owners; CloudArchie is not affiliated with any cloud provider.
