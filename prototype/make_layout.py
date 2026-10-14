"""Draws the prototype build graphics and checks the layout against the circuit.

    python3 prototype/make_layout.py

Writes into prototype/img/:
  wiring.svg        what connects to what (one colour per connection)
  step1..step5.svg  the build, one step per picture: new items glow, finished items are faded
  layout.svg        everything at once, top and (mirrored) bottom view

Holes are named <row letter><column number>, e.g. B11 = row B, column 11, seen from the component
side with the USB-C on the left. Bottom views are mirrored: what you see when you turn the board.
"""
import os
import re

COLS, ROWS = 20, 13
ROW_NAMES = "ABCDEFGHIJKLM"
P = 32            # px between holes
M = 46            # margin inside the board drawing
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "img")

# One colour per connection; the same colours in every picture.
NETS = {
    "5V":   ("#e03131", "5V"),
    "GND":  ("#343a40", "GND"),
    "TXD":  ("#2f9e44", "GPS TX → GPIO5"),
    "RXD":  ("#1971c2", "GPIO4 → GPS RX"),
    "IO7":  ("#f08c00", "GPIO7 → R1"),
    "LED":  ("#e8590c", "R1 → K1 pin 1 (+ R2)"),
    "OUT1": ("#9c36b5", "K1 pin 4 → terminal 1"),
    "OUT2": ("#c2255c", "K1 pin 3 → terminal 2"),
}

SUPERMINI_TOP = ["5", "6", "7", "8", "9", "10", "20", "21"]      # row D, columns 2..9
SUPERMINI_BOTTOM = ["5V", "G", "3V3", "4", "3", "2", "1", "0"]   # row J, columns 2..9
GPS_PADS = {"L2": "VCC", "L3": "GND", "L4": "TX", "L5": "RX"}

TRAILS = {  # bare tinned wire on the bottom, soldered at every pad
    "T1": (["D4", "C4", "B4"], "IO7"),
    "T2": (["B9", "B10", "B11"], "LED"),
    "T3": (["C10", "C11"], "GND"),
    "T4": (["B14", "B15", "B16", "B17", "B18"], "OUT1"),
    "T5": (["J2", "K2", "L2"], "5V"),
    "T6": (["J3", "K3", "L3"], "GND"),
    "T7": (["J5", "K5", "L5"], "RXD"),
}
WIRES = {  # insulated wire on the bottom, pad to pad
    "W1": ("L4", "D2", "TXD"),
    "W2": ("K3", "C11", "GND"),
    "W3": ("C14", "D18", "OUT2"),
}

PINS = {f"U1.{n}": f"D{i + 2}" for i, n in enumerate(SUPERMINI_TOP)}
PINS.update({f"U1.{n}": f"J{i + 2}" for i, n in enumerate(SUPERMINI_BOTTOM)})
PINS.update({"R1.a": "B4", "R1.b": "B9", "R2.a": "B10", "R2.b": "C10",
             "K1.1": "B11", "K1.2": "C11", "K1.3": "C14", "K1.4": "B14", "J1.1": "B18", "J1.2": "D18"})
PINS.update({f"GPS.{lab}": pad for pad, lab in GPS_PADS.items()})

EXPECTED = [  # the circuit: each group connected, nothing else
    {"U1.7", "R1.a"},
    {"R1.b", "R2.a", "K1.1"},
    {"U1.G", "R2.b", "K1.2", "GPS.GND"},
    {"K1.4", "J1.1"},
    {"K1.3", "J1.2"},
    {"U1.5V", "GPS.VCC"},
    {"U1.5", "GPS.TX"},
    {"U1.4", "GPS.RX"},
]

