"""Screw-cap container for a 50 x 40 mm cylindrical item, printed 1:1.

Run with FreeCAD's interpreter from the repo root (keep the `< /dev/null`):

    /Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd \
        models/other/screw-cap-container/build_screw_cap_container.py < /dev/null

This script is the source of truth. It overwrites screw-cap-container.FCStd and the two
.3mf files next to it on every run.

Geometry (mm, Z = 0 is the bottom of the body, Z up, cap shown closed):

- Body: inside 52 x 42 (item + 2 mm wiggle room), 2 mm wall and floor.
- Thread: 4-start, right-handed, pitch 3 mm, lead 12 mm, 45 deg flanks so both
  parts print without supports. Half a turn moves the cap LEAD / 2 = 6 mm, which is
  the full engagement length, so the cap goes from first contact to closed in about
  half a turn.
- Cap: screws over an external thread on the body neck. Height = top + engagement +
  lead-in. Closed, the cavity is 42 mm from the floor to the underside of the cap.
"""

import math
import os

import FreeCAD
import Mesh
import MeshPart
import Part
from FreeCAD import Vector

# ----------------------------------------------------------------- parameters

ITEM_D = 50.0          # the cylindrical item to store
ITEM_H = 40.0
WIGGLE = 2.0           # added to the inside diameter and height
WALL = 2.0             # body wall, body floor, cap wall and cap top

THREAD_STARTS = 4
THREAD_PITCH = 3.0     # crest to crest along the axis
THREAD_DEPTH = 1.0     # radial height of a ridge
THREAD_ROOT_W = 2.5    # axial width of a ridge at its root (45 deg flanks)
RADIAL_CLEARANCE = 0.4 # between a ridge crest and the opposite wall
LEAD_IN = 1.0          # plain skirt below the cap's thread
TOP_GAP = 0.5          # plain neck above the body's thread

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
SLUG = "screw-cap-container"

# ------------------------------------------------------------------- derived

INNER_R = (ITEM_D + WIGGLE) / 2              # 26
INNER_H = ITEM_H + WIGGLE                    # 42
BODY_R = INNER_R + WALL                      # 28, thread root on the body
BODY_H = WALL + INNER_H                      # 44, rim = underside of closed cap
LEAD = THREAD_STARTS * THREAD_PITCH          # 12
ENGAGE = LEAD / 2                            # 6, travel in half a turn
CAP_SKIRT_H = ENGAGE + LEAD_IN               # 7
CAP_H = CAP_SKIRT_H + WALL                   # 9
CAP_INNER_R = BODY_R + THREAD_DEPTH + RADIAL_CLEARANCE   # 29.4
CAP_OUTER_R = CAP_INNER_R + WALL                         # 31.4
CAP_Z0 = BODY_H - CAP_SKIRT_H                # 37, bottom of the closed cap
CREST_W = THREAD_ROOT_W - 2 * THREAD_DEPTH   # 0.5

BODY_THREAD = (CAP_Z0 + LEAD_IN / 2, BODY_H - TOP_GAP)   # 37.5 .. 43.5
CAP_THREAD = (CAP_Z0 + LEAD_IN, BODY_H)                  # 38 .. 44


# ------------------------------------------------------------------- geometry


def ridge_profile(r_wall, outward, z):
    """Trapezoid ridge section in the XZ plane. The 45 deg flanks run on 0.3 mm into
    the wall, so no edge lies on the wall surface (that breaks the boolean fuse)."""
    s = 1 if outward else -1
    e, h, w, c = 0.3, THREAD_DEPTH, THREAD_ROOT_W, CREST_W
    pts = [(r_wall - s * e, -w / 2 - e), (r_wall + s * h, -c / 2),
           (r_wall + s * h, c / 2), (r_wall - s * e, w / 2 + e)]
    pts = [Vector(x, 0, z + dz) for x, dz in pts]
    return Part.makePolygon(pts + [pts[0]])


