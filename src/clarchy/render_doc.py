"""Architecture diagrams drawn the way each cloud's own documentation draws them.

- AWS, as in AWS's reference architectures and its Architecture Icons deck: each service
  is its icon with its name under it; the AWS Cloud, Region, VPC and subnet groups carry
  AWS's group icons and colours; arrows are right-angled; numbered black markers follow
  the main request, with the steps written out under the drawing.
- Azure, as in the Azure Architecture Center: icons with names under them, a region
  boundary, a virtual network with its subnets marked by Azure's own icons, and numbered
  blue markers.
- Google Cloud, as in Google's architecture diagrams: product cards (icon, then name) on
  grey zones for Google Cloud, the region and the VPC network, and numbered blue markers.

Where each service sits (outside the region, in a public subnet, in the private network
or in the region) comes from `provider.diagram.placement` in data/mappings/<provider>.yaml.
Layout is computed, never guessed, and the same spec always gives byte-identical SVG.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from xml.sax.saxutils import escape, quoteattr

from clarchy import catalog
from clarchy.icons import IconLibrary
from clarchy.mapping import MappedComponent, ProviderArchitecture
from clarchy.render import (
    FALLBACK_COLOUR,
    FLOW_TIERS,
    FOOTER_H,
    LANE_TIERS,
    MARGIN,
    TITLE_H,
    _n,
    _reduce_crossings,
    _wrap,
    theme_for,
)
from clarchy.workflows import generate_workflows

ICON = 48
GROUP_HEAD = 42  # room for a group's icon and label above what it holds
PAD = 22  # inside a group, around what it holds
BAND_HEAD = 30
STACK_GAP = 26  # between the region's own services and its network
STEP_R = 9


@dataclass(frozen=True)
class Look:
    """How one provider's documentation draws a diagram."""

    key: str
    node: str  # "icon": the service icon with its name under it; "card": a product card
    node_w: float
    node_h: float
    col_gap: float
    row_gap: float
    font: str
    ink: str
    muted: str
    line: str
    step: str  # numbered markers
    radius: float  # group corners
    cloud_frame: bool  # a boundary around everything in the cloud
    users: str | None  # icon for the people outside the cloud
    region: str  # how the region's label starts
    group_icon: float  # size of a group's icon (0: none)
    groups: dict[str, dict[str, Any]] = field(default_factory=dict)


LOOKS: dict[str, Look] = {
    "aws": Look(
        key="aws",
        node="icon",
        node_w=150,
        node_h=110,
        col_gap=70,
        row_gap=26,
        font="'Amazon Ember', 'Helvetica Neue', Arial, sans-serif",
        ink="#232F3E",
        muted="#545B64",
        line="#232F3E",
        step="#232F3E",
        radius=0,
        cloud_frame=True,
        users="Users",
        region="",
        group_icon=32,
        # Colours and icons of AWS's group set (Architecture Icons, group icons).
        groups={
            "cloud": {"stroke": "#232F3E", "label": "#232F3E", "icon": "AWS-Cloud-logo"},
            "region": {"stroke": "#00A4A6", "dash": "6 4", "label": "#147EBA", "icon": "Region"},
            "vpc": {
                "stroke": "#8C4FFF",
                "label": "#8C4FFF",
                "icon": "Virtual-private-cloud-VPC",
                "text": "VPC",
            },
            "public": {
                "fill": "#F2F6E8",
                "label": "#248814",
                "icon": "Public-subnet",
                "text": "Public subnet",
            },
            "private": {
                "fill": "#E6F6F7",
                "label": "#147EBA",
                "icon": "Private-subnet",
                "text": "Private subnet",
            },
            "generic": {"stroke": "#7D8998", "dash": "6 4", "label": "#5A6C86"},
        },
    ),
    "azure": Look(
        key="azure",
        node="icon",
        node_w=150,
        node_h=110,
        col_gap=70,
        row_gap=26,
        font="'Segoe UI', 'Helvetica Neue', Arial, sans-serif",
        ink="#323130",
        muted="#605E5C",
        line="#605E5C",
        step="#0078D4",
        radius=4,
        cloud_frame=False,
        users="icon-service-Users",
        region="Azure region · ",
        group_icon=20,
        groups={
            "region": {"stroke": "#8A8886", "label": "#323130"},
            "vpc": {
                "stroke": "#0078D4",
                "label": "#323130",
                "icon": "icon-service-Virtual-Networks",
                "text": "Virtual network",
            },
            "public": {
                "stroke": "#0078D4",
                "dash": "4 3",
                "fill": "#F3F9FD",
                "label": "#323130",
                "icon": "icon-service-Subnet",
                "text": "App Gateway subnet",
            },
            "private": {
                "stroke": "#0078D4",
                "dash": "4 3",
                "fill": "#F3F9FD",
                "label": "#323130",
                "icon": "icon-service-Subnet",
                "text": "Workload subnet",
            },
            "generic": {"stroke": "#8A8886", "dash": "4 3", "label": "#605E5C"},
        },
    ),
    "gcp": Look(
        key="gcp",
        node="card",
        node_w=206,
        node_h=62,
        col_gap=84,
        row_gap=20,
        font="'Google Sans', Roboto, 'Helvetica Neue', Arial, sans-serif",
        ink="#202124",
        muted="#5F6368",
        line="#5F6368",
        step="#1A73E8",
        radius=8,
        cloud_frame=True,
        users=None,
        region="Region · ",
        group_icon=0,
        groups={
            "cloud": {"fill": "#F1F3F4", "label": "#5F6368", "text": "Google Cloud", "bold": True},
            "region": {"fill": "#FFFFFF", "stroke": "#DADCE0", "label": "#5F6368"},
            "vpc": {"fill": "#E8F0FE", "label": "#1967D2", "text": "VPC network"},
            "generic": {"fill": "#F8F9FA", "stroke": "#DADCE0", "dash": "4 3", "label": "#5F6368"},
        },
    ),
}


