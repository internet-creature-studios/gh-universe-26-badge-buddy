# GitHub Universe 2026 badge studio

Notes, tools and an example for building your own apps for the GitHub
Universe 2026 badge, a Pimoroni Badger 2350 running MonaOS. It's written so an
AI coding agent (or a person) can start building on the badge without
rediscovering how it works:

- how to get code onto it,
- how to recover it,
- what its API does,
- what things cost.

![The example app](examples/internet-creature-studios/preview/hills_layers.png)

**Example:** Internet Creature Studios' logo over the studio site's hills,
drawn live as parallax layers that race left or right as you tilt the badge.
It runs at about 30 fps. The example also adds a `:3` menu icon with a
blinking selection animation. See
[examples/internet-creature-studios](examples/internet-creature-studios).

## Start here

| | |
| --- | --- |
| [AGENTS.md](AGENTS.md) | Rules and workflow for AI agents (Claude Code reads it through `CLAUDE.md`) |
| [docs/workflow.md](docs/workflow.md) | Serial and disk mode, deploying safely, resetting and recovering |
| [docs/hardware.md](docs/hardware.md) | The badge, its firmware, storage and sensors |
| [docs/api.md](docs/api.md) | The Badgeware API as used on the badge |
| [docs/performance.md](docs/performance.md) | Measured costs, the frame budget, and what works |
| [docs/menu.md](docs/menu.md) | How apps get menu tiles, icons and animations |

## Quick start

You need a Mac with [`uv`](https://docs.astral.sh/uv/) and the badge on
USB-C. Everything else runs through `uvx`.

```bash
# Is it there? (serial port in normal mode)
ls /dev/cu.usbmodem*
uvx mpremote connect /dev/cu.usbmodem1101 fs ls :/system/apps

# Writing apps needs disk mode: the BADGER drive mounts
uvx mpremote connect /dev/cu.usbmodem1101 exec "import powman; powman.reset_into_msc()"
```

Then copy files from `badge/` to the same paths on `/Volumes/BADGER`. Read
[docs/workflow.md](docs/workflow.md#copying-files-safely) first: macOS and the
badge's FAT drive have a few traps. Eject, and the badge reboots to its menu.

If the badge shows no serial port and no drive, it has hung: press RESET on
the back once.

## Layout

```
badge/      mirrors the badge's /system drive: what this repo installs
stock/      the firmware's original copies of files badge/ replaces
examples/   how each example's assets are made
docs/       what's known about the badge
```

`badge/apps/menu/` and `stock/apps/menu/` hold the badge firmware's menu icon
table: the stock version, and one with the example's icon added.
