# 0012: Diagrams use their providers' official icons, bundled

**Status:** accepted · 2026-10-02 · supersedes [0002](0002-no-bundled-provider-icons.md) ·
amended the same day to add Azure, then Google Cloud and open-source logos (see the end)

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

## Amendment: Azure

Microsoft's Azure Architecture Center publishes Azure's architecture icons with these
terms: "Microsoft permits the use of these icons in architectural diagrams, training
materials, or documentation. You can copy, distribute, and display the icons only for the
permitted use", and asks that icons are not cropped, flipped, rotated, distorted or used
for another product, with the product's name near the icon. Azure diagrams in Clarchy meet
that in the same way as AWS ones, so the same decision applies:

- `data/icons/azure/` holds one SVG per Azure service Clarchy draws (29 files, about
  66 KB), saved byte for byte under Microsoft's file names (`10029-icon-service-Function-Apps.svg`);
  `icon:` in `azure.yaml` is that name without `.svg`, so Microsoft's own download, passed
  with `--icons`, is searched the same way. `NOTICE.md` records the terms and the source.
- Services that are not Azure's (GitHub Codespaces, GitHub Copilot, KEDA, Bicep), and
  those with no icon in the release used (Microsoft Fabric, Foundry Agent Service), keep
  their badges. Azure DevOps services (Repos, Pipelines) use the Azure DevOps icon.

## Amendment: Google Cloud and open-source projects

Google's Cloud icons page says its product icons may be used freely and without
permission to accurately refer to Google's technology, for example in architecture
diagrams. The open-source projects Clarchy draws publish logos that documentation and
architecture diagrams commonly use to refer to them. The same decision applies to both:

- `data/icons/gcp/` holds 18 SVGs from Google's 2025 set (about 45 KB): a product's own
  icon where Google has one (Cloud Run, Cloud SQL, BigQuery, GKE, Vertex AI) and otherwise
  the icon of its category (Networking for Cloud DNS), always with the product's name
  beside it. `NOTICE.md` records the terms and the source.
- `data/icons/oss/` holds the projects' own logos (PostgreSQL, Kafka, Keycloak, vLLM,
  LiteLLM, Langfuse and others), mostly from Simple Icons, filled with each brand's colour.
  `NOTICE.md` lists every file with its owner, licence note and source. Projects with no
  logo there keep a badge.
- A cloud diagram may borrow a project's logo with `icon: oss:<stem>` where the service is
  that project running on the cloud (LiteLLM on Cloud Run). Where the service is the
  cloud's own (LiteLLM on Amazon ECS), the cloud's icon stays.
- Every provider now ships icons, so ADR 0002 is superseded in full. Deleting a folder
  returns that provider's diagrams to badges.