def look_icons(provider: str) -> set[str]:
    """The icons a provider's diagrams draw besides its services': its group icons and the
    icon for people outside the cloud."""
    look = look_for(provider)
    if look is None:
        return set()
    stems = {g["icon"] for g in look.groups.values() if g.get("icon")}
    return stems | ({look.users} if look.users else set())


def look_for(provider: str) -> Look | None:
    style = catalog.provider_mapping(provider)["provider"].get("diagram", {}).get("style")
    return LOOKS.get(style or "")


def _placement(provider: str) -> dict[str, str]:
    raw = catalog.provider_mapping(provider)["provider"].get("diagram", {}).get("placement", {})
    return {cap: zone for zone, caps in raw.items() for cap in caps}


@dataclass
class Node:
    m: MappedComponent
    x: float
    y: float
    w: float
    h: float
    col: int  # column in the flow, or -1 in a lane

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def cy(self) -> float:
        return self.y + self.h / 2


@dataclass
class Plan:
    nodes: dict[str, Node]
    groups: list[tuple[str, float, float, float, float, str]]  # kind, x, y, w, h, label
    col_left: list[float]
    col_right: list[float]
    width: float
    bottom: float  # below the drawing; the steps follow


def _rows(n: int, look: Look) -> float:
    return n * look.node_h + max(n - 1, 0) * look.row_gap


