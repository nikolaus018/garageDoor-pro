"""Draws the prototype build graphics and checks the layout against the circuit.

    python3 prototype/make_layout.py

Writes into prototype/img/:
  wiring.svg        what connects to what (one colour per connection)
  step1..step5.svg  the build, one step per picture: new items glow, finished items are faded
  layout.svg        everything at once, top and (mirrored) bottom view

The board is a 4 × 6 cm double-sided perfboard with 20 × 14 holes, column numbers 1–20 and row
letters A–N printed on one side. Parts go on the printed side, and the holes carry the printed
names: e.g. B11 = row B, column 11. Seen from that side with 1 on the left and A at the bottom, the
SuperMini sits chip side up with USB-C on the left. Bottom views are mirrored: what you see when
you turn the board over like a page.
"""
import os
import re

COLS, ROWS = 20, 14
ROW_NAMES = "ABCDEFGHIJKLMN"   # printed along the left edge, A at the bottom
P = 32            # px between holes
M = 58            # margin inside the board drawing (printed labels)
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "img")

# One colour per connection; the same colours in every picture.
NETS = {
    "3V3":  ("#e03131", "3V3 → GPS VCC"),
    "GND":  ("#343a40", "GND"),
    "TXD":  ("#2f9e44", "GPS TX → GPIO5"),
    "RXD":  ("#1971c2", "GPIO4 → GPS RX"),
    "IO7":  ("#f08c00", "GPIO7 → R1 and R3"),
    "BASE": ("#e8590c", "R1 → Q1 base (+ R2)"),
    "IND":  ("#0c8599", "R3 → red LED D1"),
    "OUT1": ("#9c36b5", "Q1 collector → terminal screw 1 (+)"),
}

# Seen from the printed side, A at the bottom, with the SuperMini's chip and buttons facing up and
# USB-C on the left: its 5V…0 row is the upper one.
TOP_ROW, BOTTOM_ROW = "K", "E"
SUPERMINI_TOP = ["5V", "G", "3V3", "4", "3", "2", "1", "0"]      # row K, columns 2..9
SUPERMINI_BOTTOM = ["5", "6", "7", "8", "9", "10", "20", "21"]   # row E, columns 2..9
# GPS VCC sits above 3V3 (K4) so a straight trail reaches it; most of these modules are 3.3 V only.
GPS_PADS = {"M2": "TX", "M3": "GND", "M4": "VCC", "M5": "RX"}
R1 = ("C4", "C9")                                     # lying flat
R2 = ("C10", "B10")                                   # standing upright, body on C10
R3 = ("A4", "A8")                                     # lying flat, along the bottom edge
D1 = {"+": "A9", "−": "A10"}                          # 3 mm red LED: long leg (+) in A9
Q1 = {"E": "B12", "B": "C12", "C": "D12"}             # NPN transistor, TO-92, legs in one column
J1 = {"1": "D18", "2": "B18"}

TRAILS = {  # bare tinned wire on the bottom, soldered at every pad
    "T1": (["E4", "D4", "C4", "B4", "A4"], "IO7"),
    "T2": (["C9", "C10", "C11", "C12"], "BASE"),
    # GND along row B: R2, W2, the emitter and screw 2.
    "T3": (["B10", "B11", "B12", "B13", "B14", "B15", "B16", "B17", "B18"], "GND"),
    "T4": (["D12", "D13", "D14", "D15", "D16", "D17", "D18"], "OUT1"),
    "T5": (["K4", "L4", "M4"], "3V3"),
    "T6": (["K3", "L3", "M3"], "GND"),
    "T7": (["K5", "L5", "M5"], "RXD"),
    "T8": (["A8", "A9"], "IND"),
    "T9": (["A10", "B10"], "GND"),
}
WIRES = {  # insulated wire on the bottom, pad to pad
    "W1": ("M2", "E2", "TXD"),
    "W2": ("L3", "B11", "GND"),
}
# Where a trail's name goes when the default spot is taken: (pad, dx, dy) from that pad's centre.
TRAIL_LABELS = {"T1": ("B4", -26, 5), "T2": ("C10", 0, -14), "T3": ("B15", 0, 26), "T4": ("D15", 0, -14),
                "T8": ("A8", 0, 30), "T9": ("A10", 30, 5)}

