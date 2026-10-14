"""Builds hardware/garageDoor-pro.kicad_pcb from netlist.py with KiCad's pcbnew Python API.

Run with KiCad's bundled Python (see hardware/build.sh):
  1. place footprints, assign nets, board outline, inner GND/3V3 planes, antenna keep-out
  2. hand-route the GNSS RF path (50 ohm) and lock it
  3. autoroute everything else with Freerouting (Specctra DSN/SES round trip)
  4. add outer GND pours and stitching vias, fill zones, save
"""
import math
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import pcbnew  # noqa: E402

import netlist  # noqa: E402
from kicad_lib import first, get_symbol, symbol_pins  # noqa: E402
from make_schematic import lib_prop, uid  # noqa: E402

HW = os.path.dirname(HERE)
PCB = os.path.join(HW, "garageDoor-pro.kicad_pcb")
OX, OY = 100.0, 100.0  # board top-left corner in KiCad coordinates
KICAD_FP = os.path.expanduser("~/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints")
JAVA = os.environ.get("JAVA", "/opt/homebrew/opt/openjdk/bin/java")
FREEROUTING = os.environ.get("FREEROUTING", os.path.expanduser("~/.local/freerouting/freerouting-2.5.0.jar"))
CORNER_R = 1.5
F = pcbnew.FromMM


def at(x, y):
    return pcbnew.VECTOR2I(F(OX + x), F(OY + y))


def fp_lib_path(lib):
    if lib == "garageDoor":
        return os.path.join(HW, "lib", "garageDoor.pretty")
    return os.path.join(KICAD_FP, lib + ".pretty")


def unconnected_net_names():
    """KiCad gives every no-connect pin its own net, e.g. unconnected-(J1-SBU1-PadA8)."""
    names = {}
    for ref, (_v, lib_id, *_rest) in netlist.PARTS.items():
        pins = {num: name for num, name, *_ in symbol_pins(get_symbol(lib_id))}
        for r, num in netlist.NO_CONNECT:
            if r == ref:
                names[(ref, num)] = f"unconnected-({ref}-{pins[num]}-Pad{num})"
    return names


def datasheet(lib_id):
    p = lib_prop(get_symbol(lib_id), "Datasheet")
    return p[2] if p and p[2] else ""


def add_footprints(board, nets):
    pin_net = netlist.pin_nets()
    nc_nets = unconnected_net_names()
    for name in nc_nets.values():
        ni = pcbnew.NETINFO_ITEM(board, name)
        board.Add(ni)
        nets[name] = ni
    pin_net = dict(pin_net)
    pin_net.update(nc_nets)
    parts = {ref: (v, fp, {"LCSC": lcsc, "MPN": mpn, "Description": d, "Datasheet": datasheet(sym)})
             for ref, (v, sym, fp, lcsc, mpn, d) in netlist.PARTS.items()}
    for ref, net in netlist.TEST_POINTS.items():
        parts[ref] = (net, netlist.TEST_POINT_FOOTPRINT, {})
    for ref in netlist.MOUNTING_HOLES:
        parts[ref] = ("M2.5", netlist.MOUNTING_HOLE_FOOTPRINT, {})

    footprints = {}
    for ref, (value, fpid, fields) in parts.items():
        lib, name = fpid.split(":")
        fp = pcbnew.FootprintLoad(fp_lib_path(lib), name)
        if fp is None:
            raise RuntimeError(f"footprint {fpid} not found")
        fp.SetFPID(pcbnew.LIB_ID(lib, name))
        fp.SetReference(ref)
        fp.SetValue(value)
        fp.SetPath(pcbnew.KIID_PATH("/" + uid("sym", ref)))
        fp.SetSheetname("/")
        fp.SetSheetfile("garageDoor-pro.kicad_sch")
        for k, v in fields.items():
            fp.SetField(k, v)
            fp.GetField(k).SetVisible(False)
        if ref.startswith("TP") or ref.startswith("H"):
            fp.SetExcludedFromBOM(True)
            fp.SetExcludedFromPosFiles(True)
        # Reference designators go to the assembly (fab) layer, not the silkscreen.
        fp.Reference().SetLayer(pcbnew.F_Fab)
        board.Add(fp)
        x, y, rot, side = netlist.PLACEMENT[ref]
        fp.SetPosition(at(x, y))
        fp.SetOrientationDegrees(rot)
        if side == "B":
            fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_TOP_BOTTOM)

        numbers = set()
        for pad in fp.Pads():
            num = pad.GetNumber()
            if not num:
                continue
            numbers.add(num)
            net = pin_net.get((ref, num))
            if net:
                pad.SetNet(nets[net])
        missing = {p for (r, p) in pin_net if r == ref} - numbers
        if missing:
            raise RuntimeError(f"{ref} ({fpid}) has no pads {missing}")
        footprints[ref] = fp
    return footprints


