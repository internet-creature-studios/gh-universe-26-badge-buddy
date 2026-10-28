#!/usr/bin/env python3
"""Install files from badge/ onto the badge, safely, and check they arrived.

    python3 tools/deploy.py badge/apps/my_app             # one app
    python3 tools/deploy.py                               # everything in badge/
    python3 tools/deploy.py badge/apps/my_app --prune     # also remove files the repo no longer has
    python3 tools/deploy.py badge/apps/my_app --dry-run   # only show what would change

It follows the steps in docs/workflow.md:

1. Over serial, hash the badge's copies of the files and plan what differs.
   If nothing does, it stops there, without touching disk mode.
2. Check /system has room for the change.
3. Switch to disk mode (powman.reset_into_msc), unless the BADGER drive is
   already mounted.
4. For each file that differs, delete it on the drive, then copy it fresh.
   Overwriting in place has left wrong 4 KB clusters on disk.
5. With --prune, delete files under the given app folders that the repo
   doesn't have.
6. Delete the ._ files macOS wrote during the copy, then eject. The badge
   reboots to its menu.
7. Over serial, hash every file again on the badge itself, not the Mac's
   cache, and check that no ._ files are left.
8. Reset the badge to its menu.

It needs uv, for `uvx mpremote`. The exit status is non-zero if anything
fails to verify.
"""

import argparse
import glob
import hashlib
import os
import subprocess
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BADGE = os.path.join(REPO, "badge")
VOLUME = "/Volumes/BADGER"
SKIP = {".DS_Store", "__pycache__"}
# Never deploy these, whatever is in badge/.
NEVER = {"secrets.py"}
CLUSTER = 4096
# Slack left free on /system, beyond the files themselves.
SPARE = 64 * 1024

# Runs on the badge: hashes FILES, then lists every file under DIRS.
DEVICE_SCRIPT = """
import hashlib, binascii, os
def walk(d):
    try:
        entries = list(os.ilistdir(d))
    except OSError:
        return
    for e in entries:
        p = d + '/' + e[0]
        if e[1] == 0x4000:
            yield from walk(p)
        else:
            yield p
for p in FILES:
    try:
        h = hashlib.sha256()
        with open(p, 'rb') as f:
            while True:
                b = f.read(4096)
                if not b:
                    break
                h.update(b)
        print('H', binascii.hexlify(h.digest()).decode(), p)
    except OSError:
        print('M', p)
for d in DIRS:
    for p in walk(d):
        print('F', p)
s = os.statvfs('/system')
print('S', s[0] * s[3])
"""


def fail(message):
    sys.exit("deploy: " + message)


def count(items, noun):
    n = len(items)
    return "%d %s%s" % (n, noun, "" if n == 1 else "s")


def local_files(paths):
    """{path on the badge, relative to /system: local file} for the given paths."""
    files = {}
    for path in paths:
        path = os.path.abspath(path)
        if os.path.commonpath([path, BADGE]) != BADGE:
            fail("%s is not inside badge/" % path)
        if os.path.isfile(path):
            found = [path]
        elif os.path.isdir(path):
            found = []
            for root, dirs, names in os.walk(path):
                dirs[:] = sorted(d for d in dirs if d not in SKIP and not d.startswith("._"))
                found += [os.path.join(root, n) for n in sorted(names) if n not in SKIP and not n.startswith("._")]
        else:
            fail("%s does not exist" % path)
        for f in found:
            if os.path.basename(f) in NEVER:
                fail("refusing to deploy %s" % os.path.relpath(f, REPO))
            files[os.path.relpath(f, BADGE).replace(os.sep, "/")] = f
    return files


def prunable(rel_dir):
    # Only whole app folders this repo owns. Pruning apps/ or apps/menu would
    # delete the firmware's own files.
    parts = rel_dir.split("/")
    return len(parts) >= 2 and parts[0] == "apps" and parts[1] != "menu"


