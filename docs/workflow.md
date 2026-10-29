# Working with the badge from a Mac

The badge has two USB personalities. A normal boot gives a **serial port**,
which runs MicroPython commands. **Disk mode** gives the `BADGER` drive,
which is the only way to write `/system`, where apps live.

For prerequisites and a first install, start with the
[README](../README.md#install-on-your-badge). The commands here use `uvx`
to provide `mpremote` and `mpy-cross` without separate installations.

Find the serial port with `ls /dev/cu.usbmodem*`. Replace
`YOUR_BADGE_PORT` in the commands below with the badge's full port path.
If there's no port and no `BADGER` drive, see [reset and recovery](#reset-and-recovery).

```bash
uvx mpremote connect YOUR_BADGE_PORT fs ls :/system/apps
uvx mpy-cross --version   # v1.29, the version that matches the badge's .mpy files
```

## Serial mode (normal boot)

- **Connecting interrupts whatever is running**, the menu or an app. Run
  `mpremote ... reset` when you're done, so the badge reboots to the menu.
- **Reading works.** `fs ls`, `fs cp :/system/... local`, and `exec "..."` to
  run code.
- **Writing `/system` fails** with `Read-only file system`.
- **The root `/` is writable** and has about 1 MB free. It's the place to
  try out an app without installing it (below). Clean up afterwards.

### Trying an app without installing it

1. Copy the app and its assets to a folder on the root, such as `/dev_app`.

   ```bash
   uvx mpremote connect YOUR_BADGE_PORT fs mkdir :/dev_app + fs cp -r myapp/. :/dev_app/
   ```

2. Run it from that folder. The app's `run(update)` loop doesn't return until
   it exits, so cap the command with a timer:

   ```bash
   perl -e 'alarm 15; exec @ARGV' uvx mpremote connect YOUR_BADGE_PORT \
     exec "import os; os.chdir('/dev_app'); exec(open('__init__.py').read(), {'__name__': '__main__'})"
   ```

   `print` output, benchmarks for example, comes back over serial. The
   installed app can also be started the way the menu does it:
   `exec "launch('/system/apps/<name>')"`.

3. Reset the badge to the menu, and remove `/dev_app` when you're finished.

## Installing with the deploy script

`tools/deploy.py` installs files from `badge/` and does every step below for
you. It plans and verifies over serial, so the Mac's cache never gets the
last word:

```bash
python3 tools/deploy.py badge/apps/my_app             # one app (paths inside badge/)
python3 tools/deploy.py                               # everything in badge/
python3 tools/deploy.py badge/apps/my_app --dry-run   # show what would change
python3 tools/deploy.py badge/apps/my_app --prune     # also delete files the repo no longer has
```

With no path, the script installs both example apps **and shared menu
files**. Matching files are replaced, including the menu icon table; merge
any custom icon entries first, or pass just an app folder. Extra files are
kept unless you explicitly use `--prune`.

The script detects a single serial port automatically. If several match,
add `--port YOUR_BADGE_PORT`. Start in normal serial mode: if `BADGER` is
already mounted, eject it and wait for the serial port before deploying.

- **Planning:** it hashes the badge's copies over serial first. If nothing
  differs, it stops without entering disk mode.
- **`--dry-run`:** writes no badge files, but still queries the connected
  badge, interrupts the running app, and resets to the menu. `--no-reset`
  skips that final reset; it doesn't prevent the serial interruption.
- **Copying:** it checks there's room, switches to disk mode, deletes and then
  freshly copies only the files that differ, removes the `._` files macOS
  added, and ejects.
- **Checking:** it hashes every file again on the badge, flags any new `._`
  files, and resets the badge to its menu. Any mismatch makes it exit non-zero.
- **`--prune`:** works only on app folders (`badge/apps/<name>`), never on
  `apps/` or `apps/menu`, because those hold the firmware's own files. It
  lists what it will delete; check that with `--dry-run` first.
- **`secrets.py`:** the script refuses to deploy it.

It needs only Python 3 and `uv`. The rest of this section is what the script
does, for when you need to do it by hand.

## Disk mode: writing `/system`

Enter disk mode from software. It's the same call the stock Mass Storage app
makes:

```bash
uvx mpremote connect YOUR_BADGE_PORT exec "import powman; powman.reset_into_msc()"
```

The serial connection drops, which is expected, and the `BADGER` drive mounts
a few seconds later. It is `/system`: `BADGER/apps/<name>/` is
`/system/apps/<name>/`.

By hand: **double-tap RESET** on the back of the badge. This is confirmed on a
real badge, and the firmware handles it the same way as the software call.
It's the way in when nothing can reach the badge over serial.

**Ejecting** (`diskutil eject /Volumes/BADGER`) reboots the badge back to the
menu.

### Copying files safely

macOS and the badge's FAT drive don't get along. Follow these steps every
time:

1. **Touch a marker file first.** You'll use it to find the files macOS adds.
2. **Delete, then copy fresh. Don't overwrite in place.** Overwritten files
   have landed with wrong 4 KB clusters on disk, while the Mac's cache still
   showed the right bytes.
3. **Delete the `._*` files.** macOS writes a 4 KB `._name` file beside every
   file it copies, even with `cp -X` or `COPYFILE_DISABLE=1`. Across a few
   hundred files they fill the drive.

   ```bash
   find /Volumes/BADGER -name '._*' -newer "$MARKER" -type f -delete
   ```

4. **`sync`, then eject.**
5. **Verify over serial, from the badge itself.** Checksums read on the Mac
   can come from its cache, and unmounting to remount sometimes drops the badge
   out of disk mode. Pull the app back and compare:

   Replace `YOUR_APP` with the installed app's folder name.

   ```bash
   uvx mpremote connect YOUR_BADGE_PORT fs cp -r :/system/apps/YOUR_APP /tmp/check/
   diff -r /tmp/check/YOUR_APP badge/apps/YOUR_APP
   ```

Mass deletes and copies on the drive are slow: replacing about 400 small
files took several minutes. While in disk mode, `diskutil verifyVolume
/Volumes/BADGER` checks the FAT structure read-only.

Keep an eye on space. `/system` is 12.5 MB and the stock firmware uses most of
it, so check `df -h /Volumes/BADGER`.

## Reset and recovery

| Situation | What to do |
| --- | --- |
| Done working over serial | `uvx mpremote connect YOUR_BADGE_PORT reset` reboots to the menu |
| An app crashed | The launcher reboots to the menu by itself |
| No serial port and no `BADGER` drive | The badge has hung. **Press RESET on the back once.** It comes back in serial mode with the menu |
| Need disk mode | Double-tap RESET, run `powman.reset_into_msc()` over serial, or open the Mass Storage app in the menu |

Known ways to hang the badge so that it needs a RESET press:

- `screen.load_into(path)`: decoding a PNG straight into the screen buffer.

When you try an untested native call, tell the person at the badge that it
might need a RESET press.

## Testing game rules on the badge

Buttons can't be pressed from a script, but rules can still be checked on the
real hardware:

1. Read the app's source on the device.
2. Swap its `run(update)` line for a function that sets up situations (spawn a
   bot here, set a stat there) and calls the game's own update.
3. Print `PASS` or `FAIL` for each check.
4. `exec` the result.

`examples/repo-defender/selftest.py` is a worked example: it checks reload
timing, damage, pickups, shields and upgrade offers, then measures a busy
scene's frame rate.

When an assertion depends on randomness, such as a weaving bot's starting
point, pin it in the test. Otherwise the test flakes.

## Benchmarking

Time code on the device with `time.ticks_us()`. Inside an app, print a summary
line after N frames, and it comes back over serial. `bench_tilt.py` in the
example runs an app with a faked tilt reading.
