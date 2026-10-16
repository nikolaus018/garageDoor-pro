"""Builds the 3D-printable case for the perfboard prototype and checks that everything fits.

    python3 prototype/case/make_case.py

Writes prototype/case/garageDoor-case.3mf with two parts, already turned for printing, and
case.png, a picture of the case with its lid lifted and the parts inside (as plain boxes):
  tray  the box: the perfboard rests on four corner seats, a rest holds up the GPS module's free
        end, USB-C notch in the left wall, a window in the right wall for the remote's wires, snap
        windows near the top edge
  lid   printed upside down: plate with a window over the SuperMini (status LED, BOOT button), a
        hole over the red LED D1, a window over J1's two screws, a skirt with snap bumps, and three
        posts that hold the perfboard down at its corners

No CAD package needed (standard library only). Every part is a union of boxes minus boxes, cut
into a grid along all the box edges; the outer faces of the filled cells become the mesh, so it is
always closed. The script fails if a mesh isn't watertight, if a part falls apart, or if the case
touches any of the parts inside (perfboard, SuperMini and GPS module in their sockets, the
antenna on top of the GPS and room for its cable, J1, Q1, R2, D1, the USB-C plug, also for a
SuperMini soldered in directly, and the remote's wires).

Coordinates in mm, as assembled: x along the perfboard's 60 mm side (column 1 on the left), y along
the 40 mm side (row A at the front), z up from the bottom of the tray. Seen from above, as in the
layout pictures: USB-C on the left, J1 on the right, row A at the front.
"""
import bisect
import math
import os
import struct
import zipfile
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "garageDoor-case.3mf")
PICTURE = os.path.join(HERE, "case.png")

# ---------------------------------------------------------------- what goes inside

PITCH = 2.54
BOARD_W, BOARD_D, BOARD_T = 60.0, 40.0, 1.6       # 40*60MM perfboard, 20 × 14 holes


def hole_x(col):          # columns 1..20, centred on the board
    return (BOARD_W - 19 * PITCH) / 2 + (col - 1) * PITCH


def hole_y(row):          # rows "A".."N", A at the front
    return (BOARD_D - 13 * PITCH) / 2 + "ABCDEFGHIJKLMN".index(row) * PITCH


FLOOR, WALL = 2.0, 2.0
UNDER = 4.5               # room under the perfboard: header tails, joints, trails, wires
ZB = FLOOR + UNDER        # bottom of the perfboard
ZT = ZB + BOARD_T         # top of the perfboard (parts side)
LID_T = 2.0
GAP = 0.2                 # clearance between parts that slide together

# Both modules plug into round machined-pin female headers (sockets) on the perfboard, on the
# plastic of their own round male pins. Measure yours: the case grows or shrinks with SOCKET_H.
SOCKET_H = 3.0            # socket body above the perfboard
PIN_H = 2.5               # plastic of the module's male pins
# perfboard top to the underside of the lid: the GPS module (1.6 mm board, ~3 mm parts) with the
# antenna on top (up to 8 mm with its tape and cable) and 1.3 mm to spare
ROOM = SOCKET_H + PIN_H + 1.6 + 3.0 + 8.0 + 1.3
ZL = ZT + ROOM            # underside of the lid = top of the tray walls

# ESP32-C3 SuperMini, 22.5 × 18 mm, in two 1×8 sockets in rows E and K, columns 2–9
SM_X0, SM_X1 = hole_x(2) - 2.4, hole_x(9) + 2.4
SM_Y = (hole_y("E") + hole_y("K")) / 2
SM_Z0 = ZT + SOCKET_H + PIN_H
USB_Z = SM_Z0 + 1.0 + 1.6 # centre of the USB-C socket on top of the 1 mm PCB
USB_Z_LOW = ZT + PIN_H + 1.0 + 1.6   # the same with the SuperMini soldered in directly

