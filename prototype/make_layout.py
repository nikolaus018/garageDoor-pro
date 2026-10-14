"""Draws prototype/layout.svg: the perfboard build, top view and (mirrored) bottom view.

Single source for the drawing; prototype/README.md refers to the same hole names.
Holes are named <row letter><column number>, e.g. B11 = row B, column 11.
"""
import os

COLS, ROWS = 20, 13
ROW_NAMES = "ABCDEFGHIJKLM"
P = 26          # px between holes
M = 46          # margin around a board view
GAP = 70        # between the two views

# ESP32-C3 SuperMini on two 1x8 female headers, USB-C toward the left board edge.
SUPERMINI_TOP = ["5", "6", "7", "8", "9", "10", "20", "21"]          # row D, columns 2..9
SUPERMINI_BOTTOM = ["5V", "G", "3V3", "4", "3", "2", "1", "0"]       # row J, columns 2..9

# Bare tinned-wire trails on the bottom (consecutive holes, all soldered together).
TRAILS = {
    "T1": (["D4", "C4", "B4"], "GPIO7 to R1"),
    "T2": (["B9", "B10", "B11"], "R1 to R2 and K1 pin 1"),
    "T3": (["C10", "C11"], "R2 to K1 pin 2 (GND)"),
    "T4": (["B14", "B15", "B16", "B17", "B18"], "K1 pin 4 to terminal 1"),
    "T5": (["J2", "K2", "L2"], "5V to GPS VCC"),
    "T6": (["J3", "K3", "L3"], "GND to GPS GND"),
    "T7": (["J5", "K5", "L5"], "GPIO4 (TX) to GPS RX"),
}
# Insulated wires on the bottom, soldered pad to pad.
WIRES = {
    "W1": ("L4", "D2", "#d6336c", "GPS TX to GPIO5 (RX)"),
    "W2": ("K3", "C11", "#1c7ed6", "GND to K1 pin 2"),
    "W3": ("C14", "D18", "#f08c00", "K1 pin 3 to terminal 2"),
}
GPS_PADS = {"L2": "VCC", "L3": "GND", "L4": "TX", "L5": "RX"}

# Which pad each component pin sits in.
PINS = {f"U1.{name}": f"D{i + 2}" for i, name in enumerate(SUPERMINI_TOP)}
PINS.update({f"U1.{name}": f"J{i + 2}" for i, name in enumerate(SUPERMINI_BOTTOM)})
PINS.update({"R1.a": "B4", "R1.b": "B9", "R2.a": "B10", "R2.b": "C10",
             "K1.1": "B11", "K1.2": "C11", "K1.3": "C14", "K1.4": "B14",
             "J1.1": "B18", "J1.2": "D18"})
PINS.update({f"GPS.{lab}": pad for pad, lab in GPS_PADS.items()})

# The intended circuit: every group must end up connected, and nothing else.
EXPECTED = [
    {"U1.7", "R1.a"},                              # GPIO7 -> R1
    {"R1.b", "R2.a", "K1.1"},                      # R1 -> PhotoMOS LED anode, 100k pull-down
    {"U1.G", "R2.b", "K1.2", "GPS.GND"},           # GND
    {"K1.4", "J1.1"},                              # switch output -> terminal
    {"K1.3", "J1.2"},
    {"U1.5V", "GPS.VCC"},
    {"U1.5", "GPS.TX"},                            # GPS TX -> GPIO5 (UART1 RX)
    {"U1.4", "GPS.RX"},                            # GPIO4 (UART1 TX) -> GPS RX
]


