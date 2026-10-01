# 0005: The public demo replays recorded runs

**Status:** superseded by [0008](0008-plans-run-in-the-browser.md) · 2026-10-01

## Context

The live demo is a static page on GitHub Pages. It cannot run the planner, hold an API
key or read uploaded documents, but a visitor should still see what planning looks like.

## Decision

- `clarchy export-site` runs the rule-based pipeline on each sample at build time,
  records every event, and embeds the events, the resulting specs and their rendered
  designs on every provider.
- The Plan page replays a recorded run with short pauses between stages and says it is
  a recorded rule-based run. Typing and uploading are disabled, with a link to running
  Clarchy yourself.
- Designs are looked up by the exact spec text, so the same front-end code works in
  server, static and remote modes.
- `--api-base` builds a front end that calls a hosted Clarchy API instead of
  embedding data, for when a backend is deployed.

## Consequences

- The demo shows the real pipeline output, not a mock-up, and stays in step with the
  code because it is rebuilt on every push.
- The page is about 1.6 MB, mostly pre-rendered diagrams.
- Planning new documents publicly needs a hosted backend (roadmap phase 5).
