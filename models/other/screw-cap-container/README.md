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

`build_screw_cap_container.py` is the source of truth. It overwrites the `.FCStd` and
both `.3mf` files, so change the constants at its top and rebuild instead of editing the
FCStd.

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