def _plan(arch: ProviderArchitecture, look: Look, wider: dict[int, float] | None = None) -> Plan:
    """Where everything goes. `wider` widens the gap after a column, by column index, for
    the links that run through it."""
    wider = wider or {}
    zone_of = _placement(arch.provider)

    def zone(m: MappedComponent) -> str:
        tier = m.component.tier
        if tier == "external":
            return "users"
        if tier == "delivery":
            return "delivery"
        if tier == "platform":
            return "shared"
        return zone_of.get(m.component.capability, "regional")

    users = [m for m in arch.components if zone(m) == "users"]
    delivery = [m for m in arch.components if zone(m) == "delivery"]
    shared = [m for m in arch.components if zone(m) == "shared"]
    flow = [m for m in arch.components if m.component.tier not in ("external", *LANE_TIERS)]

    # Columns: the users, then the cloud's global services, then the region, each by tier.
    columns: list[list[MappedComponent]] = []
    kinds: list[str] = []
    if users:
        columns.append(users)
        kinds.append("users")
    for where in ("global", "region"):
        for tier in FLOW_TIERS[1:]:
            members = [
                m
                for m in flow
                if m.component.tier == tier and (zone(m) == "global") == (where == "global")
            ]
            if members:
                columns.append(members)
                kinds.append(where)
    _reduce_crossings(arch, columns)
    rank = {"regional": 0, "public": 1, "private": 2}
    for col, kind in zip(columns, kinds, strict=True):
        if kind == "region":
            col.sort(key=lambda m: rank[zone(m)])  # stable: keeps the crossing order

    region_cols = [i for i, k in enumerate(kinds) if k == "region"]
    regional = max((sum(zone(m) == "regional" for m in columns[i]) for i in region_cols), default=0)
    networked = max(
        (sum(zone(m) != "regional" for m in columns[i]) for i in region_cols), default=0
    )
    subnets = "public" in look.groups
    sub = 14 if subnets else 0  # a subnet's margin around its services
    net = 16 + sub if networked else 0  # the network's margin around its subnets

    # ---- across ----
    col_left: list[float] = []

    def place(x: float) -> float:
        col_left.append(x)
        return x + look.node_w + look.col_gap + wider.get(len(col_left) - 1, 0)

    x = MARGIN
    if users:
        x = place(x)
    cloud_left = x
    x += PAD if look.cloud_frame else 0
    for kind in kinds:
        if kind == "global":
            x = place(x)
    region_left = x
    x += PAD + net
    for kind in kinds:
        if kind == "region":
            x = place(x)
    inner_right = x - look.col_gap - wider.get(len(col_left) - 1, 0) + net
    lane_gap = 40
    for lane in (delivery, shared):
        if lane:
            inner_right = max(
                inner_right, region_left + PAD + 6 + len(lane) * (look.node_w + lane_gap) - lane_gap
            )
    region_right = inner_right + PAD
    cloud_right = region_right + PAD if look.cloud_frame else region_right
    col_right = [left + look.node_w for left in col_left]
    lane_x, lane_w = region_left + PAD - 8, region_right - region_left - 2 * PAD + 16

    # ---- down ----
    nodes: dict[str, Node] = {}
    y = TITLE_H + MARGIN
    cloud_top = y
    if look.cloud_frame:
        y += GROUP_HEAD
    region_top = y
    y += GROUP_HEAD
    lane_h = BAND_HEAD + look.node_h + 12
    delivery_group = None
    if delivery:
        delivery_group = ("generic", lane_x, y, lane_w, lane_h, "Build and deploy")
        for k, m in enumerate(delivery):
            left = region_left + PAD + 6 + k * (look.node_w + lane_gap)
            nodes[m.component.id] = Node(m, left, y + BAND_HEAD, look.node_w, look.node_h, -1)
        y += lane_h + STACK_GAP
    main_top = y
    regional_h = _rows(regional, look)
    stack = regional_h
    vpc_top = net_top = 0.0
    if networked:
        vpc_top = main_top + regional_h + (STACK_GAP if regional else 0)
        net_top = vpc_top + GROUP_HEAD + (GROUP_HEAD - 8 if subnets else 0)
        stack = net_top + _rows(networked, look) + sub + 16 - main_top
    outside = [len(columns[i]) for i, k in enumerate(kinds) if k != "region"]
    main_h = max(stack, _rows(max(outside, default=0), look))

    for i in region_cols:
        top = [m for m in columns[i] if zone(m) == "regional"]
        low = [m for m in columns[i] if zone(m) != "regional"]
        y0 = main_top + (regional_h - _rows(len(top), look)) / 2
        for j, m in enumerate(top):
            top_y = y0 + j * (look.node_h + look.row_gap)
            nodes[m.component.id] = Node(m, col_left[i], top_y, look.node_w, look.node_h, i)
        y1 = net_top + (_rows(networked, look) - _rows(len(low), look)) / 2
        for j, m in enumerate(low):
            top_y = y1 + j * (look.node_h + look.row_gap)
            nodes[m.component.id] = Node(m, col_left[i], top_y, look.node_w, look.node_h, i)

    # Users and global services line up with what they talk to further right.
    neighbours: dict[str, list[str]] = {m.component.id: [] for m in arch.components}
    for edge in arch.spec.edges:
        neighbours[edge.source].append(edge.target)
        neighbours[edge.target].append(edge.source)
    for i in reversed(range(len(kinds))):
        if kinds[i] == "region":
            continue
        col = columns[i]
        placed = [
            nodes[n].cy
            for m in col
            for n in neighbours[m.component.id]
            if n in nodes and nodes[n].col > i
        ]
        h = _rows(len(col), look)
        centre = sum(placed) / len(placed) if placed else main_top + main_h / 2
        y0 = min(max(centre - h / 2, main_top), main_top + main_h - h)
        for j, m in enumerate(col):
            top_y = y0 + j * (look.node_h + look.row_gap)
            nodes[m.component.id] = Node(m, col_left[i], top_y, look.node_w, look.node_h, i)

    # The network, and its subnets, around the columns that hold them.
    network: list[tuple[str, float, float, float, float, str]] = []
    if networked:
        net_bottom = net_top + _rows(networked, look)
        spans = []
        for part in ("public", "private"):
            xs = [n.x for n in nodes.values() if n.col >= 0 and zone(n.m) == part]
            if not xs:
                continue
            spans.append((min(xs), max(xs) + look.node_w))
            if subnets:
                left = min(xs) - sub
                network.append(
                    (
                        part,
                        left,
                        vpc_top + GROUP_HEAD,
                        max(xs) + look.node_w + sub - left,
                        net_bottom + sub - vpc_top - GROUP_HEAD,
                        look.groups[part]["text"],
                    )
                )
        left = min(s[0] for s in spans) - net
        right = max(s[1] for s in spans) + net
        network.insert(
            0,
            (
                "vpc",
                left,
                vpc_top,
                right - left,
                net_bottom + sub + 16 - vpc_top,
                look.groups["vpc"]["text"],
            ),
        )

    y = main_top + main_h
    shared_group = None
    if shared:
        y += STACK_GAP
        shared_group = ("generic", lane_x, y, lane_w, lane_h, "Shared services")
        for k, m in enumerate(shared):
            left = region_left + PAD + 6 + k * (look.node_w + lane_gap)
            nodes[m.component.id] = Node(m, left, y + BAND_HEAD, look.node_w, look.node_h, -1)
        y += lane_h
    y += PAD
    groups = []
    if look.cloud_frame:
        cloud_text = look.groups["cloud"].get("text", arch.cloud_label)
        groups.append(
            (
                "cloud",
                cloud_left,
                cloud_top,
                cloud_right - cloud_left,
                y + PAD - cloud_top,
                cloud_text,
            )
        )
    groups.append(
        (
            "region",
            region_left,
            region_top,
            region_right - region_left,
            y - region_top,
            look.region + arch.region_text,
        )
    )
    groups += [g for g in (delivery_group,) if g] + network + [g for g in (shared_group,) if g]
    bottom = y + (PAD if look.cloud_frame else 0)
    return Plan(nodes, groups, col_left, col_right, cloud_right + MARGIN, bottom)


