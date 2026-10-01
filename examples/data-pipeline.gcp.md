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

| Stage | Component | Capability | Service | Fidelity | Why |
|---|---|---|---|---|---|
| Users | Product apps | `client` | (outside the cloud) | - | _Generic: People or systems outside the cloud that use the application._ |
| Code | App and infrastructure code | `source-control` | Secure Source Manager | exact | Every change starts as a reviewed commit; the same repository holds the application and its infrastructure code. |
| Code | Infrastructure as code | `iac` | Infrastructure Manager (Terraform) | exact | Creates and updates the cloud resources from versioned templates, so every environment is reproducible. |
| Build | Build and test | `ci-build` | Cloud Build | exact | Builds and tests each commit, then packages the release. |
| Ship | Release pipeline | `cd-deploy` | Cloud Deploy | exact | Promotes each build through test and production with approvals and rollback. |
| Serve | Event collector | `api-gateway` | API Gateway | close | _Generic: Managed HTTP API front door with auth, throttling and routing._ |
| Integrate | Event stream | `stream` | Pub/Sub | close | Ordered, replayable ingestion that absorbs peaks and lets several consumers read the same data. |
| Integrate | Nightly transforms | `batch-etl` | Dataflow | close | Managed Spark jobs to clean and partition data without running a cluster. |
| Store | Data lake (raw + curated) | `object-storage` | Cloud Storage | exact | Cheapest durable storage for large, growing data; lifecycle rules move old data to colder tiers. |
| Store | Reporting warehouse | `data-warehouse` | BigQuery | exact | Fast SQL for dashboards; serverless billing suits a few analysts working office hours. |
| Operate | Pipeline monitoring | `monitoring` | Cloud Monitoring + Cloud Logging | exact | _Generic: Metrics, logs, dashboards and alarms._ |

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

- **API Gateway** (Event collector): alternatives: Apigee; Lighter than Amazon API Gateway or Azure API Management; Apigee is the full-featured option.
- **Pub/Sub** (Event stream): alternatives: Google Cloud Managed Service for Apache Kafka; Supports ordering keys and replay by seeking, but is not a partitioned log like Kinesis or Kafka.
- **Dataflow** (Nightly transforms): alternatives: Dataproc Serverless, Cloud Data Fusion; Dataflow runs Apache Beam pipelines; Spark jobs fit Dataproc Serverless better.
- **Secure Source Manager** (App and infrastructure code): alternatives: GitHub or GitLab via Developer Connect
- **Infrastructure Manager (Terraform)** (Infrastructure as code): alternatives: Terraform or OpenTofu; A managed service that runs Terraform configurations.

## Sizing assumptions

- **Event collector:** requests_per_month=300000000
- **Event stream:** shards=4, ingest_gb_per_month=300
- **Nightly transforms:** dpu_hours_per_month=200
- **Data lake (raw + curated):** storage_gb=2000
- **Reporting warehouse:** rpu_hours_per_month=300, storage_gb=500
- **Pipeline monitoring:** log_ingest_gb_per_month=10

## Estimated cost

About **$1,070 a month** on demand (Iowa (us-central1) list prices as of 2026-10-01; Google Cloud pricing pages, compiled manually, approximate).

| Period | On demand | With commitments |
|---|---:|---:|
| 1 month | $1,070 | – |
| 6 months | $6,511 | – |
| 1 year | $13,237 | – |
| 3 years | $42,304 | – |

| Service | Per month |
|---|---:|
| API Gateway (Event collector) | $894 |
| BigQuery (Reporting warehouse) | $95.10 |
| Cloud Storage (Data lake (raw + curated)) | $42.70 |
| Pub/Sub (Event stream) | $28.98 |
| Dataflow (Nightly transforms) | $8.32 |
| Cloud Monitoring + Cloud Logging (Pipeline monitoring) | $1.00 |
| Cloud Build (Build and test) | $0.00 |
| Cloud Deploy (Release pipeline) | $0.00 |

- Usage comes from each component's sizing and the requirements; edit it in the Spec tab.
- 730 hours a month. Always-free allowances are deducted where shown; trials are not.
- Excludes tax, support plans, and data transfer not listed.
- Prices are for Iowa (us-central1); your region (Frankfurt (europe-west3)) may differ.

---
Estimates use list prices and the usage stated above; check them with the provider's calculator. Service names belong to their owners; Clarchy is not affiliated with any cloud provider.
