"""Deterministic SVG architecture diagrams.

Layout comes from the spec, never from an LLM:
- the build-and-deploy toolchain sits in a "Build and deploy" lane at the top;
- runtime capabilities are placed in columns by tier
  (external -> edge -> entry -> compute -> integration -> data);
- platform services sit in a "Shared services" band at the bottom.
Boxes in a column are ordered by the average position of their neighbours to reduce
crossing lines. Links between the lanes (a release reaching the runtime, a service reading
secrets) are not drawn because they would cross the whole diagram; the workflows and the
explanation describe them.

Colours, fonts and the cloud boundary come from the provider's theme
(data/mappings/<provider>.yaml), so an AWS diagram follows AWS diagram conventions and an
Azure diagram follows Azure's. The same spec always produces byte-identical SVG.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from xml.sax.saxutils import escape, quoteattr

from clarchy import catalog
from clarchy.icons import IconLibrary
from clarchy.mapping import MappedComponent, ProviderArchitecture

FLOW_TIERS = ("external", "edge", "entry", "compute", "integration", "data")
LANE_TIERS = ("delivery", "platform")

NODE_W, NODE_H = 156, 116
COL_GAP, ROW_GAP = 72, 32
LANE_GAP = 64
MARGIN, TITLE_H = 24, 80
GROUP_PAD, GROUP_HEADER = 22, 30
BAND_HEADER = 34
ICON = 48
FOOTER_H = 28

DEFAULT_THEME: dict[str, Any] = {
    "font": "'Helvetica Neue', Arial, sans-serif",
    "frame": {"stroke": "#232F3E", "fill": "#FFFFFF", "label": "#232F3E", "dash": ""},
    "band": {"stroke": "#879196", "label": "#545B64"},
    "edge": "#545B64",
    "categories": {},
}
FALLBACK_COLOUR = "#545B64"


def theme_for(provider: str) -> dict[str, Any]:
    theme = catalog.provider_mapping(provider)["provider"].get("theme") or {}
    merged = {**DEFAULT_THEME, **theme}
    for key in ("frame", "band"):
        merged[key] = {**DEFAULT_THEME[key], **theme.get(key, {})}
    return merged


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

    # Connected boxes in the same column go next to each other, so their link is short.
    in_column = {m.component.id: ci for ci, col in enumerate(columns) for m in col}
    for edge in arch.spec.edges:
        ci = in_column.get(edge.source)
        if ci is None or in_column.get(edge.target) != ci:
            continue
        col = columns[ci]
        ids = [m.component.id for m in col]
        i, j = ids.index(edge.source), ids.index(edge.target)
        if abs(i - j) > 1:
            moved = col.pop(j)
            i = ids.index(edge.source) if j > i else ids.index(edge.source) - 1
            col.insert(i + 1 if j > i else i, moved)


def _layout(arch: ProviderArchitecture) -> tuple[dict[str, Box], dict[str, float]]:
    flow = [m for m in arch.components if m.component.tier not in LANE_TIERS]
    delivery = [m for m in arch.components if m.component.tier == "delivery"]
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
    cloud_top = TITLE_H + MARGIN
    delivery_top = cloud_top + GROUP_HEADER if delivery else -1
    flow_top = cloud_top + GROUP_HEADER
    if delivery:
        flow_top = delivery_top + BAND_HEADER + NODE_H + 14 + GROUP_PAD
    tallest = max((len(c) for c in columns), default=0)
    flow_h = tallest * NODE_H + max(tallest - 1, 0) * ROW_GAP

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
    cloud_left = (
        cloud_cols[0] if cloud_cols else MARGIN + NODE_W + COL_GAP + GROUP_PAD
    ) - GROUP_PAD
    right = (cloud_cols[-1] + NODE_W) if cloud_cols else cloud_left + GROUP_PAD
    bottom = flow_top + flow_h if columns else flow_top

    if delivery:
        y = delivery_top + BAND_HEADER
        for k, m in enumerate(delivery):
            boxes[m.component.id] = Box(cloud_left + GROUP_PAD + k * (NODE_W + LANE_GAP), y)
        right = max(right, cloud_left + GROUP_PAD + len(delivery) * (NODE_W + LANE_GAP) - LANE_GAP)

    platform_top = -1.0
    if platform:
        platform_top = bottom + GROUP_PAD
        y = platform_top + BAND_HEADER
        for k, m in enumerate(platform):
            boxes[m.component.id] = Box(cloud_left + GROUP_PAD + k * (NODE_W + ROW_GAP), y)
        right = max(right, cloud_left + GROUP_PAD + len(platform) * (NODE_W + ROW_GAP) - ROW_GAP)
        bottom = y + NODE_H

    frame = {
        "cloud_left": cloud_left,
        "cloud_top": cloud_top,
        "cloud_right": right + GROUP_PAD,
        "cloud_bottom": bottom + GROUP_PAD,
        "delivery_top": delivery_top,
        "delivery_bottom": delivery_top + BAND_HEADER + NODE_H + 14 if delivery else -1,
        "platform_top": platform_top,
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


ARROW_LEN, ARROW_HALF = 9, 4.5


def _arrowhead(x: float, y: float, dx: float, dy: float) -> str:
    """A filled triangle pointing along (dx, dy) with its tip at (x, y). Drawn shapes
    rather than an SVG marker, so diagrams never share ids when several are on a page."""
    if abs(dx) >= abs(dy):
        sign = 1 if dx > 0 else -1
        base = x - sign * ARROW_LEN
        pts = [(x, y), (base, y - ARROW_HALF), (base, y + ARROW_HALF)]
    else:
        sign = 1 if dy > 0 else -1
        base = y - sign * ARROW_LEN
        pts = [(x, y), (x - ARROW_HALF, base), (x + ARROW_HALF, base)]
    return " ".join(f"{_n(px)},{_n(py)}" for px, py in pts)


def _edge_svg(source: str, target: str, a: Box, b: Box, label: str | None) -> list[str]:
    x1, y1, x2, y2, horizontal = _anchor_points(a, b)
    same_column = abs(a.x - b.x) < 1
    skips_a_row = abs(a.cy - b.cy) > NODE_H + ROW_GAP + 1
    if same_column and skips_a_row:
        # Route around the right-hand side instead of through the boxes in between.
        x1, y1, x2, y2 = a.x + a.w, a.cy, b.x + b.w, b.cy
        bulge = x1 + COL_GAP * 0.6
        d = f"M{_n(x1)},{_n(y1)} C{_n(bulge)},{_n(y1)} {_n(bulge)},{_n(y2)} {_n(x2)},{_n(y2)}"
        tangent = (x2 - bulge, 0.0)
    elif horizontal:
        mid = (x1 + x2) / 2
        d = f"M{_n(x1)},{_n(y1)} C{_n(mid)},{_n(y1)} {_n(mid)},{_n(y2)} {_n(x2)},{_n(y2)}"
        tangent = (x2 - mid, 0.0)
    else:
        mid = (y1 + y2) / 2
        d = f"M{_n(x1)},{_n(y1)} C{_n(x1)},{_n(mid)} {_n(x2)},{_n(mid)} {_n(x2)},{_n(y2)}"
        tangent = (0.0, y2 - mid)
    ends = f"data-from={quoteattr(source)} data-to={quoteattr(target)}"
    out = [
        f'<path class="ca-edge" {ends} d="{d}"/>',
        f'<polygon class="ca-arrow" {ends} points="{_arrowhead(x2, y2, *tangent)}"/>',
    ]
    if label:
        out.append(
            f'<text class="ca-edge-label" {ends} x="{_n((x1 + x2) / 2)}" '
            f'y="{_n((y1 + y2) / 2 - 6)}" text-anchor="middle">{escape(label)}</text>'
        )
    return out


def _person_icon(x: float, y: float, colour: str) -> str:
    cx = x + ICON / 2
    return (
        f'<g fill="{colour}"><circle cx="{_n(cx)}" cy="{_n(y + 14)}" r="10"/>'
        f'<path d="M{_n(cx - 18)},{_n(y + 46)} Q{_n(cx - 18)},{_n(y + 28)} {_n(cx)},{_n(y + 28)}'
        f' Q{_n(cx + 18)},{_n(y + 28)} {_n(cx + 18)},{_n(y + 46)} Z"/></g>'
    )


def _node_svg(m: MappedComponent, box: Box, icons: IconLibrary, colours: dict) -> list[str]:
    comp, choice = m.component, m.choice
    colour = colours.get(comp.category, FALLBACK_COLOUR)
    ix, iy = box.x + (box.w - ICON) / 2, box.y + 10
    out = [
        f'<g class="node" data-id={quoteattr(comp.id)} '
        f"data-capability={quoteattr(comp.capability)} "
        f"data-stage={quoteattr(comp.stage or '')}>",
        f'<rect class="ca-node-box" x="{_n(box.x)}" y="{_n(box.y)}" width="{_n(box.w)}" '
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
                f'<text class="ca-badge" x="{_n(ix + ICON / 2)}" y="{_n(iy + ICON / 2 + 5)}" '
                f'text-anchor="middle">{escape(choice.short)}</text>'
            )
        title = choice.service
        subtitle = comp.display_label

    ty = iy + ICON + 16
    for k, line in enumerate(_wrap(title, 22, 2)):
        out.append(
            f'<text class="ca-service" x="{_n(box.cx)}" y="{_n(ty + k * 14)}" '
            f'text-anchor="middle">{escape(line)}</text>'
        )
    if subtitle:
        sub = _wrap(subtitle, 26, 1)[0]
        out.append(
            f'<text class="ca-label" x="{_n(box.cx)}" y="{_n(box.y + box.h - 7)}" '
            f'text-anchor="middle">{escape(sub)}</text>'
        )
    if choice is not None and choice.fidelity != "exact":
        out.append(
            f'<text class="ca-fidelity" x="{_n(box.x + box.w - 6)}" y="{_n(box.y + 14)}" '
            f'text-anchor="end">{escape(choice.fidelity)}</text>'
        )
    out.append("</g>")
    return out


def _style(theme: dict[str, Any], scope: str) -> str:
    """CSS for one diagram, scoped to its provider class. Inline SVGs share the page's
    style sheet, so unscoped rules would leak into the page and into other diagrams."""
    font, frame, band, edge = theme["font"], theme["frame"], theme["band"], theme["edge"]
    dash = f"stroke-dasharray:{frame['dash']};" if frame.get("dash") else ""
    rules = {
        "": f"font-family:{font}",
        ".ca-bg": "fill:#ffffff",
        ".ca-title": "font-size:18px;font-weight:600;fill:#16191f",
        ".ca-subtitle": "font-size:13px;fill:#545b64",
        ".ca-cloud": f"fill:{frame['fill']};stroke:{frame['stroke']};stroke-width:1.5;{dash}",
        ".ca-cloud-label": f"font-size:13px;font-weight:600;fill:{frame['label']}",
        ".ca-band": f"fill:none;stroke:{band['stroke']};stroke-dasharray:5 4",
        ".ca-band-label": f"font-size:12px;font-weight:600;fill:{band['label']}",
        ".ca-node-box": "fill:#ffffff;stroke-width:1.5",
        ".ca-badge": "font-size:14px;font-weight:700;fill:#ffffff",
        ".ca-service": "font-size:12px;font-weight:600;fill:#16191f",
        ".ca-label": "font-size:11px;fill:#545b64",
        ".ca-fidelity": "font-size:10px;font-style:italic;fill:#b0084d",
        ".ca-edge": f"fill:none;stroke:{edge};stroke-width:1.5",
        ".ca-arrow": f"fill:{edge}",
        ".ca-edge-label": "font-size:11px;fill:#16191f;paint-order:stroke;stroke:#ffffff;"
        "stroke-width:4",
        ".ca-footer": "font-size:10px;fill:#879196",
    }
    return "\n".join(
        f".{scope}{(' ' + sel) if sel else ''}{{{body}}}" for sel, body in rules.items()
    )


def _band(frame: dict, top: float, bottom: float, label: str) -> list[str]:
    return [
        f'<rect class="ca-band" x="{_n(frame["cloud_left"] + 10)}" y="{_n(top)}" '
        f'width="{_n(frame["cloud_right"] - frame["cloud_left"] - 20)}" '
        f'height="{_n(bottom - top)}" rx="4"/>',
        f'<text class="ca-band-label" x="{_n(frame["cloud_left"] + 20)}" '
        f'y="{_n(top + 20)}">{escape(label)}</text>',
    ]


def render_svg(arch: ProviderArchitecture, icons: IconLibrary | None = None) -> str:
    """A provider's diagram, drawn the way its own documentation draws one (render_doc.py),
    or, for providers without such conventions (open source), as service cards."""
    from clarchy.render_doc import look_for, render_documented

    icons = icons or IconLibrary(None)
    look = look_for(arch.provider)
    if look is not None:
        return render_documented(arch, icons, look)
    return _render_cards(arch, icons)


def _render_cards(arch: ProviderArchitecture, icons: IconLibrary) -> str:
    theme = theme_for(arch.provider)
    boxes, f = _layout(arch)
    spec = arch.spec
    width, height = f["width"], f["height"]
    w = max(width, 520)

    scope = f"ca-{arch.provider}"
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" class="ca-diagram {scope}" '
        f'width="{_n(w)}" height="{_n(height)}" '
        f'viewBox="0 0 {_n(w)} {_n(height)}" role="img" '
        # Pages that already show the title and notice can crop to the diagram body.
        f'data-body-top="{TITLE_H}" data-body-bottom="{_n(height - FOOTER_H)}" '
        f"aria-label={quoteattr(f'{spec.name} on {arch.provider_name}')}>",
        f"<style>{_style(theme, scope)}</style>",
        f'<rect class="ca-bg" width="{_n(w)}" height="{_n(height)}"/>',
        f'<text class="ca-title" x="{MARGIN}" y="{MARGIN + 12}">'
        f"{escape(spec.name)} · {escape(arch.provider_name)}</text>",
    ]
    if spec.summary:
        out.append(
            f'<text class="ca-subtitle" x="{MARGIN}" y="{MARGIN + 32}">'
            f"{escape(_wrap(spec.summary, 140, 1)[0])}</text>"
        )
    out += [
        f'<rect class="ca-cloud" x="{_n(f["cloud_left"])}" y="{_n(f["cloud_top"])}" '
        f'width="{_n(f["cloud_right"] - f["cloud_left"])}" '
        f'height="{_n(f["cloud_bottom"] - f["cloud_top"])}" rx="4"/>',
        f'<text class="ca-cloud-label" x="{_n(f["cloud_left"] + 10)}" '
        f'y="{_n(f["cloud_top"] + 19)}">{escape(arch.cloud_label)} · '
        f"{escape(arch.region_text)}</text>",
    ]
    if f["delivery_top"] >= 0:
        out += _band(f, f["delivery_top"], f["delivery_bottom"], "Build and deploy")
    if f["platform_top"] >= 0:
        out += _band(f, f["platform_top"], f["cloud_bottom"] - 10, "Shared services")

    lane = {m.component.id: m.component.tier for m in arch.components}
    for edge in spec.edges:
        a, b = lane[edge.source], lane[edge.target]
        crosses_lane = (a in LANE_TIERS or b in LANE_TIERS) and a != b
        if crosses_lane or a == b == "platform":
            continue
        out += _edge_svg(
            edge.source, edge.target, boxes[edge.source], boxes[edge.target], edge.label
        )
    for m in arch.components:
        out += _node_svg(m, boxes[m.component.id], icons, theme["categories"])

    owner = "these projects" if arch.provider == "oss" else escape(arch.provider_name)
    out.append(
        f'<text class="ca-footer" x="{MARGIN}" y="{_n(height - 12)}">Generated by Clarchy. '
        f"Service names{' and icons' if icons.root is not None else ''} belong to their owners; "
        f"Clarchy is not affiliated with {owner}.</text>"
    )
    out.append("</svg>")
    return "\n".join(out) + "\n"
