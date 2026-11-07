"""Build the three-bedroom house BIM model and its deliverables.

Run with FreeCAD's own interpreter, from anywhere:

    /Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd \
        models/bim/three-bedroom-house/build_house.py < /dev/null

Writes next to this file:
    three-bedroom-house.FCStd          native BIM model
    three-bedroom-house.ifc            IFC export
    three-bedroom-house-plan.pdf       floor plan, A3 at 1:50
    three-bedroom-house-schedule.csv   room, wall and opening quantities

All lengths are millimetres. X runs east, Y runs north, Z = 0 is the finished
floor. Edit the constants below and re-run to change the design.
"""

import csv
import math
from pathlib import Path

import Arch
import Draft
import FreeCAD
import ifcopenshell
import ifcopenshell.guid
import importers.exportIFC as exportIFC
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import Part  # noqa: E402
from FreeCAD import Placement, Rotation, Vector  # noqa: E402
from matplotlib.patches import Arc, Polygon, Rectangle  # noqa: E402

HERE = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
SLUG = "three-bedroom-house"
CREATOR = "Sebastian"  # shown on the plan and stored in the FCStd and IFC metadata

# --- Design parameters ------------------------------------------------------
LENGTH = 12000  # outer east-west size
DEPTH = 8500  # outer north-south size
WALL_H = 2700  # finished floor to top of wall
EXT_T = 150  # exterior block wall
INT_T = 100  # interior block wall
SLAB_T = 150  # slab on grade
ROOF_PITCH = 22  # degrees
ROOF_T = 100  # roof build-up
EAVE = 600  # roof overhang
FRAME_W = 50  # door and window frame face width
FRAME_DEPTH = 100  # door and window frame depth
SASH_DEPTH = 40  # door leaf and window sash depth

SPINE_X = 5400  # wall between living wing and bedroom wing
HALL_S_Y = 3700  # south hall wall
HALL_N_Y = 4800  # north hall wall
BED_SPLIT_X = 8700  # wall between bedrooms 2 and 3
BATH_SPLIT_X = 7900  # wall between bathroom and bedroom 1
KITCHEN_S_Y = 5350  # notional kitchen / dining boundary (no wall)

E = EXT_T
I2 = INT_T / 2

# name: (start, end, thickness), start and end on the wall centreline
WALLS = {
    "Wall South": ((0, E / 2), (LENGTH, E / 2), EXT_T),
    "Wall North": ((0, DEPTH - E / 2), (LENGTH, DEPTH - E / 2), EXT_T),
    "Wall West": ((E / 2, E), (E / 2, DEPTH - E), EXT_T),
    "Wall East": ((LENGTH - E / 2, E), (LENGTH - E / 2, DEPTH - E), EXT_T),
    "Wall Spine South": ((SPINE_X, E), (SPINE_X, HALL_S_Y + I2), INT_T),
    "Wall Spine North": ((SPINE_X, HALL_N_Y - I2), (SPINE_X, DEPTH - E), INT_T),
    "Wall Hall South": ((SPINE_X + I2, HALL_S_Y), (LENGTH - E, HALL_S_Y), INT_T),
    "Wall Hall North": ((SPINE_X + I2, HALL_N_Y), (LENGTH - E, HALL_N_Y), INT_T),
    "Wall Bedrooms": ((BED_SPLIT_X, E), (BED_SPLIT_X, HALL_S_Y - I2), INT_T),
    "Wall Bathroom": ((BATH_SPLIT_X, HALL_N_Y + I2), (BATH_SPLIT_X, DEPTH - E), INT_T),
}