def sha256(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def clusters(size):
    return -(-size // CLUSTER) * CLUSTER


class Badge:
    def __init__(self, port, mpremote):
        self.port = port
        self.mpremote = mpremote.split()

    def run(self, *args, timeout=180, check=True):
        # Just after a reset the port can exist but not answer yet: retry.
        for attempt in range(5):
            result = subprocess.run(self.mpremote + ["connect", self.port] + list(args),
                                    capture_output=True, text=True, timeout=timeout)
            output = result.stdout + result.stderr
            busy = "failed to access" in output or "could not enter raw repl" in output
            if result.returncode == 0 or not check or not busy:
                break
            time.sleep(2)
        if check and result.returncode != 0:
            fail("mpremote %s failed:\n%s" % (" ".join(args)[:60], output[-2000:]))
        return result.stdout

    def survey(self, rels, dirs):
        """Hashes of rels on the badge (None if missing), every file under dirs,
        and the bytes free on /system."""
        script = "FILES = %r\nDIRS = %r\n%s" % (["/system/" + r for r in rels], ["/system/" + d for d in dirs], DEVICE_SCRIPT)
        hashes, found, free = {}, [], None
        for line in self.run("exec", script).splitlines():
            kind, _, rest = line.partition(" ")
            if kind == "H":
                digest, _, path = rest.partition(" ")
                hashes[path[len("/system/"):]] = digest
            elif kind == "M":
                hashes[rest[len("/system/"):]] = None
            elif kind == "F":
                found.append(rest[len("/system/"):])
            elif kind == "S":
                free = int(rest)
        if len(hashes) != len(rels) or free is None:
            fail("could not read the badge's files over serial")
        return hashes, found, free


def find_port(port, wait=0):
    """The badge's serial port, waiting up to `wait` seconds for it, as it
    takes a few seconds to come back after a reset."""
    deadline = time.time() + wait
    while True:
        ports = [port] if port and os.path.exists(port) else sorted(glob.glob("/dev/cu.usbmodem*"))
        if len(ports) > 1:
            fail("several serial ports (%s); pick one with --port" % ", ".join(ports))
        if ports or time.time() >= deadline:
            return ports[0] if ports else None
        time.sleep(1)


def wait_for(check, what, timeout=60):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if check():
            return
        time.sleep(1)
    fail("timed out waiting for %s" % what)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("paths", nargs="*", default=[BADGE], help="files or folders inside badge/ (default: all of it)")
    parser.add_argument("--prune", action="store_true", help="delete badge files under the given app folders that the repo lacks")
    parser.add_argument("--force", action="store_true", help="copy every file, even ones that already match")
    parser.add_argument("--dry-run", action="store_true", help="show the plan and change nothing")
    parser.add_argument("--port", help="serial port (default: the one /dev/cu.usbmodem*)")
    parser.add_argument("--mpremote", default="uvx mpremote", help="command that runs mpremote (default: %(default)s)")
    parser.add_argument("--no-reset", action="store_true", help="leave the badge as it is at the end, not on its menu")
    args = parser.parse_args()

    files = local_files(args.paths)
    if not files:
        fail("nothing to deploy")
    dirs = []
    for path in args.paths:
        if os.path.isdir(path):
            rel = os.path.relpath(os.path.abspath(path), BADGE).replace(os.sep, "/")
            if args.prune and not prunable(rel):
                fail("--prune only works on app folders like badge/apps/<name>, not %s" % (rel if rel != "." else "badge/"))
            dirs.append(rel if rel != "." else "apps")
    rels = sorted(files)

    if os.path.isdir(VOLUME):
        fail("the badge is already in disk mode. Eject it (diskutil eject %s) and run again, "
             "so its files can be checked over serial" % VOLUME)
    port = find_port(args.port, wait=20)
    if not port:
        fail("no badge found: no serial port and no BADGER drive. If it's plugged in, it has hung; press RESET on its back once")
    badge = Badge(port, args.mpremote)

    print("checking %s on the badge over %s" % (count(rels, "file"), port))
    hashes, found, free = badge.survey(rels, dirs)
    differs = {r for r in rels if hashes[r] != sha256(files[r])}
    changed = [r for r in rels if args.force or r in differs]

    def owned(f):
        return any(f.startswith(d + "/") for d in dirs if prunable(d))

    # ._ files already there are left alone unless pruning an app folder;
    # only new ones fail the check at the end.
    old_junk = {f for f in found if os.path.basename(f).startswith("._")}
    extra = sorted(f for f in found if f not in files and f not in old_junk and owned(f))
    for r in changed:
        print("  %s %s" % ("new    " if hashes[r] is None else "changed" if r in differs else "same   ", r))
    for f in extra:
        print("  %s %s" % ("delete " if args.prune else "extra  ", f))
    for f in sorted(old_junk):
        print("  %s %s (macOS metadata from an earlier copy)" % ("delete " if args.prune and owned(f) else "junk   ", f))
    if (extra or any(owned(f) for f in old_junk)) and not args.prune:
        print("  (extra files stay; --prune deletes them)")

    to_delete = (extra + sorted(f for f in old_junk if owned(f))) if args.prune else []
    if args.dry_run or not (changed or to_delete):
        print("dry run: nothing changed" if args.dry_run else "already up to date")
        if not args.no_reset:
            badge.run("reset", check=False)
        return

    needed = sum(clusters(os.path.getsize(files[r])) + CLUSTER for r in changed)
    freed = sum(clusters(os.path.getsize(files[r])) for r in changed if hashes[r] is not None)
    if needed - freed > free - SPARE:
        fail("not enough room on /system: need %d KB more, %d KB free" % ((needed - freed) // 1024, free // 1024))

    print("switching to disk mode")
    badge.run("exec", "import powman; powman.reset_into_msc()", timeout=30, check=False)
    wait_for(lambda: os.path.isdir(os.path.join(VOLUME, "apps")), "the BADGER drive")

    started = time.time() - 2  # FAT keeps times to 2 seconds
    for rel in to_delete:
        os.remove(os.path.join(VOLUME, rel))
    for rel in changed:
        target = os.path.join(VOLUME, rel)
        if os.path.exists(target):
            os.remove(target)
    os.sync()
    for rel in changed:
        target = os.path.join(VOLUME, rel)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(files[rel], "rb") as src, open(target, "wb") as dst:
            dst.write(src.read())
    os.sync()

    # macOS leaves a ._ file beside what it writes; only remove the new ones.
    removed = 0
    for root, _, names in os.walk(VOLUME):
        if os.path.basename(root) in (".fseventsd", ".Trashes", ".Spotlight-V100"):
            continue
        for name in names:
            path = os.path.join(root, name)
            if name.startswith("._") and os.path.getmtime(path) >= started:
                os.remove(path)
                removed += 1
    os.sync()
    print("copied %d, deleted %d, cleaned up %s" % (len(changed), len(to_delete), count(range(removed), "._ file")))

    subprocess.run(["diskutil", "eject", VOLUME], capture_output=True, check=True)
    print("ejected; waiting for the badge to come back")
    wait_for(lambda: find_port(args.port), "the badge's serial port")
    time.sleep(2)

    hashes, found, _ = badge.survey(rels, dirs)
    bad = [r for r in rels if hashes[r] != sha256(files[r])]
    junk = [f for f in found if os.path.basename(f).startswith("._") and f not in old_junk]
    leftover = [f for f in to_delete if f in found]
    for r in bad:
        print("  MISMATCH %s" % r)
    for f in junk:
        print("  JUNK     %s" % f)
    for f in leftover:
        print("  NOT DELETED %s" % f)
    if not args.no_reset:
        badge.run("reset", check=False)
    if bad or junk or leftover:
        fail("verification failed; run again to retry the files above")
    print("verified %s on the badge%s" % (count(rels, "file"), "" if args.no_reset else "; it's back on its menu"))


if __name__ == "__main__":
    main()
