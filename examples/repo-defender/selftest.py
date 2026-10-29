"""On-badge self-test for Repo Defender's rules, then a busy-scene frame rate.

Copy the app to /dev_game on the badge's writable root and run this there:

    uvx mpremote connect /dev/cu.usbmodem1101 exec "import os; os.mkdir('/dev_game'); os.mkdir('/dev_game/assets')" \
        + fs cp badge/apps/repo_defender/__init__.py :/dev_game/__init__.py \
        + fs cp badge/apps/repo_defender/assets/studio_logo.png :/dev_game/assets/studio_logo.png
    uvx mpremote connect /dev/cu.usbmodem1101 exec "$(cat examples/repo-defender/selftest.py)"

It runs the game's own source with its run loop swapped for these checks,
prints PASS or FAIL for each, then plays a busy scene for six seconds and
prints the frame rate. It never saves the score or options. Remove
/dev_game afterwards (docs/workflow.md).
"""

import os

os.chdir('/dev_game')
src = open('__init__.py').read()
tests = '''
def check(name, ok, detail=""):
    print("SELFTEST", "PASS" if ok else "FAIL", name, detail)

def run_for(g, seconds, trigger=True, clear_bots=False):
    t = 0.0
    while t < seconds:
        g.update(0.02, trigger)
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
    g.options = dict(DEFAULT_OPTIONS)  # in memory only: never saved here
    g.aim.calibrate("rotate", 0.3)

    fresh(g)
    run_for(g, 1.0, trigger=False)
    check("nothing fires without the trigger", g.ammo[0] == 30 and not g.shots, "ammo %.1f" % g.ammo[0])

    fresh(g)
    t, empty, full = 0.0, None, None
    while t < 7.0:
        g.update(0.02, True)
        t += 0.02
        g.bots = []
        if empty is None and g.reloading[0] > 0:
            empty = t
        if empty is not None and full is None and g.reloading[0] == 0:
            full = t
    check("LINT empties after 30 shots", empty is not None and abs(empty - 29 / 7.0) < 0.15, "at %.2fs" % (empty or -1))
    check("an empty magazine reloads in 1.2s", full is not None and abs(full - empty - 1.2) < 0.1, "took %.2fs" % ((full or 0) - (empty or 0)))

    fresh(g)
    run_for(g, 0.5)
    g.reload_now()
    reloading = g.reloading[0] > 0
    run_for(g, 1.25, trigger=False)
    check("Up reloads early", reloading and g.ammo[0] == 30, "ammo %.1f" % g.ammo[0])

    fresh(g)
    g.ammo[1] = 0.0
    run_for(g, 3.0, trigger=False)
    expect = 4 / (HOLSTER_REFILL * 1.2) * 3.0
    check("a holstered weapon refills slowly", abs(g.ammo[1] - expect) < 0.2, "REVIEW %.2f of 4 after 3s (expect %.2f)" % (g.ammo[1], expect))

    fresh(g, weapon=1)
    bot = Bot("node_modules", 0.0)
    bot.distance = 12.0
    g.bots = [bot]
    run_for(g, 2.4)
    check("3 matched REVIEW shots destroy node_modules for 2x points", bot.hp <= 0 and g.score == 120,
          "hp %.1f, score %d" % (bot.hp, g.score))

    fresh(g, weapon=1)
    bot = Bot("forcepush", 0.0)
    bot.distance = 14.0
    g.bots = [bot]
    run_for(g, 0.5)
    check("unmatched REVIEW does 3 to a force-pusher", abs(bot.hp - 1) < 0.01, "hp %.1f" % bot.hp)

    fresh(g, weapon=2)
    bot = Bot("hallucinator", 0.0)
    bot.phase = 0.0  # start its weave at the centre line
    bot.distance = 8.0
    g.bots = [bot]
    run_for(g, 0.5)
    check("one REVERT blast destroys a hallucinator for 2x points", bot.hp <= 0 and g.score == 30,
          "hp %.1f, score %d" % (bot.hp, g.score))

    fresh(g)
    g.health = 50
    g.pickups = [Pickup("pizza", 0.0, 6.0)]
    run_for(g, 0.5)
    check("shooting pizza heals 25", g.health == 75 and not g.pickups, "health %d" % g.health)

    fresh(g)
    run_for(g, 1.0, clear_bots=True)
    base = 30 - g.ammo[0]
    fresh(g)
    g.collect(Pickup("coffee", 0.0, 6.0))
    run_for(g, 1.0, clear_bots=True)
    boosted = 30 - g.ammo[0]
    check("coffee doubles the fire rate", boosted >= 1.7 * base, "%d shots a second, %d with coffee" % (base, boosted))

    fresh(g)
    g.bots = [Bot(k, a) for k, a in (("forcepush", -20), ("node_modules", 0), ("hallucinator", 20), ("mega", 10))]
    g.collect(Pickup("rmrf", 0.0, 6.0))
    run_for(g, 0.02, trigger=False)
    left = [b.kind for b in g.bots]
    check("rm -rf deletes every bot but the Mega-agent", left == ["mega"] and g.score == 95, "%s, score %d" % (left, g.score))

    fresh(g)
    g.stats["shields"] = 1
    g.shields = 1
    bot = Bot("forcepush", 20.0)  # off to the side, out of the line of fire
    bot.distance = REACH + 0.01
    g.bots = [bot]
    g.update(0.02, False)
    check("a shield absorbs a bot", g.health == 100 and g.shields == 0, "health %d, shields %d" % (g.health, g.shields))
    run_for(g, SHIELD_RECHARGE + 0.2, trigger=False, clear_bots=True)
    check("the shield recharges after 8s", g.shields == 1, "shields %d" % g.shields)

    fresh(g)
    g.clock = WAVE_SECONDS - 0.01
    g.update(0.02, False)
    names = [u["name"] for u in g.offers]
    check("a finished wave offers 3 different upgrades", g.state == "upgrade" and len(set(names)) == 3, str(names))
    g.take_upgrade([u for u in UPGRADES if u["name"] == "Automated PR Review"][0])
    check("Automated PR Review makes reloads 15% faster", abs(g.stats["reload"] - 1.02) < 0.001, "%.3fs" % g.stats["reload"])
    g.stats["shields"] = MAX_SHIELDS
    offered = set()
    for i in range(30):
        g.offer_upgrades()
        offered.update(u["stat"] for u in g.offers)
    check("no shield upgrade once at 3 shields", "shields" not in offered, str(sorted(offered)))

    g.aim.level = 0.0
    right, level, left = g.aim.tilt_rate(-0.3 * 16384), g.aim.tilt_rate(0.0), g.aim.tilt_rate(0.6 * 16384)
    check("tilting turns: right dip turns right, level stops", right > 0 and level == 0 and left == -TILT_DPS,
          "%.1f, %.1f, %.1f deg/s" % (right, level, left))

    try:
        for state in ("title", "options", "paused", "upgrade", "over"):
            g.state = state
            if state == "upgrade":
                g.offer_upgrades()
            g.draw_game()
            if state == "title":
                g.draw_card(["REPO DEFENDER", "a", "b"], WEAPON_PENS[0], top=6, left=8, width=WIDTH - 40)
                g.draw_side_tab(UP_Y, "options", True)
            elif state == "options":
                g.draw_menu("OPTIONS", g.option_rows(), 1, 40)
            elif state == "paused":
                g.draw_menu("PAUSED", PAUSE_CHOICES, 2, 20)
            elif state == "upgrade":
                g.draw_upgrades()
            else:
                g.draw_card(["REPO COMPROMISED", "x", "y"], DANGER)
            display.update()
        check("every screen draws", True)
    except Exception as e:
        check("every screen draws", False, repr(e))

    # A busy scene for the frame-rate run, firing automatically.
    g.options["autofire"] = True
    fresh(g, weapon=2)
    g.spawn_in = 0.5
    for i in range(12):
        b = Bot(("forcepush", "node_modules", "hallucinator")[i % 3], -25 + i * 4.5)
        b.distance = 8 + i * 2
        g.bots.append(b)
    g.pickups = [Pickup(k, a, 10.0) for k, a in (("pizza", -15), ("coffee", -5), ("cache", 5), ("rmrf", 15))]
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
