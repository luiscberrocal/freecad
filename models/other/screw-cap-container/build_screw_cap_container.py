"""Screw-cap container for a 50 x 40 mm cylindrical item, printed 1:1.

Run with FreeCAD's interpreter from the repo root (keep the `< /dev/null`):

    /Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd \
        models/other/screw-cap-container/build_screw_cap_container.py < /dev/null

This script is the source of truth. It overwrites screw-cap-container.FCStd, the two
.3mf files and screw-cap-container-plan.pdf next to it on every run.

Geometry (mm, Z = 0 is the bottom of the body, Z up, cap shown closed):

- Body: inside 52 x 42 (item + 2 mm wiggle room), 2 mm wall and floor.
- Thread: 4-start, right-handed, pitch 3 mm, lead 12 mm, 45 deg flanks so both
  parts print without supports. Half a turn moves the cap lead / 2 = 6 mm, which is
  the full engagement length, so the cap goes from first contact to closed in about
  half a turn.
- Cap: screws over an external thread on the body neck. Height = top + engagement +
  lead-in. Closed, the cavity is 42 mm from the floor to the underside of the cap.

The FCStd is parametric: every size comes from the `globals` spreadsheet (inputs in
PARAMETERS, formulas in DERIVED), so editing a value there and recomputing reshapes the
body, the cap and the plan views. The plan's dimension lines and the PDF are written
at build time, so rebuild with this script after changing sizes.
"""

import datetime
import os

import FreeCAD
import Draft
import Mesh
import MeshPart
import Part
import Sketcher
import TechDraw
from FreeCAD import Placement, Rotation, Vector

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
SLUG = "screw-cap-container"
TITLE = "Screw Cap Container"
AUTHOR = "Luis C. Berrocal"

# ----------------------------------------------------------------- parameters
# (alias, label, value, note). Inputs: edit these, or the sheet in the FCStd.

PARAMETERS = [
    ("item_d", "Item diameter", "50 mm", "The cylinder to store"),
    ("item_h", "Item height", "40 mm", ""),
    ("wiggle", "Wiggle room", "2 mm", "Added to inside diameter and height"),
    ("wall", "Wall thickness", "2 mm", "Body wall and floor, cap wall and top"),
    ("starts", "Thread starts", "4", "Number of parallel threads"),
    ("pitch", "Thread pitch", "3 mm", "Crest to crest along the axis"),
    ("depth", "Thread depth", "1 mm", "Radial height of a ridge"),
    ("root_w", "Ridge root width", "2.5 mm", "45 deg flanks: crest = root - 2 x depth"),
    ("rad_clr", "Radial clearance", "0.4 mm", "Crest to opposite wall"),
    ("lead_in", "Cap lead-in", "1 mm", "Plain skirt below the cap thread"),
    ("top_gap", "Neck above thread", "0.5 mm", "Plain body neck above the thread"),
    ("sink", "Ridge sink", "0.3 mm", "Ridge runs into its wall for a clean fuse"),
]

# (alias, label, formula). Formulas use the aliases above.
DERIVED = [
    ("inner_d", "Inside diameter", "=item_d + wiggle"),
    ("inner_h", "Inside height", "=item_h + wiggle"),
    ("inner_r", "Inside radius", "=inner_d / 2"),
    ("body_r", "Body radius (thread root)", "=inner_r + wall"),
    ("body_h", "Body height", "=wall + inner_h"),
    ("lead", "Thread lead", "=starts * pitch"),
    ("engage", "Engagement (half turn)", "=lead / 2"),
    ("crest_w", "Ridge crest width", "=root_w - 2 * depth"),
    ("cap_skirt_h", "Cap skirt height", "=engage + lead_in"),
    ("cap_h", "Cap height", "=cap_skirt_h + wall"),
    ("cap_inner_r", "Cap inner radius", "=body_r + depth + rad_clr"),
    ("cap_outer_r", "Cap outer radius", "=cap_inner_r + wall"),
    ("cap_z0", "Cap bottom (closed)", "=body_h - cap_skirt_h"),
    ("closed_h", "Closed height", "=body_h + wall"),
    ("bt_lo", "Body thread bottom", "=cap_z0 + lead_in / 2"),
    ("bt_hi", "Body thread top", "=body_h - top_gap"),
    ("ct_lo", "Cap thread bottom", "=cap_z0 + lead_in"),
    ("ct_hi", "Cap thread top", "=body_h"),
    ("ct_phase", "Cap thread phase", "=pitch / 2"),
    # Helices start on the grid z = phase + n * lead, a lead below the band.
    ("bt_start", "Body helix start", "=lead * (floor(bt_lo / lead) - 1)"),
    ("ct_start", "Cap helix start", "=ct_phase + lead * (floor((ct_lo - ct_phase) / lead) - 1)"),
    ("bt_len", "Body helix length", "=bt_hi - bt_lo + 2 * lead"),
    ("ct_len", "Cap helix length", "=ct_hi - ct_lo + 2 * lead"),
    ("close_deg", "Turn to close (deg)", "=(bt_hi - ct_lo) / lead * 360"),
]


