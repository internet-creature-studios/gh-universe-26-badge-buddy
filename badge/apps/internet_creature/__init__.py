"""Internet Creature Studios: the studio's hills, drawn live as parallax layers.

Tilt steers them. Held level they drift left at the site's pace; tip the
badge left and they race away left, tip it right and they race right.

Launch from the normal badge menu. It's made to be left running, so no single
press leaves it: any button shows "press ↩ twice to exit", and pressing enter
(the button printed with ↩) twice in a row does. Home still leaves, as the
firmware handles it. Assets stay local; this app does not connect to the
network or save state.

The hills are four depth bands of the site's terrain, each baked into a strip
that wraps seamlessly (examples/internet-creature-studios/render_layers.py in
the gh-universe-26-badge-buddy repo). Every drawn frame repaints
the sky behind the far crests, then the strips far to near, each slid by its
own parallax speed, then the part of the logo the hills pass behind. The sky
above never changes, and the screen keeps its contents between refreshes, so
it is drawn once.
"""

import json
import math
import time


with open("assets/scene.json") as scene_file:
    scene = json.load(scene_file)

WIDTH = int(scene["width"])
if (WIDTH, int(scene["height"])) != (320, 240):
    raise ValueError("Internet Creature scene must be 320 x 240")

SKY_BAND_AT = vec2(0, scene["sky_top"])

# Speed is a multiple of each layer's drift, which is the site's pace and
# leftward. Full tilt either way races the hills past at RACE times it.
RACE = 24.0
# The menu's tilt reading, -ax against gravity, is full at about 30 degrees
# and positive when the left edge dips (docs/hardware.md). TILT_SIGN turns it
# into positive for a right tip, which races the hills right. It was 1 until
# play showed the hills running the opposite way to the tip.
GRAVITY = 16384.0
TILT_SIGN = -1
TILT_DEADZONE = 0.12
# Tilt past the dead zone is raised to this power, so a small tip nudges the
# hills and only a firm one sends them racing.
TILT_CURVE = 1.6
# Time constant for easing toward the tilt's speed, so the hills carry some
# momentum instead of snapping.
RESPONSE_MS = 300
# A layer moving a blur length or more per drawn frame shows that motion-
# blurred copy, and drops back below this fraction of it.
BLUR_RELEASE = 0.7


def optional_button(name):
    # Badgeware's button names resolve like builtins but aren't in builtins'
    # or the app's namespace, so getattr and globals() miss them. Evaluating
    # the name finds them; not every firmware has Menu or Back.
    try:
        return eval(name)
    except NameError:
        return None


ENTER = optional_button("BUTTON_SELECT")
# How to leave: any press shows the hint for HINT_MS, and a press of enter
# within HINT_MS of the one before leaves. The hint sits at the bottom, where
# the nearest hills repaint every row each frame, so redrawing them wipes it.
HINT_MS = 3000
HINT_TEXT = ("press ", " twice to exit")  # either side of the return arrow
HINT_TOP = 206
HINT_RIGHT = 304
ENTER_X = 255  # where enter sits below the screen (docs/button_positions.json)
PINK = color.rgb(242, 112, 159)  # the logo's :3
HINT_PANEL = color.rgb(20, 24, 40, 170)
WHITE = color.rgb(255, 255, 255)
# The return arrow printed beside enter, as points along one stroke in a
# 16 x 10 box: a bar along the top, a hook down the right, and a bar back
# along the bottom to an arrowhead pointing left.
ARROW_W, ARROW_H = 16, 10
ARROW = [(x, 0) for x in range(7, 11)]
ARROW += [(11 + 5 * math.cos(a / 8 * math.pi - math.pi / 2), 5 + 5 * math.sin(a / 8 * math.pi - math.pi / 2))
          for a in range(9)]
ARROW += [(x, 10) for x in range(10, 0, -1)]
ARROW += [(k, 10 - k) for k in range(1, 4)] + [(k, 10 + k) for k in range(1, 4)]
# Simulators may not model the IMU; without one the hills keep their drift.
READ_IMU = getattr(badge, "imu", None)

