# 0008: Plans run in the visitor's browser

**Status:** accepted · 2026-10-01 · supersedes [0005](0005-static-demo-replays-recorded-runs.md)

## Context

The public site is static (GitHub Pages). Replaying recorded runs (ADR 0005) showed what
planning looks like, but visitors could not plan their own requirements without
installing Clarchy. Hosting a backend costs money and would have to hold an API key
for the AI steps.

## Decision

- The site runs Clarchy's own Python package in the browser with
  [Pyodide](https://pyodide.org). `clarchy export-site` writes
  `clarchy-engine.zip` (the package's Python and data files) next to the page. On the
  first plan the page loads Pyodide and its pydantic and PyYAML packages from the Pyodide
  CDN, unpacks the bundle and calls `clarchy.browser.plan` and
  `clarchy.browser.design`, which produce the same events and payloads as the server.
  `pypdf` is installed on demand for PDF uploads.
- Planning is rule-based by default. For the AI steps the visitor can choose an
  open-source model on Hugging Face's OpenAI-compatible router with their own token, or
  any OpenAI-compatible endpoint such as Ollama on their own machine. The token stays in
  the browser tab (session storage) and is sent only to that endpoint.
- In the browser the agent calls the same tools in process (`LocalToolbox`) rather than
  through an in-memory MCP session; the tool definitions and results are identical.
- Examples, the catalog, and recorded runs and designs of the samples stay embedded, so
  they appear instantly without loading the engine.
- `--no-engine` builds the replay-only page of ADR 0005, and `--api-base` a front end for
  a hosted server.

## Consequences

- Anyone can plan their own document on the public site at no cost to the project, and
  nothing they upload leaves their browser unless they choose a hosted model.
- The first plan downloads about 15 MB (then cached) and takes a few seconds to start.
- The site depends on the Pyodide CDN and on the model provider allowing requests from
  the site's origin (CORS).
- Open models follow tool calls less reliably than frontier models; when a run fails it
  falls back to the rule-based draft and says so.