STEPS = [  # (title, view, items new in this step, instructions)
    ("Headers", "top", ["hdrD", "hdrJ", "hdrL"], [
        "Plug both 1×8 female headers onto the SuperMini.",
        "Set it into the board: pins 5…21 in D2–D9,",
        "pins 5V…0 in J2–J9, USB-C on the left.",
        "Solder the 16 header pins from below, then",
        "pull the SuperMini off again.",
        "Solder the 1×4 male header into L2–L5.",
    ]),
    ("Parts on top", "top", ["R1", "R2", "K1", "J1"], [
        "R1 330 Ω: B4 + B9, lying flat.",
        "R2 100 kΩ: B10 + C10, standing upright.",
        "K1 AQY212EH: dot (pin 1) in B11;",
        "  its pins go to B11, C11, C14, B14.",
        "J1 screw terminal: B18 + D18,",
        "  wire openings toward the right edge.",
        "Solder from below, keep the cut-off legs.",
    ]),
    ("Trails underneath", "bottom", list(TRAILS), [
        "Turn the board over: this view is mirrored.",
        "Lay a cut-off leg flat over the pads and",
        "solder it at every pad it crosses:",
        "T1 D4–B4    T2 B9–B11    T3 C10–C11",
        "T4 B14–B18  T5 J2–L2     T6 J3–L3",
        "T7 J5–L5",
        "T5, T6, T7 run side by side: they must",
        "not touch each other.",
    ]),
    ("Wires underneath", "bottom", list(WIRES), [
        "Insulated wire, 2 mm stripped at each end,",
        "soldered onto the pads:",
        "W1  L4 → D2    GPS TX → GPIO5",
        "W2  K3 → C11   GND → K1 pin 2",
        "W3  C14 → D18  K1 pin 3 → terminal 2",
        "Then do the measurements in the README",
        "before plugging anything in.",
    ]),
    ("Plug in and connect", "top", ["module", "ext"], [
        "Plug the SuperMini back in, USB-C on the left.",
        "GPS cable onto the header, by the labels",
        "on the GPS module: VCC→L2, GND→L3,",
        "TX→L4, RX→L5.",
        "Remote button wires into J1, either way.",
        "USB-C to the car charger.",
    ]),
]


# ---------------------------------------------------------------- checks

def hole(name):
    return int(name[1:]), ROW_NAMES.index(name[0])


def verify():
    parent = {}

    def find(a):
        parent.setdefault(a, a)
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for pads, _net in TRAILS.values():
        for a, b in zip(pads, pads[1:]):
            (ca, ra), (cb, rb) = hole(a), hole(b)
            assert abs(ca - cb) + abs(ra - rb) == 1, f"trail step {a}-{b} is not between neighbours"
            parent[find(a)] = find(b)
    for a, b, _net in WIRES.values():
        parent[find(a)] = find(b)
    used = {}
    for pin, pad in PINS.items():
        assert pad not in used, f"{pin} and {used[pad]} share pad {pad}"
        used[pad] = pin
    groups = {}
    for pin, pad in PINS.items():
        groups.setdefault(find(pad), set()).add(pin)
    for g in EXPECTED:
        assert len({find(PINS[p]) for p in g}) == 1, f"not connected: {sorted(g)}"
    for g in groups.values():
        if len(g) > 1:
            assert g in EXPECTED, f"unexpected connection: {sorted(g)}"
    wire_ends = {p for a, b, _n in WIRES.values() for p in (a, b)}
    trail_pads = {p for pads, _n in TRAILS.values() for p in pads}
    for pads, _n in TRAILS.values():
        for p in (pads[0], pads[-1]):
            assert p in used or p in wire_ends, f"trail end {p} is dangling"
    for p in wire_ends:
        assert p in used or p in trail_pads, f"wire end {p} is dangling"
    # The colours must agree with the copper: one connection, one colour.
    colours = {}
    for pads, net in TRAILS.values():
        for p in pads:
            colours.setdefault(find(p), set()).add(net)
    for a, _b, net in WIRES.values():
        colours.setdefault(find(a), set()).add(net)
    for nets in colours.values():
        assert len(nets) == 1, f"one connection drawn in several colours: {nets}"
    print(f"layout verified: {len(EXPECTED)} connections, {len(TRAILS)} trails, {len(WIRES)} wires")


# ---------------------------------------------------------------- drawing helpers

