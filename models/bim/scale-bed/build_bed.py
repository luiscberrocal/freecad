"""Build a parametric, scaled bed for 3D printing.

Run with FreeCAD's own interpreter, from anywhere:

    /Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd \
        models/bim/scale-bed/build_bed.py < /dev/null

Writes next to this file:
    scale-bed.FCStd             parametric model (spreadsheet "globals" + 3 bodies)
    scale-bed-mattress.3mf      print file for each body
    scale-bed-bed.3mf
    scale-bed-headboard.3mf

Every dimension lives in the "globals" spreadsheet. Column B holds the real-world
size, column C divides it by the scale (default 1:20) and carries the alias the
bodies use. After the build, open the FCStd and edit column B (or the scale in
B2) to change the bed: it stays parametric without this script.

Axes: X across the bed, Y along it with the head at Y = 0, Z = 0 the floor.
"""

from pathlib import Path

import FreeCAD
import Mesh
import MeshPart

HERE = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
SLUG = "scale-bed"

SCALE = 20  # 1:20

# (label, real-world value, alias, description). The alias holds the scaled size.
PARAMETERS = [
    ("Mattress length", "188 cm", "mt_length", "Head to foot"),
    ("Mattress width", "96.5 cm", "mt_width", ""),
    ("Mattress height", "15 cm", "mt_height", ""),
    ("Mattress fillet", "5 cm", "mt_fillet", "Corner radius seen from above"),
    ("Bed offset", "2 cm", "bd_offset", "Bed platform overhang past the mattress"),
    ("Bed body height", "10 cm", "bd_body_height", "Platform thickness"),
    ("Post size", "10 cm", "bd_post_size", "Square corner posts"),
    ("Post height", "25 cm", "bd_post_height", "Floor to top of platform"),
    ("Headboard height", "100 cm", "hb_height", "Floor to top of headboard"),
    ("Headboard thickness", "5 cm", "hb_thickness", ""),
]

# (label, formula on scaled aliases, alias). Shown in the sheet, not edited.
DERIVED = [
    ("Bed length", "=mt_length + 2 * bd_offset", "bd_length"),
    ("Bed width", "=mt_width + 2 * bd_offset", "bd_width"),
]

G = "<<globals>>."


def build_sheet(doc):
    sheet = doc.addObject("Spreadsheet::Sheet", "globals")
    sheet.Label = "globals"
    for col, text in zip("ABCD", ("Parameter", "Real size", "Scaled (print)", "Notes")):
        sheet.set(f"{col}1", text)
        sheet.setStyle(f"{col}1", "bold")
    sheet.set("A2", "Scale (1:n)")
    sheet.set("B2", str(SCALE))
    sheet.setAlias("B2", "scale")
    sheet.set("D2", "Change to 10 for 1:10, 25 for 1:25 ...")

    row = 4
    for label, value, alias, note in PARAMETERS:
        sheet.set(f"A{row}", label)
        sheet.set(f"B{row}", f"={value}")
        sheet.set(f"C{row}", f"=B{row} / scale")
        sheet.setAlias(f"C{row}", alias)
        sheet.set(f"D{row}", note)
        row += 1
    row += 1
    for label, formula, alias in DERIVED:
        sheet.set(f"A{row}", label)
        sheet.set(f"C{row}", formula)
        sheet.setAlias(f"C{row}", alias)
        sheet.set(f"D{row}", "Derived")
        row += 1
    sheet.setColumnWidth("A", 160)
    sheet.setColumnWidth("D", 280)
    return sheet


def add_box(body, name, length, width, height, x="0", y="0", z="0"):
    """Additive box whose size and position are expressions on the globals."""
    box = body.newObject("PartDesign::AdditiveBox", name)
    box.MapMode = "Deactivated"
    for prop, expr in (
        ("Length", length),
        ("Width", width),
        ("Height", height),
        ("Placement.Base.x", x),
        ("Placement.Base.y", y),
        ("Placement.Base.z", z),
    ):
        box.setExpression(prop, expr)
    return box


def build_mattress(doc):
    body = doc.addObject("PartDesign::Body", "Mattress")
    box = add_box(
        body,
        "MattressBlock",
        f"{G}mt_width",
        f"{G}mt_length",
        f"{G}mt_height",
        x=f"{G}bd_offset",
        y=f"{G}bd_offset",
        z=f"{G}bd_post_height",
    )
    doc.recompute()
    vertical = [
        f"Edge{i}"
        for i, e in enumerate(box.Shape.Edges, 1)
        if abs(e.Vertexes[0].Point.z - e.Vertexes[-1].Point.z) > 1e-6
    ]
    fillet = body.newObject("PartDesign::Fillet", "MattressCorners")
    fillet.Base = (box, vertical)
    fillet.setExpression("Radius", f"{G}mt_fillet")
    return body


def build_bed(doc):
    body = doc.addObject("PartDesign::Body", "Bed")
    add_box(
        body,
        "Platform",
        f"{G}bd_width",
        f"{G}bd_length",
        f"{G}bd_body_height",
        z=f"{G}bd_post_height - {G}bd_body_height",
    )
    far_x = f"{G}bd_width - {G}bd_post_size"
    far_y = f"{G}bd_length - {G}bd_post_size"
    for name, x, y in (
        ("PostHeadLeft", "0", "0"),
        ("PostHeadRight", far_x, "0"),
        ("PostFootLeft", "0", far_y),
        ("PostFootRight", far_x, far_y),
    ):
        add_box(
            body,
            name,
            f"{G}bd_post_size",
            f"{G}bd_post_size",
            f"{G}bd_post_height",
            x=x,
            y=y,
        )
    return body


def build_headboard(doc):
    body = doc.addObject("PartDesign::Body", "Headboard")
    add_box(
        body,
        "Board",
        f"{G}bd_width",
        f"{G}hb_thickness",
        f"{G}hb_height",
        y=f"-{G}hb_thickness",
    )
    return body


def export_3mf(body, path):
    mesh = MeshPart.meshFromShape(
        Shape=body.Shape, LinearDeflection=0.01, AngularDeflection=0.1, Relative=False
    )
    feature = body.Document.addObject("Mesh::Feature", "tmp_export")
    feature.Mesh = mesh
    Mesh.export([feature], str(path))
    body.Document.removeObject(feature.Name)


def main():
    doc = FreeCAD.newDocument(SLUG)
    build_sheet(doc)
    bodies = [build_mattress(doc), build_bed(doc), build_headboard(doc)]
    doc.recompute()

    errors = [o.Name for o in doc.Objects if "Invalid" in o.State or "Error" in o.State]
    print("OBJECTS", len(doc.Objects), "ERRORS", errors)
    for body in bodies:
        bb = body.Shape.BoundBox
        print(f"{body.Label}: {bb.XLength:.2f} x {bb.YLength:.2f} x {bb.ZLength:.2f} mm")

    doc.saveAs(str(HERE / f"{SLUG}.FCStd"))
    for body in bodies:
        export_3mf(body, HERE / f"{SLUG}-{body.Label.lower()}.3mf")
    print("DONE")


main()
