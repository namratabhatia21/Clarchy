# AI agent platform on AWS

Tool-using AI agents behind a chat API, with an LLM gateway for model routing and budgets, retrieval over company documents, and tracing of every model call.

> AWS mappings have not yet been reviewed by a specialist. Check the service choices before relying on them.

## Requirements

- **Region:** N. Virginia (us-east-1)
- **Monthly active users:** 5000
- **Peak requests/second:** 10
- **Data stored (GB):** 100
- **Data growth (GB/month):** 5
- **Availability target:** 99.9%
- **Compliance:** none stated

## Services

| Stage | Component | Capability | Service | Fidelity | Why |
|---|---|---|---|---|---|
| Users | Employees (browser) | `client` | (outside the cloud) | - | _Generic: People or systems outside the cloud that use the application._ |
| Code | App and infrastructure code | `source-control` | GitHub or GitLab via AWS CodeConnections | partial | Every change starts as a reviewed commit; the same repository holds the application, the agent graphs and the infrastructure code. |
| Code | Infrastructure as code | `iac` | AWS CloudFormation | exact | Creates and updates the cloud resources from versioned templates, so every environment is reproducible. |
| Build | Build, test and evaluate | `ci-build` | AWS CodeBuild | exact | Builds and tests each commit and runs the agent's evaluation set, then packages the services as container images and the functions as bundles. |
| Ship | Container images | `container-registry` | Amazon ECR | exact | Keeps versioned, scanned images so every environment runs exactly what was tested. |
| Ship | Release pipeline | `cd-deploy` | AWS CodePipeline | exact | Promotes each build through test and production with approvals and rollback. |
| Serve | Web front end | `cdn` | Amazon CloudFront | exact | _Generic: Content delivery network that caches content close to users._ |
| Serve | HTTPS load balancer | `load-balancer` | Application Load Balancer | exact | _Generic: Distributes HTTP traffic across healthy compute instances._ |
| Run | Chat API (streaming) | `container-service` | Amazon ECS on AWS Fargate | exact | Streams agent progress and answers over long-lived connections, which suits containers better than short-lived functions. |
| Run | Agent runtime (LangGraph) | `agent-orchestration` | Amazon Bedrock AgentCore Runtime | close | Runs LangGraph agents that plan, call tools and checkpoint their state, so long tasks survive restarts and can pause for a human to approve. |
| Run | Tool functions | `serverless-function` | AWS Lambda | exact | Small functions the agent calls as tools, such as looking up a record or opening a ticket, each with least-privilege access to one system. |
| Run | Models + embeddings | `llm-inference` | Amazon Bedrock | exact | Managed models behind the gateway; a larger model plans and a smaller one handles routine steps, billed per token. |
| Run | Chunk + embed documents | `serverless-function` | AWS Lambda | exact | Runs only when documents change. |
| Integrate | LLM gateway (LiteLLM) | `llm-gateway` | LiteLLM on Amazon ECS (AWS gateway guidance) | close | One OpenAI-compatible API in front of every model, with per-team keys and budgets, fallbacks between providers and response caching. |
| Integrate | AI guardrails | `ai-guardrails` | Amazon Bedrock Guardrails | exact | Screens prompts, tool results and answers for prompt injection, harmful content and personal data. |
| Store | Source documents | `object-storage` | Amazon S3 | exact | _Generic: Durable storage for files and blobs._ |
| Store | Knowledge index | `vector-search` | Amazon OpenSearch Serverless (vector) | close | Lets the agent ground its answers in company documents with hybrid keyword and vector search. |
| Store | Agent state + history | `relational-db` | Amazon RDS for PostgreSQL | exact | Postgres holds the agent checkpoints, chat history and the gateway's spend log in one managed database. |
| Operate | Single sign-on | `identity` | Amazon Cognito | exact | _Generic: User sign-up, sign-in and tokens._ |
| Operate | Model and tool credentials | `secrets` | AWS Secrets Manager | exact | _Generic: Stores and rotates credentials._ |
| Operate | LLM tracing (Langfuse) | `llm-observability` | Amazon CloudWatch generative AI observability | close | Traces every prompt, tool call, token and cost, and scores samples with evals, so regressions show up before users notice them. |
| Operate | Cloud access governance | `access-governance` | AWS IAM Identity Center + Organizations | exact | Staff sign in to the cloud with the company directory; the cloud architects approve least-privilege roles, and access is reviewed every quarter. |
| Operate | Audit trail | `audit-logging` | AWS CloudTrail | exact | Records every console change, data access and model call in a log nobody can edit. |
| Operate | Encryption keys | `key-management` | AWS KMS | exact | Customer-managed keys encrypt the database, documents and backups. |
| Operate | Logs, metrics, alarms | `monitoring` | Amazon CloudWatch | exact | _Generic: Metrics, logs, dashboards and alarms._ |

