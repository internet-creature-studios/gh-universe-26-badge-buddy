# Example: Repo Defender

![Menu icon](preview/icon_tiles_x3.png)

A tongue-in-cheek first-person shooter: rogue AI bots are coming for your main
branch. It plays seated.

## How it plays

- **Aim** by turning your body (or just the badge) about 30 degrees either way.
  Or, in options, by tilting the badge.
- **Hold Down** (right edge) to fire, and **press Up** to reload early. Overlays
  beside those two buttons show what they do, and the reload overlay fills as
  the reload goes. **Left and Right** switch weapons:
  - **LINT**: green, rapid fire, a 30-round magazine.
  - **REVIEW**: blue, heavy shots, 4 rounds.
  - **REVERT**: orange, a spread of 5 pellets, 3 blasts.
- **Reloading.** An empty magazine reloads by itself. Weapons you aren't
  holding slowly refill, a full magazine in about 6 s.
- **Match the colour.** The weapon matching a bot's colour does **2× damage**,
  and a kill with it scores **2× points**, with a white flash and a "MATCH"
  score. Each colour has its own identity:

  | Bot | Colour | Approach | Health | Matched kill |
  | --- | --- | --- | --- | --- |
  | Force-pusher | green | fastest, straight at you | 4 | 2 LINT hits |
  | node_modules | blue | slowest, straight, tanky | 18 | 3 REVIEW shots |
  | Hallucinator | orange | sways side to side, medium speed | 2 | 1 REVERT pellet |
  | Mega-agent | pink | slow boss, every third release | 30 | weak to nothing |

- **Pickups** bob up and down where a destroyed bot was. Shoot one within 4.5 s
  to collect it:
  - **Pizza**: +25 health.
  - **Coffee**: overdrive, double fire rate for 5 s.
  - **Cache Hit**: a shield back. It only drops once you have shields.
  - **rm -rf**: deletes every bot on the field, except the Mega-agent, which
    had backups.
- **Upgrades.** Each wave is a "release" (v0.1.0 and up). When one ships, the
  game freezes on three upgrade cards. Left and Right choose, and enter takes
  it.
- **Shields** absorb a bot completely. Without one, a bot that reaches you
  merges into main and costs you health.

## Upgrades

Every run starts from `BASE_STATS`. Each upgrade changes one stat, and its card
shows the stat now and after:

| Upgrade | Flavour | Effect |
| --- | --- | --- |
| Larger Runners | Your CI finally got the good machines. | +15% fire rate |
| CODEOWNERS | Nothing gets through without your say-so. | +1 damage on every hit |
| Copilot | Fight AI with AI. Seems only fair. | +25% damage |
| Bug Bounty | Bots drop loot now. Finders keepers! | +8% pickup chance (from 10%) |
| Automated PR Review | Reloads approve themselves. LGTM! | 15% faster reloads (from 1.2 s) |
| Branch Protection | main has been hitting the gym. | +20 max health (from 100), and heals 20 |
| Two-Factor Auth | Bots never have their phone on them. | +1 recharging shield, up to 3 |

Damage per pellet is `(weapon damage + flat) × (1 + increased) × 2 if matched`.
A shield comes back 8 s after a bot last reached you, then one every 8 s.

## Screens and options

- **The splash** shows the studio's logo: "internet", "creature" and "studios"
  rise in one at a time, then the pink `:3` hops in.
- **The title** points at the buttons. A glowing copy of the printed `↩` and an
  arrow mark enter (start), and a gear marks Up (options). The positions come
  from [docs/button_positions.json](../../docs/button_positions.json).
- **Options**, from the title or the pause menu, are saved on the badge:
  - **Firing:** hold Down (the default) or automatic.
  - **Turning:** rotate (the default: turn your body, using the gyro) or tilt
    (tip the badge left or right to turn that way, and hold it level to stop).
    Both cover the same ±30°.
- **Pause:** enter pauses, with Resume, Re-centre aim, Options, Restart and
  Quit. Up and Down choose, and enter confirms. Resume is the default, so enter
  twice is pause and unpause. Back exits at any time.
- **Saved state:** the best score and options are kept in
  `/state/repo_defender.json`.

The app is [`badge/apps/repo_defender/__init__.py`](../../badge/apps/repo_defender/__init__.py).
It's drawn entirely with rectangles, triangles, circles, lines and text, with
no image assets except the logo.

## How aiming works

- **Rotate** measures turning around "down". The accelerometer gives the
  direction of gravity, and the yaw rate is the gyro's reading along it, so it
  works however the badge is tilted in your hands. Two full turns measured 107
  and 110 raw units per degree per second (`GYRO_LSB_PER_DPS`). The game
  calibrates from the steadiest part of a one-second hold at the start, and
  keeps re-learning the gyro's zero point whenever the badge holds still.
  Turning past ±30° drags the centre along with you.
- **Tilt** reads the accelerometer's sideways component against how the badge
  was held at the start. Past a small dead zone, turning speeds up to 70°/s.
- **One projection for everything.** The grid, skyline, bots, pickups, shots
  and hit tests all go through the same `View`, so `YAW_SIGN` is the only
  direction choice. An early version drew the world rotated one way and fired
  shots the other.

Tuning knobs, at the top of the app:

- **Aim:** `YAW_LIMIT`, `YAW_SIGN`, `HFOV`, `TILT_*`.
- **Pace:** `WAVE_SECONDS`, and the spawn mix and curve in `Game.spawn` and
  `Game.update`.
- **Bots and weapons:** the `BOTS` and `WEAPONS` tables, `MATCH` and
  `HOLSTER_REFILL`.
- **Progression:** `BASE_STATS`, `UPGRADES`, `PICKUPS`, and the shield and
  pickup timings.

## Testing the rules on the badge

[`selftest.py`](selftest.py) runs the game's own code on the badge with its
run loop swapped for 18 checks. They cover:

- firing only on the trigger, reload timing, early reloads and holster refills
- each bot's matched kill and the double points
- every pickup, including rm -rf sparing the boss
- shields absorbing a bot and recharging
- the upgrade offers
- which way tilt turns
- every screen drawing

Then it measures the frame rate of a busy scene. All 18 checks pass. The busy
scene, with 12 bots, 4 pickups and REVERT firing automatically, runs at about
25 fps; normal play has far fewer bots on screen. How to run it is at the top
of the file.

## The menu icon

A shield guarding a little commit graph. To rebuild it:

```bash
python3 examples/repo-defender/make_icon.py examples/repo-defender/icon.json preview.png
python3 tools/menu_icon.py repo_defender examples/repo-defender/icon.json
python3 tools/deploy.py badge/apps/menu
```
