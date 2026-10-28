# The badge: hardware and firmware

Everything here was read off a real badge, or measured on one, unless it says
otherwise.

## Identity

| | |
| --- | --- |
| Device | GitHub Universe 2026 badge: Pimoroni's "GitHub Badger 2350", an RP2350 |
| USB name | `GitHub Badger 2350 MicroPython`, vendor `0x2e8a`, product `0x1101` |
| Serial port (macOS) | `/dev/cu.usbmodem*`, for example `/dev/cu.usbmodem1101` |
| OS | MonaOS 4.0, shown in the menu's status bar |
| MicroPython | 1.29.0 preview (`sys.implementation`: `_build='badger'`, `_mpy=7942`, which is .mpy v6.3) |
| Free heap | about 7.3 to 7.9 MB at the REPL (`gc.mem_free()`) |

## Display

- 320 x 240 in `HIRES` mode, 160 x 120 in `LORES`. Apps pick with
  `badge.mode(HIRES | VSYNC)` or similar.
- The framebuffer (`screen`) is RGB565: `screen.stride` is 640 in HIRES.
  Images you create or load are RGBA8888, and blitting converts them.
- With `VSYNC` a refresh takes 11.2 ms (about 89 Hz). Each frame takes a whole
  number of refreshes, so 22 ms of work runs at 30 fps but 23 ms drops to 22
  fps. See [performance.md](performance.md).
- The screen keeps its contents between refreshes when
  `badge.default_clear = None`.

## Motion sensor

`badge.imu()` returns six raw integers: accelerometer x, y and z, then three
gyro values. 16384 is 1 g.

- Lying flat and face up, z reads about -16384.
- The menu's tilt reading, `-ax / 16384 * 2` clamped to ±1, is positive when the
  badge's right edge dips. It reaches full scale at about 30 degrees.
- At the REPL it reads all zeros until `badge.poll()` has run. Inside an app's
  `run(update)` loop the firmware polls for you.

## Storage

| Mount | What | Size | Writable from MicroPython |
| --- | --- | --- | --- |
| `/system` | FAT. The OS, the menu and every app. It shows up as the `BADGER` drive in disk mode. | 12.5 MB | **No**, read-only over serial |
| `/` | `secrets.py`, `state/` and a filesystem backup | 1 MB | Yes |
| `/state` | App state such as `achievements.json` and `backlight.json` | (part of `/`) | Yes |
| `/rom` | Fonts and frozen libraries | | No |

`sys.path` is `['', '.frozen', '/rom', '/rom/lib', '/lib']`.

Reading `/system` over serial runs at about 1.9 MB/s: a 37 KB file takes
19 ms.

**`secrets.py` holds the badge's private settings, such as network
credentials.** Never copy it off the badge, print it, or commit it.

## `/system` layout

```
main.py        the launcher (below)
secrets.py     private: never copy or commit
startup/       runs once after a cold boot
assets/
apps/
  menu/        the launcher menu: icons, tile animations, achievements
  badge/ contacts/ mona_paint/ flappy_mona/ snake/ mona_pet/ rogue/ life/
  merge_conflict/ brattal/ pong/ iss/ mass_storage/ settings/ show/ ...
```

An app is a folder in `/system/apps` holding `__init__.py` (or
`__init__.mpy`), plus any assets it loads by relative path. The firmware runs
it with the app's folder as the working directory.

## Boot and launch flow (`/system/main.py`)

1. After a cold boot (not a watchdog reset), it preloads the menu's modules
   and runs `launch("/system/startup")`.
2. It runs `launch("/system/apps/menu")`, which returns the path of the app
   the user picked.
3. It runs `launch(app_path)`.
4. When that app returns, for any reason, `reset()` reboots back to the menu.

So an app ends by returning from its `run(update)` loop. A crash in an app
also ends with a reboot to the menu.

## Buttons

Badgeware hoists button constants into builtins: `BUTTON_LEFT`,
`BUTTON_RIGHT`, `BUTTON_UP`, `BUTTON_DOWN` and `BUTTON_SELECT` (used by the
menu), and `BUTTON_BACK`. `BUTTON_MENU` and `BUTTON_HOME` may not exist on
every firmware, so look them up with `getattr(builtins, ...)`. The menu reads
them with `badge.pressed(b)` and `badge.held(b)`.

The back of the badge has a **RESET** button. See
[workflow.md](workflow.md#reset-and-recovery).

## Battery

`badge.battery_level()` returns 0 to 100, and `badge.is_charging()` returns a
bool. The menu reads them once a second.