# name: (x0, y0, x1, y1, FreeCAD space type)
ROOMS = {
    "Kitchen": (E, KITCHEN_S_Y, SPINE_X - I2, DEPTH - E, "Food Preparation"),
    "Dining / Lounge": (E, E, SPINE_X - I2, KITCHEN_S_Y, "Lounge / Recreation"),
    "Hall": (SPINE_X + I2, HALL_S_Y + I2, LENGTH - E, HALL_N_Y - I2, "Corridor / Transition"),
    "Bathroom": (SPINE_X + I2, HALL_N_Y + I2, BATH_SPLIT_X - I2, DEPTH - E, "Restrooms"),
    "Bedroom 1": (BATH_SPLIT_X + I2, HALL_N_Y + I2, LENGTH - E, DEPTH - E, "Dormitory - Living Quarters"),
    "Bedroom 2": (SPINE_X + I2, E, BED_SPLIT_X - I2, HALL_S_Y - I2, "Dormitory - Living Quarters"),
    "Bedroom 3": (BED_SPLIT_X + I2, E, LENGTH - E, HALL_S_Y - I2, "Dormitory - Living Quarters"),
}

# Room names printed on the floor plan
PLAN_ROOM_NAMES = {
    "Kitchen": "Cocina",
    "Dining / Lounge": "Comedor / Sala",
    "Hall": "Pasillo",
    "Bathroom": "Baño",
    "Bedroom 1": "Dormitorio 1",
    "Bedroom 2": "Dormitorio 2",
    "Bedroom 3": "Dormitorio 3",
}

# name: (preset, host wall, centre along wall axis, width, height, sill)
WINDOWS = {
    "W01 Lounge": ("Sliding 2-pane", "Wall South", 3500, 2000, 1500, 600),
    "W02 Bedroom 2": ("Sliding 2-pane", "Wall South", 7050, 1500, 1200, 900),
    "W03 Bedroom 3": ("Sliding 2-pane", "Wall South", 10300, 1500, 1200, 900),
    "W04 Dining": ("Sliding 2-pane", "Wall West", 2800, 1500, 1200, 900),
    "W05 Kitchen": ("Sliding 2-pane", "Wall North", 2700, 1500, 1000, 1100),
    "W06 Bathroom": ("Awning", "Wall North", 6650, 600, 600, 1600),
    "W07 Bedroom 1 North": ("Sliding 2-pane", "Wall North", 9900, 1500, 1200, 900),
    "W08 Bedroom 1 East": ("Sliding 2-pane", "Wall East", 6600, 1200, 1200, 900),
    "W09 Hall": ("Fixed", "Wall East", 4250, 600, 1200, 900),
    "W10 Bedroom 3 East": ("Sliding 2-pane", "Wall East", 1900, 1200, 1200, 900),
}

# name: (host wall, centre along wall axis, width, height, hinge end, swing side)
# hinge end -1/+1 is the low/high end along the wall axis; swing side -1/+1 is
# the low/high side across it. Swing data is used for the plan symbol.
DOORS = {
    "D01 Main entry": ("Wall South", 1200, 1000, 2100, -1, 1),
    "D02 Kitchen": ("Wall West", 6100, 900, 2100, 1, 1),
    "D03 Bathroom": ("Wall Hall North", 6650, 800, 2100, -1, 1),
    "D04 Bedroom 1": ("Wall Hall North", 8500, 900, 2100, -1, 1),
    "D05 Bedroom 2": ("Wall Hall South", 6000, 900, 2100, -1, -1),
    "D06 Bedroom 3": ("Wall Hall South", 9300, 900, 2100, 1, -1),
}

MATERIALS = {
    "block": ("Plastered concrete block", (0.93, 0.91, 0.85)),
    "concrete": ("Reinforced concrete", (0.65, 0.65, 0.65)),
    "roof": ("Metal roof sheeting", (0.55, 0.22, 0.17)),
    "door": ("Timber", (0.55, 0.36, 0.20)),
    "window": ("Aluminium and glass", (0.60, 0.75, 0.85)),
}


# --- Model ------------------------------------------------------------------
def line(start, end):
    return Draft.make_line(Vector(*start, 0), Vector(*end, 0))


def is_along_x(wall_name):
    (x0, _), (x1, _), _ = WALLS[wall_name]
    return x0 != x1


