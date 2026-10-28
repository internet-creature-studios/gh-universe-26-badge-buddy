"""Run the app on the badge with a fixed, fake tilt and print its benchmark.

    uvx mpremote connect /dev/cu.usbmodem1101 exec "AX = 16384
    $(cat examples/internet-creature-studios/bench_tilt.py)"

AX is the raw accelerometer x reading to fake: 0 is level, 16384 a full tip
left, -16384 a full tip right. Define APP the same way to run a copy of the
app from somewhere other than /system/apps/internet_creature. The app prints
ICS_BADGE_BENCHMARK once it has drawn enough frames; stop it with Ctrl-C or
a reset.
"""

import os

try:
    app_dir = APP  # noqa: F821 - optionally defined ahead of this source
except NameError:
    app_dir = "/system/apps/internet_creature"
os.chdir(app_dir)
with open("__init__.py") as source_file:
    source = source_file.read()
hook = 'READ_IMU = getattr(badge, "imu", None)'
if hook not in source:
    raise RuntimeError("IMU hook not found in the app")
fake_ax = AX  # noqa: F821 - defined ahead of this source in the exec string
source = source.replace(hook, "READ_IMU = lambda: (%d, 0, 0)" % fake_ax)
exec(source, {"__name__": "__main__"})
