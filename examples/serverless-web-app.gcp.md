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

| Component | Capability | Service | Fidelity | Why |
|---|---|---|---|---|
| Users (browser) | `client` | (outside the cloud) | - | _Generic: People or systems outside the cloud that use the application._ |
| Domain | `dns` | Cloud DNS | exact | Managed DNS with health checks; also issues the custom domain for the CDN. |
| Static site + API edge | `cdn` | Cloud CDN | close | Serves the static front end from edge locations and keeps egress cheaper than serving from origin. |
| Front-end assets | `object-storage` | Cloud Storage | exact | Static files need no servers; the CDN reads them privately. |
| REST API | `api-gateway` | API Gateway | close | Auth, throttling and routing without running a server; pay per request. |
| Business logic | `serverless-function` | Cloud Run functions | exact | Spiky traffic and scale-to-zero make per-invocation billing cheaper than always-on containers. |
| App data | `key-value-db` | Firestore | close | Access patterns are simple key lookups; on-demand capacity scales with traffic and has no idle cost. |
| Sign-up and sign-in | `identity` | Identity Platform | exact | Managed user pool avoids building password storage and token handling yourself. |
| Logs, metrics, alarms | `monitoring` | Cloud Monitoring + Cloud Logging | exact | _Generic: Metrics, logs, dashboards and alarms._ |

## Shared services used

- REST API → Identity Platform: verify token

## Trade-offs and alternatives

- **Cloud CDN** (Static site + API edge): alternatives: Media CDN; Cloud CDN is enabled on an external Application Load Balancer rather than deployed on its own.
- **API Gateway** (REST API): alternatives: Apigee; Lighter than Amazon API Gateway or Azure API Management; Apigee is the full-featured option.
- **Firestore** (App data): alternatives: Bigtable; A document database with a different query and pricing model from DynamoDB; Bigtable suits very high-throughput wide-column data.
- **Identity Platform** (Sign-up and sign-in): alternatives: Firebase Authentication

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
