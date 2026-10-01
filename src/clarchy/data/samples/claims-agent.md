# Claims triage agent

An AI agent that helps the claims team of a UK motor insurer triage new claims.

- About 1,500 employees in the claims team sign in with the company single sign-on. Around 25,000 new claims arrive each month through the web portal and partner APIs.
- For each new claim, an agent built with LangGraph reads the first notification of loss and the uploaded photos and documents, looks up the policy and the customer's claim history through our policy and claims APIs, checks the claim against the policy wording retrieved from our policy documents (RAG), and suggests a priority, a reserve and the next steps.
- The claims handler always makes the decision; the agent never pays or declines a claim on its own.
- Models are routed through LiteLLM between Azure OpenAI and a smaller model for document extraction, with token budgets per team. Every agent run is traced in Langfuse, with evals on a weekly sample of claims.
- Personal data in prompts must be masked, and the agent must not follow instructions hidden in uploaded documents.
- Claim files and agent recommendations must be kept for 7 years. UK GDPR applies, and the regulator expects us to explain how each claim was handled.
- 99.9% availability during business hours. 8 developers maintain it. Budget is about $6,000 per month.
