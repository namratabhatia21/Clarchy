# Azure Architecture Icons

The SVG files in this folder are Microsoft's Azure architecture icons, one for each
Azure service that Clarchy draws with an icon (`icon:` in `data/mappings/azure.yaml`).
They belong to Microsoft, are not covered by Clarchy's licence, and are used under the
icon terms on the Azure Architecture Center's icons page
(<https://learn.microsoft.com/azure/architecture/icons/>):

> Microsoft permits the use of these icons in architectural diagrams, training
> materials, or documentation. You can copy, distribute, and display the icons only for
> the permitted use unless granted explicit permission by Microsoft. Microsoft reserves
> all other rights.

The same page asks that icons are not cropped, flipped, rotated, distorted or used to
represent another product, and that the product's name appears near the icon. Clarchy
therefore:

- uses them only in diagrams of Azure designs, each for the Azure service it stands for,
  with the service's name under it;
- embeds the files unchanged (scaled to the diagram's icon size, never recoloured);
- marks every diagram "not affiliated with Azure".

Services that are not Azure's (GitHub Codespaces, GitHub Copilot, KEDA, Bicep) and those
whose icon is not in this release (Microsoft Fabric, Foundry Agent Service) keep
Clarchy's lettered badges.

Source: Microsoft's Azure Public Service Icons, as embedded in the draw.io libraries of
<https://github.com/dwarfered/azure-architecture-icons-for-drawio> (March 2026). Each file
is the embedded SVG, decoded and saved byte for byte under its official file name. To use
Microsoft's own download or a newer release, get it from the page above and pass the
folder with `--icons` or `CLARCHY_ICONS_AZURE`; that folder is then used instead of this
one. See docs/decisions/0012-official-aws-icons-in-aws-diagrams.md.

The virtual network, subnet and users icons (`icon-service-Virtual-Networks.svg`,
`icon-service-Subnet.svg`, `icon-service-Users.svg`) come from the `@squinch/pack-azure`
npm package 0.14.0, which republishes Microsoft's Azure Public Service Icons V24 verbatim
(its copy of Key Vaults is byte-identical to the one above). They mark the virtual network,
its subnets and the people in Azure diagrams.