def opening_placement(wall_name, centre, width, sill):
    """Lower-left corner of an opening.

    Frames extrude against the sketch normal, so the sketch plane sits half a
    frame depth ahead of the wall's centre plane to centre the frame in the wall.
    """
    (x0, y0), _, _ = WALLS[wall_name]
    if is_along_x(wall_name):
        normal = Vector(0, -1, 0)
        origin = Vector(centre - width / 2, y0, sill)
        rotation = Rotation(Vector(1, 0, 0), Vector(0, 0, 1), normal, "ZXY")
    else:
        normal = Vector(1, 0, 0)
        origin = Vector(x0, centre - width / 2, sill)
        rotation = Rotation(Vector(0, 1, 0), Vector(0, 0, 1), normal, "ZXY")
    return Placement(origin + normal * (FRAME_DEPTH / 2), rotation)


def add_opening(preset, label, wall, wall_name, centre, width, height, sill, material):
    sashes = 2 if preset.startswith("Sliding") else 1  # sliding sashes sit side by side
    obj = Arch.makeWindowPreset(
        preset,
        width=width,
        height=height,
        h1=FRAME_W,
        h2=FRAME_W,
        h3=FRAME_W,
        w1=FRAME_DEPTH,
        w2=SASH_DEPTH,
        o1=0,
        o2=(FRAME_DEPTH - sashes * SASH_DEPTH) / 2,
        placement=opening_placement(wall_name, centre, width, sill),
    )
    obj.Label = label
    obj.Hosts = [wall]
    obj.Material = material
    return obj


def build(doc):
    materials = {key: Arch.makeMaterial(name) for key, (name, _) in MATERIALS.items()}
    for key, (_, colour) in MATERIALS.items():
        materials[key].Color = colour

    walls = {}
    for name, (start, end, thickness) in WALLS.items():
        wall = Arch.makeWall(line(start, end), width=thickness, height=WALL_H, align="Center")
        wall.Label = name
        wall.Material = materials["block"]
        walls[name] = wall
    doc.recompute()

    windows = []
    for name, (preset, host, centre, width, height, sill) in WINDOWS.items():
        windows.append(
            add_opening(
                preset, name, walls[host], host, centre, width, height, sill, materials["window"]
            )
        )
    doors = []
    for name, (host, centre, width, height, _, _) in DOORS.items():
        doors.append(
            add_opening(
                "Simple door", name, walls[host], host, centre, width, height, 0, materials["door"]
            )
        )
    doc.recompute()

    slab_base = Draft.make_rectangle(LENGTH, DEPTH, Placement(Vector(0, 0, -SLAB_T), Rotation()))
    slab = Arch.makeStructure(slab_base, height=SLAB_T)
    slab.Label = "Floor slab"
    slab.IfcType = "Slab"
    slab.Material = materials["concrete"]

    roof_base = Draft.make_rectangle(LENGTH, DEPTH, Placement(Vector(0, 0, WALL_H), Rotation()))
    doc.recompute()
    roof = Arch.makeRoof(
        roof_base,
        angles=[ROOF_PITCH] * 4,
        run=[DEPTH / 2] * 4,
        idrel=[-1] * 4,
        thickness=[ROOF_T] * 4,
        overhang=[EAVE] * 4,
    )
    roof.Label = "Hip roof"
    roof.Material = materials["roof"]

    spaces = []
    volumes = doc.addObject("App::DocumentObjectGroup", "RoomVolumes")
    volumes.Label = "Room volumes"
    for name, (x0, y0, x1, y1, space_type) in ROOMS.items():
        box = doc.addObject("Part::Box", "RoomVolume")
        box.Label = f"{name} volume"
        box.Length, box.Width, box.Height = x1 - x0, y1 - y0, WALL_H
        box.Placement = Placement(Vector(x0, y0, 0), Rotation())
        volumes.addObject(box)
        space = Arch.makeSpace(box)
        space.Label = name
        space.LongName = name
        space.SpaceType = space_type
        spaces.append(space)
    doc.recompute()

    storey = Arch.makeFloor(
        [slab, *walls.values(), *windows, *doors, roof, *spaces], name="Ground floor"
    )
    building = Arch.makeBuilding([storey], name="Three Bedroom House")
    site = Arch.makeSite([building], name="Site")
    project = Arch.makeProject([site], name="Three Bedroom House")
    doc.recompute()

    return {
        "project": project,
        "walls": walls,
        "windows": windows,
        "doors": doors,
        "slab": slab,
        "roof": roof,
        "spaces": spaces,
    }


