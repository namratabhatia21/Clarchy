# AWS Architecture Icons

The SVG files in this folder are AWS Architecture Icons, one for each AWS service that
Clarchy draws (`icon:` in `data/mappings/aws.yaml`). They are the property of Amazon Web
Services, Inc. or its affiliates, are not covered by Clarchy's licence, and are used under
the AWS Architecture Icons terms: <https://aws.amazon.com/architecture/icons/>.

Those terms let customers and partners use the icons to create architecture diagrams.
They do not allow modifying the icons, using them for anything other than AWS services, or
using them to suggest that AWS endorses a product. Clarchy therefore:

- uses them only in diagrams of AWS designs, each for the AWS service it represents;
- embeds the files unchanged (they are scaled to the diagram's icon size, never recoloured
  or redrawn);
- marks every diagram "not affiliated with Amazon Web Services".

Source: the AWS Architecture Icons release of 30 January 2026 (64 px service icons), from
the `aws-icons` npm package 3.3.0, which republishes that release as minified SVG. The
files are copied byte for byte from there and renamed to the AWS package's pattern,
`Arch_<service>_64.svg`. To use AWS's own download instead, or a newer release, get it
from the page above and pass the folder with `--icons` or `CLARCHY_ICONS_AWS`; that folder is
then used instead of this one. See docs/decisions/0012-official-aws-icons-in-aws-diagrams.md.
