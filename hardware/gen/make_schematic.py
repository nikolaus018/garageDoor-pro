"""Generates hardware/garageDoor-pro.kicad_sch (plus project and library tables) from netlist.py.

Every pin gets a short wire stub ending in a net label, a power symbol, or a no-connect flag,
so the schematic is fully defined by netlist.py. Run with the system Python 3.
"""
import json
import os
import uuid

import netlist
from kicad_lib import Str, dump, find, first, get_symbol, symbol_pins

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.dirname(HERE)
PROJECT = "garageDoor-pro"
ROOT_UUID = str(uuid.uuid5(uuid.NAMESPACE_URL, "garageDoor-pro/root"))
STUB = 2.54
POWER_SYMBOLS = {"GND": "power:GND", "+3V3": "power:+3V3"}

# Schematic placement (A3 sheet, mm). Groups: power, MCU, GNSS, output, test points.
SCH_POS = {
    "J1": (45.72, 76.2), "F1": (101.6, 50.8), "D1": (127.0, 66.04), "C3": (149.86, 66.04),
    "U3": (182.88, 55.88), "C4": (215.9, 66.04), "U4": (101.6, 101.6), "R6": (60.96, 127.0),
    "R7": (76.2, 127.0),
    "U1": (200.66, 157.48), "C5": (137.16, 205.74), "C6": (149.86, 205.74), "R2": (264.16, 116.84),
    "C9": (276.86, 127.0), "R3": (264.16, 149.86), "R4": (276.86, 149.86), "R5": (289.56, 149.86),
    "SW1": (281.94, 177.8), "R11": (264.16, 203.2), "D3": (281.94, 213.36),
    "U2": (355.6, 147.32), "C7": (322.58, 198.12), "C8": (335.28, 198.12), "R1": (381.0, 93.98),
    "C1": (393.7, 106.68), "L1": (381.0, 116.84), "C2": (393.7, 147.32), "J2": (398.78, 175.26),
    "R8": (45.72, 210.82), "R9": (58.42, 210.82), "R10": (71.12, 210.82), "D2": (88.9, 226.06),
    "K1": (124.46, 210.82), "J3": (162.56, 213.36),
}
TP_ROW_Y = 264.16
TEXTS = [
    ("Power: USB-C in, polyfuse, TVS, 3.3 V LDO, USB ESD", 30.48, 30.48),
    ("ESP32-C3-MINI-1-H4X: GPIO4/5 UART1 to GNSS, GPIO7 switch, GPIO9 BOOT/SETUP button, GPIO10 status LED",
     137.16, 106.68),
    ("GNSS: MAX-M10S, active antenna bias-T per u-blox UBX-20053088 Fig. 28 (10R / 27nH / 10nF, 47pF DC block)",
     238.76, 76.2),
    ("Switch output: CPC1017N PhotoMOS -> screw terminal to the remote's button (either polarity)", 30.48, 190.5),
    ("Test pads (bottom side, not assembled)", 30.48, 251.46),
]


def uid(*parts):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "garageDoor-pro/" + "/".join(parts)))


def lib_prop(sym, name):
    for p in find(sym, "property"):
        if p[1] == name:
            return p
    return None


def outward(angle):
    """Screen-space direction pointing away from the symbol body for a pin with this angle."""
    return {0: (-1, 0), 180: (1, 0), 90: (0, 1), 270: (0, -1)}[int(angle) % 360]


def r(v):
    return f"{round(v, 4):g}"


def prop(name, value, x, y, hide=False, angle=0, justify=None):
    effects = ["effects", ["font", ["size", "1.27", "1.27"]]]
    if justify:
        effects.append(["justify"] + justify)
    if hide:
        effects.append(["hide", "yes"])
    return ["property", Str(name), Str(value), ["at", r(x), r(y), str(angle)], effects]