# ---------- lines ----------
def _anchor(n: Node, side: str, offset: float, look: Look) -> tuple[float, float]:
    if look.node == "icon":
        ix, iy = n.cx - ICON / 2, n.y + 6
        if side == "right":
            return ix + ICON + 4, iy + ICON / 2 + offset
        if side == "left":
            return ix - 4, iy + ICON / 2 + offset
        if side == "top":
            return n.cx + offset, iy - 4
        return n.cx + offset, n.y + n.h
    if side == "right":
        return n.x + n.w, n.cy + offset
    if side == "left":
        return n.x, n.cy + offset
    if side == "top":
        return n.cx + offset, n.y
    return n.cx + offset, n.y + n.h


def _hits(points: list[tuple[float, float]], boxes: list[Node]) -> int:
    """How many node boxes a polyline passes through."""
    count = 0
    for (x1, y1), (x2, y2) in zip(points, points[1:], strict=False):
        lo_x, hi_x, lo_y, hi_y = min(x1, x2), max(x1, x2), min(y1, y2), max(y1, y2)
        for b in boxes:
            if lo_x < b.x + b.w - 2 and hi_x > b.x + 2 and lo_y < b.y + b.h - 2 and hi_y > b.y + 2:
                count += 1
    return count


def _routes(arch: ProviderArchitecture, plan: Plan, look: Look) -> tuple[dict, dict[int, int]]:
    """Right-angled routes for every drawn link. The ends that share a side of a service
    are spread apart, vertical runs in the gap between two columns each get a lane, and a
    link that would cross a service on its way detours above or below it."""
    lane = {m.component.id: m.component.tier for m in arch.components}
    drawn = []
    for edge in arch.spec.edges:
        a, b = lane[edge.source], lane[edge.target]
        if ((a in LANE_TIERS or b in LANE_TIERS) and a != b) or a == b == "platform":
            continue
        drawn.append(edge)
    nodes = plan.nodes
    boxes = list(nodes.values())

    ways: dict[tuple[str, str], str] = {}
    for e in drawn:
        a, b = nodes[e.source], nodes[e.target]
        if a.col == b.col or a.col < 0:
            if a.col < 0 and abs(a.cy - b.cy) < 1:
                ways[(e.source, e.target)] = "right" if b.cx > a.cx else "left"
                continue
            between = [
                n
                for n in boxes
                if n.col == a.col and n.x == a.x and min(a.y, b.y) < n.y < max(a.y, b.y)
            ]
            ways[(e.source, e.target)] = "around" if between else ("down" if b.y > a.y else "up")
        else:
            ways[(e.source, e.target)] = "right" if b.cx > a.cx else "left"

    sides = {
        "right": ("right", "left"),
        "left": ("left", "right"),
        "down": ("bottom", "top"),
        "up": ("top", "bottom"),
        "around": ("right", "right"),
    }
    ends: dict[tuple[str, str], list] = {}
    for e in drawn:
        key = (e.source, e.target)
        out_side, in_side = sides[ways[key]]
        a, b = nodes[e.source], nodes[e.target]
        across = out_side in ("right", "left")
        ends.setdefault((e.source, out_side), []).append((b.cy if across else b.cx, key, 0))
        ends.setdefault((e.target, in_side), []).append((a.cy if across else a.cx, key, 1))
    offset: dict[tuple[tuple[str, str], int], float] = {}
    for items in ends.values():
        items.sort(key=lambda t: (t[0], t[1]))
        for k, (_, key, end) in enumerate(items):
            offset[(key, end)] = (k - (len(items) - 1) / 2) * 10

    def gap_x(g: int) -> float:
        return (plan.col_right[g] + plan.col_left[g + 1]) / 2

    def concrete(shape, xs=None):
        return [
            (xs[(k, p[1])] if xs else gap_x(p[1]), p[2]) if p[0] == "G" else p
            for k, p in enumerate(shape)
        ]

    def length(points) -> float:
        return sum(
            abs(p[0] - q[0]) + abs(p[1] - q[1]) for p, q in zip(points, points[1:], strict=False)
        )

    shapes: dict[tuple[str, str], list] = {}
    for e in drawn:
        key = (e.source, e.target)
        a, b = nodes[e.source], nodes[e.target]
        way = ways[key]
        out_side, in_side = sides[way]
        p1 = _anchor(a, out_side, offset[(key, 0)], look)
        p2 = _anchor(b, in_side, offset[(key, 1)], look)
        if way in ("down", "up") or (a.col < 0 and way in ("right", "left")):
            p1 = _anchor(a, out_side, 0, look)
            p2 = (
                (p1[0], _anchor(b, in_side, 0, look)[1])
                if way in ("down", "up")
                else (_anchor(b, in_side, 0, look))
            )
            shapes[key] = [p1, p2]
            continue
        if way == "around":
            bx = plan.col_right[a.col] + look.col_gap * 0.3
            shapes[key] = [p1, (bx, p1[1]), (bx, p2[1]), p2]
            continue
        right = way == "right"
        gs = a.col if right else a.col - 1
        gt = b.col - 1 if right else b.col
        others = [n for n in boxes if n is not a and n is not b]
        options = []
        if abs(p1[1] - p2[1]) < 0.5:
            options.append([p1, p2])
        for g in sorted({gs, gt}):
            options.append([p1, ("G", g, p1[1]), ("G", g, p2[1]), p2])
        if gs != gt:
            lo, hi = sorted((a.col, b.col))
            channels = sorted(
                {
                    y
                    for n in others
                    if lo < n.col < hi
                    for y in (n.y - look.row_gap / 2, n.y + n.h + look.row_gap / 2)
                }
            )
            for yc in channels:
                options.append(
                    [p1, ("G", gs, p1[1]), ("G", gs, yc), ("G", gt, yc), ("G", gt, p2[1]), p2]
                )
        scored = [
            (_hits(concrete(o), others), length(concrete(o)), k) for k, o in enumerate(options)
        ]
        shapes[key] = options[min(scored)[2]]

    # Give every vertical run in a gap its own lane, left to right in order of height.
    runs: dict[int, list] = {}
    for key, shape in shapes.items():
        for k in range(len(shape) - 1):
            p, q = shape[k], shape[k + 1]
            if p[0] == "G" and q[0] == "G" and p[1] == q[1]:
                runs.setdefault(p[1], []).append((min(p[2], q[2]), max(p[2], q[2]), key, k))
    lanes: dict[tuple[tuple[str, str], int], float] = {}
    for g, items in runs.items():
        items.sort(key=lambda t: (t[0], t[1], t[2]))
        left, right = plan.col_right[g] + 12, plan.col_left[g + 1] - 12
        for i, (_, _, key, k) in enumerate(items):
            lanes[(key, k)] = left + (right - left) * (i + 1) / (len(items) + 1)

    routes: dict[tuple[str, str], list] = {}
    for key, shape in shapes.items():
        points = []
        for k, p in enumerate(shape):
            if p[0] == "G":
                run = (
                    k
                    if (k + 1 < len(shape) and shape[k + 1][0] == "G" and shape[k + 1][1] == p[1])
                    else k - 1
                )
                points.append((lanes[(key, run)], p[2]))
            else:
                points.append(p)
        routes[key] = points
    return routes, {g: len(items) for g, items in runs.items()}