# --------------------------------------------------------------- spreadsheet


def make_globals(doc):
    sheet = doc.addObject("Spreadsheet::Sheet", "globals")
    sheet.Label = "globals"
    for col, text in zip("ABCD", ("Parameter", "Value", "Alias", "Note")):
        sheet.set(f"{col}1", text)
        sheet.setStyle(f"{col}1", "bold")
    rows = [(a, label, value, note) for a, label, value, note in PARAMETERS]
    rows += [(a, label, formula, "derived") for a, label, formula in DERIVED]
    for i, (alias, label, value, note) in enumerate(rows, start=2):
        sheet.set(f"A{i}", label)
        sheet.set(f"B{i}", value)
        sheet.setAlias(f"B{i}", alias)
        sheet.set(f"C{i}", alias)
        sheet.set(f"D{i}", note)
    sheet.setColumnWidth("A", 190)
    sheet.setColumnWidth("D", 280)
    doc.recompute()
    return sheet, len(rows) + 1


def value(sheet, alias):
    v = sheet.get(alias)
    return float(getattr(v, "Value", v))


def bind(obj, prop, expr):
    obj.setExpression(prop, expr.replace("$", "globals."))


# ------------------------------------------------------------------ geometry


def cylinder(doc, name, radius, height, z="0 mm"):
    c = doc.addObject("Part::Cylinder", name)
    bind(c, "Radius", radius)
    bind(c, "Height", height)
    bind(c, ".Placement.Base.z", z)
    return c


def ridge_profile(doc, name, r_wall, outward, start):
    """Trapezoid ridge section in the XZ plane at the helix start. The 45 deg flanks
    run `sink` into the wall, so no edge lies on the wall surface (that breaks the
    fuse). Every vertex is pinned to the origin by expressions on the globals."""
    s = "+" if outward else "-"
    o = "-" if outward else "+"
    verts = [
        (f"{r_wall} {o} $sink", f"-$root_w / 2 - $sink"),
        (f"{r_wall} {s} $depth", f"-$crest_w / 2"),
        (f"{r_wall} {s} $depth", f"$crest_w / 2"),
        (f"{r_wall} {o} $sink", f"$root_w / 2 + $sink"),
    ]
    sk = doc.addObject("Sketcher::SketchObject", name)
    sk.Placement = Placement(Vector(), Rotation(Vector(1, 0, 0), 90))  # sketch Y = model Z
    bind(sk, ".Placement.Base.z", start)
    # Rough start geometry with the right winding; the constraints set the real sizes.
    r0, k = 30.0, (1 if outward else -1)
    pts = [Vector(r0 - k * 0.3, -1.6, 0), Vector(r0 + k, -0.3, 0), Vector(r0 + k, 0.3, 0),
           Vector(r0 - k * 0.3, 1.6, 0)]
    for i in range(4):
        sk.addGeometry(Part.LineSegment(pts[i], pts[(i + 1) % 4]))
    for i in range(4):
        sk.addConstraint(Sketcher.Constraint("Coincident", i, 2, (i + 1) % 4, 1))
    for i, (xe, ye) in enumerate(verts):
        for axis, expr, start_val in (("X", xe, pts[i].x), ("Y", ye, pts[i].y)):
            c = sk.addConstraint(Sketcher.Constraint(f"Distance{axis}", -1, 1, i, 1, start_val))
            sk.renameConstraint(c, f"v{i}{axis.lower()}")
            bind(sk, f".Constraints.v{i}{axis.lower()}", expr)
    return sk


