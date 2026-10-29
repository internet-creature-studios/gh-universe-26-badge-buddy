# Repo Defender: low-poly powerup proposals

**In the game since 0.3.0**, ported into `badge/apps/repo_defender/__init__.py`
as proposed: shaded once at a fixed yaw and pitch, with the triangles sorted,
then baked into images at two sizes (see examples/repo-defender/README.md).

The game already uses `screen.triangle`, so these are filled, flat-shaded triangles in 3 tones per colour (light, mid and shadow), not wireframe.
The colours come from the game's existing pens: CUP, COFFEE, CRUST, PEPPERONI and the pizza pickup yellow.

| Model | Points | Triangles | Idea |
|---|---|---|---|
| coffee | 94 | 106 | tapered 8-sided cup, sleeve band, square handle, dark coffee top, 3 steam wisps (6 sway frames via `coffee(frame)`) |
| pizza | 51 | 55 | thick wedge with a raised crust lip, cheese top, 3 hexagon pepperoni, a cheese drip |

- powerups.py: the models as points + (i, j, k, material) faces
- render_powerups.py: flat shading and a back-to-front triangle sort, with pepperoni and the coffee surface biased to draw last
- sheet_powerups.py: rebuilds everything (run it from this folder; it needs ../render.py from design/enemies)
- proposal_sheet.png, *_large.png, *_spin.gif, ingame_1x.png, ingame_x3.png

To match the bots, the game would pre-flatten each model once at a fixed yaw and pitch (like `FLAT[]`), with the triangle order already sorted. That leaves no per-frame sorting on the badge.