# --- Schedule ---------------------------------------------------------------
def schedule_rows(model):
    def m(value):
        return round(value / 1000, 3)

    def m2(value):
        return round(value / 1e6, 2)

    def m3(value):
        return round(value / 1e9, 3)

    rows = []
    for space in model["spaces"]:
        bbox = space.Shape.BoundBox
        rows.append(
            ("Room", space.Label, "IfcSpace", "", m(bbox.XLength), m(bbox.YLength), "",
             m2(space.Area.Value), m3(space.Shape.Volume))
        )  # fmt: skip
    for wall in model["walls"].values():
        rows.append(
            ("Wall", wall.Label, "IfcWall", "", m(wall.Width.Value), m(wall.Height.Value),
             m(wall.Length.Value), m2(wall.Length.Value * wall.Height.Value),
             m3(wall.Shape.Volume))
        )  # fmt: skip
    specs = {name: (spec[1], spec[3], spec[4]) for name, spec in WINDOWS.items()}
    specs |= {name: (spec[0], spec[2], spec[3]) for name, spec in DOORS.items()}
    for kind, ifc_type, objects in (
        ("Window", "IfcWindow", model["windows"]),
        ("Door", "IfcDoor", model["doors"]),
    ):
        for obj in objects:
            host, width, height = specs[obj.Label]
            rows.append(
                (kind, obj.Label, ifc_type, host, m(width), m(height), "",
                 m2(width * height), "")
            )  # fmt: skip
    for obj, ifc_type in ((model["slab"], "IfcSlab"), (model["roof"], "IfcRoof")):
        rows.append(
            ("Envelope", obj.Label, ifc_type, "", "", "", "", "", m3(obj.Shape.Volume))
        )  # fmt: skip
    return rows


def write_schedule(model, path):
    header = (
        "Category", "Name", "IFC type", "Host wall", "Width (m)", "Height or depth (m)",
        "Length (m)", "Area (m2)", "Volume (m3)",
    )  # fmt: skip
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(schedule_rows(model))


# --- Floor plan -------------------------------------------------------------
def wall_cut_faces(model, z=1200):
    """Fused section through the real wall solids, openings included."""
    faces = []
    for wall in model["walls"].values():
        for wire in wall.Shape.slice(Vector(0, 0, 1), z):
            faces.append(Part.Face(wire))
    return faces[0].multiFuse(faces[1:]).removeSplitter().Faces


def wire_xy(wire):
    return [(v.X, v.Y) for v in wire.OrderedVertexes]


def dimension(ax, p0, p1, offset, text=None):
    """Dimension line between two points, offset along its left-hand normal."""
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    length = math.hypot(dx, dy)
    nx, ny = -dy / length * offset, dx / length * offset
    a, b = (p0[0] + nx, p0[1] + ny), (p1[0] + nx, p1[1] + ny)
    ax.plot([a[0], b[0]], [a[1], b[1]], color="#333", lw=0.4)
    for p, q in ((p0, a), (p1, b)):
        ax.plot([p[0] + nx * 0.2, q[0] + nx * 0.1], [p[1] + ny * 0.2, q[1] + ny * 0.1],
                color="#333", lw=0.3)  # fmt: skip
        ax.plot([q[0] - 40, q[0] + 40], [q[1] - 40, q[1] + 40], color="#333", lw=0.7)
    rotation = 90 if abs(dy) > abs(dx) else 0
    side = 70 if offset > 0 else -70
    label_x = (a[0] + b[0]) / 2 + (side * -1 if rotation and offset > 0 else 0)
    label_y = (a[1] + b[1]) / 2
    if rotation:
        label_x = (a[0] + b[0]) / 2 - 70
    else:
        label_y += 70
    ax.text(label_x, label_y, text or f"{length:.0f}", ha="center", va="center",
            rotation=rotation, fontsize=6.5, color="#333")  # fmt: skip


