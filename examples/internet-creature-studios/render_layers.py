"""Render the site's hills as horizontally tiling parallax layers for the badge.

    uv run --with numpy --with pillow examples/internet-creature-studios/render_layers.py \
        ~/Code/internet-creature-studios/src/hills/presets/mock-match.json \
        examples/internet-creature-studios/source badge/apps/internet_creature/assets

The first argument is the site's hills preset, which lives in the studio's
private site repo, so only the studio can re-render. The source directory
holds logo.png, layout.json (where the logo sits) and sky.png, a still of the
site whose sky the badge shows.

The site raymarches a heightfield of soft mounds (src/hills/hills.frag.glsl)
and its "drift" prototype slides them sideways in three depth bands. The
badge cannot raymarch, so this bakes each depth band into a strip that wraps
seamlessly left to right, and the badge scrolls the strips at parallax speeds.

Within a strip, x is orthographic (world units per pixel fixed at the band's
reference depth) so the strip tiles, while the vertical stays in true
perspective. Every column is then a ray marched forward in depth, a 2D
"voxel space" render, shaded with the site's lighting: slope, wrapped sun,
AO, cavity, the OKLab ramp, warm shift, sheen, haze and the crest rim line.

Writes into the output directory:
    layers/<name>.png         one strip per depth band, far to near
    layers/<name>_b<n>.png    horizontally motion-blurred copies for speed
    sky_top.png               the static sky above the hills, logo included
    sky_band.png              the sky behind the far hills, redrawn each frame
    logo_lower.png            the part of the logo the hills pass behind
    scene.json                layout and drift speeds for the app
"""

import json
import math
import os
import sys
import zlib

import numpy as np
from PIL import Image

WIDTH, HEIGHT = 320, 240
# The framing of sky.png, a still of the site, so the hills sit under its
# sky: ground at infinity meets the sky at this row, and the far crests reach
# up to about row 120.
HORIZON = 135.0
SKY_CLEAN_ROWS = 120  # rows of sky.png above its own hills
FOCAL = 120 / math.tan(math.radians(16))  # the preset's 32 degree vertical fov
EYE = 12.0  # the preset camera's height
SS = 3  # supersampling per axis
RIM_WIDTH_PX = 1.3  # the site's 2.6 px at 1080p would vanish at 240 rows
HILL_FLOOR = -1.0
# How far nearer than its band a layer keeps drawing ground, so neighbouring
# layers overlap rather than leave holes where their undulations disagree.
NEAR_MARGIN = 0.15
# The badge's blit cost, measured: per pixel and per call. Strips are cut
# into tiles at multiples of TILE_STEP columns to balance the two.
BLIT_PX_MS = 0.00026
BLIT_MS = 0.14
TILE_STEP = 8
SEED = 20261028

# The site's drift bands (src/hills/prototypes.ts): mounds per 16:9 view width.
FAMILIES = [
    dict(z=(32, 75), n=6, radius=(26, 55), height=(1.5, 5)),
    dict(z=(85, 230), n=11, radius=(35, 90), height=(3, 12)),
    dict(z=(250, 520), n=8, radius=(90, 200), height=(6, 22)),
]
BIG = dict(z=(38, 58), radius=(55, 80), height=(6.5, 9.5))

# Far to near. z is the band of ground the layer owns; ref is the depth whose
# scale it takes across (where its mounds mostly stand); lift scales mound
# heights, since the site's read as low swells in the badge's 4:3 crop.
# width is the strip's length in pixels before it repeats; blur lists
# motion-blur lengths for layers that move fast enough to need them.
# busy multiplies the site's mound density, for overlapping silhouettes.
# The farthest band is one layer, not two: its hills drift a pixel or two a
# second, too little parallax to see, and splitting it cost two milliseconds
# a frame of overdraw and blits.
LAYERS = [
    dict(name="far", z=(170, None), ref=260, lift=1.1, busy=1.15, width=960, blur=()),
    dict(name="mid", z=(100, 170), ref=130, lift=1.35, busy=1.6, width=960, blur=(4,)),
    dict(name="nearmid", z=(60, 100), ref=74, lift=1.4, busy=1.5, width=1280, blur=(5, 12)),
    dict(name="near", z=(20, 60), ref=46, lift=1.25, busy=1.2, width=1280, blur=(6, 16), big=1),
]
# Art direction over the preset, for a small LCD: a little more contrast and
# a crest line wide enough to read.
LIGHT_OVERRIDES = dict(bias=0.0, gamma=1.55)


