# Analytics data pipeline on AWS

Streams application events into a data lake, transforms them on a schedule and serves dashboards from a warehouse.

> AWS mappings have not yet been reviewed by a specialist. Check the service choices before relying on them.

## Requirements

- **Region:** Frankfurt (eu-central-1)
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
| Code | App and infrastructure code | `source-control` | GitHub or GitLab via AWS CodeConnections | partial | Every change starts as a reviewed commit; the same repository holds the application and its infrastructure code. |
| Code | Infrastructure as code | `iac` | AWS CloudFormation | exact | Creates and updates the cloud resources from versioned templates, so every environment is reproducible. |
| Build | Build and test | `ci-build` | AWS CodeBuild | exact | Builds and tests each commit, then packages the release. |
| Ship | Release pipeline | `cd-deploy` | AWS CodePipeline | exact | Promotes each build through test and production with approvals and rollback. |
| Serve | Event collector | `api-gateway` | Amazon API Gateway | exact | _Generic: Managed HTTP API front door with auth, throttling and routing._ |
| Integrate | Event stream | `stream` | Amazon Kinesis Data Streams | exact | Ordered, replayable ingestion that absorbs peaks and lets several consumers read the same data. |
| Integrate | Nightly transforms | `batch-etl` | AWS Glue | exact | Managed Spark jobs to clean and partition data without running a cluster. |
| Store | Data lake (raw + curated) | `object-storage` | Amazon S3 | exact | Cheapest durable storage for large, growing data; lifecycle rules move old data to colder tiers. |
| Store | Reporting warehouse | `data-warehouse` | Amazon Redshift Serverless | exact | Fast SQL for dashboards; serverless billing suits a few analysts working office hours. |
| Operate | Pipeline monitoring | `monitoring` | Amazon CloudWatch | exact | _Generic: Metrics, logs, dashboards and alarms._ |

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

- **Amazon Kinesis Data Streams** (Event stream): alternatives: Amazon MSK
- **Amazon Redshift Serverless** (Reporting warehouse): alternatives: Amazon Athena on S3
- **GitHub or GitLab via AWS CodeConnections** (App and infrastructure code): alternatives: AWS CodeCommit; Most teams host code on GitHub or GitLab and connect it to AWS pipelines with CodeConnections. Check AWS CodeCommit's current availability before choosing it.
- **AWS CodeBuild** (Build and test): alternatives: GitHub Actions
- **AWS CodePipeline** (Release pipeline): alternatives: AWS CodeDeploy, GitHub Actions
- **AWS CloudFormation** (Infrastructure as code): alternatives: AWS CDK, Terraform or OpenTofu

## Sizing assumptions

- **Event collector:** requests_per_month=300000000
- **Event stream:** shards=4, ingest_gb_per_month=300
- **Nightly transforms:** dpu_hours_per_month=200
- **Data lake (raw + curated):** storage_gb=2000
- **Reporting warehouse:** rpu_hours_per_month=300, storage_gb=500
- **Pipeline monitoring:** log_ingest_gb_per_month=10

## Estimated cost

About **$1,469 a month** on demand (Europe (Frankfurt) list prices as of 2026-10-03; AWS Price List API).

| Period | On demand | With commitments |
|---|---:|---:|
| 1 month | $1,469 | – |
| 6 months | $8,925 | – |
| 1 year | $18,115 | $17,545 |
| 3 years | $57,521 | $55,810 |

| Service | Per month |
|---|---:|
| Amazon API Gateway (Event collector) | $1,110 |
| Amazon Redshift Serverless (Reporting warehouse) | $229 |
| AWS Glue (Nightly transforms) | $52.80 |
| Amazon S3 (Data lake (raw + curated)) | $51.91 |
| Amazon Kinesis Data Streams (Event stream) | $20.04 |
| Amazon CloudWatch (Pipeline monitoring) | $3.15 |
| AWS CodeBuild (Build and test) | $1.00 |
| AWS CodePipeline (Release pipeline) | $1.00 |

- Redshift Serverless reservations: 1 year, no upfront; renewed each year in the 3-year view.
- Usage comes from each component's sizing and the requirements; edit it in the Spec tab.
- 730 hours a month. Always-free allowances are deducted where shown; trials are not.
- Excludes tax, support plans, and data transfer not listed.

---
Estimates use list prices and the usage stated above; check them with the provider's calculator. Service names belong to their owners; Clarchy is not affiliated with any cloud provider.