CSS = """
text{font-family:-apple-system,"Segoe UI",Helvetica,Arial,sans-serif}
.pcb{fill:#1e6b45}.pad{fill:#c9a65b}.hole{fill:#0e2a1d}
.axis{font-size:13px;fill:#d3f0df;text-anchor:middle;font-weight:600}
.cap{font-size:17px;fill:#212529;font-weight:700}
.body{font-size:15px;fill:#212529}
.mono{font-family:Menlo,Consolas,monospace;font-size:14px;fill:#212529}
.h1{font-size:24px;font-weight:800;fill:#212529}
.lab{font-size:13px;font-weight:700;fill:#fff;text-anchor:middle;paint-order:stroke;stroke:#000;stroke-width:3px}
.labd{font-size:13px;font-weight:700;fill:#212529;text-anchor:middle}
.pinl{font-size:12px;font-weight:700;fill:#fff;text-anchor:middle;paint-order:stroke;stroke:#000;stroke-width:3px}
.new{filter:drop-shadow(0 0 5px #ffd43b)}
"""


def svg(w, h, body):
    # A colour given on a <text> must win over its CSS class: move it into a style attribute.
    body = re.sub(r'(<text[^>]*?) fill="([^"]+)"', r'\1 style="fill:\2"', body)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">'
            f'<style>{CSS}</style><rect width="100%" height="100%" fill="#fff"/>{body}</svg>')


def bw():
    return (COLS - 1) * P + 2 * M


def bh():
    return (ROWS - 1) * P + 2 * M


class View:
    def __init__(self, ox, oy, mirror):
        self.ox, self.oy, self.mirror = ox, oy, mirror

    def xy(self, name):
        col, row = hole(name)
        c = (COLS + 1 - col) if self.mirror else col
        return self.ox + M + (c - 1) * P, self.oy + M + row * P

    def board(self):
        s = [f'<rect x="{self.ox}" y="{self.oy}" width="{bw()}" height="{bh()}" rx="12" class="pcb"/>']
        for c in range(1, COLS + 1):
            x, _ = self.xy(f"A{c}")
            s.append(f'<text x="{x}" y="{self.oy + 22}" class="axis">{c}</text>')
        for r in ROW_NAMES:
            _, y = self.xy(f"{r}1")
            x = self.ox + 16 if not self.mirror else self.ox + bw() - 16
            s.append(f'<text x="{x}" y="{y + 5}" class="axis">{r}</text>')
            for c in range(1, COLS + 1):
                hx, hy = self.xy(f"{r}{c}")
                s.append(f'<circle cx="{hx}" cy="{hy}" r="6.5" class="pad"/>'
                         f'<circle cx="{hx}" cy="{hy}" r="2.6" class="hole"/>')
        return s


def group(items, state):
    """state: 'new' (glowing), 'done' (faded) or 'final' (normal)."""
    if state == "new":
        return ['<g class="new">'] + items + ["</g>"]
    if state == "done":
        return ['<g opacity="0.35">'] + items + ["</g>"]
    return items


# ---------------------------------------------------------------- top-view items

