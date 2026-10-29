"""Repo Defender: rogue AI bots are coming for your main branch.

Turn your body (or tilt the badge, in options) to aim, about 30 degrees
either way, so it plays seated. Hold Down to fire and press Up to reload
early; weapons you aren't holding slowly refill. Left and Right switch
weapons. Each bot is tinted the colour of the weapon it's weak to, and the
matching weapon does double damage and scores double points. Destroyed bots
sometimes leave a bobbing pickup: shoot it to collect it. After each wave
(a "release") you pick one of three upgrades to your stats. A bot that
reaches you takes a shield if one is charged, or merges itself into main
and costs you health, and at zero the bots own the repo.

It opens on the studio's logo. On the title, enter starts and Up opens the
options: firing (hold Down, or automatic) and turning (rotate, or tilt). In
a game, enter pauses: Up and Down pick, enter confirms, so enter twice is
pause and unpause. Back or Home exits. The best score and the options are
kept in /state/repo_defender.json.
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
REACH = 2.6  # a bot this close has reached you
SPAWN_DISTANCE = 34.0
SPAWN_ARC = 28.0  # bots appear within this many degrees of straight ahead

# --- Weapons and bots ------------------------------------------------------

# rate: shots a second while firing. damage: per pellet. magazine: shots
# before it reloads (a REVERT blast is one shot). radius: how wide a shot hits.
WEAPONS = [
    dict(name="LINT", rgb=(90, 255, 140), rate=7.0, damage=1, pellets=1, spread=0.0, speed=40.0, reach=34.0,
         radius=0.25, magazine=30),
    dict(name="REVIEW", rgb=(100, 170, 255), rate=1.6, damage=3, pellets=1, spread=0.0, speed=32.0, reach=34.0,
         radius=0.5, magazine=4),
    dict(name="REVERT", rgb=(255, 160, 60), rate=1.3, damage=1, pellets=5, spread=7.0, speed=36.0, reach=14.0,
         radius=0.3, magazine=3),
]
# A weapon you aren't holding refills itself: a full magazine in this many
# reload times.
HOLSTER_REFILL = 5.0
# A bot hit by the weapon of its own colour takes this many times the
# damage, and if that hit destroys it, it scores this many times the points.
MATCH = 2

# Each colour has its own way of coming at you. weak: the weapon whose
# colour it wears. hit: health lost on reaching you. weave: degrees it
# sways either side.
BOTS = {
    "forcepush": dict(name="Force-pusher", hp=4, speed=4.6, weave=0.0, size=0.34, weak=0, points=20, hit=10,
                      quip="force-pushed over your history"),
    "node_modules": dict(name="node_modules", hp=18, speed=1.5, weave=0.0, size=0.5, weak=1, points=60, hit=20,
                         quip="installed 40,000 packages into main"),
    "hallucinator": dict(name="Hallucinator", hp=2, speed=2.6, weave=11.0, size=0.34, weak=2, points=15, hit=8,
                         quip="added a package that doesn't exist"),
    "mega": dict(name="Mega-agent", hp=30, speed=1.3, weave=4.0, size=0.8, weak=None, points=150, hit=35,
                 quip="rewrote the whole repo overnight"),
}

# --- Stats and upgrades ------------------------------------------------------

# Where every run starts; upgrades change these.
BASE_STATS = dict(
    fire_rate=1.0,  # times each weapon's own rate
    flat_damage=0,  # added to every pellet
    damage_bonus=0.0,  # increased damage: 0.25 is +25%
    pickup_chance=0.10,  # chance a destroyed bot leaves a pickup
    reload=1.2,  # seconds to refill a magazine
    max_health=100,
    shields=0,  # shield slots
)
MAX_SHIELDS = 3
# Seconds after a bot last reached you before a shield comes back, and
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
    dict(stat="pickup_chance", name="Bug Bounty", flavor="Bots drop loot now. Finders keepers!",
         effect="+8% pickup chance", step=0.08),
    dict(stat="reload", name="Automated PR Review", flavor="Reloads approve themselves. LGTM!",
         effect="15% faster reloads", step=0.85),
    dict(stat="max_health", name="Branch Protection", flavor="main has been hitting the gym.",
         effect="+20 max health, and heals 20", step=20),
    dict(stat="shields", name="Two-Factor Auth", flavor="Bots never have their phone on them.",
         effect="+1 recharging shield", step=1),
]

# Destroyed bots sometimes leave one bobbing where they were. Shoot it before
# it fades to collect it. weight: how often it's the one dropped.
PICKUPS = {
    "pizza": dict(name="PIZZA", rgb=(255, 200, 80), weight=35),  # heals
    "coffee": dict(name="COFFEE", rgb=(200, 140, 90), weight=35),  # overdrive
    "cache": dict(name="CACHE HIT", rgb=(120, 200, 255), weight=20),  # a shield back
    "rmrf": dict(name="rm -rf", rgb=(255, 70, 90), weight=10),  # deletes every bot
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

PAUSE_CHOICES = ["Resume", "Re-centre aim", "Options", "Restart", "Quit"]
DEFAULT_OPTIONS = dict(autofire=False, turning="rotate")

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


def held(b):
    return b is not None and badge.held(b)


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
MEGA_PEN = pen((255, 80, 200))
MEGA_DIM = pen(dim((255, 80, 200), 0.45))
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

    def recentre(self):
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
    def __init__(self, kind, azimuth):
        self.kind = kind
        self.spec = BOTS[kind]
        self.size = self.spec["size"]
        self.home = azimuth
        self.azimuth = azimuth
        self.distance = SPAWN_DISTANCE
        self.hp = self.spec["hp"]
        self.flash = 0.0
        self.matched = False
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


class Game:
    def __init__(self):
        self.aim = Aim()
        self.view = View()
        self.state = "splash"
        self.splash = 0.0
        self.choice = 0
        self.option_row = 0
        self.options_from = "title"
        self.best, self.options = load_state()
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
        kinds = ["forcepush"] * 3 + ["hallucinator"] * 3
        if self.wave >= 1:
            kinds += ["node_modules"] * 2
        self.bots.append(Bot(random.choice(kinds), random.uniform(-SPAWN_ARC, SPAWN_ARC)))

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
        self.say("Release v0.%d.0 shipped with %s. More bots incoming." % (self.wave + 1, upgrade["name"]))
        if self.wave % 3 == 2:
            self.bots.append(Bot("mega", random.uniform(-SPAWN_ARC * 0.6, SPAWN_ARC * 0.6)))
        self.state = "play"

    def reload_now(self):
        """Up: start reloading the weapon in hand, unless it's full or already reloading."""
        i = self.weapon
        if self.reloading[i] <= 0 and self.ammo[i] < WEAPONS[i]["magazine"]:
            self.reloading[i] = self.stats["reload"]

    def hit(self, shot, bot):
        matched = bot.spec["weak"] == shot.index
        damage = (shot.weapon["damage"] + self.stats["flat_damage"]) * (1 + self.stats["damage_bonus"])
        bot.hp -= damage * (MATCH if matched else 1)
        bot.flash = 0.12
        bot.matched = matched
        if bot.hp > 0:
            return
        points = bot.spec["points"] * (MATCH if matched else 1)
        self.score += points
        if matched:
            self.popups.append([bot.azimuth, bot.distance, "MATCH +%d" % points, 1.0, WEAPON_PENS[shot.index]])
        else:
            self.popups.append([bot.azimuth, bot.distance, "+%d" % points, 0.8, TEXT])
        if random.random() < self.stats["pickup_chance"]:
            self.pickups.append(Pickup(self.pickup_kind(), bot.azimuth, max(bot.distance, 5.0)))

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
            # rm -rf: every bot on the field, bar the boss, which had backups.
            gone = [b for b in self.bots if b.hp > 0 and b.kind != "mega"]
            points = sum(b.spec["points"] for b in gone)
            for bot in gone:
                bot.hp = 0
            self.score += points
            self.nuked = 0.5
            self.say("rm -rf deleted %d bots. +%d%s" % (
                len(gone), points, " (the Mega-agent had backups)" if any(b.kind == "mega" for b in self.bots) else ""))
        self.popups.append([pickup.azimuth, pickup.distance, label, 1.0, PICKUP_PENS[pickup.kind]])

    def update(self, dt, trigger):
        """Advances the game; trigger is whether the weapon is firing."""
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

        # Fire while the trigger's held and there's a round in the magazine;
        # emptying it starts a reload.
        w = WEAPONS[self.weapon]
        rate = w["rate"] * self.stats["fire_rate"] * (2 if self.overdrive > 0 else 1)
        self.cooldown -= dt
        while trigger and self.cooldown <= 0 and self.reloading[self.weapon] <= 0 and self.ammo[self.weapon] >= 1:
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
        for bot in self.bots:
            bot.update(dt, self.clock)

        # Hits: a shot sweeps from where it was to where it is this frame,
        # and stops at the first bot or pickup it meets.
        targets = self.pickups + self.bots
        spent = []
        for shot in self.shots:
            for target in targets:
                if getattr(target, "taken", False) or getattr(target, "hp", 1) <= 0:
                    continue
                if not (shot.last - 0.6 <= target.distance <= shot.distance + 0.6):
                    continue
                reach = math.degrees(math.atan((target.size + shot.weapon["radius"]) / max(target.distance, 0.5)))
                if abs(shot.azimuth - target.azimuth) <= reach:
                    if isinstance(target, Pickup):
                        self.collect(target)
                    else:
                        self.hit(shot, target)
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
                    self.say("Two-factor auth turned away a %s." % bot.spec["name"])
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
                save_state(self.best, self.options)

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

    def draw_bots(self):
        view = self.view
        # Far to near, so near bots cover far ones.
        for bot in sorted(self.bots, key=lambda b: -b.distance):
            spec = bot.spec
            at = view.polar(bot.azimuth, bot.distance, 0.6)
            if at is None:
                continue
            x, y, depth = at
            r = spec["size"] * FOCAL / depth
            mega = bot.kind == "mega"
            body = MEGA_DIM if mega else WEAPON_DIM[spec["weak"]]
            glow = MEGA_PEN if mega else WEAPON_PENS[spec["weak"]]
            if x + r < 0 or x - r > WIDTH:
                self.edge_marker(x, y, glow)
                continue
            if bot.flash > 0:
                # A matching hit flashes white; any other just lights it up.
                body = glow = WHITE if bot.matched else glow
            if r < 3:
                screen.pen = glow
                screen.rectangle(int(x) - 1, int(y) - 1, 3, 3)
                continue
            if r < 7:
                # Far off, the antenna and health bar don't show: just the
                # body and a lit visor, in three calls rather than seven.
                screen.pen = body
                screen.rectangle(int(x - r), int(y - r), int(2 * r), int(2 * r))
                screen.pen = glow
                screen.rectangle(int(x - r * 0.6), int(y - r * 0.4), int(r * 1.2), max(1, int(r * 0.35)))
                continue
            screen.pen = body
            screen.rectangle(int(x - r), int(y - r), int(2 * r), int(2 * r))
            screen.pen = BLACK
            screen.rectangle(int(x - r * 0.75), int(y - r * 0.45), int(r * 1.5), int(r * 0.5))
            screen.pen = glow
            eye = max(1, int(r * 0.22))
            screen.rectangle(int(x - r * 0.5), int(y - r * 0.35), eye, eye)
            screen.rectangle(int(x + r * 0.5 - eye), int(y - r * 0.35), eye, eye)
            screen.rectangle(int(x - 1), int(y - r * 1.5), 2, int(r * 0.5))
            if bot.flash > 0 and bot.matched:
                # Sparks off the corners.
                s = max(2, int(r * 0.2))
                for cx, cy in ((x - r, y - r), (x + r, y - r), (x - r, y + r), (x + r, y + r)):
                    screen.rectangle(int(cx) - s // 2, int(cy) - s // 2, s, s)
            # Health, for anything that takes more than one hit.
            if spec["hp"] > 1:
                screen.pen = glow
                screen.rectangle(int(x - r), int(y + r + 2), max(1, int(2 * r * max(bot.hp, 0) / spec["hp"])), 2)

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

    def draw_side_tab(self, y, icon, active=False, progress=None):
        """An overlay on the right edge beside the button at y, showing what
        it does: 'fire', 'reload', 'options', 'up' or 'down'."""
        x0, cx = WIDTH - 24, WIDTH - 11
        screen.pen = PANEL
        screen.rectangle(x0, y - 13, 24, 26)
        lit = WEAPON_PENS[self.weapon] if icon in ("fire", "reload") else WEAPON_PENS[0]
        screen.pen = lit if active else MUTED
        screen.rectangle(x0, y - 13, 2, 26)
        if icon == "fire" and self.options["autofire"]:
            screen.font = font.winds
            centred("auto", y - 6, x0 + 2, 22)
        elif icon == "fire":
            if active:
                screen.circle(cx, y, 6)
                screen.pen = BLACK
            for dx, dy, w, h in ((-6, 0, 4, 1), (3, 0, 4, 1), (0, -6, 1, 4), (0, 3, 1, 4)):
                screen.rectangle(cx + dx, y + dy, w, h)
            screen.rectangle(cx - 1, y - 1, 2, 2)
        elif icon == "reload":
            points = RELOAD_ARC
            if progress is not None:
                lit_count = int(len(points) * progress)
                for i, (px, py) in enumerate(points):
                    screen.pen = lit if i < lit_count else TRACK
                    screen.rectangle(int(cx + px) - 1, int(y + py) - 1, 2, 2)
            else:
                for px, py in points:
                    screen.rectangle(int(cx + px) - 1, int(y + py) - 1, 2, 2)
            ex, ey = points[-1]
            screen.triangle(int(cx + ex) - 3, int(y + ey) - 2, int(cx + ex) + 3, int(y + ey) - 2, int(cx + ex), int(y + ey) + 3)
        elif icon == "options":
            screen.circle(cx, y, 5)
            for k in range(8):
                a = math.radians(k * 45)
                screen.rectangle(int(cx + 6.5 * math.cos(a)) - 1, int(y + 6.5 * math.sin(a)) - 1, 3, 3)
            screen.pen = BLACK
            screen.circle(cx, y, 2)
        else:  # 'up' or 'down': a plain arrowhead
            s = -1 if icon == "up" else 1
            screen.triangle(cx - 6, y - 3 * s, cx + 6, y - 3 * s, cx, y + 4 * s)

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
        lw, _ = screen.measure_text(label)
        screen.text(label, 196 - lw // 2, 4)
        label = "%d" % self.score
        lw, _ = screen.measure_text(label)
        screen.text(label, WIDTH - 6 - lw, 4)

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
        self.draw_side_tab(UP_Y, "reload", reloading, progress)
        self.draw_side_tab(DOWN_Y, "fire", held(DOWN) or self.options["autofire"])

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
        self.draw_bots()
        self.draw_pickups()
        self.draw_shots()
        self.draw_hud()

    def draw_menu(self, title, rows, chosen, top):
        """A panel of rows with the chosen one lit, and Up and Down beside it."""
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
        self.draw_side_tab(UP_Y, "up", True)
        self.draw_side_tab(DOWN_Y, "down", True)
        self.draw_enter_hint()

    def option_rows(self):
        firing = "Automatic" if self.options["autofire"] else "Hold Down"
        turning = "Tilt" if self.options["turning"] == "tilt" else "Rotate"
        return ["Firing: < %s >" % firing, "Turning: < %s >" % turning, "Done"]

    def draw_upgrades(self):
        screen.pen = pen((0, 0, 0), 160)
        screen.rectangle(0, 0, WIDTH, HEIGHT)
        screen.font = font.salty
        screen.pen = WEAPON_PENS[0]
        centred("v0.%d.0 shipped! Pick an upgrade" % (self.wave + 1), 8)
        width, gap, top = 98, 5, 32
        left = (WIDTH - len(self.offers) * width - (len(self.offers) - 1) * gap) // 2
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
        self.draw_pointer(LEFT_X, -1)
        self.draw_pointer(RIGHT_X, 1)
        self.draw_enter_hint()

    def frame(self, dt):
        """Runs and draws one frame; True means quit the app."""
        if self.state == "splash":
            self.splash += dt
            self.draw_splash()
            if self.splash >= SPLASH_SECONDS or (self.splash > 0.4 and badge.pressed()):
                self.state = "title"
            return False

        if self.state in ("title", "over", "options"):
            # Aim isn't calibrated until a game starts; keep the view still
            # and let the floor stream by.
            self.scroll = (self.scroll + dt * 3.0) % 4.0

        if self.state == "title":
            self.draw_world()
            aim = "Tilt" if self.options["turning"] == "tilt" else "Turn"
            fire = "Your weapon fires itself" if self.options["autofire"] else "Hold Down to fire"
            self.draw_card([
                "REPO DEFENDER",
                "Rogue AI bots want your main branch.",
                "%s to aim. %s, Up reloads." % (aim, fire),
                "Left/Right: weapon. Match colours for x2.",
                "Shoot pickups. Upgrade every release.",
                "Enter to defend. Best: %d" % self.best,
            ], WEAPON_PENS[0], top=6, left=8, width=WIDTH - 40)
            screen.font = font.salty
            screen.pen = MUTED
            screen.text("Repo Defender v" + VERSION, 6, HEIGHT - 20)
            self.draw_side_tab(UP_Y, "options", True)
            self.draw_enter_hint()
            if pressed(UP):
                self.open_options("title")
            elif pressed(SELECT):
                self.start()
            return False

        if self.state == "options":
            rows = self.option_rows()
            if pressed(UP):
                self.option_row = (self.option_row - 1) % len(rows)
            if pressed(DOWN):
                self.option_row = (self.option_row + 1) % len(rows)
            change = pressed(LEFT) or pressed(RIGHT) or pressed(SELECT)
            if change and self.option_row == 0:
                self.options["autofire"] = not self.options["autofire"]
                save_state(self.best, self.options)
            elif change and self.option_row == 1:
                self.options["turning"] = "rotate" if self.options["turning"] == "tilt" else "tilt"
                save_state(self.best, self.options)
            elif pressed(SELECT) and self.option_row == 2:
                self.close_options()
                return False
            if self.options_from == "paused":
                self.draw_game()
            else:
                self.draw_world()
            self.draw_menu("OPTIONS", self.option_rows(), self.option_row, 40)
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
            # Everything holds still; Up and Down pick, enter confirms.
            if pressed(UP):
                self.choice = (self.choice - 1) % len(PAUSE_CHOICES)
            if pressed(DOWN):
                self.choice = (self.choice + 1) % len(PAUSE_CHOICES)
            if pressed(SELECT):
                choice = PAUSE_CHOICES[self.choice]
                if choice == "Quit":
                    return True
                if choice == "Restart":
                    self.start()
                    return False
                if choice == "Options":
                    self.open_options("paused")
                    return False
                if choice == "Re-centre aim":
                    self.aim.recentre()
                self.state = "play"
            self.draw_game()
            if self.state == "paused":
                self.draw_menu("PAUSED", PAUSE_CHOICES, self.choice, 20)
            return False

        if pressed(SELECT):
            # Resume is the default, so enter twice is pause and unpause.
            self.state = "paused"
            self.choice = 0
            self.draw_game()
            self.draw_menu("PAUSED", PAUSE_CHOICES, self.choice, 20)
            return False
        self.aim.update(dt)
        if pressed(UP):
            self.reload_now()
        if pressed(LEFT):
            self.weapon = (self.weapon - 1) % len(WEAPONS)
        if pressed(RIGHT):
            self.weapon = (self.weapon + 1) % len(WEAPONS)
        self.update(dt, self.options["autofire"] or held(DOWN))
        self.draw_game()
        return False

    def open_options(self, came_from):
        self.options_from = came_from
        self.option_row = 0
        self.turning_was = self.options["turning"]
        self.state = "options"

    def close_options(self):
        if self.options_from == "paused":
            # Switching how turning works mid-game starts it from straight ahead.
            if self.options["turning"] != self.turning_was:
                self.aim.set_mode(self.options["turning"])
            self.state = "paused"
        else:
            self.state = "title"

    def start(self):
        self.draw_world()
        self.draw_card(["HOLD STILL", "Calibrating the firewall..."], WEAPON_PENS[1])
        display.update()
        self.aim.calibrate(self.options["turning"])
        self.reset()
        self.state = "play"


def load_state():
    """The best score and the options, from /state."""
    try:
        with open(STATE_PATH) as f:
            saved = json.load(f)
    except (OSError, ValueError):
        saved = {}
    options = dict(DEFAULT_OPTIONS)
    for key, value in saved.get("options", {}).items():
        if key in options and type(value) == type(options[key]):
            options[key] = value
    return int(saved.get("best", 0)), options


def save_state(best, options):
    try:
        with open(STATE_PATH, "w") as f:
            json.dump({"best": best, "options": options}, f)
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
