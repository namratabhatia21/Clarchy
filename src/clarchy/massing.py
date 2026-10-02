"""A design as an architect's massing model (ADR 0015).

Each running service is a block on a base, with its icon on top and its height set by what
it costs a month, so the expensive parts of a design stand out at a glance. Blocks stand
in lifecycle zones, the way a drawing groups them: serve, run, integrate and store in the
order a request meets them, and operate along the front edge. Connections run along the
base, under the blocks. Callouts name the costliest services.

The home page shows one, made when the site is built from a real example and the current
price book. The SVG is styled by the page (classes `m-*`), so it follows the light and dark
themes, and its blocks rise once when it is shown.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from html import escape
from typing import Any

from clarchy.icons import IconLibrary
from clarchy.mapping import ProviderArchitecture
from clarchy.payloads import capability_title

COLUMNS = ("serve", "run", "integrate", "store")  # back of the base to the front of the flow
S = 34.0  # pixels per base unit
COS = math.cos(math.radians(30))
SIN = 0.5
BLOCK = 1.8  # a block's footprint, in base units
PITCH = 2.5  # from one block to the next
THICK = 0.6  # the base's thickness
LOW, HIGH = 0.45, 3.4  # the shortest block, and how much taller the costliest one is
CALLOUTS = 4  # at most, for services that are at least SHARE of the bill
SHARE = 0.03


@dataclass
class Block:
    id: str
    name: str
    service: str
    x: float
    y: float
    h: float
    monthly: float
    icon: str | None
    short: str


def _p(x: float, y: float, z: float = 0.0) -> tuple[float, float]:
    return (x - y) * COS * S, (x + y) * SIN * S - z * S


def _pts(points: list[tuple[float, float]]) -> str:
    return " ".join(f"{a:.1f},{b:.1f}" for a, b in points)


def _poly(cls: str, points: list[tuple[float, float]]) -> str:
    return f'<polygon class="{cls}" points="{_pts(points)}"/>'


def _text(cls: str, x: float, y: float, anchor: str, text: str) -> str:
    return (
        f'<text class="{cls}" x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}">{escape(text)}</text>'
    )


def _money(value: float) -> str:
    return f"${value:,.0f}" if value >= 10 else f"${value:,.2f}".rstrip("0").rstrip(".")


def layout(arch: ProviderArchitecture, cost: dict[str, Any]) -> tuple[list[Block], float, float]:
    """Where each running service stands, and the base's width and depth."""
    monthly = {line["component"]: line["monthly"] for line in cost.get("lines", [])}
    stages = (*COLUMNS, "operate")
    running = [m for m in arch.components if m.choice and m.component.stage in stages]
    columns = [[m for m in running if m.component.stage == stage] for stage in COLUMNS]
    columns = [c for c in columns if c]
    front = [m for m in running if m.component.stage == "operate"]
    rows = max((len(c) for c in columns), default=0)
    top = max([monthly.get(m.component.id, 0.0) for m in running] + [1.0])

    def block(m, x: float, y: float) -> Block:
        cost_ = monthly.get(m.component.id, 0.0)
        return Block(
            id=m.component.id,
            name=capability_title(m.component.capability),
            service=m.choice.service,
            x=x,
            y=y,
            h=LOW + HIGH * math.sqrt(cost_ / top),
            monthly=cost_,
            icon=m.choice.icon,
            short=m.choice.short,
        )

    blocks = [
        block(m, 0.7 + ci * (PITCH + 0.2), 0.7 + ri * PITCH)
        for ci, column in enumerate(columns)
        for ri, m in enumerate(column)
    ]
    front_y = 0.7 + rows * PITCH + 0.3
    blocks += [block(m, 0.7 + k * PITCH, front_y) for k, m in enumerate(front)]
    width = max(len(columns) * (PITCH + 0.2), len(front) * PITCH) + 0.5
    depth = front_y + (PITCH if front else 0.0) + (0.2 if front else 0.0)
    return blocks, width, depth


