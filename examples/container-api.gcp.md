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

| Component | Capability | Service | Fidelity | Why |
|---|---|---|---|---|
| Clients | `client` | (outside the cloud) | - | _Generic: People or systems outside the cloud that use the application._ |
| Domain | `dns` | Cloud DNS | exact | _Generic: Domain name resolution and routing._ |
| Web firewall | `waf` | Google Cloud Armor | exact | Blocks common attacks (SQL injection, bad bots) before they reach the app. |
| HTTPS load balancer | `load-balancer` | Cloud Load Balancing (Application LB) | exact | Spreads traffic across containers in two availability zones and terminates TLS. |
| API containers | `container-service` | Cloud Run | exact | Steady traffic and long-lived connections favour always-on containers; reuses the existing Docker image. |
| Session + query cache | `cache` | Memorystore (Redis / Valkey) | exact | Cuts database reads for hot data and keeps p95 latency low. |
| PostgreSQL | `relational-db` | Cloud SQL for PostgreSQL | exact | Relational data with joins and transactions; Multi-AZ meets the 99.9% target. |
| Uploads | `object-storage` | Cloud Storage | exact | _Generic: Durable storage for files and blobs._ |
| DB credentials | `secrets` | Secret Manager | exact | Rotated credentials instead of passwords in environment files. |
| Logs, metrics, alarms | `monitoring` | Cloud Monitoring + Cloud Logging | exact | _Generic: Metrics, logs, dashboards and alarms._ |

## Shared services used

- API containers → Secret Manager

## Trade-offs and alternatives

- **Cloud Run** (API containers): alternatives: GKE Autopilot
- **Cloud SQL for PostgreSQL** (PostgreSQL): alternatives: AlloyDB for PostgreSQL

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
