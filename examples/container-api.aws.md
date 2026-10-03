# Containerised API on AWS

Always-on containerised web API with a relational database and cache, for steady traffic and existing Docker apps.

> AWS mappings have not yet been reviewed by a specialist. Check the service choices before relying on them.

## Requirements

- **Region:** Ireland (eu-west-1)
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
| Code | App and infrastructure code | `source-control` | GitHub or GitLab via AWS CodeConnections | partial | Every change starts as a reviewed commit; the same repository holds the application and its infrastructure code. |
| Code | Infrastructure as code | `iac` | AWS CloudFormation | exact | Creates and updates the cloud resources from versioned templates, so every environment is reproducible. |
| Build | Build and test | `ci-build` | AWS CodeBuild | exact | Builds and tests each commit, then packages the app as a container image. |
| Ship | Container images | `container-registry` | Amazon ECR | exact | Keeps versioned, scanned images so every environment runs exactly what was tested. |
| Ship | Release pipeline | `cd-deploy` | AWS CodePipeline | exact | Promotes each build through test and production with approvals and rollback. |
| Serve | Domain | `dns` | Amazon Route 53 | exact | _Generic: Domain name resolution and routing._ |
| Serve | Web firewall | `waf` | AWS WAF | exact | Blocks common attacks (SQL injection, bad bots) before they reach the app. |
| Serve | HTTPS load balancer | `load-balancer` | Application Load Balancer | exact | Spreads traffic across containers in two availability zones and terminates TLS. |
| Run | API containers | `container-service` | Amazon ECS on AWS Fargate | exact | Steady traffic and long-lived connections favour always-on containers; reuses the existing Docker image. |
| Store | Session + query cache | `cache` | Amazon ElastiCache (Redis OSS / Valkey) | exact | Cuts database reads for hot data and keeps p95 latency low. |
| Store | PostgreSQL | `relational-db` | Amazon RDS for PostgreSQL | exact | Relational data with joins and transactions; Multi-AZ meets the 99.9% target. |
| Store | Uploads | `object-storage` | Amazon S3 | exact | _Generic: Durable storage for files and blobs._ |
| Operate | DB credentials | `secrets` | AWS Secrets Manager | exact | Rotated credentials instead of passwords in environment files. |
| Operate | Logs, metrics, alarms | `monitoring` | Amazon CloudWatch | exact | _Generic: Metrics, logs, dashboards and alarms._ |

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

- API containers → AWS Secrets Manager

## Trade-offs and alternatives

- **Amazon Route 53** (Domain): alternatives: Cloudflare DNS
- **AWS WAF** (Web firewall): alternatives: Cloudflare WAF
- **Amazon ECS on AWS Fargate** (API containers): alternatives: Amazon EKS, AWS App Runner
- **Amazon RDS for PostgreSQL** (PostgreSQL): alternatives: Amazon Aurora PostgreSQL
- **GitHub or GitLab via AWS CodeConnections** (App and infrastructure code): alternatives: AWS CodeCommit; Most teams host code on GitHub or GitLab and connect it to AWS pipelines with CodeConnections. Check AWS CodeCommit's current availability before choosing it.
- **AWS CodeBuild** (Build and test): alternatives: GitHub Actions
- **AWS CodePipeline** (Release pipeline): alternatives: AWS CodeDeploy, GitHub Actions
- **AWS CloudFormation** (Infrastructure as code): alternatives: AWS CDK, Terraform or OpenTofu

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

About **$606 a month** on demand (Europe (Ireland) list prices as of 2026-10-03; AWS Price List API).

| Period | On demand | With commitments |
|---|---:|---:|
| 1 month | $606 | – |
| 6 months | $3,640 | – |
| 1 year | $7,292 | $6,043 |
| 3 years | $22,025 | $14,687 |

| Service | Per month |
|---|---:|
| Amazon RDS for PostgreSQL (PostgreSQL) | $322 |
| Amazon ECS on AWS Fargate (API containers) | $108 |
| Amazon ElastiCache (Redis OSS / Valkey) (Session + query cache) | $79.42 |
| AWS WAF (Web firewall) | $40.00 |
| Application Load Balancer (HTTPS load balancer) | $24.24 |
| Amazon CloudWatch (Logs, metrics, alarms) | $14.25 |
| Amazon S3 (Uploads) | $7.03 |
| AWS Secrets Manager (DB credentials) | $6.73 |
| Amazon Route 53 (Domain) | $1.10 |
| AWS CodeBuild (Build and test) | $1.00 |
| AWS CodePipeline (Release pipeline) | $1.00 |
| Amazon ECR (Container images) | $0.50 |

- Compute Savings Plans: 1- or 3-year commitment to an hourly compute spend, no upfront payment; covers Fargate, Lambda and EC2 nodes.
- RDS reserved instances: 1 year no upfront, or 3 years partial upfront with the upfront fee spread over the term.
- ElastiCache reserved nodes: 1 or 3 years, no upfront payment.
- Usage comes from each component's sizing and the requirements; edit it in the Spec tab.
- 730 hours a month. Always-free allowances are deducted where shown; trials are not.
- Excludes tax, support plans, and data transfer not listed.

---
Estimates use list prices and the usage stated above; check them with the provider's calculator. Service names belong to their owners; Clarchy is not affiliated with any cloud provider.
