"""On-badge self-test for Repo Defender's rules, then a busy-scene frame rate.

Copy the app to /dev_game on the badge's writable root and run this there:

    uvx mpremote connect /dev/cu.usbmodem1101 exec "import os; os.mkdir('/dev_game'); os.mkdir('/dev_game/assets')" \
        + fs cp badge/apps/repo_defender/__init__.py :/dev_game/__init__.py \
        + fs cp badge/apps/repo_defender/assets/studio_logo.png :/dev_game/assets/studio_logo.png
    uvx mpremote connect /dev/cu.usbmodem1101 exec "$(cat examples/repo-defender/selftest.py)"

It runs the game's own source with its run loop swapped for these checks,
prints PASS or FAIL for each, then plays a busy scene for six seconds and
prints the frame rate. It never saves the score or settings. Remove
/dev_game afterwards (docs/workflow.md).
"""

import os

os.chdir('/dev_game')
src = open('__init__.py').read()
tests = """
import gc

def check(name, ok, detail=""):
    print("SELFTEST", "PASS" if ok else "FAIL", name, detail)

def run_for(g, seconds, clear=False):
    t = 0.0
    while t < seconds:
        g.update(0.02)
        t += 0.02
        if clear:
            g.bots = []

def fresh(g, weapon=0):
    g.reset()
    g.state = "play"
    g.owned[weapon] = True
    g.weapon = weapon
    g.spawn_in = 999

def selftest():
    g = game
    g.settings = dict(DEFAULT_SETTINGS)  # in memory only: never saved here
    g.aim.calibrate("rotate", 0.3)

    gc.collect()
    free, t, count = gc.mem_free(), time.ticks_ms(), len(g.unbuilt)
    g.build_models()
    took = time.ticks_diff(time.ticks_ms(), t)
    gc.collect()
    built = sum(1 for frames in g.models.values() for sizes in frames for m in sizes if m is not None)
    t = time.ticks_us()
    gc.collect()
    collect = time.ticks_diff(time.ticks_us(), t) / 1000
    check("every bot model builds", count > 0 and not g.unbuilt and built == count,
          "%d models in %d ms, %d KB, %d KB free, a garbage collection takes %.1f ms" % (
              count, took, (free - gc.mem_free()) // 1024, gc.mem_free() // 1024, collect))

    fresh(g)
    run_for(g, 1.0, clear=True)
    check("weapons fire by themselves", g.ammo[0] < 30, "LINT has %.0f of 30 after 1s" % g.ammo[0])

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
    check("LINT empties after 30 shots", empty is not None and abs(empty - 29 / 7.0) < 0.15, "at %.2fs" % (empty or -1))
    check("an empty magazine reloads in 1.2s", full is not None and abs(full - empty - 1.2) < 0.1,
          "took %.2fs" % ((full or 0) - (empty or 0)))

    fresh(g)
    run_for(g, 0.5, clear=True)
    g.reload_now()
    reloading = g.reloading[0] > 0
    run_for(g, 1.25, clear=True)
    check("Down reloads early", reloading and g.ammo[0] >= 29, "ammo %.1f" % g.ammo[0])

    fresh(g)
    g.owned[1] = True
    g.ammo[1] = 0.0
    g.cooldown = 999  # hold fire, so only the refill moves
    run_for(g, 3.0, clear=True)
    expect = 4 / (HOLSTER_REFILL * 1.2) * 3.0
    check("a holstered weapon refills slowly", abs(g.ammo[1] - expect) < 0.2,
          "REVIEW %.2f of 4 after 3s (expect %.2f)" % (g.ammo[1], expect))

    # Weapon cards.
    fresh(g)
    owned = list(g.owned)
    g.switch_weapon(1)
    check("you start with LINT only", owned == [True, False, False] and g.weapon == 0, str(owned))
    cards = {c["weapon"]: c for c in WEAPON_CARDS}
    name = g.card_text(cards[1])[0]
    g.take_upgrade(cards[1])
    check("a REVIEW card unlocks REVIEW, in hand", name == "Code Review" and g.owned[1] and g.weapon == 1,
          "%s: owned %s, holding %d" % (name, g.owned, g.weapon))
    name = g.card_text(cards[1])[0]
    g.take_upgrade(cards[1])
    run_for(g, 0.05, clear=True)
    shot = g.shots[-1].damage if g.shots else -1
    check("once owned, a REVIEW card adds 2 damage", name == "Senior Reviewer" and g.damage[1] == 7 and shot == 7,
          "%s: damage %d, shot %d" % (name, g.damage[1], shot))
    g.take_upgrade(cards[2])
    g.take_upgrade(cards[2])
    g.shots = []
    g.cooldown = 0.0
    g.update(0.02)
    check("once owned, a REVERT card adds a pellet", g.weapon == 2 and g.pellets[2] == 6 and len(g.shots) == 6,
          "pellets %d, one blast fired %d" % (g.pellets[2], len(g.shots)))
    gaps = sorted(s.azimuth for s in g.shots)
    check("REVERT's pellets stay 3.5 degrees apart", all(abs(b - a - 3.5) < 0.01 for a, b in zip(gaps, gaps[1:])),
          str(["%.1f" % a for a in gaps]))
    g.take_upgrade(cards[0])
    g.weapon = 0
    g.ammo[0] = 0.0
    g.reload_now()
    run_for(g, 1.25, clear=True)
    check("a LINT card adds 10 rounds a magazine", g.magazine[0] == 40 and g.ammo[0] >= 39,
          "magazine %d, ammo %.1f" % (g.magazine[0], g.ammo[0]))
    g.owned = [True, False, True]
    g.weapon = 0
    order = []
    for step in (1, 1, -1):
        g.switch_weapon(step)
        order.append(g.weapon)
    check("Left and Right skip weapons you don't have", order == [2, 0, 2], str(order))

    # + cards.
    plus = total = 0
    for i in range(300):
        g.offer_upgrades()
        total += len(g.offers)
        plus += sum(1 for u, p in g.offers if p)
    check("about 15% of cards are +", 0.11 < plus / total < 0.19, "%d of %d" % (plus, total))
    card = {u["stat"]: u for u in UPGRADES}
    fresh(g)
    g.take_upgrade(card["fire_rate"], True)
    g.take_upgrade(card["reload"], True)
    g.health = 50
    g.take_upgrade(card["max_health"], True)
    check("+ stat cards do twice as much", abs(g.stats["fire_rate"] - 1.3) < 0.001 and abs(g.stats["reload"] - 0.84) < 0.001
          and g.stats["max_health"] == 140 and g.health == 90,
          "fire rate %.2f, reload %.2fs, health %d of %d" % (g.stats["fire_rate"], g.stats["reload"], g.health,
                                                           g.stats["max_health"]))
    g.health = 30
    g.take_upgrade(card["shields"], True)
    check("Two-Factor Auth+ adds a shield and fully heals", g.stats["shields"] == 1 and g.shields == 1 and g.health == 140,
          "shields %d, health %d" % (g.shields, g.health))
    fresh(g)
    name = g.card_text(cards[1], True)[0]
    g.take_upgrade(cards[1], True)
    check("Code Review+ gives REVIEW already at 7 damage", name == "Code Review+" and g.owned[1] and g.damage[1] == 7
          and g.ammo[1] == 4, "%s: damage %d, ammo %.0f" % (name, g.damage[1], g.ammo[1]))
    g.take_upgrade(cards[1], True)
    g.take_upgrade(cards[2], True)
    pellets = g.pellets[2]
    g.take_upgrade(cards[2], True)
    g.take_upgrade(cards[0], True)
    check("+ weapon cards on a weapon you have boost it twice", g.damage[1] == 11 and pellets == 6 and g.pellets[2] == 8
          and g.magazine[0] == 50, "damage %d, pellets %d then %d, magazine %d" % (g.damage[1], pellets, g.pellets[2],
                                                                                   g.magazine[0]))

    fresh(g)
    g.take_upgrade(card["risk"])
    bot = g.new_bot("bug", 0.0)
    hp, speed = bot.max_hp, bot.speed
    bot.hp = 0.01
    g.hit(Shot(WEAPONS[0], 0, 0.0, 1), bot)
    score = g.score
    g.take_upgrade(card["risk"], True)
    bot = g.new_bot("bug", 0.0)
    bot.hp = 0.01
    g.hit(Shot(WEAPONS[0], 0, 0.0, 1), bot)
    check("Friday Deploy: +10% score, and bots +10% health and speed (+20% for +)",
          abs(hp - 4.4) < 0.01 and abs(speed - 4.6 * 1.1) < 0.01 and score == 22 and g.score - score == 26,
          "hp %.2f, speed %.2f, a bug scores %d then %d" % (hp, speed, score, g.score - score))

    fresh(g)
    g.stats["pickup_chance"] = 1.0
    spots = []
    for i in range(30):
        g.aim.yaw = (0.0, 25.0, -25.0)[i % 3]
        bot = Bot("bug", g.aim.yaw)
        bot.distance = 3.0
        bot.hp = 0.01
        g.hit(Shot(WEAPONS[0], 0, g.aim.yaw, 1), bot)
        spots.append((g.pickups[-1].azimuth - g.aim.yaw, g.pickups[-1].azimuth, g.pickups[-1].distance))
    g.aim.yaw = 0.0
    check("pickups land 12 to 19 degrees from your aim, within reach",
          all(12 <= abs(off) <= 19 and abs(az) <= SPAWN_ARC and 7 <= d <= 13 for off, az, d in spots),
          "offsets %.1f to %.1f" % (min(abs(o) for o, a, d in spots), max(abs(o) for o, a, d in spots)))

    # Every card's text fits above the change line, in the badge's own fonts
    # (the layout in draw_upgrades).
    tallest = (0, "")
    for owned in (False, True):
        g.owned = [True, owned, owned]
        for c in UPGRADES + WEAPON_CARDS:
            for p in (False, True):
                name, flavor, effect, change = g.card_text(c, p)
                screen.font = font.salty
                height = 6 + 15 * len(wrap(name, 82)) + 4
                screen.font = font.winds
                height += 12 * len(wrap(flavor, 82)) + 5 + 12 * len(wrap(effect, 82))
                wide = screen.measure_text(change)[0]
                if height > tallest[0]:
                    tallest = (height, name)
                if wide > 82:
                    tallest = (999, change)
    check("every card's text fits", tallest[0] <= 136, "tallest %d of 136 px: %s" % tallest)

    fresh(g, weapon=1)
    box = Bot("node_modules", 0.0)
    box.distance = 12.0
    g.bots = [box]
    run_for(g, 2.4)
    check("3 REVIEW shots destroy node_modules", box.hp <= 0 and g.score == 50, "hp %.1f, score %d" % (box.hp, g.score))

    fresh(g, weapon=1)
    near, far = Bot("bug", 0.0), Bot("bug", 0.0)
    near.distance, far.distance = 9.0, 12.0
    g.bots = [near, far]
    run_for(g, 0.5)
    check("one REVIEW shot pierces through two bugs", near.hp <= 0 and far.hp <= 0 and g.score == 40,
          "hp %.1f and %.1f, score %d" % (near.hp, far.hp, g.score))

    fresh(g, weapon=2)
    ghost = Bot("hallucination", 0.0)
    ghost.phase = 0.0  # start its sway at the centre line
    ghost.distance = 8.0
    g.bots = [ghost]
    run_for(g, 0.5)
    check("one REVERT blast destroys a hallucination", ghost.hp <= 0 and g.score == 15,
          "hp %.1f, score %d" % (ghost.hp, g.score))

    fresh(g)
    g.health = 50
    g.pickups = [Pickup("pizza", 0.0, 6.0)]
    run_for(g, 0.5)
    check("shooting pizza heals 25", g.health == 75 and not g.pickups, "health %d" % g.health)

    fresh(g)
    run_for(g, 1.0, clear=True)
    base = 30 - g.ammo[0]
    fresh(g)
    g.collect(Pickup("coffee", 0.0, 6.0))
    run_for(g, 1.0, clear=True)
    boosted = 30 - g.ammo[0]
    check("coffee doubles the fire rate", boosted >= 1.7 * base, "%d shots a second, %d with coffee" % (base, boosted))

    fresh(g)
    g.cooldown = 999
    g.bots = [Bot(k, a) for k, a in (("bug", -20), ("node_modules", 0), ("hallucination", 20), ("agent", 10))]
    g.collect(Pickup("rmrf", 0.0, 6.0))
    run_for(g, 0.02)
    left = [b.kind for b in g.bots]
    check("rm -rf deletes every bot but the rogue agent", left == ["agent"] and g.score == 85,
          "%s, score %d" % (left, g.score))

    fresh(g)
    g.stats["shields"] = 1
    g.shields = 1
    bug = Bot("bug", 20.0)  # off to the side, out of the line of fire
    bug.distance = REACH + 0.01
    g.bots = [bug]
    g.update(0.02)
    check("a shield stops a bot", g.health == 100 and g.shields == 0, "health %d, shields %d" % (g.health, g.shields))
    run_for(g, SHIELD_RECHARGE + 0.2, clear=True)
    check("the shield recharges after 8s", g.shields == 1, "shields %d" % g.shields)

    fresh(g)
    g.clock = WAVE_SECONDS - 0.01
    g.update(0.02)
    names = [g.card_text(*u)[0] for u in g.offers]
    check("a finished wave offers 3 different upgrades", g.state == "upgrade" and len(set(names)) == 3, str(names))
    g.take_upgrade([u for u in UPGRADES if u["name"] == "Automated PR Review"][0])
    check("Automated PR Review makes reloads 15% faster", abs(g.stats["reload"] - 1.02) < 0.001,
          "%.3fs" % g.stats["reload"])
    g.stats["shields"] = MAX_SHIELDS
    offered = set()
    for i in range(30):
        g.offer_upgrades()
        offered.update(u.get("stat", "weapon") for u, plus in g.offers)
    check("no shield upgrade once at 3 shields, and weapon cards turn up", "shields" not in offered and "weapon" in offered,
          str(sorted(offered)))

    g.aim.set_mode("rotate")
    g.aim.raw, g.aim.yaw = 12.0, 12.0
    g.aim.reset_origin()
    check("Reset origin makes this way straight ahead", g.aim.yaw == 0 and g.aim.centre == 12.0, "yaw %.1f" % g.aim.yaw)
    g.aim.level = 0.0
    right, level, left = g.aim.tilt_rate(-0.3 * 16384), g.aim.tilt_rate(0.0), g.aim.tilt_rate(0.6 * 16384)
    check("tilting turns: right dip turns right, level stops", right > 0 and level == 0 and left == -TILT_DPS,
          "%.1f, %.1f, %.1f deg/s" % (right, level, left))

    # The screen isn't cleared between frames, so the world has to cover
    # every pixel, or whatever moves across a gap leaves trails.
    screen.pen = color.rgb(255, 0, 255)
    screen.clear()
    stale = str(screen.get(0, 0))
    g.draw_world()
    rows = [y for y in range(HEIGHT) if any(str(screen.get(x, y)) == stale for x in (0, 100, 200, WIDTH - 1))]
    check("the world covers every row of the screen", not rows, "rows left: %s" % rows[:8])

    try:
        fresh(g)
        g.bots = [Bot(k, a) for k, a in (("bug", -10), ("node_modules", 0), ("hallucination", 8), ("agent", 15))]
        for b, d in zip(g.bots, (4, 6, 9, 12)):
            b.distance = d
        g.bots[1].hp = 5  # dented
        g.bots[0].flash = g.bots[3].flash = 0.1  # a hit: up close it flashes white, further off it pops
        for state in ("title", "settings", "paused", "upgrade", "upgrade", "over"):
            g.state = state
            if state == "upgrade":
                g.offers = [(c, p) for c, p in zip(WEAPON_CARDS, (False, True, True))]
            g.draw_game()
            if state == "title":
                g.draw_card(["REPO DEFENDER", "a", "b"], WEAPON_PENS[0], top=6, left=8, width=WIDTH - 40)
                g.draw_side_tab(UP_Y, "settings", True)
            elif state == "settings":
                g.draw_menu("SETTINGS", g.settings_rows(), 1, 40, True)
            elif state == "paused":
                g.draw_menu("PAUSED", PAUSE_CHOICES, 2, 40)
            elif state == "upgrade":
                g.draw_upgrades()
                g.owned = [True, True, True]  # the second time, every card is a boost
            else:
                g.draw_card(["REPO COMPROMISED", "x", "y"], DANGER)
            display.update()
        check("every screen and bot draws", True)
    except Exception as e:
        check("every screen and bot draws", False, repr(e))

    # A busy scene for the frame-rate run.
    fresh(g, weapon=2)
    g.owned = [True, True, True]
    g.spawn_in = 0.5
    for i in range(12):
        b = Bot(("bug", "node_modules", "hallucination")[i % 3], -25 + i * 4.5)
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
        print("SELFTEST busy scene: %.1f fps, worst frame %.1f ms, bots %d, shots %d" % (
            frames[0] * 1000 / el, worst[0] / 1000, len(game.bots), len(game.shots)))
        return True
    return r

"""
src = src.replace("    run(update)\n", "    selftest()\n    run(probe)\n")
src = src.replace("\ntry:\n    badge.mode(HIRES | VSYNC)", "\n" + tests + "try:\n    badge.mode(HIRES | VSYNC)")
assert src.count("run(probe)") == 1
exec(src, {"__name__": "__main__"})