def thread(doc, prefix, r_wall, outward, start, length, lo, hi):
    """`starts` helical ridges on a wall of radius r_wall, cut flat to z = lo .. hi."""
    hx = doc.addObject("Part::Helix", f"{prefix}Helix")
    bind(hx, "Pitch", "$lead")
    bind(hx, "Height", length)
    bind(hx, "Radius", r_wall)
    bind(hx, ".Placement.Base.z", start)
    profile = ridge_profile(doc, f"{prefix}RidgeProfile", r_wall, outward, start)
    sweep = doc.addObject("Part::Sweep", f"{prefix}RidgeSweep")
    sweep.Sections = [profile]
    sweep.Spine = (hx, ["Edge1"])
    sweep.Solid = True
    sweep.Frenet = True
    clip = cylinder(doc, f"{prefix}ThreadBand", f"{r_wall} + 5 mm", f"{hi} - {lo}", lo)
    if not outward:
        bore = cylinder(doc, f"{prefix}ThreadBore", f"{r_wall} - $depth - 1 mm", f"{hi} - {lo}", lo)
        band = doc.addObject("Part::Cut", f"{prefix}ThreadRing")
        band.Base, band.Tool = clip, bore
        clip = band
    ridge = doc.addObject("Part::Common", f"{prefix}Ridge")
    ridge.Base, ridge.Tool = sweep, clip
    # Fusing the swept ridges with each other fails in OCC, so the array stays a
    # compound and the wall fuses with all of it in one MultiFuse.
    ridges = Draft.make_polar_array(ridge, number=4, angle=360, center=Vector(), use_link=False)
    ridges.Label = f"{prefix}Ridges"
    ridges.Fuse = False
    bind(ridges, "NumberPolar", "$starts")
    return ridges


def make_body(doc):
    outer = cylinder(doc, "BodyOuter", "$body_r", "$body_h")
    cavity = cylinder(doc, "BodyCavity", "$inner_r", "$inner_h + 1 mm", "$wall")
    shell = doc.addObject("Part::Cut", "BodyShell")
    shell.Base, shell.Tool = outer, cavity
    ridges = thread(doc, "Body", "$body_r", True, "$bt_start", "$bt_len", "$bt_lo", "$bt_hi")
    body = doc.addObject("Part::MultiFuse", "Body")
    body.Shapes = [shell, ridges]
    body.Refine = True
    return body


def make_cap(doc):
    outer = cylinder(doc, "CapOuter", "$cap_outer_r", "$cap_h", "$cap_z0")
    recess = cylinder(doc, "CapRecess", "$cap_inner_r", "$cap_skirt_h", "$cap_z0")
    shell = doc.addObject("Part::Cut", "CapShell")
    shell.Base, shell.Tool = outer, recess
    ridges = thread(doc, "Cap", "$cap_inner_r", False, "$ct_start", "$ct_len", "$ct_lo", "$ct_hi")
    cap = doc.addObject("Part::MultiFuse", "Cap")
    cap.Shapes = [shell, ridges]
    cap.Refine = True
    return cap


# -------------------------------------------------------------------- checks


def measured_inside(body, cap):
    """Inside diameter and height read from the solids, not from the sheet."""
    radii = [f.Surface.Radius for f in body.Faces if isinstance(f.Surface, Part.Cylinder)]
    floor = min(f.CenterOfMass.z for f in body.Faces
                if isinstance(f.Surface, Part.Plane) and f.normalAt(0, 0).z > 0.99
                and f.CenterOfMass.z > 1e-6)
    ceiling = max(f.CenterOfMass.z for f in cap.Faces
                  if isinstance(f.Surface, Part.Plane) and f.normalAt(0, 0).z < -0.99)
    return 2 * min(radii), ceiling - floor


