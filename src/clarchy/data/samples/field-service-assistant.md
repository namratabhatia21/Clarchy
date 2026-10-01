# Field service assistant for wind turbines

An internal AI assistant for a company that maintains wind turbines, so technicians and planners stop searching three systems for a turbine's open service orders, its fault history and the right procedure.

Who uses it
- About 6,000 people use it: technicians, planners and engineers at our sites in Germany and Denmark. Everyone signs in with the company's Microsoft Entra ID single sign-on, and the assistant only shows service orders the person can already see in the maintenance system.
- They use it in a chat window on tablets in the field and in Microsoft Teams. Peak usage is the start of the morning shift, about 40 requests per second, and answers stream back as they are generated.

What it does
- Answers questions such as "which orders are open on turbine WT-114?" with links to the orders.
- An AI agent built with LangGraph calls the maintenance system's REST API as tools: it queries service orders, reads fault logs and drafts shift reports. A person must confirm before anything is written back.
- Questions about procedures are answered from the maintenance manuals, about 2,500 pages, with citations (RAG).

Models and operations
- Models are routed through LiteLLM to Azure OpenAI, with a cheaper model for simple lookups, fallbacks and token budgets per team.
- Every agent run is traced in Langfuse, and we run evals before each release.
- Prompts and answers must not leak personal data, and the agent must resist prompt injection hidden in order text.

Security and records
- Access to the cloud accounts is granted through IAM roles with approval; administrators get just-in-time access, reviewed every quarter.
- All admin actions and data access are audited, and data is encrypted with customer-managed keys.
- Chat history is kept for 1 year and audit logs for 7 years.
- GDPR applies, and employees must always be told they are talking to an AI. The environment is ISO 27001 certified. 99.9% availability.

Team and budget
- 8 developers build and run it; they work in GitHub Codespaces and use GitHub Copilot.
- Budget is about $9,000 per month.
