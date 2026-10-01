# Microservices on Kubernetes on Google Cloud

Containerised microservices on a managed Kubernetes cluster, with queue-driven workers that scale on backlog and a GitOps release flow.

> Google Cloud mappings have not yet been reviewed by a specialist. Check the service choices before relying on them.

## Requirements

- **Region:** Belgium (europe-west1)
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
| Code | App and infrastructure code | `source-control` | Secure Source Manager | exact | Every change starts as a reviewed commit; the same repository holds the application and its infrastructure code. |
| Code | Infrastructure as code | `iac` | Infrastructure Manager (Terraform) | exact | Creates and updates the cloud resources from versioned templates, so every environment is reproducible. |
| Build | Build and test | `ci-build` | Cloud Build | exact | Builds and tests each commit, then packages the app as a container image. |
| Ship | Container images | `container-registry` | Artifact Registry | exact | Keeps versioned, scanned images so every environment runs exactly what was tested. |
| Ship | GitOps release | `cd-deploy` | Cloud Deploy | exact | Rolls new versions out to the cluster from Git, with health checks and automatic rollback. |
| Serve | Domain | `dns` | Cloud DNS | exact | _Generic: Domain name resolution and routing._ |
| Serve | Web firewall | `waf` | Google Cloud Armor | exact | Blocks bots and common attacks before they reach the cluster. |
| Serve | Cluster ingress | `load-balancer` | Cloud Load Balancing (Application LB) | exact | One HTTPS entry point that routes paths to the right microservice. |
| Run | API microservices | `kubernetes` | Google Kubernetes Engine (GKE) | exact | Several independently deployed services share one cluster; Kubernetes gives rolling updates, autoscaling and the same deployment model on every cloud. |
| Run | Order workers | `kubernetes` | Google Kubernetes Engine (GKE) | exact | Long-running order jobs run as worker pods that scale independently of the API. |
| Run | Scale on backlog | `event-autoscaling` | KEDA on GKE | close | Adds or removes workers as the backlog grows or shrinks, down to zero when idle. |
| Integrate | Order queue | `message-queue` | Pub/Sub | close | Checkout returns immediately while order processing happens in the background; failed orders are retried. |
| Store | Orders and catalogue | `relational-db` | Cloud SQL for PostgreSQL | exact | Orders, payments and inventory need transactions and joins; a multi-zone primary meets the 99.95% target. |
| Store | Sessions and hot catalogue | `cache` | Memorystore (Redis / Valkey) | exact | Keeps sessions and popular product pages in memory so the database handles fewer reads. |
| Store | Product images | `object-storage` | Cloud Storage | exact | _Generic: Durable storage for files and blobs._ |
| Operate | Customer accounts | `identity` | Identity Platform | exact | _Generic: User sign-up, sign-in and tokens._ |
| Operate | Service credentials | `secrets` | Secret Manager | exact | _Generic: Stores and rotates credentials._ |
| Operate | Logs, metrics, traces | `monitoring` | Cloud Monitoring + Cloud Logging | exact | _Generic: Metrics, logs, dashboards and alarms._ |

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

- API microservices → Identity Platform: verify token
- API microservices → Secret Manager

## Trade-offs and alternatives

- **Google Kubernetes Engine (GKE)** (API microservices): alternatives: GKE Autopilot
- **Pub/Sub** (Order queue): alternatives: Cloud Tasks; Pub/Sub is publish/subscribe; a single subscription behaves like a queue. Cloud Tasks suits explicit task dispatch with rate limits.
- **Google Kubernetes Engine (GKE)** (Order workers): alternatives: GKE Autopilot
- **Cloud SQL for PostgreSQL** (Orders and catalogue): alternatives: AlloyDB for PostgreSQL
- **Identity Platform** (Customer accounts): alternatives: Firebase Authentication
- **Secure Source Manager** (App and infrastructure code): alternatives: GitHub or GitLab via Developer Connect
- **Infrastructure Manager (Terraform)** (Infrastructure as code): alternatives: Terraform or OpenTofu; A managed service that runs Terraform configurations.
- **KEDA on GKE** (Scale on backlog): KEDA is an open-source add-on you install on GKE. Cloud Run already scales on requests and events without it.

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

---
Cost estimates arrive in a later phase. Service names belong to their owners; CloudArchie is not affiliated with any cloud provider.