def check(sheet, body, cap):
    errors = []
    for obj in (body, cap):
        if not obj.Shape.isValid() or len(obj.Shape.Solids) != 1:
            errors.append(f"{obj.Name} is not one valid solid")
    clash = body.Shape.common(cap.Shape).Volume
    if clash > 1e-3:
        errors.append(f"Body/Cap overlap {clash:.3f} mm3")
    d, h = measured_inside(body.Shape, cap.Shape)
    for name, got, alias in (("inside diameter", d, "inner_d"), ("inside height", h, "inner_h")):
        if abs(got - value(sheet, alias)) > 1e-4:
            errors.append(f"{name} measures {got:.3f}, globals.{alias} is {value(sheet, alias):.3f}")
    return errors, d, h


# ---------------------------------------------------------------------- plan

PAGE_W, PAGE_H = 420.0, 297.0
FRAME = (20.0, 10.0, 410.0, 287.0)
TITLE_BLOCK = (230.0, 10.0, 410.0, 57.0)
TEMPLATE = "Mod/TechDraw/Templates/ISO/A3_Landscape_ISO5457_minimal.svg"
FIRST, ROW = 8.0, 7.0  # paper mm from the view to the first dimension line, and between lines


def polylines(view):
    """Visible edges in unscaled view coordinates, Y up."""
    s = view.Scale
    out = []
    for e in view.getVisibleEdges():
        if e.Length < 1e-9:
            continue
        if e.Curve.TypeId == "Part::GeomLine":
            pts = [e.Vertexes[0].Point, e.Vertexes[-1].Point]
        else:
            pts = e.discretize(Deflection=0.01 * s)
        out.append([(p.x / s, -p.y / s) for p in pts])
    return out


def bbox_2d(lines):
    xs = [x for pl in lines for x, _ in pl]
    ys = [y for pl in lines for _, y in pl]
    return min(xs), min(ys), max(xs), max(ys)


