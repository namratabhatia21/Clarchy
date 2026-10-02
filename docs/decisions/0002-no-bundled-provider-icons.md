# 0002: Provider icons are not bundled

**Status:** superseded for AWS by [0012](0012-official-aws-icons-in-aws-diagrams.md) · 2026-10-01; still holds for Azure and Google Cloud

## Context

AWS, Google Cloud and Microsoft publish official architecture icons, each under its own
terms. AWS allows them to be used to create architecture diagrams but restricts
modifying them and using them for anything other than AWS services (as summarised in
search results; read the current terms on the AWS Architecture Icons page). Terms can
change, and redistribution inside an open-source repository is a different act from
using them in a diagram.

## Decision

- The repository contains no provider icons.
- Users download each provider's official package and point Clarchy at it with
  `--icons` or `CLARCHY_ICONS_<PROVIDER>`.
- Icons are embedded unmodified (as data URIs) into generated diagrams.
- Without icons, diagrams use neutral lettered badges coloured by tier.
- Every diagram carries a "not affiliated" footer.

## Consequences

- Zero licensing risk in the repository itself.
- One extra setup step for official-looking diagrams; `clarchy icons` makes it easy
  to verify.
- A hosted web version (phase 5) needs a separate review of each provider's terms
  before serving icons.
