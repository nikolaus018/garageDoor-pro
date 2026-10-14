"""Builds hardware/garageDoor-pro.kicad_pcb from netlist.py with KiCad's pcbnew Python API.

Run with KiCad's bundled Python (see hardware/build.sh):
  1. place footprints, assign nets, board outline, inner GND/3V3 planes, antenna keep-out
  2. hand-route the GNSS RF path (50 ohm) and lock it
  3. autoroute everything else with Freerouting (Specctra DSN/SES round trip)
  4. add outer GND pours and stitching vias, fill zones, save
"""
import math
import os
import re
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


def route_vbus(board, fps, nets):
    """USB-C VBUS pads -> F1, by hand: the pads sit between CC/D+/D- and GND pads, a tight spot
    for the autorouter. Right pad pair: F.Cu down, right and up into F1. Left pad pair: via and a
    B.Cu run joining the right one."""
    w = netlist.NET_CLASSES["Power"]["track"]
    vbus = nets["VBUS"]
    pads = sorted({(p.GetPosition().x, p.GetPosition().y) for p in fps["J1"].Pads() if p.GetNetname() == "/VBUS"})
    (lx, ly), (rx, ry) = pads[0], pads[-1]
    f1 = pad_of(fps["F1"], "1").GetPosition()
    drop = ry + F(1.4)
    turn_x = rx + F(3.05)
    pts = [pcbnew.VECTOR2I(rx, ry), pcbnew.VECTOR2I(rx, drop), pcbnew.VECTOR2I(turn_x, drop),
           pcbnew.VECTOR2I(turn_x, f1.y), f1]
    for a, b in zip(pts, pts[1:]):
        track(board, a, b, w, vbus)
    via(board, pcbnew.VECTOR2I(rx, drop), vbus)
    track(board, pcbnew.VECTOR2I(lx, ly), pcbnew.VECTOR2I(lx, drop), w, vbus)
    via(board, pcbnew.VECTOR2I(lx, drop), vbus)
    track(board, pcbnew.VECTOR2I(lx, drop), pcbnew.VECTOR2I(rx, drop), w, vbus, layer=pcbnew.B_Cu)


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


FANOUT_NETS = ("GND", "+3V3")
FANOUT_TRACK = 0.3
COPPER_CLEARANCE = 0.2


def clear_of_other_nets(board, pos, radius, net_code):
    """True if no pad, track or via of another net is within `radius` of pos."""
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetCode() != net_code and pad.HitTest(pos, radius):
                return False
    for t in board.GetTracks():
        if t.GetNetCode() != net_code and t.HitTest(pos, radius):
            return False
    return True


def segment_clear(board, a, b, half_width, net_code):
    steps = max(2, int(math.hypot(b.x - a.x, b.y - a.y) / F(0.1)))
    for i in range(steps + 1):
        p = pcbnew.VECTOR2I(int(a.x + (b.x - a.x) * i / steps), int(a.y + (b.y - a.y) * i / steps))
        if not clear_of_other_nets(board, p, half_width + F(COPPER_CLEARANCE), net_code):
            return False
    return True


def in_bounds(pos, margin=0.6):
    x, y = pcbnew.ToMM(pos.x) - OX, pcbnew.ToMM(pos.y) - OY
    return (netlist.ANTENNA_KEEPOUT_X + margin < x < netlist.BOARD_W - 0.8
            and 0.8 < y < netlist.BOARD_H - 0.8)


MIN_VIA_PITCH = 0.7  # mm between via centres: 0.3 mm holes keep >= 0.4 mm apart


def far_from_vias(board, pos):
    return all(math.hypot(v.GetPosition().x - pos.x, v.GetPosition().y - pos.y) >= F(MIN_VIA_PITCH)
               for v in board.GetTracks() if v.Type() == pcbnew.PCB_VIA_T)