# GY-GPS6MV2: about 25.5 × 36 mm, pins on a short edge ~2.5 mm in, lying chip side up in the 1×4
# socket in I12–L12, its board toward the right edge (it reaches past it)
GPS_HDR_X = hole_x(12)
GPS_Y = (hole_y("I") + hole_y("L")) / 2
GPS_W, GPS_L, GPS_HDR_IN = 25.7, 36.5, 2.5
GPS_X0 = GPS_HDR_X - GPS_HDR_IN
GPS_X1 = GPS_X0 + GPS_L
GPS_Z0 = ZT + SOCKET_H + PIN_H
ANT = 25.0                # ceramic patch, stuck on top of the module, ceramic side up
ANT_X0 = (GPS_X0 + GPS_X1) / 2 - ANT / 2
# its cable runs to the module's socket at the far end; spare length is coiled loosely in the free
# corner beside J1 (front right), clear of the lid's corner post and the remote's wires
CABLE_RUN = (ANT_X0 + ANT + 0.2, GPS_Y - GPS_W / 2, GPS_Z0 + 4.6, 68.5, GPS_Y + GPS_W / 2 - 1.0, ZT + ROOM - 0.3)
CABLE_COIL = (hole_x(18) + 5.0, 3.5, ZT + 6.5, 68.5, 13.5, ZT + ROOM - 0.3)

PARTS = {  # envelopes the case must stay out of: (x0, y0, z0, x1, y1, z1)
    "perfboard": (0, 0, ZB, BOARD_W, BOARD_D, ZT),
    "joints underneath": (hole_x(1) - 1.3, hole_y("A") - 1.3, ZB - 3.5, hole_x(20) + 1.3, hole_y("N") + 1.3, ZB),
    "SuperMini + sockets": (SM_X0 - 0.8, SM_Y - 9.1, ZT, SM_X1 + 0.2, SM_Y + 9.1, SM_Z0 + 4.5),
    "USB-C plug": (-15, SM_Y - 6.5, USB_Z - 4, SM_X0 - 0.8, SM_Y + 6.5, USB_Z + 4),
    "USB-C plug, SuperMini soldered in": (-15, SM_Y - 6.5, USB_Z_LOW - 4, SM_X0 - 0.8, SM_Y + 6.5, USB_Z_LOW + 4),
    "GPS socket + pins": (GPS_HDR_X - 1.3, hole_y("I") - 1.3, ZT, GPS_HDR_X + 1.3, hole_y("L") + 1.3, GPS_Z0),
    "GPS module": (GPS_X0, GPS_Y - GPS_W / 2, GPS_Z0, GPS_X1, GPS_Y + GPS_W / 2, GPS_Z0 + 1.6 + 3.0),
    "antenna": (ANT_X0, GPS_Y - ANT / 2, GPS_Z0 + 4.6, ANT_X0 + ANT, GPS_Y + ANT / 2, GPS_Z0 + 4.6 + 8.0),
    "antenna cable to the module": CABLE_RUN,
    "antenna cable, spare length": CABLE_COIL,
    "J1 screw terminal": (hole_x(18) - 3.8, hole_y("B") - 2.6, ZT, hole_x(18) + 3.8, hole_y("D") + 2.6, ZT + 10.5),
    "Q1": (hole_x(12) - 2.5, hole_y("B") - 0.6, ZT, hole_x(12) + 2.5, hole_y("D") + 0.6, ZT + 9.0),
    "R2 (upright)": (hole_x(10) - 1.3, hole_y("B") - 1.3, ZT, hole_x(10) + 1.3, hole_y("C") + 1.3, ZT + 12.0),
    "D1": (hole_x(9.5) - 2.0, hole_y("A") - 2.0, ZT, hole_x(9.5) + 2.0, hole_y("A") + 2.0, ZT + 9.0),
    "remote wires": (hole_x(18) + 3.8, hole_y("B") - 1.0, ZT + 2.0, 90, hole_y("D") + 1.0, ZT + 6.0),
}

# ---------------------------------------------------------------- the case

IX0, IY0 = -0.8, -0.8                     # inside of the walls
IX1 = GPS_X1 + 2.5                        # room for a slightly longer GPS board
IY1 = GPS_Y + GPS_W / 2 + 1.3
OX0, OY0, OX1, OY1 = IX0 - WALL, IY0 - WALL, IX1 + WALL, IY1 + WALL