def add_outline(board):
    w, h, rr = netlist.BOARD_W, netlist.BOARD_H, CORNER_R

    def seg(a, b):
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(F(0.1))
        s.SetStart(at(*a))
        s.SetEnd(at(*b))
        board.Add(s)

    def arc(c, start, mid, end):
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(pcbnew.SHAPE_T_ARC)
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(F(0.1))
        s.SetArcGeometry(at(*start), at(*mid), at(*end))
        board.Add(s)

    k = rr * (1 - math.sqrt(0.5))
    seg((rr, 0), (w - rr, 0))
    seg((w, rr), (w, h - rr))
    seg((w - rr, h), (rr, h))
    seg((0, h - rr), (0, rr))
    arc(None, (w - rr, 0), (w - k, k), (w, rr))
    arc(None, (w, h - rr), (w - k, h - k), (w - rr, h))
    arc(None, (rr, h), (k, h - k), (0, h - rr))
    arc(None, (0, rr), (k, k), (rr, 0))


def rect_outline(zone, x0, y0, x1, y1):
    o = zone.Outline()
    o.NewOutline()
    for p in [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]:
        o.Append(at(*p))


def add_zone(board, nets, net, layer, priority, rect=None):
    z = pcbnew.ZONE(board)
    z.SetLayer(layer)
    z.SetNet(nets[net])
    z.SetAssignedPriority(priority)
    z.SetMinThickness(F(0.2))
    z.SetLocalClearance(F(0.25))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
    z.SetThermalReliefGap(F(0.3))
    z.SetThermalReliefSpokeWidth(F(0.35))
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    rect_outline(z, *(rect or (0, 0, netlist.BOARD_W, netlist.BOARD_H)))
    board.Add(z)
    return z


def add_antenna_keepout(board):
    """No tracks, vias or copper pours on any layer under/beside the ESP32 PCB antenna."""
    z = pcbnew.ZONE(board)
    z.SetIsRuleArea(True)
    z.SetLayerSet(pcbnew.LSET.AllCuMask())
    z.SetDoNotAllowTracks(True)
    z.SetDoNotAllowVias(True)
    z.SetDoNotAllowZoneFills(True)
    z.SetDoNotAllowPads(False)
    z.SetDoNotAllowFootprints(False)
    z.SetZoneName("ESP32 antenna keep-out")
    rect_outline(z, -1, -1, netlist.ANTENNA_KEEPOUT_X, netlist.BOARD_H + 1)
    board.Add(z)


def pad_of(fp, num):
    for pad in fp.Pads():
        if pad.GetNumber() == num:
            return pad
    raise KeyError(num)


def track(board, a, b, width, net, layer=pcbnew.F_Cu, locked=True):
    t = pcbnew.PCB_TRACK(board)
    t.SetStart(a)
    t.SetEnd(b)
    t.SetWidth(F(width))
    t.SetLayer(layer)
    t.SetNet(net)
    t.SetLocked(locked)
    board.Add(t)
    return t


def via(board, pos, net, locked=True, size=0.6, drill=0.3):
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(pos)
    v.SetWidth(F(size))
    v.SetDrill(F(drill))
    v.SetViaType(pcbnew.VIATYPE_THROUGH)
    v.SetNet(net)
    v.SetLocked(locked)
    board.Add(v)
    return v


def route_rf(board, fps, nets):
    """GNSS RF path on F.Cu over the In1 GND plane: RF_IN -> C2 -> ANT_FEED -> U.FL, plus the bias feed."""
    rf_w = netlist.NET_CLASSES["RF"]["track"]
    rf_in = pad_of(fps["U2"], "11").GetPosition()
    c2a = pad_of(fps["C2"], "1").GetPosition()
    c2b = pad_of(fps["C2"], "2").GetPosition()
    ufl = pad_of(fps["J2"], "1").GetPosition()
    l1b = pad_of(fps["L1"], "2").GetPosition()
    track(board, rf_in, c2a, rf_w, nets["GPS_RF_IN"])
    track(board, c2b, ufl, rf_w, nets["ANT_FEED"])
    tap = pcbnew.VECTOR2I(l1b.x, c2b.y)
    track(board, l1b, tap, 0.25, nets["ANT_FEED"])
    # Bias network: VCC_RF -> R1 -> ANT_BIAS (C1) -> L1, kept short and away from the RF line.
    route_bias(board, fps, nets)


