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

| Stage | Component | Capability | Service | Fidelity | Why |
|---|---|---|---|---|---|
| Users | Product apps | `client` | (outside the cloud) | - | _Generic: People or systems outside the cloud that use the application._ |
| Code | App and infrastructure code | `source-control` | GitLab Community Edition | exact | Every change starts as a reviewed commit; the same repository holds the application and its infrastructure code. |
| Code | Infrastructure as code | `iac` | OpenTofu | exact | Creates and updates the cloud resources from versioned templates, so every environment is reproducible. |
| Build | Build and test | `ci-build` | Jenkins | exact | Builds and tests each commit, then packages the release. |
| Ship | Release pipeline | `cd-deploy` | Argo CD | exact | Promotes each build through test and production with approvals and rollback. |
| Serve | Event collector | `api-gateway` | Kong Gateway (OSS) | close | _Generic: Managed HTTP API front door with auth, throttling and routing._ |
| Integrate | Event stream | `stream` | Apache Kafka | exact | Ordered, replayable ingestion that absorbs peaks and lets several consumers read the same data. |
| Integrate | Nightly transforms | `batch-etl` | Apache Spark | close | Managed Spark jobs to clean and partition data without running a cluster. |
| Store | Data lake (raw + curated) | `object-storage` | Ceph Object Gateway | close | Cheapest durable storage for large, growing data; lifecycle rules move old data to colder tiers. |
| Store | Reporting warehouse | `data-warehouse` | ClickHouse | close | Fast SQL for dashboards; serverless billing suits a few analysts working office hours. |
| Operate | Pipeline monitoring | `monitoring` | Prometheus + Grafana | close | _Generic: Metrics, logs, dashboards and alarms._ |

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

- **Kong Gateway (OSS)** (Event collector): alternatives: Apache APISIX; Feature-rich, but you operate, scale and upgrade it.
- **Apache Kafka** (Event stream): alternatives: Apache Pulsar
- **Apache Spark** (Nightly transforms): alternatives: Apache Airflow + dbt; You run the cluster and a scheduler; managed ETL services hide both.
- **Ceph Object Gateway** (Data lake (raw + curated)): alternatives: SeaweedFS, Garage, MinIO; S3-compatible API, but you operate durability, replication, capacity and upgrades.
- **ClickHouse** (Reporting warehouse): alternatives: Apache Doris, DuckDB; Very fast analytical queries, but you size and operate the cluster.
- **Prometheus + Grafana** (Pipeline monitoring): alternatives: OpenTelemetry Collector, Grafana Loki; You store and retain metrics and logs yourself.
- **GitLab Community Edition** (App and infrastructure code): alternatives: Forgejo, Gitea; You run, back up and upgrade the Git server yourself.
- **Jenkins** (Build and test): alternatives: Tekton, GitLab CI/CD, Woodpecker CI; Build agents and plugins are yours to operate.
- **Argo CD** (Release pipeline): alternatives: Flux; GitOps deployment to Kubernetes from the Git repository.
- **OpenTofu** (Infrastructure as code): alternatives: Pulumi, Crossplane

## Sizing assumptions

- **Event collector:** requests_per_month=300000000
- **Event stream:** shards=4, ingest_gb_per_month=300
- **Nightly transforms:** dpu_hours_per_month=200
- **Data lake (raw + curated):** storage_gb=2000
- **Reporting warehouse:** rpu_hours_per_month=300, storage_gb=500
- **Pipeline monitoring:** log_ingest_gb_per_month=10

## Estimated cost

Open-source software has no licence fee: you pay for the machines it runs on and the people who operate it, which depends on where you host it. Open a cloud tab to see a managed-service estimate.

---
Estimates use list prices and the usage stated above; check them with the provider's calculator. Service names belong to their owners; CloudArchie is not affiliated with any cloud provider.