def symbol_instance(lib_id, ref, value, x, y, angle=0, footprint="", extra=None, in_bom=True, sym=None):
    sym = sym or get_symbol(lib_id)
    node = ["symbol", ["lib_id", Str(lib_id)], ["at", r(x), r(y), str(angle)], ["unit", "1"],
            ["exclude_from_sim", "no"], ["in_bom", "yes" if in_bom else "no"], ["on_board", "yes"],
            ["dnp", "no"], ["uuid", Str(uid("sym", ref))]]
    for name, value_, hide in [("Reference", ref, ref.startswith("#")), ("Value", value, ref.startswith("#FLG")),
                               ("Footprint", footprint, True), ("Datasheet", "~", True)]:
        lp = lib_prop(sym, name)
        px, py = (float(first(lp, "at")[1]), float(first(lp, "at")[2])) if lp else (0.0, 0.0)
        if lp and name == "Datasheet":
            value_ = lp[2] or "~"
        node.append(prop(name, value_, x + px, y - py, hide=hide))
    for name, value_ in (extra or {}).items():
        node.append(prop(name, value_, x, y, hide=True))
    for num in sorted({p[0] for p in symbol_pins(sym)}):
        node.append(["pin", Str(num), ["uuid", Str(uid("pin", ref, num))]])
    node.append(["instances", ["project", Str(PROJECT),
                               ["path", Str("/" + ROOT_UUID), ["reference", Str(ref)], ["unit", "1"]]]])
    return node


class Sheet:
    def __init__(self):
        self.items = []
        self.lib_ids = set()
        self.pwr = 0
        self.points = {}  # connection point -> net, to catch accidental merges

    def claim(self, at, net, what):
        key = (round(at[0], 2), round(at[1], 2))
        if key in self.points and self.points[key] != net:
            raise ValueError(f"{what} at {key} collides with net {self.points[key]}")
        self.points[key] = net

    def wire(self, a, b, key):
        self.items.append(["wire", ["pts", ["xy", r(a[0]), r(a[1])], ["xy", r(b[0]), r(b[1])]],
                           ["stroke", ["width", "0"], ["type", "default"]], ["uuid", Str(uid("wire", key))]])

    def label(self, net, at, direction, key):
        angle = {(1, 0): 0, (-1, 0): 180, (0, -1): 90, (0, 1): 270}[direction]
        justify = ["left", "bottom"] if angle in (0, 90) else ["right", "bottom"]
        self.items.append(["label", Str(net), ["at", r(at[0]), r(at[1]), str(angle)], ["fields_autoplaced", "yes"],
                           ["effects", ["font", ["size", "1.27", "1.27"]], ["justify"] + justify],
                           ["uuid", Str(uid("label", key))]])

    def power(self, net, at, direction, key):
        lib_id = POWER_SYMBOLS[net]
        self.lib_ids.add(lib_id)
        self.pwr += 1
        if net == "GND":   # default graphic points down
            angle = {(0, 1): 0, (1, 0): 90, (0, -1): 180, (-1, 0): 270}[direction]
        else:              # +3V3 graphic points up
            angle = {(0, -1): 0, (-1, 0): 90, (0, 1): 180, (1, 0): 270}[direction]
        self.items.append(symbol_instance(lib_id, f"#PWR{self.pwr:03d}", net, at[0], at[1], angle))

    def flag(self, net, at, n):
        self.lib_ids.add("power:PWR_FLAG")
        self.items.append(symbol_instance("power:PWR_FLAG", f"#FLG{n:02d}", "PWR_FLAG", at[0], at[1]))
        if net in POWER_SYMBOLS:
            self.power(net, at, (0, 1), f"flag{n}")
        else:
            self.label(net, at, (1, 0), f"flag{n}")

    def no_connect(self, at, key):
        self.items.append(["no_connect", ["at", r(at[0]), r(at[1])], ["uuid", Str(uid("nc", key))]])

    def text(self, s, x, y):
        self.items.append(["text", Str(s), ["exclude_from_sim", "no"], ["at", r(x), r(y), "0"],
                           ["effects", ["font", ["size", "2", "2"]], ["justify", "left", "bottom"]],
                           ["uuid", Str(uid("text", s))]])