def verify():
    """Traces trails and wires through the pads and checks the result against EXPECTED."""
    parent = {}

    def find(a):
        parent.setdefault(a, a)
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        parent[find(a)] = find(b)

    for pads, _ in TRAILS.values():
        for a, b in zip(pads, pads[1:]):
            ca, ra = hole(a)
            cb, rb = hole(b)
            assert abs(ca - cb) + abs(ra - rb) == 1, f"trail step {a}-{b} is not between neighbouring holes"
            union(a, b)
    for a, b, _c, _w in WIRES.values():
        union(a, b)
    pads_used = {}
    for pin, pad in PINS.items():
        assert pad not in pads_used, f"{pin} and {pads_used[pad]} share pad {pad}"
        pads_used[pad] = pin
    nets = {}
    for pin, pad in PINS.items():
        nets.setdefault(find(pad), set()).add(pin)
    got = [n for n in nets.values() if len(n) > 1]
    for group in EXPECTED:
        roots = {find(PINS[p]) for p in group}
        assert len(roots) == 1, f"not connected: {sorted(group)}"
    for net in got:
        assert any(net == g for g in EXPECTED), f"unexpected connection: {sorted(net)}"
    # No dangling copper: trail ends sit on a component pad or a wire end; wire ends on a
    # component pad or a trail.
    wire_ends = {p for a, b, _c, _w in WIRES.values() for p in (a, b)}
    trail_pads = {p for pads, _ in TRAILS.values() for p in pads}
    for pads, _ in TRAILS.values():
        for p in (pads[0], pads[-1]):
            assert p in pads_used or p in wire_ends, f"trail end {p} is dangling"
    for p in wire_ends:
        assert p in pads_used or p in trail_pads, f"wire end {p} is dangling"
    print(f"layout verified: {len(EXPECTED)} nets, {len(TRAILS)} trails, {len(WIRES)} wires")


def hole(name):
    row = ROW_NAMES.index(name[0])
    col = int(name[1:])
    return col, row


def xy(name, ox, mirror):
    col, row = hole(name)
    c = (COLS + 1 - col) if mirror else col
    return ox + M + (c - 1) * P, M + row * P


def board(ox, mirror, title):
    w, h = (COLS - 1) * P + 2 * M, (ROWS - 1) * P + 2 * M
    s = [f'<rect x="{ox}" y="0" width="{w}" height="{h}" rx="10" class="pcb"/>',
         f'<text x="{ox + w / 2}" y="{h + 34}" class="title">{title}</text>']
    for c in range(1, COLS + 1):
        x, _ = xy(f"A{c}", ox, mirror)
        s.append(f'<text x="{x}" y="{M - 24}" class="lbl">{c}</text>')
    for r, rn in enumerate(ROW_NAMES):
        x0, y = xy(f"{rn}1", ox, mirror)
        side = ox + 16 if not mirror else ox + w - 16
        s.append(f'<text x="{side}" y="{y + 4}" class="lbl">{rn}</text>')
        for c in range(1, COLS + 1):
            x, y = xy(f"{rn}{c}", ox, mirror)
            s.append(f'<circle cx="{x}" cy="{y}" r="5.2" class="pad"/><circle cx="{x}" cy="{y}" r="2" class="hole"/>')
    return s


