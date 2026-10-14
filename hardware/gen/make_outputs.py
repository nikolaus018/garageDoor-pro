"""Writes the JLCPCB order package to hardware/production/ (system Python 3).

Refuses to produce anything unless ERC and DRC are clean (0 errors, 0 warnings).
"""
import csv
import os
import re
import shutil
import subprocess
import sys
import zipfile

import netlist

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.dirname(HERE)
OUT = os.path.join(HW, "production")
SCH = os.path.join(HW, "garageDoor-pro.kicad_sch")
PCB = os.path.join(HW, "garageDoor-pro.kicad_pcb")
CLI = os.path.expanduser("~/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli")

GERBER_LAYERS = ["F.Cu", "In1.Cu", "In2.Cu", "B.Cu", "F.Paste", "B.Paste", "F.Silkscreen", "B.Silkscreen",
                 "F.Mask", "B.Mask", "Edge.Cuts"]

# JLCPCB's part models are not always oriented like KiCad's footprints. These offsets are the
# commonly used corrections (same convention as the JLCPCB KiCad fabrication toolkits); the
# order preview still has to be checked, see hardware/ORDERING.md.
ROTATION_OFFSETS = [
    (r"^Package_TO_SOT_SMD:SOT-23", 180),
    (r"^Package_SO:SOP-4", 270),
    (r"^Diode_SMD:D_SOD-123", 180),
]


def run(args, **kw):
    print("$", " ".join(os.path.basename(a) if a == CLI else a for a in args), flush=True)
    return subprocess.run(args, check=True, **kw)


def check_clean():
    erc = os.path.join(OUT, "erc.rpt")
    drc = os.path.join(OUT, "drc.rpt")
    run([CLI, "sch", "erc", "--severity-all", "-o", erc, SCH], stdout=subprocess.DEVNULL)
    run([CLI, "pcb", "drc", "--severity-all", "--schematic-parity", "--refill-zones", "-o", drc, PCB],
        stdout=subprocess.DEVNULL)
    erc_text, drc_text = open(erc).read(), open(drc).read()
    erc_ok = "ERC messages: 0  Errors 0  Warnings 0" in erc_text
    drc_ok = all(s in drc_text for s in ("Found 0 DRC violations", "Found 0 unconnected pads",
                                         "Found 0 Footprint errors"))
    if not (erc_ok and drc_ok):
        sys.exit(f"ERC clean: {erc_ok}, DRC clean: {drc_ok} - see {erc} / {drc}")
    print("ERC and DRC clean", flush=True)


def gerbers():
    gdir = os.path.join(OUT, "gerbers")
    shutil.rmtree(gdir, ignore_errors=True)
    os.makedirs(gdir)
    run([CLI, "pcb", "export", "gerbers", "--layers", ",".join(GERBER_LAYERS), "--subtract-soldermask",
         "--check-zones", "-o", gdir + "/", PCB], stdout=subprocess.DEVNULL)
    run([CLI, "pcb", "export", "drill", "--format", "excellon", "--excellon-separate-th",
         "--excellon-units", "mm", "--generate-map", "--map-format", "pdf", "-o", gdir + "/", PCB],
        stdout=subprocess.DEVNULL)
    zpath = os.path.join(OUT, "garageDoor-pro-gerbers.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for name in sorted(os.listdir(gdir)):
            if not name.endswith(".pdf"):
                z.write(os.path.join(gdir, name), name)
    print("wrote", zpath)


def footprint_ids():
    return {ref: fp for ref, (_v, _s, fp, *_r) in netlist.PARTS.items()}


def bom():
    groups = {}
    for ref, (value, _sym, fp, lcsc, mpn, desc) in netlist.PARTS.items():
        groups.setdefault((value, fp.split(":")[1], lcsc, mpn), []).append(ref)
    path = os.path.join(OUT, "bom-jlcpcb.csv")
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #", "Manufacturer Part", "Quantity"])
        for (value, fp, lcsc, mpn), refs in sorted(groups.items(), key=lambda g: natural(g[1][0])):
            refs.sort(key=natural)
            w.writerow([value, ",".join(refs), fp, lcsc, mpn, len(refs)])
    print("wrote", path)


LCSC_BOARDS = 3  # parts for this many boards in bom-lcsc.csv (self-assembly)


def bom_lcsc():
    """Upload at lcsc.com -> BOM tool; it rounds up to each part's minimum order quantity."""
    qty = {}
    for ref, (_v, _s, _fp, lcsc, mpn, _d) in netlist.PARTS.items():
        qty.setdefault((lcsc, mpn), 0)
        qty[(lcsc, mpn)] += 1
    path = os.path.join(OUT, "bom-lcsc.csv")
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["LCSC Part Number", "Manufacture Part Number", "Quantity"])
        for (lcsc, mpn), n in sorted(qty.items()):
            w.writerow([lcsc, mpn, n * LCSC_BOARDS])
    print("wrote", path)


def natural(ref):
    m = re.match(r"([A-Z]+)(\d+)", ref)
    return (m.group(1), int(m.group(2)))


def cpl():
    raw = os.path.join(OUT, "pos-kicad.csv")
    run([CLI, "pcb", "export", "pos", "--format", "csv", "--units", "mm", "--side", "both", "-o", raw, PCB],
        stdout=subprocess.DEVNULL)
    fps = footprint_ids()
    path = os.path.join(OUT, "cpl-jlcpcb.csv")
    with open(raw) as fin, open(path, "w", newline="") as fout:
        w = csv.writer(fout)
        w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        for row in csv.DictReader(fin):
            ref = row["Ref"]
            if ref not in fps:
                continue  # test pads, mounting holes
            rot = float(row["Rot"])
            for pattern, offset in ROTATION_OFFSETS:
                if re.search(pattern, fps[ref]):
                    rot += offset
            rot %= 360
            side = "Top" if row["Side"].lower() == "top" else "Bottom"
            w.writerow([ref, f"{float(row['PosX']):.4f}mm", f"{float(row['PosY']):.4f}mm", side, f"{rot:g}"])
    os.remove(raw)
    print("wrote", path)


def docs():
    run([CLI, "sch", "export", "pdf", "-o", os.path.join(OUT, "schematic.pdf"), SCH], stdout=subprocess.DEVNULL)
    run([CLI, "pcb", "export", "pdf", "--layers", "F.Fab,F.Silkscreen,Edge.Cuts", "--mode-single",
         "-o", os.path.join(OUT, "assembly-top.pdf"), PCB], stdout=subprocess.DEVNULL)
    for side in ("top", "bottom"):
        run([CLI, "pcb", "render", "--side", side, "--quality", "high", "--width", "1600", "--height", "900",
             "--background", "opaque", "-o", os.path.join(OUT, f"render-{side}.png"), PCB],
            stdout=subprocess.DEVNULL)
    run([CLI, "pcb", "render", "--rotate", "-40,0,30", "--perspective", "--quality", "high", "--width", "1600",
         "--height", "900", "--background", "opaque", "-o", os.path.join(OUT, "render-iso.png"), PCB],
        stdout=subprocess.DEVNULL)
    run([CLI, "pcb", "export", "step", "--force", "-o", os.path.join(OUT, "garageDoor-pro.step"), PCB],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    check_clean()
    gerbers()
    bom()
    bom_lcsc()
    cpl()
    docs()
