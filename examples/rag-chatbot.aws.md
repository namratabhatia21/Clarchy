# RAG chatbot on AWS

Chat assistant that answers from your own documents using retrieval-augmented generation with a managed LLM.

> AWS mappings have not yet been reviewed by a specialist. Check the service choices before relying on them.

## Requirements

- **Region:** Oregon (us-west-2)
- **Monthly active users:** 2000
- **Peak requests/second:** 5
- **Data stored (GB):** 50
- **Data growth (GB/month):** 5
- **Availability target:** 99.9%
- **Compliance:** none stated

## Services

| Stage | Component | Capability | Service | Fidelity | Why |
|---|---|---|---|---|---|
| Users | Employees (browser) | `client` | (outside the cloud) | - | _Generic: People or systems outside the cloud that use the application._ |
| Code | App and infrastructure code | `source-control` | GitHub or GitLab via AWS CodeConnections | partial | Every change starts as a reviewed commit; the same repository holds the application and its infrastructure code. |
| Code | Infrastructure as code | `iac` | AWS CloudFormation | exact | Creates and updates the cloud resources from versioned templates, so every environment is reproducible. |
| Build | Build and test | `ci-build` | AWS CodeBuild | exact | Builds and tests each commit, then packages the services as container images and the functions as bundles. |
| Ship | Container images | `container-registry` | Amazon ECR | exact | Keeps versioned, scanned images so every environment runs exactly what was tested. |
| Ship | Release pipeline | `cd-deploy` | AWS CodePipeline | exact | Promotes each build through test and production with approvals and rollback. |
| Serve | Web front end | `cdn` | Amazon CloudFront | exact | _Generic: Content delivery network that caches content close to users._ |
| Serve | HTTPS load balancer | `load-balancer` | Application Load Balancer | exact | _Generic: Distributes HTTP traffic across healthy compute instances._ |
| Run | Chat API (streaming) | `container-service` | Amazon ECS on AWS Fargate | exact | Streaming responses hold connections for many seconds, which suits containers better than short-lived functions. |
| Run | LLM + embeddings | `llm-inference` | Amazon Bedrock | exact | Managed models avoid hosting GPUs; pay per token. |
| Run | Chunk + embed documents | `serverless-function` | AWS Lambda | exact | Runs only when documents change. |
| Store | Source documents | `object-storage` | Amazon S3 | exact | _Generic: Durable storage for files and blobs._ |
| Store | Embeddings index | `vector-search` | Amazon OpenSearch Serverless (vector) | close | Similarity search over document chunks; hybrid keyword + vector improves recall. |
| Store | Chat history | `key-value-db` | Amazon DynamoDB | exact | _Generic: Serverless key-value / document database with single-digit ms reads._ |
| Operate | Single sign-on | `identity` | Amazon Cognito | exact | _Generic: User sign-up, sign-in and tokens._ |
| Operate | Logs, traces, cost alarms | `monitoring` | Amazon CloudWatch | exact | _Generic: Metrics, logs, dashboards and alarms._ |

## Workflows

### Serving a request

1. Employees (browser) → Web front end: load the app through the CDN (HTTPS)
2. Web front end → HTTPS load balancer: forward API calls
3. HTTPS load balancer → Chat API (streaming): run the business logic
4. Chat API (streaming) → Embeddings index: retrieve relevant passages
5. Chat API (streaming) → LLM + embeddings: generate the answer
6. Chat API (streaming) → Chat history: read and write items
7. Chat API (streaming) → Single sign-on: verify the user's sign-in token
8. Every component → Logs, traces, cost alarms: send logs and metrics

### Background processing

1. Source documents → Chunk + embed documents: start when a document is uploaded
2. Chunk + embed documents → LLM + embeddings: create embeddings
3. Chunk + embed documents → Embeddings index: index the new chunks

### Shipping a change

1. A developer → App and infrastructure code: push a reviewed change
2. App and infrastructure code → Build and test: start a build on every push
3. Build and test → Container images: publish the tested image
4. Container images → Release pipeline: start the release
5. Release pipeline → Infrastructure as code: apply infrastructure changes
6. Release pipeline → Chat API (streaming), Chunk + embed documents: roll out the new version

