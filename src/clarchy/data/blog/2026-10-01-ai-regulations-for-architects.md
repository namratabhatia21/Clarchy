---
title: AI regulations every architecture should plan for
date: 2026-10-01
author: Namrata Bhatia
role: Founder
summary: The EU AI Act, GDPR, the OWASP Top 10 for LLM apps, the NIST AI RMF and ISO/IEC 42001, and the parts of a design that help meet each of them.
---
Most AI regulation is about process: assessments, notices, contracts and governance. But a surprising amount of it lands on the architecture. If the design has no place to log what the model did, no way to mask personal data and no owner for access, no amount of policy writing will fill the gap later.

Clarchy's Policies view checks each design against the frameworks below. Every obligation is marked **covered** when a component does the job, a **gap** when a capability that would help is missing, or an **action** when it is work for the team. Here is what each one asks of an architecture.

## EU AI Act

The EU's AI law entered into force in August 2024 and applies in stages, from February 2025 to August 2027. The duties depend on the risk level of the use case. For architects, three things matter most:

- **Transparency.** People must be told when they are interacting with an AI system, and AI-generated content must be marked (Article 50).
- **Record-keeping.** High-risk systems must keep logs that let you trace what happened (Article 12). LLM tracing and an audit trail cover this.
- **Human oversight.** Consequential decisions need a person who can understand and override the system.

The EU has proposed moving some high-risk deadlines, so check the current timeline before you plan around a date.

## GDPR and UK GDPR

Personal data in prompts, documents, logs and backups is still personal data. Run a data protection impact assessment before processing it at scale with AI. Keep it out of prompts where you can and mask it where you can't (guardrails), protect it with encryption and access control, keep it in the regions you promised, and delete or archive it on a schedule.

## OWASP Top 10 for LLM Applications

The most practical list for security reviews. The design-level controls are prompt-injection screening (LLM01), masking sensitive data (LLM02), least-privilege tools for agents (LLM06), and rate limits and token budgets (LLM10), which is exactly what an LLM gateway is for.

## NIST AI RMF and ISO/IEC 42001

The NIST AI Risk Management Framework organises the work into govern, map, measure and manage. ISO/IEC 42001 turns it into a certifiable management system, built like ISO/IEC 27001. Both expect named owners, documented use cases, measurement before and after release, and records that show the controls work.

## Model provider terms

Where your prompts go is decided by the endpoint you call. Enterprise endpoints such as Amazon Bedrock, Azure OpenAI and Vertex AI don't train on your prompts by default; for any third-party API, check the retention settings. Sending all model traffic through one gateway keeps keys, budgets and usage logs in one place.

*This is a design checklist, not legal advice. Check the current text with each source, and involve your privacy and legal teams early.*
