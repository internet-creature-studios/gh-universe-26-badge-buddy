#!/usr/bin/env python3
"""Add or replace an app's menu icon, and compile the menu's icon table.

    python3 tools/menu_icon.py <app folder name> <contours.json>

contours.json is a list of contours, each a list of [x, y] points in icon
units: about -0.5 to 0.5 across, centred on 0, y down. The menu fills them in
white with the non-zero rule, so wind a hole the opposite way to the shape
around it (see docs/menu.md).

Edits badge/apps/menu/src/icons.py, copying it from stock/ first if needed,
and compiles it to badge/apps/menu/icons.mpy with mpy-cross 1.29 (via uvx).
Install both with tools/deploy.py badge/apps/menu.
"""

import json
import os
import re
import shutil
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = os.path.join(REPO, "badge", "apps", "menu", "src", "icons.py")
STOCK = os.path.join(REPO, "stock", "apps", "menu", "src", "icons.py")
COMPILED = os.path.join(REPO, "badge", "apps", "menu", "icons.mpy")
MPY_CROSS = ["uvx", "mpy-cross"]
# The badge's MicroPython 1.29 loads .mpy v6.3.
MPY_FORMAT = "mpy v6.3"


def number(v):
    s = "%.3f" % v
    s = s.rstrip("0").rstrip(".")
    if s in ("-0", ""):
        s = "0"
    return s if "." in s else s + ".0"


def entry(name, contours):
    lines = ['    "%s": (' % name]
    for contour in contours:
        if len(contour) < 3:
            sys.exit("menu_icon: every contour needs at least 3 points")
        lines.append("        (%s)," % ", ".join(number(c) for point in contour for c in point))
    lines.append("    ),")
    return "\n".join(lines) + "\n"


def main(name, contours_path):
    if not re.fullmatch(r"[a-z0-9_]+", name):
        sys.exit("menu_icon: %r is not an app folder name" % name)
    contours = json.load(open(contours_path))
    if not os.path.exists(SOURCE):
        os.makedirs(os.path.dirname(SOURCE), exist_ok=True)
        shutil.copyfile(STOCK, SOURCE)
    source = open(SOURCE).read()
    new = entry(name, contours)
    existing = re.compile(r'^    "%s": \(\n(?:        .*\n)*?    \),\n' % re.escape(name), re.M)
    if existing.search(source):
        source = existing.sub(lambda m: new, source, count=1)
        action = "replaced"
    else:
        end = source.rindex("\n}")
        source = source[:end + 1] + new + source[end + 1:]
        action = "added"
    version = subprocess.run(MPY_CROSS + ["--version"], capture_output=True, text=True).stdout
    if MPY_FORMAT not in version:
        sys.exit("menu_icon: mpy-cross emits %r, but the badge needs %s" % (version.strip(), MPY_FORMAT))
    with open(SOURCE, "w") as f:
        f.write(source)
    subprocess.run(MPY_CROSS + ["-s", "icons.py", "-o", COMPILED, SOURCE], check=True)
    print("%s the %s icon (%d contours); compiled %s" % (action, name, len(contours), os.path.relpath(COMPILED, REPO)))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__.strip())
    main(sys.argv[1], sys.argv[2])
