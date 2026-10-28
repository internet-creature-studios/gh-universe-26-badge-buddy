"""Trace the pink ':3' from logo.png into menu icon contours.

Writes contours.json: {"three": [[x, y], ...], "dots": [[cx, cy, r], ...]}
in menu icon units (centred on 0, y down).
"""

import json
import math
import sys

from PIL import Image, ImageFilter

logo_path, out_path = sys.argv[1], sys.argv[2]
UP = 8
EXTENT = 0.78  # the larger side of ':3' in icon units

logo = Image.open(logo_path).convert("RGBA")
box = (188, 105, 234, 150)
crop = logo.crop(box)
# Keep only pink pixels (the black wordmark does not reach this box, but be safe).
mask = Image.new("L", crop.size, 0)
src = crop.load()
dst = mask.load()
for y in range(crop.size[1]):
    for x in range(crop.size[0]):
        r, g, b, a = src[x, y]
        dst[x, y] = a if r > 180 and g < 200 else 0
pad = 4
padded = Image.new("L", (mask.size[0] + 2 * pad, mask.size[1] + 2 * pad), 0)
padded.paste(mask, (pad, pad))
big = padded.resize((padded.size[0] * UP, padded.size[1] * UP), Image.BICUBIC)
big = big.filter(ImageFilter.GaussianBlur(UP * 0.45))
W, H = big.size
F = [[v / 255.0 for v in big.crop((0, y, W, y + 1)).getdata()] for y in range(H)]
T = 0.5


def lerp(a, b):
    return (T - a) / (b - a) if a != b else 0.5


adj = {}
pts = {}


def link(e1, e2):
    adj.setdefault(e1, []).append(e2)
    adj.setdefault(e2, []).append(e1)


for i in range(H - 1):
    row, nxt = F[i], F[i + 1]
    for j in range(W - 1):
        tl, tr, br, bl = row[j], row[j + 1], nxt[j + 1], nxt[j]
        s = (tl > T, tr > T, br > T, bl > T)
        if s[0] == s[1] == s[2] == s[3]:
            continue
        edges = {}
        if s[0] != s[1]:
            k = ("h", i, j)
            pts[k] = (j + lerp(tl, tr), i)
            edges["top"] = k
        if s[1] != s[2]:
            k = ("v", i, j + 1)
            pts[k] = (j + 1, i + lerp(tr, br))
            edges["right"] = k
        if s[3] != s[2]:
            k = ("h", i + 1, j)
            pts[k] = (j + lerp(bl, br), i + 1)
            edges["bottom"] = k
        if s[0] != s[3]:
            k = ("v", i, j)
            pts[k] = (j, i + lerp(tl, bl))
            edges["left"] = k
        if len(edges) == 2:
            a, b = edges.values()
            link(a, b)
        else:
            centre = (tl + tr + br + bl) / 4 > T
            if centre == s[0]:
                link(edges["top"], edges["right"])
                link(edges["bottom"], edges["left"])
            else:
                link(edges["left"], edges["top"])
                link(edges["right"], edges["bottom"])

loops = []
seen = set()
for start in adj:
    if start in seen:
        continue
    loop = [start]
    seen.add(start)
    prev, cur = None, start
    while True:
        nbrs = [n for n in adj[cur] if n != prev]
        nxt_key = nbrs[0]
        if nxt_key == start:
            break
        if nxt_key in seen:
            break
        seen.add(nxt_key)
        loop.append(nxt_key)
        prev, cur = cur, nxt_key
    loops.append([pts[k] for k in loop])


def area(poly):
    return sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1])) / 2


loops.sort(key=lambda p: -abs(area(p)))
print("loops", [(len(p), round(abs(area(p)))) for p in loops], file=sys.stderr)
three, dot_loops = loops[0], loops[1:3]


def rdp(points, eps):
    if len(points) < 3:
        return points
    (x0, y0), (x1, y1) = points[0], points[-1]
    dx, dy = x1 - x0, y1 - y0
    norm = math.hypot(dx, dy) or 1e-9
    best, index = -1, 0
    for k in range(1, len(points) - 1):
        px, py = points[k]
        d = abs(dy * (px - x0) - dx * (py - y0)) / norm
        if d > best:
            best, index = d, k
    if best <= eps:
        return [points[0], points[-1]]
    return rdp(points[: index + 1], eps)[:-1] + rdp(points[index:], eps)


def simplify_closed(poly, eps):
    # split at the two most distant points so both halves are open curves
    far = max(range(len(poly)), key=lambda k: (poly[k][0] - poly[0][0]) ** 2 + (poly[k][1] - poly[0][1]) ** 2)
    a = rdp(poly[: far + 1], eps)
    b = rdp(poly[far:] + [poly[0]], eps)
    return a[:-1] + b[:-1]


three = simplify_closed(three, eps=UP * 0.12)
if area(three) < 0:
    three.reverse()

dots = []
for loop in dot_loops:
    cx = sum(p[0] for p in loop) / len(loop)
    cy = sum(p[1] for p in loop) / len(loop)
    r = math.sqrt(abs(area(loop)) / math.pi)
    dots.append((cx, cy, r))
dots.sort(key=lambda d: d[1])

xs = [p[0] for p in three] + [d[0] - d[2] for d in dots] + [d[0] + d[2] for d in dots]
ys = [p[1] for p in three] + [d[1] - d[2] for d in dots] + [d[1] + d[2] for d in dots]
cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
scale = EXTENT / max(max(xs) - min(xs), max(ys) - min(ys))


def norm(x, y):
    return [(x - cx) * scale, (y - cy) * scale]


out = {
    "three": [norm(x, y) for x, y in three],
    "dots": [norm(x, y) + [r * scale] for x, y, r in dots],
}
print("three points", len(out["three"]), "dots", out["dots"], file=sys.stderr)
with open(out_path, "w") as f:
    json.dump(out, f)