def top_item(v, key):
    s = []
    if key in ("hdrD", "hdrJ"):
        row = "D" if key == "hdrD" else "J"
        (x0, y), (x1, _) = v.xy(f"{row}2"), v.xy(f"{row}9")
        s.append(f'<rect x="{x0 - 15}" y="{y - 13}" width="{x1 - x0 + 30}" height="26" rx="3" fill="#212529"/>')
        labels = SUPERMINI_TOP if row == "D" else SUPERMINI_BOTTOM
        for i, lab in enumerate(labels):
            x, yy = v.xy(f"{row}{i + 2}")
            s.append(f'<rect x="{x - 4}" y="{yy - 4}" width="8" height="8" fill="#868e96"/>')
            ty = yy - 20 if row == "D" else yy + 30
            s.append(f'<text x="{x}" y="{ty}" class="lab">{lab}</text>')
    elif key == "hdrL":
        (x0, y), (x1, _) = v.xy("L2"), v.xy("L5")
        s.append(f'<rect x="{x0 - 14}" y="{y - 12}" width="{x1 - x0 + 28}" height="24" rx="2" fill="#111"/>')
        for pad, lab in GPS_PADS.items():
            x, yy = v.xy(pad)
            s.append(f'<rect x="{x - 4}" y="{yy - 4}" width="8" height="8" fill="#fcc419"/>'
                     f'<text x="{x}" y="{yy + 30}" class="lab">{lab}</text>')
    elif key == "R1":
        (ax, ay), (bx, by) = v.xy("B4"), v.xy("B9")
        s.append(f'<line x1="{ax}" y1="{ay}" x2="{bx}" y2="{by}" stroke="#adb5bd" stroke-width="4"/>'
                 f'<rect x="{(ax + bx) / 2 - 42}" y="{ay - 12}" width="84" height="24" rx="10" fill="#e9d5a1" '
                 f'stroke="#7a5c1e" stroke-width="2"/>'
                 f'<text x="{(ax + bx) / 2}" y="{ay + 5}" class="labd">R1 330Ω</text>')
    elif key == "R2":
        (ax, ay), (bx, by) = v.xy("B10"), v.xy("C10")
        s.append(f'<line x1="{ax}" y1="{ay}" x2="{bx}" y2="{by}" stroke="#adb5bd" stroke-width="4"/>'
                 f'<circle cx="{ax}" cy="{ay}" r="12" fill="#e9d5a1" stroke="#7a5c1e" stroke-width="2"/>'
                 f'<text x="{ax - 4}" y="{ay - 20}" class="lab">R2 100k ↑</text>')
    elif key == "K1":
        (p1x, p1y), (p3x, p3y) = v.xy("B11"), v.xy("C14")
        s.append(f'<rect x="{p1x - 10}" y="{p1y - 14}" width="{p3x - p1x + 20}" height="{p3y - p1y + 28}" rx="4" '
                 f'fill="#16181b" stroke="#495057"/>'
                 f'<circle cx="{p1x + 12}" cy="{p1y - 1}" r="4.5" fill="#f1f3f5"/>'
                 f'<text x="{(p1x + p3x) / 2}" y="{(p1y + p3y) / 2 + 5}" class="lab">K1</text>')
        for pad, n in (("B11", "1"), ("C11", "2"), ("C14", "3"), ("B14", "4")):
            x, y = v.xy(pad)
            dx = -18 if n in "12" else 18
            s.append(f'<rect x="{x - 5}" y="{y - 5}" width="10" height="10" fill="#adb5bd"/>'
                     f'<text x="{x + dx}" y="{y + 5}" class="lab">{n}</text>')
        s.append(f'<text x="{(p1x + p3x) / 2 + 14}" y="{p1y - 22}" class="lab">AQY212EH</text>')
    elif key == "J1":
        (tx, ty), (_ux, uy) = v.xy("B18"), v.xy("D18")
        s.append(f'<rect x="{tx - 1.25 * P}" y="{ty - 0.85 * P}" width="{2.5 * P}" height="{uy - ty + 1.7 * P}" rx="5" '
                 f'fill="#2b8a3e" stroke="#0b3d1f" stroke-width="2"/>')
        for pad, n in (("B18", "1"), ("D18", "2")):
            x, y = v.xy(pad)
            s.append(f'<circle cx="{x}" cy="{y}" r="10" fill="#ced4da" stroke="#495057" stroke-width="2"/>'
                     f'<line x1="{x - 6}" y1="{y + 6}" x2="{x + 6}" y2="{y - 6}" stroke="#495057" stroke-width="2.5"/>'
                     f'<text x="{x - 23}" y="{y + 5}" class="lab">{n}</text>')
        s.append(f'<text x="{tx}" y="{uy + 1.2 * P}" class="lab">J1 →</text>')
    elif key == "module":
        (x0, y0), (x1, y1) = v.xy("D2"), v.xy("J9")
        l, t, r, b = x0 - 1.3 * P, y0 - 0.65 * P, x1 + 1.3 * P, y1 + 0.65 * P
        s.append(f'<rect x="{l}" y="{t}" width="{r - l}" height="{b - t}" rx="6" fill="#1c2b4a" stroke="#adb5bd" stroke-width="2"/>'
                 f'<rect x="{l - 22}" y="{(t + b) / 2 - 26}" width="40" height="52" rx="9" fill="#ced4da" stroke="#495057" stroke-width="2"/>'
                 f'<text x="{l - 2}" y="{(t + b) / 2 + 5}" class="labd" font-size="11">USB-C</text>'
                 f'<text x="{(l + r) / 2}" y="{(t + b) / 2 - 4}" class="lab">ESP32-C3</text>'
                 f'<text x="{(l + r) / 2}" y="{(t + b) / 2 + 16}" class="lab">SuperMini</text>'
                 f'<rect x="{r - 30}" y="{t + 10}" width="20" height="{b - t - 20}" rx="3" fill="#495057"/>')
        for row, labels in (("D", SUPERMINI_TOP), ("J", SUPERMINI_BOTTOM)):
            for i, lab in enumerate(labels):
                x, y = v.xy(f"{row}{i + 2}")
                s.append(f'<text x="{x}" y="{y + 5}" class="pinl">{lab}</text>')
    elif key == "ext":
        # GPS cable: four wires straight down off the board edge to the module
        bottom = v.oy + bh() + 28
        for pad, lab in GPS_PADS.items():
            x, y = v.xy(pad)
            net = {"VCC": "5V", "GND": "GND", "TX": "TXD", "RX": "RXD"}[lab]
            s.append(f'<path d="M{x},{y} L{x},{bottom}" fill="none" stroke="{NETS[net][0]}" '
                     f'stroke-width="5" stroke-linecap="round"/>')
        x, _ = v.xy("L6")
        s.append(f'<text x="{x - 6}" y="{bottom + 2}" class="labd" text-anchor="start">'
                 f'↓ GPS module cable: VCC → L2, GND → L3, TX → L4, RX → L5</text>')
        for pad, net in (("B18", "OUT1"), ("D18", "OUT2")):
            x, y = v.xy(pad)
            s.append(f'<path d="M{x + 12},{y} L{x + 2.2 * P},{y}" stroke="{NETS[net][0]}" stroke-width="5" stroke-linecap="round"/>')
        x, y = v.xy("F18")
        s.append(f'<text x="{x + 0.6 * P}" y="{y + 2}" class="lab">→ remote</text>')
    return s


