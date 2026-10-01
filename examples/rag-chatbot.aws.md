# RAG chatbot on AWS

Chat assistant that answers from your own documents using retrieval-augmented generation with a managed LLM.

## Requirements

- **Region:** US West (Oregon) (us-west-2)
- **Monthly active users:** 2000
- **Peak requests/second:** 5
- **Data stored (GB):** 50
- **Data growth (GB/month):** 5
- **Availability target:** 99.9%
- **Compliance:** none stated

## Services

| Component | Capability | Service | Fidelity | Why |
|---|---|---|---|---|
| Employees (browser) | `client` | (outside the cloud) | - | _Generic: People or systems outside the cloud that use the application._ |
| Web front end | `cdn` | Amazon CloudFront | exact | _Generic: Content delivery network that caches content close to users._ |
| HTTPS load balancer | `load-balancer` | Application Load Balancer | exact | _Generic: Distributes HTTP traffic across healthy compute instances._ |
| Chat API (streaming) | `container-service` | Amazon ECS on AWS Fargate | exact | Streaming responses hold connections for many seconds, which suits containers better than short-lived functions. |
| LLM + embeddings | `llm-inference` | Amazon Bedrock | exact | Managed models avoid hosting GPUs; pay per token. |
| Chunk + embed documents | `serverless-function` | AWS Lambda | exact | Runs only when documents change. |
| Source documents | `object-storage` | Amazon S3 | exact | _Generic: Durable storage for files and blobs._ |
| Embeddings index | `vector-search` | Amazon OpenSearch Serverless (vector) | close | Similarity search over document chunks; hybrid keyword + vector improves recall. |
| Chat history | `key-value-db` | Amazon DynamoDB | exact | _Generic: Serverless key-value / document database with single-digit ms reads._ |
| Single sign-on | `identity` | Amazon Cognito | exact | _Generic: User sign-up, sign-in and tokens._ |
| Logs, traces, cost alarms | `monitoring` | Amazon CloudWatch | exact | _Generic: Metrics, logs, dashboards and alarms._ |

## Shared services used

- Chat API (streaming) → Amazon Cognito: verify token

## Trade-offs and alternatives

- **Amazon ECS on AWS Fargate** (Chat API (streaming)): alternatives: Amazon EKS, AWS App Runner
- **Amazon OpenSearch Serverless (vector)** (Embeddings index): alternatives: Aurora PostgreSQL with pgvector, Amazon S3 Vectors; Vector search is one feature of a general search engine; a smaller workload may be cheaper on pgvector in the relational database.

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

---
Cost estimates arrive in a later phase. Service names belong to their owners; CloudArchie is not affiliated with any cloud provider.