def _arrow(points: list[tuple[float, float]]) -> str:
    (x0, y0), (x, y) = points[-2], points[-1]
    dx, dy = x - x0, y - y0
    if abs(dx) >= abs(dy):
        s = 1 if dx > 0 else -1
        pts = [(x, y), (x - s * 9, y - 4.5), (x - s * 9, y + 4.5)]
    else:
        s = 1 if dy > 0 else -1
        pts = [(x, y), (x - 4.5, y - s * 9), (x + 4.5, y - s * 9)]
    return " ".join(f"{_n(px)},{_n(py)}" for px, py in pts)


def _edges_svg(arch: ProviderArchitecture, routes: dict, marks: list, plan: Plan) -> list[str]:
    """The links, each with an arrowhead. As in the providers' reference diagrams, a link
    numbered as a step of the main request is explained under the drawing rather than
    labelled; the other links keep their label, placed where it is clear of other labels,
    step markers and services."""
    labels = {(e.source, e.target): e.label for e in arch.spec.edges}
    numbered = {key for *_, key in marks if key}
    taken = [(mx - STEP_R, my - STEP_R, mx + STEP_R, my + STEP_R) for _, mx, my, _ in marks]
    taken += [(n.x + 2, n.y + 2, n.x + n.w - 2, n.y + n.h - 2) for n in plan.nodes.values()]

    def free(box: tuple[float, float, float, float]) -> bool:
        x1, y1, x2, y2 = box
        return all(x2 <= a or x1 >= c or y2 <= b or y1 >= d for a, b, c, d in taken)

    out = []
    for (src, dst), pts in routes.items():
        ends = f"data-from={quoteattr(src)} data-to={quoteattr(dst)}"
        # The arrowhead ends where the line ends; the line stops short of the tip.
        (x0, y0), (x, y) = pts[-2], pts[-1]
        length = max(abs(x - x0), abs(y - y0)) or 1
        cut = [*pts[:-1], (x - (x - x0) / length * 6, y - (y - y0) / length * 6)]
        d = "M" + " L".join(f"{_n(px)},{_n(py)}" for px, py in cut)
        out.append(f'<path class="ca-edge" {ends} d="{d}"/>')
        out.append(f'<polygon class="ca-arrow" {ends} points="{_arrow(pts)}"/>')
        label = labels.get((src, dst))
        if not label or (src, dst) in numbered:
            continue
        half = len(label) * 3.1 + 3
        spots = []
        segs = sorted(
            ((abs(p[0] - q[0]), p, q) for p, q in zip(pts, pts[1:], strict=False) if p[1] == q[1]),
            key=lambda t: -t[0],
        )
        for seg_len, p, q in segs:
            left = min(p[0], q[0])
            for share in (0.5, 0.3, 0.7):
                if share != 0.5 and seg_len < 4 * half:
                    continue
                cx = left + seg_len * share
                spots += [(cx, p[1] - 7, "middle"), (cx, p[1] + 15, "middle")]
        for p, q in zip(pts, pts[1:], strict=False):
            if p[0] == q[0]:
                my = (p[1] + q[1]) / 2 + 4
                spots += [(p[0] + 7, my, "start"), (p[0] - 7, my, "end")]
        chosen = None
        for lx, ly, anchor in spots:
            x1 = lx - half if anchor == "middle" else lx if anchor == "start" else lx - 2 * half
            box = (x1, ly - 10, x1 + 2 * half, ly + 3)
            if free(box):
                chosen = (lx, ly, anchor, box)
                break
        if chosen is None and spots:
            lx, ly, anchor = spots[0]
            chosen = (lx, ly, anchor, (lx - half, ly - 10, lx + half, ly + 3))
        if chosen is None:
            continue
        lx, ly, anchor, box = chosen
        taken.append(box)
        out.append(
            f'<text class="ca-edge-label" {ends} x="{_n(lx)}" y="{_n(ly)}" '
            f'text-anchor="{anchor}">{escape(label)}</text>'
        )
    return out


