#!/bin/sh
# Regenerates schematic, PCB (placement, routing, pours) and the JLCPCB order package from
# gen/netlist.py. Needs KiCad 10 in ~/Applications, Java (brew install openjdk) and
# Freerouting 2.5 at ~/.local/freerouting/freerouting-2.5.0.jar (override with $FREEROUTING).
set -e
cd "$(dirname "$0")/gen"
KICAD_PY="$HOME/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3"
quiet() { grep -v -e 'wxApp' -e 'assert' || true; }

python3 make_schematic.py
"$KICAD_PY" make_pcb.py 2>&1 | quiet
"$KICAD_PY" route.py 2>&1 | quiet
python3 make_outputs.py