def top_board(v, show, new):
    s = v.board()
    for key in ["hdrD", "hdrJ", "hdrL", "R1", "R2", "K1", "J1", "module", "ext"]:
        if key in show:
            state = "new" if key in new else ("done" if new else "final")
            s += group(top_item(v, key), state)
    return s


# ---------------------------------------------------------------- bottom-view items

def bottom_board(v, show_trails, show_wires, new):
    s = v.board()
    joints = [f"D{c}" for c in range(2, 10)] + [f"J{c}" for c in range(2, 10)] + list(GPS_PADS) + \
             ["B4", "B9", "B10", "C10", "B11", "C11", "B14", "C14", "B18", "D18"]
    for pad in joints:   # solder joints of everything that sits on top
        x, y = v.xy(pad)
        s.append(f'<circle cx="{x}" cy="{y}" r="8.5" fill="#dee2e6" stroke="#868e96" stroke-width="1.5"/>')
    for name in show_trails:
        pads, net = TRAILS[name]
        col = NETS[net][0]
        pts = " ".join(f"{x},{y}" for x, y in (v.xy(p) for p in pads))
        items = [f'<polyline points="{pts}" fill="none" stroke="#fff" stroke-width="11" stroke-linecap="round" stroke-linejoin="round"/>',
                 f'<polyline points="{pts}" fill="none" stroke="{col}" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/>']
        (x0, y0), (x1, y1) = v.xy(pads[0]), v.xy(pads[-1])
        if y0 == y1:
            items.append(f'<text x="{(x0 + x1) / 2}" y="{y0 - 14}" class="lab">{name}</text>')
        else:
            items.append(f'<text x="{x0 - 20}" y="{(y0 + y1) / 2 + 5}" class="lab">{name}</text>')
        s += group(items, "new" if name in new else ("done" if new else "final"))
    for name in show_wires:
        a, b, net = WIRES[name]
        col = NETS[net][0]
        (ax, ay), (bx, by) = v.xy(a), v.xy(b)
        mx, my = (ax + bx) / 2 + (by - ay) * 0.22, (ay + by) / 2 - (bx - ax) * 0.22
        items = [f'<path d="M{ax},{ay} Q{mx},{my} {bx},{by}" fill="none" stroke="#fff" stroke-width="9" stroke-linecap="round"/>',
                 f'<path d="M{ax},{ay} Q{mx},{my} {bx},{by}" fill="none" stroke="{col}" stroke-width="5" stroke-linecap="round"/>',
                 f'<circle cx="{ax}" cy="{ay}" r="6" fill="{col}" stroke="#fff" stroke-width="2"/>',
                 f'<circle cx="{bx}" cy="{by}" r="6" fill="{col}" stroke="#fff" stroke-width="2"/>',
                 f'<text x="{(ax + bx) / 2 + (by - ay) * 0.11}" y="{(ay + by) / 2 - (bx - ax) * 0.11 + 5}" class="lab">{name}</text>']
        s += group(items, "new" if name in new else ("done" if new else "final"))
    return s


