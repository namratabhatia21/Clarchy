"""CloudArchie as an MCP server.

    cloudarchie mcp                       # stdio, for Claude Desktop / Claude Code
    cloudarchie mcp --transport streamable-http --port 8765

Any MCP client can then list capabilities and patterns, search equivalent services across
clouds, validate a spec, add a build-and-deploy toolchain, draft a design from plain-text
requirements and render diagrams. The built-in planning agent talks to this same server.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from cloudarchie import catalog
from cloudarchie.tools import TOOLS

INSTRUCTIONS = """\
CloudArchie designs cloud architectures as cloud-neutral YAML specs built from
capabilities (object-storage, relational-db, kubernetes, ...), then maps them to AWS,
Azure, Google Cloud or open-source services. Typical flow: list_patterns and
get_pattern for a starting point, list_capabilities for the vocabulary, write or adapt a
spec, validate_spec until it is valid, add_delivery_toolchain for build and deploy, then
render_design for the chosen provider. search_services finds equivalent services across
providers. draft_architecture produces a rule-based first draft from requirements text.
"""


def build_server(log_level: str = "WARNING") -> FastMCP:
    server = FastMCP("cloudarchie", instructions=INSTRUCTIONS, log_level=log_level)
    for tool in TOOLS.values():
        server.add_tool(tool.func, name=tool.name, description=tool.description)

    @server.resource("cloudarchie://patterns/{pattern_id}", mime_type="application/yaml")
    def pattern_resource(pattern_id: str) -> str:
        """A reference architecture as a YAML spec."""
        return catalog.pattern_text(pattern_id)

    @server.prompt(name="design_architecture")
    def design_architecture(requirements: str) -> str:
        """Design a cloud architecture for the given requirements using CloudArchie's tools."""
        return (
            "Design a cloud architecture for these requirements using the CloudArchie tools.\n"
            "1. Call list_patterns and read the closest pattern with get_pattern.\n"
            "2. Write a spec using only capabilities from list_capabilities; give every "
            "component a rationale tied to the requirements.\n"
            "3. Call validate_spec and fix every error.\n"
            "4. Call add_delivery_toolchain, then render_design for the provider I care about.\n"
            "5. Explain the design, the trade-offs and what you assumed.\n\n"
            f"Requirements:\n{requirements}"
        )

    return server


def main(transport: str = "stdio", port: int = 8765) -> None:
    server = build_server()
    server.settings.port = port
    server.run(transport=transport)  # type: ignore[arg-type]
