# 0016: Each cloud's diagram is drawn the way its own documentation draws one

**Status:** accepted · 2026-10-02 · refines [0006](0006-provider-themes-and-scoped-diagram-styles.md)

## Context

Until now every diagram had the same shape: rounded cards with a coloured outline, curved
links, one boundary box for the cloud and a theme that changed only the colours. The
author asked for diagrams that look exactly like the ones in AWS's, Azure's and Google
Cloud's own documentation, so that an architect recognises them at once.

Those conventions differ by provider, and they are structural, not only colours:

- **AWS** reference architectures and the AWS Architecture Icons deck draw each service
  as its icon with its name underneath; groups nest (AWS Cloud, Region, VPC, public and
  private subnets), each with its own group icon and colour; arrows are right-angled; and
  the main flow is numbered with black markers whose steps are written out beside or
  under the drawing.
- The **Azure Architecture Center** also draws icons with names underneath, inside a
  region, a virtual network and subnets marked with Azure's own icons, with numbered
  steps.
- **Google Cloud** architecture diagrams use product cards (the icon, then the name) on
  grey zones for Google Cloud, the region and the VPC network.

## Decision

- **One style per provider** (`render_doc.py`), chosen by `provider.diagram.style` in
  each mapping: `aws`, `azure` or `gcp`. The open-source view has no provider
  documentation to follow and keeps Clarchy's own cards (`render.py`).
- **Placement from the mapping.** `provider.diagram.placement` says where a capability's
  service sits: `global` (outside the region: DNS, CDN, WAF, and on Google Cloud the
  global load balancer), `public` (a public subnet: the load balancer on AWS and Azure),
  `private` (inside the network: containers, Kubernetes, PostgreSQL, the cache) or the
  region by default (managed serverless services). Build and deploy and the shared
  services stay in their own dashed groups inside the region.
- **The provider's own group icons**, bundled like the service icons (ADR 0012): AWS's
  AWS Cloud, Region, VPC, public and private subnet and Users icons; Azure's virtual
  network, subnet and users icons. Google Cloud's zones are labelled, as Google draws them.
- **Right-angled links** with their ends spread along a service's side, a lane each where
  they run through the gap between two columns, gaps widened when many links share them,
  and a detour above or below a service rather than through it.
- **The main request numbered.** The design's request workflow is marked step by step on
  its links (black on AWS, blue on Azure and Google Cloud) and written out under the
  drawing. A numbered link drops its label, as in the providers' diagrams; other links
  keep theirs, placed clear of other labels, markers and services.
- The page scripts keep working: every service is still a `g.node` with a box (invisible
  on AWS and Azure until it is hovered or selected), links keep `data-from` and `data-to`,
  and `data-drawing-bottom` lets thumbnails leave the numbered steps out.

## Consequences

- AWS, Azure and Google Cloud diagrams now read like the providers' reference
  architectures, in the app, in downloads and on the Examples page.
- The layout is still computed from the spec and byte-identical for the same input; the
  golden files changed once, with this decision.
- Microsoft's and Google's documentation sites can't be reached from the build sandbox,
  so their conventions here come from their icon kits and published guidance rather than
  from tracing their diagrams. AWS's group colours come from AWS's group icons themselves.
- Dense designs (twenty services or more) still cross lines in the middle; a hand-drawn
  reference diagram would leave some links out. The numbered steps carry the main flow.
