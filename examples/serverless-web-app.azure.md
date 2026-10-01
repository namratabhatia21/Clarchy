# Serverless web app on Azure

Single-page app with a serverless API, for spiky or low traffic where paying per request beats paying for idle servers.

> Azure mappings have not yet been reviewed by a specialist. Check the service choices before relying on them.

## Requirements

- **Region:** Virginia (eastus)
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
| Code | App and infrastructure code | `source-control` | Azure Repos | exact | Every change starts as a reviewed commit; the same repository holds the application and its infrastructure code. |
| Code | Infrastructure as code | `iac` | Bicep | exact | Creates and updates the cloud resources from versioned templates, so every environment is reproducible. |
| Build | Build and test | `ci-build` | Azure Pipelines | exact | Builds and tests each commit, then packages the functions. |
| Ship | Release pipeline | `cd-deploy` | Azure Pipelines (release stages) | exact | Promotes each build through test and production with approvals and rollback. |
| Serve | Domain | `dns` | Azure DNS | exact | Managed DNS with health checks; also issues the custom domain for the CDN. |
| Serve | Static site + API edge | `cdn` | Azure Front Door | exact | Serves the static front end from edge locations and keeps egress cheaper than serving from origin. |
| Serve | REST API | `api-gateway` | Azure API Management | exact | Auth, throttling and routing without running a server; pay per request. |
| Run | Business logic | `serverless-function` | Azure Functions | exact | Spiky traffic and scale-to-zero make per-invocation billing cheaper than always-on containers. |
| Store | Front-end assets | `object-storage` | Azure Blob Storage | exact | Static files need no servers; the CDN reads them privately. |
| Store | App data | `key-value-db` | Azure Cosmos DB | exact | Access patterns are simple key lookups; on-demand capacity scales with traffic and has no idle cost. |
| Operate | Sign-up and sign-in | `identity` | Microsoft Entra External ID | exact | Managed user pool avoids building password storage and token handling yourself. |
| Operate | Logs, metrics, alarms | `monitoring` | Azure Monitor + Application Insights | exact | _Generic: Metrics, logs, dashboards and alarms._ |

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

- REST API → Microsoft Entra External ID: verify token

## Trade-offs and alternatives

- **Azure Front Door** (Static site + API edge): Front Door combines CDN, global HTTP load balancing and an optional WAF in one service.
- **Azure Cosmos DB** (App data): alternatives: Azure Table Storage
- **Azure Repos** (App and infrastructure code): alternatives: GitHub
- **Azure Pipelines** (Build and test): alternatives: GitHub Actions
- **Azure Pipelines (release stages)** (Release pipeline): alternatives: GitHub Actions environments; The same Azure Pipelines definition usually builds and deploys.
- **Bicep** (Infrastructure as code): alternatives: ARM templates, Terraform or OpenTofu

## Sizing assumptions

- **Static site + API edge:** egress_gb_per_month=100, requests_per_month=5000000
- **Front-end assets:** storage_gb=1
- **REST API:** requests_per_month=3000000
- **Business logic:** invocations_per_month=3000000, avg_duration_ms=120, memory_mb=512
- **App data:** storage_gb=20, reads_per_month=6000000, writes_per_month=1000000
- **Sign-up and sign-in:** monthly_active_users=20000
- **Logs, metrics, alarms:** log_ingest_gb_per_month=5

---
Cost estimates arrive in a later phase. Service names belong to their owners; CloudArchie is not affiliated with any cloud provider.
