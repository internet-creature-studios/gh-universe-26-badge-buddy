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
| `screen.rectangle` filling the whole screen, or `screen.clear()` | ~0.58 ms: ~35 times cheaper than blitting the same area |
| `screen.rectangle`, small | ~0.02 to 0.04 ms |
| `screen.line`, 200 px | ~0.05 ms. It takes numbers (floats are fine) or two `vec2`s. |
| `screen.text`, 20 characters | ~0.35 ms with `font.salty` (17 px tall), ~0.6 ms with `font.ignore` (28 px) |
| `badge.imu()` | ~0.02 ms |

**Drawn shapes are far cheaper than blitted images.** Prefer rectangles,
lines and text for anything that changes every frame, and keep images for
detail that can't be drawn.

| Operation | Cost |
| --- | --- |
| `screen.triangle(x0, y0, x1, y1, x2, y2)`, about 30 px | ~0.1 ms |
| `screen.circle(x, y, r)`, r = 12 | ~0.03 ms |

Both are filled, and both also take `vec2`s.

The cost of any call is mostly Python's:

| Operation | Cost |
| --- | --- |
| Calling an empty Python function | 3.4 µs |
| `screen.pen = ...` | 14 µs |
| `screen.rectangle`, small | 17 µs |
| A two-rectangle health bar, with its arithmetic | 0.15 ms |

Vector shapes and images (see [api.md](api.md#shapes)):

| Operation | Cost |
| --- | --- |
| `screen.shape` of 53 combined lines, glow and core (two shapes), 8 to 70 px radius | 0.8 to 2.0 ms |
| The same with 112 lines | 1.2 to 2.2 ms |
| The same lines drawn one `screen.line` call at a time, core only | 1.9 ms (53 lines), 3.3 ms (112) |
| `image.X2` antialiasing on shapes | Nothing extra when small, 50 to 80% more at 70 px radius |
| Building a combined shape with `shape.line` and `shape.combine` | ~0.15 ms a line |
| Drawing a small model into an `image`, antialiased | 2 to 5 ms |
| `screen.blit` of that image, scaled with a `rect` | 0.1 ms (15 px) to 1.2 ms (72 px) |

**A shape costs about the same however small it's drawn**: its cost goes by
how many lines it has. For many small things, draw them once into images and
blit those.

**For vector-drawn games, Python is the cost, not pixels.** In Repo Defender's
busiest scene (12 bots, 4 pickups), a frame takes about 36 ms of Python, spread
over hundreds of small draw calls and the maths that projects each thing.

- **Floats allocate.** Every floating-point result is a heap object, so that
  frame allocates about 11 KB, and each garbage collection costs about 5.6 ms.
- **Live data makes every collection slower.** With about 840 KB of shapes and
  images kept, a collection takes 20 ms; with 1.4 MB, 39 ms. Collections are
  rare with 6 MB free, but each one is a dropped frame or two. Keep only what
  you draw from.
- **Spend calls on what's close.** Draw far-off things with fewer calls, and
  cache anything that doesn't change per frame, such as text widths.
- **Expect the heaviest moments to dip.** Repo Defender runs at about 30 fps
  in normal play, and about 19 to 20 in a stress scene of 12 neon wireframe
  bots and 4 pickups at once (21 to 24 with its earlier, flat bots).

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
