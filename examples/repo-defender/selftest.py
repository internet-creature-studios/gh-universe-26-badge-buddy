"""On-badge self-test for Repo Defender's rules, then a busy-scene frame rate.

Copy the app to /dev_game on the badge's writable root and run this there:

    uvx mpremote connect /dev/cu.usbmodem1101 exec "import os; os.mkdir('/dev_game'); os.mkdir('/dev_game/assets')" \
        + fs cp badge/apps/repo_defender/__init__.py :/dev_game/__init__.py \
        + fs cp badge/apps/repo_defender/assets/studio_logo.png :/dev_game/assets/studio_logo.png
    uvx mpremote connect /dev/cu.usbmodem1101 exec "$(cat examples/repo-defender/selftest.py)"

It runs the game's own source with its run loop swapped for these checks,
prints PASS or FAIL for each, then plays a busy scene for six seconds and
prints the frame rate. Remove /dev_game afterwards (docs/workflow.md).
"""

import os
os.chdir('/dev_game')
src = open('__init__.py').read()
tests = '''
def check(name, ok, detail=""):
    print("SELFTEST", "PASS" if ok else "FAIL", name, detail)

def run_for(g, seconds, clear_bots=False):
    t = 0.0
    while t < seconds:
        g.update(0.02)
        t += 0.02
        if clear_bots:
            g.bots = []

def fresh(g, weapon=0):
    g.reset()
    g.state = "play"
    g.weapon = weapon
    g.spawn_in = 999

def selftest():
    g = game
    g.aim.calibrate(0.3)

    fresh(g)
    t, empty, full = 0.0, None, None
    while t < 7.0:
        g.update(0.02)
        t += 0.02
        g.bots = []
        if empty is None and g.reloading[0] > 0:
            empty = t
        if empty is not None and full is None and g.reloading[0] == 0:
            full = t
    check("LINT empties after 30 shots", empty is not None and abs(empty - 30 / 7.0) < 0.3, "at %.2fs (expect %.2f)" % (empty or -1, 30 / 7.0))
    check("reload takes 1.2s", full is not None and abs(full - empty - 1.2) < 0.1, "took %.2fs" % ((full or 0) - (empty or 0)))

    fresh(g, weapon=1)
    bot = Bot("hallucinator", 0.0)
    bot.phase = 0.0  # start its weave at the centre line
    bot.distance = 8.0
    g.bots = [bot]
    run_for(g, 0.5)
    check("matched REVIEW one-shots a hallucinator for 2x points", g.score == 50 and bot.hp <= 0,
          "score %d, hp %.1f, popup %s" % (g.score, bot.hp, g.popups[-1][2] if g.popups else None))

    fresh(g, weapon=1)
    bot = Bot("forcepush", 0.0)
    bot.distance = 12.0
    g.bots = [bot]
    run_for(g, 0.5)
    check("unmatched REVIEW does 3 to a force-pusher", abs(bot.hp - 5) < 0.01 and g.score == 0, "hp %.1f" % bot.hp)

    fresh(g)
    g.health = 50
    g.pickups = [Pickup("hotfix", 0.0, 6.0)]
    run_for(g, 0.5)
    check("shooting a hotfix heals 25", g.health == 75 and not g.pickups, "health %d" % g.health)

    fresh(g)
    g.stats["shields"] = 1
    g.shields = 1
    bot = Bot("spam", 20.0)  # off to the side, out of the line of fire
    bot.distance = REACH + 0.01
    g.bots = [bot]
    g.update(0.02)
    check("a shield absorbs a bot", g.health == 100 and g.shields == 0, "health %d, shields %d" % (g.health, g.shields))
    run_for(g, SHIELD_RECHARGE + 0.2, clear_bots=True)
    check("the shield recharges after 8s", g.shields == 1, "shields %d" % g.shields)

    fresh(g)
    g.clock = WAVE_SECONDS - 0.01
    g.update(0.02)
    names = [u["name"] for u in g.offers]
    check("a finished wave offers 3 different upgrades", g.state == "upgrade" and len(set(names)) == 3, str(names))
    g.take_upgrade([u for u in UPGRADES if u["stat"] == "reload"][0])
    check("Hot Reload makes reloads 15% faster", abs(g.stats["reload"] - 1.02) < 0.001 and g.state == "play", "%.3fs" % g.stats["reload"])
    g.stats["shields"] = MAX_SHIELDS
    offered = set()
    for i in range(30):
        g.offer_upgrades()
        offered.update(u["stat"] for u in g.offers)
    check("no shield upgrade once at 3 shields", "shields" not in offered, str(sorted(offered)))

    try:
        g.offer_upgrades()
        g.draw_game()
        g.draw_upgrades()
        display.update()
        g.state = "paused"
        g.draw_game()
        g.draw_pause()
        display.update()
        check("upgrade and pause screens draw", True)
    except Exception as e:
        check("upgrade and pause screens draw", False, repr(e))

    # A busy scene for the frame-rate run.
    fresh(g, weapon=2)
    g.spawn_in = 0.5
    for i in range(12):
        b = Bot(("spam", "hallucinator", "forcepush")[i % 3], -25 + i * 4.5)
        b.distance = 8 + i * 2
        g.bots.append(b)
    g.pickups = [Pickup(k, a, 10.0) for k, a in (("hotfix", -15), ("cache", 0), ("overclock", 15))]
    g.stats["shields"] = 2
    g.shields = 1

t0 = [0]
frames = [0]
worst = [0]
def probe():
    if t0[0] == 0:
        t0[0] = time.ticks_ms()
    s = time.ticks_us()
    r = update()
    worst[0] = max(worst[0], time.ticks_diff(time.ticks_us(), s))
    frames[0] += 1
    el = time.ticks_diff(time.ticks_ms(), t0[0])
    if el > 6000:
        print("SELFTEST busy scene: %.1f fps, worst frame %.1f ms, bots %d, shots %d" % (frames[0] * 1000 / el, worst[0] / 1000, len(game.bots), len(game.shots)))
        return True
    return r

'''
src = src.replace("    run(update)\n", "    selftest()\n    run(probe)\n")
src = src.replace("\ntry:\n    badge.mode(HIRES | VSYNC)", "\n" + tests + "try:\n    badge.mode(HIRES | VSYNC)")
assert src.count("run(probe)") == 1
exec(src, {"__name__": "__main__"})