def thread(r_wall, outward, band, phase):
    """THREAD_STARTS helical ridges on a wall of radius r_wall, cut flat to band.
    At angle 0 a ridge is centred on z = phase + n * THREAD_PITCH."""
    lo, hi = band
    # Start on the absolute grid z = phase + n * LEAD, so the phase does not depend on
    # where the band begins.
    z_start = phase + LEAD * (math.floor((lo - phase) / LEAD) - 1)
    height = (hi - lo) + 2 * LEAD
    helix = Part.makeHelix(LEAD, height, r_wall)
    helix.translate(Vector(0, 0, z_start))
    one = Part.Wire(helix).makePipeShell([ridge_profile(r_wall, outward, z_start)], True, True)
    clip = Part.makeCylinder(r_wall + 5, hi - lo, Vector(0, 0, lo))
    if not outward:
        clip = clip.cut(Part.makeCylinder(r_wall - THREAD_DEPTH - 1, hi - lo, Vector(0, 0, lo)))
    one = one.common(clip)
    # Fusing the swept ridges with each other fails in OCC, so return them separately
    # and let the caller fuse them into the wall in a single multiFuse.
    ridges = [one]
    for i in range(1, THREAD_STARTS):
        copy = one.copy()
        copy.rotate(Vector(), Vector(0, 0, 1), 360.0 * i / THREAD_STARTS)
        ridges.append(copy)
    return ridges


def make_body():
    shell = Part.makeCylinder(BODY_R, BODY_H)
    shell = shell.cut(Part.makeCylinder(INNER_R, INNER_H + 1, Vector(0, 0, WALL)))
    return shell.multiFuse(thread(BODY_R, True, BODY_THREAD, 0.0)).removeSplitter()


def make_cap():
    cap = Part.makeCylinder(CAP_OUTER_R, CAP_H, Vector(0, 0, CAP_Z0))
    cap = cap.cut(Part.makeCylinder(CAP_INNER_R, CAP_SKIRT_H, Vector(0, 0, CAP_Z0)))
    # Half a pitch out of phase so the cap ridges sit between the body ridges.
    return cap.multiFuse(thread(CAP_INNER_R, False, CAP_THREAD, THREAD_PITCH / 2)).removeSplitter()


# --------------------------------------------------------------------- output


def export_3mf(doc, shape, flip, path):
    s = shape.copy()
    if flip:
        s.rotate(Vector(), Vector(1, 0, 0), 180)
    bb = s.BoundBox
    s.translate(Vector(0, 0, -bb.ZMin))
    mesh = MeshPart.meshFromShape(Shape=s, LinearDeflection=0.01, AngularDeflection=0.1,
                                  Relative=False)
    feature = doc.addObject("Mesh::Feature", "tmp_export")
    feature.Mesh = mesh
    Mesh.export([feature], path)
    doc.removeObject(feature.Name)
    return s.BoundBox


def main():
    doc = FreeCAD.newDocument("ScrewCapContainer")
    body, cap = make_body(), make_cap()
    errors = [n for n, s in (("Body", body), ("Cap", cap))
              if not s.isValid() or len(s.Solids) != 1]
    clash = body.common(cap).Volume
    if clash > 1e-3:
        errors.append(f"Body/Cap overlap {clash:.3f} mm3")

    for name, shape in (("Body", body), ("Cap", cap)):
        obj = doc.addObject("Part::Feature", name)
        obj.Shape = shape
    doc.recompute()
    doc.saveAs(os.path.join(OUT_DIR, f"{SLUG}.FCStd"))

    for name, shape, flip in (("body", body, False), ("cap", cap, True)):
        path = os.path.join(OUT_DIR, f"{SLUG}-{name}.3mf")
        bb = export_3mf(doc, shape, flip, path)
        print(f"PIECE {name} {'top down' if flip else 'upright'} "
              f"{bb.XLength:.1f} x {bb.YLength:.1f} x {bb.ZLength:.1f} mm {os.path.basename(path)}")

    print(f"INNER {2 * INNER_R:.1f} x {INNER_H:.1f}  BODY OD {2 * BODY_R:.1f}  "
          f"CAP OD {2 * CAP_OUTER_R:.1f} H {CAP_H:.1f}  CLOSED H {BODY_H + WALL:.1f}  "
          f"LEAD {LEAD:.1f} TURN TO CLOSE {(BODY_THREAD[1] - CAP_THREAD[0]) / LEAD * 360:.0f} deg")
    print("OBJECTS", len(doc.Objects), "ERRORS", errors)
    print("DONE")


main()