# ------------------------------------------------------------------ colour

def srgb_to_linear(c):
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(c):
    c = np.clip(c, 0.0, 1.0)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(c, 1 / 2.4) - 0.055)


def hex_to_oklab(hex_colour):
    v = int(hex_colour.lstrip("#")[:6], 16)
    r, g, b = srgb_to_linear(np.array([(v >> 16) & 255, (v >> 8) & 255, v & 255]) / 255.0)
    l = np.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b)
    m = np.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b)
    s = np.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b)
    return np.array([
        0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s,
        1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s,
        0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s,
    ])


def oklab_to_srgb(lab):
    L, a, b = lab[..., 0], lab[..., 1], lab[..., 2]
    l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s = (L - 0.0894841775 * a - 1.291485548 * b) ** 3
    rgb = np.stack([
        4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
        -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
        -0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s,
    ], axis=-1)
    return linear_to_srgb(rgb)


def mix(a, b, t):
    return a + (b - a) * t


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / np.maximum(e1 - e0, 1e-9), 0.0, 1.0)
    return t * t * (3 - 2 * t)


# ----------------------------------------------------------------- terrain

def smax(a, b, k):
    h = np.maximum(k - np.abs(a - b), 0.0) / k
    return np.maximum(a, b) + h * h * k * 0.25


class Band:
    """One layer's terrain: ground undulation plus its mounds, periodic in x."""

    def __init__(self, spec, preset, rng):
        self.name = spec["name"]
        self.z0, self.z1 = spec["z"]
        self.ref = spec["ref"]
        self.lift = spec["lift"]
        self.upp = self.ref / FOCAL  # world units per pixel across
        self.width = spec["width"]
        self.period = self.width * self.upp
        self.blend = preset["terrain"]["blend"]
        self.mounds = self._place_mounds(spec, rng)
        self.waves = self._ground_waves(preset["terrain"], rng)

    def _place_mounds(self, spec, rng):
        z_hi = self.z1 if self.z1 is not None else 520.0
        mounds = []
        for family in FAMILIES:
            lo, hi = max(self.z0, family["z"][0]), min(z_hi, family["z"][1])
            if hi <= lo:
                continue
            fz0, fz1 = family["z"]
            density = family["n"] / (1.02 * 0.5 * (fz0 + fz1) * (fz1 - fz0))
            count = int(round(density * spec["busy"] * self.period * (hi - lo)))
            for i in range(count):
                mounds.append(self._mound(family, (i + rng.uniform(0.1, 0.9)) * self.period / count, rng.uniform(lo, hi), rng))
        big = spec.get("big", 0)
        for i in range(big):
            mounds.append(self._mound(BIG, (i + rng.uniform(0.2, 0.8)) * self.period / big, rng.uniform(*BIG["z"]), rng))
        return mounds

    def _mound(self, family, x, z, rng):
        radius = rng.uniform(*family["radius"])
        stretch = 0.35 + rng.uniform() * 0.25
        height = 0.4 + rng.uniform(*family["height"]) * rng.uniform(0.8, 1.0) * self.lift
        if self.z1 is not None:
            # Only the far band rises over the horizon, as on the site; a
            # nearer hill that did would also widen what redraws each frame.
            height = min(height, EYE - 0.5)
        return dict(
            x=x, z=z,
            height=height,
            rx=radius, rz=radius * stretch,
            shape=1.2 + rng.uniform() * 1.4,
        )

    def _ground_waves(self, terrain, rng):
        # The site's base fbm, as sines whose x frequencies are whole cycles
        # per period so the strip wraps without a seam. Its fine detail noise
        # is left out: at 240 rows it only breaks crest lines into dashes.
        waves = []
        for freq, amp in ((1.0, 0.35), (2.03, 0.17), (4.12, 0.09)):
            waves.append((terrain["baseScale"] * freq, terrain["baseAmp"] * amp))
        out = []
        for freq, amp in waves:
            angle = rng.uniform(0, math.pi)
            cycles = max(1, round(freq * abs(math.cos(angle)) * self.period))
            out.append((cycles * 2 * math.pi / self.period, freq * math.sin(angle) * 2 * math.pi, rng.uniform(0, 2 * math.pi), amp))
        return out

    def ground(self, x, z):
        g = np.zeros(np.broadcast(x, z).shape)
        for kx, kz, phase, amp in self.waves:
            g = g + amp * np.sin(kx * x + kz * z + phase)
        return g

    def mound_heights(self, x, z):
        """Each mound's height at (x, z), the floor outside it, one at a time."""
        p = self.period
        for m in self.mounds:
            dx = np.mod(x - m["x"] + p / 2, p) - p / 2
            q2 = (dx / m["rx"]) ** 2 + ((z - m["z"]) / m["rz"]) ** 2
            yield np.where(q2 < 1, mix(HILL_FLOOR, m["height"], np.power(np.clip(1 - q2, 0, None), m["shape"])), HILL_FLOOR)

    def height(self, x, z):
        h = self.ground(x, z)
        for mh in self.mound_heights(x, z):
            h = np.where(mh > HILL_FLOOR, smax(h, mh, self.blend), h)
        return h

    def coverage(self, x, z, h):
        total = np.zeros(np.broadcast(x, z).shape)
        for mh in self.mound_heights(x, z):
            total = total + np.exp(-np.maximum(h - mh, 0.0) / (0.5 * self.blend))
        return np.minimum(total, 1.0)


