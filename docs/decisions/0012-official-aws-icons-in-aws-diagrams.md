# 0012: AWS diagrams use the official AWS Architecture Icons, bundled

**Status:** accepted · 2026-10-02 · supersedes [0002](0002-no-bundled-provider-icons.md) for AWS

## Context

ADR 0002 kept every provider icon out of the repository, so diagrams on clarchy.com drew
lettered badges. The founder wants AWS diagrams to use the AWS icons that readers
recognise. Other sites doing so is not what makes it acceptable; AWS's own terms are. The
AWS Architecture Icons page lets customers and partners use the icons to create
architecture diagrams, and prohibits modifying them or using them for anything other
than AWS services. That is the use Clarchy makes of them: a diagram of an AWS design,
each icon standing for the AWS service it names.

## Decision

- **Ship the icons Clarchy draws, and only those:** one 64 px SVG per AWS service in
  `data/mappings/aws.yaml`, in `src/clarchy/data/icons/aws/`, named like AWS's package
  (`Arch_<service>_64.svg`), with a `NOTICE.md` that states who owns them, their terms and
  where the copy came from. A test fails if a mapped service has no icon or an unused icon
  is shipped.
- **Unchanged files.** Icons are embedded byte for byte as data URIs and only scaled to
  the diagram's icon size; themes never recolour them.
- **AWS services only.** Services that aren't AWS's (KEDA, GitHub or GitLab) keep their
  badges, and Azure, Google Cloud and the open-source view keep badges too: their icon
  terms haven't been reviewed, so ADR 0002 still applies to them.
- **No endorsement implied.** Every diagram's footer says "Service names and icons belong
  to their owners; Clarchy is not affiliated with AWS", and the site's notes say the same.
- **The user's own copy still wins.** `--icons` or `CLARCHY_ICONS_AWS` points at a newer
  AWS package, which is then used instead of the bundled files.

## Consequences

- AWS diagrams look like the AWS diagrams readers know, on clarchy.com, in the
  in-browser engine, from `clarchy serve` and from the CLI.
- About 55 KB of icons in the package; each AWS diagram grows by roughly 2 KB per service
  drawn (smaller once compressed).
- If AWS changes its terms or asks for the icons to be removed, deleting
  `data/icons/aws/` returns every diagram to badges with no other change.
- AWS refreshes the set a few times a year. Updating means replacing the files from a new
  release and running the tests, which list any service whose icon is missing.
