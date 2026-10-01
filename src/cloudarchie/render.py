"""Deterministic SVG architecture diagrams.

Layout comes from the spec, never from an LLM: capabilities are placed in columns by
tier (external -> edge -> entry -> compute -> integration -> data), platform services sit
in a shared-services band, and everything inside the cloud boundary is grouped. Boxes in a
column are ordered by the average position of their neighbours to reduce crossing lines.
Links to platform services are not drawn (they would cross the whole diagram); the explain
output lists them. The same spec always produces byte-identical SVG, which keeps golden-file
tests meaningful.
"""

from __future__ import annotations

from dataclasses import dataclass
from xml.sax.saxutils import escape, quoteattr

from cloudarchie.icons import IconLibrary
from cloudarchie.mapping import MappedComponent, ProviderArchitecture

FLOW_TIERS = ("external", "edge", "entry", "compute", "integration", "data")

NODE_W, NODE_H = 156, 116
COL_GAP, ROW_GAP = 72, 32
MARGIN, TITLE_H = 24, 80
GROUP_PAD, GROUP_HEADER = 22, 30
BAND_HEADER = 34
ICON = 48
FOOTER_H = 28

TIER_COLOURS = {
    "external": "#545B64",
    "edge": "#8C4FFF",
    "entry": "#E7157B",
    "compute": "#ED7100",
    "integration": "#B0084D",
    "data": "#3B48CC",
    "platform": "#DD344C",
}


@dataclass(frozen=True)
class Box:
    x: float
    y: float
    w: float = NODE_W
    h: float = NODE_H

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def cy(self) -> float:
        return self.y + self.h / 2


def _n(value: float) -> str:
    """Stable number formatting so output is byte-identical across runs."""
    return f"{round(value, 1):g}"


def _wrap(text: str, width: int, max_lines: int) -> list[str]:
    words, lines, line = text.split(), [], ""
    for word in words:
        candidate = f"{line} {word}".strip()
        if len(candidate) <= width or not line:
            line = candidate
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1][: width - 1].rstrip() + "…"
    return lines


def _reduce_crossings(arch: ProviderArchitecture, columns: list[list[MappedComponent]]) -> None:
    """Barycentre ordering: sort each column by the mean centred row of its neighbours in
    other columns. Two forward and backward sweeps; ties keep spec order (deterministic)."""
    neighbours: dict[str, set[str]] = {m.component.id: set() for m in arch.components}
    for edge in arch.spec.edges:
        neighbours[edge.source].add(edge.target)
        neighbours[edge.target].add(edge.source)
    spec_order = {m.component.id: i for i, m in enumerate(arch.components)}

    def positions() -> dict[str, tuple[int, float]]:
        return {
            m.component.id: (ci, j - (len(col) - 1) / 2)
            for ci, col in enumerate(columns)
            for j, m in enumerate(col)
        }

    sweep = list(range(len(columns)))
    for order in (sweep, sweep[::-1], sweep, sweep[::-1]):
        for ci in order:
            pos = positions()

            def key(m: MappedComponent, ci: int = ci, pos=pos) -> tuple[float, int]:
                rows = [
                    pos[n][1] for n in neighbours[m.component.id] if n in pos and pos[n][0] != ci
                ]
                own = pos[m.component.id][1]
                return (sum(rows) / len(rows) if rows else own, spec_order[m.component.id])

            columns[ci].sort(key=key)


def _layout(arch: ProviderArchitecture) -> tuple[dict[str, Box], dict[str, float]]:
    flow = [m for m in arch.components if m.component.tier != "platform"]
    platform = [m for m in arch.components if m.component.tier == "platform"]

    columns: list[list[MappedComponent]] = []
    column_tiers: list[str] = []
    for tier in FLOW_TIERS:
        members = [m for m in flow if m.component.tier == tier]
        if members:
            columns.append(members)
            column_tiers.append(tier)

    _reduce_crossings(arch, columns)

    has_external = bool(column_tiers) and column_tiers[0] == "external"
    first_cloud_col = 1 if has_external else 0
    tallest = max((len(c) for c in columns), default=0)
    flow_h = tallest * NODE_H + max(tallest - 1, 0) * ROW_GAP
    flow_top = TITLE_H + MARGIN + GROUP_HEADER

    boxes: dict[str, Box] = {}
    col_x: list[float] = []
    for i, members in enumerate(columns):
        x = MARGIN + i * (NODE_W + COL_GAP) + (GROUP_PAD if i >= first_cloud_col else 0)
        col_x.append(x)
        col_h = len(members) * NODE_H + (len(members) - 1) * ROW_GAP
        y0 = flow_top + (flow_h - col_h) / 2
        for j, m in enumerate(members):
            boxes[m.component.id] = Box(x, y0 + j * (NODE_H + ROW_GAP))

    cloud_cols = col_x[first_cloud_col:]
    cloud_left = (cloud_cols[0] if cloud_cols else MARGIN + GROUP_PAD) - GROUP_PAD
    right = (cloud_cols[-1] + NODE_W) if cloud_cols else cloud_left + GROUP_PAD
    bottom = flow_top + flow_h

    band_top = None
    if platform:
        band_top = bottom + GROUP_PAD
        y = band_top + BAND_HEADER
        for k, m in enumerate(platform):
            boxes[m.component.id] = Box(cloud_left + GROUP_PAD + k * (NODE_W + ROW_GAP), y)
        right = max(right, cloud_left + GROUP_PAD + len(platform) * (NODE_W + ROW_GAP) - ROW_GAP)
        bottom = y + NODE_H

    frame = {
        "cloud_left": cloud_left,
        "cloud_top": flow_top - GROUP_HEADER,
        "cloud_right": right + GROUP_PAD,
        "cloud_bottom": bottom + GROUP_PAD,
        "band_top": band_top if band_top is not None else -1,
        "width": right + GROUP_PAD + MARGIN,
        "height": bottom + GROUP_PAD + MARGIN + FOOTER_H,
    }
    return boxes, frame


