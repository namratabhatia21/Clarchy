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

| Component | Capability | Service | Fidelity | Why |
|---|---|---|---|---|
| Clients | `client` | (outside the cloud) | - | _Generic: People or systems outside the cloud that use the application._ |
| Domain | `dns` | Azure DNS | exact | _Generic: Domain name resolution and routing._ |
| Web firewall | `waf` | Azure Web Application Firewall | exact | Blocks common attacks (SQL injection, bad bots) before they reach the app. |
| HTTPS load balancer | `load-balancer` | Azure Application Gateway | exact | Spreads traffic across containers in two availability zones and terminates TLS. |
| API containers | `container-service` | Azure Container Apps | exact | Steady traffic and long-lived connections favour always-on containers; reuses the existing Docker image. |
| Session + query cache | `cache` | Azure Managed Redis | exact | Cuts database reads for hot data and keeps p95 latency low. |
| PostgreSQL | `relational-db` | Azure Database for PostgreSQL (Flexible Server) | exact | Relational data with joins and transactions; Multi-AZ meets the 99.9% target. |
| Uploads | `object-storage` | Azure Blob Storage | exact | _Generic: Durable storage for files and blobs._ |
| DB credentials | `secrets` | Azure Key Vault | exact | Rotated credentials instead of passwords in environment files. |
| Logs, metrics, alarms | `monitoring` | Azure Monitor + Application Insights | exact | _Generic: Metrics, logs, dashboards and alarms._ |

## Shared services used

- API containers → Azure Key Vault

## Trade-offs and alternatives

- **Azure Web Application Firewall** (Web firewall): Runs on Azure Front Door or Application Gateway rather than as a separate service.
- **Azure Container Apps** (API containers): alternatives: Azure Kubernetes Service
- **Azure Managed Redis** (Session + query cache): alternatives: Azure Cache for Redis

## Sizing assumptions

- **Web firewall:** rules=10, requests_per_month=50000000
- **HTTPS load balancer:** lcu_hours_per_month=1460
- **API containers:** vcpu=1, memory_gb=2, tasks=3, hours_per_month=730
- **Session + query cache:** node_memory_gb=3, nodes=2
- **PostgreSQL:** vcpu=2, memory_gb=8, storage_gb=200, multi_az=True, backup_gb=200
- **Uploads:** storage_gb=300, egress_gb_per_month=200
- **DB credentials:** secrets=5
- **Logs, metrics, alarms:** log_ingest_gb_per_month=30

---
Cost estimates arrive in a later phase. Service names belong to their owners; CloudArchie is not affiliated with any cloud provider.