def place_part(sheet, ref, lib_id, value, footprint, x, y, pin_net, extra, in_bom=True):
    sym = get_symbol(lib_id)
    sheet.lib_ids.add(lib_id)
    sheet.items.append(symbol_instance(lib_id, ref, value, x, y, 0, footprint, extra, in_bom, sym))
    nc = set(netlist.NO_CONNECT)
    stacks = {}  # stacked pins (same position) share one stub and must share a net
    for num, _name, _etype, px, py, angle in symbol_pins(sym):
        stacks.setdefault((px, py, angle), []).append(num)
    for (px, py, angle), nums in stacks.items():
        at = (x + px, y - py)
        key = f"{ref}.{nums[0]}"
        nets = {"NC" if (ref, n) in nc else pin_net.get((ref, n)) for n in nums}
        if None in nets:
            missing = [n for n in nums if (ref, n) not in nc and (ref, n) not in pin_net]
            raise ValueError(f"{ref} pins {missing} are neither on a net nor marked no-connect")
        if len(nets) != 1:
            raise ValueError(f"{ref} stacked pins {nums} are on different nets {nets}")
        net = nets.pop()
        if net == "NC":
            sheet.claim(at, f"NC:{key}", key)
            sheet.no_connect(at, key)
            continue
        d = outward(angle)
        end = (at[0] + d[0] * STUB, at[1] + d[1] * STUB)
        sheet.claim(at, f"PIN:{key}", key)
        sheet.claim(end, f"END:{key}:{net}", key)
        sheet.wire(at, end, key)
        if net in POWER_SYMBOLS:
            sheet.power(net, end, d, key)
        else:
            sheet.label(net, end, d, key)


def build():
    pin_net = netlist.pin_nets()
    used = {rp for rp in pin_net} | set(netlist.NO_CONNECT)
    sheet = Sheet()

    for ref, (value, lib_id, footprint, lcsc, mpn, desc) in netlist.PARTS.items():
        x, y = SCH_POS[ref]
        place_part(sheet, ref, lib_id, value, footprint, x, y, pin_net,
                   {"LCSC": lcsc, "MPN": mpn, "Description": desc})
        pins = {p[0] for p in symbol_pins(get_symbol(lib_id))}
        stray = {p for (rr, p) in used if rr == ref} - pins
        if stray:
            raise ValueError(f"{ref}: netlist uses pins {stray} that the symbol does not have")

    for i, (ref, net) in enumerate(netlist.TEST_POINTS.items()):
        place_part(sheet, ref, "Connector:TestPoint", net, netlist.TEST_POINT_FOOTPRINT,
                   40.64 + i * 20.32, TP_ROW_Y, pin_net, {}, in_bom=False)
    for i, ref in enumerate(netlist.MOUNTING_HOLES):
        sheet.lib_ids.add("Mechanical:MountingHole")
        sheet.items.append(symbol_instance("Mechanical:MountingHole", ref, "M2.5",
                                           259.08 + i * 12.7, 264.16, 0, netlist.MOUNTING_HOLE_FOOTPRINT,
                                           in_bom=False))

    # Nets without any power_out pin need a PWR_FLAG for ERC.
    sheet.flag("GND", (299.72, 251.46), 1)
    sheet.flag("VIN_5V", (322.58, 251.46), 2)
    sheet.flag("VBUS", (345.44, 251.46), 3)

    for s, x, y in TEXTS:
        sheet.text(s, x, y)

    lib_symbols = ["lib_symbols"] + [get_symbol(lid) for lid in sorted(sheet.lib_ids)]
    doc = ["kicad_sch", ["version", "20250114"], ["generator", Str("eeschema")], ["generator_version", Str("9.0")],
           ["uuid", Str(ROOT_UUID)], ["paper", Str("A3")],
           ["title_block", ["title", Str("garageDoor-pro")], ["date", Str("2026-10-14")], ["rev", Str("1.0")],
            ["comment", "1", Str("ESP32-C3 + MAX-M10S automatic garage door opener")],
            ["comment", "2", Str("Generated from hardware/gen/netlist.py - edit that, not this file")]],
           lib_symbols] + sheet.items + [["sheet_instances", ["path", Str("/"), ["page", Str("1")]]]]
    with open(os.path.join(HW, PROJECT + ".kicad_sch"), "w") as f:
        f.write(dump(doc) + "\n")


STD_SYMBOL_LIBS = ["power", "Device", "Connector", "Regulator_Linear", "Power_Protection", "RF_GPS",
                   "Relay_SolidState", "Switch", "Mechanical"]


