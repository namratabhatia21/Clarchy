# 0004: The AI planner is an agent that designs through MCP tools

**Status:** accepted · 2026-10-01 · refines [0003](0003-llm-proposes-code-calculates.md)

## Context

People describe apps in documents, not YAML. Turning a requirements document into a
design needs judgement (which compute model, which data stores, what to assume), which a
model is good at, but the result must stay trustworthy: no invented services, no
unexplained choices, and no quotes the document never said.

## Decision

- The pipeline has fixed stages: read, understand, design, toolchain, workflows, map.
  Only understand, design and workflows use the model; the rest is deterministic code.
- **Understand** and **workflows** use structured outputs (JSON schemas). Workflow steps
  may only name real component ids.
- **Design** is a tool-use loop. The agent is an MCP client of CloudArchie's own MCP
  server, connected in memory, using six research and validation tools with strict
  schemas. Extra MCP servers can be attached (`--mcp`). The loop ends only when the model
  calls `submit_design` with a spec that validates against the schema and maps to every
  provider; otherwise the errors go back to the model.
- Every evidence quote is checked against the document text and dropped if it is not
  there. Toolchain components and workflows the model submits are dropped and rebuilt by
  code, so build and deploy is consistent across designs.
- The conversation is append-only, with thinking blocks passed back unchanged. Tools,
  the system prompt and the opening document are cached, so each turn re-reads them from
  the cache.
- Any model failure (API error, refusal, no submission within 14 turns) falls back to
  the rule-based planner, and the user is told.
- The model is reached through a thin `LLM` interface (Claude API with server-side
  refusal fallbacks enabled, or Amazon Bedrock), so tests drive the whole loop with a
  scripted model.

## Consequences

- The model may compose capabilities beyond the pattern library (0003 limited it to
  patterns), but only from the catalog, and every result is validated.
- The same tools serve the built-in agent, Claude Desktop, Claude Code and any other MCP
  client.
- Without an API key the product still works; the rule-based planner gives a reasonable
  first draft with evidence and open questions.
- Output quality with a real model has to be checked on real documents; the tests prove
  the guardrails, not the judgement.