# ---------- services ----------
def _person(x: float, y: float, size: float, colour: str) -> str:
    cx, r = x + size / 2, size * 0.2
    return (
        f'<g fill="{colour}"><circle cx="{_n(cx)}" cy="{_n(y + r + 2)}" r="{_n(r)}"/>'
        f'<path d="M{_n(cx - size * 0.38)},{_n(y + size)} Q{_n(cx - size * 0.38)},'
        f"{_n(y + size * 0.55)} {_n(cx)},{_n(y + size * 0.55)} Q{_n(cx + size * 0.38)},"
        f'{_n(y + size * 0.55)} {_n(cx + size * 0.38)},{_n(y + size)} Z"/></g>'
    )


def _image(x: float, y: float, size: float, uri: str) -> str:
    return f'<image x="{_n(x)}" y="{_n(y)}" width="{_n(size)}" height="{_n(size)}" href="{uri}"/>'


def _picture(m: MappedComponent, x: float, y: float, size: float, icons, look, colours) -> str:
    comp, choice = m.component, m.choice
    if choice is None:
        uri = icons.data_uri(look.users) if look.users else None
        return _image(x, y, size, uri) if uri else _person(x, y, size, look.muted)
    uri = icons.data_uri(choice.icon)
    if uri:
        return _image(x, y, size, uri)
    colour = colours.get(comp.category, FALLBACK_COLOUR)
    return (
        f'<rect x="{_n(x)}" y="{_n(y)}" width="{_n(size)}" height="{_n(size)}" rx="4" '
        f'fill="{colour}"/><text class="ca-badge" x="{_n(x + size / 2)}" '
        f'y="{_n(y + size / 2 + 4.5)}" text-anchor="middle">{escape(choice.short)}</text>'
    )


def _node_svg(n: Node, icons: IconLibrary, look: Look, colours: dict) -> list[str]:
    comp, choice = n.m.component, n.m.choice
    title = choice.service if choice else comp.display_label
    subtitle = comp.display_label if choice else None
    out = [
        f'<g class="node" data-id={quoteattr(comp.id)} '
        f"data-capability={quoteattr(comp.capability)} "
        f"data-stage={quoteattr(comp.stage or '')}>",
        f'<rect class="ca-node-box" x="{_n(n.x)}" y="{_n(n.y)}" width="{_n(n.w)}" '
        f'height="{_n(n.h)}" rx="{6 if look.node == "card" else 4}"/>',
    ]
    if look.node == "icon":
        out.append(_picture(n.m, n.cx - ICON / 2, n.y + 6, ICON, icons, look, colours))
        ty = n.y + 6 + ICON + 16
        lines = _wrap(title, 22, 2)
        for k, line in enumerate(lines):
            out.append(
                f'<text class="ca-service" x="{_n(n.cx)}" y="{_n(ty + k * 14)}" '
                f'text-anchor="middle">{escape(line)}</text>'
            )
        if subtitle:
            out.append(
                f'<text class="ca-label" x="{_n(n.cx)}" y="{_n(ty + len(lines) * 14 + 1)}" '
                f'text-anchor="middle">{escape(_wrap(subtitle, 26, 1)[0])}</text>'
            )
    else:
        out.append(_picture(n.m, n.x + 12, n.cy - 16, 32, icons, look, colours))
        lines = _wrap(title, 24, 2)
        top = n.cy - (len(lines) - 1) * 7 - (6 if subtitle else -4)
        for k, line in enumerate(lines):
            out.append(
                f'<text class="ca-service" x="{_n(n.x + 54)}" y="{_n(top + k * 14)}">'
                f"{escape(line)}</text>"
            )
        if subtitle:
            out.append(
                f'<text class="ca-label" x="{_n(n.x + 54)}" '
                f'y="{_n(top + len(lines) * 14 + 1)}">{escape(_wrap(subtitle, 28, 1)[0])}</text>'
            )
    if choice is not None and choice.fidelity != "exact":
        # On a card, in its corner under the name; beside an icon, top right.
        fy = n.y + n.h - 6 if look.node == "card" else n.y + 12
        out.append(
            f'<text class="ca-fidelity" x="{_n(n.x + n.w - 6)}" y="{_n(fy)}" '
            f'text-anchor="end">{escape(choice.fidelity)}</text>'
        )
    out.append("</g>")
    return out


