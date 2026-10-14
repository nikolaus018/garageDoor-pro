"""Autoroutes the placed board with Freerouting, then adds outer GND pours and stitching vias.

Run with KiCad's bundled Python after make_pcb.py (see hardware/build.sh).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import pcbnew  # noqa: E402

import netlist  # noqa: E402
from make_pcb import PCB, F, add_zone, at, far_from_vias, freeroute, segment_clear, via  # noqa: E402

STITCH_PITCH = 2.5      # mm grid for GND stitching vias
STITCH_CLEARANCE = 0.3  # extra margin around other copper, on top of the via radius
EDGE_MARGIN = 1.0


def is_free(board, pos, radius):
    """True if nothing but GND copper is within `radius` of pos on any layer."""
    for fp in board.GetFootprints():
        if fp.GetCourtyard(pcbnew.F_CrtYd).Contains(pos) or fp.GetCourtyard(pcbnew.B_CrtYd).Contains(pos):
            return False
        for pad in fp.Pads():
            if pad.HitTest(pos, radius):
                return False
    for t in board.GetTracks():
        if t.HitTest(pos, radius):
            return False
    for d in board.GetDrawings():
        if d.GetLayer() == pcbnew.Edge_Cuts and d.HitTest(pos, F(EDGE_MARGIN)):
            return False
    return True


def stitch(board, gnd):
    r = F(0.3 + STITCH_CLEARANCE)
    added = 0
    x = netlist.ANTENNA_KEEPOUT_X + EDGE_MARGIN
    while x < netlist.BOARD_W - EDGE_MARGIN:
        y = EDGE_MARGIN
        while y < netlist.BOARD_H - EDGE_MARGIN:
            pos = at(x, y)
            if is_free(board, pos, r) and far_from_vias(board, pos):
                via(board, pos, gnd, locked=False)
                added += 1
            y += STITCH_PITCH
        x += STITCH_PITCH
    return added


def rf_fence(board, gnd):
    """GND vias along both sides of the RF line, 0.9 mm from its centre."""
    rf = [t for t in board.GetTracks() if t.GetNetname() in ("/GPS_RF_IN", "/ANT_FEED") and t.GetWidth() >= F(0.36)]
    added = 0
    r = F(0.3 + STITCH_CLEARANCE)
    for t in rf:
        a, b = t.GetStart(), t.GetEnd()
        if a.y != b.y:
            continue
        x0, x1 = sorted((a.x, b.x))
        x = x0
        while x <= x1:
            for dy in (-F(0.9), F(0.9)):
                pos = pcbnew.VECTOR2I(x, a.y + dy)
                if is_free(board, pos, r) and far_from_vias(board, pos):
                    via(board, pos, gnd, locked=False)
                    added += 1
            x += F(1.0)
    return added


TARGET_WIDTH = 0.15  # Default net class width; the router necks down near fine-pitch pins


def widen_narrow_tracks(board):
    """Router neck-downs: widen back to the class width wherever the clearance allows it."""
    widened = kept = 0
    for t in board.GetTracks():
        if t.Type() != pcbnew.PCB_TRACE_T or t.GetWidth() >= F(TARGET_WIDTH) - 1:
            continue
        old = t.GetWidth()
        t.SetWidth(F(TARGET_WIDTH))
        if segment_clear(board, t.GetStart(), t.GetEnd(), F(TARGET_WIDTH / 2), t.GetNetCode()):
            widened += 1
        else:
            t.SetWidth(old)
            kept += 1
    return widened, kept


def main():
    board = freeroute()
    widened, kept = widen_narrow_tracks(board)
    print(f"widened {widened} necked-down tracks, {kept} stay narrow")
    gnd = board.FindNet("GND")
    nets = {"GND": gnd}
    add_zone(board, nets, "GND", pcbnew.F_Cu, 0)
    add_zone(board, nets, "GND", pcbnew.B_Cu, 0)
    fence = rf_fence(board, gnd)
    stitched = stitch(board, gnd)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(PCB, board)
    print(f"routed; {fence} RF fence vias, {stitched} stitching vias")


if __name__ == "__main__":
    main()
