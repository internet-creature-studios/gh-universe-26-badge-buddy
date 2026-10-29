"""Repo Defender: evil bots are coming for your main branch.

Turn your body (or tilt the badge, in settings) to aim, about 30 degrees
either way, so it plays seated. Your weapon fires by itself and Down reloads
early. You start with LINT; the other weapons come as upgrade cards, and
once you have a weapon its card improves it. Left and Right switch between
the weapons you have, and the ones you aren't holding slowly refill. Each
kind of bot comes at you its own way: bugs rush straight in, node_modules
hauls in slow and heavy, hallucinations sway side to side, and now and then
the rogue agent lumbers in. Destroyed bots sometimes drop a bobbing pickup
off to one side: shoot it to collect it. After each wave (a "release") you
pick one of three upgrade cards, and now and then one is a stronger + card. A bot that reaches you takes a shield if one is charged, or
merges itself into main and costs you health, and at zero main is theirs.

It opens on the studio's logo. Up opens settings from any screen (turning,
and resetting where straight ahead is), and Up again closes them. Enter
starts, and in a game pauses: Down picks Resume, Restart or Quit, and enter
confirms, so enter twice is pause and unpause. Back or Home exits. The best
score and the settings are kept in /state/repo_defender.json.
"""

import json
import math
import random
import time

# The game's own version (see examples/repo-defender/CHANGELOG.md), not the
# in-game "releases" each wave calls itself.
VERSION = "0.3.0"

# --- Aim -------------------------------------------------------------------

# Raw gyro units per degree a second. Two full turns, holding the badge as
# you play, measured 107 and 110 (the gyro's +-250 degree/s setting is 114).
GYRO_LSB_PER_DPS = 110.0
# A left turn reads positive around the accelerometer's "down", and aim
# (positive to the right) should follow it left: so -1. Everything (grid,
# skyline, bots, shots, hits) goes through the one View, so flipping this
# mirrors them all together.
YAW_SIGN = -1
# How far either way you can aim. Turning further drags the centre along,
# which also soaks up gyro drift.
YAW_LIMIT = 30.0
# The gyro's zero point wanders, and held in a hand it's never quite still.
# Any stretch of STILL_FRAMES with less spread than this (degrees a second)
# on every axis counts as still, and its average nudges the zero point.
STILL_SPREAD = 0.5
STILL_FRAMES = 12
# Tilt turning: tip the badge left or right to turn that way, hold it as it
# was at the start to stop. Past the dead zone (how far it's tipped, as the
# sine of the angle), turning speeds up to TILT_DPS at a tip of TILT_FULL.
# Tipping the right edge down raises the accelerometer's x reading (found in
# play: the first guess was mirrored), so TILT_SIGN makes that a right turn.
TILT_DPS = 70.0
TILT_DEADZONE = 0.08
TILT_FULL = 0.5
TILT_SIGN = -1

# --- View ------------------------------------------------------------------

WIDTH, HEIGHT = 320, 240
HFOV = 50.0
FOCAL = (WIDTH / 2) / math.tan(math.radians(HFOV / 2))
HORIZON = 92
EYE = 1.0  # camera height, in world units
REACH = 2.6  # a bot this close has reached you
SPAWN_DISTANCE = 34.0
SPAWN_ARC = 28.0  # bots appear within this many degrees of straight ahead

# --- Weapons and bots ------------------------------------------------------

# Weapons fire by themselves. rate: shots a second. damage: per pellet.
# magazine: shots before it reloads (a REVERT blast is one shot). gap:
# degrees between pellets. radius: how wide a shot hits. pierce: carries on
# through everything in its path. Cards change damage, magazine and pellets
# for the run.
WEAPONS = [
    dict(name="LINT", rgb=(90, 255, 140), rate=7.0, damage=1, pellets=1, gap=0.0, speed=40.0, reach=34.0,
         radius=0.25, magazine=60, pierce=False),
    dict(name="REVIEW", rgb=(100, 170, 255), rate=1.6, damage=5, pellets=1, gap=0.0, speed=32.0, reach=34.0,
         radius=0.5, magazine=8, pierce=True),
    dict(name="REVERT", rgb=(255, 160, 60), rate=1.3, damage=1, pellets=5, gap=3.5, speed=36.0, reach=14.0,
         radius=0.3, magazine=6, pierce=False),
]
# A weapon you aren't holding refills itself: a full magazine in this many
# reload times.
HOLSTER_REFILL = 5.0

# Bots: neon wireframe creatures (see "Bot models" below), each kind with its
# own way of coming at you. hit: health lost on reaching you. weave: degrees
# it sways either side. height: where its middle floats. rgb: its neon.
BOTS = {
    "bug": dict(name="A bug", hp=3, speed=4.6, weave=0.0, size=0.32, height=0.5, points=20, hit=10,
                quip="made it into prod", rgb=(244, 255, 58)),
    "node_modules": dict(name="node_modules", hp=10, speed=1.5, weave=0.0, size=0.55, height=0.6, points=50, hit=20,
                         quip="installed 40,000 packages into main", rgb=(46, 246, 255)),
    "hallucination": dict(name="A hallucination", hp=2, speed=2.6, weave=11.0, size=0.36, height=0.85, points=15, hit=8,
                          quip="added a package that doesn't exist", rgb=(255, 61, 242)),
    "agent": dict(name="The rogue agent", hp=30, speed=1.3, weave=4.0, size=0.85, height=0.95, points=150, hit=35,
                  quip="rewrote the whole repo overnight", rgb=(255, 51, 85)),
}
# Each bot is drawn as a bright core line over a wider, dimmer glow, these
# many pixels wide whatever its size, so each model is built ahead at a
# ladder of radii MODEL_STEP apart (MODEL_SIZES, px) and scaled to the
# nearest. Anything smaller than the first is drawn as a dot. A shape costs
# about the same to draw however small, so the first SPRITE_SIZES are also
# drawn once into images, which cost far less to scale onto the screen.
NEON_CORE = 1.3
NEON_GLOW = 3.6
GLOW_DIM = 0.35
MODEL_STEP = 1.5
MODEL_SIZES = tuple(5.0 * MODEL_STEP ** i for i in range(8))
SPRITE_SIZES = 5

# --- Upgrades ----------------------------------------------------------------

# Where every run starts; stat cards change these.
BASE_STATS = dict(
    fire_rate=1.0,  # times each weapon's own rate
    flat_damage=0,  # added to every pellet
    damage_bonus=0.0,  # increased damage: 0.25 is +25%
    pickup_chance=0.10,  # chance a destroyed bot leaves a pickup
    reload=1.2,  # seconds to refill a magazine
    max_health=100,
    shields=0,  # shield slots
    risk=0.0,  # Friday Deploy: 0.1 is +10% score, and bots with 10% more health and speed
)
MAX_SHIELDS = 3
# Seconds after a bot last reached you before a shield comes back, and
# between each one after that.
SHIELD_RECHARGE = 8.0

# Any card offered has this chance of being its + version, which does twice
# as much (effect_plus says what).
PLUS_CHANCE = 0.15

# Stat cards. step is what one pick adds, or for reload, how much quicker it
# makes them. Two-Factor Auth+ adds one shield like the plain card, and
# fully heals you as well.
UPGRADES = [
    dict(stat="fire_rate", name="Larger Runners", flavor="Your CI finally got the good machines.",
         effect="+15% fire rate", effect_plus="+30% fire rate", step=0.15),
    dict(stat="flat_damage", name="CODEOWNERS", flavor="Nothing gets through without your say-so.",
         effect="+1 damage on every hit", effect_plus="+2 damage on every hit", step=1),
    dict(stat="damage_bonus", name="Copilot", flavor="Fight AI with AI. Seems only fair.",
         effect="+25% damage", effect_plus="+50% damage", step=0.25),
    dict(stat="pickup_chance", name="Bug Bounty", flavor="Bots drop loot now. Finders keepers!",
         effect="+8% pickup chance", effect_plus="+16% pickup chance", step=0.08),
    dict(stat="reload", name="Automated PR Review", flavor="Reloads approve themselves. LGTM!",
         effect="15% faster reloads", effect_plus="30% faster reloads", step=0.15),
    dict(stat="max_health", name="Branch Protection", flavor="main has been hitting the gym.",
         effect="+20 max health, and heals 20", effect_plus="+40 max health, and heals 40", step=20),
    dict(stat="shields", name="Two-Factor Auth", flavor="Bots never have their phone on them.",
         effect="+1 recharging shield", effect_plus="+1 recharging shield, and a full heal", step=1),
    dict(stat="risk", name="Friday Deploy", flavor="What could possibly go wrong?",
         effect="+10% score, but bots get +10% health and speed",
         effect_plus="+20% score, but bots get +20% health and speed", step=0.10),
]

# Weapon cards, rolled alongside. Without the weapon, its card gives it to
# you; with it, the card improves it: boost is what it adds step to. A + card
# gives you the weapon already improved once, or improves it twice.
WEAPON_CARDS = [
    dict(weapon=0, boost="magazine", step=10, name="More Lint Rules",
         flavor="Your linter has opinions now. So many opinions.", effect="+10 rounds per LINT magazine",
         effect_plus="+20 rounds per LINT magazine"),
    dict(weapon=1, boost="damage", step=2, name="Senior Reviewer",
         flavor="Leaves very, very thorough comments.", effect="+2 damage per REVIEW shot",
         effect_plus="+4 damage per REVIEW shot",
         unlock="Code Review", unlock_flavor="A second pair of eyes that goes right through things.",
         unlock_effect="New weapon: REVIEW, shots that pierce",
         unlock_effect_plus="New weapon: REVIEW, piercing shots, +2 damage"),
    dict(weapon=2, boost="pellets", step=1, name="Revert Harder",
         flavor="Undo even more of whatever's in front of you.", effect="+1 pellet in REVERT's spread",
         effect_plus="+2 pellets in REVERT's spread",
         unlock="git revert", unlock_flavor="Undo everything in front of you, all at once.",
         unlock_effect="New weapon: REVERT, a wide spread",
         unlock_effect_plus="New weapon: REVERT, a wide spread, +1 pellet"),
]

# Destroyed bots sometimes leave one bobbing where they were. Shoot it
# before it fades to collect it. weight: how often it's the one dropped.
PICKUPS = {
    "pizza": dict(name="PIZZA", rgb=(255, 200, 80), weight=35),  # heals
    "coffee": dict(name="COFFEE", rgb=(200, 140, 90), weight=35),  # overdrive: full ammo that lasts, faster fire
    "cache": dict(name="CACHE HIT", rgb=(120, 200, 255), weight=20),  # a shield back
    "rmrf": dict(name="rm -rf", rgb=(255, 70, 90), weight=10),  # deletes every bot
}
PICKUP_SECONDS = 4.5
PICKUP_SIZE = 0.4
# A pickup lands this many degrees to one side of where you're aiming, and
# this far away, so you see it before you shoot it.
PICKUP_OFFSET = (12.0, 19.0)
PICKUP_DISTANCE = (7.0, 13.0)
PIZZA_HEAL = 25
OVERDRIVE_SECONDS = 5.0