## Workflows

### Serving a request

1. Employees (browser) → Web front end: load the app through the CDN (HTTPS)
2. Web front end → HTTPS load balancer: forward API calls
3. HTTPS load balancer → Chat API (streaming): run the business logic
4. Chat API (streaming) → Agent runtime (LangGraph): hand the request to the agent
5. Chat API (streaming) → Single sign-on: verify the user's sign-in token
6. Agent runtime (LangGraph) → LLM gateway (LiteLLM): send the prompt through the gateway
7. Agent runtime (LangGraph) → Knowledge index: retrieve relevant passages
8. Agent runtime (LangGraph) → Tool functions: call tools that look up or change data
9. Agent runtime (LangGraph) → Agent state + history: save the agent's progress and the conversation
10. Agent runtime (LangGraph) → Model and tool credentials: fetch credentials
11. Agent runtime (LangGraph) → AI guardrails: screen the prompt and the answer
12. LLM gateway (LiteLLM) → Models + embeddings: call the chosen model, falling back to another if it fails
13. Every model call → LLM tracing (Langfuse): record the prompt, tool calls, tokens and cost
14. Every component → Logs, metrics, alarms: send logs and metrics

### Background processing

1. Source documents → Chunk + embed documents: start when a document is uploaded
2. Chunk + embed documents → LLM gateway (LiteLLM): create embeddings
3. Chunk + embed documents → Knowledge index: index the new chunks

### Shipping a change

1. A developer → App and infrastructure code: push a reviewed change
2. App and infrastructure code → Build, test and evaluate: start a build on every push
3. Build, test and evaluate → Container images: publish the tested image
4. Container images → Release pipeline: start the release
5. Release pipeline → Infrastructure as code: apply infrastructure changes
6. Release pipeline → Chat API (streaming), Agent runtime (LangGraph), Tool functions, LLM gateway (LiteLLM), Chunk + embed documents: roll out the new version

## Shared services used

- Chat API (streaming) → Amazon Cognito: verify token
- Agent runtime (LangGraph) → AWS Secrets Manager

## Trade-offs and alternatives

- **Amazon CloudFront** (Web front end): alternatives: Cloudflare
- **Amazon ECS on AWS Fargate** (Chat API (streaming)): alternatives: Amazon EKS, AWS App Runner
- **Amazon Bedrock AgentCore Runtime** (Agent runtime (LangGraph)): alternatives: LangGraph on Amazon ECS, Amazon Bedrock Agents; Hosts agents built with LangGraph, CrewAI or Strands in isolated sessions, billed for active CPU and memory; AgentCore Memory, Gateway and Identity are separate add-ons.
- **LiteLLM on Amazon ECS (AWS gateway guidance)** (LLM gateway (LiteLLM)): alternatives: Amazon Bedrock inference profiles, Amazon API Gateway; AWS has no managed LLM gateway; its multi-provider generative AI gateway guidance runs LiteLLM on ECS. Bedrock on its own gives one API across Bedrock models only.
- **Amazon Bedrock** (Models + embeddings): alternatives: OpenAI API, Anthropic API (Claude), Hugging Face Inference Endpoints
- **Amazon OpenSearch Serverless (vector)** (Knowledge index): alternatives: Aurora PostgreSQL with pgvector, Amazon S3 Vectors; Vector search is one feature of a general search engine; a smaller workload may be cheaper on pgvector in the relational database.
- **Amazon RDS for PostgreSQL** (Agent state + history): alternatives: Amazon Aurora PostgreSQL
- **Amazon CloudWatch generative AI observability** (LLM tracing (Langfuse)): alternatives: Langfuse on AWS, Bedrock model invocation logging; OpenTelemetry traces of agent steps, model calls, tokens and latency; prompt versions and evaluation datasets need AgentCore Evaluations or Langfuse.
- **Amazon Bedrock Guardrails** (AI guardrails): alternatives: NeMo Guardrails, Llama Guard; Content filters, prompt-attack detection, denied topics and PII masking; works with any model through the ApplyGuardrail API.
- **AWS IAM Identity Center + Organizations** (Cloud access governance): alternatives: IAM roles, Service control policies; Staff sign in with the company directory; permission sets per role; service control policies set limits for every account.
- **AWS CloudTrail** (Audit trail): alternatives: CloudTrail Lake; Management events of one trail are free; data events (object reads, function calls, model invocations) are billed per event.
- **AWS KMS** (Encryption keys): alternatives: AWS CloudHSM
- **GitHub or GitLab via AWS CodeConnections** (App and infrastructure code): alternatives: AWS CodeCommit; Most teams host code on GitHub or GitLab and connect it to AWS pipelines with CodeConnections. Check AWS CodeCommit's current availability before choosing it.
- **AWS CodeBuild** (Build, test and evaluate): alternatives: GitHub Actions
- **AWS CodePipeline** (Release pipeline): alternatives: AWS CodeDeploy, GitHub Actions
- **AWS CloudFormation** (Infrastructure as code): alternatives: AWS CDK, Terraform or OpenTofu