def draw_window(ax, wall_name, centre, width):
    (x0, y0), _, thickness = WALLS[wall_name]
    half = thickness / 2
    if is_along_x(wall_name):
        box = (centre - width / 2, y0 - half, width, thickness)
        glass = [(centre - width / 2, centre + width / 2), (y0, y0)]
    else:
        box = (x0 - half, centre - width / 2, thickness, width)
        glass = [(x0, x0), (centre - width / 2, centre + width / 2)]
    ax.add_patch(Rectangle(box[:2], box[2], box[3], fc="white", ec="#222", lw=0.5))
    ax.plot(*glass, color="#2a6fa8", lw=1.1)


def draw_door(ax, wall_name, centre, width, hinge, swing):
    (x0, y0), _, thickness = WALLS[wall_name]
    half = thickness / 2 * swing
    if is_along_x(wall_name):
        hinge_point = (centre + hinge * width / 2, y0 + half)
        open_dir, closed_dir = (0, swing), (-hinge, 0)
    else:
        hinge_point = (x0 + half, centre + hinge * width / 2)
        open_dir, closed_dir = (swing, 0), (0, -hinge)
    leaf_end = (hinge_point[0] + open_dir[0] * width, hinge_point[1] + open_dir[1] * width)
    ax.plot([hinge_point[0], leaf_end[0]], [hinge_point[1], leaf_end[1]], color="#222", lw=0.8)
    angles = [math.degrees(math.atan2(d[1], d[0])) % 360 for d in (open_dir, closed_dir)]
    start = angles[0] if (angles[1] - angles[0]) % 360 == 90 else angles[1]
    ax.add_patch(
        Arc(hinge_point, 2 * width, 2 * width, theta1=start, theta2=start + 90,
            color="#222", lw=0.4)
    )  # fmt: skip