def route_bias(board, fps, nets):
    """Bias network VCC_RF -> R1 -> ANT_BIAS (C1, L1): short tracks above the RF line."""
    w = 0.3
    vcc_rf = pad_of(fps["U2"], "14").GetPosition()
    r1a = pad_of(fps["R1"], "1").GetPosition()
    r1b = pad_of(fps["R1"], "2").GetPosition()
    c1a = pad_of(fps["C1"], "1").GetPosition()
    l1a = pad_of(fps["L1"], "1").GetPosition()
    d = abs(r1a.y - vcc_rf.y)
    knee = pcbnew.VECTOR2I(r1a.x - d, vcc_rf.y)          # 45-degree approach to R1
    track(board, vcc_rf, knee, w, nets["VCC_RF"])
    track(board, knee, r1a, w, nets["VCC_RF"])
    track(board, r1b, c1a, w, nets["ANT_BIAS"])
    dx = abs(r1b.x - l1a.x)
    knee2 = pcbnew.VECTOR2I(r1b.x, l1a.y - dx)            # down, then 45 degrees into L1
    track(board, r1b, knee2, w, nets["ANT_BIAS"])
    track(board, knee2, l1a, w, nets["ANT_BIAS"])


def thermal_vias_under_esp(board, fps, nets):
    """Vias inside the ESP32 module's centre GND pads: tie them to the In1 plane and conduct heat."""
    seen = set()
    for pad in fps["U1"].Pads():
        if pad.GetNumber() == "49" and pad.GetShape() == pcbnew.PAD_SHAPE_RECT:
            p = pad.GetPosition()
            key = (p.x, p.y)
            if key not in seen:
                seen.add(key)
                via(board, p, nets["GND"])


def freeroute(board):
    dsn = PCB.replace(".kicad_pcb", ".dsn")
    ses = PCB.replace(".kicad_pcb", ".ses")
    if os.path.exists(ses):
        os.remove(ses)
    if not pcbnew.ExportSpecctraDSN(board, dsn):
        raise RuntimeError("DSN export failed")
    cmd = [JAVA, "-jar", FREEROUTING, "-de", dsn, "-do", ses, "-mp", "40", "--gui.enabled=false"]
    print("running", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1800)
    if not os.path.exists(ses):
        raise RuntimeError("Freerouting produced no session file")
    if not pcbnew.ImportSpecctraSES(board, ses):
        raise RuntimeError("SES import failed")
    os.remove(dsn)
    os.remove(ses)


def add_silkscreen(board):
    def text(s, x, y, size=0.8, layer=pcbnew.F_SilkS, angle=0, mirror=False):
        t = pcbnew.PCB_TEXT(board)
        t.SetText(s)
        t.SetPosition(at(x, y))
        t.SetLayer(layer)
        t.SetTextSize(pcbnew.VECTOR2I(F(size), F(size)))
        t.SetTextThickness(F(0.15))
        t.SetTextAngleDegrees(angle)
        if mirror:
            t.SetMirrored(True)
        board.Add(t)
        return t

    text("garageDoor-pro v1.0", 25.6, 30.1, 0.8)
    text("<- REMOTE", 49.0, 25.4, 0.8)
    text("5V", 30.0, 2.0, 0.8)
    text("ANT", 55.75, 21.1, 0.8)
    text("SETUP", 20.2, 22.9, 0.8)
    text("STATUS", 3.6, 29.3, 0.8)
    text("PRESS", 15.2, 30.1, 0.8)
    # JLCPCB prints its order number where this placeholder is (bottom side).
    text("JLCJLCJLCJLC", 24.0, 20.0, 0.8, layer=pcbnew.B_SilkS, mirror=True)
    for ref, label in netlist.TEST_POINT_LABELS.items():
        x, y, _r, _s = netlist.PLACEMENT[ref]
        t = text(label, x + 1.1 + 0.45 * len(label), y, 0.8, layer=pcbnew.B_SilkS, mirror=True)


def build():
    board = pcbnew.NewBoard(PCB)
    board.SetCopperLayerCount(4)
    ds = board.GetDesignSettings()
    ds.SetBoardThickness(F(1.6))

    nets = {}
    for name in netlist.NETS:
        ni = pcbnew.NETINFO_ITEM(board, netlist.pcb_net_name(name))
        board.Add(ni)
        nets[name] = ni

    fps = add_footprints(board, nets)
    add_outline(board)
    add_antenna_keepout(board)
    add_zone(board, nets, "GND", pcbnew.In1_Cu, 1)
    add_zone(board, nets, "+3V3", pcbnew.In2_Cu, 1)
    route_rf(board, fps, nets)
    thermal_vias_under_esp(board, fps, nets)
    add_silkscreen(board)
    pcbnew.SaveBoard(PCB, board)
    return PCB


if __name__ == "__main__":
    build()
    print("wrote", PCB)