previous_mode = badge.mode()
previous_antialias = screen.antialias
previous_clear = badge.default_clear
cleaned_up = False


class Layer:
    """One depth band: a strip that wraps, slid by its own parallax speed."""

    def __init__(self, spec):
        name = spec["name"]
        self.top = spec["top"]
        self.width = spec["width"]
        self.drift = spec["drift"]
        self.blur_lengths = spec["blur"]
        # The sharp strip, then its motion-blurred copies, shortest first.
        self.images = [image.load("assets/layers/%s.png" % name)] + [
            image.load("assets/layers/%s_b%d.png" % (name, n)) for n in range(1, len(self.blur_lengths) + 1)
        ]
        # Each image as tiles cropped to the pixels that hold hills, since
        # blit time goes by area and a strip is as tall as its tallest hill:
        # (window, x and y within the strip, width).
        self.tiles = [
            [(strip.window(x, y, w, h), x, y, w) for x, y, w, h in rects]
            for strip, rects in zip(self.images, spec["tiles"])
        ]
        self.position = 0.0
        self.blur = 0
        self.drawn = None

    def advance(self, factor, dt_ms):
        """Moves the strip; True if it now draws differently."""
        step = self.drift * factor * dt_ms / 1000
        self.position = (self.position + step) % self.width
        moved = abs(step)
        lengths = self.blur_lengths
        while self.blur < len(lengths) and moved >= lengths[self.blur]:
            self.blur += 1
        while self.blur > 0 and moved < lengths[self.blur - 1] * BLUR_RELEASE:
            self.blur -= 1
        state = (int(self.position), self.blur)
        if state == self.drawn:
            return False
        self.drawn = state
        return True

    def draw(self):
        # The strip column at the screen's left edge. A strip is more than a
        # screen and a tile wider, so each tile shows at most once.
        left = (self.width - int(self.position)) % self.width
        for window, x, y, w in self.tiles[self.blur]:
            x -= left
            if x + w <= 0:
                x += self.width
            if x < WIDTH:
                screen.blit(window, vec2(x, self.top + y))


def on_exit():
    """Also called by Badgeware's Home interrupt; safe to call twice."""
    global cleaned_up
    if cleaned_up:
        return
    cleaned_up = True
    # Asset loading can fail before the counters exist. Otherwise, include
    # short runs that ended before the 60-frame report.
    if globals().get("drawn_count", 0) > 0 and not globals().get("benchmark_reported", False):
        report_benchmark()
    badge.default_clear = previous_clear
    badge.mode(previous_mode)
    screen.antialias = previous_antialias


def pressed(button=None):
    """Whether a button (or with none, any button) was pressed this frame."""
    return badge.pressed() if button is None else button is not None and badge.pressed(button)


def draw_hint(now):
    """A panel at the bottom saying how to leave, with the return arrow in
    the logo's pink, and a pink pointer bobbing down at enter itself."""
    global hint_widths
    screen.font = font.salty
    if hint_widths is None:
        hint_widths = [screen.measure_text(part)[0] for part in HINT_TEXT]
    before, after = hint_widths
    width = before + ARROW_W + after + 16
    left = HINT_RIGHT - width
    screen.pen = HINT_PANEL
    screen.rectangle(left, HINT_TOP, width, 22)
    screen.pen = WHITE
    screen.text(HINT_TEXT[0], left + 8, HINT_TOP + 2)
    screen.text(HINT_TEXT[1], left + 8 + before + ARROW_W, HINT_TOP + 2)
    screen.pen = PINK
    ax, ay = left + 8 + before, HINT_TOP + 6
    for x, y in ARROW:
        screen.rectangle(int(ax + x), int(ay + y), 2, 2)
    bob = int(1.5 + 1.5 * math.sin(now / 1000 * 6.0))
    screen.triangle(ENTER_X - 4, 230 + bob, ENTER_X + 4, 230 + bob, ENTER_X, 235 + bob)