def write_plan(model, path):
    sheet_w, sheet_h, scale = 420, 297, 50  # A3 in mm, 1:50
    figure = plt.figure(figsize=(sheet_w / 25.4, sheet_h / 25.4))
    ax = figure.add_axes([0, 0, 1, 1])
    ox, oy = -3000, -3100  # model coordinates of the sheet's lower-left corner
    ax.set_xlim(ox, ox + sheet_w * scale)
    ax.set_ylim(oy, oy + sheet_h * scale)
    ax.set_aspect("equal")
    ax.axis("off")

    ax.add_patch(
        Rectangle((-EAVE, -EAVE), LENGTH + 2 * EAVE, DEPTH + 2 * EAVE, fill=False,
                  ec="#777", lw=0.5, ls=(0, (6, 4)))
    )  # fmt: skip
    ridge_y, ridge_inset = DEPTH / 2, DEPTH / 2
    ridge = [(ridge_inset, ridge_y), (LENGTH - ridge_inset, ridge_y)]
    for corner, end in (
        ((-EAVE, -EAVE), ridge[0]),
        ((-EAVE, DEPTH + EAVE), ridge[0]),
        ((LENGTH + EAVE, -EAVE), ridge[1]),
        ((LENGTH + EAVE, DEPTH + EAVE), ridge[1]),
    ):
        ax.plot([corner[0], end[0]], [corner[1], end[1]], color="#bbb", lw=0.3, ls=(0, (6, 4)))
    ax.plot(*zip(*ridge), color="#bbb", lw=0.3, ls=(0, (6, 4)))

    for face in wall_cut_faces(model):
        ax.add_patch(Polygon(wire_xy(face.OuterWire), closed=True, fc="#3a3a3a", ec="#111", lw=0.6))

    for name, (_, host, centre, width, _, _) in WINDOWS.items():
        draw_window(ax, host, centre, width)
        tag = name.split()[0]
        (x0, y0), _, _ = WALLS[host]
        if is_along_x(host):
            outside = -280 if y0 < DEPTH / 2 else 280
            ax.text(centre, y0 + outside, tag, ha="center", va="center", fontsize=6, color="#2a6fa8")
        else:
            outside = -280 if x0 < LENGTH / 2 else 280
            ax.text(x0 + outside, centre, tag, ha="center", va="center", fontsize=6,
                    color="#2a6fa8", rotation=90)  # fmt: skip
    for name, (host, centre, width, _, hinge, swing) in DOORS.items():
        draw_door(ax, host, centre, width, hinge, swing)

    for space in model["spaces"]:
        bbox = space.Shape.BoundBox
        ax.text(bbox.Center.x, bbox.Center.y + 130, PLAN_ROOM_NAMES[space.Label], ha="center", va="center",
                fontsize=9, fontweight="bold", color="#111")  # fmt: skip
        ax.text(bbox.Center.x, bbox.Center.y - 170, f"{space.Area.Value / 1e6:.1f} m²",
                ha="center", va="center", fontsize=7.5, color="#444")  # fmt: skip

    ax.plot([E, SPINE_X - I2], [KITCHEN_S_Y, KITCHEN_S_Y], color="#999", lw=0.4, ls=(0, (3, 3)))

    dimension(ax, (0, 0), (LENGTH, 0), -1400)
    dimension(ax, (0, 0), (SPINE_X, 0), -1000)
    dimension(ax, (SPINE_X, 0), (BED_SPLIT_X, 0), -1000)
    dimension(ax, (BED_SPLIT_X, 0), (LENGTH, 0), -1000)
    dimension(ax, (0, 0), (0, DEPTH), 1400)
    dimension(ax, (0, 0), (0, HALL_S_Y), 1000)
    dimension(ax, (0, HALL_S_Y), (0, HALL_N_Y), 1000)
    dimension(ax, (0, HALL_N_Y), (0, DEPTH), 1000)

    arrow_x, arrow_y = 15500, 9000
    ax.annotate("", (arrow_x, arrow_y + 900), (arrow_x, arrow_y),
                arrowprops={"arrowstyle": "-|>", "color": "#222", "lw": 1})  # fmt: skip
    ax.text(arrow_x, arrow_y + 1100, "N", ha="center", fontsize=11, fontweight="bold")

    total = sum(space.Area.Value for space in model["spaces"]) / 1e6
    block = [
        ("Three Bedroom House", 12, "bold"),
        ("Ground floor plan", 9, "normal"),
        ("Scale 1:50 on A3   Dimensions in mm", 7.5, "normal"),
        (f"Internal floor area {total:.1f} m²", 7.5, "normal"),
        (f"Gross footprint {LENGTH * DEPTH / 1e6:.1f} m²", 7.5, "normal"),
        ("Dashed outline: roof above", 7.5, "normal"),
        (f"Created by {CREATOR}", 7.5, "normal"),
    ]
    y = 6900
    for text, size, weight in block:
        ax.text(13700, y, text, fontsize=size, fontweight=weight, color="#111")
        y -= 480 if size < 12 else 620
    figure.savefig(path)
    plt.close(figure)


def write_ifc(model, path):
    """Export IFC, then repair two gaps in FreeCAD's exporter.

    It creates openings but no IfcRelFillsElement, so each door and window is
    linked to its opening here. It also writes OverallWidth and OverallHeight
    in millimetres although the file's length unit is the metre.
    """
    exportIFC.export([model["project"]], str(path))
    ifc = ifcopenshell.open(str(path))
    history = ifc.by_type("IfcOwnerHistory")[0]
    openings = {opening.Name: opening for opening in ifc.by_type("IfcOpeningElement")}
    for element in ifc.by_type("IfcWindow") + ifc.by_type("IfcDoor"):
        ifc.createIfcRelFillsElement(
            ifcopenshell.guid.new(), history, "Fills", None, openings[element.Name], element
        )
        element.OverallWidth /= 1000
        element.OverallHeight /= 1000
    ifc.write(str(path))


def main():
    doc = FreeCAD.newDocument("ThreeBedroomHouse")
    doc.CreatedBy = CREATOR
    model = build(doc)
    errors = [obj.Label for obj in doc.Objects if "Invalid" in obj.State or "Error" in obj.State]
    print("OBJECTS", len(doc.Objects), "ERRORS", errors)

    doc.saveAs(str(HERE / f"{SLUG}.FCStd"))
    write_ifc(model, HERE / f"{SLUG}.ifc")
    write_schedule(model, HERE / f"{SLUG}-schedule.csv")
    write_plan(model, HERE / f"{SLUG}-plan.pdf")
    print("DONE")
    return doc, model


main()