USB_NOTCH = (SM_Y - 7.5, SM_Y + 7.5, ZT + 1.0)    # y0, y1, bottom of the notch (open to the top)
WIRE_WIN = (hole_y("B") - 2.0, hole_y("D") + 2.0, ZT + 1.4, ZT + 7.4)   # y0, y1, z0, z1
SKIRT, SKIRT_T = 4.0, 1.2
SNAP_X = (14.0, (IX0 + IX1) / 2 + 14.0)  # snaps on the front and back walls
SNAP_W, SNAP_Z = 8.0, ZL - SKIRT + 1.0   # bump: 1 mm tall, 0.5 mm proud, from SNAP_Z up
LED_WIN = (hole_x(9.5) - 2.0, hole_y("A") - 2.0, hole_x(9.5) + 2.0, hole_y("A") + 2.0)
SM_WIN = (SM_X0 - 0.5, SM_Y - 8.5, SM_X1 + 0.5, SM_Y + 8.5)
# J1's screws sit on top of the terminal, one above each pin (B18, D18): a slot over both, so the
# remote's wires can be fastened with the lid on
J1_SCREWS = [(hole_x(18), hole_y("B")), (hole_x(18), hole_y("D"))]
J1_WIN = (hole_x(18) - 3.2, hole_y("B") - 3.0, hole_x(18) + 3.2, hole_y("D") + 3.0)
SEATS = [(0, 0), (BOARD_W, 0), (0, BOARD_D), (BOARD_W, BOARD_D)]
POSTS = [(0, 0), (BOARD_W, 0), (0, BOARD_D)]   # the fourth corner is under the GPS module
# a pillar from the floor under the GPS module's free end, past the perfboard's edge, 0.3 mm short
# of it so the module still sits fully in its socket
GPS_REST = (BOARD_W + 1.5, GPS_Y - 3.0, FLOOR, GPS_X1 - 2.5, GPS_Y + 3.0, GPS_Z0 - 0.3)


def box(x0, y0, z0, x1, y1, z1):
    return (min(x0, x1), min(y0, y1), min(z0, z1), max(x0, x1), max(y0, y1), max(z0, z1))


def tray():
    add = [box(OX0, OY0, 0, OX1, OY1, ZL)]
    sub = [box(IX0, IY0, FLOOR, IX1, IY1, ZL + 1)]
    seats = []
    for cx, cy in SEATS:
        sx, sy = (1 if cx == 0 else -1), (1 if cy == 0 else -1)
        # a 3.5 × 3 mm block under the corner, and a lip around it that keeps the board in place
        seats.append(box(cx, cy, FLOOR, cx + 3.5 * sx, cy + 3.0 * sy, ZB))
        lip_x = max(IX0, cx - 1.3) if sx > 0 else cx + GAP + 1.2
        lip_y = max(IY0, cy - 1.3) if sy > 0 else cy + GAP + 1.2
        seats.append(box(cx - GAP * sx, cy + 3.0 * sy, FLOOR, lip_x, lip_y, ZT + 1.0))
        seats.append(box(cx + 3.5 * sx, cy - GAP * sy, FLOOR, lip_x, lip_y, ZT + 1.0))
    seats.append(box(*GPS_REST))
    sub.append(box(OX0 - 1, USB_NOTCH[0], USB_NOTCH[2], IX0 + 0.5, USB_NOTCH[1], ZL + 1))
    y0, y1, z0, z1 = WIRE_WIN
    sub.append(box(IX1 - 0.5, y0, z0, OX1 + 1, y1, z1))
    for x in SNAP_X:   # through-windows the lid's bumps click into
        sub.append(box(x - SNAP_W / 2 - 0.5, OY0 - 1, SNAP_Z - 0.2, x + SNAP_W / 2 + 0.5, IY0 + 0.5, SNAP_Z + 1.2))
        sub.append(box(x - SNAP_W / 2 - 0.5, IY1 - 0.5, SNAP_Z - 0.2, x + SNAP_W / 2 + 0.5, OY1 + 1, SNAP_Z + 1.2))
    return add, sub, seats


