#!/usr/bin/env python3
"""Find where the badge's buttons sit around its screen, with someone's help.

    python3 tools/locate_buttons.py            # saves docs/button_positions.json

A light travels around the screen's edge, once clockwise and once
anticlockwise. The person at the badge presses each button as the light
passes it. Each press says which button it is and where along the edge the
light was. Averaging the two directions cancels out reaction time.

It needs the badge on serial (see docs/workflow.md) and waits up to ten
minutes for the first press. Home isn't part of it: it leaves apps.
"""

import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "docs", "button_positions.json")
WIDTH, HEIGHT = 320, 240
PERIMETER = 2 * (WIDTH + HEIGHT)
SPEED = 70  # px a second: a lap takes about 16 seconds

DEVICE = """
import time
NAMES = ('BUTTON_UP', 'BUTTON_DOWN', 'BUTTON_LEFT', 'BUTTON_RIGHT', 'BUTTON_SELECT')
BUTTONS = []
for n in NAMES:
    try:
        BUTTONS.append((n, eval(n)))
    except NameError:
        pass
W, H, P, SPEED = %d, %d, %d, %d
badge.mode(HIRES)
screen.font = font.salty
DARK = color.rgb(8, 10, 22)
TEXT = color.rgb(200, 230, 255)
GLOW = color.rgb(90, 255, 140)
DIM = color.rgb(40, 110, 70)

def where(p):
    p %%= P
    if p < W:
        return p, 0, 'top'
    if p < W + H:
        return W - 1, p - W, 'right'
    if p < 2 * W + H:
        return W - 1 - (p - W - H), H - 1, 'bottom'
    return 0, H - 1 - (p - 2 * W - H), 'left'

def draw(p, lines):
    screen.pen = DARK
    screen.clear()
    x, y, edge = where(p)
    screen.pen = GLOW
    if edge in ('top', 'bottom'):
        screen.rectangle(int(x) - 14, 0 if edge == 'top' else H - 8, 28, 8)
        y0, y1 = (12, 60) if edge == 'top' else (H - 60, H - 12)
        screen.rectangle(int(x) - 1, y0, 3, y1 - y0)
    else:
        screen.rectangle(0 if edge == 'left' else W - 8, int(y) - 14, 8, 28)
        x0, x1 = (12, 60) if edge == 'left' else (W - 60, W - 12)
        screen.rectangle(x0, int(y) - 1, x1 - x0, 3)
    yy = 80
    for i, line in enumerate(lines):
        screen.pen = GLOW if i == 0 else TEXT
        w, _ = screen.measure_text(line)
        screen.text(line, (W - w) // 2, yy)
        yy += 20
    display.update()

draw(0, ['Button finder', 'A light will go round the edge.', 'Press each button as it passes.', 'Press any button to begin.'])
start = time.ticks_ms()
badge.poll()
while not badge.pressed():
    badge.poll()
    if time.ticks_diff(time.ticks_ms(), start) > 600000:
        print('RESULT timeout')
        raise SystemExit
    time.sleep_ms(10)
time.sleep_ms(400)
badge.poll()
for lap, direction in ((1, 1), (2, -1)):
    seen = []
    t0 = time.ticks_ms()
    while True:
        badge.poll()
        s = time.ticks_diff(time.ticks_ms(), t0) / 1000 * SPEED
        if s >= P:
            break
        p = s if direction > 0 else P - s
        for name, b in BUTTONS:
            if badge.pressed(b) and name not in seen:
                seen.append(name)
                print('EVENT', lap, name, round(p %% P, 1))
        label = 'clockwise' if direction > 0 else 'anticlockwise'
        draw(p, ['Lap %%d of 2, %%s' %% (lap, label), 'Press each button as the light passes it.', 'Pressed: %%d of %%d' %% (len(seen), len(BUTTONS))])
draw(0, ['Thanks!', 'Button positions recorded.'])
print('RESULT done')
""" % (WIDTH, HEIGHT, PERIMETER, SPEED)


def edge_position(p):
    p %= PERIMETER
    if p < WIDTH:
        return "top", round(p)
    if p < WIDTH + HEIGHT:
        return "right", round(p - WIDTH)
    if p < 2 * WIDTH + HEIGHT:
        return "bottom", round(WIDTH - 1 - (p - WIDTH - HEIGHT))
    return "left", round(HEIGHT - 1 - (p - 2 * WIDTH - HEIGHT))


def main():
    port = sys.argv[1] if len(sys.argv) > 1 else None
    if not port:
        import glob
        ports = sorted(glob.glob("/dev/cu.usbmodem*"))
        if len(ports) != 1:
            sys.exit("locate_buttons: need exactly one /dev/cu.usbmodem* port, found %s" % ports)
        port = ports[0]
    print("follow the instructions on the badge's screen")
    result = subprocess.run(["uvx", "mpremote", "connect", port, "exec", DEVICE],
                            capture_output=True, text=True, timeout=900)
    events = {}
    for line in result.stdout.splitlines():
        parts = line.split()
        if parts[:1] == ["EVENT"]:
            events.setdefault(parts[2], {})[int(parts[1])] = float(parts[3])
        elif parts[:2] == ["RESULT", "timeout"]:
            sys.exit("locate_buttons: nobody pressed a button within ten minutes")
    subprocess.run(["uvx", "mpremote", "connect", port, "reset"], capture_output=True)

    positions = {}
    for name, laps in sorted(events.items()):
        if 1 in laps and 2 in laps:
            a, b = laps[1], laps[2]
            if abs(a - b) > PERIMETER / 2:  # either side of the starting corner
                b += PERIMETER if b < a else -PERIMETER
            p, note = (a + b) / 2, "both laps"
        else:
            p, note = next(iter(laps.values())), "one lap only: reaction time not cancelled"
        edge, at = edge_position(p)
        positions[name] = {"edge": edge, "at": at, "laps": {str(k): v for k, v in laps.items()}, "note": note}
        print("%-14s %-6s edge at %3d px  (%s)" % (name, edge, at, note))
    if not positions:
        sys.exit("locate_buttons: no button presses came back")
    with open(OUT, "w") as f:
        json.dump({
            "about": "Where each button sits beside the 320x240 screen: the edge it's next to, and how far along "
                     "that edge (x for top and bottom, y for left and right). From tools/locate_buttons.py.",
            "buttons": positions,
        }, f, indent=2)
        f.write("\n")
    print("saved %s" % os.path.relpath(OUT, REPO))


if __name__ == "__main__":
    main()