# ----------------------------------------------------------------- shading

class Look:
    def __init__(self, p):
        self.ramp = [hex_to_oklab(p["ramp"][k]) for k in ("c0", "c1", "c2", "c3", "c4")]
        s1 = min(max(p["ramp"]["s1"], 0.01), 0.97)
        s2 = min(max(p["ramp"]["s2"], s1 + 0.01), 0.98)
        self.stops = (s1, s2, min(max(p["ramp"]["s3"], s2 + 0.01), 0.99))
        az, el = math.radians(p["sun"]["azimuth"]), math.radians(p["sun"]["elevation"])
        self.sun = np.array([math.sin(az) * math.cos(el), math.sin(el), -math.cos(az) * math.cos(el)])
        self.warmth = (p["warmth"]["amount"], math.radians(p["warmth"]["hue"]), p["warmth"]["chroma"], p["warmth"]["lift"])
        self.light = dict(p["light"], **LIGHT_OVERRIDES)
        self.rim = p["rim"]
        self.rim_lab = hex_to_oklab(p["rim"]["color"])
        self.sheen = p["sheen"]
        self.sheen_lab = hex_to_oklab(p["sheen"]["color"])
        self.haze = p["haze"]
        self.haze_lab = hex_to_oklab(p["haze"]["color"])
        sky = p["sky"]
        self.horizon_lab = hex_to_oklab(sky["horizon"])
        self.glow_lab = hex_to_oklab(sky["glowColor"])
        self.glow = (sky["glow"], sky["glowPower"])

    def ramp_at(self, x):
        s1, s2, s3 = self.stops
        r = self.ramp
        x = x[..., None]
        return np.where(x < s1, mix(r[0], r[1], x / s1),
               np.where(x < s2, mix(r[1], r[2], (x - s1) / (s2 - s1)),
               np.where(x < s3, mix(r[2], r[3], (x - s2) / (s3 - s2)),
                        mix(r[3], r[4], (x - s3) / (1 - s3)))))

    def warm_shift(self, lab, sun):
        amount, hue_shift, chroma_scale, lift = self.warmth
        w = sun * amount
        chroma = np.hypot(lab[..., 1], lab[..., 2]) * mix(1.0, chroma_scale, w)
        hue = np.arctan2(lab[..., 2], lab[..., 1]) + hue_shift * w
        return np.stack([lab[..., 0] + lift * w, chroma * np.cos(hue), chroma * np.sin(hue)], axis=-1)


