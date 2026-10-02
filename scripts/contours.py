"""Draws the contour lines behind page headings: static/brand/contours.svg.

A topographic map of a few soft hills, traced at even heights with marching squares and
simplified, in the spirit of Haikei's generated SVG backgrounds. Lines fade out towards
the left, where the page's words sit. Pure Python, no dependencies; the output is
committed, so run this only to change the drawing:

    python scripts/contours.py src/clarchy/static/brand/contours.svg
"""

from __future__ import annotations

import math
import sys

WIDTH, HEIGHT = 960, 360
STEP = 8  # grid spacing in px
HILLS = [  # x, y, height, spread
    (820, 120, 1.0, 150),
    (610, 300, 0.75, 120),
    (980, 330, 0.6, 110),
    (470, 40, 0.45, 95),
]
LEVELS = [0.08 + 0.075 * i for i in range(13)]


def field(x: float, y: float) -> float:
    h = sum(a * math.exp(-((x - cx) ** 2 + (y - cy) ** 2) / (2 * s * s)) for cx, cy, a, s in HILLS)
    # Gentle ripples so the rings are not perfect ellipses.
    h += 0.035 * math.sin(x * 0.019 + 1.3) * math.cos(y * 0.023 - 0.4)
    h += 0.02 * math.sin((x + y) * 0.031 + 0.7)
    return h


def segments(level: float) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    cols, rows = WIDTH // STEP + 1, HEIGHT // STEP + 1
    v = [[field(c * STEP, r * STEP) for c in range(cols)] for r in range(rows)]
    out = []

    def edge(r: int, c: int, k: int) -> tuple[float, float]:
        # Edges: 0 top, 1 right, 2 bottom, 3 left, interpolated where the level crosses.
        (r0, c0), (r1, c1) = [
            ((r, c), (r, c + 1)),
            ((r, c + 1), (r + 1, c + 1)),
            ((r + 1, c), (r + 1, c + 1)),
            ((r, c), (r + 1, c)),
        ][k]
        a, b = v[r0][c0], v[r1][c1]
        t = 0.5 if a == b else (level - a) / (b - a)
        return (c0 + (c1 - c0) * t) * STEP, (r0 + (r1 - r0) * t) * STEP

    pairs = {
        1: [(3, 2)],
        2: [(2, 1)],
        3: [(3, 1)],
        4: [(0, 1)],
        5: [(3, 0), (2, 1)],
        6: [(0, 2)],
        7: [(3, 0)],
        8: [(3, 0)],
        9: [(0, 2)],
        10: [(0, 1), (3, 2)],
        11: [(0, 1)],
        12: [(3, 1)],
        13: [(2, 1)],
        14: [(3, 2)],
    }
    for r in range(rows - 1):
        for c in range(cols - 1):
            idx = (
                ((v[r][c] > level) << 3)
                | ((v[r][c + 1] > level) << 2)
                | ((v[r + 1][c + 1] > level) << 1)
                | (v[r + 1][c] > level)
            )
            for k0, k1 in pairs.get(idx, []):
                out.append((edge(r, c, k0), edge(r, c, k1)))
    return out


def chains(segs):
    """Joins segments that share an end into polylines."""
    key = lambda p: (round(p[0], 3), round(p[1], 3))  # noqa: E731
    ends: dict = {}
    for i, (a, b) in enumerate(segs):
        ends.setdefault(key(a), []).append(i)
        ends.setdefault(key(b), []).append(i)
    used = [False] * len(segs)
    lines = []
    for i in range(len(segs)):
        if used[i]:
            continue
        used[i] = True
        line = [segs[i][0], segs[i][1]]
        for forward in (True, False):
            while True:
                tip = line[-1] if forward else line[0]
                nxt = next((j for j in ends.get(key(tip), []) if not used[j]), None)
                if nxt is None:
                    break
                used[nxt] = True
                a, b = segs[nxt]
                point = b if key(a) == key(tip) else a
                if forward:
                    line.append(point)
                else:
                    line.insert(0, point)
        lines.append(line)
    return lines


def simplify(points, eps=1.2):
    """Ramer-Douglas-Peucker."""
    if len(points) < 3:
        return points
    (x1, y1), (x2, y2) = points[0], points[-1]
    dx, dy = x2 - x1, y2 - y1
    norm = math.hypot(dx, dy) or 1e-9
    far, index = 0.0, 0
    for i, (x, y) in enumerate(points[1:-1], 1):
        d = abs(dy * x - dx * y + x2 * y1 - y2 * x1) / norm
        if d > far:
            far, index = d, i
    if far <= eps:
        return [points[0], points[-1]]
    return simplify(points[: index + 1], eps)[:-1] + simplify(points[index:], eps)


def path(points) -> str:
    # Smooth through the points with quadratic curves between midpoints.
    if len(points) < 3:
        return "M" + " L".join(f"{x:.0f} {y:.0f}" for x, y in points)
    out = [f"M{points[0][0]:.0f} {points[0][1]:.0f}"]
    for (x0, y0), (x1, y1) in zip(points[1:-1], points[2:], strict=False):
        out.append(f"Q{x0:.0f} {y0:.0f} {(x0 + x1) / 2:.0f} {(y0 + y1) / 2:.0f}")
    out.append(f"L{points[-1][0]:.0f} {points[-1][1]:.0f}")
    return "".join(out)


def svg() -> str:
    paths = []
    for i, level in enumerate(LEVELS):
        for line in chains(segments(level)):
            line = simplify(line)
            if len(line) >= 2 and math.dist(line[0], line[-1]) + len(line) * STEP > 40:
                width = "1.4" if i % 4 == 3 else "0.8"  # every fourth line is an index contour
                paths.append(f'<path d="{path(line)}" stroke-width="{width}"/>')
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" '
        'preserveAspectRatio="xMaxYMin slice">'
        '<defs><linearGradient id="fade" x1="0" x2="1" y1="0" y2="0">'
        '<stop offset="0.25" stop-color="#000" stop-opacity="0"/>'
        '<stop offset="0.7" stop-color="#000" stop-opacity="1"/></linearGradient></defs>'
        '<g fill="none" stroke="url(#fade)" stroke-linecap="round" stroke-linejoin="round">'
        + "".join(paths)
        + "</g></svg>\n"
    )


if __name__ == "__main__":
    text = svg()
    if len(sys.argv) > 1:
        with open(sys.argv[1], "w", encoding="utf-8") as f:
            f.write(text)
        print(f"wrote {sys.argv[1]} ({len(text) // 1024} KB)")
    else:
        sys.stdout.write(text)
