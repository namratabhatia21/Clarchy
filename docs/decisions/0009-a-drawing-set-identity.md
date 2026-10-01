# 0009: Clarchy looks like an architect's drawing set

**Status:** accepted · 2026-10-01 · works with [0006](0006-provider-themes-and-scoped-diagram-styles.md)

## Context

The product is now called Clarchy (from "cloud architecture"), served at clarchy.com. Its
output is architecture drawings, so the site should look like the place those drawings are
made, without changing how the site works.

## Decision

- **Two papers.** Light mode is ink on trace paper (warm off-white, graphite text,
  blueprint-blue accent). Dark mode is a blueprint (deep blue, white lines, light blue
  accent). Both carry a faint drafting grid with a heavier line every fifth square.
- **Drawing conventions instead of ornament.** Hairline frames with crop marks around the
  composer and each diagram sheet; "How it works" drawn as a chain dimension with slash
  ticks; pipeline stages as numbered grid bubbles; pages numbered as sheets (01 Plan,
  02 Examples, 03 Services); title blocks under each diagram (drawing, cloud, region,
  services, scale, sheet), on each example card and in the footer.
- **Lettering.** Archivo, condensed and upper case, for titles (drawing-title lettering);
  IBM Plex Mono in small spaced capitals for labels and annotations; IBM Plex Sans for
  reading text.
- **Diagrams are printed on paper in both themes.** The diagram's white background is
  dropped on screen so it sits on the sheet's grid. The SVG files themselves, and each
  provider's colours inside the workspace (ADR 0006), are unchanged.
- **The look only.** Every interaction, view and flow stays as it was; the change is
  confined to the style sheet, decorative markup and the title-block text.

## Consequences

- One consistent identity across the three pages and both themes, with the cloud
  providers' own looks still applied to results.
- The headline fonts come from Google Fonts; when they cannot load, the fallback is wider,
  so headline sizes leave room for it on phones.
