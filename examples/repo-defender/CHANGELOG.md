# Repo Defender changelog

Versions follow [semantic versioning](https://semver.org/). While the major
number is 0, anything can change between versions:

- **New features or content** bump the middle number (0.2.0).
- **Fixes and tuning** bump the last number (0.1.1).

Each release is tagged `repo-defender-v<version>`, because this repo holds
several apps.

## 0.2.0: stats and upgrades

- **Player stats** that scale every weapon:
  - fire rate
  - flat damage
  - increased damage
  - pickup chance
  - reload time
  - max health
  - 0–3 shields
- **An upgrade pick at every release.** The game freezes on three cards, each
  showing the stat now and after, with arrows pointing at Left, Right and
  enter:
  - Caffeinated CI
  - Strong Typing
  - 10x Engineer
  - Bug Bounty
  - Hot Reload
  - Branch Protection
  - Two-Factor Auth
- **Magazines and reloading.** All weapons reload at once, so switching away
  from an empty one keeps you firing.
- **Shields** absorb a bot completely, and recharge 8 s after you were last
  reached.
- **Pickups** a destroyed bot sometimes leaves: Hotfix, Cache Hit and
  Overclock. Shoot one before it fades to collect it.
- **Matching your weapon to a bot's colour now does 2× damage and scores 2×
  points**, with a white flash and a "MATCH" score. It used to do 3× damage
  that hardly ever mattered, because REVIEW destroyed nearly every bot in one
  hit regardless.
- **Rebalanced.** REVIEW does 3 damage, not 4. Hallucinators have 6 HP,
  force-pushers 8 and mega-agents 30.
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
