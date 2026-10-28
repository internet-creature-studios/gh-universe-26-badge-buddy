"""Composite the badge scene the way the app draws it, for checking by eye.

    python3 examples/internet-creature-studios/preview_scene.py badge/apps/internet_creature/assets out.png [seconds ...]

Each time given (default 0) becomes one row of the output: the scene after
that many seconds of the level drift, so layers have slid apart.
"""

import json
import os
import sys

from PIL import Image


def frame(assets, scene, seconds, blur=0):
    img = Image.new("RGBA", (scene["width"], scene["height"]))
    img.alpha_composite(Image.open(os.path.join(assets, "sky_top.png")).convert("RGBA"), (0, 0))
    img.alpha_composite(Image.open(os.path.join(assets, "sky_band.png")).convert("RGBA"), (0, scene["sky_top"]))
    for layer in scene["layers"]:
        name = layer["name"]
        if blur and layer["blur"]:
            name += "_b%d" % min(blur, len(layer["blur"]))
        strip = Image.open(os.path.join(assets, "layers", name + ".png")).convert("RGBA")
        x = int(round(-(layer["drift"] * seconds))) % layer["width"]
        for left in (-x, layer["width"] - x):
            if left < scene["width"]:
                img.alpha_composite(strip, (left, layer["top"]))
    logo = Image.open(os.path.join(assets, "logo_lower.png")).convert("RGBA")
    img.alpha_composite(logo, (scene["logo_lower"]["x"], scene["logo_lower"]["y"]))
    return img


def main(assets, out, *times):
    scene = json.load(open(os.path.join(assets, "scene.json")))
    times = [float(t) for t in times] or [0.0]
    sheet = Image.new("RGBA", (scene["width"], scene["height"] * len(times)))
    for row, seconds in enumerate(times):
        sheet.alpha_composite(frame(assets, scene, seconds), (0, row * scene["height"]))
    sheet.convert("RGB").save(out)


if __name__ == "__main__":
    main(*sys.argv[1:])
