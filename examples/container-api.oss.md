# Containerised API on Open source

Always-on containerised web API with a relational database and cache, for steady traffic and existing Docker apps.

> Open source mappings have not yet been reviewed by a specialist. Check the service choices before relying on them.

## Requirements

- **Region:** Western Europe
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
| Domain | `dns` | PowerDNS | partial | _Generic: Domain name resolution and routing._ |
| Web firewall | `waf` | Coraza WAF + OWASP Core Rule Set | close | Blocks common attacks (SQL injection, bad bots) before they reach the app. |
| HTTPS load balancer | `load-balancer` | HAProxy | close | Spreads traffic across containers in two availability zones and terminates TLS. |
| API containers | `container-service` | Kubernetes | close | Steady traffic and long-lived connections favour always-on containers; reuses the existing Docker image. |
| Session + query cache | `cache` | Valkey | exact | Cuts database reads for hot data and keeps p95 latency low. |
| PostgreSQL | `relational-db` | PostgreSQL | exact | Relational data with joins and transactions; Multi-AZ meets the 99.9% target. |
| Uploads | `object-storage` | Ceph Object Gateway | close | _Generic: Durable storage for files and blobs._ |
| DB credentials | `secrets` | OpenBao | exact | Rotated credentials instead of passwords in environment files. |
| Logs, metrics, alarms | `monitoring` | Prometheus + Grafana | close | _Generic: Metrics, logs, dashboards and alarms._ |

## Shared services used

- API containers → OpenBao

## Trade-offs and alternatives

- **PowerDNS** (Domain): alternatives: BIND, CoreDNS (internal DNS); You run and protect authoritative DNS servers yourself; most teams keep a managed DNS provider.
- **Coraza WAF + OWASP Core Rule Set** (Web firewall): alternatives: ModSecurity; You own rule updates, tuning and false positives.
- **HAProxy** (HTTPS load balancer): alternatives: NGINX, Envoy; Run at least two instances for availability and handle TLS certificates yourself.
- **Kubernetes** (API containers): alternatives: K3s, HashiCorp Nomad; You manage the cluster, nodes and upgrades; there is no per-second serverless billing.
- **Valkey** (Session + query cache): alternatives: Redis
- **PostgreSQL** (PostgreSQL): Backups, failover and upgrades are yours to run (tools such as Patroni help).
- **Ceph Object Gateway** (Uploads): alternatives: SeaweedFS, Garage, MinIO; S3-compatible API, but you operate durability, replication, capacity and upgrades.
- **OpenBao** (DB credentials): alternatives: HashiCorp Vault
- **Prometheus + Grafana** (Logs, metrics, alarms): alternatives: OpenTelemetry Collector, Grafana Loki; You store and retain metrics and logs yourself.

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
