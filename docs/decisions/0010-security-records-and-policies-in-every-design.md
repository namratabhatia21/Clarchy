# 0010: Security, records and AI policies are part of every design

**Status:** accepted · 2026-10-01

## Context

Reviews of real systems ask first about access, audit, encryption, retention and, for AI,
about guardrails and regulation. A design that only draws the app leaves those answers
to a later document, which is where gaps hide. Teams also pay for tools outside the cloud
bill (dev environments, AI coding assistants, model APIs) and often hold prepaid credits.

## Decision

- Capabilities for access governance, key management, audit logging, AI guardrails,
  backup, archive storage, dev environments and AI coding assistants, mapped on every
  provider and priced (AWS from the Price List API; Azure, Google Cloud and third-party
  SaaS such as GitHub from their pricing pages, marked approximate).
- The rule-based planner adds a security baseline when the brief states a compliance
  regime, uses language models or asks for it, adds backups and an archive when records
  must be kept, and reads team size and retention periods. The AI planner extracts the
  same two numbers.
- A Policies view checks each design against the AI and data regulations that apply
  (data/policies.yaml): each obligation is covered by a component, a gap with a suggested
  capability, or an action for the team.
- Prepaid credits were entered on the cost view and applied client-side; removed on
  2026-10-02 at the author's request, to keep the cost view to list prices.

## Consequences

- Designs are larger, but they answer the questions a security or compliance review asks.
- The policy checklist is guidance for design, not legal advice, and needs updating as
  regulations change.