## Sizing assumptions

- **Web front end:** egress_gb_per_month=30
- **Chat API (streaming):** vcpu=1, memory_gb=2, tasks=2
- **Agent runtime (LangGraph):** requests_per_month=150000
- **Tool functions:** invocations_per_month=400000, avg_duration_ms=300, memory_mb=512
- **LLM gateway (LiteLLM):** vcpu=0.5, memory_gb=1, tasks=2
- **Models + embeddings:** requests_per_month=450000
- **Source documents:** storage_gb=100
- **Chunk + embed documents:** invocations_per_month=50000, avg_duration_ms=3000, memory_mb=1024
- **Agent state + history:** storage_gb=50
- **Single sign-on:** monthly_active_users=5000
- **LLM tracing (Langfuse):** requests_per_month=150000
- **Logs, metrics, alarms:** log_ingest_gb_per_month=20

## Estimated cost

About **$1,071 a month** on demand (US East (N. Virginia) list prices as of 2026-10-01; AWS Price List API).

| Period | On demand | With commitments |
|---|---:|---:|
| 1 month | $1,071 | – |
| 6 months | $6,425 | – |
| 1 year | $12,855 | $12,280 |
| 3 years | $38,614 | $35,102 |

| Service | Per month |
|---|---:|
| Amazon OpenSearch Serverless (vector) (Knowledge index) | $350 |
| Amazon Bedrock Guardrails (AI guardrails) | $338 |
| Amazon RDS for PostgreSQL (Agent state + history) | $106 |
| Amazon Bedrock (Models + embeddings) | $84.07 |
| Amazon ECS on AWS Fargate (Chat API (streaming)) | $72.08 |
| LiteLLM on Amazon ECS (AWS gateway guidance) (LLM gateway (LiteLLM)) | $36.04 |
| Amazon Bedrock AgentCore Runtime (Agent runtime (LangGraph)) | $30.67 |
| Application Load Balancer (HTTPS load balancer) | $22.27 |
| AWS KMS (Encryption keys) | $9.67 |
| Amazon CloudWatch (Logs, metrics, alarms) | $7.50 |
| Amazon CloudFront (Web front end) | $4.05 |
| AWS Secrets Manager (Model and tool credentials) | $2.39 |
| Amazon S3 (Source documents) | $2.34 |
| Amazon CloudWatch generative AI observability (LLM tracing (Langfuse)) | $1.88 |
| AWS CloudTrail (Audit trail) | $1.58 |
| AWS CodeBuild (Build, test and evaluate) | $1.00 |
| AWS CodePipeline (Release pipeline) | $1.00 |
| Amazon ECR (Container images) | $0.50 |
| AWS Lambda (Tool functions) | $0.00 |
| AWS Lambda (Chunk + embed documents) | $0.00 |
| Amazon Cognito (Single sign-on) | $0.00 |

- Compute Savings Plans: 1- or 3-year commitment to an hourly compute spend, no upfront payment; covers Fargate, Lambda and EC2 nodes.
- RDS reserved instances: 1 year no upfront, or 3 years partial upfront with the upfront fee spread over the term.
- Usage comes from each component's sizing and the requirements; edit it in the Spec tab.
- 730 hours a month. Always-free allowances are deducted where shown; trials are not.
- Excludes tax, support plans, and data transfer not listed.

---
Estimates use list prices and the usage stated above; check them with the provider's calculator. Service names belong to their owners; Clarchy is not affiliated with any cloud provider.