def shade(band, look, x, z, dy):
    """Colour (sRGB 0..1) of hits at (x, z) seen along rays climbing dy per unit depth."""
    h = band.height(x, z)
    t = np.hypot(z, EYE - h)
    # World axes as the shader has them: z there points back toward the eye.
    e = 0.02 + 0.0015 * t
    dhdx = (band.height(x + e, z) - band.height(x - e, z)) / (2 * e)
    dhdz = (band.height(x, z + e) - band.height(x, z - e)) / (2 * e)
    n = np.stack([-dhdx, np.ones_like(h), dhdz], axis=-1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    rd = np.stack([np.zeros_like(dy), dy, -np.ones_like(dy)], axis=-1)
    rd /= np.linalg.norm(rd, axis=-1, keepdims=True)
    v = -rd
    nv = np.clip(np.sum(n * v, axis=-1), 0.0, 1.0)

    # Crest line: curvature along the view, as in the shader.
    eb = 0.3 + 0.004 * t
    bend = -(band.height(x, z + eb) - 2 * h + band.height(x, z - eb)) / (eb * eb)
    nv_line = np.minimum(np.sqrt(2 * t * (1 / FOCAL) * RIM_WIDTH_PX * np.maximum(bend, 0.0)), look.rim["grazing"])
    crest = np.where(bend > 0, 1 - smoothstep(0.55 * nv_line, nv_line, nv), 0.0)

    L = look.light
    slope = np.clip((n[..., 1] - L["slopeFloor"]) / max(1 - L["slopeFloor"], 1e-3), 0, 1)
    sun = np.clip((n @ look.sun + L["wrap"]) / (1 + L["wrap"]), 0, 1)
    light = L["sky"] * slope + L["sun"] * sun

    # AO along the normal and cavity against a ring, radii growing with distance.
    radius = L["aoRadius"] * (1 + L["radiusGrow"] * t * 0.01)
    occ = np.zeros_like(h)
    weight, total = 1.0, 0.0
    for i in range(1, 6):
        hh = radius * i / 5
        qx, qy, qz = x + n[..., 0] * hh, h + n[..., 1] * hh, z - n[..., 2] * hh
        occ += weight * np.clip((hh - (qy - band.height(qx, qz))) / hh, 0, 1)
        total += weight
        weight *= 0.8
    ao = 1 - occ / total
    r = L["cavityRadius"] * (1 + L["radiusGrow"] * t * 0.01)
    ring = band.height(x + r, z) + band.height(x - r, z) + band.height(x, z + r) + band.height(x, z - r)
    cavity = np.clip((0.25 * ring - h) / (0.15 * r), -1, 1)

    light = light * mix(1.0, ao, L["ao"]) - L["folds"] * np.maximum(cavity, 0) + L["crests"] * np.maximum(-cavity, 0)
    light = np.power(np.clip(light + L["bias"], 0, 1), L["gamma"])

    lab = look.warm_shift(look.ramp_at(light), sun)
    half = look.sun + v
    half /= np.linalg.norm(half, axis=-1, keepdims=True)
    spec = np.power(np.maximum(np.sum(n * half, axis=-1), 0), look.sheen["power"])
    lab = mix(lab, look.sheen_lab, np.clip(look.sheen["strength"] * spec, 0, 1)[..., None])

    toward = np.maximum(rd @ look.sun, 0)
    sky = mix(look.horizon_lab, look.glow_lab, (look.glow[0] * np.power(toward, look.glow[1]))[..., None])
    hz = look.haze
    fog = 1 - np.exp(-np.power(np.maximum(t - hz["start"], 0) * hz["density"], hz["power"]))
    lab = mix(lab, mix(look.haze_lab, sky, hz["skyMix"]), fog[..., None])

    coverage = band.coverage(x, z, h)
    fade = smoothstep(0.2, 0.7, coverage) / (1 + (t * t) / (look.rim["fade"] ** 2))
    rim = np.clip(crest + look.rim["glow"] * np.power(1 - nv, look.rim["glowPower"]), 0, 1) * look.rim["strength"] * fade
    lab = mix(lab, look.rim_lab, rim[..., None])
    return oklab_to_srgb(lab)


# ----------------------------------------------------------------- render

def render_band(band, look, ss, width):
    cols = width * ss
    x = (np.arange(cols) + 0.5) / ss * band.upp
    reach = max([m["rz"] for m in band.mounds] + [0])
    z_lo = max(6.0, min(band.z0 * (1 - NEAR_MARGIN), band.z0 - reach))
    z_hi = 8000.0 if band.z1 is None else band.z1 + reach
    zs = np.geomspace(z_lo, z_hi, 1400)
    H = band.height(x[:, None], zs[None, :])  # (cols, depth samples)

    rgba = np.zeros((HEIGHT * ss, cols, 4))
    for row in range(HEIGHT * ss):
        y = (row + 0.5) / ss
        dy = (HORIZON - y) / FOCAL
        ray = EYE + dy * zs
        below = ray[None, :] <= H
        hit = below.any(axis=1)
        if not hit.any():
            continue
        i = np.argmax(below, axis=1)
        cols_hit = np.nonzero(hit & (i > 0))[0]
        if cols_hit.size == 0:
            continue
        i = i[cols_hit]
        d0 = ray[i - 1] - H[cols_hit, i - 1]
        d1 = ray[i] - H[cols_hit, i]
        z = zs[i - 1] + (zs[i] - zs[i - 1]) * d0 / np.maximum(d0 - d1, 1e-9)
        xh = x[cols_hit]
        h = band.height(xh, z)
        on_mound = band.coverage(xh, z, h) > 0.5
        nearest = band.z0 * (1 - NEAR_MARGIN)
        keep = on_mound | ((z >= nearest) & ((band.z1 is None) | (z <= (band.z1 or 0))))
        if not keep.any():
            continue
        cols_hit, z, xh = cols_hit[keep], z[keep], xh[keep]
        rgba[row, cols_hit, :3] = shade(band, look, xh, z, np.full(z.shape, dy))
        rgba[row, cols_hit, 3] = 1.0

    # Resolve the supersamples with premultiplied alpha.
    pre = rgba.copy()
    pre[..., :3] *= pre[..., 3:4]
    pre = pre.reshape(HEIGHT, ss, width, ss, 4).mean(axis=(1, 3))
    return pre  # premultiplied, (HEIGHT, width, 4)


def unpremultiply(pre):
    out = pre.copy()
    a = out[..., 3:4]
    out[..., :3] = np.where(a > 0, out[..., :3] / np.maximum(a, 1e-9), 0)
    return out


def motion_blur(pre, length):
    """Box blur along x over a strip that wraps, in premultiplied alpha."""
    if length <= 1:
        return pre
    acc = np.zeros_like(pre)
    for k in range(length):
        acc += np.roll(pre, k - length // 2, axis=1)
    return acc / length


def to_image(pre):
    rgba = unpremultiply(pre)
    return Image.fromarray(np.round(np.clip(rgba, 0, 1) * 255).astype(np.uint8), "RGBA")


def plan_tiles(img):
    """Rectangles [x, y, w, h] covering every pixel of img with any alpha.

    The badge blits only these: a blit costs about BLIT_PX_MS per pixel,
    transparent or not, plus BLIT_MS each, and a strip is as tall as its
    tallest hill. So the image splits at runs of empty rows, then each band
    is cut into columns where the saving in area outweighs another blit.
    Every row from the horizon down is still repainted each frame by
    something opaque, since tiles only leave out pixels with zero alpha.
    """
    alpha = np.asarray(img.getchannel("A")) > 0
    filled_rows = np.nonzero(alpha.any(axis=1))[0]
    bands = []
    for y in filled_rows:
        if bands and y - bands[-1][1] <= 2:
            bands[-1][1] = y + 1
        else:
            bands.append([y, y + 1])
    tiles = []
    for y0, y1 in bands:
        band = alpha[y0:y1]
        groups = range(0, img.width, TILE_STEP)
        extent = []
        for x in groups:
            rows = np.nonzero(band[:, x:x + TILE_STEP].any(axis=1))[0]
            extent.append((y0 + rows[0], y0 + rows[-1] + 1) if rows.size else None)
        n = len(extent)
        best = [0.0] + [math.inf] * n
        cut = [0] * (n + 1)
        for end in range(1, n + 1):
            top, bottom = math.inf, -math.inf
            for start in range(end - 1, -1, -1):
                if extent[start] is not None:
                    top, bottom = min(top, extent[start][0]), max(bottom, extent[start][1])
                width = min(end * TILE_STEP, img.width) - start * TILE_STEP
                cost = 0.0 if bottom < top else BLIT_MS + BLIT_PX_MS * width * (bottom - top)
                if best[start] + cost < best[end]:
                    best[end], cut[end] = best[start] + cost, start
        end = n
        while end > 0:
            start = cut[end]
            rows = [e for e in extent[start:end] if e is not None]
            if rows:
                x = start * TILE_STEP
                top, bottom = min(r[0] for r in rows), max(r[1] for r in rows)
                tiles.append([x, int(top), min(end * TILE_STEP, img.width) - x, int(bottom - top)])
            end = start
    return sorted(tiles)


def main(preset_path, source, out, mode="full"):
    # "preview" renders one screen of each strip without supersampling, for
    # quick looks with preview_scene.py.
    preview = mode == "preview"
    preset = json.load(open(preset_path))
    look = Look(preset)
    os.makedirs(os.path.join(out, "layers"), exist_ok=True)

    bands, renders, opaque = [], [], []
    for spec in LAYERS:
        # Seeded per layer, so retuning one layer leaves the others' hills be.
        band = Band(spec, preset, np.random.default_rng([SEED, zlib.crc32(spec["name"].encode())]))
        width = WIDTH if preview else band.width
        pre = render_band(band, look, 1 if preview else SS, width)
        full = np.nonzero(pre[..., 3].min(axis=1) > 0.999)[0]
        bands.append((spec, band, width))
        renders.append(pre)
        opaque.append((int(full[0]), int(full[-1])) if full.size else None)

    # No row from the horizon down may ever be left undrawn: each layer's
    # opaque rows must reach the next nearer layer's.
    for k in range(len(LAYERS) - 1):
        if opaque[k] is None or opaque[k + 1] is None or opaque[k][1] + 1 < opaque[k + 1][0]:
            raise SystemExit("gap between %s %s and %s %s" % (LAYERS[k]["name"], opaque[k], LAYERS[k + 1]["name"], opaque[k + 1]))
    if opaque[0][0] > HORIZON + 3 or opaque[-1][1] != HEIGHT - 1:
        raise SystemExit("layers do not cover the horizon to the bottom: %s" % opaque)

    layers = []
    rows_drawn = 0
    for k, ((spec, band, width), pre) in enumerate(zip(bands, renders)):
        # Rows that nearer layers always cover all the way down need not be
        # drawn, so the strip stops where that cover begins.
        cover = HEIGHT
        for start, end in reversed(opaque[k + 1:]):
            if end + 1 >= cover:
                cover = min(cover, start)
        rows = np.nonzero(pre[..., 3].max(axis=1) > 0.004)[0]
        top, bottom = int(rows[0]), min(int(rows[-1]) + 1, cover)
        strip = pre[top:bottom]
        img = to_image(strip)
        img.save(os.path.join(out, "layers", spec["name"] + ".png"), optimize=True)
        tiles = [plan_tiles(img)]
        blurs = []
        for n, length in enumerate(spec["blur"], 1):
            img = to_image(motion_blur(strip, length))
            img.save(os.path.join(out, "layers", "%s_b%d.png" % (spec["name"], n)), optimize=True)
            tiles.append(plan_tiles(img))
            blurs.append(length)
        # The site's drift: 1.6 * sqrt(150 / d) world units a second, to the
        # left on the badge, as the site's own recording showed.
        drift = -1.6 * math.sqrt(150 / band.ref) / band.upp
        layers.append(dict(name=spec["name"], top=top, width=width, drift=round(drift, 3), blur=blurs, tiles=tiles))
        rows_drawn += sum(w * h for x, y, w, h in tiles[0]) / width
        print("%-8s rows %3d-%3d  %4d px wide  %2d mounds  drift %6.1f px/s"
              % (spec["name"], top, bottom - 1, width, len(band.mounds), drift))
    print("layer rows drawn per frame, on average: %d" % rows_drawn)
    sky_top = min(l["top"] for l in layers)
    sky_bottom = opaque[0][0]  # the far layer is opaque from here down
    layout = json.load(open(os.path.join(source, "layout.json")))
    frame = Image.open(os.path.join(source, "sky.png")).convert("RGBA")
    logo = Image.open(os.path.join(source, "logo.png")).convert("RGBA")
    logo_at = (layout["logo_x"], layout["logo_y"])

    # Below row SKY_CLEAN_ROWS - 1, sky.png shows the site's own hills. Both
    # sky images repeat that last clean row instead: the static one too, or
    # a sliver of those hills hangs frozen above the live ones.
    def sky(first, end):
        img = Image.new("RGBA", (WIDTH, end - first))
        for y in range(first, end):
            row = min(y, SKY_CLEAN_ROWS - 1)
            img.paste(frame.crop((0, row, WIDTH, row + 1)), (0, y - first))
        return img

    sky(sky_top, sky_bottom + 1).convert("RGB").save(os.path.join(out, "sky_band.png"), optimize=True)

    top_img = sky(0, sky_top)
    top_img.alpha_composite(logo, logo_at)
    top_img.convert("RGB").save(os.path.join(out, "sky_top.png"), optimize=True)

    lower = logo.crop((0, sky_top - logo_at[1], logo.width, logo.height))
    lower.save(os.path.join(out, "logo_lower.png"), optimize=True)

    scene = dict(
        width=WIDTH, height=HEIGHT, sky_top=sky_top,
        logo_lower=dict(x=logo_at[0], y=sky_top, tiles=plan_tiles(lower)),
        layers=layers,
    )
    with open(os.path.join(out, "scene.json"), "w") as f:
        json.dump(scene, f, indent=2)
        f.write("\n")
    print("sky_top %d, sky band to %d" % (sky_top, sky_bottom))


if __name__ == "__main__":
    main(*sys.argv[1:5])