# --- Splash ----------------------------------------------------------------

# The studio's logo, a line at a time, then the pink :3. Each piece is
# (x, y, w, h) in assets/studio_logo.png and the second it appears.
LOGO_AT = (44, 46)
LOGO_PIECES = [
    ((0, 0, 189, 41), 0.30),  # internet
    ((0, 58, 204, 36), 0.75),  # creature
    ((0, 107, 177, 41), 1.20),  # studios
    ((190, 107, 42, 41), 1.85),  # :3
]
SPLASH_SECONDS = 3.4

PAUSE_CHOICES = ["Resume", "Restart", "Quit"]
DEFAULT_SETTINGS = dict(turning="rotate")

# --- The buttons -------------------------------------------------------------

# Where the buttons sit beside the screen, from tools/locate_buttons.py (see
# docs/button_positions.json): Left, Right and enter below the bottom edge at
# these x, Up and Down beside the right edge at these y.
LEFT_X = 59
RIGHT_X = 163
ENTER_X = 255
UP_Y = 72
DOWN_Y = 167


def polyline(*corners):
    """Points a pixel apart along straight strokes through corners."""
    points = []
    for (x0, y0), (x1, y1) in zip(corners, corners[1:]):
        n = max(abs(x1 - x0), abs(y1 - y0))
        points += [(x0 + (x1 - x0) * k / n, y0 + (y1 - y0) * k / n) for k in range(n)]
    return points + [corners[-1]]


# What the screens show right over Left, Right and enter (a checkmark: it
# takes what's chosen): points around the button's x, up from just above the
# bottom edge.
BUTTON_MARKS = {
    "left": polyline((4, -18), (-5, -9), (4, 0)),
    "right": polyline((-4, -18), (5, -9), (-4, 0)),
    "check": polyline((-9, -8), (-3, -2), (9, -16)),
}
# Reload's icon: most of a circle, ending in an arrowhead.
RELOAD_ARC = [(5.5 * math.cos(math.radians(a)), 5.5 * math.sin(math.radians(a))) for a in range(40, 360, 20)]

WAVE_SECONDS = 25.0
GAME_OVER_LINES = [
    "The bots renamed it skynet-final-v2.",
    "main now has 4,096 open PRs.",
    "Your README is now a poem about bots.",
    "CI passes. Nothing else does.",
]
STATE_PATH = "/state/repo_defender.json"


def button(name):
    # Badgeware's button names resolve like builtins but aren't listed in
    # builtins or globals, so look them up by evaluating the name.
    try:
        return eval(name)
    except NameError:
        return None


BACK = button("BUTTON_BACK")
HOME = button("BUTTON_HOME")
LEFT = button("BUTTON_LEFT")
RIGHT = button("BUTTON_RIGHT")
UP = button("BUTTON_UP")
DOWN = button("BUTTON_DOWN")
SELECT = button("BUTTON_SELECT")


def pressed(b):
    return b is not None and badge.pressed(b)


def pen(rgb, alpha=255):
    return color.rgb(rgb[0], rgb[1], rgb[2], alpha)


def dim(rgb, k):
    return (int(rgb[0] * k), int(rgb[1] * k), int(rgb[2] * k))


SKY = [pen((8, 10, 22)), pen((12, 16, 36)), pen((18, 24, 52))]
FLOOR = pen((6, 10, 14))
GRID = pen((30, 90, 70))
GRID_FAR = pen((18, 52, 44))
TOWER = pen((22, 28, 58))
WINDOW = pen((70, 90, 160))
WHITE = pen((255, 255, 255))
TEXT = pen((200, 230, 255))
MUTED = pen((110, 130, 160))
DANGER = pen((255, 70, 90))
BLACK = pen((0, 0, 0))
TRACK = pen((30, 36, 60))
PANEL = pen((0, 0, 0), 170)
WEAPON_PENS = [pen(w["rgb"]) for w in WEAPONS]
WEAPON_DIM = [pen(dim(w["rgb"], 0.45)) for w in WEAPONS]
AIM_LINE = [pen(dim(w["rgb"], 0.25)) for w in WEAPONS]
BOT_PENS = {kind: pen(b["rgb"]) for kind, b in BOTS.items()}
BOT_GLOW = {kind: pen(dim(b["rgb"], GLOW_DIM)) for kind, b in BOTS.items()}
PICKUP_PENS = {kind: pen(p["rgb"]) for kind, p in PICKUPS.items()}
PLUS_PEN = pen((255, 205, 70))
PLUS_DIM = pen((125, 98, 35))
SHIELD_PEN = pen(PICKUPS["cache"]["rgb"])
SHIELD_DIM = pen(dim(PICKUPS["cache"]["rgb"], 0.35))
SPLASH_BACKGROUND = pen((238, 245, 247))  # the studio site's horizon

# Distant server towers on the horizon: (azimuth, width in degrees, height px).
# A fixed seed keeps the skyline the same every launch; the game reseeds.
random.seed(7)
TOWERS = []
az = -70.0
while az < 70.0:
    width = random.uniform(2.0, 5.5)
    TOWERS.append((az, width, random.randint(6, 26)))
    az += width + random.uniform(0.5, 3.0)
random.seed(time.ticks_us())


def stats(samples):
    """Per-axis mean of gyro samples, and the largest per-axis spread."""
    n = len(samples)
    mean = [sum(s[i] for s in samples) / n for i in range(3)]
    spread = max(math.sqrt(sum((s[i] - mean[i]) ** 2 for s in samples) / n) for i in range(3))
    return mean, spread


def wrap(text, width):
    """text split into lines no wider than width in the current font."""
    lines, line = [], ""
    for word in text.split(" "):
        trial = word if not line else line + " " + word
        if line and screen.measure_text(trial)[0] > width:
            lines.append(line)
            line = word
        else:
            line = trial
    lines.append(line)
    return lines


WIDTHS = {}


def text_width(text):
    """Width of text in font.salty, measured once: measuring every frame adds up."""
    w = WIDTHS.get(text)
    if w is None:
        screen.font = font.salty
        w = WIDTHS[text] = screen.measure_text(text)[0]
        if len(WIDTHS) > 200:
            WIDTHS.clear()
    return w


