# 0013: A page per address, rendered before it is sent

**Status:** accepted · 2026-10-02 · updates [0008](0008-plans-run-in-the-browser.md)

## Context

clarchy.com was one HTML file. Pricing, How to, the examples and the rest were sections
shown by a hash (`/#pricing`), and most lists (samples, examples, services) were drawn by
scripts. Search engines ignore the hash, so they saw a single address with one title,
nine `<h1>`s and little text, and nothing to list in a sitemap. The founder wants the site
to be found: an address, title, description and heading per page, a sitemap, breadcrumbs
and structured data, and a fast first paint without layout shift.

## Decision

- **One address per page**, each ending in a slash: `/`, `/examples/`, `/examples/<id>/`,
  `/services/`, `/pricing/`, `/how-to/`, `/blog/` and `/blog/<id>/`, `/about/`,
  `/privacy/`, `/terms/`. `site.py` holds the list, with each page's title (under 65
  characters), description (under 160), breadcrumbs and whether it goes in the sitemap.
- **One template, rendered before it is sent.** `static/index.html` keeps every section
  between `<!-- page:KEY -->` markers. A page's document carries only its own section,
  with the lists the scripts used to draw already in the HTML (samples, regions, examples,
  services, posts, an example's title), its head, visible breadcrumbs and JSON-LD
  (Organization, person, WebSite and WebApplication on the home page; a BreadcrumbList on
  the others; the questions on Pricing as an FAQPage). `export-site` writes the files;
  `clarchy serve` renders the same pages per request.
- **It still feels like one app.** Once a page has loaded, `app.js` catches links to the
  site's pages, fetches a page's section the first time (while the pointer is on its
  link), keeps it, and updates the address, title, description and canonical link. A plan
  in progress survives a look at Pricing, and Back and Forward work. Old links such as
  `/#pricing` go to the new address.
- **Files beside the pages:** `sitemap.xml`, `robots.txt` (everything but `/api/`),
  `_headers` (a year's caching for the hashed `assets/`, `noindex` on the workers.dev copy)
  and `_redirects` (`/pricing` and `/pricing/index.html` move to `/pricing/` with one
  301). Scripts and data move out of the page into `assets/` with a content hash, so a
  visitor downloads them once; the styles stay inline for the first paint.
- **Single-file builds stay.** `--fragment` (and `build_site`) puts every section in one
  file with `#hash` links, for hosts that take one file.

## Consequences

- Each page is about 100 KB of HTML (most of it the inline styles, which compress well),
  and the scripts and data are fetched once and kept.
- The site must sit at the root of its domain: links are root-relative.
- The pre-rendered Services list repeats what `services.js` draws, so the colours and
  match labels live in both places; a test checks they agree.
- Pages are only as good as their words: titles, descriptions and the copy itself still
  decide what people search for and click.