def lid():
    add = [box(OX0, OY0, ZL, OX1, OY1, ZL + LID_T)]
    # skirt that slides into the tray, with a bump on the front and back for each snap window
    sx0, sy0, sx1, sy1 = IX0 + GAP, IY0 + GAP, IX1 - GAP, IY1 - GAP
    add.append(box(sx0, sy0, ZL - SKIRT, sx1, sy1, ZL))
    for x in SNAP_X:
        add.append(box(x - SNAP_W / 2, sy0 - 0.5, SNAP_Z, x + SNAP_W / 2, sy0, SNAP_Z + 1.0))
        add.append(box(x - SNAP_W / 2, sy1, SNAP_Z, x + SNAP_W / 2, sy1 + 0.5, SNAP_Z + 1.0))
    sub = [box(sx0 + SKIRT_T, sy0 + SKIRT_T, ZL - SKIRT - 1, sx1 - SKIRT_T, sy1 - SKIRT_T, ZL)]
    sub.append(box(sx0 - 1, USB_NOTCH[0], ZL - SKIRT - 1, sx0 + SKIRT_T + 1, USB_NOTCH[1], ZL))
    sub.append(box(*SM_WIN[:2], ZL - 1, *SM_WIN[2:], ZL + LID_T + 1))
    sub.append(box(*LED_WIN[:2], ZL - 1, *LED_WIN[2:], ZL + LID_T + 1))
    sub.append(box(*J1_WIN[:2], ZL - 1, *J1_WIN[2:], ZL + LID_T + 1))
    posts = []
    for cx, cy in POSTS:   # 3 × 2.5 mm posts down onto the perfboard's free corners
        px, py = (1 if cx == 0 else -1), (1 if cy == 0 else -1)
        x0 = max(sx0, cx + 0.5 * px) if px > 0 else min(sx1, cx + 0.5 * px)
        y0 = max(sy0, cy + 0.5 * py) if py > 0 else min(sy1, cy + 0.5 * py)
        posts.append(box(x0, y0, ZT, cx + 3.5 * px, cy + 3.0 * py, ZL + 0.01))
        posts.append(box(x0, y0, ZL - SKIRT, sx0 if px > 0 else sx1, sy0 if py > 0 else sy1, ZL))
    return add, sub, posts


# ---------------------------------------------------------------- boxes → closed mesh

