# 0015: A massing model of a real design leads the home page

**Status:** accepted · 2026-10-02 · builds on [0009](0009-a-drawing-set-identity.md)

## Context

The author compared three concepts for the home page, drawn from sites they admire: a
dark field survey, a bold poster and an architect's model, and chose the model. The home
page had a headline, the composer and, below it, a flat drawing of an example; nothing
above the fold showed what Clarchy gives back, and in particular not the cost.

## Decision

- **The hero has two columns:** the headline, composer and samples on the left, unchanged
  in behaviour, and a massing model of the RAG chatbot example on AWS on the right. Below
  1100px the model follows the samples; on phones its callouts give way to the caption.
- **The model is data, not artwork.** `massing.py` lays out any design: each running
  service is a block in its lifecycle zone (serve, run, integrate, store, and operate
  along the front), with the provider's official icon on top and a height that grows with
  the square root of its monthly cost. Connections run along the base. Up to four
  callouts name the services that are at least 3% of the bill, placed right to left so
  no label crosses another leader. It is generated with the page from the current price
  book, so the daily price refresh updates it.
- **It reads as an image:** `role="img"` with a title and a description that lists every
  service and its monthly cost. The headline keeps "cloud architecture" for search and
  marks "priced" as its one accented word.
- **Motion once:** the blocks rise to their height when the page opens and the callouts
  follow; nothing moves with reduced motion. The protractor waits while the model is on
  screen and turns as before once it scrolls away.

## Consequences

- The home page grows by about 50 KB of HTML (the icons are embedded), which compresses
  well; layout shift stays under 0.02 and the headline is still the largest paint.
- The same generator can draw any design, for example as a model view of a plan later.
- Block heights compare services within one design; they are not a scale across designs.

## Amendment, 2026-10-02: three frames

The author asked for the poster concept as the first frame, the model second and How it
works third. The poster is drawn on a 1440 x 820 sheet scaled to the screen (container
units keep its type and marks in place), with its own protractor that turns with the
scroll; on phones it stacks. Its headline is the page's h1 ("Brief in, drawing out");
the model frame's headline becomes an h2 and keeps "priced" as its accent. The header
takes the poster's colour while the poster is in view, and the instruments wait until
both the poster and the model have scrolled away. The example drawing now follows How it
works, as its result.

## Amendment, 2026-10-02: the page closes on the examples

The author asked for something in orange to see the examples, with a protractor, in
place of the example drawing at the bottom. The last frame takes the poster's orange: "See
the examples", the first four examples as a drawing register (number, name, services, each
linking to its page) and a "See examples" button, beside a pantograph: the author chose
it from a plate of 18th-century drawing instruments (plate K) over a second protractor.
As the frame scrolls into view its tracer follows a small sketch of three services while
its pencil draws the same sketch at twice the size, and the copy is taken back on the way
up (drafting.js; with reduced motion it is shown finished). site.py solves the linkage
(two equal bars from a fixed pivot, a parallelogram holding the tracer halfway) and draws
it finished, so the frame needs no script to read; drafting.js runs the same sums. The massing model above already shows a real
design, priced, so the drawing no longer needs repeating.
