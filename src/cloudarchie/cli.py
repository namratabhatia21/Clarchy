"""Command-line interface.

cloudarchie patterns
cloudarchie validate <pattern-or-spec.yaml>
cloudarchie render   <pattern-or-spec.yaml> --provider aws -o diagram.svg
cloudarchie explain  <pattern-or-spec.yaml> --provider aws [-o explain.md]
cloudarchie icons    --provider aws [--icons DIR]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pydantic import ValidationError

from cloudarchie import catalog
from cloudarchie.explain import explain_markdown
from cloudarchie.icons import IconLibrary, icon_dir_from_env
from cloudarchie.mapping import MappingError, map_to_provider
from cloudarchie.render import render_svg
from cloudarchie.spec import load_pattern, load_spec_or_pattern


def _icons(provider: str, explicit: str | None) -> IconLibrary:
    root = Path(explicit).expanduser() if explicit else icon_dir_from_env(provider)
    return IconLibrary(root)


def _write(text: str, output: str | None) -> None:
    if output:
        Path(output).write_text(text, encoding="utf-8")
        print(f"wrote {output}", file=sys.stderr)
    else:
        sys.stdout.write(text)


def cmd_patterns(_: argparse.Namespace) -> int:
    for name in catalog.pattern_names():
        print(f"{name:24} {load_pattern(name).summary or ''}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    spec = load_spec_or_pattern(args.spec)
    for provider in catalog.providers():
        map_to_provider(spec, provider)
    print(
        f"ok: {spec.name} ({len(spec.components)} components, {len(spec.edges)} edges; "
        f"maps to {', '.join(catalog.providers())})"
    )
    return 0


def cmd_render(args: argparse.Namespace) -> int:
    arch = map_to_provider(load_spec_or_pattern(args.spec), args.provider)
    _write(render_svg(arch, _icons(args.provider, args.icons)), args.output)
    return 0


def cmd_explain(args: argparse.Namespace) -> int:
    arch = map_to_provider(load_spec_or_pattern(args.spec), args.provider)
    _write(explain_markdown(arch), args.output)
    return 0


def cmd_icons(args: argparse.Namespace) -> int:
    library = _icons(args.provider, args.icons)
    if library.root is None:
        print(
            f"no icon directory: pass --icons or set CLOUDARCHIE_ICONS_{args.provider.upper()}",
            file=sys.stderr,
        )
        return 1
    services = catalog.provider_mapping(args.provider)["services"]
    missing = 0
    for capability, raw in services.items():
        found = library.find(raw.get("icon"))
        missing += found is None
        where = found.relative_to(library.root).as_posix() if found else "NOT FOUND"
        print(f"{capability:20} {raw['service']:42} {where}")
    print(f"\n{len(services) - missing}/{len(services)} icons found", file=sys.stderr)
    return 0 if missing == 0 else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cloudarchie", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("patterns", help="list built-in architecture patterns").set_defaults(
        func=cmd_patterns
    )

    p = sub.add_parser("validate", help="validate a spec and its mappings")
    p.add_argument("spec", help="pattern name or path to a YAML spec")
    p.set_defaults(func=cmd_validate)

    for name, func, help_text in (
        ("render", cmd_render, "render an SVG diagram"),
        ("explain", cmd_explain, "explain service choices as Markdown"),
    ):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("spec", help="pattern name or path to a YAML spec")
        p.add_argument("--provider", default="aws", choices=catalog.providers())
        p.add_argument("-o", "--output", help="output file (default: stdout)")
        if name == "render":
            p.add_argument("--icons", help="folder with the provider's official icon package")
        p.set_defaults(func=func)

    p = sub.add_parser("icons", help="check which service icons are found in an icon package")
    p.add_argument("--provider", default="aws", choices=catalog.providers())
    p.add_argument("--icons", help="folder with the provider's official icon package")
    p.set_defaults(func=cmd_icons)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (ValidationError, MappingError, KeyError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
