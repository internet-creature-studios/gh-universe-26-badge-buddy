# Performance and limits

Measured on the badge in HIRES mode (320x240), with `time.ticks_us()`.

## Costs

| Operation | Cost |
| --- | --- |
| Display refresh with `VSYNC` | 11.2 ms; each frame takes a whole number of them |
| `screen.blit` | ~0.26 µs per destination pixel + ~0.14 ms per call |
| Blit of a full screen | ~20 ms |
| Fully transparent pixels | Cost the same as opaque ones; half-transparent ones cost ~12% more |
| Blit of a 1280 px wide strip | Only the on-screen part costs anything |
| `img.window(...)` | ~0.04 ms, and blits at the same speed as a plain image |
| PNG decode, 320x240 (~37 KB) | 72 to 78 ms (about 1 µs per pixel) |
| PNG decode from `bytes` already in RAM | ~67 ms: file reading is ~19 ms of the 78 |
| 256-colour palette PNG decode | ~55 ms, but it bands smooth gradients |
| JPEG decode, same size | 67 to 80 ms: no faster than PNG |
| `vec2(...)` | ~9 µs |

## The frame budget

With `VSYNC`, a frame takes 1, 2, 3 or 4 refreshes:

| Frame rate | Frame time | Rough budget for drawing |
| --- | --- | --- |
| 44.6 fps | 22.4 ms | ~12 ms |
| **29.8 fps** | 33.6 ms | **~21 ms** |
| 22.3 fps | 44.8 ms | ~32 ms |

The "Python and display" part of each frame is about 10 to 12 ms. A frame
that's 1 ms over a boundary drops a whole refresh, and frames that alternate
between two rates judder. Leave a millisecond or two of slack.

Without `VSYNC`, frames aren't rounded up: 36 ms of work ran at 27 fps. Fast
horizontal motion may tear, though. That wasn't checked.

## What works

- **Draw only what changed.** With `badge.default_clear = None` the screen
  keeps its pixels, so a frame with nothing new can skip drawing entirely.
- **Decode once, at launch.** Over 7 MB of heap holds plenty of images. Video
  playback that decodes a PNG per frame tops out around 12 fps, while live
  layers blitted from RAM run at 30.
- **Crop what you blit.** Blit time goes by area, transparent or not, so cut
  big images into tiles cropped to their visible pixels. Each blit costs
  ~0.14 ms, so tiles narrower than ~100 px stop paying off. Plan tiles at build
  time with that cost model (see `plan_tiles` in
  `examples/internet-creature-studios/render_layers.py`).
- **Keep overlap down.** Layers that overlap get blitted twice. Merging layers
  that barely differ saved ~2 ms per frame.
- **Fake speed with blur.** Precomputed, horizontally motion-blurred copies of
  fast layers look smooth where sharp ones strobe at 20+ px per frame.

## Limits found

- `/system` is read-only to MicroPython. Writing it needs disk mode.
- About 1 MB is writable on the root over serial.
- `screen.load_into()` hangs the badge.
- There's no RGB565 image type, so there's no faster copy to the screen.
- `badge.imu()` reads zeros at the REPL until `badge.poll()` runs.