def _anchor_points(a: Box, b: Box) -> tuple[float, float, float, float, bool]:
    """Pick connection points on the facing sides. Returns (x1, y1, x2, y2, horizontal)."""
    if abs(b.cx - a.cx) > NODE_W / 2:
        if b.cx > a.cx:
            return a.x + a.w, a.cy, b.x, b.cy, True
        return a.x, a.cy, b.x + b.w, b.cy, True
    if b.cy > a.cy:
        return a.cx, a.y + a.h, b.cx, b.y, False
    return a.cx, a.y, b.cx, b.y + b.h, False


def _edge_svg(a: Box, b: Box, label: str | None) -> list[str]:
    x1, y1, x2, y2, horizontal = _anchor_points(a, b)
    if horizontal:
        mid = (x1 + x2) / 2
        d = f"M{_n(x1)},{_n(y1)} C{_n(mid)},{_n(y1)} {_n(mid)},{_n(y2)} {_n(x2)},{_n(y2)}"
    else:
        mid = (y1 + y2) / 2
        d = f"M{_n(x1)},{_n(y1)} C{_n(x1)},{_n(mid)} {_n(x2)},{_n(mid)} {_n(x2)},{_n(y2)}"
    out = [f'<path class="edge" d="{d}" marker-end="url(#arrow)"/>']
    if label:
        out.append(
            f'<text class="edge-label" x="{_n((x1 + x2) / 2)}" y="{_n((y1 + y2) / 2 - 6)}" '
            f'text-anchor="middle">{escape(label)}</text>'
        )
    return out


def _person_icon(x: float, y: float, colour: str) -> str:
    cx = x + ICON / 2
    return (
        f'<g fill="{colour}"><circle cx="{_n(cx)}" cy="{_n(y + 14)}" r="10"/>'
        f'<path d="M{_n(cx - 18)},{_n(y + 46)} Q{_n(cx - 18)},{_n(y + 28)} {_n(cx)},{_n(y + 28)}'
        f' Q{_n(cx + 18)},{_n(y + 28)} {_n(cx + 18)},{_n(y + 46)} Z"/></g>'
    )


def _node_svg(m: MappedComponent, box: Box, icons: IconLibrary) -> list[str]:
    comp, choice = m.component, m.choice
    colour = TIER_COLOURS[comp.tier]
    ix, iy = box.x + (box.w - ICON) / 2, box.y + 10
    out = [
        f'<g class="node" data-id={quoteattr(comp.id)} '
        f"data-capability={quoteattr(comp.capability)}>",
        f'<rect class="node-box" x="{_n(box.x)}" y="{_n(box.y)}" width="{_n(box.w)}" '
        f'height="{_n(box.h)}" rx="8" style="stroke:{colour}"/>',
    ]
    if choice is None:
        out.append(_person_icon(ix, iy, colour))
        title = comp.display_label
        subtitle = None
    else:
        uri = icons.data_uri(choice.icon)
        if uri:
            out.append(
                f'<image x="{_n(ix)}" y="{_n(iy)}" width="{ICON}" height="{ICON}" href="{uri}"/>'
            )
        else:
            out.append(
                f'<rect x="{_n(ix)}" y="{_n(iy)}" width="{ICON}" height="{ICON}" rx="6" '
                f'fill="{colour}"/>'
                f'<text class="badge" x="{_n(ix + ICON / 2)}" y="{_n(iy + ICON / 2 + 5)}" '
                f'text-anchor="middle">{escape(choice.short)}</text>'
            )
        title = choice.service
        subtitle = comp.display_label

    ty = iy + ICON + 16
    for k, line in enumerate(_wrap(title, 22, 2)):
        out.append(
            f'<text class="service" x="{_n(box.cx)}" y="{_n(ty + k * 14)}" '
            f'text-anchor="middle">{escape(line)}</text>'
        )
    if subtitle:
        sub = _wrap(subtitle, 26, 1)[0]
        out.append(
            f'<text class="label" x="{_n(box.cx)}" y="{_n(box.y + box.h - 7)}" '
            f'text-anchor="middle">{escape(sub)}</text>'
        )
    if choice is not None and choice.fidelity != "exact":
        out.append(
            f'<text class="fidelity" x="{_n(box.x + box.w - 6)}" y="{_n(box.y + 14)}" '
            f'text-anchor="end">{escape(choice.fidelity)}</text>'
        )
    out.append("</g>")
    return out


