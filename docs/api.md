# Badgeware API notes

The badge runs Pimoroni's Badgeware on MicroPython. These are the parts used
and checked while building the examples.

Badgeware's names (`badge`, `screen`, `image`, `BUTTON_LEFT`, `HIRES`, ...)
resolve like builtins, so apps don't import them. They don't appear in
`dir(builtins)` or `globals()`, though, and `getattr(builtins, name)` misses
them. Refer to them by name, or with `eval(name)` inside `try/except
NameError` (see [hardware.md](hardware.md#buttons)).

## App shape

```python
import time

def update():
    # Called once per display refresh.
    if badge.pressed(BUTTON_BACK):
        return True   # any non-None return ends run() and the app
    ...               # draw into `screen`
    return None

def on_exit():
    ...               # Badgeware's Home interrupt calls this; make it safe to call twice

badge.mode(HIRES | VSYNC)
try:
    run(update)
finally:
    on_exit()         # restore badge.mode, badge.default_clear, screen.antialias
```

- Module-level code runs at launch, with the app's folder as the working
  directory, so `image.load("assets/x.png")` works.
- `run(update)` calls `update()`, refreshes the display, and repeats. With
  `badge.default_clear = None` it doesn't clear the screen between calls, so
  you can draw only what changed.
- Restore anything global you changed (mode, `default_clear`, antialias)
  before returning.

## `badge`

| Call | Notes |
| --- | --- |
| `badge.mode()` / `badge.mode(HIRES \| VSYNC)` | Get or set the display mode. `HIRES` is 320x240 and `LORES` is 160x120. |
| `badge.default_clear` | The colour cleared before each `update()`, or `None` to keep the screen |
| `badge.pressed(b)`, `held(b)`, `released(b)` | Button state. With no argument: any button. |
| `badge.poll()` | Read the inputs. `run()` does this for you. |
| `badge.imu()` | `(ax, ay, az, gx, gy, gz)`, raw; 16384 is 1 g. Costs ~0.02 ms. See [hardware.md](hardware.md#motion-sensor). |
| `badge.ticks` | Milliseconds, as used by the menu |
| `badge.battery_level()`, `badge.is_charging()` | |

## `screen` and `image`

`screen` is an `image` (RGB565) that is the display.

| Call | Notes |
| --- | --- |
| `image(w, h)` | A new RGBA8888 image. A third argument must be a buffer to back it, not a format. |
| `image.load(path_or_bytes)` | Loads a PNG or JPEG |
| `img.load_into(path_or_bytes)` | Decodes into an existing image of the same size, with no allocation. **Never on `screen`: that hangs the badge.** |
| `img.window(x, y, w, h)` | A view of part of an image, with no copy (~0.04 ms). It blits like any image. |
| `img.raw` | A live `bytearray` view of the pixels: RGBA8888, `stride = w * 4`. `screen.raw` is RGB565, little-endian: saving it captures the screen ([workflow.md](workflow.md#capturing-the-screen)). |
| `img.get(x, y)` | A `color` |
| `screen.blit(img, vec2(x, y))` | Alpha-composites. Off-screen parts are clipped at no cost. |
| `screen.blit(img, rect(x, y, w, h))` | Scales the image to fill the rect, cheaply: 32 x 32 to 64 x 64 took 0.57 ms. |
| `screen.blit(img, src, dst)` | The part of the image in `rect` `src`, scaled into `rect` `dst`. |
| `screen.pen = color.rgb(r, g, b[, a])` | Then `rectangle`, `clear`, `text`, `shape`, ... |
| `screen.antialias` | `image.OFF`, `image.X2` or `image.X4`. Blits ignore it. |
| `screen.font = font.<name>` | Fonts seen: `font.salty`, `font.ignore`, `font.absolute` |
| `screen.text(s, x, y)`, `screen.measure_text(s)` | |
| `screen.clip = rect(x, y, w, h)` | Used by the menu to clip tiles |

Images also have filters that haven't been tested here: `blur`, `dither`,
`bloom`, `crt`, `glitch`, `oilpaint`, `vignette`, and more (see `dir(image)`).

There's no RGB565 image type, so every blit converts RGBA into the screen's
format.

**Images can be drawn on**, like the screen. Each has its own `pen`,
`antialias` and `fill_rule`, and `shape`, `rectangle`, `circle` and the rest
work on it. A new `image(w, h)` starts fully transparent. That makes it cheap
to draw something complicated once, with `image.X4` antialiasing, and blit it
every frame after (Repo Defender's distant bots).

## Shapes

Vector shapes are drawn with `screen.shape(...)` in the current pen:

```python
from array import array
s = shape.custom(array("f", [x0, y0, x1, y1, ...]), ...)   # one array per contour
s.transform = mat3().translate(cx, cy).scale(size)
screen.fill_rule = image.NON_ZERO
screen.shape(s)
```

The menu's icons and tile animations are drawn this way. See
[menu.md](menu.md).

| Call | Notes |
| --- | --- |
| `shape.line(x0, y0, x1, y1, width)` | A line as a filled shape. The width is required. |
| `shape.combine([s1, s2, ...])` | One shape from many, drawn in one call: a whole wireframe, say. |
| `shape.stroke(s, width)` or `s.stroke(width)` | An outline of `s`, as a shape. `shape.PATH_OPEN`, `JOIN_*` and `CAP_*` exist for it. |
| `shape.circle`, `rectangle`, `rounded_rectangle`, `regular_polygon`, `star`, `arc`, `pie`, `squircle`, `ellipse` | Not tried here yet. |
| `s.bounds()` | A `rect`, after the transform. |
| `mat3().translate(x, y).scale(sx, sy)` | `scale` takes one or two numbers, not a `vec2`. A negative `sx` mirrors. |

- **Widths are part of the shape.** A transform scales them along with
  everything else, so lines drawn at 10x get 10x thicker. To keep a fixed
  width in pixels, build the shape at a few sizes and pick the nearest.
- **Set the fill rule.** At the REPL it starts as `image.EVEN_ODD`, where
  overlapping parts cancel out and leave holes. The menu sets
  `image.NON_ZERO`, where they add up. An app shouldn't rely on either.

## Pointing at a button

Players won't know which physical button is "Select". Show them: draw toward
the button's spot beside the screen ([hardware.md](hardware.md#buttons)).
Repo Defender's title screen does it with a glowing copy of the `↩` printed
beside enter, and a bobbing arrow down at it:

```python
ENTER_X = 255   # BUTTON_SELECT: below the bottom edge, at this x

def draw_enter_arrow(t):
    tip = 236 + int(3 * math.sin(t * 6))   # bob toward the edge
    screen.pen = color.rgb(90, 255, 140)
    screen.rectangle(ENTER_X - 1, tip - 24, 2, 20)            # shaft
    for k in range(8):                                          # head
        screen.rectangle(ENTER_X - k - 1, tip - 4 - k - 1, 2, 2)
        screen.rectangle(ENTER_X + k - 1, tip - 4 - k - 1, 2, 2)
```

For buttons on the right edge (Up and Down), point right at `x ≈ 316`, at
their `y`.

## Also available

- `display.update()`, `display.set_async(bool)`. Async made no measurable
  difference in tests.
- `launch(path)` runs an app or folder and returns its result. `reset()`
  reboots.
- `powman.reset_into_msc()` reboots into disk mode.
- `vec2`, `rect`, `mat3`, `color.rgb(...)`, and `time.ticks_ms()` and
  `ticks_us()` for timing.
