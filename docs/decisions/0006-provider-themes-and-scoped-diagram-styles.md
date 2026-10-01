# 0006: Provider themes without logos, and diagram styles scoped per provider

**Status:** accepted · 2026-10-01 · updates [0002](0002-no-bundled-provider-icons.md)

## Context

Results should feel native to each cloud (AWS, Azure, Google Cloud) without copying
logos or icons (0002). The web UI also shows several diagrams on one page, and an SVG
`<style>` element inlined into HTML applies to the whole document, so one diagram's rules
changed another's text (badge labels inherited a 14px font size).

## Decision

- Each provider's mapping file carries a `theme`: font, frame colours, line style and a
  colour per service category, drawn from the provider's published architecture-diagram
  conventions. The UI uses matching accents for the provider bar and tabs.
- Badges are lettered abbreviations coloured by category, never logos.
- Every diagram class starts with `ca-`, the root carries `ca-<provider>`, and every
  style rule is scoped to it. Arrowheads are drawn as polygons rather than shared
  `<marker>` elements, so diagrams contain no ids that could clash.

## Consequences

- Diagrams can be inlined any number of times on a page, in any order.
- Themes are data, so adjusting a provider's look is a YAML change, covered by the
  golden-file tests.
- Official icons remain opt-in, as before.