def top_view(ox):
    s = board(ox, False, "TOP (component side)")
    d2 = xy("D2", ox, False)
    j9 = xy("J9", ox, False)
    # SuperMini outline (raised on female headers), USB-C left, antenna end right.
    x0, y0 = d2[0] - 1.2 * P, d2[1] - 0.6 * P
    x1, y1 = j9[0] + 1.1 * P, j9[1] + 0.6 * P
    s.append(f'<rect x="{x0}" y="{y0}" width="{x1 - x0}" height="{y1 - y0}" rx="6" class="module"/>')
    s.append(f'<rect x="{x0 - 18}" y="{(y0 + y1) / 2 - 22}" width="34" height="44" rx="8" class="usb"/>')
    s.append(f'<text x="{x0 - 1}" y="{(y0 + y1) / 2 + 5}" class="usbt">USB-C</text>')
    s.append(f'<text x="{(x0 + x1) / 2}" y="{(y0 + y1) / 2 - 6}" class="part">ESP32-C3 SuperMini</text>')
    s.append(f'<text x="{(x0 + x1) / 2}" y="{(y0 + y1) / 2 + 14}" class="sub">on 2× female header 1×8</text>')
    s.append(f'<text x="{x1 - 22}" y="{(y0 + y1) / 2 + 42}" class="sub">antenna</text>')
    for i, lab in enumerate(SUPERMINI_TOP):
        x, y = xy(f"D{i + 2}", ox, False)
        s.append(f'<rect x="{x - 6}" y="{y - 6}" width="12" height="12" class="pin"/>'
                 f'<text x="{x}" y="{y - 12}" class="pinl">{lab}</text>')
    for i, lab in enumerate(SUPERMINI_BOTTOM):
        x, y = xy(f"J{i + 2}", ox, False)
        s.append(f'<rect x="{x - 6}" y="{y - 6}" width="12" height="12" class="pin"/>'
                 f'<text x="{x}" y="{y + 22}" class="pinl">{lab}</text>')
    # R1 330R between B4 and B9
    (ax, ay), (bx, by) = xy("B4", ox, False), xy("B9", ox, False)
    s.append(f'<line x1="{ax}" y1="{ay}" x2="{bx}" y2="{by}" class="lead"/>'
             f'<rect x="{(ax + bx) / 2 - 30}" y="{ay - 9}" width="60" height="18" rx="7" class="res"/>'
             f'<text x="{(ax + bx) / 2}" y="{ay + 4}" class="rl">R1 330Ω</text>')
    # R2 100k standing upright between B10 and C10
    (ax, ay), (bx, by) = xy("B10", ox, False), xy("C10", ox, False)
    s.append(f'<line x1="{ax}" y1="{ay}" x2="{bx}" y2="{by}" class="lead"/>'
             f'<circle cx="{ax}" cy="{ay}" r="9" class="res"/>'
             f'<text x="{ax - 14}" y="{ay - 14}" class="rl2">R2 100k (upright)</text>')
    # K1 AQY212EH: pins 1 B11, 2 C11, 3 C14, 4 B14
    (p1x, p1y), (p3x, p3y) = xy("B11", ox, False), xy("C14", ox, False)
    s.append(f'<rect x="{p1x - 8}" y="{p1y - 10}" width="{p3x - p1x + 16}" height="{p3y - p1y + 20}" rx="3" class="ic"/>'
             f'<circle cx="{p1x + 9}" cy="{p1y}" r="3.5" class="dot"/>'
             f'<text x="{(p1x + p3x) / 2}" y="{p1y - 30}" class="part">K1 AQY212EH</text>')
    for pad, n in (("B11", "1"), ("C11", "2"), ("C14", "3"), ("B14", "4")):
        x, y = xy(pad, ox, False)
        s.append(f'<rect x="{x - 5}" y="{y - 5}" width="10" height="10" class="pin"/>'
                 f'<text x="{x + (14 if n in "34" else -14)}" y="{y + 4}" class="pinl">{n}</text>')
    # J1 screw terminal: pins B18 / D18, wire entry facing the right edge
    (tx, ty), (ux, uy) = xy("B18", ox, False), xy("D18", ox, False)
    s.append(f'<rect x="{tx - 1.2 * P}" y="{ty - 0.8 * P}" width="{2.4 * P}" height="{uy - ty + 1.6 * P}" rx="4" class="term"/>'
             f'<text x="{tx}" y="{uy + 1.6 * P + 4}" class="part">J1 screw terminal</text>'
             f'<text x="{tx}" y="{ty - 0.8 * P - 8}" class="sub">remote wires in →</text>')
    for pad in ("B18", "D18"):
        x, y = xy(pad, ox, False)
        s.append(f'<circle cx="{x}" cy="{y}" r="7" class="pin"/>')
    # GPS cable soldered into L2..L5
    for pad, lab in GPS_PADS.items():
        x, y = xy(pad, ox, False)
        s.append(f'<circle cx="{x}" cy="{y}" r="7" class="gps"/><text x="{x}" y="{y + 24}" class="pinl">{lab}</text>')
    x, y = xy("M2", ox, False)
    s.append(f'<text x="{x - 8}" y="{y + 24}" class="subl">↑ GPS module cable soldered into L2–L5</text>')
    return s