def centred(text, y, left=0, width=WIDTH):
    tw, _ = screen.measure_text(text)
    screen.text(text, left + (width - tw) // 2, y)


def stepped(upgrade, value, plus=False):
    """A stat after taking its card. A + card steps twice as far, except for
    shields, where it heals you instead."""
    step = upgrade["step"] * (2 if plus and upgrade["stat"] != "shields" else 1)
    return value * (1 - step) if upgrade["stat"] == "reload" else value + step


def stat_text(stat, value):
    if stat in ("fire_rate", "pickup_chance"):
        return "%d%%" % round(value * 100)
    if stat in ("damage_bonus", "risk"):
        return "+%d%%" % round(value * 100)
    if stat == "flat_damage":
        return "+%d" % value
    if stat == "reload":
        return "%.2fs" % value
    return "%d" % value


# --- Bot models ----------------------------------------------------------------

# Neon wireframe creatures, from the designs in design/enemies: 3D models in
# units where the body fits a radius-1 sphere (the bot's size scales it), with
# y up and -z toward you. Each takes a frame number, for its animation or, for
# node_modules, how battered it is.


class Wireframe:
    """A 3D line model: points, the edges between them, and its eyes."""

    def __init__(self):
        self.points = []
        self.edges = []
        self.eyes = []

    def strip(self, points, closed=True, joined=True):
        """Adds points, each joined to the next unless joined is False, and
        returns the index of the first."""
        start = len(self.points)
        self.points += points
        if joined:
            n = len(points)
            for i in range(n if closed else n - 1):
                self.edges.append((start + i, start + (i + 1) % n))
        return start

    def rungs(self, a, b, n):
        """Joins each of the n points from a to its match from b."""
        for i in range(n):
            self.edges.append((a + i, b + i))

    def fan(self, a, n, apex):
        """Joins each of the n points from a to one more point."""
        top = self.strip([apex], joined=False)
        for i in range(n):
            self.edges.append((a + i, top))

    def line(self, p, q):
        self.strip([p, q], closed=False)


def ring(cx, cy, cz, rx, n, rz=None, ry=None):
    """n points around (cx, cy, cz): a level ring rx across and rz deep, or
    with ry, an upright one facing you, ry tall."""
    points = []
    for i in range(n):
        a = 2 * math.pi * i / n
        if ry is None:
            points.append((cx + rx * math.cos(a), cy, cz + (rz or rx) * math.sin(a)))
        else:
            points.append((cx + rx * math.cos(a), cy + ry * math.sin(a), cz))
    return points


def skitter(frame):
    """The bug: a six-legged mite. Each frame lifts the other three legs."""
    m = Wireframe()
    # Its body: two stacked octagons and a peak.
    low = m.strip(ring(0, 0.05, 0, 0.7, 8, rz=0.8))
    high = m.strip(ring(0, 0.45, 0, 0.45, 8))
    m.rungs(low, high, 8)
    m.fan(high, 8, (0, 0.65, 0))
    # A wedge of a head, and mandibles.
    head = m.strip([(-0.25, 0.15, -0.55), (0.25, 0.15, -0.55), (0, 0.0, -0.85)])
    m.edges += [(low + 6, head), (low + 6, head + 1), (low + 5, head), (low + 7, head + 1)]
    m.line((-0.1, 0.0, -0.85), (-0.25, -0.15, -1.0))
    m.line((0.1, 0.0, -0.85), (0.25, -0.15, -1.0))
    # Six jointed legs, scuttling.
    for k, z in enumerate((-0.35, 0, 0.35)):
        for side in (-1, 1):
            lift = 0.15 if (k + (1 if side > 0 else 0) + frame) % 2 else 0.0
            knee = (side * 0.95, 0.45 + lift, z * 1.4)
            m.line((side * 0.5, 0.1, z), knee)
            m.line(knee, (side * 1.25, -0.5 + lift, z * 1.8 - lift))
    m.eyes = [(-0.12, 0.18, -0.6), (0.12, 0.18, -0.6)]
    return m


def hoardshell(frame):
    """node_modules: a domed, plated pillbug. frame (0 to 3) is how many
    layers of its armour have dropped off: the skirt, the cap and top ring,
    then the next ring."""
    m = Wireframe()
    rings = 4 - max(0, frame - 1)  # the dome's rings still on
    rows = []
    for j, ph in enumerate((0, 0.35, 0.7, 1.0)):
        rows.append(m.strip(ring(0, -0.3 + 0.75 * math.sin(ph * 1.35), 0, math.cos(ph * 1.2), 10), joined=j < rings))
    for j in range(rings - 1):
        m.rungs(rows[j], rows[j + 1], 10)
    if frame < 2:
        m.fan(rows[3], 10, (0, 0.55, 0))
    skirt = m.strip(ring(0, -0.45, 0, 1.05, 10), joined=frame < 1)
    if frame < 1:
        m.rungs(rows[0], skirt, 10)
    head = m.strip([(-0.3, -0.4, -0.95), (0.3, -0.4, -0.95), (0.3, 0.0, -1.0), (-0.3, 0.0, -1.0)])
    m.edges += [(head, rows[0] + 7), (head + 1, rows[0] + 8), (head + 2, rows[0] + 8), (head + 3, rows[0] + 7)]
    for i in (1, 3, 6, 8):  # stubby legs
        x, y, z = m.points[skirt + i]
        m.line((x, y, z), (x * 1.05, -0.8, z * 1.05))
    m.eyes = [(-0.15, -0.2, -1.0), (0.15, -0.2, -1.0)]
    return m


def mirage(frame):
    """The hallucination: a drifting jellyfish with mismatched eyes. Each
    frame moves the ripple along its tentacles."""
    m = Wireframe()
    above = None
    for y, r in ((0.0, 0.85), (0.3, 0.75), (0.55, 0.5), (0.7, 0.2)):
        row = m.strip(ring(0, y, 0, r, 9))
        if above is not None:
            m.rungs(above, row, 9)
        above = row
    for i in range(0, 9, 2):
        a = 2 * math.pi * i / 9
        x0, z0 = 0.8 * math.cos(a), 0.8 * math.sin(a)
        m.strip([(x0 * (1 - 0.1 * k) + 0.15 * math.sin(k * 1.7 + i + frame * 2.1), -0.25 * k, z0 * (1 - 0.1 * k))
                 for k in range(5)], closed=False)
    m.eyes = [(-0.3, 0.3, -0.68), (0.22, 0.38, -0.62)]
    return m


def overmind(frame):
    """The rogue agent: a horned wireframe dragon, wings spread. Frame 1 is
    the down beat of its wings."""
    m = Wireframe()
    head = m.strip([(-0.22, 0.55, -0.35), (0.22, 0.55, -0.35), (0.15, 0.75, -0.25), (-0.15, 0.75, -0.25)])
    snout = m.strip([(-0.1, 0.5, -0.7), (0.1, 0.5, -0.7)], joined=False)
    jaw = m.strip([(0, 0.32, -0.62)], joined=False)
    m.edges += [(snout, snout + 1), (head, snout), (head + 1, snout + 1), (head + 3, snout), (head + 2, snout + 1),
                (head, jaw), (head + 1, jaw), (snout, jaw), (snout + 1, jaw)]
    m.line((-0.15, 0.75, -0.25), (-0.4, 1.1, 0.0))  # horns
    m.line((0.15, 0.75, -0.25), (0.4, 1.1, 0.0))
    neck = m.strip(ring(0, 0.35, -0.1, 0.18, 4, ry=0.15))
    m.edges += [(head, neck + 2), (head + 1, neck)]
    body = m.strip(ring(0, 0.1, 0.25, 0.32, 4, ry=0.26))
    m.rungs(neck, body, 4)
    tail = m.strip([(0, -0.15, 0.5), (0.3, -0.35, 0.8), (0.55, -0.45, 1.0), (0.75, -0.35, 1.1)], closed=False)
    m.edges.append((body + 3, tail))
    m.strip([(0.75, -0.35, 1.1), (0.9, -0.25, 1.05), (0.85, -0.5, 1.15)])  # the tail's spade
    beat = -0.3 * frame
    for side in (-1, 1):
        shoulder = (side * 0.3, 0.25, 0.15)
        elbow = (side * 0.8, 0.85 + beat * 0.7, 0.3)
        tip = (side * 1.45, 1.0 + beat, 0.4)
        fingers = ((side * 1.3, 0.2 + beat * 0.8, 0.45), (side * 0.85, -0.05 + beat * 0.5, 0.4))
        m.line(shoulder, elbow)
        m.line(elbow, tip)
        for finger in fingers:
            m.line(elbow, finger)
        m.strip([tip, fingers[0], fingers[1], (side * 0.3, 0.0, 0.3)], closed=False)
    m.eyes = [(-0.13, 0.65, -0.42), (0.13, 0.65, -0.42)]
    return m


def flatten(model, yaw, pitch=0.15):
    """The model as the game shows it: turned yaw radians, tipped pitch
    toward you, with a little perspective. Its points and eyes come back in
    units of the bot's radius, x right and y down."""
    cy, sy, cp, sp = math.cos(yaw), math.sin(yaw), math.cos(pitch), math.sin(pitch)

    def seen(p):
        x, y, z = p
        x, z = x * cy - z * sy, x * sy + z * cy
        y, z = y * cp - z * sp, y * sp + z * cp
        k = 4.0 / (4.0 + z)
        return (x * k, -y * k)

    return [seen(p) for p in model.points], model.edges, [seen(p) for p in model.eyes]


# Each kind's model, how many frames it has, and how far it's turned to show
# its depth: they face a little to the right, mirrored when on the right.
MODELS = {
    "bug": (skitter, 2, 0.5),
    "node_modules": (hoardshell, 4, 0.5),
    "hallucination": (mirage, 3, 0.5),
    "agent": (overmind, 2, 0.35),
}
FLAT = {kind: [flatten(build(f), yaw) for f in range(frames)] for kind, (build, frames, yaw) in MODELS.items()}


LOG_STEP = math.log(MODEL_STEP)
SIZE_ROUNDING = math.sqrt(MODEL_STEP)


def model_size(r):
    """The index of the MODEL_SIZES to draw something r px in radius with
    (the nearest, as a ratio), or None if it's smaller than them all."""
    r *= SIZE_ROUNDING
    if r < MODEL_SIZES[0]:
        return None
    return min(len(MODEL_SIZES) - 1, int(math.log(r / MODEL_SIZES[0]) / LOG_STEP))


def neon(points, edges, size):
    """A flattened model's glow and core lines, as two shapes whose lines
    are NEON_GLOW and NEON_CORE px wide when it's drawn size px in radius."""
    def lines(width):
        w = width / size
        return shape.combine([shape.line(points[a][0], points[a][1], points[b][0], points[b][1], w) for a, b in edges])
    return lines(NEON_GLOW), lines(NEON_CORE)


def bake(kind, points, eyes, glow, core, size, facing):
    """A model drawn into an image, antialiased, size px in radius and facing
    right (1) or left (-1). Returns the image and its left, top, width and
    height from the bot's middle, in units of the bot's radius, so it can be
    scaled to any radius."""
    pad = NEON_GLOW / size  # room for the glow
    xs = [facing * x for x, y in points]
    ys = [y for x, y in points]
    left, top = min(xs) - pad, min(ys) - pad
    w = int((max(xs) + pad - left) * size) + 2
    h = int((max(ys) + pad - top) * size) + 2
    img = image(w, h)
    img.antialias = image.X4
    img.fill_rule = image.NON_ZERO
    place = mat3().translate(-left * size, -top * size).scale(facing * size, size)
    glow.transform = place
    core.transform = place
    img.pen = BOT_GLOW[kind]
    img.shape(glow)
    img.pen = BOT_PENS[kind]
    img.shape(core)
    img.pen = WHITE
    for ex, ey in eyes:
        img.circle(int((facing * ex - left) * size), int((ey - top) * size), max(1, int(size * 0.07)))
    return img, left, top, w / size, h / size


# --- Pickup models -------------------------------------------------------------

# Low-poly coffee and pizza, from the designs in design/powerups: points in
# the same units as the bots, and triangles of them, each of a material. They
# are flat-shaded in three tones and baked into images, like distant bots,
# at two sizes (PICKUP_ART_SIZES, px) that the blit scales between.
MATERIALS = {
    "cup": (235, 225, 210), "sleeve": (200, 140, 90), "coffee": (110, 65, 35), "steam": (220, 230, 240),
    "crust": (190, 110, 50), "cheese": (255, 200, 80), "pepperoni": (210, 50, 50),
}
LIGHT = (-0.4, 0.75, -0.5)  # toward the light, unnormalised
PICKUP_ART_SIZES = (11.0, 18.0)


class Faces:
    """A low-poly model: points, and triangles of them, each with a material."""

    def __init__(self):
        self.points = []
        self.faces = []

    def point(self, x, y, z):
        self.points.append((x, y, z))
        return len(self.points) - 1

    def ring(self, cx, y, cz, r, n):
        return [self.point(cx + r * math.cos(2 * math.pi * i / n), y, cz + r * math.sin(2 * math.pi * i / n))
                for i in range(n)]

    def quad(self, a, b, c, d, material):
        self.faces += [(a, b, c, material), (a, c, d, material)]

    def band(self, lower, upper, material):
        """Quads joining two loops of points, all the way round."""
        n = len(lower)
        for i in range(n):
            j = (i + 1) % n
            self.quad(lower[i], lower[j], upper[j], upper[i], material)

    def fan(self, centre, loop, material):
        for i in range(len(loop)):
            self.faces.append((centre, loop[i], loop[(i + 1) % len(loop)], material))


def mug(frame):
    """Coffee: a tapered eight-sided cup with a sleeve and a handle. Each frame
    sways its three wisps of steam."""
    m = Faces()
    base = m.ring(0, -0.75, 0, 0.42, 8)
    low = m.ring(0, -0.25, 0, 0.5, 8)
    high = m.ring(0, 0.15, 0, 0.56, 8)
    rim = m.ring(0, 0.55, 0, 0.62, 8)
    m.fan(m.point(0, -0.75, 0), base[::-1], "cup")
    m.band(base, low, "cup")
    m.band(low, high, "sleeve")
    m.band(high, rim, "cup")
    m.fan(m.point(0, 0.48, 0), m.ring(0, 0.48, 0, 0.58, 8), "coffee")  # just below the rim
    # The handle: a square loop of boxes on the right.
    previous = None
    for x, y in ((0.55, 0.3), (0.9, 0.3), (0.95, -0.15), (0.55, -0.3)):
        box = [m.point(x, y + 0.07, -0.07), m.point(x, y + 0.07, 0.07), m.point(x, y - 0.07, 0.07),
               m.point(x, y - 0.07, -0.07)]
        if previous:
            m.band(previous, box, "cup")
        previous = box
    # Steam: three thin ribbons, narrowing as they rise.
    for k, x in enumerate((-0.25, 0.05, 0.3)):
        wisp = [(x + 0.1 * math.sin(j * 1.8 + k + frame * 1.2), 0.65 + 0.22 * j, -0.1) for j in range(4)]
        for j in range(3):
            (x0, y0, z0), (x1, y1, z1) = wisp[j], wisp[j + 1]
            w = 0.045 * (1 - j / 4)
            m.quad(m.point(x0 - w, y0, z0), m.point(x0 + w, y0, z0), m.point(x1 + w, y1, z1), m.point(x1 - w, y1, z1),
                   "steam")
    return m


def pizza_slice(frame):
    """Pizza: a thick wedge with a raised crust, cheese, three pepperoni and a
    drip of cheese. It has one frame."""
    m = Faces()
    t = 0.18  # thick
    # The wedge's tip points at you; the crust runs along a slight curve.
    arc = [(-0.75 + 1.5 * i / 4, 0.75 - 0.12 * abs(i - 2)) for i in range(5)]
    tip_top, tip_bottom = m.point(0, t / 2, -0.9), m.point(0, -t / 2, -0.9)
    top = [m.point(x, t / 2, z) for x, z in arc]
    bottom = [m.point(x, -t / 2, z) for x, z in arc]
    for i in range(4):
        m.faces.append((tip_top, top[i + 1], top[i], "cheese"))
        m.faces.append((tip_bottom, bottom[i], bottom[i + 1], "crust"))
    m.quad(tip_top, top[0], bottom[0], tip_bottom, "crust")
    m.quad(tip_top, tip_bottom, bottom[4], top[4], "crust")
    # The crust's lip, raised along the arc.
    front = [m.point(x, t / 2 + 0.15, z - 0.12) for x, z in arc]
    back = [m.point(x, t / 2 + 0.15, z + 0.05) for x, z in arc]
    back_low = [m.point(x, -t / 2, z + 0.05) for x, z in arc]
    for i in range(4):
        m.quad(top[i], top[i + 1], front[i + 1], front[i], "crust")
        m.quad(front[i], front[i + 1], back[i + 1], back[i], "crust")
        m.quad(back[i], back[i + 1], back_low[i + 1], back_low[i], "crust")
    for cx, cz in ((-0.28, 0.35), (0.3, 0.38), (0.0, -0.15)):
        loop = m.ring(cx, t / 2 + 0.03, cz, 0.15, 6)
        m.fan(m.point(cx, t / 2 + 0.03, cz), loop[::-1], "pepperoni")
    drip = [m.point(-0.36, t / 2 + 0.01, -0.1), m.point(-0.5, t / 2 + 0.01, 0.25), m.point(-0.5, -t / 2 - 0.25, 0.05)]
    m.faces.append(tuple(drip) + ("cheese",))
    return m


# Each pickup's model, its frames, and how it's turned to you.
PICKUP_MODELS = {
    "coffee": (mug, 6, -0.5),
    "pizza": (pizza_slice, 1, 0.5),
}


def shade(model, yaw, pitch=-0.45):
    """The model's triangles as the game shows them: turned yaw, tipped pitch,
    each flat-shaded in one of three tones by how it faces LIGHT, and ordered
    far to near (pepperoni and coffee last, over what they sit on). Each is
    ([x0, y0, x1, y1, x2, y2], pen) in units of its radius, y down."""
    cy, sy, cp, sp = math.cos(yaw), math.sin(yaw), math.cos(pitch), math.sin(pitch)
    turned = []
    for x, y, z in model.points:
        x, z = x * cy - z * sy, x * sy + z * cy
        y, z = y * cp - z * sp, y * sp + z * cp
        turned.append((x, y, z))
    light = math.sqrt(sum(v * v for v in LIGHT))
    faces = []
    for a, b, c, material in model.faces:
        pa, pb, pc = turned[a], turned[b], turned[c]
        u = [pb[i] - pa[i] for i in range(3)]
        v = [pc[i] - pa[i] for i in range(3)]
        n = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
        size = math.sqrt(n[0] * n[0] + n[1] * n[1] + n[2] * n[2]) or 1.0
        facing = (n[0] * LIGHT[0] + n[1] * LIGHT[1] + n[2] * LIGHT[2]) / size / light
        if n[2] > 0:  # both sides of every face are lit: the side toward you
            facing = -facing
        tone = 1.0 if facing > 0.45 else 0.72 if facing > 0.0 else 0.48
        depth = (pa[2] + pb[2] + pc[2]) / 3 - (0.5 if material in ("pepperoni", "coffee") else 0)
        flat = []
        for x, y, z in (pa, pb, pc):
            k = 4.0 / (4.0 + z)
            flat += [x * k, -y * k]
        faces.append((depth, flat, (material, tone)))
    faces.sort(key=lambda f: -f[0])
    pens = {}
    for depth, flat, look in faces:
        if look not in pens:
            pens[look] = pen(dim(MATERIALS[look[0]], look[1]))
    return [(flat, pens[look]) for depth, flat, look in faces]


def bake_pickup(faces, size):
    """Shaded triangles (see shade) drawn into an image size px in radius,
    returned like bake's."""
    xs = [flat[i] for flat, p in faces for i in (0, 2, 4)]
    ys = [flat[i] for flat, p in faces for i in (1, 3, 5)]
    left, top = min(xs), min(ys)
    w = int((max(xs) - left) * size) + 2
    h = int((max(ys) - top) * size) + 2
    img = image(w, h)
    img.antialias = image.OFF  # antialiased, neighbouring triangles show seams
    for flat, p in faces:
        x0, y0, x1, y1, x2, y2 = flat
        img.pen = p
        img.triangle(int((x0 - left) * size + 0.5), int((y0 - top) * size + 0.5), int((x1 - left) * size + 0.5),
                     int((y1 - top) * size + 0.5), int((x2 - left) * size + 0.5), int((y2 - top) * size + 0.5))
    return img, left, top, w / size, h / size


class Aim:
    """Where you're aiming, in degrees, from the gyro (rotate) or from how
    far the badge is tipped (tilt), within the limit either way."""

    def __init__(self):
        self.mode = "rotate"
        self.bias = [0.0, 0.0, 0.0]
        self.down = [0.0, 0.0, 1.0]
        self.level = 0.0  # accelerometer x as the badge was held at the start
        self.raw = 0.0
        self.centre = 0.0
        self.yaw = 0.0
        self.window = []

    def calibrate(self, mode, seconds=1.0):
        samples = []
        down = [0.0, 0.0, 0.0]
        end = time.ticks_add(time.ticks_ms(), int(seconds * 1000))
        while time.ticks_diff(end, time.ticks_ms()) > 0:
            badge.poll()
            v = badge.imu()
            samples.append(v[3:6])
            for i in range(3):
                down[i] += v[i]
            time.sleep_ms(5)
        self.set_down(down)
        # The steadiest quarter of the hold is the best guess at zero.
        size = max(1, len(samples) // 4)
        best = None
        for start in range(0, len(samples) - size + 1, max(1, size // 2)):
            mean, spread = stats(samples[start:start + size])
            if best is None or spread < best[1]:
                best = (mean, spread)
        self.bias = best[0]
        self.set_mode(mode)
        self.level = down[0] / len(samples)

    def set_mode(self, mode):
        """Switches how aiming works, starting from straight ahead."""
        self.mode = mode
        self.level = badge.imu()[0]
        self.window = []
        self.raw = self.centre = self.yaw = 0.0

    def set_down(self, a):
        length = math.sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2]) or 1.0
        self.down = [a[0] / length, a[1] / length, a[2] / length]

    def tilt_rate(self, ax):
        """Degrees a second to turn, for an accelerometer x reading."""
        tip = TILT_SIGN * (self.level - ax) / 16384.0
        if abs(tip) <= TILT_DEADZONE:
            return 0.0
        amount = min(1.0, (abs(tip) - TILT_DEADZONE) / (TILT_FULL - TILT_DEADZONE))
        return TILT_DPS * amount * (1 if tip > 0 else -1)

    def update(self, dt):
        v = badge.imu()
        if self.mode == "tilt":
            self.yaw = max(-YAW_LIMIT, min(YAW_LIMIT, self.yaw + self.tilt_rate(v[0]) * dt))
            return
        # Follow slow changes in how the badge is held.
        d = self.down
        self.set_down([d[i] * 0.9 + v[i] / 16384.0 * 0.1 for i in range(3)])
        w = [v[3 + i] - self.bias[i] for i in range(3)]
        rate = (w[0] * self.down[0] + w[1] * self.down[1] + w[2] * self.down[2]) / GYRO_LSB_PER_DPS
        self.window.append(v[3:6])
        if len(self.window) >= STILL_FRAMES:
            mean, spread = stats(self.window)
            if spread < STILL_SPREAD * GYRO_LSB_PER_DPS:
                self.bias = [b + (m - b) * 0.3 for b, m in zip(self.bias, mean)]
            self.window = []
        self.raw += YAW_SIGN * rate * dt
        yaw = self.raw - self.centre
        if yaw > YAW_LIMIT:
            self.centre += yaw - YAW_LIMIT
        elif yaw < -YAW_LIMIT:
            self.centre += yaw + YAW_LIMIT
        self.yaw = self.raw - self.centre

    def reset_origin(self):
        """Makes the way you're facing (or holding the badge) straight ahead."""
        self.centre = self.raw
        self.yaw = 0.0
        self.level = badge.imu()[0]


class View:
    """World (azimuth degrees, distance) to screen, for the current yaw."""

    def set(self, yaw):
        # Rotate the world by -yaw, so a point at azimuth a lands at
        # tan(a - yaw): straight ahead of where you aim is the screen's centre,
        # the same as screen_x uses for the skyline.
        r = math.radians(yaw)
        self.cos = math.cos(r)
        self.sin = math.sin(r)

    def project(self, x, z, height):
        # Camera space, then the pinhole: None if behind or beside the eye.
        xc = x * self.cos - z * self.sin
        zc = x * self.sin + z * self.cos
        if zc < 0.3:
            return None
        return WIDTH / 2 + FOCAL * xc / zc, HORIZON + (EYE - height) * FOCAL / zc, zc

    def polar(self, azimuth, distance, height):
        a = math.radians(azimuth)
        return self.project(distance * math.sin(a), distance * math.cos(a), height)

    def segment(self, x0, z0, x1, z1, height):
        """A floor line as screen coordinates, cut where it passes the eye,
        or None if it's all behind."""
        c, s = self.cos, self.sin
        ax, az = x0 * c - z0 * s, x0 * s + z0 * c
        bx, bz = x1 * c - z1 * s, x1 * s + z1 * c
        near = 1.0
        if az < near and bz < near:
            return None
        if az < near:
            ax += (bx - ax) * (near - az) / (bz - az)
            az = near
        elif bz < near:
            bx += (ax - bx) * (near - bz) / (az - bz)
            bz = near
        lift = (EYE - height) * FOCAL
        return (WIDTH / 2 + FOCAL * ax / az, HORIZON + lift / az,
                WIDTH / 2 + FOCAL * bx / bz, HORIZON + lift / bz)


class Bot:
    def __init__(self, kind, azimuth, toughness=1.0):
        self.kind = kind
        self.spec = BOTS[kind]
        self.size = self.spec["size"]
        self.home = azimuth
        self.azimuth = azimuth
        self.distance = SPAWN_DISTANCE
        # Friday Deploy raises toughness: more health, and faster.
        self.hp = self.max_hp = self.spec["hp"] * toughness
        self.speed = self.spec["speed"] * toughness
        self.flash = 0.0
        self.phase = random.uniform(0, 6.28)

    def update(self, dt, t):
        self.distance -= self.speed * dt
        if self.spec["weave"]:
            self.azimuth = self.home + self.spec["weave"] * math.sin(t * 2.0 + self.phase)
        self.flash = max(0.0, self.flash - dt)


class Pickup:
    def __init__(self, kind, azimuth, distance):
        self.kind = kind
        self.spec = PICKUPS[kind]
        self.size = PICKUP_SIZE
        self.azimuth = azimuth
        self.distance = distance
        self.life = PICKUP_SECONDS
        self.phase = random.uniform(0, 6.28)
        self.taken = False


class Shot:
    def __init__(self, weapon, index, azimuth, damage):
        self.weapon = weapon
        self.index = index
        self.azimuth = azimuth
        self.damage = damage
        self.distance = REACH
        self.last = REACH
        self.struck = []  # bots a piercing shot has already hit


class Game:
    def __init__(self):
        self.aim = Aim()
        self.view = View()
        self.state = "splash"
        self.splash = 0.0
        self.choice = 0
        self.setting_row = 0
        self.settings_from = "title"
        self.origin_note = 0.0
        self.best, self.settings = load_state()
        # Bot models, by kind, frame and size, built ahead a few at a time on
        # the splash and title screens, at the sizes each kind can appear:
        # small ones first, as bots arrive small.
        self.models = {kind: [[None] * len(MODEL_SIZES) for f in range(MODELS[kind][1])] for kind in BOTS}
        self.unbuilt = []
        for kind, spec in BOTS.items():
            far = model_size(spec["size"] * FOCAL / SPAWN_DISTANCE) or 0
            near = model_size(spec["size"] * FOCAL / REACH)
            for size in range(far, near + 1):
                for frame in range(MODELS[kind][1]):
                    self.unbuilt.append((kind, frame, size))
        self.unbuilt.sort(key=lambda key: -key[2])
        self.unbuilt = [(self.model, key) for key in self.unbuilt]
        # Pickup art, by kind and frame, each at every one of the
        # PICKUP_ART_SIZES, built first of all.
        self.pickup_arts = {kind: [None] * frames for kind, (build, frames, yaw) in PICKUP_MODELS.items()}
        for kind, (build, frames, yaw) in PICKUP_MODELS.items():
            for frame in range(frames):
                self.unbuilt.append((self.pickup_art, (kind, frame)))
        logo = image.load("assets/studio_logo.png")
        self.logo = logo  # the pieces are windows onto it
        self.logo_pieces = [
            (logo.window(x, y, w, h), LOGO_AT[0] + x, LOGO_AT[1] + y, appear)
            for (x, y, w, h), appear in LOGO_PIECES
        ]
        self.reset()

    def reset(self):
        self.stats = dict(BASE_STATS)
        self.health = self.stats["max_health"]
        self.shields = 0
        self.shield_timer = 0.0
        self.bots = []
        self.shots = []
        self.pickups = []
        self.popups = []
        # You start with LINT; weapon cards add the others and improve them.
        self.owned = [True] + [False] * (len(WEAPONS) - 1)
        self.magazine = [w["magazine"] for w in WEAPONS]
        self.damage = [w["damage"] for w in WEAPONS]
        self.pellets = [w["pellets"] for w in WEAPONS]
        self.weapon = 0
        self.cooldown = 0.0
        self.ammo = [float(w["magazine"]) for w in WEAPONS]
        self.reloading = [0.0] * len(WEAPONS)
        self.overdrive = 0.0
        self.offers = []
        self.card = 0
        self.score = 0
        self.clock = 0.0
        self.wave = 0
        self.spawn_in = 1.5
        self.hurt = 0.0
        self.blocked = 0.0
        self.nuked = 0.0
        self.message = ""
        self.message_time = 0.0
        self.scroll = 0.0
        self.quip = random.choice(GAME_OVER_LINES)

    # --- rules ---

    def new_bot(self, kind, azimuth):
        return Bot(kind, azimuth, 1 + self.stats["risk"])

    def points(self, bot):
        return round(bot.spec["points"] * (1 + self.stats["risk"]))

    def spawn(self):
        kinds = ["bug"] * 3 + ["hallucination"] * 3
        if self.wave >= 1:
            kinds += ["node_modules"] * 2
        self.bots.append(self.new_bot(random.choice(kinds), random.uniform(-SPAWN_ARC, SPAWN_ARC)))

    def offer_upgrades(self):
        """Freezes the game on three different cards to choose from, each
        (card, plus)."""
        pool = [u for u in UPGRADES if not (u["stat"] == "shields" and self.stats["shields"] >= MAX_SHIELDS)]
        pool += WEAPON_CARDS
        self.offers = []
        while pool and len(self.offers) < 3:
            pick = random.choice(pool)
            pool.remove(pick)
            self.offers.append((pick, random.random() < PLUS_CHANCE))
        self.card = len(self.offers) // 2
        self.state = "upgrade"

    def card_text(self, card, plus=False):
        """What a card says, as things stand: name, flavour, effect, and the
        change it makes."""
        mark = "+" if plus else ""
        effect = "effect_plus" if plus else "effect"
        if "weapon" in card:
            i = card["weapon"]
            now = getattr(self, card["boost"])[i]
            unit = {"magazine": " rounds", "damage": " damage", "pellets": " pellets"}[card["boost"]]
            if not self.owned[i]:
                change = "new: %d%s" % (now + card["step"], unit) if plus else "new weapon"
                return card["unlock"] + mark, card["unlock_flavor"], card["unlock_" + effect], change
            later = now + card["step"] * (2 if plus else 1)
            return card["name"] + mark, card["flavor"], card[effect], "%d -> %d%s" % (now, later, unit)
        stat = card["stat"]
        now = self.stats[stat]
        change = stat_text(stat, now) + " -> " + stat_text(stat, stepped(card, now, plus))
        return card["name"] + mark, card["flavor"], card[effect], change

    def take_upgrade(self, card, plus=False):
        name = self.card_text(card, plus)[0]
        if "weapon" in card:
            i = card["weapon"]
            boost = getattr(self, card["boost"])
            if self.owned[i]:
                boost[i] += card["step"] * (2 if plus else 1)
            else:
                # A new weapon goes straight into your hands to try out, and a
                # + card's comes already improved once.
                self.owned[i] = True
                if plus:
                    boost[i] += card["step"]
                self.ammo[i] = float(self.magazine[i])
                self.weapon = i
        else:
            stat = card["stat"]
            before = self.stats[stat]
            self.stats[stat] = stepped(card, before, plus)
            if stat == "max_health":
                self.health = min(self.stats["max_health"], self.health + self.stats[stat] - before)
            elif stat == "shields":
                self.shields += 1  # a new shield arrives charged
                if plus:
                    self.health = self.stats["max_health"]
        self.say("Release v0.%d.0 shipped with %s. More bots incoming." % (self.wave + 1, name))
        if self.wave % 3 == 2:
            self.bots.append(self.new_bot("agent", random.uniform(-SPAWN_ARC * 0.6, SPAWN_ARC * 0.6)))
        self.state = "play"

    def switch_weapon(self, step):
        """Left and Right: the next weapon you have, either way."""
        i = self.weapon
        for _ in range(len(WEAPONS)):
            i = (i + step) % len(WEAPONS)
            if self.owned[i]:
                self.weapon = i
                return

    def reload_now(self):
        """Down: start reloading the weapon in hand, unless it's full or already reloading."""
        i = self.weapon
        if self.reloading[i] <= 0 and self.ammo[i] < self.magazine[i]:
            self.reloading[i] = self.stats["reload"]

    def hit(self, shot, bot):
        bot.hp -= (shot.damage + self.stats["flat_damage"]) * (1 + self.stats["damage_bonus"])
        bot.flash = 0.12
        if bot.hp > 0:
            return
        points = self.points(bot)
        self.score += points
        self.popups.append([bot.azimuth, bot.distance, "+%d" % points, 0.8, TEXT])
        if random.random() < self.stats["pickup_chance"]:
            distance = min(max(bot.distance, PICKUP_DISTANCE[0]), PICKUP_DISTANCE[1])
            self.pickups.append(Pickup(self.pickup_kind(), self.pickup_azimuth(), distance))

    def pickup_azimuth(self):
        """Off to one side of your aim, so your next shot doesn't take a pickup
        before you've seen it, but never wider than bots come from."""
        offset = random.uniform(*PICKUP_OFFSET) * random.choice((-1, 1))
        if abs(self.aim.yaw + offset) > SPAWN_ARC:
            offset = -offset
        return self.aim.yaw + offset

    def pickup_kind(self):
        kinds = [k for k in PICKUPS if k != "cache" or self.stats["shields"] > 0]
        roll = random.uniform(0, sum(PICKUPS[k]["weight"] for k in kinds))
        for kind in kinds:
            roll -= PICKUPS[kind]["weight"]
            if roll <= 0:
                return kind
        return kinds[-1]

    def collect(self, pickup):
        pickup.taken = True
        label = pickup.spec["name"]
        if pickup.kind == "pizza":
            self.health = min(self.stats["max_health"], self.health + PIZZA_HEAL)
            label = "PIZZA +%d" % PIZZA_HEAL
        elif pickup.kind == "cache":
            self.shields = min(self.stats["shields"], self.shields + 1)
        elif pickup.kind == "coffee":
            # Overdrive: every weapon full and firing twice as fast, using no
            # ammo until it ends.
            self.overdrive = OVERDRIVE_SECONDS
            for i in range(len(WEAPONS)):
                if self.owned[i]:
                    self.ammo[i] = float(self.magazine[i])
                    self.reloading[i] = 0.0
            label = "COFFEE: OVERDRIVE"
        else:
            # rm -rf: every bot on the field, bar the rogue agent, which had backups.
            gone = [b for b in self.bots if b.hp > 0 and b.kind != "agent"]
            points = sum(self.points(b) for b in gone)
            for bot in gone:
                bot.hp = 0
            self.score += points
            self.nuked = 0.5
            self.say("rm -rf deleted %d bots. +%d%s" % (
                len(gone), points, " (the rogue agent had backups)" if any(b.kind == "agent" for b in self.bots) else ""))
        self.popups.append([pickup.azimuth, pickup.distance, label, 1.0, PICKUP_PENS[pickup.kind]])

    def update(self, dt):
        self.clock += dt
        self.scroll = (self.scroll + dt * 3.0) % 4.0
        wave = int(self.clock // WAVE_SECONDS)
        if wave != self.wave:
            # A release shipped: freeze on the upgrade choice before going on.
            self.wave = wave
            self.offer_upgrades()
            return
        self.spawn_in -= dt
        if self.spawn_in <= 0:
            self.spawn()
            self.spawn_in = max(0.45, 2.2 * 0.86 ** self.wave) * random.uniform(0.7, 1.3)

        # Reloads finish whether or not the weapon's in hand, and weapons on
        # the holster slowly refill by themselves.
        for i in range(len(WEAPONS)):
            if not self.owned[i]:
                continue
            if self.reloading[i] > 0:
                self.reloading[i] -= dt
                if self.reloading[i] <= 0:
                    self.reloading[i] = 0.0
                    self.ammo[i] = float(self.magazine[i])
            elif i != self.weapon and self.ammo[i] < self.magazine[i]:
                refill = self.magazine[i] / (HOLSTER_REFILL * self.stats["reload"])
                self.ammo[i] = min(float(self.magazine[i]), self.ammo[i] + refill * dt)

        # The weapon in hand fires whenever it has a round; emptying the
        # magazine starts a reload. Overdrive uses no rounds.
        i = self.weapon
        w = WEAPONS[i]
        rate = w["rate"] * self.stats["fire_rate"] * (2 if self.overdrive > 0 else 1)
        self.cooldown -= dt
        while self.cooldown <= 0 and self.reloading[i] <= 0 and self.ammo[i] >= 1:
            self.cooldown += 1.0 / rate
            n = self.pellets[i]
            for p in range(n):
                self.shots.append(Shot(w, i, self.aim.yaw + w["gap"] * (p - (n - 1) / 2), self.damage[i]))
            if self.overdrive <= 0:
                self.ammo[i] -= 1
                if self.ammo[i] < 1:
                    self.reloading[i] = self.stats["reload"]
        self.cooldown = max(self.cooldown, 0.0)

        for shot in self.shots:
            shot.last = shot.distance
            shot.distance += shot.weapon["speed"] * dt
        for bot in self.bots:
            bot.update(dt, self.clock)

        # Hits: a shot sweeps from where it was to where it is this frame. It
        # stops at the first bot or pickup it meets, unless it pierces.
        targets = self.pickups + self.bots
        spent = []
        for shot in self.shots:
            for target in targets:
                if getattr(target, "taken", False) or getattr(target, "hp", 1) <= 0 or target in shot.struck:
                    continue
                if not (shot.last - 0.6 <= target.distance <= shot.distance + 0.6):
                    continue
                reach = math.degrees(math.atan((target.size + shot.weapon["radius"]) / max(target.distance, 0.5)))
                if abs(shot.azimuth - target.azimuth) <= reach:
                    if isinstance(target, Pickup):
                        self.collect(target)
                    else:
                        self.hit(shot, target)
                    if shot.weapon["pierce"]:
                        shot.struck.append(target)
                    else:
                        spent.append(shot)
                        break
        if spent:
            self.shots = [s for s in self.shots if s not in spent]
        self.shots = [s for s in self.shots if s.distance < s.weapon["reach"]]

        # Bots that reach you hit a shield if one's charged, or merge into main.
        alive = []
        for bot in self.bots:
            if bot.hp <= 0:
                continue
            if bot.distance <= REACH:
                self.shield_timer = SHIELD_RECHARGE
                if self.shields > 0:
                    self.shields -= 1
                    self.blocked = 0.35
                    self.say("Two-factor auth stopped %s." % bot.spec["name"].lower())
                else:
                    self.health -= bot.spec["hit"]
                    self.hurt = 0.35
                    self.say("%s %s. -%d" % (bot.spec["name"], bot.spec["quip"], bot.spec["hit"]))
            else:
                alive.append(bot)
        self.bots = alive

        if self.shields < self.stats["shields"]:
            self.shield_timer -= dt
            if self.shield_timer <= 0:
                self.shields += 1
                self.shield_timer = SHIELD_RECHARGE

        for pickup in self.pickups:
            pickup.life -= dt
        self.pickups = [p for p in self.pickups if p.life > 0 and not p.taken]
        for popup in self.popups:
            popup[3] -= dt
        self.popups = [p for p in self.popups if p[3] > 0]
        self.overdrive = max(0.0, self.overdrive - dt)
        self.hurt = max(0.0, self.hurt - dt)
        self.blocked = max(0.0, self.blocked - dt)
        self.nuked = max(0.0, self.nuked - dt)
        self.message_time = max(0.0, self.message_time - dt)

        if self.health <= 0:
            self.health = 0
            self.state = "over"
            if self.score > self.best:
                self.best = self.score
                save_state(self.best, self.settings)

    def say(self, text):
        self.message = text
        self.message_time = 3.0

    # --- drawing ---

    def draw_world(self):
        view = self.view
        view.set(self.aim.yaw)
        # Sky bands, then the floor. The screen isn't cleared between frames,
        # so together they cover every row.
        for i, p in enumerate(SKY):
            top = i * HORIZON // len(SKY)
            screen.pen = p
            screen.rectangle(0, top, WIDTH, (i + 1) * HORIZON // len(SKY) - top)
        screen.pen = FLOOR
        screen.rectangle(0, HORIZON, WIDTH, HEIGHT - HORIZON)

        # Server towers on the horizon.
        for azimuth, width, height in TOWERS:
            left = self.screen_x(azimuth)
            right = self.screen_x(azimuth + width)
            if right < 0 or left > WIDTH:
                continue
            screen.pen = TOWER
            screen.rectangle(int(left), HORIZON - height, max(1, int(right - left)), height)
            if right - left >= 3:
                # A few lit windows; every call costs, so not many.
                screen.pen = WINDOW
                for wy in range(HORIZON - height + 3, HORIZON - 2, 8):
                    screen.rectangle(int(left) + 1, wy, 1, 1)

        # The floor grid: lines running away from you, and lines across that
        # stream toward you.
        screen.pen = GRID_FAR
        for k in range(-12, 13):
            line = view.segment(k * 1.5, 1.0, k * 1.5, 60.0, 0.0)
            if line:
                screen.line(*line)
        screen.pen = GRID
        z = 2.0 + (4.0 - self.scroll)
        while z < 40.0:
            line = view.segment(-25.0, z, 25.0, z, 0.0)
            if line:
                screen.line(*line)
            z *= 1.35

    def screen_x(self, azimuth):
        return WIDTH / 2 + FOCAL * math.tan(math.radians(azimuth - self.aim.yaw))

    def edge_marker(self, x, y, p):
        # Something off screen: a mark at that edge, lower as it gets closer.
        # The right one sits clear of the Up and Down overlays.
        screen.pen = p
        screen.rectangle(2 if x < 0 else WIDTH - 32, int(min(HEIGHT - 26, max(HORIZON + 4, y))) - 4, 4, 8)

    def model(self, kind, frame, size):
        """A bot model at one of MODEL_SIZES, built now if it wasn't already:
        its glow and core shapes and its eyes, or for the first SPRITE_SIZES,
        only images of it facing right and left (see bake). Every model
        kept is more for each garbage collection to look through."""
        built = self.models[kind][frame][size]
        if built is None:
            points, edges, eyes = FLAT[kind][frame]
            r = MODEL_SIZES[size]
            glow, core = neon(points, edges, r)
            if size < SPRITE_SIZES:
                built = (None, None, eyes, [bake(kind, points, eyes, glow, core, r, facing) for facing in (1, -1)])
            else:
                built = (glow, core, eyes, None)
            self.models[kind][frame][size] = built
        return built

    def build_models(self, budget_ms=None):
        """Builds bot models ahead of need, for up to budget_ms, or all that
        are left."""
        start = time.ticks_ms()
        while self.unbuilt and (budget_ms is None or time.ticks_diff(time.ticks_ms(), start) < budget_ms):
            build, key = self.unbuilt.pop()
            build(*key)

    def pickup_art(self, kind, frame):
        """A frame of a pickup as images at each of PICKUP_ART_SIZES, built
        now if they weren't already. Shading is most of the work, so it's
        done once for them all."""
        art = self.pickup_arts[kind][frame]
        if art is None:
            build, frames, yaw = PICKUP_MODELS[kind]
            faces = shade(build(frame), yaw)
            art = self.pickup_arts[kind][frame] = [bake_pickup(faces, size) for size in PICKUP_ART_SIZES]
        return art

    def bot_frame(self, bot, t):
        """Which of its model's frames a bot shows: bugs scuttle, node_modules
        sheds armour as it's hit, hallucinations ripple, the agent's wings beat."""
        if bot.kind == "bug":
            return int(t * 12 + bot.phase) % 2
        if bot.kind == "node_modules":
            return min(3, int(4 * (1 - max(bot.hp, 0) / bot.max_hp)))
        if bot.kind == "hallucination":
            return (0, 1, 2, 1)[int(t * 6 + bot.phase) % 4]
        return int(t * 2.5 + bot.phase) % 2

    def draw_bots(self):
        view = self.view
        t = time.ticks_ms() / 1000
        screen.antialias = image.X2
        # Far to near, so near ones cover far ones.
        for bot in sorted(self.bots, key=lambda b: -b.distance):
            spec = bot.spec
            at = view.polar(bot.azimuth, bot.distance, spec["height"])
            if at is None:
                continue
            x, y, depth = at
            r = spec["size"] * FOCAL / depth
            if x + r < 0 or x - r > WIDTH:
                self.edge_marker(x, y, BOT_PENS[bot.kind])
                continue
            size = model_size(r)
            if size is None:
                # Too far off for a model: a dot.
                screen.pen = BOT_PENS[bot.kind]
                screen.rectangle(int(x) - 1, int(y) - 1, 2, 2)
                continue
            frame = self.bot_frame(bot, t)
            glow, core, eyes, sprites = self.models[bot.kind][frame][size] or self.model(bot.kind, frame, size)
            # Models face a little to the right. Weavers turn the way they're
            # swaying; the rest face the middle of the screen.
            if spec["weave"]:
                facing = 1 if math.cos(self.clock * 2.0 + bot.phase) > 0 else -1  # see Bot.update
            else:
                facing = 1 if x < WIDTH / 2 else -1
            if sprites:
                img, left, top, w, h = sprites[0 if facing > 0 else 1]
                k = r * 1.15 if bot.flash > 0 else r  # a hit makes it pop
                screen.blit(img, rect(int(x + left * k), int(y + top * k), int(w * k), int(h * k)))
                self.draw_health(bot, x, y, r)
                continue
            # Up close: the shapes themselves, flashing white from a hit.
            place = mat3().translate(x, y).scale(facing * r, r)
            glow.transform = place
            core.transform = place
            screen.pen = BOT_PENS[bot.kind] if bot.flash > 0 else BOT_GLOW[bot.kind]
            screen.shape(glow)
            screen.pen = WHITE if bot.flash > 0 else BOT_PENS[bot.kind]
            screen.shape(core)
            screen.pen = WHITE
            dot = max(1, int(r * 0.07))
            for ex, ey in eyes:
                screen.circle(int(x + facing * ex * r), int(y + ey * r), dot)
            self.draw_health(bot, x, y, r)
        screen.antialias = image.OFF

    def draw_health(self, bot, x, y, r):
        # Once it's hurt, for anything that takes more than a couple of hits.
        if bot.hp < bot.max_hp and bot.spec["hp"] > 2:
            screen.pen = TRACK
            screen.rectangle(int(x - r), int(y + r + 3), int(2 * r), 2)
            screen.pen = BOT_PENS[bot.kind]
            screen.rectangle(int(x - r), int(y + r + 3), max(1, int(2 * r * max(bot.hp, 0) / bot.max_hp)), 2)

    def draw_pickups(self):
        t = time.ticks_ms() / 1000
        for pickup in self.pickups:
            # Fading out: blink through the last second.
            if pickup.life < 1.0 and int(pickup.life * 10) % 2:
                continue
            # Pickups bob up and down, which bots never do.
            at = self.view.polar(pickup.azimuth, pickup.distance, 0.75 + 0.25 * math.sin(t * 3.0 + pickup.phase))
            if at is None:
                continue
            x, y, depth = at
            r = max(4, int(pickup.size * FOCAL / depth))
            if x + r < 0 or x - r > WIDTH:
                self.edge_marker(x, y, PICKUP_PENS[pickup.kind])
                continue
            if pickup.kind in PICKUP_MODELS:
                frame = int(t * 8 + pickup.phase) % PICKUP_MODELS[pickup.kind][1]
                art = self.pickup_arts[pickup.kind][frame] or self.pickup_art(pickup.kind, frame)
                img, left, top, w, h = art[0 if r < 14 else 1]
                screen.blit(img, rect(int(x + left * r), int(y + top * r), int(w * r), int(h * r)))
            elif pickup.kind == "cache":
                screen.pen = PICKUP_PENS["cache"]
                screen.rectangle(int(x - r * 0.7), int(y - r * 0.7), int(r * 1.4), int(r * 0.8))
                screen.triangle(int(x - r * 0.7), int(y + r * 0.1), int(x + r * 0.7), int(y + r * 0.1), int(x), int(y + r))
                screen.pen = WHITE
                screen.circle(int(x), int(y - r * 0.15), max(1, int(r * 0.2)))
            else:
                screen.pen = PICKUP_PENS["rmrf"]
                screen.rectangle(int(x - r * 1.4), int(y - r * 0.55), int(r * 2.8), int(r * 1.1))
                screen.pen = BLACK
                screen.rectangle(int(x - r * 1.4) + 2, int(y - r * 0.55) + 2, int(r * 2.8) - 4, int(r * 1.1) - 4)
                if r >= 7:
                    screen.font = font.winds
                    screen.pen = PICKUP_PENS["rmrf"]
                    tw, th = screen.measure_text("rm -rf")
                    screen.text("rm -rf", int(x) - tw // 2, int(y) - th // 2)

    def draw_shots(self):
        for shot in self.shots:
            at = self.view.polar(shot.azimuth, shot.distance, 0.75)
            if at is None:
                continue
            x, y, depth = at
            size = max(1, int(0.18 * FOCAL / depth))
            screen.pen = WEAPON_PENS[shot.index]
            screen.rectangle(int(x) - size // 2, int(y) - size // 2, size, size)

    def draw_side_tab(self, y, icon, lit=False, progress=None):
        """An overlay on the right edge beside the button at y, showing what
        it does: 'settings', 'reload' or 'next'."""
        x0, cx = WIDTH - 24, WIDTH - 11
        screen.pen = PANEL
        screen.rectangle(x0, y - 13, 24, 26)
        glow = WEAPON_PENS[self.weapon] if icon == "reload" else WEAPON_PENS[0]
        screen.pen = glow if lit else MUTED
        screen.rectangle(x0, y - 13, 2, 26)
        if icon == "reload":
            points = RELOAD_ARC
            done = len(points) if progress is None else int(len(points) * progress)
            for i, (px, py) in enumerate(points):
                screen.pen = (glow if lit else MUTED) if i < done else TRACK
                screen.rectangle(int(cx + px) - 1, int(y + py) - 1, 2, 2)
            ex, ey = points[-1]
            screen.triangle(int(cx + ex) - 3, int(y + ey) - 2, int(cx + ex) + 3, int(y + ey) - 2, int(cx + ex), int(y + ey) + 3)
        elif icon == "settings":
            screen.circle(cx, y, 5)
            for k in range(8):
                a = math.radians(k * 45)
                screen.rectangle(int(cx + 6.5 * math.cos(a)) - 1, int(y + 6.5 * math.sin(a)) - 1, 3, 3)
            screen.pen = BLACK
            screen.circle(cx, y, 2)
        else:  # 'next': a down arrowhead
            screen.triangle(cx - 6, y - 3, cx + 6, y - 3, cx, y + 4)

    def draw_hud(self):
        cx, cy = WIDTH // 2, HORIZON + int(0.4 * FOCAL / 6.0)
        reloading = self.reloading[self.weapon] > 0
        # Only left and right matter when aiming, so a faint line marks it
        # from the horizon down, under the crosshair.
        screen.pen = AIM_LINE[self.weapon]
        screen.line(cx, HORIZON + 2, cx, HEIGHT - 28)
        screen.pen = WEAPON_DIM[self.weapon] if reloading else WEAPON_PENS[self.weapon]
        screen.rectangle(cx - 7, cy, 5, 1)
        screen.rectangle(cx + 3, cy, 5, 1)
        screen.rectangle(cx, cy - 7, 1, 5)
        screen.rectangle(cx, cy + 3, 1, 5)
        if reloading:
            screen.font = font.winds
            screen.pen = TEXT
            centred("reloading", cy + 10)

        screen.font = font.salty
        for azimuth, distance, text, life, p in self.popups:
            at = self.view.polar(azimuth, distance, 1.0)
            if at:
                screen.pen = p
                screen.text(text, int(at[0]) - text_width(text) // 2, int(at[1]) - 10 - int((1.0 - life) * 20))

        # Health, then shields.
        screen.pen = MUTED
        screen.text("main", 6, 4)
        screen.pen = TRACK
        screen.rectangle(40, 7, 80, 7)
        screen.pen = DANGER if self.health < 0.3 * self.stats["max_health"] else WEAPON_PENS[0]
        screen.rectangle(40, 7, int(80 * max(self.health, 0) / self.stats["max_health"]), 7)
        for i in range(self.stats["shields"]):
            screen.pen = SHIELD_PEN if i < self.shields else SHIELD_DIM
            screen.rectangle(126 + i * 10, 6, 7, 9)
        if self.overdrive > 0:
            screen.font = font.winds
            screen.pen = PICKUP_PENS["coffee"]
            screen.text("OVERDRIVE %.1f" % self.overdrive, 40, 17)
            screen.font = font.salty
        screen.pen = TEXT
        label = "v0.%d.0" % (self.wave + 1)
        screen.text(label, 196 - text_width(label) // 2, 4)
        label = "%d" % self.score
        screen.text(label, WIDTH - 6 - text_width(label), 4)

        # The weapons you have, each with its ammo or how far its reload is.
        x = 6
        for i, weapon in enumerate(WEAPONS):
            if not self.owned[i]:
                continue
            tw = text_width(weapon["name"])
            if i == self.weapon:
                screen.pen = WEAPON_PENS[i]
                screen.rectangle(x - 3, HEIGHT - 23, tw + 6, 15)
                screen.pen = BLACK
            else:
                screen.pen = WEAPON_DIM[i]
            screen.text(weapon["name"], x, HEIGHT - 22)
            screen.pen = TRACK
            screen.rectangle(x - 3, HEIGHT - 6, tw + 6, 3)
            if self.reloading[i] > 0:
                screen.pen = MUTED
                done = 1 - self.reloading[i] / self.stats["reload"]
            else:
                screen.pen = WEAPON_PENS[i]
                done = self.ammo[i] / self.magazine[i]
            screen.rectangle(x - 3, HEIGHT - 6, int((tw + 6) * done), 3)
            x += tw + 14

        # What Up and Down do, beside them.
        progress = 1 - self.reloading[self.weapon] / self.stats["reload"] if reloading else None
        self.draw_side_tab(UP_Y, "settings")
        self.draw_side_tab(DOWN_Y, "reload", reloading, progress)

        if self.message_time > 0:
            screen.pen = TEXT
            y = 31
            for line in wrap(self.message, WIDTH - 40):
                centred(line, y)
                y += 16

        for timer, colour in ((self.hurt, (255, 40, 60)), (self.blocked, PICKUPS["cache"]["rgb"]),
                              (self.nuked, PICKUPS["rmrf"]["rgb"])):
            if timer > 0:
                screen.pen = pen(colour, int(160 * min(1.0, timer / 0.35)))
                screen.rectangle(0, 0, WIDTH, 4)
                screen.rectangle(0, HEIGHT - 4, WIDTH, 4)
                screen.rectangle(0, 0, 4, HEIGHT)
                screen.rectangle(WIDTH - 4, 0, 4, HEIGHT)

    def draw_card(self, lines, colour, top=40, left=20, width=WIDTH - 40):
        # The title in the big font, then each line wrapped to the card.
        screen.font = font.salty
        body = []
        for line in lines[1:]:
            body += wrap(line, width - 20)
        screen.pen = PANEL
        screen.rectangle(left, top, width, 46 + 17 * len(body))
        screen.font = font.ignore
        screen.pen = colour
        centred(lines[0], top + 8, left, width)
        screen.font = font.salty
        screen.pen = TEXT
        y = top + 42
        for line in body:
            centred(line, y, left, width)
            y += 17

    def draw_splash(self):
        screen.pen = SPLASH_BACKGROUND
        screen.clear()
        last = len(self.logo_pieces) - 1
        for i, (window, x, y, appear) in enumerate(self.logo_pieces):
            age = self.splash - appear
            if age < 0:
                continue
            k = min(1.0, age / 0.3)
            if i == last:
                offset = -10 * math.sin(math.pi * k)  # the :3 hops in place
            else:
                offset = 8 * (1 - k) ** 2  # the words rise into place
            screen.blit(window, vec2(x, y + offset))

    def glow_pens(self):
        pulse = 0.5 + 0.5 * math.sin(time.ticks_ms() / 1000 * 4.0)
        return ((5, pen(WEAPONS[0]["rgb"], int(50 + 70 * pulse))), (2, WEAPON_PENS[0]))

    def draw_mark(self, x, mark):
        """A glowing mark from BUTTON_MARKS, bobbing right over the button
        below the screen at x."""
        base = HEIGHT - 6 + int(3 * math.sin(time.ticks_ms() / 1000 * 6.0))
        for stroke, p in self.glow_pens():
            screen.pen = p
            for px, py in BUTTON_MARKS[mark]:
                screen.rectangle(int(x + px) - stroke // 2, int(base + py) - stroke // 2, stroke, stroke)

    def draw_game(self):
        self.draw_world()
        self.draw_bots()
        self.draw_pickups()
        self.draw_shots()
        self.draw_hud()

    def draw_menu(self, title, rows, chosen, top, settings_lit=False):
        """A panel of rows with the chosen one lit. Down moves to the next row,
        enter takes it, and Up is settings, as everywhere."""
        left, width = 60, WIDTH - 120
        screen.pen = PANEL
        screen.rectangle(left, top, width, 52 + 26 * len(rows))
        screen.font = font.ignore
        screen.pen = WEAPON_PENS[0]
        centred(title, top + 8)
        screen.font = font.salty
        y = top + 46
        for i, label in enumerate(rows):
            if i == chosen:
                screen.pen = WEAPON_PENS[0]
                screen.rectangle(left + 12, y - 3, width - 24, 22)
                screen.pen = BLACK
            else:
                screen.pen = TEXT
            centred(label, y)
            y += 26
        self.draw_side_tab(UP_Y, "settings", settings_lit)
        self.draw_side_tab(DOWN_Y, "next", True)
        self.draw_mark(ENTER_X, "check")

    def settings_rows(self):
        turning = "Tilt" if self.settings["turning"] == "tilt" else "Rotate"
        return ["Turning: < %s >" % turning, "Reset origin", "Back"]

    def draw_upgrades(self):
        screen.pen = pen((0, 0, 0), 160)
        screen.rectangle(0, 0, WIDTH, HEIGHT)
        screen.font = font.salty
        screen.pen = WEAPON_PENS[0]
        centred("v0.%d.0 shipped! Pick an upgrade" % (self.wave + 1), 8)
        width, gap, top = 92, 5, 32
        left = 8
        for i, (card, plus) in enumerate(self.offers):
            name, flavor, effect, change = self.card_text(card, plus)
            x = left + i * (width + gap)
            chosen = i == self.card
            y = top - (4 if chosen else 0)
            # Weapon cards wear their weapon's colour, and + cards a gold frame.
            accent = WEAPON_PENS[card["weapon"]] if "weapon" in card else WEAPON_PENS[0]
            if plus:
                screen.pen = PLUS_PEN if chosen else PLUS_DIM
            else:
                screen.pen = accent if chosen else TRACK
            screen.rectangle(x - 2, y - 2, width + 4, 158)
            screen.pen = pen((10, 14, 30))
            screen.rectangle(x, y, width, 154)
            if "weapon" in card:
                screen.pen = accent
                screen.rectangle(x, y, width, 3)
            screen.font = font.salty
            screen.pen = accent if chosen else TEXT
            ty = y + 6
            for line in wrap(name, width - 10):
                screen.text(line, x + 5, ty)
                ty += 15
            screen.font = font.winds
            screen.pen = MUTED
            ty += 4
            for line in wrap(flavor, width - 10):
                screen.text(line, x + 5, ty)
                ty += 12
            screen.pen = TEXT
            ty += 5
            for line in wrap(effect, width - 10):
                screen.text(line, x + 5, ty)
                ty += 12
            screen.pen = accent if chosen else MUTED
            screen.text(change, x + 5, y + 138)
        self.draw_side_tab(UP_Y, "settings")
        self.draw_mark(LEFT_X, "left")
        self.draw_mark(RIGHT_X, "right")
        self.draw_mark(ENTER_X, "check")

    def draw_behind_settings(self):
        if self.settings_from in ("play", "paused", "upgrade"):
            self.draw_game()
        else:
            self.draw_world()

    def frame(self, dt):
        """Runs and draws one frame; True means quit the app."""
        if self.state == "splash":
            self.splash += dt
            self.draw_splash()
            self.build_models(20)
            if self.splash >= SPLASH_SECONDS or (self.splash > 0.4 and badge.pressed()):
                self.state = "title"
            return False

        # Up is settings on every screen, and Up again closes them.
        if pressed(UP):
            if self.state == "settings":
                self.state = self.settings_from
            else:
                self.settings_from = self.state
                self.setting_row = 0
                self.state = "settings"

        if self.state in ("title", "over") or (self.state == "settings" and self.settings_from in ("title", "over")):
            # Aim isn't calibrated until a game starts; keep the view still
            # and let the floor stream by, and build any bot models left.
            self.scroll = (self.scroll + dt * 3.0) % 4.0
            self.build_models(8)

        if self.state == "settings":
            rows = self.settings_rows()
            if pressed(DOWN):
                self.setting_row = (self.setting_row + 1) % len(rows)
            change = pressed(LEFT) or pressed(RIGHT) or pressed(SELECT)
            if change and self.setting_row == 0:
                self.settings["turning"] = "rotate" if self.settings["turning"] == "tilt" else "tilt"
                self.aim.set_mode(self.settings["turning"])
                save_state(self.best, self.settings)
            elif pressed(SELECT) and self.setting_row == 1:
                self.aim.reset_origin()
                self.origin_note = 1.5
            elif pressed(SELECT) and self.setting_row == 2:
                self.state = self.settings_from
            self.origin_note = max(0.0, self.origin_note - dt)
            self.draw_behind_settings()
            if self.state == "settings":
                self.draw_menu("SETTINGS", self.settings_rows(), self.setting_row, 40, True)
                if self.origin_note > 0:
                    screen.font = font.salty
                    screen.pen = WEAPON_PENS[0]
                    centred("Straight ahead is here now", 176)
            return False

        if self.state == "title":
            self.draw_world()
            aim = "Tilt" if self.settings["turning"] == "tilt" else "Turn"
            self.draw_card([
                "REPO DEFENDER",
                "Evil bots are coming for main.",
                "%s to aim. Your weapon fires itself; Down reloads." % aim,
                "Win more weapons and upgrades every release.",
                "Shoot pickups to grab them.",
                "Enter to defend. Best: %d" % self.best,
            ], WEAPON_PENS[0], top=6, left=8, width=WIDTH - 40)
            screen.font = font.salty
            screen.pen = MUTED
            screen.text("Repo Defender v" + VERSION, 6, HEIGHT - 20)
            self.draw_side_tab(UP_Y, "settings", True)
            self.draw_mark(ENTER_X, "check")
            if pressed(SELECT):
                self.start()
            return False

        if self.state == "over":
            self.draw_world()
            self.draw_bots()
            self.draw_card([
                "REPO COMPROMISED",
                self.quip,
                "Reached v0.%d.0. Score %d, best %d" % (self.wave + 1, self.score, self.best),
                "Press enter to try again",
            ], DANGER)
            self.draw_side_tab(UP_Y, "settings")
            self.draw_mark(ENTER_X, "check")
            if pressed(SELECT):
                self.start()
            return False

        if self.state == "upgrade":
            # Frozen until you pick: Left and Right choose, enter takes it.
            if pressed(LEFT):
                self.card = (self.card - 1) % len(self.offers)
            if pressed(RIGHT):
                self.card = (self.card + 1) % len(self.offers)
            if pressed(SELECT):
                self.take_upgrade(*self.offers[self.card])
            self.draw_game()
            if self.state == "upgrade":
                self.draw_upgrades()
            return False

        if self.state == "paused":
            # Everything holds still; Down (or Left and Right) picks, enter confirms.
            if pressed(DOWN) or pressed(RIGHT):
                self.choice = (self.choice + 1) % len(PAUSE_CHOICES)
            if pressed(LEFT):
                self.choice = (self.choice - 1) % len(PAUSE_CHOICES)
            if pressed(SELECT):
                choice = PAUSE_CHOICES[self.choice]
                if choice == "Quit":
                    return True
                if choice == "Restart":
                    self.start()
                    return False
                self.state = "play"
            self.draw_game()
            if self.state == "paused":
                self.draw_menu("PAUSED", PAUSE_CHOICES, self.choice, 40)
            return False

        if pressed(SELECT):
            # Resume is the default, so enter twice is pause and unpause.
            self.state = "paused"
            self.choice = 0
            self.draw_game()
            self.draw_menu("PAUSED", PAUSE_CHOICES, self.choice, 40)
            return False
        self.aim.update(dt)
        if pressed(DOWN):
            self.reload_now()
        if pressed(LEFT):
            self.switch_weapon(-1)
        if pressed(RIGHT):
            self.switch_weapon(1)
        self.update(dt)
        self.draw_game()
        return False

    def start(self):
        self.draw_world()
        self.draw_card(["HOLD STILL", "Calibrating the firewall..."], WEAPON_PENS[1])
        display.update()
        self.build_models()
        self.aim.calibrate(self.settings["turning"])
        self.reset()
        self.state = "play"


def load_state():
    """The best score and the settings, from /state."""
    try:
        with open(STATE_PATH) as f:
            saved = json.load(f)
    except (OSError, ValueError):
        saved = {}
    settings = dict(DEFAULT_SETTINGS)
    # Older versions saved these as "options".
    for key, value in saved.get("settings", saved.get("options", {})).items():
        if key in settings and type(value) == type(settings[key]):
            settings[key] = value
    return int(saved.get("best", 0)), settings


def save_state(best, settings):
    try:
        with open(STATE_PATH, "w") as f:
            json.dump({"best": best, "settings": settings}, f)
    except OSError:
        pass


previous_mode = badge.mode()
previous_clear = badge.default_clear
previous_antialias = screen.antialias
previous_fill_rule = screen.fill_rule
cleaned_up = False


def on_exit():
    """Also called by Badgeware's Home interrupt; safe to call twice."""
    global cleaned_up
    if cleaned_up:
        return
    cleaned_up = True
    badge.default_clear = previous_clear
    badge.mode(previous_mode)
    screen.antialias = previous_antialias
    screen.fill_rule = previous_fill_rule


def update():
    global last_tick
    if pressed(BACK) or pressed(HOME):
        return True
    now = time.ticks_ms()
    dt = min(time.ticks_diff(now, last_tick), 100) / 1000
    last_tick = now
    if game.frame(dt):
        return True
    return None


try:
    badge.mode(HIRES | VSYNC)
    screen.antialias = image.OFF
    # Bot models are many overlapping lines: overlaps add up, not cancel.
    screen.fill_rule = image.NON_ZERO
    badge.default_clear = None
    game = Game()
    last_tick = time.ticks_ms()
    run(update)
finally:
    on_exit()