def fanout(board):
    """Short track + via from every SMD GND/3V3 pad down to its inner plane.

    Freerouting then only has to route the signal nets. Pads that already have a via inside
    them (ESP32 centre pads) are skipped.
    """
    failed = []
    vias_in_pads = [t for t in board.GetTracks() if t.Type() == pcbnew.PCB_VIA_T]
    for fp in board.GetFootprints():
        centre = fp.GetPosition()
        for pad in fp.Pads():
            if pad.GetNetname() not in FANOUT_NETS or pad.GetAttribute() != pcbnew.PAD_ATTRIB_SMD:
                continue
            layer = pcbnew.F_Cu if pad.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu
            p0 = pad.GetPosition()
            if any(pad.HitTest(v.GetPosition(), 0) for v in vias_in_pads):
                continue
            code = pad.GetNetCode()
            base = math.atan2(p0.y - centre.y, p0.x - centre.x) if p0 != centre else 0.0
            half = max(pad.GetSize(layer).x, pad.GetSize(layer).y) / 2
            done = False
            for extra in (0.55, 0.8, 1.1, 1.5, 2.0):
                for k in (0, 1, -1, 2, -2, 3, -3, 4):
                    ang = base + k * math.pi / 4
                    d = half + F(extra)
                    ux, uy = math.cos(ang), math.sin(ang)
                    pos = pcbnew.VECTOR2I(int(p0.x + d * ux), int(p0.y + d * uy))
                    # Start the track a little inside the pad, towards the via, so its edge never
                    # pokes past the pad (matters for pads at the antenna keep-out line).
                    inset = min(F(0.25), half - F(0.1))
                    start = pcbnew.VECTOR2I(int(p0.x + inset * ux), int(p0.y + inset * uy))
                    if not (in_bounds(pos) and in_bounds(start, margin=FANOUT_TRACK / 2 + 0.05)):
                        continue
                    if not far_from_vias(board, pos):
                        continue
                    if not clear_of_other_nets(board, pos, F(0.3 + COPPER_CLEARANCE), code):
                        continue
                    if not segment_clear(board, start, pos, F(FANOUT_TRACK / 2), code):
                        continue
                    track(board, start, pos, FANOUT_TRACK, pad.GetNet(), layer=layer)
                    vias_in_pads.append(via(board, pos, pad.GetNet()))
                    done = True
                    break
                if done:
                    break
            if not done:
                done = bridge_to_neighbour(board, fp, pad)
            if not done:
                failed.append(f"{fp.GetReference()}.{pad.GetNumber()}")
    return failed


def bridge_to_neighbour(board, fp, pad):
    """Fallback: short track to the nearest same-net pad of the same footprint."""
    p0 = pad.GetPosition()
    others = sorted((o for o in fp.Pads() if o is not pad and o.GetNetCode() == pad.GetNetCode()),
                    key=lambda o: math.hypot(o.GetPosition().x - p0.x, o.GetPosition().y - p0.y))
    for o in others[:3]:
        q = o.GetPosition()
        dist = math.hypot(q.x - p0.x, q.y - p0.y)
        if dist < F(0.05):
            continue  # coincident pad, already the same copper
        if dist > F(2.0):
            break
        ux, uy = (q.x - p0.x) / dist, (q.y - p0.y) / dist
        half = max(pad.GetSize(pcbnew.F_Cu).x, pad.GetSize(pcbnew.F_Cu).y) / 2
        inset = min(F(0.25), half - F(0.1))
        start = pcbnew.VECTOR2I(int(p0.x + inset * ux), int(p0.y + inset * uy))
        if in_bounds(start, margin=FANOUT_TRACK / 2 + 0.05) and segment_clear(
                board, start, q, F(FANOUT_TRACK / 2), pad.GetNetCode()):
            track(board, start, q, FANOUT_TRACK, pad.GetNet())
            return True
    return False


ROUTER_STRATEGIES = [
    ["-mp", "60"],
    ["-mp", "100", "-is", "random"],
    ["-mp", "100", "-us", "global"],
    ["-mp", "100", "-us", "hybrid", "-hr", "1:1"],
    ["-mp", "150", "-is", "sequential"],
]


