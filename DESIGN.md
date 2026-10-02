# Clarchy design

Read this before changing anything people see on clarchy.com. It describes the look the
site has and the patterns it never uses. The reasoning is in
[ADR 0009](docs/decisions/0009-a-drawing-set-identity.md).

## The idea

Clarchy makes architecture drawings, so the site looks like an architect's drawing set:
cream drafting paper, pencil and ink lines, one orange accent, a title block in the
footer, sheet numbers, crop marks and dimension lines. The proof of the product is a real
drawing that Clarchy made, not an illustration of one.

## Tokens (app.css `:root`)

| Token | Light | Dark | Use |
|---|---|---|---|
| `--bg` | `#f3f1ea` | `#121c26` | Paper. Never pure white. |
| `--surface` | `#fbfaf6` | `#172431` | Sheets, cards, inputs |
| `--text` | `#1b2127` | `#ebeff4` | Ink |
| `--muted` | `#545d66` | `#aab6c3` | Secondary text |
| `--faint` | `#62686d` | `#8191a2` | Labels; at least 4.5:1 on every surface |
| `--rule` | `#1b2127` | `#c9d4df` | Frames and rules |
| `--tick` | `#8e8775` | `#71859a` | Crop marks, contour lines |
| `--accent` | `#c43e14` | `#ff7a3d` | The one accent: primary buttons, the current page, a trace |
| `--radius` | `3px` | | Corners are nearly square |

## Type

- Headings: **Archivo** bold, condensed to 87.5% (the file holds only that weight, at
  62% to 87.5% width). Sentence case.
- Text: **IBM Plex Sans** 400 to 700. Labels and figures: **IBM Plex Mono**, tabular.
- Self-hosted in `static/fonts/`, preloaded, under the SIL Open Font License.

## Motion

Motion happens once, means something, and never loops on its own (only progress
indicators turn, and only while a plan is being made):

- the home headline is lettered in, word by word;
- the brief's frame is traced in pencil, then the trace lifts off;
- diagrams draw their lines; drawings and plan cards are plotted top to bottom the first
  time they scroll into view;
- cost totals are worked out to their value when the Cost view opens;
- the protractor turns and the scale marks how far down the page you are.

`prefers-reduced-motion` switches every animation off. Hover changes colour or a border,
never position or size.

## Backgrounds

Grid paper on the home page only. Contour lines (`scripts/contours.py`, in the spirit of
Haikei's generated SVGs) behind page headings, in `--tick`, fading out where the words
are. Nothing else sits behind text.

## Never

These make a site look generated. Do not add them:

- blue side icons, sparkle icons, emojis, icon-led feature rows;
- a pure white background, rainbow colouring, neon colours, basic pastels, purple and black;
- drop shadows on everything (only floating menus and dialogs have one);
- three feature cards in a row, bento grids, three pricing tiers;
- liquid glass, frosted glass, radial orbs, glowing blobs, dot grids;
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
