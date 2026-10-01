# Containerised API on Azure

Always-on containerised web API with a relational database and cache, for steady traffic and existing Docker apps.

> Azure mappings have not yet been reviewed by a specialist. Check the service choices before relying on them.

## Requirements

- **Region:** Ireland (northeurope)
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
| Code | App and infrastructure code | `source-control` | Azure Repos | exact | Every change starts as a reviewed commit; the same repository holds the application and its infrastructure code. |
| Code | Infrastructure as code | `iac` | Bicep | exact | Creates and updates the cloud resources from versioned templates, so every environment is reproducible. |
| Build | Build and test | `ci-build` | Azure Pipelines | exact | Builds and tests each commit, then packages the app as a container image. |
| Ship | Container images | `container-registry` | Azure Container Registry | exact | Keeps versioned, scanned images so every environment runs exactly what was tested. |
| Ship | Release pipeline | `cd-deploy` | Azure Pipelines (release stages) | exact | Promotes each build through test and production with approvals and rollback. |
| Serve | Domain | `dns` | Azure DNS | exact | _Generic: Domain name resolution and routing._ |
| Serve | Web firewall | `waf` | Azure Web Application Firewall | exact | Blocks common attacks (SQL injection, bad bots) before they reach the app. |
| Serve | HTTPS load balancer | `load-balancer` | Azure Application Gateway | exact | Spreads traffic across containers in two availability zones and terminates TLS. |
| Run | API containers | `container-service` | Azure Container Apps | exact | Steady traffic and long-lived connections favour always-on containers; reuses the existing Docker image. |
| Store | Session + query cache | `cache` | Azure Managed Redis | exact | Cuts database reads for hot data and keeps p95 latency low. |
| Store | PostgreSQL | `relational-db` | Azure Database for PostgreSQL (Flexible Server) | exact | Relational data with joins and transactions; Multi-AZ meets the 99.9% target. |
| Store | Uploads | `object-storage` | Azure Blob Storage | exact | _Generic: Durable storage for files and blobs._ |
| Operate | DB credentials | `secrets` | Azure Key Vault | exact | Rotated credentials instead of passwords in environment files. |
| Operate | Logs, metrics, alarms | `monitoring` | Azure Monitor + Application Insights | exact | _Generic: Metrics, logs, dashboards and alarms._ |

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

- API containers → Azure Key Vault

## Trade-offs and alternatives

- **Azure DNS** (Domain): alternatives: Cloudflare DNS
- **Azure Web Application Firewall** (Web firewall): alternatives: Cloudflare WAF; Runs on Azure Front Door or Application Gateway rather than as a separate service.
- **Azure Container Apps** (API containers): alternatives: Azure Kubernetes Service
- **Azure Managed Redis** (Session + query cache): alternatives: Azure Cache for Redis
- **Azure Repos** (App and infrastructure code): alternatives: GitHub
- **Azure Pipelines** (Build and test): alternatives: GitHub Actions
- **Azure Pipelines (release stages)** (Release pipeline): alternatives: GitHub Actions environments; The same Azure Pipelines definition usually builds and deploys.
- **Bicep** (Infrastructure as code): alternatives: ARM templates, Terraform or OpenTofu

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

About **$914 a month** on demand (East US list prices as of 2026-10-01; Azure pricing pages, compiled manually, approximate).

| Period | On demand | With commitments |
|---|---:|---:|
| 1 month | $914 | – |
| 6 months | $5,488 | – |
| 1 year | $10,985 | $9,468 |
| 3 years | $33,075 | $26,482 |

| Service | Per month |
|---|---:|
| Azure Database for PostgreSQL (Flexible Server) (PostgreSQL) | $306 |
| Azure Container Apps (API containers) | $237 |
| Azure Application Gateway (HTTPS load balancer) | $185 |
| Azure Managed Redis (Session + query cache) | $73.00 |
| Azure Monitor + Application Insights (Logs, metrics, alarms) | $58.50 |
| Azure Web Application Firewall (Web firewall) | $40.00 |
| Azure Blob Storage (Uploads) | $5.65 |
| Azure Container Registry (Container images) | $5.00 |
| Azure Key Vault (DB credentials) | $2.84 |
| Azure DNS (Domain) | $1.10 |
| Azure Pipelines (Build and test) | $0.00 |

- Azure savings plan for compute: 1- or 3-year hourly spend commitment; about 15% (1 year) or 17% (3 years) off Container Apps.
- Reserved capacity: 1 or 3 years for Azure Database for PostgreSQL (General Purpose); burstable servers are not eligible.
- Usage comes from each component's sizing and the requirements; edit it in the Spec tab.
- 730 hours a month. Always-free allowances are deducted where shown; trials are not.
- Excludes tax, support plans, and data transfer not listed.
- Prices are for East US; your region (Ireland (northeurope)) may differ.

---
Estimates use list prices and the usage stated above; check them with the provider's calculator. Service names belong to their owners; Clarchy is not affiliated with any cloud provider.
