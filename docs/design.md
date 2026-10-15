# garageDoor-pro: design

One small board that lives in the car and opens the garage door on its own, when you leave home
and when you arrive. No phone, no app. Successor to the legacy setup in `~/Documents/garageDoor`
(tag `legacy-v1`: car ESP32 + BLE + iOS Shortcuts).

## Behaviour

The board is powered from a car USB socket that switches off with the ignition, so it boots when
the car starts and loses power when it stops. The underground garage has no GPS reception, so the
board remembers in flash where the car was last parked:

```
boot, parked HOME  -> LEAVING:  press 10x (every 2 s); GPS beyond the leave radius -> AWAY (saved)
boot, parked AWAY  -> AWAY:     wait for GPS
AWAY, GPS inside the arrive radius -> ARRIVED: save HOME, press every 2 s for up to 180 s
ARRIVED, GPS beyond the leave radius (drove past) -> AWAY: save, stop pressing
no home set        -> nothing is pressed; setup Wi-Fi opens on every start
```

- Two radii (hysteresis) so GPS jitter at the edge doesn't flap: arrive 150 m, leave 300 m by default.
  Both are configurable, and the leave radius is always at least 50 m larger.
- A fix only counts with gnssFixOK, ≤ 50 m accuracy and ≥ 4 satellites.
- Extra presses while the door moves just keep it open longer (checked on the real door).
- Compared with legacy: it presses on start only when the car was parked at home, arrival needs
  no phone, and driving past home is detected and stops the pressing.

Implementation: `firmware/main/trip.c` (pure C, unit-tested on the host).

## Web panel

- Hold SETUP for 3 s: an open Wi-Fi `GarageDoor-XXXX` (no password) opens until 10 minutes pass
  without use.
  It also opens on every start while no home is set. Phones open the panel automatically
  (captive portal, DHCP option 114), otherwise it is at http://192.168.4.1.
- No Wi-Fi password, by choice: the board sits in the owner's car and the Wi-Fi only runs during
  setup. Anyone within range during those minutes can use the whole panel, firmware upload
  included.
- **Set home to where the car is now** uses the board's own GPS fix, or you type coordinates.
  - It can't use the phone's location, because browsers only allow that on HTTPS pages.
  - It can't show a map, because the phone has no internet while it's on the board's network.
- Settings: arrive/leave radius, presses on leaving, arrival pressing duration.
- Live status, **Press the remote once** and **Hold the remote for 5 s** tests, and a firmware update
  (OTA with rollback).
- Wi-Fi is off otherwise, which keeps 2.4 GHz noise away from the GPS.

## Block diagram

```
USB-C ─► 500 mA polyfuse ─► SMF5.0A TVS ─► AP2112K-3.3 ─► 3V3 (inner plane)
  │ CC1/CC2: 5.1 kΩ to GND (C-to-C chargers supply 5 V)
  └ D+/D− ─► USBLC6-2SC6 ─► ESP32-C3 native USB (power, flashing, logs)

ESP32-C3-MINI-1-H4X
  ├ UART1 (GPIO4/5) ◄──► MAX-M10S ◄── bias-T ◄── U.FL ◄── active GNSS antenna
  ├ GPIO6 ──► MAX-M10S RESET_N (open-drain)
  ├ GPIO7 ──► CPC1017N PhotoMOS ──► 2-pin screw terminal ──► spare remote's button
  │        └► red LED
  ├ GPIO10 ─► green status LED
  └ GPIO9 ◄─ SETUP button (also BOOT strap)
```

## Parts

LCSC stock and prices were checked live on 2026-10-14. The full list with every passive is in
`hardware/production/bom-jlcpcb.csv`.

