# Containerised API on Google Cloud

Always-on containerised web API with a relational database and cache, for steady traffic and existing Docker apps.

> Google Cloud mappings have not yet been reviewed by a specialist. Check the service choices before relying on them.

## Requirements

- **Region:** Belgium (europe-west1)
- **Monthly active users:** 50000
- **Peak requests/second:** 120
- **Data stored (GB):** 200
- **Data growth (GB/month):** 15
- **Availability target:** 99.9%
- **Compliance:** none stated

## Services

| Stage | Component | Capability | Service | Fidelity | Why |
|---|---|---|---|---|---|
| Users | Clients | `client` | (outside the cloud) | - | _Generic: People or systems outside the cloud that use the application._ |
| Code | App and infrastructure code | `source-control` | Secure Source Manager | exact | Every change starts as a reviewed commit; the same repository holds the application and its infrastructure code. |
| Code | Infrastructure as code | `iac` | Infrastructure Manager (Terraform) | exact | Creates and updates the cloud resources from versioned templates, so every environment is reproducible. |
| Build | Build and test | `ci-build` | Cloud Build | exact | Builds and tests each commit, then packages the app as a container image. |
| Ship | Container images | `container-registry` | Artifact Registry | exact | Keeps versioned, scanned images so every environment runs exactly what was tested. |
| Ship | Release pipeline | `cd-deploy` | Cloud Deploy | exact | Promotes each build through test and production with approvals and rollback. |
| Serve | Domain | `dns` | Cloud DNS | exact | _Generic: Domain name resolution and routing._ |
| Serve | Web firewall | `waf` | Google Cloud Armor | exact | Blocks common attacks (SQL injection, bad bots) before they reach the app. |
| Serve | HTTPS load balancer | `load-balancer` | Cloud Load Balancing (Application LB) | exact | Spreads traffic across containers in two availability zones and terminates TLS. |
| Run | API containers | `container-service` | Cloud Run | exact | Steady traffic and long-lived connections favour always-on containers; reuses the existing Docker image. |
| Store | Session + query cache | `cache` | Memorystore (Redis / Valkey) | exact | Cuts database reads for hot data and keeps p95 latency low. |
| Store | PostgreSQL | `relational-db` | Cloud SQL for PostgreSQL | exact | Relational data with joins and transactions; Multi-AZ meets the 99.9% target. |
| Store | Uploads | `object-storage` | Cloud Storage | exact | _Generic: Durable storage for files and blobs._ |
| Operate | DB credentials | `secrets` | Secret Manager | exact | Rotated credentials instead of passwords in environment files. |
| Operate | Logs, metrics, alarms | `monitoring` | Cloud Monitoring + Cloud Logging | exact | _Generic: Metrics, logs, dashboards and alarms._ |

## Workflows

### Serving a request

1. Clients → Domain: look up the app's address
2. Clients → Web firewall: filter malicious traffic (HTTPS)
3. Web firewall → HTTPS load balancer: spread requests across healthy instances
4. HTTPS load balancer → API containers: run the business logic
5. API containers → Session + query cache: read and refresh cached results
6. API containers → PostgreSQL: read and write records
7. API containers → Uploads: store or read files
8. API containers → DB credentials: fetch credentials
9. Every component → Logs, metrics, alarms: send logs and metrics

### Shipping a change

1. A developer → App and infrastructure code: push a reviewed change
2. App and infrastructure code → Build and test: start a build on every push
3. Build and test → Container images: publish the tested image
4. Container images → Release pipeline: start the release
5. Release pipeline → Infrastructure as code: apply infrastructure changes
6. Release pipeline → API containers: roll out the new version

## Shared services used

- API containers → Secret Manager

## Trade-offs and alternatives

- **Cloud DNS** (Domain): alternatives: Cloudflare DNS
- **Google Cloud Armor** (Web firewall): alternatives: Cloudflare WAF
- **Cloud Run** (API containers): alternatives: GKE Autopilot
- **Cloud SQL for PostgreSQL** (PostgreSQL): alternatives: AlloyDB for PostgreSQL
- **Secure Source Manager** (App and infrastructure code): alternatives: GitHub or GitLab via Developer Connect
- **Infrastructure Manager (Terraform)** (Infrastructure as code): alternatives: Terraform or OpenTofu; A managed service that runs Terraform configurations.

## Sizing assumptions

- **Web firewall:** rules=10, requests_per_month=50000000
- **HTTPS load balancer:** lcu_hours_per_month=1460
- **API containers:** vcpu=1, memory_gb=2, tasks=3, hours_per_month=730
- **Session + query cache:** node_memory_gb=3, nodes=2
- **PostgreSQL:** vcpu=2, memory_gb=8, storage_gb=200, multi_az=True, backup_gb=200
- **Uploads:** storage_gb=300, egress_gb_per_month=200
- **DB credentials:** secrets=5
- **Logs, metrics, alarms:** log_ingest_gb_per_month=30

## Estimated cost

About **$654 a month** on demand (Iowa (us-central1) list prices as of 2026-10-01; Google Cloud pricing pages, compiled manually, approximate).

| Period | On demand | With commitments |
|---|---:|---:|
| 1 month | $654 | – |
| 6 months | $3,929 | – |
| 1 year | $7,870 | $6,625 |
| 3 years | $23,738 | $17,186 |

| Service | Per month |
|---|---:|
| Cloud SQL for PostgreSQL (PostgreSQL) | $270 |
| Cloud Run (API containers) | $173 |
| Memorystore (Redis / Valkey) (Session + query cache) | $118 |
| Google Cloud Armor (Web firewall) | $47.50 |
| Cloud Load Balancing (Application LB) (HTTPS load balancer) | $33.39 |
| Cloud Storage (Uploads) | $6.13 |
| Secret Manager (DB credentials) | $2.81 |
| Cloud Monitoring + Cloud Logging (Logs, metrics, alarms) | $1.00 |
| Cloud DNS (Domain) | $0.80 |
| Artifact Registry (Container images) | $0.45 |
| Cloud Build (Build and test) | $0.00 |
| Cloud Deploy (Release pipeline) | $0.00 |

- Committed use discounts: 1- or 3-year commitments; about 37% or 55% off GKE node VMs, 25% or 52% off Cloud SQL, 20% or 40% off Memorystore.
- Cloud Run committed use discounts: 17% off for a 1- or 3-year spend commitment.
- Usage comes from each component's sizing and the requirements; edit it in the Spec tab.
- 730 hours a month. Always-free allowances are deducted where shown; trials are not.
- Excludes tax, support plans, and data transfer not listed.
- Prices are for Iowa (us-central1); your region (Belgium (europe-west1)) may differ.

---
Estimates use list prices and the usage stated above; check them with the provider's calculator. Service names belong to their owners; Clarchy is not affiliated with any cloud provider.
