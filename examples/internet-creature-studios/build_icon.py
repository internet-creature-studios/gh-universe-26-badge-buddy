"""Build the internet_creature menu icon entry, its BWIC animation, and previews.

usage: build_icon.py contours.json icons.py anim.bin preview_dir
"""

import json
import math
import struct
import sys

from PIL import Image, ImageDraw

contours_path, icons_path, anim_path, preview_dir = sys.argv[1:5]
data = json.load(open(contours_path))
THREE = [tuple(p) for p in data["three"]]
DOTS = [tuple(d) for d in data["dots"]]
DOT_POINTS = 20
FPS = 30


def ease(t):
    return 0.5 - 0.5 * math.cos(math.pi * max(0.0, min(1.0, t)))


def frame_contours(sx=1.0, sy=1.0, blink=1.0):
    """Whole glyph scaled about its centre; blink squashes the eyes in x
    (':3' is a sideways face, so its eyelids close horizontally)."""
    contours = [[(x * sx, y * sy) for x, y in THREE]]
    for cx, cy, r in DOTS:
        ring = []
        for k in range(DOT_POINTS):
            a = 2 * math.pi * k / DOT_POINTS
            ring.append(((cx + r * blink * math.cos(a)) * sx, (cy + r * math.sin(a)) * sy))
        contours.append(ring)
    return contours


def timeline():
    frames = []
    # squash and stretch: 9 frames
    bounce = [(1.0, 1.0), (1.06, 0.94), (1.12, 0.88), (1.08, 0.94), (0.97, 1.04), (0.95, 1.06), (0.99, 1.02), (1.01, 0.99), (1.0, 1.0)]
    for sx, sy in bounce:
        frames.append(frame_contours(sx, sy))
    frames.append(frame_contours())
    # blink: close over 4 frames, open over 5
    for k in range(1, 10):
        t = k / 4 if k <= 4 else 1 - (k - 4) / 5
        frames.append(frame_contours(blink=1 - 0.85 * ease(t)))
    frames.append(frame_contours())
    return frames


frames = timeline()
static = frames[-1]

# --- icons.py entry ---------------------------------------------------------
def fmt(v):
    s = "%.3f" % v
    s = s.rstrip("0").rstrip(".") if "." in s else s
    if s in ("-0", ""):
        s = "0.0"
    if "." not in s:
        s += ".0"
    return s


lines = ['    "internet_creature": (']
for contour in static:
    flat = ", ".join(fmt(c) for x, y in contour for c in (x, y))
    lines.append("        (%s)," % flat)
lines.append("    ),")
entry = "\n".join(lines) + "\n"

source = open(icons_path).read()
assert '"internet_creature"' not in source
anchor = '    "iss": ('
assert source.count(anchor) == 1
source = source.replace(anchor, entry + anchor)
open(icons_path, "w").write(source)

# --- BWIC v3 animation --------------------------------------------------------
header_size = 9 + 4 * len(frames)
blobs = []
for contours in frames:
    blob = bytearray(struct.pack("<B", len(contours)))
    for contour in contours:
        blob += struct.pack("<H", len(contour))
        for x, y in contour:
            blob += struct.pack("<ff", x, y)
    blobs.append(bytes(blob))
offsets = []
cursor = header_size
for blob in blobs:
    offsets.append(cursor)
    cursor += len(blob)
with open(anim_path, "wb") as f:
    f.write(b"BWIC" + struct.pack("<HBH", 3, FPS, len(frames)))
    f.write(struct.pack("<%dI" % len(frames), *offsets))
    for blob in blobs:
        f.write(blob)
print("frames", len(frames), "bytes", cursor, file=sys.stderr)

# --- previews -------------------------------------------------------------------
TILE, ICON, SS = 75, 48, 6


def tile(contours, rgb, selected):
    im = Image.new("RGB", (TILE * SS, TILE * SS), rgb if selected else tuple(round(c * 0.22) for c in rgb))
    d = ImageDraw.Draw(im)
    if selected:
        d.rectangle((0, 0, TILE * SS - 1, TILE * SS - 1), outline="white", width=2 * SS)
    for contour in contours:
        d.polygon([((TILE / 2 + x * ICON) * SS, (TILE / 2 + y * ICON) * SS) for x, y in contour], fill="white")
    return im.resize((TILE, TILE), Image.LANCZOS)


pink = (247, 54, 120)
row = Image.new("RGB", (TILE * 4 + 12, TILE), "black")
for k, (rgb, sel) in enumerate([(pink, False), (pink, True), ((88, 58, 247), True), ((22, 143, 251), True)]):
    row.paste(tile(static, rgb, sel), (k * (TILE + 4), 0))
row.resize((row.size[0] * 3, row.size[1] * 3), Image.NEAREST).save(preview_dir + "/icon_tiles_x3.png")

strip = Image.new("RGB", ((TILE + 2) * len(frames), TILE), "black")
for k, contours in enumerate(frames):
    strip.paste(tile(contours, pink, True), (k * (TILE + 2), 0))
strip.save(preview_dir + "/icon_anim_strip.png")
