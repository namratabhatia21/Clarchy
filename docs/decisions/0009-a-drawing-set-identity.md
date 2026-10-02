# 0009: Clarchy looks like an architect's drawing set

**Status:** accepted · 2026-10-01 · amended 2026-10-02 (see the end) · works with [0006](0006-provider-themes-and-scoped-diagram-styles.md)

## Context

The product is now called Clarchy (from "cloud architecture"), served at clarchy.com. Its
output is architecture drawings, so the site should look like the place those drawings are
made, without changing how the site works.

## Decision

- **Two papers, one redline.** Light mode is ink on trace paper (warm off-white, graphite
  text); dark mode is a drafting table at night (deep slate, pale lines). Both carry a
  faint drafting grid with a heavier line every fifth square. The single accent is a
  redline orange, the colour architects mark drawings up with, so the main action, the
  current sheet and annotations stand out against the cool paper and grid.
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
- **Instruments in motion (`drafting.js`).** On the home page a large protractor turns as
  you scroll, read by a fixed redline needle, and an architect's scale in the margin marks
  how far down the page you are. "From brief to drawing" is a detail sheet that assembles
  stage by stage as you scroll: the brief, redline mark-ups of the numbers that matter,
  the architecture, the build lane, numbered workflow bubbles, then the same drawing on
  every cloud with a cost dimension. While a plan runs, a compass draws a circle and a
  parallel rule hatches lines; results and new provider sheets draw themselves in.
  Everything stands still for people who prefer reduced motion.
- **The look only.** Every interaction, view and flow stays as it was; the changes are
  confined to the style sheet, decorative markup, title-block text and decorative
  motion.

## Consequences

- One consistent identity across the three pages and both themes, with the cloud
  providers' own looks still applied to results.
- The headline fonts come from Google Fonts; when they cannot load, the fallback is wider,
  so headline sizes leave room for it on phones. (Superseded: fonts are now served with
  the site; see the amendment.)

## Amendment, 2026-10-02: restraint

Applied everywhere, the conventions read as a template rather than a drawing set: a
spaced-capitals label above every section, numbered sheets in the menu, upper-case titles
on every page and grid paper behind everything. The drawing look now appears where it
means something.

- **Where it stays.** The Plan page keeps the grid, the instruments and the crop-marked
  composer; diagrams keep their sheets and title blocks; the footer keeps its title block,
  which is now the only place sheet numbers appear.
- **Lettering.** Titles are Archivo in sentence case. Spaced monospace capitals are kept
  for drawing annotation only: title blocks, table column headers, tags, and the "Detail A"
  callout of the scroll story. Interface labels are IBM Plex Sans in sentence case.
- **Plain paper elsewhere.** Examples, Services, How to, Blog, About, Privacy and Terms
  sit on plain paper, without section eyebrows.
- **Quieter instruments.** The protractor's lines are lighter, and its size follows the
  free margin beside the content so it never sits behind text; below 1280px it is a
  faint watermark.
- **Fonts served with the site** (`static/fonts/`, SIL Open Font License), so pages
  render without a request to Google and nothing about visitors goes to a font service.

## Amendment, 2026-10-02: no grid paper

A faint grid behind a page or a card has become one of the commonest marks of a generated
or template site. The page-wide grid on the home page and the small grids behind the home
drawing, example cards, the scroll story and the drafting loader are gone; those sheets
are plain paper. Only the diagram viewer keeps a faint grid, as the surface a drawing is
read on. Contour lines behind page headings remain the one background motif.
