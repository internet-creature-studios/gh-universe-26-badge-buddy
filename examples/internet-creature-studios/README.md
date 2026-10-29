# Example: Internet Creature Studios

The studio's logo over its website's rolling hills. The hills are drawn live as
four parallax layers, and the badge's tilt steers them. Held level, they drift
left at the site's pace. Tip the badge and they race away that way, up to 24
times as fast. It runs at about 30 fps.

![The badge scene at four moments](preview/hills_layers.png)

## Install and use

Follow the repo's [installation guide](../../README.md#install-on-your-badge)
for prerequisites and port discovery. From the repo root, install just this
app with:

```bash
python3 tools/deploy.py badge/apps/internet_creature --dry-run
python3 tools/deploy.py badge/apps/internet_creature
```

Open **Internet Creature** in the badge menu. Tilt to steer; **press Enter
(↩) twice** to exit. Enter is on the bottom row. Other buttons only show a
reminder of that, so it's safe to leave running. Home also exits.

All scene assets are included; no rendering step is needed to run the app.
For the custom menu icon and its animation, use the full install in the
installation guide, which also explains the shared menu files it replaces.

## Customize the motion

The app is in [`badge/apps/internet_creature/`](../../badge/apps/internet_creature).
Its feel is set by constants at the top of `__init__.py`: `RACE`,
`TILT_CURVE`, `RESPONSE_MS` and `TILT_SIGN`.

After editing, deploy the same app folder again. To try changes without an
installed copy, use the [temporary app workflow](../../docs/workflow.md#trying-an-app-without-installing-it).

## Preview the supplied assets on your Mac

This needs Pillow; `uv` provides it for the command. From the repo root:

```bash
uv run --with pillow examples/internet-creature-studios/preview_scene.py \
  badge/apps/internet_creature/assets out.png 0 12 24
```

`out.png` shows the scene at three moments of the level drift. This works
with the included assets and doesn't need the private terrain preset.

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

**Regenerating the terrain requires a private input.** The hills preset lives
in the studio's private site repo and isn't included here. The command below
is for someone who already has that repo at the shown path; a public clone
of this repo is enough to install or preview the app, but can't reproduce
this rendering step on its own:

```bash
uv run --with numpy --with pillow examples/internet-creature-studios/render_layers.py \
  ~/Code/internet-creature-studios/src/hills/presets/mock-match.json \
  examples/internet-creature-studios/source badge/apps/internet_creature/assets
```

The look is tuned in `LAYERS` and `LIGHT_OVERRIDES` at the top of the script.
Use the preview command above to check a render without the badge.

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

This section runs code on the connected badge. Use the serial port you found
in the installation guide in place of `YOUR_BADGE_PORT`, and reset to the
menu when finished.

[`bench_tilt.py`](bench_tilt.py) runs the app on the badge with the motion
sensor replaced by a fixed reading, and prints the app's
`ICS_BADGE_BENCHMARK` line:

```bash
uvx mpremote connect YOUR_BADGE_PORT exec "AX = 16384
$(cat examples/internet-creature-studios/bench_tilt.py)"
```

After the benchmark line appears, press **Ctrl-C** to stop the running
command, then reset:

```bash
uvx mpremote connect YOUR_BADGE_PORT reset
```
