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

| Stage | Component | Capability | Service | Fidelity | Why |
|---|---|---|---|---|---|
| Users | Product apps | `client` | (outside the cloud) | - | _Generic: People or systems outside the cloud that use the application._ |
| Code | App and infrastructure code | `source-control` | Azure Repos | exact | Every change starts as a reviewed commit; the same repository holds the application and its infrastructure code. |
| Code | Infrastructure as code | `iac` | Bicep | exact | Creates and updates the cloud resources from versioned templates, so every environment is reproducible. |
| Build | Build and test | `ci-build` | Azure Pipelines | exact | Builds and tests each commit, then packages the release. |
| Ship | Release pipeline | `cd-deploy` | Azure Pipelines (release stages) | exact | Promotes each build through test and production with approvals and rollback. |
| Serve | Event collector | `api-gateway` | Azure API Management | exact | _Generic: Managed HTTP API front door with auth, throttling and routing._ |
| Integrate | Event stream | `stream` | Azure Event Hubs | exact | Ordered, replayable ingestion that absorbs peaks and lets several consumers read the same data. |
| Integrate | Nightly transforms | `batch-etl` | Azure Data Factory | close | Managed Spark jobs to clean and partition data without running a cluster. |
| Store | Data lake (raw + curated) | `object-storage` | Azure Blob Storage | exact | Cheapest durable storage for large, growing data; lifecycle rules move old data to colder tiers. |
| Store | Reporting warehouse | `data-warehouse` | Microsoft Fabric Data Warehouse | close | Fast SQL for dashboards; serverless billing suits a few analysts working office hours. |
| Operate | Pipeline monitoring | `monitoring` | Azure Monitor + Application Insights | exact | _Generic: Metrics, logs, dashboards and alarms._ |

## Workflows

### Serving a request

1. Product apps → Event collector: send events
2. Event collector → Event stream: append to the event stream
3. Every component → Pipeline monitoring: send logs and metrics

### Data pipeline

1. Event stream → Data lake (raw + curated): land the raw events
2. Data lake (raw + curated) → Reporting warehouse: load curated data
3. Nightly transforms → Data lake (raw + curated): read and write curated data

### Shipping a change

1. A developer → App and infrastructure code: push a reviewed change
2. App and infrastructure code → Build and test: start a build on every push
3. Build and test → Release pipeline: hand over the tested package
4. Release pipeline → Infrastructure as code: apply infrastructure changes
5. Release pipeline → Nightly transforms: roll out the new version

## Trade-offs and alternatives

- **Azure Data Factory** (Nightly transforms): alternatives: Azure Databricks, Microsoft Fabric; Data Factory orchestrates and moves data; heavy transformations usually run in Databricks or Fabric Spark.
- **Microsoft Fabric Data Warehouse** (Reporting warehouse): alternatives: Azure Synapse Analytics; Fabric is an analytics platform billed by reserved capacity, not per query or per compute-second.
- **Azure Repos** (App and infrastructure code): alternatives: GitHub
- **Azure Pipelines** (Build and test): alternatives: GitHub Actions
- **Azure Pipelines (release stages)** (Release pipeline): alternatives: GitHub Actions environments; The same Azure Pipelines definition usually builds and deploys.
- **Bicep** (Infrastructure as code): alternatives: ARM templates, Terraform or OpenTofu

## Sizing assumptions

- **Event collector:** requests_per_month=300000000
- **Event stream:** shards=4, ingest_gb_per_month=300
- **Nightly transforms:** dpu_hours_per_month=200
- **Data lake (raw + curated):** storage_gb=2000
- **Reporting warehouse:** rpu_hours_per_month=300, storage_gb=500
- **Pipeline monitoring:** log_ingest_gb_per_month=10

## Estimated cost

About **$1,681 a month** on demand (East US list prices as of 2026-10-01; Azure pricing pages, compiled manually, approximate).

| Period | On demand | With commitments |
|---|---:|---:|
| 1 month | $1,681 | – |
| 6 months | $10,168 | – |
| 1 year | $20,534 | $19,257 |
| 3 years | $63,987 | $60,156 |

| Service | Per month |
|---|---:|
| Azure API Management (Event collector) | $1,256 |
| Microsoft Fabric Data Warehouse (Reporting warehouse) | $274 |
| Azure Data Factory (Nightly transforms) | $65.79 |
| Azure Blob Storage (Data lake (raw + curated)) | $39.50 |
| Azure Event Hubs (Event stream) | $32.94 |
| Azure Monitor + Application Insights (Pipeline monitoring) | $12.50 |
| Azure Pipelines (Build and test) | $0.00 |

- Fabric capacity reservation: 1 year; renewed each year in the 3-year view.
- Usage comes from each component's sizing and the requirements; edit it in the Spec tab.
- 730 hours a month. Always-free allowances are deducted where shown; trials are not.
- Excludes tax, support plans, and data transfer not listed.
- Prices are for East US; your region (Frankfurt (germanywestcentral)) may differ.

---
Estimates use list prices and the usage stated above; check them with the provider's calculator. Service names belong to their owners; Clarchy is not affiliated with any cloud provider.
