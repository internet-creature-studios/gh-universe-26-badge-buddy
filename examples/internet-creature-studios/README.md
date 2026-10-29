# Example: Internet Creature Studios

![The badge scene at four moments](preview/hills_layers.png)

The studio's logo over its website's rolling hills. The hills are drawn live as
four parallax layers, and the badge's tilt steers them. Held level, they drift
left at the site's pace. Tip the badge and they race away that way, up to 24
times as fast. It runs at about 30 fps.

The app is in [`badge/apps/internet_creature/`](../../badge/apps/internet_creature).
Its feel is set by constants at the top of `__init__.py`: `RACE`,
`TILT_CURVE`, `RESPONSE_MS` and `TILT_SIGN`.

It's made to be left running on a badge you're wearing, so no single press
leaves it. Any button shows "press ↩ twice to exit" at the bottom, with a
pointer bobbing down at enter, and two presses of enter within 3 s
(`HINT_MS`) leave. Home still leaves, as the firmware handles it. The hint
sits over the nearest hills, which repaint every row each frame, so the next
redraw wipes it.

## How the hills are made

The website raymarches a heightfield of soft mounds in a WebGL shader, which
the badge can't do. [`render_layers.py`](render_layers.py) bakes the site's
"drift" scene ahead of time instead:

- **Depth bands:** the scene is split into four, each a strip that wraps
  seamlessly left to right. Across each strip, x is flat (orthographic), so it
  can tile. Up and down stays in true perspective.
- **Rendering:** each column is a ray marched forward through the band's
  terrain. It's shaded like the site: slope and wrapped sun light, AO, cavity,
  an OKLab colour ramp, warm shift, sheen, haze and crest rim lines.
- **Motion blur:** the fast layers also get horizontally blurred copies. The
  app switches to one when a layer moves farther per frame than its blur.
- **Tiles:** each strip is cut into tiles cropped to its visible pixels, planned
  from the badge's measured blit costs.

Rendering needs the hills preset from the studio's private site repo, so only
the studio can re-render:

```bash
uv run --with numpy --with pillow examples/internet-creature-studios/render_layers.py \
  ~/Code/internet-creature-studios/src/hills/presets/mock-match.json \
  examples/internet-creature-studios/source badge/apps/internet_creature/assets
```

The look is tuned in `LAYERS` and `LIGHT_OVERRIDES` at the top of the script.
To check a render without the badge:

```bash
python3 examples/internet-creature-studios/preview_scene.py badge/apps/internet_creature/assets out.png 0 12 24
```

`source/` holds `logo.png`, `layout.json` (the logo's position) and
`sky.png`, a still of the site whose sky sits above the hills.

## The menu icon

The menu draws tile icons from vector contours, not images (see
[docs/menu.md](../../docs/menu.md)):

- [`trace_icon.py`](trace_icon.py) traces the pink `:3` out of `logo.png` into
  contours, with the two dots fitted as circles.
- [`build_icon.py`](build_icon.py) adds them to the menu's `icons.py` as
  `internet_creature`. It also writes the selection animation, a
  squash-and-stretch and then the sideways face blinking, as
  `anim/internet_creature.bin`.

![Icon on tiles](preview/icon_tiles_x3.png)

## Benchmarking with a fake tilt

[`bench_tilt.py`](bench_tilt.py) runs the app on the badge with the motion
sensor replaced by a fixed reading, and prints the app's
`ICS_BADGE_BENCHMARK` line:

```bash
uvx mpremote connect /dev/cu.usbmodem1101 exec "AX = 16384
$(cat examples/internet-creature-studios/bench_tilt.py)"
```