class Solid:
    def __init__(self, add, sub, add_after=()):
        """Fills add, cuts sub, then fills add_after (parts that cross a cut-out)."""
        add_after = list(add_after)
        lo = [min(b[a] for b in add + add_after) for a in range(3)]
        hi = [max(b[a + 3] for b in add + add_after) for a in range(3)]
        self.c = []
        for a in range(3):
            vals = {round(min(max(v, lo[a]), hi[a]), 4) for b in add + sub + add_after for v in (b[a], b[a + 3])}
            self.c.append(sorted(vals))
        self.n = [len(c) - 1 for c in self.c]
        nx, ny, nz = self.n
        self.cells = bytearray(nx * ny * nz)
        for boxes, val in ((add, 1), (sub, 0), (add_after, 1)):
            for b in boxes:
                r = [self.span(a, b[a], b[a + 3]) for a in range(3)]
                for i in range(*r[0]):
                    for j in range(*r[1]):
                        base = (i * ny + j) * nz
                        self.cells[base + r[2][0]:base + r[2][1]] = bytes([val]) * (r[2][1] - r[2][0])

    def span(self, a, v0, v1):
        """Cell index range [i0, i1) of v0..v1, clipped to the grid."""
        c, n = self.c[a], len(self.c[a]) - 1
        i0, i1 = (bisect.bisect_left(c, round(v, 4) - 1e-6) for v in (v0, v1))
        return min(max(i0, 0), n), min(max(i1, 0), n)

    def full(self, i, j, k):
        nx, ny, nz = self.n
        return 0 <= i < nx and 0 <= j < ny and 0 <= k < nz and self.cells[(i * ny + j) * nz + k]

    def solid_cells(self):
        nx, ny, nz = self.n
        for i in range(nx):
            for j in range(ny):
                for k in range(nz):
                    if self.cells[(i * ny + j) * nz + k]:
                        yield i, j, k

    def mesh(self):
        """Outer faces of the filled cells, two triangles each, wound counter-clockwise from outside."""
        verts, index, tris = [], {}, []

        def v(i, j, k):
            key = (i, j, k)
            if key not in index:
                index[key] = len(verts)
                verts.append((self.c[0][i], self.c[1][j], self.c[2][k]))
            return index[key]

        for i, j, k in self.solid_cells():
            for (di, dj, dk), quad in (
                    ((1, 0, 0), ((1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1))),
                    ((-1, 0, 0), ((0, 0, 0), (0, 0, 1), (0, 1, 1), (0, 1, 0))),
                    ((0, 1, 0), ((0, 1, 0), (0, 1, 1), (1, 1, 1), (1, 1, 0))),
                    ((0, -1, 0), ((0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1))),
                    ((0, 0, 1), ((0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1))),
                    ((0, 0, -1), ((0, 0, 0), (0, 1, 0), (1, 1, 0), (1, 0, 0)))):
                if not self.full(i + di, j + dj, k + dk):
                    q = [v(i + a, j + b, k + c) for a, b, c in quad]
                    tris += [(q[0], q[1], q[2]), (q[0], q[2], q[3])]
        return verts, tris

    def at(self, x, y, z):
        """True if the point is inside the solid."""
        idx = [bisect.bisect_right(self.c[a], v) - 1 for a, v in enumerate((x, y, z))]
        return bool(self.full(*idx))

    def touches(self, env):
        """True if any filled cell overlaps the envelope (just touching it is fine)."""
        r = [self.span(a, max(env[a], self.c[a][0]), min(env[a + 3], self.c[a][-1])) for a in range(3)]
        for i in range(*r[0]):
            for j in range(*r[1]):
                for k in range(*r[2]):
                    if self.full(i, j, k):
                        lo = (self.c[0][i], self.c[1][j], self.c[2][k])
                        hi = (self.c[0][i + 1], self.c[1][j + 1], self.c[2][k + 1])
                        if all(lo[a] < env[a + 3] - 1e-6 and hi[a] > env[a] + 1e-6 for a in range(3)):
                            return True
        return False

    def pieces(self):
        """Number of separate lumps (face-connected)."""
        seen, count = set(), 0
        for start in self.solid_cells():
            if start in seen:
                continue
            count += 1
            stack = [start]
            seen.add(start)
            while stack:
                i, j, k = stack.pop()
                for d in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
                    nb = (i + d[0], j + d[1], k + d[2])
                    if nb not in seen and self.full(*nb):
                        seen.add(nb)
                        stack.append(nb)
        return count


def check_mesh(name, verts, tris):
    edges = {}
    for t in tris:
        for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
            edges[(a, b)] = edges.get((a, b), 0) + 1
    bad = [e for e, n in edges.items() if n != 1 or edges.get((e[1], e[0])) != 1]
    assert not bad, f"{name}: {len(bad)} edges are not shared by exactly two faces, e.g. {verts[bad[0][0]]}"
    vol = 0.0
    for a, b, c in tris:
        (x1, y1, z1), (x2, y2, z2), (x3, y3, z3) = verts[a], verts[b], verts[c]
        vol += (x1 * (y2 * z3 - y3 * z2) - x2 * (y1 * z3 - y3 * z1) + x3 * (y1 * z2 - y2 * z1)) / 6
    assert vol > 0, f"{name}: faces point inward"
    return vol


# ---------------------------------------------------------------- 3MF

def write_3mf(path, objects):
    """objects: (name, verts, tris), already placed on the print bed."""
    model = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<model unit="millimeter" xml:lang="en-US" '
             'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">',
             '<metadata name="Title">garageDoor prototype case</metadata>',
             '<metadata name="Application">prototype/case/make_case.py</metadata>',
             '<resources>']
    for oid, (name, verts, tris) in enumerate(objects, start=1):
        model.append(f'<object id="{oid}" name="{name}" type="model"><mesh><vertices>')
        model += [f'<vertex x="{x:.4f}" y="{y:.4f}" z="{z:.4f}"/>' for x, y, z in verts]
        model.append('</vertices><triangles>')
        model += [f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in tris]
        model.append('</triangles></mesh></object>')
    model.append('</resources><build>')
    model += [f'<item objectid="{oid}"/>' for oid in range(1, len(objects) + 1)]
    model.append('</build></model>')
    types = ('<?xml version="1.0" encoding="UTF-8"?>'
             '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
             '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
             '<Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>'
             '</Types>')
    rels = ('<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Target="/3D/3dmodel.model" Id="rel0" '
            'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in (("[Content_Types].xml", types), ("_rels/.rels", rels),
                           ("3D/3dmodel.model", "\n".join(model))):
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))   # same bytes on every run
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, data)


