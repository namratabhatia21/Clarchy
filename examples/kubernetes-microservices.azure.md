# Microservices on Kubernetes on Azure

Containerised microservices on a managed Kubernetes cluster, with queue-driven workers that scale on backlog and a GitOps release flow.

> Azure mappings have not yet been reviewed by a specialist. Check the service choices before relying on them.

## Requirements

- **Region:** Ireland (northeurope)
- **Monthly active users:** 200000
- **Peak requests/second:** 400
- **Data stored (GB):** 300
- **Data growth (GB/month):** 25
- **Availability target:** 99.95%
- **Compliance:** none stated

## Assumptions

- The team already builds Docker images and wants Kubernetes for portability across clouds.
- Order processing can finish within a few minutes, so it runs as background jobs.

## Services

| Stage | Component | Capability | Service | Fidelity | Why |
|---|---|---|---|---|---|
| Users | Web and mobile clients | `client` | (outside the cloud) | - | _Generic: People or systems outside the cloud that use the application._ |
| Code | App and infrastructure code | `source-control` | Azure Repos | exact | Every change starts as a reviewed commit; the same repository holds the application and its infrastructure code. |
| Code | Infrastructure as code | `iac` | Bicep | exact | Creates and updates the cloud resources from versioned templates, so every environment is reproducible. |
| Build | Build and test | `ci-build` | Azure Pipelines | exact | Builds and tests each commit, then packages the app as a container image. |
| Ship | Container images | `container-registry` | Azure Container Registry | exact | Keeps versioned, scanned images so every environment runs exactly what was tested. |
| Ship | GitOps release | `cd-deploy` | Azure Pipelines (release stages) | exact | Rolls new versions out to the cluster from Git, with health checks and automatic rollback. |
| Serve | Domain | `dns` | Azure DNS | exact | _Generic: Domain name resolution and routing._ |
| Serve | Web firewall | `waf` | Azure Web Application Firewall | exact | Blocks bots and common attacks before they reach the cluster. |
| Serve | Cluster ingress | `load-balancer` | Azure Application Gateway | exact | One HTTPS entry point that routes paths to the right microservice. |
| Run | API microservices | `kubernetes` | Azure Kubernetes Service (AKS) | exact | Several independently deployed services share one cluster; Kubernetes gives rolling updates, autoscaling and the same deployment model on every cloud. |
| Run | Order workers | `kubernetes` | Azure Kubernetes Service (AKS) | exact | Long-running order jobs run as worker pods that scale independently of the API. |
| Run | Scale on backlog | `event-autoscaling` | KEDA add-on for AKS | exact | Adds or removes workers as the backlog grows or shrinks, down to zero when idle. |
| Integrate | Order queue | `message-queue` | Azure Service Bus (queues) | exact | Checkout returns immediately while order processing happens in the background; failed orders are retried. |
| Store | Orders and catalogue | `relational-db` | Azure Database for PostgreSQL (Flexible Server) | exact | Orders, payments and inventory need transactions and joins; a multi-zone primary meets the 99.95% target. |
| Store | Sessions and hot catalogue | `cache` | Azure Managed Redis | exact | Keeps sessions and popular product pages in memory so the database handles fewer reads. |
| Store | Product images | `object-storage` | Azure Blob Storage | exact | _Generic: Durable storage for files and blobs._ |
| Operate | Customer accounts | `identity` | Microsoft Entra External ID | exact | _Generic: User sign-up, sign-in and tokens._ |
| Operate | Service credentials | `secrets` | Azure Key Vault | exact | _Generic: Stores and rotates credentials._ |
| Operate | Logs, metrics, traces | `monitoring` | Azure Monitor + Application Insights | exact | _Generic: Metrics, logs, dashboards and alarms._ |

## Workflows

### Serving a request

1. Web and mobile clients → Domain: look up the app's address
2. Web and mobile clients → Web firewall: filter malicious traffic (HTTPS)
3. Web firewall → Cluster ingress: spread requests across healthy instances
4. Cluster ingress → API microservices: run the business logic
5. API microservices → Orders and catalogue: read and write records
6. API microservices → Sessions and hot catalogue: read and refresh cached results
7. API microservices → Product images: store or read files
8. API microservices → Order queue: queue the job (new order)
9. API microservices → Customer accounts: verify the user's sign-in token
10. API microservices → Service credentials: fetch credentials
11. Every component → Logs, metrics, traces: send logs and metrics