def export_dsn(board, dsn):
    if not pcbnew.ExportSpecctraDSN(board, dsn):
        raise RuntimeError("DSN export failed")
    # Inner layers are solid GND / 3V3 planes: mark them as power layers so the router only
    # drops vias onto them and keeps signals on F.Cu / B.Cu.
    text = open(dsn).read()
    for layer in ("In1.Cu", "In2.Cu"):
        old = f"(layer {layer}\n      (type signal)"
        if old not in text:
            raise RuntimeError(f"unexpected DSN layer format for {layer}")
        text = text.replace(old, f"(layer {layer}\n      (type power)")
    # GND and 3V3 are complete already (fanout vias into the planes, verified by KiCad DRC).
    # Keep the nets, so their tracks/vias stay fixed obstacles, but give them no pins to route.
    for net in FANOUT_NETS:
        text, n = re.subn(r"\(net %s\n\s*\(pins [^)]*\)\n\s*\)" % re.escape(net), f"(net {net})", text)
        if n != 1:
            raise RuntimeError(f"could not strip pins of {net} from the DSN")
    open(dsn, "w").write(text)


def unconnected(board):
    board.BuildConnectivity()
    return board.GetConnectivity().GetUnconnectedCount(False)


def freeroute():
    """Tries router strategies on fresh copies of the placed board until one routes 100 %.

    Returns the routed board (zones not yet filled)."""
    dsn = PCB.replace(".kicad_pcb", ".dsn")
    ses = PCB.replace(".kicad_pcb", ".ses")
    best = None
    for opts in ROUTER_STRATEGIES:
        board = pcbnew.LoadBoard(PCB)
        export_dsn(board, dsn)
        if os.path.exists(ses):
            os.remove(ses)
        cmd = [JAVA, "-jar", FREEROUTING, "-de", dsn, "-do", ses, "--gui.enabled=false",
               "--router.neck_width_um=130"] + opts  # neck-down at fine-pitch pins, never below 0.13 mm
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1800)
        if not os.path.exists(ses) or not pcbnew.ImportSpecctraSES(board, ses):
            continue
        pcbnew.ZONE_FILLER(board).Fill(board.Zones())
        left = unconnected(board)
        print(f"router {' '.join(opts)}: {left} unconnected", flush=True)
        if best is None or left < best[0]:
            best = (left, board)
        if left == 0:
            break
    for f in (dsn, ses):
        if os.path.exists(f):
            os.remove(f)
    if best is not None and best[0] != 0:
        pcbnew.SaveBoard(PCB.replace(".kicad_pcb", "-incomplete.kicad_pcb"), best[1])
    if best is None or best[0] != 0:
        raise RuntimeError(f"no router strategy completed the board (best: {best and best[0]} unconnected)")
    return best[1]


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
    text("JLCJLCJLCJLC", 30.0, 16.5, 0.8, layer=pcbnew.B_SilkS, mirror=True)
    for ref, label in netlist.TEST_POINT_LABELS.items():
        x, y, _r, _s = netlist.PLACEMENT[ref]
        t = text(label, x + 1.1 + 0.45 * len(label), y, 0.8, layer=pcbnew.B_SilkS, mirror=True)


def build():
    board = pcbnew.NewBoard(PCB)
    board.SetCopperLayerCount(4)
    ds = board.GetDesignSettings()
    ds.SetBoardThickness(F(1.6))
    ds.m_TentViasFront = True   # vias under the ESP32 module and parts stay covered
    ds.m_TentViasBack = True

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
    route_vbus(board, fps, nets)
    thermal_vias_under_esp(board, fps, nets)
    failed = fanout(board)
    print("fanout failed for:", failed or "none")
    add_silkscreen(board)
    pcbnew.SaveBoard(PCB, board)
    return PCB


if __name__ == "__main__":
    build()
    print("wrote", PCB)
