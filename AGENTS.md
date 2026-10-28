# Guide for AI agents

This repo is for building custom apps for the GitHub Universe 2026 badge, a
Pimoroni Badger 2350 running MonaOS 4.0 on MicroPython 1.29. Someone is
usually sitting with the badge plugged into their Mac over USB-C, and you
drive it with `mpremote`.

Read these before touching the badge:

- [docs/workflow.md](docs/workflow.md): serial and disk mode, safe deploys,
  resets and recovery.
- [docs/hardware.md](docs/hardware.md): what the badge is, and its storage.
- [docs/api.md](docs/api.md): the Badgeware API.
- [docs/performance.md](docs/performance.md): what things cost, and the frame
  budget.
- [docs/menu.md](docs/menu.md): tiles, names, icons and animations.

## Rules

1. **Over serial, `/system` is read-only.** Don't retry writes there. Use disk
   mode (`powman.reset_into_msc()`) and follow the copy steps in
   [workflow.md](docs/workflow.md#copying-files-safely): delete then copy, clear
   the `._*` files, and verify over serial afterwards.
2. **Try apps from the writable root first** (`/dev_app` or similar) and
   install them only once they work. Remove test folders afterwards.
3. **Never touch `/system/secrets.py`.** Don't copy it off the badge, print it
   or commit it.
4. **Don't call `screen.load_into()`.** It hangs the badge until someone
   presses RESET. Before trying any other untested native call, tell the person
   it might need a RESET press.
5. **Leave the badge on its menu.** Finish with `mpremote ... reset`.
6. **No serial port and no `BADGER` drive means the badge has hung.** Ask the
   person to press RESET once. Don't loop on retries.
7. **Measure on the device.** Frames are quantized to 11.2 ms refreshes, so
   aim for about 21 ms or less of drawing for 30 fps
   ([performance.md](docs/performance.md#the-frame-budget)).
8. **Keep the stock originals** of any firmware file you change in `stock/`,
   mirroring their `/system` paths.

## Repo layout

```
badge/      mirrors the badge's /system drive: what this repo installs
  apps/internet_creature/    the example app, with its built assets
  apps/menu/                 menu files this repo changes (icons, tile animation)
stock/      the firmware's original copies of files badge/ replaces
examples/   how each example's assets are made: scripts, sources, previews
docs/       what's known about the badge
```

Deploying is copying `badge/<path>` to `/Volumes/BADGER/<path>`, only the
files you mean to change.

## Making a new app

1. Create `badge/apps/<folder_name>/__init__.py`. The folder name becomes the
   menu name ("my_app" shows as "My App"). Follow the app shape in
   [api.md](docs/api.md#app-shape): `run(update)`, exit on Back, restore modes
   on exit.
2. Load assets by relative path, and decode images once at launch, not per
   frame.
3. Copy it to `/dev_app` and run it over serial with a timeout. Print timing
   lines, and check them against the frame budget.
4. Install it in disk mode, verify, and reset to the menu.
5. For a menu icon, add an `ICONS` entry and recompile `icons.mpy` with
   mpy-cross 1.29 ([menu.md](docs/menu.md)). Keep the stock originals.
6. Put whatever builds the assets (scripts, sources) in
   `examples/<name>/`, and make the app's behaviour knobs constants at the top
   of its `__init__.py`.

## Example: Internet Creature Studios

`badge/apps/internet_creature` draws the studio site's hills as live parallax
layers that the badge's tilt steers, at about 30 fps.
`examples/internet-creature-studios/` explains how its layers, sky, logo and
menu icon were made.
