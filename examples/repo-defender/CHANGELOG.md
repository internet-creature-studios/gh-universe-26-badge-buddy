# Repo Defender changelog

Versions follow [semantic versioning](https://semver.org/). While the major
number is 0, anything can change between versions:

- **New features or content** bump the middle number (0.2.0).
- **Fixes and tuning** bump the last number (0.1.1).

Each release is tagged `repo-defender-v<version>`, because this repo holds
several apps.

## 0.2.0: stats, upgrades and manual fire

- **You fire now.** Hold Down to fire, and press Up to reload early. Overlays
  beside those buttons show what they do. Automatic fire is an option.
- **Magazines and reloading.** An empty magazine reloads by itself, and weapons
  you aren't holding slowly refill.
- **Player stats** that scale every weapon:
  - fire rate
  - flat damage
  - increased damage
  - pickup chance
  - reload time
  - max health
  - 0–3 shields
- **An upgrade pick at every release.** The game freezes on three cards with
  flavour text, each showing the stat now and after, with arrows pointing at
  Left, Right and enter:
  - Larger Runners
  - CODEOWNERS
  - Copilot
  - Bug Bounty
  - Automated PR Review
  - Branch Protection
  - Two-Factor Auth
- **Each bot colour has an identity:**
  - Green force-pushers are fastest, straight at you, with medium health.
  - Blue node_modules are slow tanks, three matched REVIEW shots.
  - Orange hallucinators sway side to side, with low health.
- **Matching your weapon to a bot's colour now does 2× damage and scores 2×
  points**, with a white flash and a "MATCH" score. It used to do 3× damage
  that hardly ever mattered, because REVIEW destroyed nearly every bot in one
  hit regardless.
- **Shields** absorb a bot completely, and recharge 8 s after you were last
  reached.
- **Pickups** bob up and down where a destroyed bot was. Shoot one before it
  fades to collect it:
  - pizza (health)
  - coffee (overdrive)
  - Cache Hit (a shield back)
  - rm -rf (deletes every bot, bar the boss)
- **Options**, saved on the badge: firing (hold Down, or automatic) and
  turning (rotate your body, or tilt the badge).
- **The pause menu** adds Re-centre aim and Options.
- **The title's rules sit higher**, clear of the version, and point at the
  options button.
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