PINS = {f"U1.{n}": f"{TOP_ROW}{i + 2}" for i, n in enumerate(SUPERMINI_TOP)}
PINS.update({f"U1.{n}": f"{BOTTOM_ROW}{i + 2}" for i, n in enumerate(SUPERMINI_BOTTOM)})
PINS.update({"R1.a": R1[0], "R1.b": R1[1], "R2.a": R2[0], "R2.b": R2[1], "R3.a": R3[0], "R3.b": R3[1]})
PINS.update({f"D1.{n}": pad for n, pad in D1.items()})
PINS.update({f"Q1.{n}": pad for n, pad in Q1.items()})
PINS.update({f"J1.{n}": pad for n, pad in J1.items()})
PINS.update({f"GPS.{lab}": pad for pad, lab in GPS_PADS.items()})

EXPECTED = [  # the circuit: each group connected, nothing else
    {"U1.7", "R1.a", "R3.a"},
    {"R1.b", "R2.a", "Q1.B"},
    {"R3.b", "D1.+"},
    {"U1.G", "R2.b", "Q1.E", "J1.2", "GPS.GND", "D1.−"},
    {"Q1.C", "J1.1"},
    {"U1.3V3", "GPS.VCC"},
    {"U1.5", "GPS.TX"},
    {"U1.4", "GPS.RX"},
]

STEPS = [  # (title, view, items new in this step, instructions)
    ("Headers", "top", ["hdrTop", "hdrBot", "hdrG"], [
        "Printed side up, 1 on the left: A must be at",
        "the bottom (if it's at the top, stop: README).",
        "Plug both 1×8 female headers onto the SuperMini",
        "and set it in chip side up, USB-C to the left:",
        "pins 5V…0 in K2–K9, pins 5…21 in E2–E9.",
        "Solder the 16 header pins from below, then",
        "pull the SuperMini off again.",
        "Solder the 1×4 male header into M2–M5.",
    ]),
    ("Parts on top", "top", ["R1", "R2", "R3", "D1", "Q1", "J1"], [
        "R1 330 Ω: C4 + C9, lying flat.",
        "R2 100 kΩ: C10 + B10, standing upright,",
        "  body on C10.",
        "R3 1 kΩ: A4 + A8, lying flat.",
        "D1 red LED 3 mm: long leg (+) in A9,",
        "  short leg / flat side (−) in A10.",
        "Q1 NPN transistor: E in B12, B in C12,",
        "  C in D12 (which way the flat side faces:",
        "  README, step 3).",
        "J1 screw terminal: D18 + B18,",
        "  wire openings toward the right edge.",
        "Solder from below, keep the cut-off legs.",
    ]),
    ("Trails underneath", "bottom", list(TRAILS), [
        "Turn the board over like a page. This side has",
        "no print: find your way by the solder joints.",
        "USB-C end now on the right, J1 on the left.",
        "Lay a cut-off leg flat over the pads and",
        "solder it at every pad it crosses:",
        "T1  pin 7 → R1 → R3 (4 pads down)",
        "T2  R1 → R2 → Q1 base",
        "T3  R2 → Q1 emitter → J1 screw 2 (GND)",
        "T4  Q1 collector → J1 screw 1",
        "T5  3V3 → GPS VCC",
        "T6  G → GPS GND",
        "T7  pin 4 → GPS RX",
        "T8  R3 → D1 + (bridge)",
        "T9  D1 − → R2 (bridge)",
        "T2 / T3 and T5 / T6 / T7 run side by side:",
        "  they must not touch.",
    ]),
    ("Wires underneath", "bottom", list(WIRES), [
        "Insulated wire, 2 mm stripped at each end,",
        "soldered onto the pads:",
        "W1  GPS TX → pin 5",
        "W2  middle pad of T6 → T3 (GND) at B11",
        "Then do the measurements in the README",
        "before plugging anything in.",
    ]),
    ("Plug in and connect", "top", ["module", "ext"], [
        "Printed side up again. Plug the SuperMini in:",
        "  chip side up, USB-C on the left.",
        "GPS onto the header with 4 jumpers, by the",
        "labels on the GPS module: TX→M2, GND→M3,",
        "VCC→M4, RX→M5.",
        "Remote button into J1: its + side to screw 1,",
        "  its − side to screw 2.",
        "USB-C to the car charger.",
    ]),
]


# ---------------------------------------------------------------- checks

