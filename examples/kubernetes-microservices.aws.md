# Microservices on Kubernetes on AWS

Containerised microservices on a managed Kubernetes cluster, with queue-driven workers that scale on backlog and a GitOps release flow.

> AWS mappings have not yet been reviewed by a specialist. Check the service choices before relying on them.

## Requirements

- **Region:** Ireland (eu-west-1)
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
| Code | App and infrastructure code | `source-control` | GitHub or GitLab via AWS CodeConnections | partial | Every change starts as a reviewed commit; the same repository holds the application and its infrastructure code. |
| Code | Infrastructure as code | `iac` | AWS CloudFormation | exact | Creates and updates the cloud resources from versioned templates, so every environment is reproducible. |
| Build | Build and test | `ci-build` | AWS CodeBuild | exact | Builds and tests each commit, then packages the app as a container image. |
| Ship | Container images | `container-registry` | Amazon ECR | exact | Keeps versioned, scanned images so every environment runs exactly what was tested. |
| Ship | GitOps release | `cd-deploy` | AWS CodePipeline | exact | Rolls new versions out to the cluster from Git, with health checks and automatic rollback. |
| Serve | Domain | `dns` | Amazon Route 53 | exact | _Generic: Domain name resolution and routing._ |
| Serve | Web firewall | `waf` | AWS WAF | exact | Blocks bots and common attacks before they reach the cluster. |
| Serve | Cluster ingress | `load-balancer` | Application Load Balancer | exact | One HTTPS entry point that routes paths to the right microservice. |
| Run | API microservices | `kubernetes` | Amazon EKS | exact | Several independently deployed services share one cluster; Kubernetes gives rolling updates, autoscaling and the same deployment model on every cloud. |
| Run | Order workers | `kubernetes` | Amazon EKS | exact | Long-running order jobs run as worker pods that scale independently of the API. |
| Run | Scale on backlog | `event-autoscaling` | KEDA on Amazon EKS | close | Adds or removes workers as the backlog grows or shrinks, down to zero when idle. |
| Integrate | Order queue | `message-queue` | Amazon SQS | exact | Checkout returns immediately while order processing happens in the background; failed orders are retried. |
| Store | Orders and catalogue | `relational-db` | Amazon RDS for PostgreSQL | exact | Orders, payments and inventory need transactions and joins; a multi-zone primary meets the 99.95% target. |
| Store | Sessions and hot catalogue | `cache` | Amazon ElastiCache (Redis OSS / Valkey) | exact | Keeps sessions and popular product pages in memory so the database handles fewer reads. |
| Store | Product images | `object-storage` | Amazon S3 | exact | _Generic: Durable storage for files and blobs._ |
| Operate | Customer accounts | `identity` | Amazon Cognito | exact | _Generic: User sign-up, sign-in and tokens._ |
| Operate | Service credentials | `secrets` | AWS Secrets Manager | exact | _Generic: Stores and rotates credentials._ |
| Operate | Logs, metrics, traces | `monitoring` | Amazon CloudWatch | exact | _Generic: Metrics, logs, dashboards and alarms._ |

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

- API microservices → Amazon Cognito: verify token
- API microservices → AWS Secrets Manager

## Trade-offs and alternatives

- **Amazon Route 53** (Domain): alternatives: Cloudflare DNS
- **AWS WAF** (Web firewall): alternatives: Cloudflare WAF
- **Amazon EKS** (API microservices): alternatives: EKS Auto Mode
- **Amazon EKS** (Order workers): alternatives: EKS Auto Mode
- **Amazon RDS for PostgreSQL** (Orders and catalogue): alternatives: Amazon Aurora PostgreSQL
- **GitHub or GitLab via AWS CodeConnections** (App and infrastructure code): alternatives: AWS CodeCommit; Most teams host code on GitHub or GitLab and connect it to AWS pipelines with CodeConnections. Check AWS CodeCommit's current availability before choosing it.
- **AWS CodeBuild** (Build and test): alternatives: GitHub Actions
- **AWS CodePipeline** (GitOps release): alternatives: AWS CodeDeploy, GitHub Actions
- **AWS CloudFormation** (Infrastructure as code): alternatives: AWS CDK, Terraform or OpenTofu
- **KEDA on Amazon EKS** (Scale on backlog): alternatives: Application Auto Scaling (ECS); KEDA is an open-source CNCF project you install on EKS. For ECS services, Application Auto Scaling with queue-based target tracking does a similar job.

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

About **$2,309 a month** on demand (Europe (Ireland) list prices as of 2026-10-03; AWS Price List API).

| Period | On demand | With commitments |
|---|---:|---:|
| 1 month | $2,309 | – |
| 6 months | $13,861 | – |
| 1 year | $27,742 | $25,440 |
| 3 years | $83,474 | $71,008 |

| Service | Per month |
|---|---:|
| Amazon Cognito (Customer accounts) | $1,045 |
| Amazon RDS for PostgreSQL (Orders and catalogue) | $348 |
| Amazon EKS (API microservices) | $206 |
| Amazon ElastiCache (Redis OSS / Valkey) (Sessions and hot catalogue) | $203 |
| AWS WAF (Web firewall) | $190 |
| Amazon EKS (Order workers) | $133 |
| Amazon CloudWatch (Logs, metrics, traces) | $65.55 |
| Amazon SQS (Order queue) | $47.60 |
| Application Load Balancer (Cluster ingress) | $35.92 |
| AWS Secrets Manager (Service credentials) | $17.77 |
| Amazon S3 (Product images) | $11.72 |
| Amazon Route 53 (Domain) | $2.90 |
| AWS CodeBuild (Build and test) | $1.00 |
| AWS CodePipeline (GitOps release) | $1.00 |
| Amazon ECR (Container images) | $0.50 |

- Compute Savings Plans: 1- or 3-year commitment to an hourly compute spend, no upfront payment; covers Fargate, Lambda and EC2 nodes.
- RDS reserved instances: 1 year no upfront, or 3 years partial upfront with the upfront fee spread over the term.
- ElastiCache reserved nodes: 1 or 3 years, no upfront payment.
- Usage comes from each component's sizing and the requirements; edit it in the Spec tab.
- 730 hours a month. Always-free allowances are deducted where shown; trials are not.
- Excludes tax, support plans, and data transfer not listed.

---
Estimates use list prices and the usage stated above; check them with the provider's calculator. Service names belong to their owners; Clarchy is not affiliated with any cloud provider.