_STYLE = """
.bg{fill:#ffffff}
.title{font:600 18px sans-serif;fill:#16191f}
.subtitle{font:13px sans-serif;fill:#545b64}
.cloud{fill:#f8f9fa;stroke:#232f3e;stroke-width:1.5}
.cloud-label{font:600 13px sans-serif;fill:#232f3e}
.band{fill:none;stroke:#aab7b8;stroke-dasharray:5 4}
.band-label{font:600 12px sans-serif;fill:#545b64}
.node-box{fill:#ffffff;stroke-width:1.5}
.badge{font:700 14px sans-serif;fill:#ffffff}
.service{font:600 12px sans-serif;fill:#16191f}
.label{font:11px sans-serif;fill:#545b64}
.fidelity{font:italic 10px sans-serif;fill:#b0084d}
.edge{fill:none;stroke:#545b64;stroke-width:1.5}
.edge-label{font:11px sans-serif;fill:#16191f;paint-order:stroke;stroke:#ffffff;stroke-width:4}
.footer{font:10px sans-serif;fill:#879196}
""".strip()


def render_svg(arch: ProviderArchitecture, icons: IconLibrary | None = None) -> str:
    icons = icons or IconLibrary(None)
    boxes, f = _layout(arch)
    spec = arch.spec
    width, height = f["width"], f["height"]
    w = max(width, 520)

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{_n(w)}" height="{_n(height)}" '
        f'viewBox="0 0 {_n(w)} {_n(height)}" role="img" '
        f"aria-label={quoteattr(f'{spec.name} on {arch.provider_name}')}>",
        f"<style>{_STYLE}</style>",
        '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" '
        'markerHeight="8" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" '
        'fill="#545b64"/></marker></defs>',
        f'<rect class="bg" width="{_n(w)}" height="{_n(height)}"/>',
        f'<text class="title" x="{MARGIN}" y="{MARGIN + 12}">'
        f"{escape(spec.name)} · {escape(arch.provider_name)}</text>",
    ]
    if spec.summary:
        out.append(
            f'<text class="subtitle" x="{MARGIN}" y="{MARGIN + 32}">'
            f"{escape(_wrap(spec.summary, 140, 1)[0])}</text>"
        )
    out += [
        f'<rect class="cloud" x="{_n(f["cloud_left"])}" y="{_n(f["cloud_top"])}" '
        f'width="{_n(f["cloud_right"] - f["cloud_left"])}" '
        f'height="{_n(f["cloud_bottom"] - f["cloud_top"])}" rx="4"/>',
        f'<text class="cloud-label" x="{_n(f["cloud_left"] + 10)}" '
        f'y="{_n(f["cloud_top"] + 19)}">{escape(arch.cloud_label)} · '
        f"{escape(arch.region_label)} ({escape(arch.region_code)})</text>",
    ]
    if f["band_top"] >= 0:
        out += [
            f'<rect class="band" x="{_n(f["cloud_left"] + 10)}" y="{_n(f["band_top"])}" '
            f'width="{_n(f["cloud_right"] - f["cloud_left"] - 20)}" '
            f'height="{_n(f["cloud_bottom"] - f["band_top"] - 10)}" rx="4"/>',
            f'<text class="band-label" x="{_n(f["cloud_left"] + 20)}" '
            f'y="{_n(f["band_top"] + 20)}">Shared services</text>',
        ]

    for edge in spec.edges:
        if "platform" in (spec.component(edge.source).tier, spec.component(edge.target).tier):
            continue
        out += _edge_svg(boxes[edge.source], boxes[edge.target], edge.label)
    for m in arch.components:
        out += _node_svg(m, boxes[m.component.id], icons)

    out.append(
        f'<text class="footer" x="{MARGIN}" y="{_n(height - 12)}">Generated by CloudArchie. '
        f"Service names and icons belong to their owners; CloudArchie is not affiliated "
        f"with {escape(arch.provider_name)}.</text>"
    )
    out.append("</svg>")
    return "\n".join(out) + "\n"
