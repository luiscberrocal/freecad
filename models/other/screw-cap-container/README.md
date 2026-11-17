---
title: "Screw Cap Container"
slug: screw-cap-container
category: other
created: 2026-11-15
updated: 2026-11-15
version: 1
status: draft
description: "Screw-cap container for a 50 x 40 mm cylinder; 4-start thread closes in half a turn"
tags: [container, screw-cap, thread, 3d-print]
author: "Luis C. Berrocal"
freecad:
  source: screw-cap-container.FCStd
  parametric: true
  freecad_version: "1.1.1"
---

# Screw Cap Container

A container for a cylindrical item 50 mm across and 40 mm tall. It has a cap that
screws closed in about half a turn. It prints 1:1 without supports.

`build_screw_cap_container.py` is the source of truth. It overwrites the `.FCStd`, both
`.3mf` files and `screw-cap-container-plan.pdf`, so change `PARAMETERS` or `DERIVED` at
its top and rebuild instead of editing the FCStd.

## Parametric model

Every size in the FCStd comes from the `globals` spreadsheet, which has inputs such as
`item_d`, `wiggle`, `wall`, `starts` and `pitch`, plus formulas such as
`inner_d = item_d + wiggle` and `cap_h = lead / 2 + lead_in + wall`. The geometry uses
Part workbench features bound to those cells: cylinders and cuts, a helix, a sketch for
the ridge profile, a sweep, a clip band, and a polar array for the starts.

If you change a value in the sheet and recompute, the body, the cap and the plan views
follow. The plan's dimension text, its PDF and the 3MFs are written at build time, so
change the script and rebuild them after you change sizes.

On every run the build reads the inside size off the solids and fails if it doesn't
match `globals.inner_d` / `globals.inner_h`. It currently measures Ø52 × 42.

## Plan

There's a TechDraw page `Plan` in the FCStd, also written as
`screw-cap-container-plan.pdf`: A3 landscape with an ISO 5457 frame. It has these views:

- Section A-A at 2:1, hatched, with the thread visible. It's dimensioned with the
  inside Ø52 and 42, body Ø56 and 44, cap Ø62.8 and 9, closed height 46, the 6 mm
  engagement and the 2 mm floor.
- Front at 1:1, with Ø62.8 × 46.
- Top at 1:1, with the cutting plane A-A.
- Isometric.
- The `globals` table and the thread and print notes.

## Dimensions (mm)

| | |
|---|---|
| Inside (item + 2 mm wiggle room) | Ø52 x 42 (floor to underside of the closed cap) |
| Wall, floor, cap wall, cap top | 2 |
| Body | Ø56 (Ø58 over the thread) x 44 |
| Cap | Ø62.8 x 9 |
| Closed | Ø62.8 x 46 |

## Thread

- 4-start, right-handed, pitch 3 mm, lead 12 mm.
- 45° flanks, 1 mm deep, 2.5 mm at the root, 0.5 mm crest, so both sides print without
  supports.
- Clearance: 0.4 mm radial, about 0.5 mm axial.
- Half a turn advances the cap `lead / 2 = 6 mm`, which is the full engagement length.
  From first contact to closed takes about 165°.
- Cap height = 2 mm top + 6 mm engagement + 1 mm plain lead-in = **9 mm**.

The build checks that the closed parts don't overlap. The cap was also tested along
the whole screw path, in 30° steps up to 180°, with no interference.

## Printing

| File | Orientation | Size |
|---|---|---|
| `screw-cap-container-body.3mf` | upright, opening up | 58 x 58 x 44 mm |
| `screw-cap-container-cap.3mf` | top on the bed | 62.8 x 62.8 x 9 mm |

## Rebuilding

From the repo root:

```sh
/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd \
    models/other/screw-cap-container/build_screw_cap_container.py < /dev/null
```

A good run prints `ERRORS []` and then `DONE`.
