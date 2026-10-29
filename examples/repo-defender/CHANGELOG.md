# Repo Defender changelog

Versions follow [semantic versioning](https://semver.org/). While the major
number is 0, anything can change between versions:

- **New features or content** bump the middle number (0.2.0).
- **Fixes and tuning** bump the last number (0.1.1).

Each release is tagged `repo-defender-v<version>`, because this repo holds
several apps.

## 0.2.0: stats, upgrades and new enemies

- **New enemies with their own behaviours**, in place of colour-coded robots:
  - bugs (fast, straight)
  - node_modules boxes (slow tanks that dent)
  - hallucinations (swaying ghosts)
  - a rogue agent boss with a terminal for a face
- **Weapons fire by themselves.** What sets them apart is the job each suits:
  REVIEW now pierces through everything in a line, and REVERT's spread handles
  swaying enemies. Colour matching is gone.
- **Magazines and reloading.** Down reloads early, an empty magazine reloads
  by itself, and weapons you aren't holding slowly refill. An overlay beside
  Down shows the reload filling.
- **Up is settings on every screen**, separate from pause:
  - turning (rotate your body, or tilt the badge)
  - Reset origin
- **Pause** is Resume, Restart and Quit.
- **Player stats** that scale every weapon:
  - fire rate
  - flat damage
  - increased damage
  - pickup chance
  - reload time
  - max health
  - 0–3 shields
- **An upgrade pick at every release.** The game freezes on three cards with
  flavour text, each showing the stat now and after:
  - Larger Runners
  - CODEOWNERS
  - Copilot
  - Bug Bounty
  - Automated PR Review
  - Branch Protection
  - Two-Factor Auth
- **Shields** stop an enemy completely, and recharge 8 s after one last
  reached you.
- **Pickups** bob up and down where a destroyed enemy was. Shoot one before it
  fades to collect it:
  - pizza (health)
  - coffee (overdrive)
  - Cache Hit (a shield back)
  - rm -rf (deletes everything, bar the boss)
- **The title's rules sit higher**, clear of the version.
- **An on-badge self-test** of the rules (`selftest.py`).

## 0.1.0: first playable

- **Aim by turning.** Turn your body, or just the badge, about 30 degrees either
  way, so it plays seated. The gyro tracks you around whichever way is down,
  and keeps re-learning its zero point while you hold steady.
- **Three weapons** fire by themselves. Left and Right switch between them:
  - **LINT**: rapid fire.
  - **REVIEW**: heavy shots.
  - **REVERT**: a short-range spread.
- **Four bots**, each tinted the colour of the weapon it's weak to:
  - spam bots
  - hallucinators, which weave
  - force-pushers, which charge
  - mega-agents, which turn up every third wave
- **Waves ship as "releases"** (v0.1.0, v0.2.0, ...) and get harder. A bot that
  reaches you merges into main with a quip and costs you integrity.
- **A splash screen** with the studio's logo, a line at a time, then the pink
  `:3`.
- **The title and game-over screens** point at the enter button with a glowing
  copy of its printed `↩` label.
- **Pause:** enter pauses, with Resume, Restart and Quit.
- **Best score** is saved on the badge, and the game has its own shield icon in
  the menu.
