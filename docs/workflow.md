# Working with the badge from a Mac

The badge has two USB personalities. A normal boot gives a **serial port**,
which runs MicroPython commands. **Disk mode** gives the `BADGER` drive,
which is the only way to write `/system`, where apps live.

The tools are run with `uv`, so nothing needs installing:

```bash
uvx mpremote connect /dev/cu.usbmodem1101 fs ls :/system/apps
uvx mpy-cross --version   # v1.29, the version that matches the badge's .mpy files
```

Find the port with `ls /dev/cu.usbmodem*`. If there's no port and no `BADGER`
drive, see [reset and recovery](#reset-and-recovery).

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
   uvx mpremote connect /dev/cu.usbmodem1101 fs mkdir :/dev_app + fs cp -r myapp/. :/dev_app/
   ```

2. Run it from that folder. The app's `run(update)` loop doesn't return until
   it exits, so cap the command with a timer:

   ```bash
   perl -e 'alarm 15; exec @ARGV' uvx mpremote connect /dev/cu.usbmodem1101 \
     exec "import os; os.chdir('/dev_app'); exec(open('__init__.py').read(), {'__name__': '__main__'})"
   ```

   `print` output, benchmarks for example, comes back over serial. The
   installed app can also be started the way the menu does it:
   `exec "launch('/system/apps/<name>')"`.

3. Reset the badge to the menu, and remove `/dev_app` when you're finished.

## Disk mode: writing `/system`

Enter disk mode from software. It's the same call the stock Mass Storage app
makes:

```bash
uvx mpremote connect /dev/cu.usbmodem1101 exec "import powman; powman.reset_into_msc()"
```

The serial connection drops, which is expected, and the `BADGER` drive mounts
a few seconds later. It is `/system`: `BADGER/apps/<name>/` is
`/system/apps/<name>/`.

According to the firmware's own comments, double-tapping RESET does the same
thing. That hasn't been tested here.

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

   ```bash
   uvx mpremote connect /dev/cu.usbmodem1101 fs cp -r :/system/apps/<name> /tmp/check/
   diff -r /tmp/check/<name> badge/apps/<name>
   ```

Mass deletes and copies on the drive are slow: replacing about 400 small
files took several minutes. While in disk mode, `diskutil verifyVolume
/Volumes/BADGER` checks the FAT structure read-only.

Keep an eye on space. `/system` is 12.5 MB and the stock firmware uses most of
it, so check `df -h /Volumes/BADGER`.

## Reset and recovery

| Situation | What to do |
| --- | --- |
| Done working over serial | `uvx mpremote connect /dev/cu.usbmodem1101 reset` reboots to the menu |
| An app crashed | The launcher reboots to the menu by itself |
| No serial port and no `BADGER` drive | The badge has hung. **Press RESET on the back once.** It comes back in serial mode with the menu |
| Need disk mode | `powman.reset_into_msc()` over serial, or the Mass Storage app in the menu |

Known ways to hang the badge so that it needs a RESET press:

- `screen.load_into(path)`: decoding a PNG straight into the screen buffer.

When you try an untested native call, tell the person at the badge that it
might need a RESET press.

## Benchmarking

Time code on the device with `time.ticks_us()`. Inside an app, print a summary
line after N frames, and it comes back over serial. `bench_tilt.py` in the
example runs an app with a faked tilt reading.