def build_plan(doc, sheet, nrows, body, cap, pdf_path):
    g = {a: value(sheet, a) for a, *_ in PARAMETERS + DERIVED}
    R = g["cap_outer_r"]

    page = doc.addObject("TechDraw::DrawPage", "Plan")
    tpl = doc.addObject("TechDraw::DrawSVGTemplate", "PlanTemplate")
    tpl.Template = FreeCAD.getResourceDir() + TEMPLATE
    page.Template = tpl

    def part_view(name, direction, xdir, scale):
        v = doc.addObject("TechDraw::DrawViewPart", name)
        page.addView(v)
        v.Source = [body, cap]
        v.Direction, v.XDirection = direction, xdir
        v.ScaleType, v.Scale, v.CoarseView = "Custom", scale, False
        v.Caption = ""
        return v

    views = {
        "front": part_view("Front", Vector(0, -1, 0), Vector(1, 0, 0), 1.0),
        "top": part_view("Top", Vector(0, 0, 1), Vector(1, 0, 0), 1.0),
        "iso": part_view("Isometric", Vector(1, -1, 1), Vector(1, 1, 0), 1.0),
    }
    sec = doc.addObject("TechDraw::DrawViewSection", "SectionAA")
    page.addView(sec)
    sec.BaseView = views["top"]
    sec.Source = [body, cap]
    sec.SectionNormal = Vector(0, -1, 0)
    sec.Direction = Vector(0, -1, 0)
    sec.XDirection = Vector(1, 0, 0)
    sec.SectionOrigin = Vector(0, 0, 0)
    sec.SectionSymbol = "A"
    sec.ScaleType, sec.Scale = "Custom", 2.0
    views["section"] = sec
    doc.recompute()

    lines = {n: polylines(v) for n, v in views.items()}
    boxes = {n: bbox_2d(pl) for n, pl in lines.items()}
    scales = {n: v.Scale for n, v in views.items()}

    # Paper position of each view's centre.
    centres = {"section": (118.0, 178.0), "front": (257.0, 150.0), "top": (257.0, 240.0),
               "iso": (360.0, 115.0)}
    origin = {}
    for n, v in views.items():
        bx0, by0, bx1, by1 = boxes[n]
        k = scales[n]
        cx, cy = centres[n]
        origin[n] = (cx - (bx0 + bx1) / 2 * k, cy - (by0 + by1) / 2 * k)
        v.X, v.Y = origin[n]

    # Model -> unscaled view coordinates, anchored on the outline: the cap's outer
    # radius is the widest point and Z = 0 the bottom (front, section), the cap
    # circle in the top view.
    def to_view(n, a, b):
        bx0, by0, _bx1, _by1 = boxes[n]
        return a + bx0 + R, b + by0 + (R if n == "top" else 0.0)

    def fmt(x, dia=False):
        return ("Ø" if dia else "") + f"{round(x, 2):g}"

    dims = [  # view, side, from, to, text; side h = below, l = left, r = right
        ("section", "h", -g["inner_r"], g["inner_r"], fmt(g["inner_d"], True)),
        ("section", "h", -g["body_r"], g["body_r"], fmt(2 * g["body_r"], True)),
        ("section", "h", -R, R, fmt(2 * R, True)),
        ("section", "l", g["wall"], g["body_h"], fmt(g["inner_h"])),
        ("section", "l", 0.0, g["body_h"], fmt(g["body_h"])),
        ("section", "l", 0.0, g["closed_h"], fmt(g["closed_h"])),
        ("section", "r", 0.0, g["wall"], fmt(g["wall"])),
        ("section", "r", g["ct_lo"], g["ct_hi"], fmt(g["engage"])),
        ("section", "r", g["cap_z0"], g["closed_h"], fmt(g["cap_h"])),
        ("front", "h", -R, R, fmt(2 * R, True)),
        ("front", "l", 0.0, g["closed_h"], fmt(g["closed_h"])),
    ]
    rows, dim_list = {}, []
    for view, side, a, b, text in dims:
        row = rows.get((view, side), 0)
        rows[(view, side)] = row + 1
        dim_list.append({"view": view, "side": side, "a": a, "b": b, "text": text, "row": row})

    # TechDraw dimensions on cosmetic points at the view's edge (text set at build time).
    for d in dim_list:
        n, v, k = d["view"], views[d["view"]], scales[d["view"]]
        bx0, by0, bx1, _ = boxes[n]
        off = (FIRST + d["row"] * ROW) / k
        if d["side"] == "h":
            (ua, _), (ub, _) = to_view(n, d["a"], 0), to_view(n, d["b"], 0)
            p1, p2, kind = Vector(ua, by0, 0), Vector(ub, by0, 0), "DistanceX"
            tx, ty = (ua + ub) / 2 * k, (by0 - off) * k
        else:
            (_, va), (_, vb) = to_view(n, 0, d["a"]), to_view(n, 0, d["b"])
            edge = bx0 if d["side"] == "l" else bx1
            p1, p2, kind = Vector(edge, va, 0), Vector(edge, vb, 0), "DistanceY"
            tx = (edge - off if d["side"] == "l" else edge + off) * k
            ty = (va + vb) / 2 * k
        dim = TechDraw.makeDistanceDim(v, kind, Vector(p1.x * k, -p1.y * k, 0),
                                       Vector(p2.x * k, -p2.y * k, 0))
        dim.Arbitrary = True
        dim.FormatSpec = d["text"]
        dim.X, dim.Y = tx, ty

    table = doc.addObject("TechDraw::DrawViewSpreadsheet", "GlobalsTable")
    page.addView(table)
    table.Source = sheet
    table.CellStart, table.CellEnd = "A1", f"C{nrows}"
    table.TextSize = 2.5
    table.X, table.Y = 357.0, 222.0

    notes = [
        f"Thread: {g['starts']:g}-start right-hand, pitch {g['pitch']:g}, lead {g['lead']:g}, "
        f"depth {g['depth']:g}, 45° flanks",
        f"Clearance {g['rad_clr']:g} radial. Closes in {g['close_deg']:.0f}° (half a turn "
        f"= {g['engage']:g} mm travel)",
        "Print: body upright, cap top on the bed, no supports",
        "All dimensions in mm",
    ]
    note = doc.addObject("TechDraw::DrawViewAnnotation", "Notes")
    page.addView(note)
    note.Text = notes
    note.TextSize = 3.0
    note.X, note.Y = 270.0, 70.0

    fields = {"title": TITLE, "drawing_number": SLUG, "creator": AUTHOR,
              "date_of_issue": datetime.date.today().isoformat(), "scale": "1:1 (section 2:1)",
              "document_type": "Plan", "sheet_number": "1/1", "language_code": "en",
              "legal_owner_1": "Print 1:1", "legal_owner_2": "Dimensions in mm"}
    texts = dict(tpl.EditableTexts)
    for key in texts:
        texts[key] = fields.get(key, "")
    tpl.EditableTexts = texts
    doc.recompute()

    # Section faces for the hatch, from a real slice of the solids at the cut plane.
    hatch = []
    for shape in (body.Shape, cap.Shape):
        for w in shape.slice(Vector(0, 1, 0), 0.0):
            pts = w.discretize(Deflection=0.005)
            hatch.append([to_view("section", p.x, p.z) for p in pts])

    render_pdf(pdf_path, views, lines, boxes, scales, origin, dim_list, to_view, hatch,
               sheet, nrows, notes, fields, g)
    return len(dim_list)