def _group_svg(kind: str, x, y, w, h, label: str, look: Look, icons: IconLibrary) -> list[str]:
    spec = look.groups[kind]
    out = [
        f'<rect class="ca-group ca-group-{kind}" x="{_n(x)}" y="{_n(y)}" width="{_n(w)}" '
        f'height="{_n(h)}" rx="{_n(look.radius)}"/>'
    ]
    tx = x + 12
    if spec.get("icon") and look.group_icon:
        size = look.group_icon
        ix, iy = (x, y) if look.key == "aws" else (x + 10, y + 10)
        uri = icons.data_uri(spec["icon"])
        if uri:
            out.append(
                f'<image x="{_n(ix)}" y="{_n(iy)}" width="{_n(size)}" height="{_n(size)}" '
                f'href="{uri}"/>'
            )
        else:  # without the icon files (golden files), the group's colour stands in
            colour = spec.get("stroke") or spec.get("label")
            out.append(
                f'<rect x="{_n(ix)}" y="{_n(iy)}" width="{_n(size)}" height="{_n(size)}" '
                f'fill="{colour}"/>'
            )
        tx = ix + size + 8
    ty = y + (21 if look.key == "aws" else 25)
    out.append(
        f'<text class="ca-group-label ca-group-{kind}-label" x="{_n(tx)}" y="{_n(ty)}">'
        f"{escape(label)}</text>"
    )
    return out


# ---------- the main request, numbered ----------
def _steps(arch: ProviderArchitecture, routes: dict, plan: Plan) -> tuple[str, list, list[str]]:
    """The main request's steps, each marked on its own line just before the arrowhead,
    where links that leave one service together have already parted."""
    flows = list(arch.spec.workflows) or generate_workflows(arch.spec)
    if not flows:
        return "", [], []
    flow = next((w for w in flows if w.kind == "request"), flows[0])
    marks: list[tuple[int, float, float, tuple[str, str] | None]] = []

    def clear(x: float, y: float) -> bool:
        gap = 2 * STEP_R + 3
        return all(abs(x - mx) >= gap or abs(y - my) >= gap for _, mx, my, _ in marks)

    texts = []
    for i, step in enumerate(flow.steps, 1):
        texts.append(step.text)
        comps = [c for c in step.components if c in plan.nodes]
        pts = routes.get((comps[0], comps[1])) if len(comps) >= 2 else None
        key = (comps[0], comps[1]) if pts else None
        if pts:
            (x0, y0), (x1, y1) = pts[-2], pts[-1]
            length = max(abs(x1 - x0), abs(y1 - y0)) or 1
            ux, uy = (x1 - x0) / length, (y1 - y0) / length
            back = min(9 + 5 + STEP_R, length / 2)
            x, y = x1 - ux * back, y1 - uy * back
            while not clear(x, y) and back + 2 * STEP_R + 4 < length:
                back += 2 * STEP_R + 4
                x, y = x1 - ux * back, y1 - uy * back
        elif comps:
            n = plan.nodes[comps[-1]]
            x, y = n.x + 10, n.y + 6
        else:
            continue
        while not clear(x, y):
            y += 2 * STEP_R + 4
        marks.append((i, x, y, key))
    return flow.name, marks, texts


def _marker(i: int, x: float, y: float) -> str:
    return (
        f'<g class="ca-step" data-step="{i}"><circle cx="{_n(x)}" cy="{_n(y)}" r="{STEP_R}"/>'
        f'<text x="{_n(x)}" y="{_n(y + 3.8)}" text-anchor="middle">{i}</text></g>'
    )


