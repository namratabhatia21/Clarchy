# Microservices on Kubernetes on Open source

Containerised microservices on a managed Kubernetes cluster, with queue-driven workers that scale on backlog and a GitOps release flow.

> Open source mappings have not yet been reviewed by a specialist. Check the service choices before relying on them.

## Requirements

- **Region:** Western Europe
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
| Code | App and infrastructure code | `source-control` | GitLab Community Edition | exact | Every change starts as a reviewed commit; the same repository holds the application and its infrastructure code. |
| Code | Infrastructure as code | `iac` | OpenTofu | exact | Creates and updates the cloud resources from versioned templates, so every environment is reproducible. |
| Build | Build and test | `ci-build` | Jenkins | exact | Builds and tests each commit, then packages the app as a container image. |
| Ship | Container images | `container-registry` | Harbor | exact | Keeps versioned, scanned images so every environment runs exactly what was tested. |
| Ship | GitOps release | `cd-deploy` | Argo CD | exact | Rolls new versions out to the cluster from Git, with health checks and automatic rollback. |
| Serve | Domain | `dns` | PowerDNS | partial | _Generic: Domain name resolution and routing._ |
| Serve | Web firewall | `waf` | Coraza WAF + OWASP Core Rule Set | close | Blocks bots and common attacks before they reach the cluster. |
| Serve | Cluster ingress | `load-balancer` | HAProxy | close | One HTTPS entry point that routes paths to the right microservice. |
| Run | API microservices | `kubernetes` | Kubernetes | exact | Several independently deployed services share one cluster; Kubernetes gives rolling updates, autoscaling and the same deployment model on every cloud. |
| Run | Order workers | `kubernetes` | Kubernetes | exact | Long-running order jobs run as worker pods that scale independently of the API. |
| Run | Scale on backlog | `event-autoscaling` | KEDA | exact | Adds or removes workers as the backlog grows or shrinks, down to zero when idle. |
| Integrate | Order queue | `message-queue` | RabbitMQ | exact | Checkout returns immediately while order processing happens in the background; failed orders are retried. |
| Store | Orders and catalogue | `relational-db` | PostgreSQL | exact | Orders, payments and inventory need transactions and joins; a multi-zone primary meets the 99.95% target. |
| Store | Sessions and hot catalogue | `cache` | Valkey | exact | Keeps sessions and popular product pages in memory so the database handles fewer reads. |
| Store | Product images | `object-storage` | Ceph Object Gateway | close | _Generic: Durable storage for files and blobs._ |
| Operate | Customer accounts | `identity` | Keycloak | exact | _Generic: User sign-up, sign-in and tokens._ |
| Operate | Service credentials | `secrets` | OpenBao | exact | _Generic: Stores and rotates credentials._ |
| Operate | Logs, metrics, traces | `monitoring` | Prometheus + Grafana | close | _Generic: Metrics, logs, dashboards and alarms._ |

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

- API microservices → Keycloak: verify token
- API microservices → OpenBao

## Trade-offs and alternatives

- **PowerDNS** (Domain): alternatives: BIND, CoreDNS (internal DNS), Cloudflare DNS; You run and protect authoritative DNS servers yourself; most teams keep a managed DNS provider.
- **Coraza WAF + OWASP Core Rule Set** (Web firewall): alternatives: ModSecurity, Cloudflare WAF; You own rule updates, tuning and false positives.
- **HAProxy** (Cluster ingress): alternatives: NGINX, Envoy; Run at least two instances for availability and handle TLS certificates yourself.
- **Kubernetes** (API microservices): alternatives: K3s; You run the control plane, nodes and upgrades yourself.
- **RabbitMQ** (Order queue): alternatives: NATS JetStream
- **Kubernetes** (Order workers): alternatives: K3s; You run the control plane, nodes and upgrades yourself.
- **PostgreSQL** (Orders and catalogue): Backups, failover and upgrades are yours to run (tools such as Patroni help).
- **Valkey** (Sessions and hot catalogue): alternatives: Redis
- **Ceph Object Gateway** (Product images): alternatives: SeaweedFS, Garage, MinIO; S3-compatible API, but you operate durability, replication, capacity and upgrades.
- **OpenBao** (Service credentials): alternatives: HashiCorp Vault
- **Prometheus + Grafana** (Logs, metrics, traces): alternatives: OpenTelemetry Collector, Grafana Loki; You store and retain metrics and logs yourself.
- **GitLab Community Edition** (App and infrastructure code): alternatives: Forgejo, Gitea; You run, back up and upgrade the Git server yourself.
- **Jenkins** (Build and test): alternatives: Tekton, GitLab CI/CD, Woodpecker CI; Build agents and plugins are yours to operate.
- **Argo CD** (GitOps release): alternatives: Flux; GitOps deployment to Kubernetes from the Git repository.
- **OpenTofu** (Infrastructure as code): alternatives: Pulumi, Crossplane

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

Open-source software has no licence fee: you pay for the machines it runs on and the people who operate it, which depends on where you host it. Open a cloud tab to see a managed-service estimate.

---
Estimates use list prices and the usage stated above; check them with the provider's calculator. Service names belong to their owners; Clarchy is not affiliated with any cloud provider.
