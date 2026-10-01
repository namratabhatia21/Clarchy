# Claims agent

An AI agent that helps insurance adjusters handle claims.

Requirements:
1. 1,500 adjusters in the UK sign in with the company single sign-on.
2. The agent is built with LangGraph: it reads a claim, looks up the policy, calls our claims and policy APIs as tools and drafts a decision for the adjuster to review.
3. Its answers must cite the policy wording, retrieved from our policy documents (RAG).
4. We use LiteLLM to route between Azure OpenAI and a cheaper model, with fallbacks and token budgets per team.
5. Every agent run is traced in Langfuse, with evals on a sample of decisions.
6. GDPR applies and the service needs 99.9% availability. Budget is about $3,000 per month.
