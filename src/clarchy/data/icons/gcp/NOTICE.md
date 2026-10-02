# Google Cloud icons

The SVG files in this folder are Google Cloud product and category icons, from Google's
2025 icon set (<https://cloud.google.com/icons>). They belong to Google and are not covered
by Clarchy's licence. Google's icons page says its product icons may be used freely and
without permission to accurately refer to Google's technology, for example in
architecture diagrams.

Google's set has its own icon for its core products (Cloud Run, Cloud SQL, Cloud Storage,
BigQuery, GKE, Vertex AI and others) and an icon per product category for the rest.
Clarchy uses a product's own icon where it has one, and otherwise the icon of the
category the product belongs to (Networking for Cloud DNS, Security and identity for
Secret Manager), always with the product's name beside it. The files are unchanged, and
every diagram says Clarchy is not affiliated with Google Cloud. Services that are not
Google's keep a badge (KEDA) or use the project's own logo (LiteLLM, `oss:litellm`).

Source: the `gcp-icons` npm package 1.0.6 (<https://github.com/kfkhalili/gcp-icons>),
which republishes Google's category-icons.zip and core-products-icons.zip unoptimised and
unaltered under kebab-case file names. To use Google's own download, pass the folder
with `--icons` or `CLARCHY_ICONS_GCP`. See docs/decisions/0012-official-aws-icons-in-aws-diagrams.md.