# ---------------------------------------------------------------- pictures

def legend(x, y, nets):
    s = []
    for i, key in enumerate(nets):
        col, text = NETS[key]
        yy = y + i * 25
        s.append(f'<line x1="{x}" y1="{yy}" x2="{x + 30}" y2="{yy}" stroke="{col}" stroke-width="6" stroke-linecap="round"/>'
                 f'<text x="{x + 40}" y="{yy + 5}" class="body">{text}</text>')
    return s


def step_picture(n, title, view, new, lines):
    v = View(0, 50, view == "bottom")
    if view == "top":
        show = set(new) | {"hdrD", "hdrJ", "hdrL"}
        if n >= 5:
            show |= {"R1", "R2", "K1", "J1"}
        body = top_board(v, show, set(new))
    else:
        body = bottom_board(v, list(TRAILS), list(WIRES) if n >= 4 else [], set(new))
    tx = bw() + 36
    side = "TOP side (parts)" if view == "top" else "BOTTOM side (solder) · mirrored"
    text = [f'<text x="0" y="30" class="h1">Step {n} of 5 · {title}</text>',
            f'<text x="{tx}" y="{50 + 26}" class="cap">{side}</text>']
    for i, line in enumerate(lines):
        cls = "mono" if line[:2] in ("T1", "T4", "T7", "W1", "W2", "W3") else "body"
        text.append(f'<text x="{tx}" y="{50 + 64 + i * 26}" class="{cls}" xml:space="preserve">{line}</text>')
    y = 50 + 64 + len(lines) * 26 + 16
    text.append(f'<text x="{tx}" y="{y}" class="body" fill="#868e96">glowing = do now · faded = done before</text>')
    if view == "bottom":
        nets = sorted({TRAILS[k][1] for k in new if k in TRAILS} | {WIRES[k][2] for k in new if k in WIRES},
                      key=list(NETS).index)
        text += legend(tx, y + 40, nets)
    return svg(bw() + 480, bh() + 110, "".join(text + body))


def overview():
    top, bottom = View(0, 50, False), View(bw() + 60, 50, True)
    body = top_board(top, {"hdrD", "hdrJ", "hdrL", "R1", "R2", "K1", "J1"}, set())
    body += bottom_board(bottom, list(TRAILS), list(WIRES), set())
    body += [f'<text x="{bw() / 2}" y="34" class="cap" text-anchor="middle">TOP (parts)</text>',
             f'<text x="{bw() + 60 + bw() / 2}" y="34" class="cap" text-anchor="middle">BOTTOM (solder side, mirrored)</text>']
    body += legend(30, bh() + 96, list(NETS)[:4]) + legend(420, bh() + 96, list(NETS)[4:])
    return svg(2 * bw() + 60, bh() + 200, "".join(body))


