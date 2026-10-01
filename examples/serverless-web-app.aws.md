# Serverless web app on AWS

Single-page app with a serverless API, for spiky or low traffic where paying per request beats paying for idle servers.

> AWS mappings have not yet been reviewed by a specialist. Check the service choices before relying on them.

## Requirements

- **Region:** N. Virginia (us-east-1)
- **Monthly active users:** 20000
- **Peak requests/second:** 30
- **Data stored (GB):** 20
- **Data growth (GB/month):** 2
- **Availability target:** 99.9%
- **Compliance:** none stated

## Services

| Stage | Component | Capability | Service | Fidelity | Why |
|---|---|---|---|---|---|
| Users | Users (browser) | `client` | (outside the cloud) | - | _Generic: People or systems outside the cloud that use the application._ |
| Code | App and infrastructure code | `source-control` | GitHub or GitLab via AWS CodeConnections | partial | Every change starts as a reviewed commit; the same repository holds the application and its infrastructure code. |
| Code | Infrastructure as code | `iac` | AWS CloudFormation | exact | Creates and updates the cloud resources from versioned templates, so every environment is reproducible. |
| Build | Build and test | `ci-build` | AWS CodeBuild | exact | Builds and tests each commit, then packages the functions. |
| Ship | Release pipeline | `cd-deploy` | AWS CodePipeline | exact | Promotes each build through test and production with approvals and rollback. |
| Serve | Domain | `dns` | Amazon Route 53 | exact | Managed DNS with health checks; also issues the custom domain for the CDN. |
| Serve | Static site + API edge | `cdn` | Amazon CloudFront | exact | Serves the static front end from edge locations and keeps egress cheaper than serving from origin. |
| Serve | REST API | `api-gateway` | Amazon API Gateway | exact | Auth, throttling and routing without running a server; pay per request. |
| Run | Business logic | `serverless-function` | AWS Lambda | exact | Spiky traffic and scale-to-zero make per-invocation billing cheaper than always-on containers. |
| Store | Front-end assets | `object-storage` | Amazon S3 | exact | Static files need no servers; the CDN reads them privately. |
| Store | App data | `key-value-db` | Amazon DynamoDB | exact | Access patterns are simple key lookups; on-demand capacity scales with traffic and has no idle cost. |
| Operate | Sign-up and sign-in | `identity` | Amazon Cognito | exact | Managed user pool avoids building password storage and token handling yourself. |
| Operate | Logs, metrics, alarms | `monitoring` | Amazon CloudWatch | exact | _Generic: Metrics, logs, dashboards and alarms._ |

## Workflows

### Serving a request

1. Users (browser) → Domain: look up the app's address
2. Users (browser) → Static site + API edge: load the app through the CDN (HTTPS)
3. Static site + API edge → Front-end assets: serve the site's files
4. Static site + API edge → REST API: forward API calls
5. REST API → Business logic: run the function
6. REST API → Sign-up and sign-in: verify the user's sign-in token
7. Business logic → App data: read and write items
8. Every component → Logs, metrics, alarms: send logs and metrics

### Shipping a change

1. A developer → App and infrastructure code: push a reviewed change
2. App and infrastructure code → Build and test: start a build on every push
3. Build and test → Release pipeline: hand over the tested package
4. Release pipeline → Infrastructure as code: apply infrastructure changes
5. Release pipeline → Business logic: roll out the new version

## Shared services used

- REST API → Amazon Cognito: verify token

## Trade-offs and alternatives

- **GitHub or GitLab via AWS CodeConnections** (App and infrastructure code): alternatives: AWS CodeCommit; Most teams host code on GitHub or GitLab and connect it to AWS pipelines with CodeConnections. Check AWS CodeCommit's current availability before choosing it.
- **AWS CodeBuild** (Build and test): alternatives: GitHub Actions
- **AWS CodePipeline** (Release pipeline): alternatives: AWS CodeDeploy, GitHub Actions
- **AWS CloudFormation** (Infrastructure as code): alternatives: AWS CDK, Terraform or OpenTofu

## Sizing assumptions

- **Static site + API edge:** egress_gb_per_month=100, requests_per_month=5000000
- **Front-end assets:** storage_gb=1
- **REST API:** requests_per_month=3000000
- **Business logic:** invocations_per_month=3000000, avg_duration_ms=120, memory_mb=512
- **App data:** storage_gb=20, reads_per_month=6000000, writes_per_month=1000000
- **Sign-up and sign-in:** monthly_active_users=20000
- **Logs, metrics, alarms:** log_ingest_gb_per_month=5

## Estimated cost

About **$83.56 a month** on demand (US East (N. Virginia) list prices as of 2026-10-01; AWS Price List API).

| Period | On demand | With commitments |
|---|---:|---:|
| 1 month | $83.56 | – |
| 6 months | $502 | – |
| 1 year | $1,006 | – |
| 3 years | $3,037 | – |

| Service | Per month |
|---|---:|
| Amazon Cognito (Sign-up and sign-in) | $55.00 |
| Amazon CloudFront (Static site + API edge) | $13.50 |
| Amazon API Gateway (REST API) | $10.50 |
| Amazon DynamoDB (App data) | $1.38 |
| AWS CodeBuild (Build and test) | $1.00 |
| AWS CodePipeline (Release pipeline) | $1.00 |
| Amazon Route 53 (Domain) | $0.74 |
| AWS Lambda (Business logic) | $0.40 |
| Amazon S3 (Front-end assets) | $0.04 |
| Amazon CloudWatch (Logs, metrics, alarms) | $0.00 |

- Compute Savings Plans: 1- or 3-year commitment to an hourly compute spend, no upfront payment; covers Fargate, Lambda and EC2 nodes.
- Usage comes from each component's sizing and the requirements; edit it in the Spec tab.
- 730 hours a month. Always-free allowances are deducted where shown; trials are not.
- Excludes tax, support plans, and data transfer not listed.

---
Estimates use list prices and the usage stated above; check them with the provider's calculator. Service names belong to their owners; Clarchy is not affiliated with any cloud provider.
