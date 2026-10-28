"""Repo Defender's menu icon: a shield guarding a little commit graph.

    python3 examples/repo-defender/make_icon.py icon.json preview.png
    python3 tools/menu_icon.py repo_defender icon.json

Writes the icon's contours (see tools/menu_icon.py) and a preview of it on
menu tiles at real size.
"""

import json
import math
import sys

from PIL import Image, ImageDraw


def shield(scale, cy=0.0):
    """The shield's outline, clockwise on screen (y down)."""
    top, side, waist, tip = -0.40, 0.35, 0.02, 0.44
    points = [(-side, top), (side, top), (side, waist)]
    # The right flank curves in to the tip, then the left mirrors it.
    for k in range(1, 9):
        t = k / 8
        x = (1 - t) ** 2 * side + 2 * (1 - t) * t * side * 0.9 + t * t * 0.0
        y = (1 - t) ** 2 * waist + 2 * (1 - t) * t * 0.32 + t * t * tip
        points.append((x, y))
    for x, y in reversed(points[3:-1]):
        points.append((-x, y))
    points.append((-side, waist))
    return [(x * scale, cy + (y - cy) * scale) for x, y in points]


def circle(cx, cy, r, n=14):
    return [(cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n)) for k in range(n)]


def bar(x0, y0, x1, y1, width):
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy)
    nx, ny = -dy / length * width / 2, dx / length * width / 2
    return [(x0 + nx, y0 + ny), (x1 + nx, y1 + ny), (x1 - nx, y1 - ny), (x0 - nx, y0 - ny)]


def area(contour):
    return sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(contour, contour[1:] + contour[:1])) / 2


def wound(contour, sign):
    """contour turned to wind one way (sign 1) or the other (-1)."""
    return contour if area(contour) * sign > 0 else list(reversed(contour))


def contours():
    # Under the non-zero rule the hole winds against the shield, and the
    # graph inside winds all one way, so where its parts overlap they add up
    # rather than cancel.
    return [wound(shield(1.0), 1), wound(shield(0.74), -1)] + [
        wound(c, 1)
        for c in (
            bar(-0.06, -0.20, -0.06, 0.18, 0.06),  # main
            bar(-0.06, 0.06, 0.10, -0.08, 0.06),  # a branch off it
            circle(-0.06, -0.20, 0.07),
            circle(-0.06, 0.18, 0.07),
            circle(0.10, -0.08, 0.07),
        )
    ]


def preview(shapes, path):
    tile, icon, ss = 75, 48, 6
    out = Image.new("RGB", (tile * 3 + 8, tile), "black")
    for n, rgb in enumerate([(88, 58, 247), (22, 143, 251), (15, 191, 62)]):
        # Non-zero fill: draw the shape, then knock the hole back out, then
        # draw what sits inside the hole.
        im = Image.new("RGB", (tile * ss, tile * ss), rgb)
        d = ImageDraw.Draw(im)
        at = lambda c: [((tile / 2 + x * icon) * ss, (tile / 2 + y * icon) * ss) for x, y in c]
        d.polygon(at(shapes[0]), fill="white")
        d.polygon(at(shapes[1]), fill=rgb)
        for c in shapes[2:]:
            d.polygon(at(c), fill="white")
        out.paste(im.resize((tile, tile), Image.LANCZOS), (n * (tile + 4), 0))
    out.resize((out.width * 3, out.height * 3), Image.NEAREST).save(path)


if __name__ == "__main__":
    shapes = contours()
    with open(sys.argv[1], "w") as f:
        json.dump([[list(p) for p in c] for c in shapes], f)
    preview(shapes, sys.argv[2])