def wiring():
    W, H = 1180, 640
    s = ['<text x="30" y="40" class="h1">What connects to what</text>']

    def box(x, y, w, h, title, sub, fill):
        return [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{fill}" stroke="#343a40" stroke-width="2"/>',
                f'<text x="{x + w / 2}" y="{y + 30}" class="cap" text-anchor="middle" fill="#fff">{title}</text>',
                f'<text x="{x + w / 2}" y="{y + 52}" class="body" text-anchor="middle" fill="#dee2e6">{sub}</text>']

    def pin(x, y, label, inside):
        """Pin on a box edge; the label goes inside the box ('left' = box is left of the pin)."""
        tx, anchor = (x - 14, "end") if inside == "left" else (x + 14, "start")
        return [f'<circle cx="{x}" cy="{y}" r="6" fill="#fff" stroke="#343a40" stroke-width="2"/>',
                f'<text x="{tx}" y="{y + 5}" class="body" text-anchor="{anchor}" fill="#fff">{label}</text>']

    def wire(points, net, label=None, lx=0, ly=0):
        col = NETS[net][0]
        d = "M" + " L".join(f"{x},{y}" for x, y in points)
        out = [f'<path d="{d}" fill="none" stroke="{col}" stroke-width="5" stroke-linejoin="round" stroke-linecap="round"/>']
        if label:
            out.append(f'<text x="{lx}" y="{ly}" class="body" font-weight="700" fill="{col}">{label}</text>')
        return out

    s += box(40, 80, 300, 480, "ESP32-C3 SuperMini", "USB-C ← car charger", "#1c2b4a")
    s += box(780, 80, 250, 210, "GPS module", "e.g. Beitian BE-220", "#5f3dc4")
    s += box(660, 370, 220, 190, "K1 AQY212EH", "PhotoMOS relay", "#212529")
    s += box(980, 390, 170, 150, "Spare remote", "button contacts", "#495057")
    esp = {"5V": 160, "GND": 220, "GPIO5": 280, "GPIO4": 340, "GPIO7": 440}
    for lab, y in esp.items():
        s += pin(340, y, lab, "left")
    s.append('<text x="60" y="520" class="body" fill="#dee2e6">LED = GPIO8 · BOOT/SETUP = GPIO9</text>')
    gps = {"VCC": 160, "GND": 200, "TX": 240, "RX": 270}
    for lab, y in gps.items():
        s += pin(780, y, lab, "right")
    for lab, (x, y, inside) in {"1 (+)": (660, 420, "right"), "2 (−)": (660, 510, "right"),
                                "4": (880, 420, "left"), "3": (880, 510, "left")}.items():
        s += pin(x, y, lab, inside)
    s += wire([(346, 160), (774, 160)], "5V", "5V", 380, 152)
    s += wire([(346, 220), (720, 220), (720, 200), (774, 200)], "GND", "GND", 380, 212)
    s += wire([(346, 280), (740, 280), (740, 240), (774, 240)], "TXD", "GPS TX → GPIO5", 380, 272)
    s += wire([(346, 340), (755, 340), (755, 270), (774, 270)], "RXD", "GPIO4 → GPS RX", 380, 332)
    s += wire([(346, 440), (440, 440)], "IO7")
    s.append('<rect x="440" y="428" width="84" height="24" rx="10" fill="#e9d5a1" stroke="#7a5c1e" stroke-width="2"/>'
             '<text x="482" y="445" class="labd">R1 330Ω</text>')
    s += wire([(524, 440), (600, 440), (600, 420), (654, 420)], "LED")
    s += wire([(600, 440), (600, 462)], "LED")
    s.append('<rect x="588" y="462" width="24" height="54" rx="10" fill="#e9d5a1" stroke="#7a5c1e" stroke-width="2"/>'
             '<text x="622" y="485" class="labd" text-anchor="start" font-size="12">R2</text>'
             '<text x="622" y="500" class="labd" text-anchor="start" font-size="12">100k</text>')
    s += wire([(600, 516), (600, 580), (636, 580), (636, 510), (654, 510)], "GND")
    s += wire([(600, 580), (370, 580), (370, 220)], "GND")
    s += wire([(886, 420), (974, 420)], "OUT1", "J1", 920, 408)
    s += wire([(886, 510), (974, 510)], "OUT2")
    for (x, y, net) in ((600, 440, "LED"), (600, 580, "GND"), (370, 220, "GND")):   # junctions
        s.append(f'<circle cx="{x}" cy="{y}" r="7" fill="{NETS[net][0]}"/>')
    s.append('<text x="1065" y="470" class="body" text-anchor="middle" fill="#fff">either way round</text>')
    s.append(f'<text x="40" y="{H - 24}" class="body">Same colours as on the board pictures. '
             'K1 closes like a pressed button and stays open without power.</text>')
    return svg(W, H, "".join(s))


def main():
    verify()
    os.makedirs(OUT, exist_ok=True)
    files = {"wiring.svg": wiring(), "layout.svg": overview()}
    for i, (title, view, new, lines) in enumerate(STEPS, start=1):
        files[f"step{i}.svg"] = step_picture(i, title, view, new, lines)
    for name, content in files.items():
        with open(os.path.join(OUT, name), "w") as f:
            f.write(content)
    print("wrote", ", ".join(sorted(files)), "to", OUT)


if __name__ == "__main__":
    main()
