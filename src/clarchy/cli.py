"""Command-line interface.

clarchy plan <file-or-text> [-o out/] [--rules]    requirements -> architecture
clarchy patterns
clarchy validate <pattern-or-spec.yaml>
clarchy render   <pattern-or-spec.yaml> --provider aws -o diagram.svg
clarchy explain  <pattern-or-spec.yaml> --provider aws [-o explain.md]
clarchy icons    --provider aws [--icons DIR]
clarchy serve    [--host 127.0.0.1] [--port 8000]   web UI (needs the "web" extra)
clarchy mcp      [--transport stdio]                MCP server for AI clients
clarchy prices   update | lookup <Service> <words>  latest AWS prices (Price List API)
clarchy export-site -o site/ [--fragment] [--api-base URL]   static site, no server needed
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pydantic import ValidationError

from clarchy import catalog
from clarchy.explain import explain_markdown
from clarchy.icons import IconLibrary, icon_library
from clarchy.mapping import MappingError, map_to_provider
from clarchy.render import render_svg
from clarchy.spec import load_pattern, load_spec_or_pattern


def _icons(provider: str, explicit: str | None) -> IconLibrary:
    return icon_library(provider, Path(explicit).expanduser() if explicit else None)


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
            f"no icon directory: pass --icons or set CLARCHY_ICONS_{args.provider.upper()}",
            file=sys.stderr,
        )
        return 1
    print(f"icons from {library.root}", file=sys.stderr)
    services = catalog.provider_mapping(args.provider)["services"]
    drawn = {k: raw for k, raw in services.items() if raw.get("icon")}
    missing = 0
    for capability, raw in services.items():
        if capability not in drawn:
            where = "badge (not a provider service)"
        else:
            found = library.find(raw["icon"])
            missing += found is None
            if found is None:
                where = "NOT FOUND"
            elif found.is_relative_to(library.root):
                where = found.relative_to(library.root).as_posix()
            else:
                where = f"{found.name} (open-source logos)"
        print(f"{capability:20} {raw['service']:42} {where}")
    print(f"\n{len(drawn) - missing}/{len(drawn)} icons found", file=sys.stderr)
    return 0 if missing == 0 else 1


def cmd_serve(args: argparse.Namespace) -> int:
    try:
        from clarchy.web import serve
    except ImportError:
        print('error: the web UI needs extra packages: pip install -e ".[web]"', file=sys.stderr)
        return 2
    print(f"Clarchy UI on http://{args.host}:{args.port}", file=sys.stderr)
    serve(args.host, args.port)
    return 0


def cmd_export_site(args: argparse.Namespace) -> int:
    from clarchy.export import PYODIDE_BASE, export_site

    path = export_site(
        args.output,
        fragment=args.fragment,
        api_base=args.api_base,
        with_engine=not args.no_engine,
        pyodide_base=args.pyodide_base or PYODIDE_BASE,
    )
    pages = sorted(path.parent.rglob("index.html"))
    print(f"wrote {len(pages)} page(s) to {path.parent}", file=sys.stderr)
    return 0


def cmd_plan(args: argparse.Namespace) -> int:
    import asyncio
    import re

    from clarchy.explain import explain_markdown
    from clarchy.ingest import IngestError, from_text, read_document
    from clarchy.planner import PlanError, PlanOptions, run_plan
    from clarchy.planner.llm import LLMError, llm_from_env

    source = Path(args.input)
    try:
        is_file = source.is_file()
    except OSError:  # long requirements text is not a valid path ("File name too long")
        is_file = False
    try:
        doc = read_document(source.read_bytes(), source.name) if is_file else from_text(args.input)
        llm = None if args.rules else llm_from_env()
    except (IngestError, LLMError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    def show(event: dict) -> None:
        kind = event["type"]
        if kind == "stage" and event["status"] == "done":
            print(f"✔ {event['title']}: {event.get('detail', '')}", file=sys.stderr)
        elif kind == "tool_call":
            print(f"    → {event['name']} {event['summary']}", file=sys.stderr)
        elif kind == "tool_result" and not event["ok"]:
            print(f"    ✗ {event['name']}: {event['summary']}", file=sys.stderr)
        elif kind == "notice":
            print(f"! {event['text']}", file=sys.stderr)

    options = PlanOptions(
        mode="rules" if args.rules else "auto", region=args.region, extra_mcp_servers=args.mcp
    )
    try:
        result = asyncio.run(run_plan(doc, options, llm=llm, emit=show))
    except PlanError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    slug = re.sub(r"[^a-z0-9]+", "-", result.spec.name.lower()).strip("-") or "plan"
    out = Path(args.output or f"plan-{slug}")
    out.mkdir(parents=True, exist_ok=True)
    (out / "spec.yaml").write_text(result.spec_yaml, encoding="utf-8")
    for provider in catalog.providers():
        arch = map_to_provider(result.spec, provider)
        svg = render_svg(arch, _icons(provider, None))
        (out / f"{provider}.svg").write_text(svg, encoding="utf-8")
        (out / f"{provider}.md").write_text(explain_markdown(arch), encoding="utf-8")
    how = f"AI ({result.model})" if result.mode == "ai" else "rule-based planner"
    print(f"wrote {out}/ (spec.yaml, diagrams and explanations; {how})", file=sys.stderr)
    return 0


def cmd_prices(args: argparse.Namespace) -> int:
    from clarchy import aws_prices

    if args.action == "update":
        argv = (["--output", args.output] if args.output else []) + (
            ["--cache", args.cache] if args.cache else []
        )
        return aws_prices.main(argv)
    if not args.service:
        print("error: prices lookup needs an AWS service code, e.g. AWSLambda", file=sys.stderr)
        return 2
    try:
        rows = aws_prices.lookup(args.service, " ".join(args.search))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    for row in rows:
        price = f"{row['price_usd']:.10f}".rstrip("0").rstrip(".")
        print(f"${price:>14} / {row['unit']:<16} {row['description']}")
    return 0


def cmd_mcp(args: argparse.Namespace) -> int:
    try:
        from clarchy.mcp_server import main as run_mcp
    except ImportError:
        print('error: the MCP server needs: pip install "clarchy[agent]"', file=sys.stderr)
        return 2

    run_mcp(args.transport, args.port)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="clarchy", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("plan", help="turn a requirements document into an architecture")
    p.add_argument("input", help="a .docx, .xlsx, .pdf, .md or .txt file, or the requirements text")
    p.add_argument("-o", "--output", help="output folder (default: plan-<name>)")
    p.add_argument("--rules", action="store_true", help="use the rule-based planner, no AI")
    p.add_argument("--region", choices=sorted(catalog.regions()), help="override the region")
    p.add_argument(
        "--mcp",
        action="append",
        default=[],
        metavar="COMMAND",
        help="extra MCP server for the agent, e.g. 'uvx some-mcp-server' (repeatable)",
    )
    p.set_defaults(func=cmd_plan)

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

    p = sub.add_parser("serve", help="start the web UI")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.set_defaults(func=cmd_serve)

    p = sub.add_parser("export-site", help="export the web UI as a static site")
    p.add_argument("-o", "--output", default="site", help="output folder (default: site)")
    p.add_argument(
        "--fragment",
        action="store_true",
        help="omit <html>/<head>/<body> for hosts that wrap pages in their own skeleton",
    )
    p.add_argument(
        "--api-base",
        metavar="URL",
        help="use a hosted Clarchy API (clarchy serve) instead of embedded demo data",
    )
    p.add_argument(
        "--no-engine", action="store_true", help="replay-only page, no in-browser engine"
    )
    p.add_argument(
        "--pyodide-base", metavar="URL", help="where to load Pyodide from (default: its CDN)"
    )
    p.set_defaults(func=cmd_export_site)

    p = sub.add_parser("prices", help="refresh or search the latest AWS prices")
    p.add_argument("action", choices=["update", "lookup"])
    p.add_argument("service", nargs="?", help="lookup: AWS service code, e.g. AmazonS3")
    p.add_argument("search", nargs="*", help="lookup: words to find, e.g. storage")
    p.add_argument("--output", help="update: price book to write (default: your user cache)")
    p.add_argument("--cache", help="update: folder to keep downloaded offer files")
    p.set_defaults(func=cmd_prices)

    p = sub.add_parser("mcp", help="run Clarchy as an MCP server for AI clients")
    p.add_argument("--transport", default="stdio", choices=["stdio", "streamable-http"])
    p.add_argument("--port", type=int, default=8765, help="port for streamable-http")
    p.set_defaults(func=cmd_mcp)
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
