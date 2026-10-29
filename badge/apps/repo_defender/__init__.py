"""Repo Defender: bugs, hallucinations and worse are coming for your main branch.

Turn your body (or tilt the badge, in settings) to aim, about 30 degrees
either way, so it plays seated. Your weapon fires by itself; Left and Right
switch weapons and Down reloads early, and weapons you aren't holding slowly
refill. Each enemy comes at you its own way: bugs scuttle straight in fast,
node_modules boxes slide in slow and heavy, hallucinations sway side to side,
and now and then a rogue agent lumbers in. Destroyed enemies sometimes leave
a bobbing pickup: shoot it to collect it. After each wave (a "release") you
pick one of three upgrades to your stats. An enemy that reaches you takes a
shield if one is charged, or merges itself into main and costs you health,
and at zero main belongs to them.

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
VERSION = "0.2.0"

# --- Aim -------------------------------------------------------------------

# Raw gyro units per degree a second. Two full turns, holding the badge as
# you play, measured 107 and 110 (the gyro's +-250 degree/s setting is 114).
GYRO_LSB_PER_DPS = 110.0
# A left turn reads positive around the accelerometer's "down", and aim
# (positive to the right) should follow it left: so -1. Everything (grid,
# skyline, enemies, shots, hits) goes through the one View, so flipping this
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
# Positive tips the right edge down, and turns right.
TILT_DPS = 70.0
TILT_DEADZONE = 0.08
TILT_FULL = 0.5
TILT_SIGN = 1

# --- View ------------------------------------------------------------------

WIDTH, HEIGHT = 320, 240
HFOV = 50.0
FOCAL = (WIDTH / 2) / math.tan(math.radians(HFOV / 2))
HORIZON = 92
EYE = 1.0  # camera height, in world units
REACH = 2.6  # an enemy this close has reached you
SPAWN_DISTANCE = 34.0
SPAWN_ARC = 28.0  # enemies appear within this many degrees of straight ahead

# --- Weapons and enemies -----------------------------------------------------

# Weapons fire by themselves. rate: shots a second. damage: per pellet.
# magazine: shots before it reloads (a REVERT blast is one shot). radius: how
# wide a shot hits. pierce: carries on through everything in its path.
WEAPONS = [
    dict(name="LINT", rgb=(90, 255, 140), rate=7.0, damage=1, pellets=1, spread=0.0, speed=40.0, reach=34.0,
         radius=0.25, magazine=30, pierce=False),
    dict(name="REVIEW", rgb=(100, 170, 255), rate=1.6, damage=5, pellets=1, spread=0.0, speed=32.0, reach=34.0,
         radius=0.5, magazine=4, pierce=True),
    dict(name="REVERT", rgb=(255, 160, 60), rate=1.3, damage=1, pellets=5, spread=7.0, speed=36.0, reach=14.0,
         radius=0.3, magazine=3, pierce=False),
]
# A weapon you aren't holding refills itself: a full magazine in this many
# reload times.
HOLSTER_REFILL = 5.0

# Each enemy comes at you its own way. hit: health lost on reaching you.
# weave: degrees it sways either side. height: where its middle floats.
ENEMIES = {
    "bug": dict(name="A bug", hp=4, speed=4.6, weave=0.0, size=0.34, height=0.32, points=20, hit=10,
                quip="made it into prod", rgb=(220, 60, 70)),
    "node_modules": dict(name="node_modules", hp=15, speed=1.5, weave=0.0, size=0.55, height=0.55, points=50, hit=20,
                         quip="installed 40,000 packages into main", rgb=(200, 150, 90)),
    "hallucination": dict(name="A hallucination", hp=2, speed=2.6, weave=11.0, size=0.36, height=0.85, points=15, hit=8,
                          quip="added a package that doesn't exist", rgb=(215, 215, 245)),
    "agent": dict(name="The rogue agent", hp=30, speed=1.3, weave=4.0, size=0.85, height=0.95, points=150, hit=35,
                  quip="rewrote the whole repo overnight", rgb=(255, 80, 200)),
}

# --- Stats and upgrades ------------------------------------------------------

# Where every run starts; upgrades change these.
BASE_STATS = dict(
    fire_rate=1.0,  # times each weapon's own rate
    flat_damage=0,  # added to every pellet
    damage_bonus=0.0,  # increased damage: 0.25 is +25%
    pickup_chance=0.10,  # chance a destroyed enemy leaves a pickup
    reload=1.2,  # seconds to refill a magazine
    max_health=100,
    shields=0,  # shield slots
)
MAX_SHIELDS = 3
# Seconds after an enemy last reached you before a shield comes back, and
# between each one after that.
SHIELD_RECHARGE = 8.0

# Offered three at a time after each wave. step is what one pick adds, or
# for reload, what it multiplies by.
UPGRADES = [
    dict(stat="fire_rate", name="Larger Runners", flavor="Your CI finally got the good machines.",
         effect="+15% fire rate", step=0.15),
    dict(stat="flat_damage", name="CODEOWNERS", flavor="Nothing gets through without your say-so.",
         effect="+1 damage on every hit", step=1),
    dict(stat="damage_bonus", name="Copilot", flavor="Fight AI with AI. Seems only fair.",
         effect="+25% damage", step=0.25),
    dict(stat="pickup_chance", name="Bug Bounty", flavor="Bugs drop loot now. Finders keepers!",
         effect="+8% pickup chance", step=0.08),
    dict(stat="reload", name="Automated PR Review", flavor="Reloads approve themselves. LGTM!",
         effect="15% faster reloads", step=0.85),
    dict(stat="max_health", name="Branch Protection", flavor="main has been hitting the gym.",
         effect="+20 max health, and heals 20", step=20),
    dict(stat="shields", name="Two-Factor Auth", flavor="Bugs never have their phone on them.",
         effect="+1 recharging shield", step=1),
]

# Destroyed enemies sometimes leave one bobbing where they were. Shoot it
# before it fades to collect it. weight: how often it's the one dropped.
PICKUPS = {
    "pizza": dict(name="PIZZA", rgb=(255, 200, 80), weight=35),  # heals
    "coffee": dict(name="COFFEE", rgb=(200, 140, 90), weight=35),  # overdrive
    "cache": dict(name="CACHE HIT", rgb=(120, 200, 255), weight=20),  # a shield back
    "rmrf": dict(name="rm -rf", rgb=(255, 70, 90), weight=10),  # deletes every enemy
}
PICKUP_SECONDS = 4.5
PICKUP_SIZE = 0.4
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
# docs/button_positions.json): Left, Right and enter (printed with a return
# arrow) below the bottom edge at these x, Up and Down beside the right edge
# at these y.
LEFT_X = 59
RIGHT_X = 163
ENTER_X = 255
UP_Y = 72
DOWN_Y = 167
# The return-arrow glyph printed beside enter, as one stroke in a 26 x 16
# box: a short bar along the top, a hook down the right, and a long bar back
# along the bottom to an arrowhead pointing left.
ENTER_GLYPH_SIZE = (26, 16)


def enter_glyph_points():
    w, h = ENTER_GLYPH_SIZE
    r = h / 2
    points = [(x, 0.0) for x in range(int(w * 0.45), int(w - r))]
    for k in range(17):
        a = -math.pi / 2 + math.pi * k / 16
        points.append((w - r + r * math.cos(a), r + r * math.sin(a)))
    points += [(x, float(h)) for x in range(int(w - r), 0, -1)]
    for k in range(1, 6):  # the arrowhead's two barbs
        points += [(k, h - k), (k, h + k)]
    return points


ENTER_GLYPH = enter_glyph_points()
# Reload's icon: most of a circle, ending in an arrowhead.
RELOAD_ARC = [(5.5 * math.cos(math.radians(a)), 5.5 * math.sin(math.radians(a))) for a in range(40, 360, 20)]

WAVE_SECONDS = 25.0
GAME_OVER_LINES = [
    "main now has 4,096 open PRs.",
    "Your README is now a poem about bugs.",
    "CI passes. Nothing else does.",
    "node_modules is now bigger than the repo.",
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
ENEMY_PENS = {kind: pen(e["rgb"]) for kind, e in ENEMIES.items()}
BUG_DARK = pen((90, 20, 30))
BUG_LEGS = pen((240, 120, 120))
BOX_TOP = pen((225, 180, 120))
BOX_SIDE = pen((160, 115, 65))
TAPE = pen((235, 215, 160))
DENT = pen((110, 75, 40))
GHOST_DIM = pen((165, 165, 205))
GHOST_EYES = pen((40, 30, 70))
AGENT_BODY = pen((60, 52, 80))
TERMINAL = WEAPON_PENS[0]
ANTENNA_LIGHT = pen((255, 60, 60))
PICKUP_PENS = {kind: pen(p["rgb"]) for kind, p in PICKUPS.items()}
SHIELD_PEN = pen(PICKUPS["cache"]["rgb"])
SHIELD_DIM = pen(dim(PICKUPS["cache"]["rgb"], 0.35))
CRUST = pen((190, 110, 50))
PEPPERONI = pen((210, 50, 50))
CUP = pen((235, 225, 210))
COFFEE = pen((110, 65, 35))
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


def stepped(upgrade, value):
    return value * upgrade["step"] if upgrade["stat"] == "reload" else value + upgrade["step"]


def stat_text(stat, value):
    if stat in ("fire_rate", "pickup_chance"):
        return "%d%%" % round(value * 100)
    if stat == "damage_bonus":
        return "+%d%%" % round(value * 100)
    if stat == "flat_damage":
        return "+%d" % value
    if stat == "reload":
        return "%.2fs" % value
    return "%d" % value


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


class Enemy:
    def __init__(self, kind, azimuth):
        self.kind = kind
        self.spec = ENEMIES[kind]
        self.size = self.spec["size"]
        self.home = azimuth
        self.azimuth = azimuth
        self.distance = SPAWN_DISTANCE
        self.hp = self.spec["hp"]
        self.flash = 0.0
        self.phase = random.uniform(0, 6.28)

    def update(self, dt, t):
        self.distance -= self.spec["speed"] * dt
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
    def __init__(self, weapon, index, azimuth):
        self.weapon = weapon
        self.index = index
        self.azimuth = azimuth
        self.distance = REACH
        self.last = REACH
        self.struck = []  # enemies a piercing shot has already hit


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
        self.enemies = []
        self.shots = []
        self.pickups = []
        self.popups = []
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

    def spawn(self):
        kinds = ["bug"] * 3 + ["hallucination"] * 3
        if self.wave >= 1:
            kinds += ["node_modules"] * 2
        self.enemies.append(Enemy(random.choice(kinds), random.uniform(-SPAWN_ARC, SPAWN_ARC)))

    def offer_upgrades(self):
        """Freezes the game on three different upgrades to choose from."""
        pool = [u for u in UPGRADES if not (u["stat"] == "shields" and self.stats["shields"] >= MAX_SHIELDS)]
        self.offers = []
        while pool and len(self.offers) < 3:
            pick = random.choice(pool)
            pool.remove(pick)
            self.offers.append(pick)
        self.card = len(self.offers) // 2
        self.state = "upgrade"

    def take_upgrade(self, upgrade):
        stat = upgrade["stat"]
        self.stats[stat] = stepped(upgrade, self.stats[stat])
        if stat == "max_health":
            self.health = min(self.stats["max_health"], self.health + upgrade["step"])
        elif stat == "shields":
            self.shields += 1  # a new shield arrives charged
        self.say("Release v0.%d.0 shipped with %s. More incoming." % (self.wave + 1, upgrade["name"]))
        if self.wave % 3 == 2:
            self.enemies.append(Enemy("agent", random.uniform(-SPAWN_ARC * 0.6, SPAWN_ARC * 0.6)))
        self.state = "play"

    def reload_now(self):
        """Down: start reloading the weapon in hand, unless it's full or already reloading."""
        i = self.weapon
        if self.reloading[i] <= 0 and self.ammo[i] < WEAPONS[i]["magazine"]:
            self.reloading[i] = self.stats["reload"]

    def hit(self, shot, enemy):
        enemy.hp -= (shot.weapon["damage"] + self.stats["flat_damage"]) * (1 + self.stats["damage_bonus"])
        enemy.flash = 0.12
        if enemy.hp > 0:
            return
        points = enemy.spec["points"]
        self.score += points
        self.popups.append([enemy.azimuth, enemy.distance, "+%d" % points, 0.8, TEXT])
        if random.random() < self.stats["pickup_chance"]:
            self.pickups.append(Pickup(self.pickup_kind(), enemy.azimuth, max(enemy.distance, 5.0)))

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
            self.overdrive = OVERDRIVE_SECONDS
            label = "COFFEE: OVERDRIVE"
        else:
            # rm -rf: everything on the field, bar the rogue agent, which had backups.
            gone = [e for e in self.enemies if e.hp > 0 and e.kind != "agent"]
            points = sum(e.spec["points"] for e in gone)
            for enemy in gone:
                enemy.hp = 0
            self.score += points
            self.nuked = 0.5
            self.say("rm -rf deleted %d. +%d%s" % (
                len(gone), points, " (the rogue agent had backups)" if any(e.kind == "agent" for e in self.enemies) else ""))
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
        for i, weapon in enumerate(WEAPONS):
            if self.reloading[i] > 0:
                self.reloading[i] -= dt
                if self.reloading[i] <= 0:
                    self.reloading[i] = 0.0
                    self.ammo[i] = float(weapon["magazine"])
            elif i != self.weapon and self.ammo[i] < weapon["magazine"]:
                refill = weapon["magazine"] / (HOLSTER_REFILL * self.stats["reload"])
                self.ammo[i] = min(float(weapon["magazine"]), self.ammo[i] + refill * dt)

        # The weapon in hand fires whenever it has a round; emptying the
        # magazine starts a reload.
        w = WEAPONS[self.weapon]
        rate = w["rate"] * self.stats["fire_rate"] * (2 if self.overdrive > 0 else 1)
        self.cooldown -= dt
        while self.cooldown <= 0 and self.reloading[self.weapon] <= 0 and self.ammo[self.weapon] >= 1:
            self.cooldown += 1.0 / rate
            for p in range(w["pellets"]):
                offset = 0.0 if w["pellets"] == 1 else w["spread"] * (p / (w["pellets"] - 1) * 2 - 1)
                self.shots.append(Shot(w, self.weapon, self.aim.yaw + offset))
            self.ammo[self.weapon] -= 1
            if self.ammo[self.weapon] < 1:
                self.reloading[self.weapon] = self.stats["reload"]
        self.cooldown = max(self.cooldown, 0.0)

        for shot in self.shots:
            shot.last = shot.distance
            shot.distance += shot.weapon["speed"] * dt
        for enemy in self.enemies:
            enemy.update(dt, self.clock)

        # Hits: a shot sweeps from where it was to where it is this frame. It
        # stops at the first enemy or pickup it meets, unless it pierces.
        targets = self.pickups + self.enemies
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

        # Enemies that reach you hit a shield if one's charged, or merge into main.
        alive = []
        for enemy in self.enemies:
            if enemy.hp <= 0:
                continue
            if enemy.distance <= REACH:
                self.shield_timer = SHIELD_RECHARGE
                if self.shields > 0:
                    self.shields -= 1
                    self.blocked = 0.35
                    self.say("Two-factor auth stopped %s." % enemy.spec["name"].lower())
                else:
                    self.health -= enemy.spec["hit"]
                    self.hurt = 0.35
                    self.say("%s %s. -%d" % (enemy.spec["name"], enemy.spec["quip"], enemy.spec["hit"]))
            else:
                alive.append(enemy)
        self.enemies = alive

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
        # Sky bands, then the floor.
        band = HORIZON // 3
        for i, p in enumerate(SKY):
            screen.pen = p
            screen.rectangle(0, i * band, WIDTH, band + 1)
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

    def draw_enemies(self):
        view = self.view
        t = time.ticks_ms() / 1000
        # Far to near, so near ones cover far ones.
        for enemy in sorted(self.enemies, key=lambda e: -e.distance):
            spec = enemy.spec
            at = view.polar(enemy.azimuth, enemy.distance, spec["height"])
            if at is None:
                continue
            x, y, depth = at
            r = spec["size"] * FOCAL / depth
            if x + r < 0 or x - r > WIDTH:
                self.edge_marker(x, y, ENEMY_PENS[enemy.kind])
                continue
            main = WHITE if enemy.flash > 0 else ENEMY_PENS[enemy.kind]
            if r < 9:
                # Far off, detail doesn't show: one shape, in a call or two.
                screen.pen = main
                if enemy.kind == "node_modules":
                    screen.rectangle(int(x - r), int(y - r), int(2 * r), int(2 * r))
                else:
                    screen.circle(int(x), int(y), max(1, int(r * 0.8)))
                continue
            if enemy.kind == "bug":
                self.draw_bug(x, y, r, main, enemy, t)
            elif enemy.kind == "node_modules":
                self.draw_box(x, y, r, main, enemy)
            elif enemy.kind == "hallucination":
                self.draw_ghost(x, y, r, main, enemy, t)
            else:
                self.draw_agent(x, y, r, main, t)
            # Health, for anything that takes more than a couple of hits.
            if spec["hp"] > 2:
                screen.pen = TRACK
                screen.rectangle(int(x - r), int(y + r + 3), int(2 * r), 2)
                screen.pen = ENEMY_PENS[enemy.kind]
                screen.rectangle(int(x - r), int(y + r + 3), max(1, int(2 * r * max(enemy.hp, 0) / spec["hp"])), 2)

    def draw_bug(self, x, y, r, main, enemy, t):
        """A beetle scuttling at you: legs going, shell behind its head."""
        wiggle = r * 0.18 * math.sin(t * 20 + enemy.phase)
        screen.pen = BUG_LEGS
        strokes = (0, 1) if r >= 18 else (0,)  # thicker legs only up close
        for k, ly in enumerate((-0.35, 0.05, 0.45)):
            dy = wiggle if k % 2 else -wiggle
            for o in strokes:
                screen.line(x - r * 0.55, y + ly * r + o, x - r * 1.2, y + ly * r + r * 0.25 + dy + o)
                screen.line(x + r * 0.55, y + ly * r + o, x + r * 1.2, y + ly * r + r * 0.25 - dy + o)
        screen.pen = main
        screen.circle(int(x), int(y - r * 0.15), int(r * 0.8))
        screen.pen = BUG_DARK
        screen.rectangle(int(x) - 1, int(y - r * 0.9), 2, int(r * 0.9))
        screen.circle(int(x), int(y + r * 0.45), int(r * 0.42))
        screen.line(x - r * 0.15, y + r * 0.1, x - r * 0.55, y - r * 0.55)  # antennae
        screen.line(x + r * 0.15, y + r * 0.1, x + r * 0.55, y - r * 0.55)
        screen.pen = WHITE
        eye = max(1, int(r * 0.11))
        screen.circle(int(x - r * 0.16), int(y + r * 0.4), eye)
        screen.circle(int(x + r * 0.16), int(y + r * 0.4), eye)

    def draw_box(self, x, y, r, main, enemy):
        """node_modules: the heaviest object in the universe, as a cardboard
        box sliding at you. It dents as it takes damage."""
        s, top = r, r * 0.4
        screen.pen = BOX_TOP
        screen.triangle(int(x - s), int(y - s), int(x + s), int(y - s), int(x + s * 0.75), int(y - s - top))
        screen.triangle(int(x - s), int(y - s), int(x + s * 0.75), int(y - s - top), int(x - s * 0.75), int(y - s - top))
        screen.pen = main
        screen.rectangle(int(x - s), int(y - s), int(2 * s), int(2 * s))
        screen.pen = BOX_SIDE
        screen.rectangle(int(x + s) - 2, int(y - s), 2, int(2 * s))
        screen.pen = TAPE
        tape = max(2, int(s * 0.22))
        screen.rectangle(int(x) - tape // 2, int(y - s), tape, int(s * 0.9))
        screen.triangle(int(x) - tape // 2, int(y - s), int(x) + tape // 2, int(y - s), int(x), int(y - s - top))
        # The label, with its name once it's big enough to read.
        screen.pen = BLACK
        screen.rectangle(int(x - s * 0.8), int(y + s * 0.15), int(s * 1.6), int(s * 0.5))
        if s >= 38:
            screen.font = font.winds
            screen.pen = WHITE
            tw, th = screen.measure_text("node_modules")
            screen.text("node_modules", int(x) - tw // 2, int(y + s * 0.4) - th // 2)
        dents = int(4 * (1 - max(enemy.hp, 0) / enemy.spec["hp"]))
        screen.pen = DENT
        for k in range(dents):
            dx = ((k * 37 + int(enemy.phase * 10)) % 13 - 6) / 7.0
            dy = ((k * 23 + int(enemy.phase * 7)) % 9 - 4) / 6.0
            screen.circle(int(x + dx * s * 0.7), int(y - s * 0.4 + dy * s * 0.3), max(1, int(s * 0.12)))

    def draw_ghost(self, x, y, r, main, enemy, t):
        """A hallucination: a wobbly ghost that isn't quite there."""
        body = main if enemy.flash > 0 or int(t * 8 + enemy.phase) % 5 else GHOST_DIM
        screen.pen = body
        screen.circle(int(x), int(y - r * 0.2), int(r * 0.8))
        screen.rectangle(int(x - r * 0.8), int(y - r * 0.2), int(r * 1.6), int(r * 0.85))
        for k in (-1, 0, 1):  # the wavy hem
            screen.circle(int(x + k * r * 0.53), int(y + r * 0.65 + r * 0.06 * math.sin(t * 6 + k)), int(r * 0.27))
        screen.pen = GHOST_EYES
        screen.circle(int(x - r * 0.3), int(y - r * 0.25), max(1, int(r * 0.15)))
        screen.circle(int(x + r * 0.3), int(y - r * 0.25), max(1, int(r * 0.15)))
        screen.circle(int(x), int(y + r * 0.15), max(1, int(r * 0.1)))
        if r >= 14:
            screen.font = font.salty
            screen.pen = body
            screen.text("?", int(x + r * 0.6), int(y - r * 1.4))

    def draw_agent(self, x, y, r, main, t):
        """The rogue agent: a big robot with a terminal for a face."""
        screen.pen = main
        screen.rectangle(int(x - r), int(y - r * 0.85), int(2 * r), int(r * 1.7))
        screen.line(x, y - r * 0.85, x, y - r * 1.35)
        screen.pen = ANTENNA_LIGHT if int(t * 3) % 2 else BUG_DARK
        screen.circle(int(x), int(y - r * 1.4), max(2, int(r * 0.1)))
        screen.pen = AGENT_BODY
        screen.rectangle(int(x - r) + 3, int(y - r * 0.85) + 3, int(2 * r) - 6, int(r * 1.7) - 6)
        screen.pen = BLACK
        screen.rectangle(int(x - r * 0.75), int(y - r * 0.6), int(r * 1.5), int(r * 1.05))
        # Its face: a prompt, with the cursor blinking.
        screen.pen = TERMINAL
        k = max(2, int(r * 0.12))
        px, py = int(x - r * 0.5), int(y - r * 0.1)
        for i in range(3):  # the ">": two strokes meeting at its point
            screen.rectangle(px + i * k, py - 2 * k + i * k, k, k)
            screen.rectangle(px + i * k, py + 2 * k - i * k, k, k)
        if int(t * 2) % 2:
            screen.rectangle(int(x), py + k, int(r * 0.35), k)

    def draw_pickups(self):
        t = time.ticks_ms() / 1000
        for pickup in self.pickups:
            # Fading out: blink through the last second.
            if pickup.life < 1.0 and int(pickup.life * 10) % 2:
                continue
            # Pickups bob up and down, which enemies never do.
            at = self.view.polar(pickup.azimuth, pickup.distance, 0.75 + 0.25 * math.sin(t * 3.0 + pickup.phase))
            if at is None:
                continue
            x, y, depth = at
            r = max(4, int(pickup.size * FOCAL / depth))
            if x + r < 0 or x - r > WIDTH:
                self.edge_marker(x, y, PICKUP_PENS[pickup.kind])
                continue
            if pickup.kind == "pizza":
                screen.pen = PICKUP_PENS["pizza"]
                screen.triangle(int(x - r), int(y - r * 0.6), int(x + r), int(y - r * 0.6), int(x), int(y + r))
                screen.pen = CRUST
                screen.rectangle(int(x - r), int(y - r * 0.85), int(2 * r), max(2, int(r * 0.3)))
                screen.pen = PEPPERONI
                for px, py in ((-0.35, -0.3), (0.3, -0.25), (0.0, 0.25)):
                    screen.circle(int(x + px * r), int(y + py * r), max(1, int(r * 0.17)))
            elif pickup.kind == "coffee":
                screen.pen = CUP
                screen.rectangle(int(x - r * 0.6), int(y - r * 0.4), int(r * 1.2), int(r * 1.1))
                screen.circle(int(x + r * 0.75), int(y + r * 0.1), max(2, int(r * 0.3)))
                screen.pen = FLOOR
                screen.circle(int(x + r * 0.75), int(y + r * 0.1), max(1, int(r * 0.15)))
                screen.pen = COFFEE
                screen.rectangle(int(x - r * 0.6), int(y - r * 0.4), int(r * 1.2), max(2, int(r * 0.25)))
                screen.pen = CUP
                for k in range(3):  # steam
                    sway = int(r * 0.15 * math.sin(t * 6 + k))
                    screen.rectangle(int(x - r * 0.25) + sway, int(y - r * 0.65 - k * r * 0.2), 2, 2)
                    screen.rectangle(int(x + r * 0.2) - sway, int(y - r * 0.6 - k * r * 0.2), 2, 2)
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

        # Weapons, each with its ammo, or how far along its reload is.
        x = 6
        for i, weapon in enumerate(WEAPONS):
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
                done = self.ammo[i] / weapon["magazine"]
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

    def draw_pointer(self, x, chevron=0):
        """A glowing arrow bobbing down at the button below the screen at x,
        with a chevron over it for Left (-1) or Right (1)."""
        tip = HEIGHT - 4 + int(3 * math.sin(time.ticks_ms() / 1000 * 6.0))
        for stroke, p in self.glow_pens():
            screen.pen = p
            screen.rectangle(x - stroke // 2, tip - 24, stroke, 20)
            for k in range(8):
                screen.rectangle(x - k - stroke // 2, tip - 4 - k - stroke // 2, stroke, stroke)
                screen.rectangle(x + k - stroke // 2, tip - 4 - k - stroke // 2, stroke, stroke)
            # The chevron's point sits on the side it names, over the shaft.
            for k in range(9 if chevron else 0):
                cx = x + chevron * (4 - abs(k - 4) * 2)
                screen.rectangle(cx - stroke // 2, tip - 44 + k * 2 - stroke // 2, stroke, stroke)

    def draw_enter_hint(self):
        """A glowing return arrow, like the one printed on the badge, in the
        bottom right corner, and an arrow down at the enter button itself."""
        gw, gh = ENTER_GLYPH_SIZE
        gx, gy = WIDTH - gw - 10, HEIGHT - gh - 12
        for stroke, p in self.glow_pens():
            screen.pen = p
            for x, y in ENTER_GLYPH:
                screen.rectangle(int(gx + x - stroke / 2), int(gy + y - stroke / 2), stroke, stroke)
        self.draw_pointer(ENTER_X)

    def draw_game(self):
        self.draw_world()
        self.draw_enemies()
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
        self.draw_enter_hint()

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
        for i, upgrade in enumerate(self.offers):
            x = left + i * (width + gap)
            chosen = i == self.card
            y = top - (4 if chosen else 0)
            screen.pen = WEAPON_PENS[0] if chosen else TRACK
            screen.rectangle(x - 2, y - 2, width + 4, 158)
            screen.pen = pen((10, 14, 30))
            screen.rectangle(x, y, width, 154)
            screen.font = font.salty
            screen.pen = WEAPON_PENS[0] if chosen else TEXT
            ty = y + 5
            for line in wrap(upgrade["name"], width - 10):
                screen.text(line, x + 5, ty)
                ty += 15
            screen.font = font.winds
            screen.pen = MUTED
            ty += 4
            for line in wrap(upgrade["flavor"], width - 10):
                screen.text(line, x + 5, ty)
                ty += 12
            screen.pen = TEXT
            ty += 5
            for line in wrap(upgrade["effect"], width - 10):
                screen.text(line, x + 5, ty)
                ty += 12
            stat = upgrade["stat"]
            now = self.stats[stat]
            screen.pen = WEAPON_PENS[0] if chosen else MUTED
            screen.text(stat_text(stat, now) + " -> " + stat_text(stat, stepped(upgrade, now)), x + 5, y + 138)
        self.draw_side_tab(UP_Y, "settings")
        self.draw_pointer(LEFT_X, -1)
        self.draw_pointer(RIGHT_X, 1)
        self.draw_enter_hint()

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
            # and let the floor stream by.
            self.scroll = (self.scroll + dt * 3.0) % 4.0

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
                "Bugs and worse are coming for main.",
                "%s to aim. Your weapons fire themselves." % aim,
                "Left/Right: weapon. Down: reload.",
                "Shoot pickups. Upgrade every release.",
                "Enter to defend. Best: %d" % self.best,
            ], WEAPON_PENS[0], top=6, left=8, width=WIDTH - 40)
            screen.font = font.salty
            screen.pen = MUTED
            screen.text("Repo Defender v" + VERSION, 6, HEIGHT - 20)
            self.draw_side_tab(UP_Y, "settings", True)
            self.draw_enter_hint()
            if pressed(SELECT):
                self.start()
            return False

        if self.state == "over":
            self.draw_world()
            self.draw_enemies()
            self.draw_card([
                "REPO COMPROMISED",
                self.quip,
                "Reached v0.%d.0. Score %d, best %d" % (self.wave + 1, self.score, self.best),
                "Press enter to try again",
            ], DANGER)
            self.draw_side_tab(UP_Y, "settings")
            self.draw_enter_hint()
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
                self.take_upgrade(self.offers[self.card])
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
            self.weapon = (self.weapon - 1) % len(WEAPONS)
        if pressed(RIGHT):
            self.weapon = (self.weapon + 1) % len(WEAPONS)
        self.update(dt)
        self.draw_game()
        return False

    def start(self):
        self.draw_world()
        self.draw_card(["HOLD STILL", "Calibrating the firewall..."], WEAPON_PENS[1])
        display.update()
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
    badge.default_clear = None
    game = Game()
    last_tick = time.ticks_ms()
    run(update)
finally:
    on_exit()