def bottom_view(ox):
    s = board(ox, True, "BOTTOM (solder side) — mirrored, as you see it when soldering")
    leads = [f"D{c}" for c in range(2, 10)] + [f"J{c}" for c in range(2, 10)] + [
        "B4", "B9", "B10", "C10", "B11", "C11", "B14", "C14", "B18", "D18"] + list(GPS_PADS)
    for pad in leads:
        x, y = xy(pad, ox, True)
        s.append(f'<rect x="{x - 6}" y="{y - 6}" width="12" height="12" class="pinb"/>')
    for name, (pads, _what) in TRAILS.items():
        pts = " ".join(f"{x},{y}" for x, y in (xy(p, ox, True) for p in pads))
        s.append(f'<polyline points="{pts}" class="trail"/>')
        x, y = xy(pads[len(pads) // 2], ox, True)
        dy = -14 if pads[0][0] == pads[-1][0] else 0
        dx = 0 if dy else 16
        s.append(f'<text x="{x + dx}" y="{y + dy}" class="tl">{name}</text>')
    for name, (a, b, color, _what) in WIRES.items():
        (ax, ay), (bx, by) = xy(a, ox, True), xy(b, ox, True)
        mx, my = (ax + bx) / 2 + (by - ay) * 0.18, (ay + by) / 2 - (bx - ax) * 0.18
        s.append(f'<path d="M{ax},{ay} Q{mx},{my} {bx},{by}" stroke="{color}" class="wire"/>'
                 f'<circle cx="{ax}" cy="{ay}" r="4" fill="{color}"/><circle cx="{bx}" cy="{by}" r="4" fill="{color}"/>'
                 f'<text x="{mx}" y="{my - 6}" class="wl" fill="{color}">{name}</text>')
    return s


def legend(y):
    items = [("trail", "T = bare tinned wire laid over the pads, soldered at every pad"),
             ("wire", "W = insulated wire, soldered pad to pad"),
             ("pin", "pad with a header pin, component lead or GPS wire")]
    s = []
    for i, (cls, text) in enumerate(items):
        x = 40 + i * 470
        if cls == "trail":
            s.append(f'<line x1="{x}" y1="{y}" x2="{x + 40}" y2="{y}" class="trail"/>')
        elif cls == "wire":
            s.append(f'<line x1="{x}" y1="{y}" x2="{x + 40}" y2="{y}" stroke="#1c7ed6" class="wire"/>')
        else:
            s.append(f'<rect x="{x + 14}" y="{y - 6}" width="12" height="12" class="pin"/>')
        s.append(f'<text x="{x + 52}" y="{y + 5}" class="leg">{text}</text>')
    return s


def main():
    verify()
    w = (COLS - 1) * P + 2 * M
    h = (ROWS - 1) * P + 2 * M
    total_w, total_h = 2 * w + GAP, h + 120
    parts = top_view(0) + bottom_view(w + GAP) + legend(h + 90)
    css = """
    .pcb{fill:#1f6f43}.pad{fill:#d8b56a}.hole{fill:#123}
    .lbl{font:12px sans-serif;fill:#cfe8d8;text-anchor:middle}
    .title{font:bold 16px sans-serif;fill:#222;text-anchor:middle}
    .module{fill:#2b2b2b;fill-opacity:.82;stroke:#999;stroke-dasharray:6 4}
    .usb{fill:#bbb;stroke:#666}.usbt{font:bold 10px sans-serif;fill:#333;text-anchor:middle}
    .part{font:bold 13px sans-serif;fill:#fff;text-anchor:middle}
    .sub{font:12px sans-serif;fill:#e9ecef;text-anchor:middle}
    .subl{font:12px sans-serif;fill:#e9ecef;text-anchor:start}
    .pin{fill:#adb5bd;stroke:#222}.pinb{fill:#d8b56a;stroke:#555}
    .pinl{font:bold 11px sans-serif;fill:#fff;text-anchor:middle}
    .lead{stroke:#ced4da;stroke-width:3}
    .res{fill:#e8d5a8;stroke:#7a5c1e}.rl{font:bold 10px sans-serif;fill:#3b2a07;text-anchor:middle}
    .rl2{font:bold 11px sans-serif;fill:#fff;text-anchor:middle}
    .ic{fill:#111;stroke:#666}.dot{fill:#ddd}
    .term{fill:#2f9e44;stroke:#145;stroke-width:2}
    .gps{fill:#f59f00;stroke:#222}
    .trail{fill:none;stroke:#e9ecef;stroke-width:6;stroke-linecap:round;stroke-linejoin:round}
    .tl{font:bold 12px sans-serif;fill:#fff;text-anchor:middle}
    .wire{fill:none;stroke-width:4;stroke-linecap:round}
    .wl{font:bold 13px sans-serif;text-anchor:middle;paint-order:stroke;stroke:#1f6f43;stroke-width:3}
    .leg{font:13px sans-serif;fill:#222}
    """
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {total_w} {total_h}" '
           f'width="{total_w}" height="{total_h}"><style>{css}</style>'
           f'<rect width="100%" height="100%" fill="#fff"/>' + "".join(parts) + "</svg>")
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "layout.svg")
    open(out, "w").write(svg)
    print("wrote", out)


if __name__ == "__main__":
    main()
