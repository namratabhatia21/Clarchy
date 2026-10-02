# Clarchy visual design

Read this before changing anything people see on clarchy.com. It describes the look the
site has and the patterns it never uses. The reasoning is in
[ADR 0009](decisions/0009-a-drawing-set-identity.md).

## The idea

Clarchy makes architecture drawings, so the site looks like an architect's drawing set:
blue-white blueprint paper, navy ink lines, one signal-orange accent, a title block in the
footer, sheet numbers, crop marks and dimension lines. The proof of the product is a real
drawing that Clarchy made, not an illustration of one.

The home page is three frames. First the hero: "Brief in, drawing out" in huge condensed
type on a burnt-orange field, one sentence on what Clarchy does, two buttons (Design my
architecture, See an example) and a line saying it needs no sign-up and runs in the
browser. Beside them a card draws a real design and its monthly price, in front of a
protractor that turns as the page scrolls, with two architect's stamps in place of
stickers. The header sits on it until it scrolls away, then offers "Try it free". The
hero's orange (#b83c0c) is darker than the closing frame's so that its small cream text
passes AA (5.1:1). Then the brief beside a model of a real design, then how it works. The page closes on
the poster's orange again: "See the examples" in the same huge type, a drawing register of
real examples on a paper sheet, and a pantograph (plate K of Bion's book of drawing
instruments) that traces a small sketch and draws it again at twice the size as the frame
scrolls into view: one design, copied to every cloud. Small text there sits on the paper or the navy button, never
on the orange, which is too light for it.

The second frame shows an architect's massing model of a real design (`massing.py`,
[ADR 0015](decisions/0015-a-massing-model-on-the-home-page.md)): each running service
is a white block on a navy base, with its official icon on top and its height set by what
it costs a month, and callouts name the costliest. It is made from the RAG chatbot example
and the current price book every time the site is built, so it is never a mock-up.

## Layout

- The header has four sections (Examples, Services, Pricing, How to) and one button,
  Log in / Sign up (a person outline; once logged in, the visitor's initial and first
  name, with a small menu); the logo goes home. About, Blog, Privacy, Terms and the
  planner note are in the footer.
- The home page sits within gutters of 6% of the width (24 to 96px). The scale stands in
  the left gutter only where it is wide enough (1400px and up), so it never touches text.

## Tokens (app.css `:root`)

| Token | Light | Dark | Use |
|---|---|---|---|
| `--bg` | `#edf1f7` | `#0c1829` | Blueprint paper. Never pure white. |
| `--surface` | `#fafcff` | `#122237` | Sheets, cards, inputs |
| `--text` | `#0a1f3d` | `#ebeff4` | Navy ink, the brand colour |
| `--muted` | `#3c5272` | `#a9b8cb` | Secondary text |
| `--faint` | `#4b5f80` | `#8698b2` | Labels; at least 4.5:1 on every surface |
| `--rule` | `#0a1f3d` | `#c6d4e6` | Frames and rules |
| `--tick` | `#8ca0bc` | `#6c84a5` | Crop marks, contour lines |
| `--accent` | `#d4450c` | `#ff7a3d` | Signal orange, only for the main action, the current page and red lines |
| `--radius` | `3px` | | Corners are nearly square |

## Type

- Headings: **Archivo** bold, condensed to 87.5% (the file holds only that weight, at
  62% to 87.5% width). Sentence case.
- Text: **IBM Plex Sans** 400 to 700. Labels and figures: **IBM Plex Mono**, tabular.
- Self-hosted in `static/fonts/`, preloaded, under the SIL Open Font License.

## Motion

Motion happens once, means something, and never loops on its own (only progress
indicators turn, and only while a plan is being made):

- the home headline is lettered in, word by word, and the model's blocks rise to their
  cost once the page opens;
- the brief's frame is traced in pencil, then the trace lifts off;
- diagrams draw their lines; drawings and plan cards are plotted top to bottom the first
  time they scroll into view;
- cost totals are worked out to their value when the Cost view opens;
- the protractor turns and the scale marks how far down the page you are; while the
  model is on screen the protractor waits, so the two never overlap.

`prefers-reduced-motion` switches every animation off. Hover changes colour or a border,
never position or size.

## Backgrounds

No grid paper. A faint grid behind a page or a card is a template cliché; the only grid
is inside the diagram viewer, where it is a working surface for reading a drawing.
Contour lines (`scripts/contours.py`, in the spirit of Haikei's generated SVGs) behind
page headings, in `--tick`, fading out where the words are. Nothing else sits behind
text.

## Never

These make a site look generated. Do not add them:

- blue side icons, sparkle icons, emojis, icon-led feature rows;
- a pure white background, rainbow colouring, neon colours, basic pastels, purple and black;
- drop shadows on everything (only floating menus and dialogs have one);
- three feature cards in a row, bento grids, three pricing tiers;
- liquid glass, frosted glass, radial orbs, glowing blobs, dot grids, grid-paper backgrounds;
- Inter, Geist or Space Grotesk;
- em dashes in copy; "It's not X, it's Y" sentences; checkmark bullets;
- a coloured stripe along the top of a card;
- fake testimonials, invented logos or numbers;
- a terminal window as decoration;
- soft, very round corners;
- hover animations on everything, animated arrows, looping motion;
- skeleton-less blank loading, or pages with no real product to show;
- a site without Terms and a Privacy page.

## Copy

Plain, short and specific. Sentence case for headings and buttons. Say what Clarchy
does with the reader's brief, in their terms. No superlatives.