def hole(name):
    col = int(name[1:])
    assert name[0] in ROW_NAMES and 1 <= col <= COLS, f"{name} is not on the board"
    return col, ROW_NAMES.index(name[0])


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
.axis{font-size:13px;fill:#f1f3f5;text-anchor:middle;font-weight:600}
.ghost{fill:none;stroke:#d3f0df;stroke-width:2;stroke-dasharray:6 4;opacity:.75}
.ghostt{font-size:12px;font-weight:700;fill:#d3f0df;text-anchor:middle;opacity:.9}
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
    # CSS classes beat presentation attributes, so a fill, size or anchor given on a <text>
    # would be ignored: turn those attributes into an inline style, which beats the class.
    def inline(m):
        props = re.findall(r' (fill|font-size|font-weight|text-anchor)="([^"]+)"', m.group(0))
        tag = re.sub(r' (fill|font-size|font-weight|text-anchor)="[^"]+"', "", m.group(0))
        if not props:
            return tag
        size = lambda k, val: val + "px" if k == "font-size" and val.isdigit() else val
        style = ";".join(f"{k}:{size(k, val)}" for k, val in props)
        return tag[:-1] + f' style="{style}">'
    body = re.sub(r"<text[^>]*>", inline, body)
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
        return self.ox + M + (c - 1) * P, self.oy + M + (ROWS - 1 - row) * P

    def board(self):
        # Letters, numbers and "40*60MM" are printed on the parts side only; the solder side is bare.
        s = [f'<rect x="{self.ox}" y="{self.oy}" width="{bw()}" height="{bh()}" rx="12" class="pcb"/>']
        for x in (self.ox + 15, self.ox + bw() - 15):   # mounting holes
            for y in (self.oy + 15, self.oy + bh() - 15):
                s.append(f'<circle cx="{x}" cy="{y}" r="5" fill="#fff"/>')
        if not self.mirror:
            s.append(f'<text x="{self.ox + bw() / 2}" y="{self.oy + 26}" class="axis">40*60MM</text>')
            for c in range(1, COLS + 1):
                x, _ = self.xy(f"A{c}")
                s.append(f'<text x="{x}" y="{self.oy + bh() - 22}" class="axis">{c}</text>')
        for r in ROW_NAMES:
            _, y = self.xy(f"{r}1")
            if not self.mirror:
                s.append(f'<text x="{self.ox + 37}" y="{y + 5}" class="axis">{r}</text>')
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

def top_item(v, key, pin_labels=True):
    s = []
    if key in ("hdrTop", "hdrBot"):
        row = TOP_ROW if key == "hdrTop" else BOTTOM_ROW
        (x0, y), (x1, _) = v.xy(f"{row}2"), v.xy(f"{row}9")
        s.append(f'<rect x="{x0 - 15}" y="{y - 13}" width="{x1 - x0 + 30}" height="26" rx="3" fill="#212529"/>')
        labels = SUPERMINI_TOP if row == TOP_ROW else SUPERMINI_BOTTOM
        for i, lab in enumerate(labels):
            x, yy = v.xy(f"{row}{i + 2}")
            s.append(f'<rect x="{x - 4}" y="{yy - 4}" width="8" height="8" fill="#868e96"/>')
            if pin_labels:
                ty = yy - 20 if row == TOP_ROW else yy + 30
                s.append(f'<text x="{x}" y="{ty}" class="lab">{lab}</text>')
    elif key == "hdrG":
        pads = list(GPS_PADS)
        (x0, y), (x1, _) = v.xy(pads[0]), v.xy(pads[-1])
        s.append(f'<rect x="{x0 - 14}" y="{y - 12}" width="{x1 - x0 + 28}" height="24" rx="2" fill="#111"/>')
        for pad, lab in GPS_PADS.items():
            x, yy = v.xy(pad)
            s.append(f'<rect x="{x - 4}" y="{yy - 4}" width="8" height="8" fill="#fcc419"/>'
                     f'<text x="{x}" y="{yy - 20}" class="lab">{lab}</text>')
    elif key in ("R1", "R3"):
        (ax, ay), (bx, by) = v.xy((R1 if key == "R1" else R3)[0]), v.xy((R1 if key == "R1" else R3)[1])
        value = "330Ω" if key == "R1" else "1k"
        s.append(f'<line x1="{ax}" y1="{ay}" x2="{bx}" y2="{by}" stroke="#adb5bd" stroke-width="4"/>'
                 f'<rect x="{(ax + bx) / 2 - 38}" y="{ay - 12}" width="76" height="24" rx="10" fill="#e9d5a1" '
                 f'stroke="#7a5c1e" stroke-width="2"/>'
                 f'<text x="{(ax + bx) / 2}" y="{ay + 5}" class="labd">{key} {value}</text>')
    elif key == "D1":
        (px, py), (nx, ny) = v.xy(D1["+"]), v.xy(D1["−"])
        cx = (px + nx) / 2
        flat = cx + (13 if nx > px else -13)   # the flat side of the rim marks the − leg
        s.append(f'<circle cx="{cx}" cy="{py}" r="15" fill="#fa5252" stroke="#a51111" stroke-width="2"/>'
                 f'<line x1="{flat}" y1="{py - 11}" x2="{flat}" y2="{py + 11}" stroke="#fff" stroke-width="3"/>')
        for lab, (x, y) in (("+", (px, py)), ("−", (nx, ny))):   # leg marks inside the rim
            s.append(f'<text x="{x + (cx - x) * 0.45}" y="{y + 5}" class="lab">{lab}</text>')
        s.append(f'<text x="{max(px, nx) + 26}" y="{py + 5}" class="lab">D1</text>')
    elif key == "R2":
        (ax, ay), (bx, by) = v.xy(R2[0]), v.xy(R2[1])
        s.append(f'<line x1="{ax}" y1="{ay}" x2="{bx}" y2="{by}" stroke="#adb5bd" stroke-width="4"/>'
                 f'<circle cx="{ax}" cy="{ay}" r="12" fill="#e9d5a1" stroke="#7a5c1e" stroke-width="2"/>'
                 f'<text x="{bx - 18}" y="{by + 5}" class="lab" text-anchor="end">R2 100k ↑</text>')
    elif key == "Q1":
        # TO-92 from above: legs in one column, flat face toward the terminal (E-B-C parts such as
        # 2N2222 or S8050; C-B-E parts such as BC547 face the other way, see the README)
        (ex, ey), (_, cy) = v.xy(Q1["E"]), v.xy(Q1["C"])
        top, bot, flat, back = cy - 26, ey + 26, ex + 13, ex - 27
        s.append(f'<path d="M{flat},{top} L{flat},{bot} A{flat - back},{(bot - top) / 2} 0 0 1 {flat},{top} Z" '
                 f'fill="#16181b" stroke="#495057" stroke-width="2"/>'
                 f'<line x1="{flat}" y1="{top + 3}" x2="{flat}" y2="{bot - 3}" stroke="#ced4da" stroke-width="3"/>'
                 f'<text x="{flat + 4}" y="{top - 10}" class="lab">Q1 NPN</text>')
        for n, pad in Q1.items():
            x, y = v.xy(pad)
            s.append(f'<rect x="{x - 5}" y="{y - 5}" width="10" height="10" fill="#adb5bd"/>'
                     f'<text x="{flat + 14}" y="{y + 5}" class="lab">{n}</text>')
    elif key == "J1":
        (tx, ty), (_ux, uy) = v.xy(J1["1"]), v.xy(J1["2"])
        s.append(f'<rect x="{tx - 1.25 * P}" y="{ty - 0.85 * P}" width="{2.5 * P}" height="{uy - ty + 1.7 * P}" rx="5" '
                 f'fill="#2b8a3e" stroke="#0b3d1f" stroke-width="2"/>')
        for n, pad in J1.items():
            x, y = v.xy(pad)
            s.append(f'<circle cx="{x}" cy="{y}" r="10" fill="#ced4da" stroke="#495057" stroke-width="2"/>'
                     f'<line x1="{x - 6}" y1="{y + 6}" x2="{x + 6}" y2="{y - 6}" stroke="#495057" stroke-width="2.5"/>'
                     f'<text x="{x - 23}" y="{y + 5}" class="lab">{n}</text>')
        s.append(f'<text x="{tx}" y="{ty - 1.1 * P}" class="lab">J1 →</text>')
    elif key == "module":
        (x0, y0), (x1, y1) = v.xy(f"{TOP_ROW}2"), v.xy(f"{BOTTOM_ROW}9")
        l, t, r, b = x0 - 1.3 * P, y0 - 0.65 * P, x1 + 1.3 * P, y1 + 0.65 * P
        s.append(f'<rect x="{l}" y="{t}" width="{r - l}" height="{b - t}" rx="6" fill="#1c2b4a" stroke="#adb5bd" stroke-width="2"/>'
                 f'<rect x="{l - 22}" y="{(t + b) / 2 - 26}" width="40" height="52" rx="9" fill="#ced4da" stroke="#495057" stroke-width="2"/>'
                 f'<text x="{l - 2}" y="{(t + b) / 2 + 5}" class="labd" font-size="11">USB-C</text>'
                 f'<text x="{(l + r) / 2}" y="{(t + b) / 2 - 4}" class="lab">ESP32-C3</text>'
                 f'<text x="{(l + r) / 2}" y="{(t + b) / 2 + 16}" class="lab">SuperMini</text>'
                 f'<text x="{(l + r) / 2}" y="{(t + b) / 2 + 36}" class="lab" font-size="11">chip side up</text>'
                 f'<rect x="{r - 30}" y="{t + 10}" width="20" height="{b - t - 20}" rx="3" fill="#495057"/>')
        for row, labels in ((TOP_ROW, SUPERMINI_TOP), (BOTTOM_ROW, SUPERMINI_BOTTOM)):
            for i, lab in enumerate(labels):
                x, y = v.xy(f"{row}{i + 2}")
                s.append(f'<text x="{x}" y="{y + 5}" class="pinl">{lab}</text>')
    elif key == "ext":
        # GPS cable: four wires straight up over the free rows and off the board edge to the module
        top = v.oy - 24
        for pad, lab in GPS_PADS.items():
            x, y = v.xy(pad)
            net = {"VCC": "3V3", "GND": "GND", "TX": "TXD", "RX": "RXD"}[lab]
            s.append(f'<path d="M{x},{y} L{x},{top}" fill="none" stroke="{NETS[net][0]}" '
                     f'stroke-width="5" stroke-linecap="round"/>')
        x, _ = v.xy("A7")
        gps = ", ".join(f"{lab} → {pad}" for pad, lab in GPS_PADS.items())
        s.append(f'<text x="{x - 6}" y="{top + 4}" class="labd" text-anchor="start">↑ GPS module: {gps}</text>')
        for net, pad in (("OUT1", J1["1"]), ("GND", J1["2"])):
            x, y = v.xy(pad)
            s.append(f'<path d="M{x + 12},{y} L{x + 2.2 * P},{y}" stroke="{NETS[net][0]}" stroke-width="5" stroke-linecap="round"/>')
        (x, y1), (_x, y2) = v.xy(J1["1"]), v.xy(J1["2"])
        s.append(f'<text x="{x + 1.4 * P}" y="{(y1 + y2) / 2 + 5}" class="lab">remote</text>')
    return s


def top_board(v, show, new):
    s = v.board()
    for key in ["hdrTop", "hdrBot", "hdrG", "R1", "R2", "R3", "D1", "Q1", "J1", "module", "ext"]:
        if key in show:
            state = "new" if key in new else ("done" if new else "final")
            # with the SuperMini plugged in its own pin labels replace the header labels
            s += group(top_item(v, key, pin_labels="module" not in show), state)
    return s


# ---------------------------------------------------------------- bottom-view items

def ghost_parts(v):
    """Dashed outlines of the parts on the other side, as seen through the board from below."""
    s = []

    def box(pads, mx, my, label, ly=None):
        xs, ys = zip(*(v.xy(p) for p in pads))
        l, r, t, b = min(xs) - mx, max(xs) + mx, min(ys) - my, max(ys) + my
        s.append(f'<rect x="{l}" y="{t}" width="{r - l}" height="{b - t}" rx="5" class="ghost"/>')
        if label:
            s.append(f'<text x="{(l + r) / 2}" y="{(t + b) / 2 + 5 if ly is None else ly}" class="ghostt">{label}</text>')
        return l, r, t, b

    l, r, t, b = box([f"{TOP_ROW}2", f"{BOTTOM_ROW}9"], 1.3 * P, 0.65 * P, None)
    usb_right = v.xy(f"{TOP_ROW}2")[0] > v.xy(f"{TOP_ROW}9")[0]
    ux = r - 18 if usb_right else l - 22
    mx = (l + r) / 2 + (r - l) * (-0.22 if usb_right else 0.22)   # toward the far end, clear of W2
    s.append(f'<rect x="{ux}" y="{(t + b) / 2 - 26}" width="40" height="52" rx="9" class="ghost"/>'
             f'<text x="{ux + 20}" y="{(t + b) / 2 + 5}" class="ghostt">USB-C</text>'
             f'<text x="{mx}" y="{(t + b) / 2 - 4}" class="ghostt">SuperMini</text>'
             f'<text x="{mx}" y="{(t + b) / 2 + 14}" class="ghostt">(on the other side)</text>')
    box(list(GPS_PADS), 14, 12, None)
    for name, (a, b) in (("R1", R1), ("R3", R3)):
        (ax, ay), (bx, _) = v.xy(a), v.xy(b)
        s.append(f'<rect x="{(ax + bx) / 2 - 38}" y="{ay - 12}" width="76" height="24" rx="10" class="ghost"/>'
                 f'<text x="{(ax + bx) / 2}" y="{ay + 5}" class="ghostt">{name}</text>')
    rx_, ry_ = v.xy(R2[0])
    s.append(f'<circle cx="{rx_}" cy="{ry_}" r="13" class="ghost"/>')
    (px, py), (nx, _) = v.xy(D1["+"]), v.xy(D1["−"])
    s.append(f'<circle cx="{(px + nx) / 2}" cy="{py}" r="15" class="ghost"/>')
    box(list(Q1.values()), 16, 16, None)
    box(list(J1.values()), 1.25 * P, 0.85 * P, "J1", v.xy(J1["2"])[1] - (v.xy(J1["2"])[1] - v.xy(J1["1"])[1]) / 2 + 5)
    return s


def joint_labels(v):
    """What each solder joint is: SuperMini pin names, GPS pins, Q1 legs, J1 screws."""
    s = []
    lab = lambda x, y, t: s.append(f'<text x="{x}" y="{y}" class="pinl">{t}</text>')
    for i, name in enumerate(SUPERMINI_TOP):      # labels inside the SuperMini outline
        x, y = v.xy(f"{TOP_ROW}{i + 2}")
        lab(x, y + 25, name)
    for i, name in enumerate(SUPERMINI_BOTTOM):
        x, y = v.xy(f"{BOTTOM_ROW}{i + 2}")
        lab(x, y - 15, name)
    for pad, name in GPS_PADS.items():            # above the trail labels T5-T7
        x, y = v.xy(pad)
        lab(x, y - 32, name)
    kx = v.xy(Q1["B"])[0]
    side = -1 if v.mirror else 1   # B toward column 13, C toward column 11: away from the trails
    for n, (dx, dy) in {"E": (0, 28), "B": (17 * side, 5), "C": (-17 * side, 5)}.items():
        x, y = v.xy(Q1[n])
        lab(x + dx, y + dy, n)
    for n, pad in J1.items():
        x, y = v.xy(pad)
        lab(x - 22, y + 5, n)
    (x, _), (_, y) = v.xy(R2[0]), v.xy(R2[1])   # beside the lower leg, away from Q1 and the T2 label
    lab(x + (26 if x > kx else -26), y + 5, "R2")
    for n, pad in D1.items():                   # below the LED's legs, at the board edge
        x, y = v.xy(pad)
        lab(x, y + 30, "D1" + n)
    return s


def bottom_board(v, show_trails, show_wires, new):
    s = v.board() + ghost_parts(v)
    for pad in PINS.values():   # solder joints of everything that sits on top
        x, y = v.xy(pad)
        s.append(f'<circle cx="{x}" cy="{y}" r="8.5" fill="#dee2e6" stroke="#868e96" stroke-width="1.5"/>')
    for name in show_trails:
        pads, net = TRAILS[name]
        col = NETS[net][0]
        pts = " ".join(f"{x},{y}" for x, y in (v.xy(p) for p in pads))
        items = [f'<polyline points="{pts}" fill="none" stroke="#fff" stroke-width="11" stroke-linecap="round" stroke-linejoin="round"/>',
                 f'<polyline points="{pts}" fill="none" stroke="{col}" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/>']
        (x0, y0), (x1, y1) = v.xy(pads[0]), v.xy(pads[-1])
        if name in TRAIL_LABELS:
            pad, dx, dy = TRAIL_LABELS[name]
            x, y = v.xy(pad)
            dx = -dx if v.mirror else dx
            items.append(f'<text x="{x + dx}" y="{y + dy}" class="lab">{name}</text>')
        elif y0 == y1:
            # in the lowest row the wires come from above, so the label goes below
            lowest = min(hole(q)[1] for q, _n in ((q, n) for ps, n in TRAILS.values() for q in ps))
            dy = 26 if hole(pads[0])[1] == lowest else -14
            items.append(f'<text x="{(x0 + x1) / 2}" y="{y0 + dy}" class="lab">{name}</text>')
        else:
            # past the end away from the SuperMini: beside the trail the label would sit between
            # parallel trails, and on the SuperMini side wires to its pins pass by
            above = min(y0, y1) < v.xy(f"{TOP_ROW}2")[1]
            y = min(y0, y1) - 14 if above else max(y0, y1) + 26
            items.append(f'<text x="{x0}" y="{y}" class="lab">{name}</text>')
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
    s += joint_labels(v)
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
    top = 90   # room above the board for the GPS cable in step 5
    v = View(0, top, view == "bottom")
    if view == "top":
        show = set(new) | {"hdrTop", "hdrBot", "hdrG"}
        if n >= 5:
            show |= {"R1", "R2", "R3", "D1", "Q1", "J1"}
        body = top_board(v, show, set(new))
    else:
        body = bottom_board(v, list(TRAILS), list(WIRES) if n >= 4 else [], set(new))
    tx = bw() + 36
    side = "PRINTED side (parts)" if view == "top" else "UNPRINTED side (solder) · mirrored"
    text = [f'<text x="0" y="30" class="h1">Step {n} of 5 · {title}</text>',
            f'<text x="{tx}" y="{top + 26}" class="cap">{side}</text>']
    for i, line in enumerate(lines):
        cls = "mono" if re.match(r"[TW]\d+ | {5}", line) else "body"
        text.append(f'<text x="{tx}" y="{top + 64 + i * 26}" class="{cls}" xml:space="preserve">{line}</text>')
    y = top + 64 + len(lines) * 26 + 16
    text.append(f'<text x="{tx}" y="{y}" class="body" fill="#868e96">glowing = do now · faded = done before</text>')
    nets = []
    if view == "bottom":
        nets = sorted({TRAILS[k][1] for k in new if k in TRAILS} | {WIRES[k][2] for k in new if k in WIRES},
                      key=list(NETS).index)
        text += legend(tx, y + 40, nets)
    height = max(bh() + top + 60, y + 40 + len(nets) * 25 + 20)
    return svg(bw() + 480, height, "".join(text + body))


def overview():
    top, bottom = View(0, 50, False), View(bw() + 60, 50, True)
    body = top_board(top, {"hdrTop", "hdrBot", "hdrG", "R1", "R2", "R3", "D1", "Q1", "J1"}, set())
    body += bottom_board(bottom, list(TRAILS), list(WIRES), set())
    body += [f'<text x="{bw() / 2}" y="34" class="cap" text-anchor="middle">PRINTED side (parts)</text>',
             f'<text x="{bw() + 60 + bw() / 2}" y="34" class="cap" text-anchor="middle">UNPRINTED side (solder, mirrored)</text>']
    body += legend(30, bh() + 96, list(NETS)[:5]) + legend(420, bh() + 96, list(NETS)[5:])
    return svg(2 * bw() + 60, bh() + 96 + 5 * 25 + 20, "".join(body))


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
    s += box(780, 80, 250, 210, "GPS module", "e.g. ATGM336H, 3.3 V", "#5f3dc4")
    s += box(980, 390, 170, 150, "Spare remote", "button contacts", "#495057")
    esp = {"3V3": 160, "GND": 220, "GPIO5": 280, "GPIO4": 340, "GPIO7": 440}
    for lab, y in esp.items():
        s += pin(340, y, lab, "left")
    s.append('<text x="60" y="520" class="body" fill="#dee2e6">LED = GPIO8 · BOOT/SETUP = GPIO9</text>')
    gps = {"VCC": 160, "GND": 200, "TX": 240, "RX": 270}
    for lab, y in gps.items():
        s += pin(780, y, lab, "right")
    s += wire([(346, 160), (774, 160)], "3V3", "3V3", 380, 152)
    s += wire([(346, 220), (720, 220), (720, 200), (774, 200)], "GND", "GND", 380, 212)
    s += wire([(346, 280), (740, 280), (740, 240), (774, 240)], "TXD", "GPS TX → GPIO5", 380, 272)
    s += wire([(346, 340), (755, 340), (755, 270), (774, 270)], "RXD", "GPIO4 → GPS RX", 380, 332)
    s += wire([(346, 440), (440, 440)], "IO7")
    # R3 and the red LED D1 from GPIO7 to GND: lights while the board presses the remote
    s += wire([(405, 440), (405, 458)], "IO7")
    s.append('<rect x="393" y="458" width="24" height="44" rx="10" fill="#e9d5a1" stroke="#7a5c1e" stroke-width="2"/>'
             '<text x="425" y="478" class="labd" text-anchor="start" font-size="12">R3</text>'
             '<text x="425" y="493" class="labd" text-anchor="start" font-size="12">1k</text>')
    s += wire([(405, 502), (405, 522)], "IND")
    s.append('<path d="M393,522 L417,522 L405,542 Z" fill="#fa5252" stroke="#a51111" stroke-width="2"/>'
             '<line x1="393" y1="543" x2="417" y2="543" stroke="#a51111" stroke-width="3"/>'
             '<text x="425" y="537" class="labd" text-anchor="start" font-size="12">D1 red</text>')
    s += wire([(405, 544), (405, 580)], "GND")
    s.append('<rect x="440" y="428" width="84" height="24" rx="10" fill="#e9d5a1" stroke="#7a5c1e" stroke-width="2"/>'
             '<text x="482" y="445" class="labd">R1 330Ω</text>')
    s += wire([(524, 440), (712, 440)], "BASE")
    s += wire([(600, 440), (600, 462)], "BASE")
    s.append('<rect x="588" y="462" width="24" height="54" rx="10" fill="#e9d5a1" stroke="#7a5c1e" stroke-width="2"/>'
             '<text x="622" y="485" class="labd" text-anchor="start" font-size="12">R2</text>'
             '<text x="622" y="500" class="labd" text-anchor="start" font-size="12">100k</text>')
    s += wire([(600, 516), (600, 580)], "GND")
    s += wire([(760, 580), (370, 580), (370, 220)], "GND")
    # Q1: base bar, collector up to screw 1, emitter (arrow) down to GND and screw 2
    s.append('<line x1="712" y1="405" x2="712" y2="475" stroke="#212529" stroke-width="5"/>'
             '<line x1="712" y1="425" x2="760" y2="395" stroke="#212529" stroke-width="3"/>'
             '<line x1="712" y1="455" x2="760" y2="485" stroke="#212529" stroke-width="3"/>'
             '<path d="M760,485 L743,484 L751,470 Z" fill="#212529"/>'
             '<text x="700" y="392" class="labd" text-anchor="end" font-weight="700">Q1 NPN</text>'
             '<text x="700" y="410" class="labd" text-anchor="end" font-size="12">2N2222, S8050, BC547…</text>'
             '<text x="768" y="392" class="labd" text-anchor="start">C</text>'
             '<text x="768" y="498" class="labd" text-anchor="start">E</text>'
             '<text x="700" y="433" class="labd" text-anchor="end">B</text>')
    s += wire([(760, 395), (760, 360), (880, 360), (880, 420), (974, 420)], "OUT1", "J1 screw 1", 790, 350)
    s += wire([(760, 485), (760, 580)], "GND")
    s += wire([(760, 510), (974, 510)], "GND", "J1 screw 2", 790, 500)
    for (x, y, net) in ((600, 440, "BASE"), (600, 580, "GND"), (370, 220, "GND"),   # junctions
                        (405, 440, "IO7"), (405, 580, "GND"), (760, 510, "GND")):
        s.append(f'<circle cx="{x}" cy="{y}" r="7" fill="{NETS[net][0]}"/>')
    s.append('<text x="1065" y="470" class="body" text-anchor="middle" fill="#fff">+ to 1, − to 2</text>')
    s.append(f'<text x="40" y="{H - 24}" class="body">Same colours as on the board pictures. '
             'Q1 switches like a pressed button (+ side to screw 1); R2 keeps it off while the board boots.</text>')
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