## Shared services used

- Chat API (streaming) → Amazon Cognito: verify token

## Trade-offs and alternatives

- **Amazon CloudFront** (Web front end): alternatives: Cloudflare
- **Amazon ECS on AWS Fargate** (Chat API (streaming)): alternatives: Amazon EKS, AWS App Runner
- **Amazon Bedrock** (LLM + embeddings): alternatives: OpenAI API, Anthropic API (Claude), Hugging Face Inference Endpoints
- **Amazon OpenSearch Serverless (vector)** (Embeddings index): alternatives: Aurora PostgreSQL with pgvector, Amazon S3 Vectors; Vector search is one feature of a general search engine; a smaller workload may be cheaper on pgvector in the relational database.
- **GitHub or GitLab via AWS CodeConnections** (App and infrastructure code): alternatives: AWS CodeCommit; Most teams host code on GitHub or GitLab and connect it to AWS pipelines with CodeConnections. Check AWS CodeCommit's current availability before choosing it.
- **AWS CodeBuild** (Build and test): alternatives: GitHub Actions
- **AWS CodePipeline** (Release pipeline): alternatives: AWS CodeDeploy, GitHub Actions
- **AWS CloudFormation** (Infrastructure as code): alternatives: AWS CDK, Terraform or OpenTofu

## Sizing assumptions

- **Web front end:** egress_gb_per_month=20
- **Chat API (streaming):** vcpu=1, memory_gb=2, tasks=2, hours_per_month=730
- **LLM + embeddings:** input_tokens_per_month=60000000, output_tokens_per_month=8000000, embedding_tokens_per_month=20000000
- **Chunk + embed documents:** invocations_per_month=50000, avg_duration_ms=3000, memory_mb=1024
- **Source documents:** storage_gb=50
- **Embeddings index:** vectors=2000000, dimensions=1024
- **Chat history:** storage_gb=10, reads_per_month=2000000, writes_per_month=1000000
- **Single sign-on:** monthly_active_users=2000
- **Logs, traces, cost alarms:** log_ingest_gb_per_month=15

## Estimated cost

About **$464 a month** on demand (US East (N. Virginia) list prices as of 2026-10-01; AWS Price List API).

| Period | On demand | With commitments |
|---|---:|---:|
| 1 month | $464 | – |
| 6 months | $2,787 | – |
| 1 year | $5,578 | $5,405 |
| 3 years | $16,783 | $15,615 |

| Service | Per month |
|---|---:|
| Amazon OpenSearch Serverless (vector) (Embeddings index) | $350 |
| Amazon ECS on AWS Fargate (Chat API (streaming)) | $72.08 |
| Application Load Balancer (HTTPS load balancer) | $22.27 |
| Amazon Bedrock (LLM + embeddings) | $7.56 |
| Amazon CloudWatch (Logs, traces, cost alarms) | $5.00 |
| Amazon CloudFront (Web front end) | $2.30 |
| Amazon S3 (Source documents) | $1.19 |
| AWS CodeBuild (Build and test) | $1.00 |
| AWS CodePipeline (Release pipeline) | $1.00 |
| Amazon DynamoDB (Chat history) | $0.88 |
| Amazon ECR (Container images) | $0.50 |
| AWS Lambda (Chunk + embed documents) | $0.00 |
| Amazon Cognito (Single sign-on) | $0.00 |

- Compute Savings Plans: 1- or 3-year commitment to an hourly compute spend, no upfront payment; covers Fargate, Lambda and EC2 nodes.
- Usage comes from each component's sizing and the requirements; edit it in the Spec tab.
- 730 hours a month. Always-free allowances are deducted where shown; trials are not.
- Excludes tax, support plans, and data transfer not listed.
- Prices are for US East (N. Virginia); your region (Oregon (us-west-2)) may differ.

---
Estimates use list prices and the usage stated above; check them with the provider's calculator. Service names belong to their owners; Clarchy is not affiliated with any cloud provider.