def read_tilt():
    if READ_IMU is None:
        return 0.0
    return TILT_SIGN * max(-1.0, min(1.0, -READ_IMU()[0] / GRAVITY * 2))


def target_factor(tilt):
    if abs(tilt) < TILT_DEADZONE:
        return 1.0
    amount = ((abs(tilt) - TILT_DEADZONE) / (1 - TILT_DEADZONE)) ** TILT_CURVE
    if tilt < 0:
        return 1.0 + amount * (RACE - 1.0)
    # Tipping right has to cancel the drift first, so it covers more range.
    return 1.0 - amount * (RACE + 1.0)


def report_benchmark():
    global benchmark_reported
    duration_ms = max(1, time.ticks_diff(time.ticks_ms(), started_at))
    print(
        "ICS_BADGE_BENCHMARK displayed=%d draw_avg_ms=%.2f draw_max_ms=%.2f displayed_fps=%.2f factor=%.2f"
        % (
            drawn_count,
            draw_total_us / drawn_count / 1000,
            draw_max_us / 1000,
            drawn_count * 1000 / duration_ms,
            factor,
        )
    )
    benchmark_reported = True


def update():
    global last_tick, factor, drawn_count, draw_total_us, draw_max_us, hint_until, last_enter, hint_drawn

    if drawn_count >= 60 and not benchmark_reported:
        report_benchmark()

    now = time.ticks_ms()
    if pressed():
        if pressed(ENTER):
            if last_enter is not None and time.ticks_diff(now, last_enter) < HINT_MS:
                # Any non-None return stops Badgeware's run(update) loop.
                return True
            last_enter = now
        hint_until = time.ticks_add(now, HINT_MS)
    showing = time.ticks_diff(hint_until, now) > 0

    # Cap the step so a stall does not fling the hills a long way at once.
    dt = min(time.ticks_diff(now, last_tick), 100)
    last_tick = now
    factor += (target_factor(read_tilt()) - factor) * (1 - math.exp(-dt / RESPONSE_MS))

    # While the hint shows, every frame redraws, for its pointer's bob, and
    # once more after, to wipe it.
    changed = showing or hint_drawn
    for layer in layers:
        changed = layer.advance(factor, dt) or changed
    if not changed:
        return None

    draw_started = time.ticks_us()
    screen.blit(sky_band, SKY_BAND_AT)
    for layer in layers:
        layer.draw()
    for window, at in logo_tiles:
        screen.blit(window, at)
    if showing:
        draw_hint(now)
    hint_drawn = showing
    draw_us = time.ticks_diff(time.ticks_us(), draw_started)
    draw_total_us += draw_us
    draw_max_us = max(draw_max_us, draw_us)
    drawn_count += 1
    return None


try:
    badge.mode(HIRES | VSYNC)
    screen.antialias = image.OFF
    # The loop relies on the screen keeping the sky between refreshes.
    badge.default_clear = None

    screen.blit(image.load("assets/sky_top.png"), vec2(0, 0))
    sky_band = image.load("assets/sky_band.png")
    # The part of the logo the hills pass behind, redrawn over them each
    # frame, in tiles cropped like the strips'.
    logo_lower = image.load("assets/logo_lower.png")
    logo = scene["logo_lower"]
    logo_tiles = [
        (logo_lower.window(x, y, w, h), vec2(logo["x"] + x, logo["y"] + y))
        for x, y, w, h in logo["tiles"]
    ]
    layers = [Layer(spec) for spec in scene["layers"]]

    started_at = time.ticks_ms()
    last_tick = started_at
    factor = 1.0
    drawn_count = 0
    draw_total_us = 0
    draw_max_us = 0
    benchmark_reported = False
    hint_until = started_at
    last_enter = None
    hint_drawn = False
    hint_widths = None

    run(update)
finally:
    on_exit()
