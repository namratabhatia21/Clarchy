# Policy assistant

An internal AI assistant that answers employee questions from our HR, IT and travel policy documents.

Requirements:
1. 2,000 employees in Europe sign in with the company single sign-on.
2. Employees ask questions in natural language in a chat window in the browser; answers must cite the policy documents they come from (retrieval over our internal documents, RAG).
3. HR uploads new versions of the policy PDFs every week; the assistant should pick them up automatically.
4. Responses should stream back to the browser as they are generated.
5. Chat history is kept for 90 days.
6. GDPR applies. Budget is about $1,500 per month.
