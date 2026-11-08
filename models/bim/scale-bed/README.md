---
title: "Scale Bed"
slug: scale-bed
category: bim
created: 2026-11-08
updated: 2026-11-08
version: 1
status: draft
description: "Parametric bed with mattress and headboard at 1:20, for 3D printing"
tags: [bed, furniture, scale-model, 3d-printing]
author: "Luis C. Berrocal"
freecad:
  source: scale-bed.FCStd
  parametric: true
  freecad_version: "1.1"
---

# Scale Bed

A scale-model bed in three separate printable bodies:

- **Mattress**: block with rounded corners, sitting on the platform.
- **Bed**: platform with four square corner posts.
- **Headboard**: board against the head end of the bed.

## Parameters

All sizes are in the `globals` spreadsheet. Column B holds the real-world size,
and column C divides it by the scale and holds the alias the bodies use. The
scale is in `B2` (`20` means 1:20). Edit column B or the scale in the FCStd and
recompute; the bodies follow.

| Parameter | Default | Alias |
|---|---|---|
| Mattress length | 188 cm | `mt_length` |
| Mattress width | 96.5 cm | `mt_width` |
| Mattress height | 15 cm | `mt_height` |
| Mattress fillet | 5 cm | `mt_fillet` |
| Bed offset | 2 cm | `bd_offset` |
| Bed body height | 10 cm | `bd_body_height` |
| Post size | 10 cm | `bd_post_size` |
| Post height | 25 cm | `bd_post_height` |
| Headboard height | 100 cm | `hb_height` |
| Headboard thickness | 5 cm | `hb_thickness` |

At 1:20 the printed parts are about 48 x 94 x 7.5 mm (mattress),
50 x 96 x 12.5 mm (bed) and 50 x 2.5 x 50 mm (headboard).

## Rebuilding

`build_bed.py` creates the FCStd and one `.3mf` per body. Running it overwrites
them, and it also overwrites any edits made directly in the FCStd:

```sh
/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd \
    models/bim/scale-bed/build_bed.py < /dev/null
```

## Printing notes

- Print the bed upside down (platform top on the build plate) so the posts need no supports.
- Print the headboard lying flat.
- Thin features at 1:20: the 2 cm offset becomes a 1 mm ledge, and the 5 cm
  headboard becomes a 2.5 mm board.