def _callouts(blocks: list[Block], tops: dict[str, tuple[float, float]], ceiling: float):
    """Labels above the model for the costliest services, each on a leader from its block.
    No label sits across another callout's leader or label."""
    total = sum(b.monthly for b in blocks) or 1.0
    worth = [b for b in blocks if b.monthly >= SHARE * total]
    chosen = sorted(worth, key=lambda b: -b.monthly)[:CALLOUTS]
    placed: list[dict[str, Any]] = []
    # Right to left, each as low as it fits: a label reaches right from its leader, so it
    # can only meet the leaders of labels further right, which stop below it.
    for b in sorted(chosen, key=lambda b: -tops[b.id][0]):
        bx, _by = tops[b.id]
        line1 = f"{b.name.upper()} · {_money(b.monthly)}/MO"
        width = max(len(line1) * 7.7, len(b.service) * 6.5)
        for row in range(6):
            y = ceiling - 22 - row * 44
            for side in (1,):
                x0, x1 = (bx + 6, bx + 6 + width) if side == 1 else (bx - 6 - width, bx - 6)
                clash = any(
                    (p["row"] == row and x0 < p["x1"] + 14 and p["x0"] < x1 + 14)
                    or (p["row"] > row and x0 - 4 < p["bx"] < x1 + 4)
                    or (p["row"] < row and p["x0"] - 4 < bx < p["x1"] + 4)
                    for p in placed
                )
                if not clash:
                    placed.append(
                        {
                            "block": b,
                            "row": row,
                            "y": y,
                            "x0": x0,
                            "x1": x1,
                            "bx": bx,
                            "side": side,
                            "line1": line1,
                        }
                    )
                    break
            else:
                continue
            break
    return placed


