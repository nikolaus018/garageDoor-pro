# Ordering the board

Two ways: **bare boards + stencil and solder them yourself** (cheapest), or **assembled by JLCPCB**.
Everything needed is in `production/`:

| File | Upload at |
|------|-----------|
| `garageDoor-pro-gerbers.zip` | PCB order: "Add gerber file" |
| `bom-jlcpcb.csv` | PCB Assembly: "BOM" |
| `cpl-jlcpcb.csv` | PCB Assembly: "CPL" (pick and place) |
| `bom-lcsc.csv` | lcsc.com BOM tool: all parts for 3 boards (self-assembly) |

`schematic.pdf`, `assembly-top.pdf` and the `render-*.png` files are for checking and for your records.
`erc.rpt` / `drc.rpt` are the clean electrical and design-rule check reports the files were produced from.

## Self-assembly: bare PCB + stencil

1. Order the PCB with the options in section 1, **without** assembly. In the same order add an
   **SMT stencil**: frameless, **top side only**, **0.12 mm** thick (right for the 0.5 mm-pitch
   USB-C and the 0402 parts). It is cut from the same Gerber zip, no extra file needed.
2. Order the parts from LCSC: upload `bom-lcsc.csv` in LCSC's BOM tool. It rounds every line up to
   the part's minimum order quantity, so cheap passives come in tens or hundreds.
3. Solder (all SMD parts are on the top side):
   - Tape two spare boards around the one you print on, as a level frame, so the stencil lies flat.
     Line the stencil up, put on a line of paste and draw it across once with a card.
   - Place the parts with tweezers, following `assembly-top.pdf` and the orientation notes in
     section 3 below.
   - Reflow on a hot plate (or a preheated board plus hot air). Paste: Sn63Pb37 (183 °C) is the
     easiest by hand, SAC305 (217 °C) if you want lead-free.
   - Afterwards: solder the screw terminal J3 with an iron, then check the USB-C pins under a
     magnifier and clear any bridges with flux and solder wick.
   - Keep the MAX-M10S sealed until use (moisture sensitive), and bake it as its label says if it
     sat open for days.
4. Go through the first power-up checklist (section 5).

## 1. PCB options

| Option | Value | Why |
|--------|-------|-----|
| Layers | **4** | GND and 3.3 V inner planes |
| Dimensions | 60 × 31 mm (read from the Gerbers) | |
| PCB qty | 5 | |
| Thickness | 1.6 mm | |
| Impedance control | **Yes, JLC04161H-7628** | the 0.36 mm GNSS RF trace is ~50 Ω on this stackup |
| Via covering | **Tented** | vias under the ESP32 module and parts must stay covered |
| Surface finish | **ENIG** | flat pads for the ESP32 and GNSS modules (LGA) |
| Min via hole / diameter | 0.3 mm / 0.6 mm (default, no extra cost) | |
| Mark on PCB (order number) | **Specify a location** | placeholder `JLCJLCJLCJLC` on the bottom side |
| Solder mask / silkscreen | any colour | |

## 2. Assembly options (only if JLCPCB assembles)

| Option | Value |
|--------|-------|
| PCBA type | **Standard** (the screw terminal J3 is through-hole) |
| Assembly side | Top |
| PCBA qty | 2 for a first test run, more once it is proven |
| Tooling holes | Added by JLCPCB |
| Confirm parts placement | **Yes** |

Then upload the BOM and CPL. All 25 BOM lines have LCSC part numbers; stock and prices were
checked on 2026-10-14 (GNSS module ~11 $, ESP32-C3 module ~3 $, everything else < 2 $). If a part
is out of stock, pick an equivalent in the BOM step (same value, package and rating; for U1 only
ESP32-C3-MINI-1-**H4X** or **H4**, which are rated to 105 °C).

## 3. Part orientation (check the JLCPCB placement preview, or when placing by hand)

JLCPCB's part models are not always rotated like KiCad's footprints. `cpl-jlcpcb.csv` already
contains the usual corrections, but check every part with a pin 1 or polarity in the 3D/2D
preview before paying. Pin 1 of the part must sit on the pin-1 mark of the footprint:

| Ref | Part | What to check |
|-----|------|---------------|
| U1 | ESP32-C3-MINI-1-H4X | antenna end over the bare copper-free area at the board edge |
| U2 | MAX-M10S | pin 1 in the top-left corner of U2 (toward the USB-C side) |
| U3, U4 | SOT-23-5 / SOT-23-6 | pin 1 dot matches |
| Q1 | SS8050 (SOT-23) | the single pin (collector) on the right, toward the screw terminal |
| J1 | USB-C | receptacle opening at the top board edge |
| J2 | U.FL | centre pin toward C2 |
| D1 | SMF5.0A TVS | cathode band on the right, toward C3 (VIN_5V); anode to GND |
| D2, D3 | LEDs | cathode (pad 1) on the right side of each LED |
| SW1, all R/C/L/F | – | non-polarised, only check they sit on their pads |

If something is off, rotate it in the preview (JLCPCB offers this) and note the change.

## 4. Also buy

- **Active GNSS antenna** with U.FL (IPEX) plug, 3.3–5 V supply, GPS/Galileo L1, 1–3 m cable
  (the board supplies ~3.2 V on the antenna input).
- **A spare remote** for your garage door, the same model as yours, paired with the door.
- **USB car charger** (USB-C or USB-A to C cable) on a socket that is switched off with the ignition.

## 5. First power-up checklist (do this on the bench, per board)

1. Plug USB-C into the Mac. 3V3 test pad (bottom, TP1) reads 3.25–3.35 V.
2. `ls /dev/cu.usbmodem*` shows the board (native USB). Flash it: see `firmware/README.md`.
3. Serial log shows `start: NO_HOME` and the green LED flashes 3× every 3 s; the setup Wi-Fi
   `GarageDoor-XXXX` appears (fast green blinking).
4. Connect the GNSS antenna, put it near a window: within ~1 minute the panel shows a fix.
5. Remote not connected yet: multimeter on Ω across the screw terminal, red probe on **+**, black on
   **−**. It reads open; tap **Hold the remote for 5 s** in the panel and it reads low for 5 s,
   while the red LED is lit.
6. Wire the spare remote: button + side to **+**, − side to **−** (see `docs/user-guide.md`). Tap
   **Press the remote once**: the red LED flashes and the remote transmits.

Only then install it in the car (see `docs/user-guide.md`).

## Regenerating the files

`./build.sh` rebuilds schematic, PCB, routing and this package from `gen/netlist.py`. It needs
KiCad 10 in `~/Applications`, Java (`brew install openjdk`) and Freerouting 2.5
(`~/.local/freerouting/freerouting-2.5.0.jar`). The ESP32-C3-MINI-1 footprint, symbol and 3D model in
`lib/` are from Espressif's official KiCad library (3.2.1). KiCad's own library has no 3D models for
the USB-C receptacle, MAX-M10S and SW1, so they are missing from the renders and the STEP file.