# ---------------------------------------------------------------- picture

COLOURS = {"tray": (206, 208, 214), "lid": (110, 150, 214), "perfboard": (38, 120, 72),
           "SuperMini + sockets": (34, 46, 84), "USB-C plug": (80, 80, 84), "GPS socket + pins": (20, 20, 20),
           "GPS module": (40, 90, 190), "antenna": (226, 196, 128), "J1 screw terminal": (40, 140, 64),
           "Q1": (30, 30, 30), "R2 (upright)": (226, 205, 150), "D1": (235, 60, 60),
           "remote wires": (150, 60, 175)}


def render(path, meshes, w=1000, h=760, scale=8.2):
    """Shaded, z-buffered view from the front left and above. meshes: (verts, tris, rgb)."""
    az, el = math.radians(-32), math.radians(32)
    ca, sa, ce, se = math.cos(az), math.sin(az), math.cos(el), math.sin(el)
    cx, cy, cz = (OX0 + OX1) / 2, (OY0 + OY1) / 2, 24

    def proj(p):
        x, y, z = p[0] - cx, p[1] - cy, p[2] - cz
        xr, yr = x * ca + y * sa, -x * sa + y * ca    # yr grows away from the viewer
        return w / 2 + xr * scale, h / 2 - (z * ce + yr * se) * scale, yr * ce - z * se

    light = (-0.35, -0.55, 0.76)
    depth = [1e9] * (w * h)
    img = bytearray(b"\xff" * (w * h * 3))
    for verts, tris, rgb in meshes:
        pts = [proj(v) for v in verts]
        for a, b, c in tris:
            (x1, y1, z1), (x2, y2, z2), (x3, y3, z3) = verts[a], verts[b], verts[c]
            n = ((y2 - y1) * (z3 - z1) - (z2 - z1) * (y3 - y1), (z2 - z1) * (x3 - x1) - (x2 - x1) * (z3 - z1),
                 (x2 - x1) * (y3 - y1) - (y2 - y1) * (x3 - x1))
            length = math.sqrt(sum(q * q for q in n)) or 1
            shade = 0.5 + 0.5 * max(0.0, sum(n[i] * light[i] for i in range(3)) / length)
            col = bytes(min(255, int(ch * shade)) for ch in rgb)
            (ax, ay, ad), (bx, by, bd), (qx, qy, qd) = pts[a], pts[b], pts[c]
            den = (by - qy) * (ax - qx) + (qx - bx) * (ay - qy)
            if abs(den) < 1e-9:
                continue
            for py in range(max(0, int(min(ay, by, qy))), min(h, int(max(ay, by, qy)) + 2)):
                for px in range(max(0, int(min(ax, bx, qx))), min(w, int(max(ax, bx, qx)) + 2)):
                    l1 = ((by - qy) * (px - qx) + (qx - bx) * (py - qy)) / den
                    l2 = ((qy - ay) * (px - qx) + (ax - qx) * (py - qy)) / den
                    if l1 < -1e-6 or l2 < -1e-6 or l1 + l2 > 1 + 1e-6:
                        continue
                    d, i = l1 * ad + l2 * bd + (1 - l1 - l2) * qd, py * w + px
                    if d < depth[i]:
                        depth[i] = d
                        img[3 * i:3 * i + 3] = col
    out = bytearray(img)   # dark outlines where the depth jumps
    for py in range(1, h - 1):
        for px in range(1, w - 1):
            i = py * w + px
            if any(abs(depth[i] - depth[j]) > 1.2 for j in (i + 1, i + w)):
                out[3 * i:3 * i + 3] = b"\x3a\x3d\x44"
    rows = b"".join(b"\x00" + bytes(out[y * w * 3:(y + 1) * w * 3]) for y in range(h))

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(rows, 9)) + chunk(b"IEND", b""))