def render_pdf(path, views, lines, boxes, scales, origin, dims, to_view, hatch, sheet, nrows,
               notes, fields, g):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages

    matplotlib.rcParams["pdf.fonttype"] = 42
    matplotlib.rcParams["hatch.linewidth"] = 0.3
    inch = 25.4
    pt = 72 / inch
    fig = plt.figure(figsize=(PAGE_W / inch, PAGE_H / inch))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, PAGE_W)
    ax.set_ylim(0, PAGE_H)
    ax.set_aspect("equal")
    ax.axis("off")
    thick, thin = 0.5 * pt, 0.18 * pt

    def line(xs, ys, lw=thin, **kw):
        ax.plot(xs, ys, color="black", lw=lw, solid_capstyle="round", **kw)

    def text(x, y, s, size, **kw):
        ax.text(x, y, s, fontsize=size * pt * 1.4, **kw)

    def paper(n, u, v):
        ox, oy = origin[n]
        return ox + u * scales[n], oy + v * scales[n]

    # Frame and title block.
    fx0, fy0, fx1, fy1 = FRAME
    ax.add_patch(plt.Rectangle((fx0, fy0), fx1 - fx0, fy1 - fy0, fill=False, lw=thick))
    tx0, ty0, tx1, ty1 = TITLE_BLOCK
    ax.add_patch(plt.Rectangle((tx0, ty0), tx1 - tx0, ty1 - ty0, fill=False, lw=thick))
    rws = [ty0, ty0 + 12, ty0 + 24, ty1]
    for y in rws[1:-1]:
        line([tx0, tx1], [y, y])
    line([tx0 + 100, tx0 + 100], [ty0, ty1])
    cells = [
        (tx0, rws[2], "Title", fields["title"], 5.0),
        (tx0 + 100, rws[2], "Drawing scale", fields["scale"], 3.2),
        (tx0, rws[1], "Model", fields["legal_owner_1"], 3.5),
        (tx0 + 100, rws[1], "Dimensions", "mm", 3.0),
        (tx0, rws[0], "Drawing number", f"{fields['drawing_number']}  ·  sheet 1/1", 3.0),
        (tx0 + 100, rws[0], "Creator / date", f"{fields['creator']}  {fields['date_of_issue']}", 2.6),
    ]
    for x, y, label, val, size in cells:
        height = (ty1 - rws[2]) if y == rws[2] else 12
        text(x + 2, y + height - 2.2, label, 1.8, va="top", color="#444")
        text(x + 2, y + 2.5, val, size, va="bottom")

    # Section hatch under the edges.
    for poly in hatch:
        xy = [paper("section", u, v) for u, v in poly]
        ax.add_patch(plt.Polygon(xy, closed=True, facecolor="#e6e6e6", edgecolor="none",
                                 hatch="////", lw=0))
    for n in views:
        for pl in lines[n]:
            xy = [paper(n, u, v) for u, v in pl]
            line([p[0] for p in xy], [p[1] for p in xy], lw=thick * 0.7)
    # Axis centre lines.
    for n in ("section", "front"):
        _bx0, by0, _bx1, by1 = boxes[n]
        u, _ = to_view(n, 0.0, 0.0)
        (x, y0), (_, y1) = paper(n, u, by0 - 3), paper(n, u, by1 + 3)
        line([x, x], [y0, y1], lw=thin, dashes=(8, 2, 1, 2))
    # Cutting plane A-A on the top view (the X axis through the centre).
    bx0, by0, bx1, by1 = boxes["top"]
    _, v = to_view("top", 0.0, 0.0)
    (xa, y), (xb, _) = paper("top", bx0 - 5, v), paper("top", bx1 + 5, v)
    line([xa, xb], [y, y], lw=thin, dashes=(8, 2, 1, 2))
    for x in (xa, xb):
        line([x, x], [y, y + 0.01], lw=thick)
        ax.annotate("", (x, y + 6), (x, y), arrowprops=dict(arrowstyle="-|>", color="black", lw=thick))
        text(x, y + 7, "A", 4.0, ha="center", va="bottom", fontweight="bold")

    captions = {"section": "SECTION A-A  (2:1)", "front": "FRONT", "top": "TOP", "iso": "ISOMETRIC"}
    for n, label in captions.items():
        bx0, _by0, bx1, by1 = boxes[n]
        x, y = paper(n, (bx0 + bx1) / 2, by1)
        text(x, y + 4.5, label, 4.0, ha="center", va="center", fontweight="bold")

    arrow = dict(arrowstyle="<|-|>,head_length=0.5,head_width=0.18", color="black", lw=thin,
                 shrinkA=0, shrinkB=0)
    fs = 2.5
    for d in dims:
        n = d["view"]
        bx0, by0, bx1, _ = boxes[n]
        off = FIRST + d["row"] * ROW
        if d["side"] == "h":
            (ua, _), (ub, _) = to_view(n, d["a"], 0), to_view(n, d["b"], 0)
            (xa, y_edge), (xb, _) = paper(n, ua, by0), paper(n, ub, by0)
            y = y_edge - off
            for x in (xa, xb):
                line([x, x], [y_edge - 1.0, y - 1.5])
            ax.annotate("", (xa, y), (xb, y), arrowprops=arrow)
            text((xa + xb) / 2, y + 0.8, d["text"], fs, ha="center", va="bottom")
        else:
            (_, va), (_, vb) = to_view(n, 0, d["a"]), to_view(n, 0, d["b"])
            left = d["side"] == "l"
            (x_edge, ya), (_, yb) = paper(n, bx0 if left else bx1, va), paper(n, 0, vb)
            x = x_edge - off if left else x_edge + off
            for yy in (ya, yb):
                line([x_edge + (-1.0 if left else 1.0), x + (-1.5 if left else 1.5)], [yy, yy])
            ax.annotate("", (x, ya), (x, yb), arrowprops=arrow)
            if abs(yb - ya) < 6:  # short dimension: text beside the line
                text(x + (-1.0 if left else 1.0), (ya + yb) / 2, d["text"], fs,
                     ha="right" if left else "left", va="center")
            else:
                text(x - 0.8, (ya + yb) / 2, d["text"], fs, ha="center", va="bottom",
                     rotation=90, rotation_mode="anchor")

    # Globals table.
    x0, y_top, rh = 310.0, 278.0, 3.0
    widths = (52.0, 16.0, 26.0)
    text(x0, y_top + 1.5, "globals (spreadsheet)", 3.0, fontweight="bold", va="bottom")
    for r in range(1, nrows + 1):
        y = y_top - (r - 1) * rh
        vals = []
        for col in "ABC":
            try:
                cell = sheet.get(f"{col}{r}")
            except Exception:
                cell = ""
            if hasattr(cell, "Value"):
                cell = f"{round(cell.Value, 3):g}"
            elif isinstance(cell, float):
                cell = f"{round(cell, 3):g}"
            vals.append(str(cell))
        x = x0
        for w, val in zip(widths, vals):
            text(x + 0.8, y - rh / 2, val, 1.8, va="center",
                 fontweight="bold" if r == 1 else "normal")
            x += w
        line([x0, x0 + sum(widths)], [y - rh, y - rh], lw=thin * 0.6)
    y_end = y_top - nrows * rh
    for xx in (x0, x0 + widths[0], x0 + widths[0] + widths[1], x0 + sum(widths)):
        line([xx, xx], [y_top, y_end], lw=thin * 0.6)
    line([x0, x0 + sum(widths)], [y_top, y_top], lw=thin * 0.6)

    for i, s in enumerate(notes):
        text(215.0, 78.0 - i * 5.0, s, 2.8, va="center")

    meta = {"Title": f"{TITLE} - plan", "Creator": "build_screw_cap_container.py",
            "Producer": None, "CreationDate": None}
    with PdfPages(path, metadata=meta) as pdf:
        pdf.savefig(fig)
    plt.close(fig)