### Background processing

1. Order queue → Order workers: process the queued jobs
2. Order queue → Scale on backlog: report the backlog
3. Order workers → Orders and catalogue: read and write records
4. Scale on backlog → Order workers: scale the workers

### Shipping a change

1. A developer → App and infrastructure code: push a reviewed change
2. App and infrastructure code → Build and test: start a build on every push
3. Build and test → Container images: publish the tested image
4. Container images → GitOps release: start the release
5. GitOps release → Infrastructure as code: apply infrastructure changes
6. GitOps release → API microservices, Order workers: roll out the new version

## Shared services used

- API microservices → Microsoft Entra External ID: verify token
- API microservices → Azure Key Vault

## Trade-offs and alternatives

- **Azure Web Application Firewall** (Web firewall): Runs on Azure Front Door or Application Gateway rather than as a separate service.
- **Azure Service Bus (queues)** (Order queue): alternatives: Azure Queue Storage
- **Azure Managed Redis** (Sessions and hot catalogue): alternatives: Azure Cache for Redis
- **Azure Repos** (App and infrastructure code): alternatives: GitHub
- **Azure Pipelines** (Build and test): alternatives: GitHub Actions
- **Azure Pipelines (release stages)** (GitOps release): alternatives: GitHub Actions environments; The same Azure Pipelines definition usually builds and deploys.
- **Bicep** (Infrastructure as code): alternatives: ARM templates, Terraform or OpenTofu
- **KEDA add-on for AKS** (Scale on backlog): Azure Container Apps also scales with KEDA rules built in.

## Sizing assumptions

- **Web firewall:** rules=15, requests_per_month=300000000
- **Cluster ingress:** lcu_hours_per_month=2190
- **API microservices:** node_vcpu=4, node_memory_gb=16, nodes_min=3, nodes_max=12
- **Order queue:** requests_per_month=40000000
- **Order workers:** pods_min=0, pods_max=50, vcpu_per_pod=0.5, memory_gb_per_pod=1
- **Orders and catalogue:** vcpu=4, memory_gb=32, storage_gb=300, multi_az=True, backup_gb=300
- **Sessions and hot catalogue:** node_memory_gb=6, nodes=2
- **Product images:** storage_gb=500, egress_gb_per_month=1500
- **Customer accounts:** monthly_active_users=200000
- **Service credentials:** secrets=20
- **Logs, metrics, traces:** log_ingest_gb_per_month=120

## Estimated cost

About **$6,103 a month** on demand (East US list prices as of 2026-10-01; Azure pricing pages, compiled manually, approximate).

| Period | On demand | With commitments |
|---|---:|---:|
| 1 month | $6,103 | – |
| 6 months | $36,625 | – |
| 1 year | $73,267 | $70,931 |
| 3 years | $219,999 | $208,851 |

| Service | Per month |
|---|---:|
| Microsoft Entra External ID (Customer accounts) | $4,500 |
| Azure Database for PostgreSQL (Flexible Server) (Orders and catalogue) | $329 |
| Azure Monitor + Application Insights (Logs, metrics, traces) | $266 |
| Azure Kubernetes Service (AKS) (API microservices) | $213 |
| Azure Application Gateway (Cluster ingress) | $197 |
| Azure Web Application Firewall (Web firewall) | $190 |
| Azure Managed Redis (Sessions and hot catalogue) | $146 |
| Azure Kubernetes Service (AKS) (Order workers) | $140 |
| Azure Service Bus (queues) (Order queue) | $95.46 |
| Azure Key Vault (Service credentials) | $9.46 |
| Azure Blob Storage (Product images) | $9.42 |
| Azure Container Registry (Container images) | $5.00 |
| Azure DNS (Domain) | $2.90 |
| Azure Pipelines (Build and test) | $0.00 |

- Reserved VM instances: 1 or 3 years; about 37% or 60% off the AKS node VMs.
- Reserved capacity: 1 or 3 years for Azure Database for PostgreSQL (General Purpose); burstable servers are not eligible.
- Usage comes from each component's sizing and the requirements; edit it in the Spec tab.
- 730 hours a month. Always-free allowances are deducted where shown; trials are not.
- Excludes tax, support plans, and data transfer not listed.
- Prices are for East US; your region (Ireland (northeurope)) may differ.

---
Estimates use list prices and the usage stated above; check them with the provider's calculator. Service names belong to their owners; CloudArchie is not affiliated with any cloud provider.
