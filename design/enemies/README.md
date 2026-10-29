# Repo Defender: neon wireframe enemy proposals (proposal only; the game is unchanged)

Source game: badge/apps/repo_defender/__init__.py (MicroPython, 320x240 badge screen, draws with screen.line/rectangle).
The current bots are flat 2D heads (draw_head), four kinds in BOTS: bug, node_modules, hallucination, agent (boss).
The background (draw_world) is a dark sky in three bands, dim server towers, and a 1px green perspective floor grid.

Files
- proposal_sheet.png: everything on one sheet
- <key>_large.png: each creature large over the background
- ingame_1x.png / ingame_x3.png: all five at true in-game size; the near strip is in the sheet
- creatures.py: 3D vertex/edge/eye models (radius ~1; scale by the bot's `size`). Plain lists, so they port to MicroPython
- render.py: a PIL copy of draw_world, plus a projector; sheet.py builds everything (`python3 sheet.py`)

| Creature | Hex | Replaces | Idea |
|---|---|---|---|
| Skitter | #F4FF3A | Bug | six-legged mite, rushes straight in |
| Hoardshell | #2EF6FF | node_modules | domed, plated pillbug; armour rings drop off as it takes damage |
| Mirage | #FF3DF2 | Hallucination | drifting jellyfish with mismatched eyes; its tentacles sway with the weave |
| Overmind | #FF3355 | Rogue agent | horned wireframe dragon, wings spread (boss), 52 lines |
| Glitchwyrm | #A45CFF | spare | segmented serpent, for a possible 5th enemy |

In-game rendering: a 1px neon line over a dim 3px halo (about 35% of the colour), with white eye dots. The models are rotated a little and projected.
Edge counts are about 40 to 90, so drawing up to 2x that many line calls per bot each frame needs a performance check on the badge (see docs/performance.md).