def _legend(name: str, texts: list[str], top: float, width: float) -> tuple[list[str], float]:
    if not texts:
        return [], top
    out = [f'<text class="ca-steps-title" x="{MARGIN}" y="{_n(top + 14)}">{escape(name)}</text>']
    columns = 2 if width >= 900 else 1
    col_w = (width - 2 * MARGIN - (columns - 1) * 28) / columns
    chars = max(int((col_w - 28) / 6.2), 30)
    per_col = -(-len(texts) // columns)
    bottom = top + 24
    for c in range(columns):
        y = top + 34
        for i in range(c * per_col, min((c + 1) * per_col, len(texts))):
            x = MARGIN + c * (col_w + 28)
            lines = _wrap(texts[i], chars, 3)
            out.append(_marker(i + 1, x + STEP_R, y - 4))
            for k, line in enumerate(lines):
                out.append(
                    f'<text class="ca-steps-text" x="{_n(x + 2 * STEP_R + 8)}" '
                    f'y="{_n(y + k * 15)}">{escape(line)}</text>'
                )
            y += len(lines) * 15 + 9
        bottom = max(bottom, y)
    return out, bottom


# ---------- the document ----------
def _style(look: Look, scope: str, colours: dict) -> str:
    rules = {
        "": f"font-family:{look.font}",
        ".ca-bg": "fill:#ffffff",
        ".ca-title": f"font-size:18px;font-weight:700;fill:{look.ink}",
        ".ca-subtitle": f"font-size:13px;fill:{look.muted}",
        ".ca-group-label": f"font-size:12px;font-weight:600;fill:{look.ink}",
        ".ca-badge": "font-size:13px;font-weight:700;fill:#ffffff",
        ".ca-service": f"font-size:12px;font-weight:600;fill:{look.ink}",
        ".ca-label": f"font-size:11px;fill:{look.muted}",
        ".ca-fidelity": "font-size:10px;font-style:italic;fill:#b0084d",
        ".ca-edge": f"fill:none;stroke:{look.line};stroke-width:1.5;stroke-linejoin:round",
        ".ca-arrow": f"fill:{look.line}",
        ".ca-edge-label": f"font-size:11px;fill:{look.ink};paint-order:stroke;stroke:#ffffff;"
        "stroke-width:4;stroke-linejoin:round",
        ".ca-step circle": f"fill:{look.step};stroke:#ffffff;stroke-width:1.5",
        ".ca-step text": "font-size:11px;font-weight:700;fill:#ffffff",
        ".ca-steps-title": f"font-size:13px;font-weight:700;fill:{look.ink}",
        ".ca-steps-text": f"font-size:12px;fill:{look.ink}",
        ".ca-footer": "font-size:10px;fill:#879196",
    }
    if look.node == "card":
        rules[".ca-node-box"] = "fill:#ffffff;stroke:#DADCE0;stroke-width:1"
        rules[".ca-service"] = f"font-size:12.5px;font-weight:500;fill:{look.ink}"
    else:
        # The service is its icon; the box is only there to select it.
        rules[".ca-node-box"] = "fill:transparent;stroke:transparent;stroke-width:1.5"
    for kind, spec in look.groups.items():
        dash = f";stroke-dasharray:{spec['dash']}" if spec.get("dash") else ""
        stroke = spec.get("stroke", "none")
        rules[f".ca-group-{kind}"] = f"fill:{spec.get('fill', 'none')};stroke:{stroke}{dash}"
        weight = "700;font-size:13px" if spec.get("bold") else "600"
        rules[f".ca-group-{kind}-label"] = f"fill:{spec['label']};font-weight:{weight}"
    return "\n".join(
        f".{scope}{(' ' + sel) if sel else ''}{{{body}}}" for sel, body in rules.items()
    )


def render_documented(arch: ProviderArchitecture, icons: IconLibrary, look: Look) -> str:
    plan = _plan(arch, look)
    routes, crowd = _routes(arch, plan, look)
    # A gap that many links run through is widened, so their vertical runs stay apart.
    wider: dict[int, float] = {}
    for _ in range(2):
        need = {
            g: 28 + 14 * n - (plan.col_left[g + 1] - plan.col_right[g]) for g, n in crowd.items()
        }
        grow = {g: v for g, v in need.items() if v > 0}
        if not grow:
            break
        for g, v in grow.items():
            wider[g] = wider.get(g, 0) + v
        plan = _plan(arch, look, wider)
        routes, crowd = _routes(arch, plan, look)
    colours = theme_for(arch.provider)["categories"]
    spec = arch.spec
    name, marks, texts = _steps(arch, routes, plan)
    width = max(plan.width, 640)
    legend, legend_bottom = _legend(name, texts, plan.bottom + 22, width)
    height = legend_bottom + 14 + FOOTER_H
    scope = f"ca-{arch.provider}"
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" class="ca-diagram {scope}" '
        f'width="{_n(width)}" height="{_n(height)}" viewBox="0 0 {_n(width)} {_n(height)}" '
        f'role="img" data-body-top="{TITLE_H}" data-body-bottom="{_n(height - FOOTER_H)}" '
        f'data-drawing-bottom="{_n(plan.bottom + 8)}" '
        f"aria-label={quoteattr(f'{spec.name} on {arch.provider_name}')}>",
        f"<style>{_style(look, scope, colours)}</style>",
        f'<rect class="ca-bg" width="{_n(width)}" height="{_n(height)}"/>',
        f'<text class="ca-title" x="{MARGIN}" y="{MARGIN + 12}">'
        f"{escape(spec.name)} on {escape(arch.provider_name)}</text>",
    ]
    if spec.summary:
        out.append(
            f'<text class="ca-subtitle" x="{MARGIN}" y="{MARGIN + 32}">'
            f"{escape(_wrap(spec.summary, 140, 1)[0])}</text>"
        )
    for kind, x, y, w, h, label in plan.groups:
        out += _group_svg(kind, x, y, w, h, label, look, icons)
    out += _edges_svg(arch, routes, marks, plan)
    for m in arch.components:
        out += _node_svg(plan.nodes[m.component.id], icons, look, colours)
    out += [_marker(i, x, y) for i, x, y, _ in marks]
    out += legend
    out.append(
        f'<text class="ca-footer" x="{MARGIN}" y="{_n(height - 12)}">Generated by Clarchy. '
        f"Service names{' and icons' if icons.root is not None else ''} belong to their owners; "
        f"Clarchy is not affiliated with {escape(arch.provider_name)}.</text>"
    )
    out.append("</svg>")
    return "\n".join(out) + "\n"