def main():
    parts = {"tray": Solid(*tray()), "lid": Solid(*lid())}
    for pname, solid in parts.items():
        n = solid.pieces()
        assert n == 1, f"{pname} falls apart into {n} pieces"
        for env_name, env in PARTS.items():
            assert not solid.touches(env), f"{pname} runs into the {env_name}"
    # the perfboard rests on all four seats, the lid's posts come down onto three corners, and the
    # lips around the corners keep it from sliding
    for cx, cy in SEATS:
        x, y = cx + (1.0 if cx == 0 else -1.0), cy + (1.0 if cy == 0 else -1.0)
        assert parts["tray"].at(x, y, ZB - 0.1), f"no seat under the perfboard corner at {cx, cy}"
        x, y = cx + (-0.5 if cx == 0 else 0.5), cy + (1.0 if cy == 0 else -1.0)
        assert parts["tray"].at(x, y, ZT + 0.5), f"no lip beside the perfboard corner at {cx, cy}"
    for cx, cy in POSTS:
        x, y = cx + (1.0 if cx == 0 else -1.0), cy + (1.0 if cy == 0 else -1.0)
        assert parts["lid"].at(x, y, ZT + 0.1), f"no post above the perfboard corner at {cx, cy}"
    assert parts["tray"].at((GPS_REST[0] + GPS_REST[3]) / 2, GPS_Y, GPS_Z0 - 0.4), "no rest under the GPS"
    for x, y in J1_SCREWS:   # a screwdriver reaches each screw straight down with the lid on
        for dx, dy in ((0, 0), (-1.5, 0), (1.5, 0), (0, -1.5), (0, 1.5)):
            for z in (ZL - 0.5, ZL + 0.5, ZL + LID_T - 0.5):
                assert not parts["lid"].at(x + dx, y + dy, z), f"lid covers the J1 screw at {x:.1f}, {y:.1f}"
    for cable in ("antenna cable to the module", "antenna cable, spare length"):   # free room, not parts
        for name, env in PARTS.items():
            if "cable" not in name and name != "joints underneath":
                assert not all(PARTS[cable][a] < env[a + 3] and PARTS[cable][a + 3] > env[a] for a in range(3)), \
                    f"the {cable} space runs into the {name}"
    placed = []
    # tray as it is, moved to the origin; lid turned over (180° about x) next to it
    verts, tris = parts["tray"].mesh()
    vol = check_mesh("tray", verts, tris)
    placed.append(("tray", [(x - OX0, y - OY0, z) for x, y, z in verts], tris))
    print(f"tray: {OX1 - OX0:.1f} × {OY1 - OY0:.1f} × {ZL:.1f} mm, {vol / 1000:.1f} cm³, {len(tris)} triangles")
    verts, tris = parts["lid"].mesh()
    vol = check_mesh("lid", verts, tris)
    top, gap = ZL + LID_T, 8.0
    placed.append(("lid", [(x - OX0, (OY1 - y) + (OY1 - OY0) + gap, top - z) for x, y, z in verts], tris))
    print(f"lid:  {OX1 - OX0:.1f} × {OY1 - OY0:.1f} × {top - ZT:.1f} mm (posts included), "
          f"{vol / 1000:.1f} cm³, {len(tris)} triangles")
    print(f"closed case: {OX1 - OX0:.1f} × {OY1 - OY0:.1f} × {top:.1f} mm")
    write_3mf(OUT, placed)
    print("wrote", OUT)
    lift = 26.0
    meshes = [parts["tray"].mesh() + (COLOURS["tray"],)]
    verts, tris = parts["lid"].mesh()
    meshes.append(([(x, y, z + lift) for x, y, z in verts], tris, COLOURS["lid"]))
    for name, env in PARTS.items():
        if name in COLOURS:   # outside the case, show just a stub of the plug and the wires
            env = (max(env[0], OX0 - 14),) + env[1:3] + (min(env[3], OX1 + 10),) + env[4:]
            meshes.append(Solid([env], []).mesh() + (COLOURS[name],))
    render(PICTURE, meshes)
    print("wrote", PICTURE)


if __name__ == "__main__":
    main()
