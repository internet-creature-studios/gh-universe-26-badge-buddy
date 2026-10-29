# Repo Defender changelog

Versions follow [semantic versioning](https://semver.org/). While the major
number is 0, anything can change between versions:

- **New features or content** bump the middle number (0.2.0).
- **Fixes and tuning** bump the last number (0.1.1).

Each release is tagged `repo-defender-v<version>`, because this repo holds
several apps.

## 0.3.0: neon creatures, + cards, Friday Deploy, and pickups you can see

- **Neon wireframe bots**, from Grok's designs in `design/enemies`, in place of
  the flat heads. Each keeps its behaviour:
  - the bug is a six-legged mite, scuttling
  - node_modules is a domed pillbug that sheds armour as you hit it
  - the hallucination is a jellyfish that turns as it sways
  - the rogue agent is a horned dragon, wings beating

  They're native vector shapes, and small ones are drawn from images baked at
  launch (see the README). Health bars only show once a bot is hurt. A close
  bot flashes white when hit, and a distant one pops.
- **Fixed: trails along the horizon.** The sky stopped a row short of the
  floor, so anything crossing the horizon left streaks there.

- **+ cards.** Any card offered has a 15% chance of being its + version, in a
  gold frame, which does twice as much:
  - stat cards double their increase
  - a weapon you have gets boosted twice
  - a new weapon arrives already boosted once
  - Two-Factor Auth+ adds a shield and fully heals you
- **Friday Deploy**, a new card: +10% score, but bots get +10% health and
  speed (+20% each for Friday Deploy+). It stacks.
- **Pickups land off to one side** of where you're aiming, 12° to 19° away and
  within reach, instead of where the bot was. Your next shot no longer takes
  them before you've seen them.
- **The upgrade screen marks its buttons** with a glowing, bobbing `<`, `>` and
  ✓ right over Left, Right and enter, in place of the arrows and `↩`.
- **The self-test** grows to 36 checks, including that every card's text
  fits in the badge's own fonts, that every bot model builds, and that the
  world covers every row of the screen.

## 0.2.0: stats, upgrades, weapon cards and new bots

- **Bots with their own behaviours**, in place of colour-coded ones. They're
  all evil heads with red eyes, and each kind has a feature or two of its own:
  - bugs (fast, straight): two antennae, angry brows and fangs
  - node_modules (slow tanks): a wide riveted head with one long eye slit,
    denting as you hit it
  - hallucinations (swaying): a flickering dome with mismatched eyes and a "?"
  - the rogue agent (a boss): horns, three eyes, and a terminal for a mouth
- **Weapons fire by themselves.** What sets them apart is the job each suits:
  REVIEW now pierces through everything in a line, and REVERT's spread handles
  swaying bots. Colour matching is gone.
- **You start with LINT, and win the other weapons from cards.** Each weapon
  has a card. Without the weapon, it gives it to you. With it, it improves it:
  - LINT: More Lint Rules, +10 rounds per magazine
  - REVIEW: Code Review unlocks it, then Senior Reviewer adds 2 damage a shot
  - REVERT: git revert unlocks it, then Revert Harder adds a pellet to the
    spread

  Left and Right only switch between the weapons you have.
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
- **Shields** stop a bot completely, and recharge 8 s after one last
  reached you.
- **Pickups** bob up and down where a destroyed bot was. Shoot one before it
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