def svg(arch: ProviderArchitecture, cost: dict[str, Any], icons: IconLibrary) -> str:
    """The massing model as inline SVG."""
    blocks, width, depth = layout(arch, cost)
    by_id = {b.id: b for b in blocks}
    out: list[str] = []
    base = [(0.0, 0.0), (width, 0.0), (width, depth), (0.0, depth)]
    shade = [_p(x + 0.9, y + 0.9, -THICK - 0.15) for x, y in base]
    front = [_p(0, depth), _p(width, depth), _p(width, depth, -THICK), _p(0, depth, -THICK)]
    side = [_p(width, 0), _p(width, depth), _p(width, depth, -THICK), _p(width, 0, -THICK)]
    out.append(_poly("m-shadow", shade))
    out.append(_poly("m-base-left", front))
    out.append(_poly("m-base-right", side))
    out.append(_poly("m-base-top", [_p(x, y) for x, y in base]))

    # Zones: a dashed outline round each lifecycle column and the operate row.
    groups: dict[float, list[Block]] = {}
    for b in blocks:
        key = b.y if arch_stage(arch, b.id) == "operate" else -b.x
        groups.setdefault(key, []).append(b)
    for members in groups.values():
        x0 = min(b.x for b in members) - 0.35
        y0 = min(b.y for b in members) - 0.35
        x1 = max(b.x for b in members) + BLOCK + 0.35
        y1 = max(b.y for b in members) + BLOCK + 0.35
        zone = [_p(x0, y0), _p(x1, y0), _p(x1, y1), _p(x0, y1)]
        out.append(_poly("m-zone", zone))

    # Connections along the base, under the blocks; visitors come in from the left edge.
    def centre(b: Block) -> tuple[float, float]:
        return _p(b.x + BLOCK / 2, b.y + BLOCK / 2)

    entry_label = None
    for edge in arch.spec.edges:
        src, dst = by_id.get(edge.source), by_id.get(edge.target)
        if src and dst:
            out.append(f'<polyline class="m-wire" points="{_pts([centre(src), centre(dst)])}"/>')
        elif dst and not src and arch_stage(arch, edge.source) == "users":
            start = _p(-1.8, dst.y + BLOCK / 2)
            out.append(f'<polyline class="m-wire" points="{_pts([start, centre(dst)])}"/>')
            entry_label = (start, label_of(arch, edge.source))

    tops: dict[str, tuple[float, float]] = {}
    for i, b in enumerate(sorted(blocks, key=lambda b: (b.x + b.y, b.x))):
        x, y, h = b.x, b.y, b.h
        x1, y1 = x + BLOCK, y + BLOCK
        faces = [
            ("m-left", [_p(x, y1), _p(x1, y1), _p(x1, y1, h), _p(x, y1, h)]),
            ("m-right", [_p(x1, y), _p(x1, y1), _p(x1, y1, h), _p(x1, y, h)]),
            ("m-top", [_p(x, y, h), _p(x1, y, h), _p(x1, y1, h), _p(x, y1, h)]),
        ]
        parts = [_poly(cls, pts) for cls, pts in faces]
        side = BLOCK * 0.62
        ox, oy = _p(x + (BLOCK - side) / 2, y + (BLOCK - side) / 2, h)
        matrix = (COS * S * side, SIN * S * side, -COS * S * side, SIN * S * side, ox, oy)
        transform = f"matrix({' '.join(f'{v:.3f}' for v in matrix)})"
        uri = icons.data_uri(b.icon)
        if uri:
            parts.append(f'<image href="{uri}" width="1" height="1" transform="{transform}"/>')
        else:
            parts.append(
                f'<text class="m-badge" transform="{transform}" x=".5" y=".62" '
                f'font-size=".34" text-anchor="middle">{escape(b.short)}</text>'
            )
        out.append(f'<g class="m-blk" style="--i:{i}">{"".join(parts)}</g>')
        tops[b.id] = _p(x + BLOCK / 2, y + BLOCK / 2, h)

    xs = [_p(x, y, z)[0] for x, y in base for z in (0, -THICK)]
    ys = [_p(x, y, z)[1] for x, y in base for z in (0, -THICK)] + [t[1] for t in tops.values()]
    ceiling = min(ys) - 18
    labels = _callouts(blocks, tops, ceiling)
    for c in labels:
        b, (bx, by) = c["block"], tops[c["block"].id]
        anchor = "start" if c["side"] == 1 else "end"
        tx = bx + 6 * c["side"]
        out.append(
            f'<g class="m-callout"><path class="m-leader" d="M{bx:.1f} {by:.1f}V{c["y"] - 9:.1f}"/>'
            f'<circle class="m-dot" cx="{bx:.1f}" cy="{by:.1f}" r="3"/>'
            + _text("m-name", tx, c["y"] - 12, anchor, c["line1"])
            + _text("m-svc", tx, c["y"] + 4, anchor, b.service)
            + "</g>"
        )
    if entry_label:
        (ex, ey), text = entry_label
        out.append(_text("m-name m-entry", ex - 8, ey + 4, "end", text.upper()))
        xs.append(ex - 8 - len(text) * 7.7)

    xs += [c["x0"] for c in labels] + [c["x1"] for c in labels]
    top_y = min([ceiling] + [c["y"] - 26 for c in labels])
    left, right = min(xs) - 10, max(xs) + 10
    bottom = max(ys + [_p(width + 0.9, depth + 0.9, -THICK - 0.15)[1]]) + 10
    total = sum(line["monthly"] for line in cost.get("lines", []))
    described = "; ".join(
        f"{b.name}, {b.service}, {_money(b.monthly)} a month"
        for b in sorted(blocks, key=lambda b: -b.monthly)
    )
    title = f"{arch.spec.name} on {arch.provider_name} as a massing model"
    desc = (
        f"{len(blocks)} running services, about {_money(total)} a month in "
        f"{cost.get('price_region', arch.region_label)}. Block height is monthly cost. {described}."
    )
    # How much of the width the callouts take above the model, so a narrow page can drop them.
    band = (ceiling - top_y) / (right - left) * 100
    view = f"{left:.0f} {top_y:.0f} {right - left:.0f} {bottom - top_y:.0f}"
    return (
        f'<svg class="massing" viewBox="{view}" style="--band:{band:.2f}%" role="img" '
        'aria-labelledby="massing-title massing-desc" xmlns="http://www.w3.org/2000/svg">'
        f'<title id="massing-title">{escape(title)}</title>'
        f'<desc id="massing-desc">{escape(desc)}</desc>' + "".join(out) + "</svg>"
    )


def arch_stage(arch: ProviderArchitecture, component_id: str) -> str | None:
    found = (m.component.stage for m in arch.components if m.component.id == component_id)
    return next(found, None)


def label_of(arch: ProviderArchitecture, component_id: str) -> str:
    return next(
        (m.component.display_label for m in arch.components if m.component.id == component_id),
        component_id,
    )