| Ref | Function | Part | LCSC | Temp |
|-----|----------|------|------|------|
| U1 | MCU, Wi-Fi, PCB antenna | Espressif ESP32-C3-MINI-1-H4X | C41349510 | −40…105 °C |
| U2 | GNSS receiver | u-blox MAX-M10S-00B | C4153167 | −40…85 °C |
| U3 | 3.3 V LDO 600 mA | AP2112K-3.3TRG1 | C51118 | −40…85 °C |
| U4 | USB ESD | USBLC6-2SC6 | C7519 | −40…125 °C |
| K1 | Isolated switch, 60 V / 100 mA, either polarity | Littelfuse CPC1017NTR | C81521 | −40…85 °C |
| J1 | USB-C 16-pin | HRO TYPE-C-31-M-12 | C165948 | |
| J2 | GNSS antenna | Hirose U.FL-R-SMT-1(10) | C88373 | −40…90 °C |
| J3 | Remote wires, 0.2–2.5 mm² | KEFA KF128-5.08-2P screw terminal | C474952 | −40…105 °C |
| F1 / D1 | VBUS protection | SMD1206-050C-6V / SMF5.0A | C22472478 / C1509112 | |
| L1, R1, C1, C2 | Antenna bias-T 27 nH / 10 Ω / 10 nF, 47 pF DC block | Murata LQG15HS27NJ02D, … | C12669, … | |

The parts cost about 18–20 $ per board at prototype quantities, more than half of it the GNSS module.

**Why these parts**
- **CPC1017N instead of the AQY212GS** from the first draft: it has an exact KiCad library footprint,
  23k in stock, and 100 mA is plenty for a remote's button.
- **ESP32-C3-MINI-1 footprint, symbol and 3D model:** from Espressif's official KiCad library 3.2.1,
  which includes the antenna keep-out.
- **No V_BCKP backup supercap:** typical SMD supercaps are rated to only 60 °C. Per the u-blox
  manual, V_BCKP stays open. Cold start takes about 25–30 s, and only matters on very short trips.
- **No on-board GNSS antenna:** an external active antenna on the dashboard receives far better than
  one on a board hidden in the console.

## Circuit notes

- **MAX-M10S** (integration manual UBX-20053088 R05, option 1, 3.3 V)
  - VCC and V_IO on 3V3 with 10 µF + 100 nF. VIO_SEL, V_BCKP, LNA_EN, SDA/SCL and EXTINT are open.
  - TIMEPULSE and SAFEBOOT_N go to test pads.
- **Antenna supply** (manual Figure 28, appendix C): VCC_RF → 10 Ω (1206, 0.25 W) → 27 nH, with
  10 nF to GND, plus a 47 pF C0G DC block before RF_IN.
- **ESP32-C3:** EN has a 10 kΩ pull-up and 1 µF. GPIO2, GPIO8 and GPIO9 have 10 kΩ pull-ups.
  USB goes straight to D−/D+ (GPIO18/19) through the USBLC6.
- **Switch:** GPIO7 → 330 Ω → CPC1017N LED (~6 mA), with a 100 kΩ pull-down so the switch stays open
  during boot. The firmware drives GPIO7 low before anything else.

## PCB

- **Layout:** 60 × 31 mm, 4 layers (F.Cu signal / In1 solid GND / In2 solid 3V3 / B.Cu signal).
  - The ESP32 antenna points out of the left edge, with no copper of any kind left of x = 6.2 mm.
  - USB-C sits on the top edge, the U.FL on the right edge and the screw terminal on the bottom edge.
  - There are 2 × M2.5 mounting holes, and test pads on the bottom.
- **Routing:**
  - The GNSS RF path is hand-routed at 0.36 mm (~50 Ω on JLC04161H-7628) over the GND plane.
  - USB VBUS is also hand-routed.
  - Every GND/3V3 pin is fanned out to its plane by script.
  - The remaining signals are routed with Freerouting on the outer layers only, at 0.15 mm / 0.2 mm
    clearance (≥ 0.11 mm at neck-downs).
  - The outer layers get GND pours and stitching vias.
- **Checks:** ERC 0, DRC 0 violations / 0 unconnected / 0 schematic-parity issues.
- **How it's built:** schematic and PCB are generated from `hardware/gen/netlist.py`, so they cannot
  drift apart.

## Environment

Every part is rated to at least −40…85 °C, and the ESP module to 105 °C. Mount the board out of
direct sun; only the antenna needs sky view.

## Status

The design is complete and checked; the order package is in `hardware/production/`. Before larger
quantities, a first run of assembled boards has to pass the bring-up checklist in
`hardware/ORDERING.md` and a real drive (leave + arrive).