def footprint_libs():
    libs = {fp.split(":")[0] for (_v, _s, fp, *_rest) in netlist.PARTS.values()}
    libs |= {netlist.TEST_POINT_FOOTPRINT.split(":")[0], netlist.MOUNTING_HOLE_FOOTPRINT.split(":")[0]}
    return sorted(libs - {"garageDoor"})


def write_project_files():
    # Project-local tables, so the project opens the same on any machine without global setup.
    sym = ['  (lib (name "Espressif")(type "KiCad")(uri "${KIPRJMOD}/lib/Espressif.kicad_sym")(options "")'
           '(descr "ESP32-C3-MINI-1 from espressif/kicad-libraries 3.2.1"))']
    sym += [f'  (lib (name "{n}")(type "KiCad")(uri "${{KICAD10_SYMBOL_DIR}}/{n}.kicad_sym")(options "")(descr ""))'
            for n in STD_SYMBOL_LIBS]
    with open(os.path.join(HW, "sym-lib-table"), "w") as f:
        f.write("(sym_lib_table\n  (version 7)\n" + "\n".join(sym) + "\n)\n")
    fps = ['  (lib (name "garageDoor")(type "KiCad")(uri "${KIPRJMOD}/lib/garageDoor.pretty")(options "")'
           '(descr "Project footprints"))']
    fps += [f'  (lib (name "{n}")(type "KiCad")(uri "${{KICAD10_FOOTPRINT_DIR}}/{n}.pretty")(options "")(descr ""))'
            for n in footprint_libs()]
    with open(os.path.join(HW, "fp-lib-table"), "w") as f:
        f.write("(fp_lib_table\n  (version 7)\n" + "\n".join(fps) + "\n)\n")

    def nc(name, track, clearance, priority):
        return {"name": name, "clearance": clearance, "track_width": track, "via_diameter": 0.6,
                "via_drill": 0.3, "microvia_diameter": 0.3, "microvia_drill": 0.1, "diff_pair_width": 0.2,
                "diff_pair_gap": 0.25, "diff_pair_via_gap": 0.25, "wire_width": 6, "bus_width": 12,
                "line_style": 0, "priority": priority}

    classes = [nc("Default", 0.2, 0.15, 2147483647)]
    patterns = []
    for i, (name, c) in enumerate(netlist.NET_CLASSES.items()):
        classes.append(nc(name, c["track"], c["clearance"], i))
        patterns += [{"netclass": name, "pattern": netlist.pcb_net_name(n)} for n in c["nets"]]
    project = {
        "meta": {"filename": PROJECT + ".kicad_pro", "version": 3},
        "board": {"design_settings": {
            "defaults": {"copper_line_width": 0.2, "silk_line_width": 0.15, "silk_text_size_h": 0.8,
                         "silk_text_size_v": 0.8, "silk_text_thickness": 0.15},
            "rules": {  # JLCPCB 4-layer standard capabilities, with margin
                "min_clearance": 0.15, "min_track_width": 0.15, "min_via_diameter": 0.5,
                "min_through_hole_diameter": 0.3, "min_via_annular_width": 0.13,
                "min_copper_edge_clearance": 0.3, "min_hole_clearance": 0.25, "min_hole_to_hole": 0.25,
                "min_silk_clearance": 0.0, "min_text_height": 0.6, "min_text_thickness": 0.1,
                "solder_mask_to_copper_clearance": 0.0, "min_microvia_diameter": 0.2, "min_microvia_drill": 0.1},
            "track_widths": [0.0, 0.2, 0.25, 0.36, 0.5, 0.8], "via_dimensions": [{"diameter": 0.0, "drill": 0.0},
                                                                              {"diameter": 0.6, "drill": 0.3}],
        }},
        "net_settings": {"meta": {"version": 4}, "classes": classes, "netclass_patterns": patterns},
        "schematic": {"legacy_lib_dir": "", "legacy_lib_list": []},
        "sheets": [[ROOT_UUID, "Root"]],
    }
    with open(os.path.join(HW, PROJECT + ".kicad_pro"), "w") as f:
        json.dump(project, f, indent=2)


if __name__ == "__main__":
    write_project_files()
    build()
    print("wrote", os.path.join(HW, PROJECT + ".kicad_sch"))
