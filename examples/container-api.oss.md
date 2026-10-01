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

| Stage | Component | Capability | Service | Fidelity | Why |
|---|---|---|---|---|---|
| Users | Clients | `client` | (outside the cloud) | - | _Generic: People or systems outside the cloud that use the application._ |
| Code | App and infrastructure code | `source-control` | GitLab Community Edition | exact | Every change starts as a reviewed commit; the same repository holds the application and its infrastructure code. |
| Code | Infrastructure as code | `iac` | OpenTofu | exact | Creates and updates the cloud resources from versioned templates, so every environment is reproducible. |
| Build | Build and test | `ci-build` | Jenkins | exact | Builds and tests each commit, then packages the app as a container image. |
| Ship | Container images | `container-registry` | Harbor | exact | Keeps versioned, scanned images so every environment runs exactly what was tested. |
| Ship | Release pipeline | `cd-deploy` | Argo CD | exact | Promotes each build through test and production with approvals and rollback. |
| Serve | Domain | `dns` | PowerDNS | partial | _Generic: Domain name resolution and routing._ |
| Serve | Web firewall | `waf` | Coraza WAF + OWASP Core Rule Set | close | Blocks common attacks (SQL injection, bad bots) before they reach the app. |
| Serve | HTTPS load balancer | `load-balancer` | HAProxy | close | Spreads traffic across containers in two availability zones and terminates TLS. |
| Run | API containers | `container-service` | Kubernetes | close | Steady traffic and long-lived connections favour always-on containers; reuses the existing Docker image. |
| Store | Session + query cache | `cache` | Valkey | exact | Cuts database reads for hot data and keeps p95 latency low. |
| Store | PostgreSQL | `relational-db` | PostgreSQL | exact | Relational data with joins and transactions; Multi-AZ meets the 99.9% target. |
| Store | Uploads | `object-storage` | Ceph Object Gateway | close | _Generic: Durable storage for files and blobs._ |
| Operate | DB credentials | `secrets` | OpenBao | exact | Rotated credentials instead of passwords in environment files. |
| Operate | Logs, metrics, alarms | `monitoring` | Prometheus + Grafana | close | _Generic: Metrics, logs, dashboards and alarms._ |

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
- **GitLab Community Edition** (App and infrastructure code): alternatives: Forgejo, Gitea; You run, back up and upgrade the Git server yourself.
- **Jenkins** (Build and test): alternatives: Tekton, GitLab CI/CD, Woodpecker CI; Build agents and plugins are yours to operate.
- **Argo CD** (Release pipeline): alternatives: Flux; GitOps deployment to Kubernetes from the Git repository.
- **OpenTofu** (Infrastructure as code): alternatives: Pulumi, Crossplane

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
