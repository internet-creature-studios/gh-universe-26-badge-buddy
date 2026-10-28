# Example: Repo Defender

![Menu icon](preview/icon_tiles_x3.png)

A tongue-in-cheek first-person shooter: rogue AI bots are coming for your main
branch.

- **Aim by turning.** Turn your body, or just the badge, about 30 degrees either
  way, so it plays seated. The gyro does the aiming.
- **Firing is automatic.** Left and Right switch between three weapons:
  - **LINT**: rapid fire.
  - **REVIEW**: heavy shots.
  - **REVERT**: a short-range spread.
- **Match the colour.** Each bot is tinted the colour of the weapon it's weak
  to, and takes triple damage from it:
  - spam bots: LINT
  - hallucinators, which weave: REVIEW
  - force-pushers, which charge: REVERT
  - mega-agents, which turn up every third release, aren't weak to anything.
- **Defend main.** A bot that reaches you merges into main and costs you
  integrity. Waves are releases, v0.1.0 and up.
- **Buttons.** Select starts, Up re-centres your aim, and Back exits. The best
  score is kept in `/state/repo_defender.json`.

The app is [`badge/apps/repo_defender/__init__.py`](../../badge/apps/repo_defender/__init__.py).
Everything is drawn with rectangles, lines and text, which cost a fraction of
blitting images (see [docs/performance.md](../../docs/performance.md)), so it
runs at 30+ fps with no assets.

## How aiming works

- **Turning is measured around "down".** The accelerometer gives the direction
  of gravity, and the yaw rate is the gyro's reading along it. So it works
  however the badge is tilted in your hands.
- **Gyro units:** two full turns in a playing pose measured 107 and 110 raw
  units per degree per second (`GYRO_LSB_PER_DPS`).
- **Re-learning zero:** the gyro's zero point wanders, and in a hand it's never
  quite still. The game calibrates from the steadiest part of a one-second hold
  at Select, then keeps re-learning zero whenever the badge holds still for
  about 0.4 seconds.
- **The ±30° limit:** turning past it drags the centre along with you, which
  also soaks up whatever drift is left. Up re-centres.

Tuning knobs, at the top of the app:

- **Aim:** `YAW_LIMIT`, `YAW_SIGN`, `HFOV`.
- **Pace:** `WAVE_SECONDS`, and the spawn curve in `Game.update`.
- **Bots and weapons:** the `WEAPONS` and `BOTS` tables.

## The menu icon

A shield guarding a little commit graph. To rebuild it:

```bash
python3 examples/repo-defender/make_icon.py examples/repo-defender/icon.json preview.png
python3 tools/menu_icon.py repo_defender examples/repo-defender/icon.json
python3 tools/deploy.py badge/apps/menu
```
