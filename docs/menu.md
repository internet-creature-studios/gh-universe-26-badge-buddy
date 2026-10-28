# The launcher menu: tiles, names and icons

The menu is itself an app, `/system/apps/menu`. It finds apps by scanning
`/system/apps`.

## How an app gets a tile

- **Which folders:** every folder in `/system/apps`, except `menu`, that holds
  `__init__.py` or `__init__.mpy`.
- **Name:** from the folder name, with underscores becoming spaces and each
  word capitalised, so `internet_creature` shows as "Internet Creature". (The
  ribbon shows it lowercased.)
- **Order:** the stock apps come first, in the `APP_ORDER` list in
  `menu/app.py`. Any others follow, alphabetically.
- **Tile colour:** from a fixed palette, chosen by the tile's position.
- **Icon:** looked up by folder name in `ICONS`, from the menu's `icons`
  module. An app without an entry gets the generic `default` icon. **An
  `icon.png` in the app's folder is ignored.**

## Adding an icon

`ICONS` maps a folder name to a tuple of contours. Each contour is a flat
tuple `(x0, y0, x1, y1, ...)`, in units where the icon spans about -0.5 to 0.5
across, centred on 0, with y pointing down. The menu fills them in white, with
the non-zero rule, at 48 px for a 75 px tile:

```python
ICONS = {
    "default": ((...), (...)),
    "internet_creature": (
        (0.184, -0.381, 0.21, -0.378, ...),   # the 3
        (...),                                # one dot
        (...),                                # the other dot
    ),
    ...
}
```

The menu imports the compiled `icons.mpy` from `/system/apps/menu/`. The source
is `/system/apps/menu/src/icons.py`, which isn't on the import path. To add an
icon:

1. Copy `src/icons.py` off the badge, or start from `stock/apps/menu/src/`.
2. Add your entry.
3. Compile it with **mpy-cross v1.29**. Compiling the stock `icons.py` with it
   reproduces the stock `icons.mpy` byte for byte, so this is the right
   version.

   ```bash
   uvx mpy-cross -s icons.py -o icons.mpy icons.py
   ```

4. Copy `icons.mpy` (and `src/icons.py`, to keep them matching) onto the badge
   in disk mode.

A firmware update will probably replace these files. Keep the originals, which
are in `stock/`, so you can restore them.

`examples/internet-creature-studios/trace_icon.py` shows one way to make the
contours: it traces a shape out of a logo image.

## Selection animations

When a tile is selected, its icon can play an animation. The menu looks for
`/system/apps/menu/anim/<folder name>.bin`, but only if the folder name also
has an `ICONS` entry. The animation plays once and holds its last frame, which
should match the static icon.

The format, `BWIC` version 3, is little-endian:

```
"BWIC"             4 bytes
version            u16 = 3
fps                u8
frame count        u16
frame offsets      u32 x frame count, from the start of the file
then for each frame:
  contour count    u8
  then for each contour:
    point count    u16
    points         f32 x, f32 y, point count times, in icon units
```

`examples/internet-creature-studios/build_icon.py` writes one: a little
squash-and-stretch, then the `:3` face blinks.