# -------------------------------------------------------------------- output


def export_3mf(doc, shape, flip, path):
    s = shape.copy()
    if flip:
        s.rotate(Vector(), Vector(1, 0, 0), 180)
    s.translate(Vector(0, 0, -s.BoundBox.ZMin))
    mesh = MeshPart.meshFromShape(Shape=s, LinearDeflection=0.01, AngularDeflection=0.1,
                                  Relative=False)
    feature = doc.addObject("Mesh::Feature", "tmp_export")
    feature.Mesh = mesh
    Mesh.export([feature], path)
    doc.removeObject(feature.Name)
    return feature, s.BoundBox


def main():
    doc = FreeCAD.newDocument("ScrewCapContainer")
    sheet, nrows = make_globals(doc)
    body, cap = make_body(doc), make_cap(doc)
    doc.recompute()
    errors = [f"{o.Label}: {o.State}" for o in doc.Objects if "Invalid" in o.State]
    if not errors:
        errors, inner_d, inner_h = check(sheet, body, cap)
        print(f"INSIDE measured diameter {inner_d:.2f} height {inner_h:.2f}")

    for o in doc.Objects:
        if o.TypeId.startswith(("Part::", "Sketcher::")):
            o.Visibility = o in (body, cap)

    for name, obj, flip in (("body", body, False), ("cap", cap, True)):
        path = os.path.join(OUT_DIR, f"{SLUG}-{name}.3mf")
        _, bb = export_3mf(doc, obj.Shape, flip, path)
        print(f"PIECE {name} {'top down' if flip else 'upright'} "
              f"{bb.XLength:.1f} x {bb.YLength:.1f} x {bb.ZLength:.1f} mm {os.path.basename(path)}")

    pdf = os.path.join(OUT_DIR, f"{SLUG}-plan.pdf")
    ndims = build_plan(doc, sheet, nrows, body, cap, pdf)
    print(f"PLAN {os.path.basename(pdf)} 1:1 (section 2:1) {ndims} dimensions mm")

    doc.saveAs(os.path.join(OUT_DIR, f"{SLUG}.FCStd"))
    g = lambda a: value(sheet, a)  # noqa: E731
    print(f"INNER {g('inner_d'):.1f} x {g('inner_h'):.1f}  BODY OD {2 * g('body_r'):.1f}  "
          f"CAP OD {2 * g('cap_outer_r'):.1f} H {g('cap_h'):.1f}  CLOSED H {g('closed_h'):.1f}  "
          f"LEAD {g('lead'):.1f} TURN TO CLOSE {g('close_deg'):.0f} deg")
    print("OBJECTS", len(doc.Objects), "ERRORS", errors)
    print("DONE")


main()
