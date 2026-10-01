# Serverless web app on Google Cloud

Single-page app with a serverless API, for spiky or low traffic where paying per request beats paying for idle servers.

> Google Cloud mappings have not yet been reviewed by a specialist. Check the service choices before relying on them.

## Requirements

- **Region:** N. Virginia (us-east4)
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
| Code | App and infrastructure code | `source-control` | Secure Source Manager | exact | Every change starts as a reviewed commit; the same repository holds the application and its infrastructure code. |
| Code | Infrastructure as code | `iac` | Infrastructure Manager (Terraform) | exact | Creates and updates the cloud resources from versioned templates, so every environment is reproducible. |
| Build | Build and test | `ci-build` | Cloud Build | exact | Builds and tests each commit, then packages the functions. |
| Ship | Release pipeline | `cd-deploy` | Cloud Deploy | exact | Promotes each build through test and production with approvals and rollback. |
| Serve | Domain | `dns` | Cloud DNS | exact | Managed DNS with health checks; also issues the custom domain for the CDN. |
| Serve | Static site + API edge | `cdn` | Cloud CDN | close | Serves the static front end from edge locations and keeps egress cheaper than serving from origin. |
| Serve | REST API | `api-gateway` | API Gateway | close | Auth, throttling and routing without running a server; pay per request. |
| Run | Business logic | `serverless-function` | Cloud Run functions | exact | Spiky traffic and scale-to-zero make per-invocation billing cheaper than always-on containers. |
| Store | Front-end assets | `object-storage` | Cloud Storage | exact | Static files need no servers; the CDN reads them privately. |
| Store | App data | `key-value-db` | Firestore | close | Access patterns are simple key lookups; on-demand capacity scales with traffic and has no idle cost. |
| Operate | Sign-up and sign-in | `identity` | Identity Platform | exact | Managed user pool avoids building password storage and token handling yourself. |
| Operate | Logs, metrics, alarms | `monitoring` | Cloud Monitoring + Cloud Logging | exact | _Generic: Metrics, logs, dashboards and alarms._ |

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

- REST API → Identity Platform: verify token

## Trade-offs and alternatives

- **Cloud DNS** (Domain): alternatives: Cloudflare DNS
- **Cloud CDN** (Static site + API edge): alternatives: Media CDN, Cloudflare; Cloud CDN is enabled on an external Application Load Balancer rather than deployed on its own.
- **API Gateway** (REST API): alternatives: Apigee; Lighter than Amazon API Gateway or Azure API Management; Apigee is the full-featured option.
- **Firestore** (App data): alternatives: Bigtable; A document database with a different query and pricing model from DynamoDB; Bigtable suits very high-throughput wide-column data.
- **Identity Platform** (Sign-up and sign-in): alternatives: Firebase Authentication
- **Secure Source Manager** (App and infrastructure code): alternatives: GitHub or GitLab via Developer Connect
- **Infrastructure Manager (Terraform)** (Infrastructure as code): alternatives: Terraform or OpenTofu; A managed service that runs Terraform configurations.

## Sizing assumptions

- **Static site + API edge:** egress_gb_per_month=100, requests_per_month=5000000
- **Front-end assets:** storage_gb=1
- **REST API:** requests_per_month=3000000
- **Business logic:** invocations_per_month=3000000, avg_duration_ms=120, memory_mb=512
- **App data:** storage_gb=20, reads_per_month=6000000, writes_per_month=1000000
- **Sign-up and sign-in:** monthly_active_users=20000
- **Logs, metrics, alarms:** log_ingest_gb_per_month=5

## Estimated cost

About **$22.18 a month** on demand (Iowa (us-central1) list prices as of 2026-10-01; Google Cloud pricing pages, compiled manually, approximate).

| Period | On demand | With commitments |
|---|---:|---:|
| 1 month | $22.18 | – |
| 6 months | $134 | – |
| 1 year | $269 | – |
| 3 years | $824 | – |

| Service | Per month |
|---|---:|
| Cloud CDN (Static site + API edge) | $11.75 |
| Firestore (App data) | $5.55 |
| API Gateway (REST API) | $3.00 |
| Cloud Monitoring + Cloud Logging (Logs, metrics, alarms) | $1.00 |
| Cloud DNS (Domain) | $0.44 |
| Cloud Run functions (Business logic) | $0.40 |
| Cloud Storage (Front-end assets) | $0.04 |
| Identity Platform (Sign-up and sign-in) | $0.00 |
| Cloud Build (Build and test) | $0.00 |
| Cloud Deploy (Release pipeline) | $0.00 |

- Usage comes from each component's sizing and the requirements; edit it in the Spec tab.
- 730 hours a month. Always-free allowances are deducted where shown; trials are not.
- Excludes tax, support plans, and data transfer not listed.
- Prices are for Iowa (us-central1); your region (N. Virginia (us-east4)) may differ.

---
Estimates use list prices and the usage stated above; check them with the provider's calculator. Service names belong to their owners; Clarchy is not affiliated with any cloud provider.
