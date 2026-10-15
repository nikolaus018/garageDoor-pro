# Prototype build (perfboard)

The garageDoor board, built by hand from ready-made modules on a perfboard. It runs the same firmware
as the PCB version, and the build takes about an hour.

```
            ESP32-C3 SuperMini
car USB-C ─► USB-C
            3V3  ───────────────────────────► GPS VCC
            GND  ──────┬────────────┬────────► GPS GND
            GPIO5 ◄────┼────────────┼───────── GPS TX
            GPIO4 ─────┼────────────┼────────► GPS RX
            GPIO7 ── R1 330Ω ──┬── 1 ┌──────────┐ 4 ──► screw terminal 1 ─┐  across the
                               │     │  PC817C  │  (C)   (+ side)        ├─ remote's
                         R2 100k     │ opto-    │                        │  button
                               │     │ coupler  │  (E)   (− side)        │
            GND ───────────────┴── 2 └──────────┘ 3 ──► screw terminal 2 ─┘
            GPIO8: blue LED on the SuperMini (status)   GPIO9: BOOT button (= SETUP)
```

![what connects to what](img/wiring.svg)

- **R1** sets the optocoupler's LED current (~6 mA).
- **R2** keeps the switch off while the ESP32 boots.
- **The PC817C** connects the two screw-terminal wires like a pressed button, and it's fully
  isolated from the rest of the board. Unpowered, it stays open. Its output is a transistor, so
  **polarity matters**: terminal 1 goes to the button's **+ side**, terminal 2 to the **− side**
  (see Bench test). It switches up to ~10–20 mA, plenty for a remote's button, which only signals
  the remote's chip. If a remote's button carries the transmitter's whole current instead, use a
  PhotoMOS relay (AQY212EH, TLP222A, G3VM-61A1: same DIP-4 holes, any polarity).

## Parts list

| # | Part | Qty | Notes | ~€ |
|---|------|----:|-------|---:|
| 1 | **ESP32-C3 SuperMini** | 2 | Get the **standard** one, not "SuperMini **Plus**": the Plus has different pins and an RGB LED on GPIO8. The second one is a spare. | 3 each |
| 2 | **GPS module with UART that runs on 3.3 V**, e.g. **ATGM336H** or **GY-NEO6MV2**, with its antenna | 1 | Powered from the SuperMini's **3V3** pin (most of these modules are 2.7–3.6 V only; boards with their own regulator work on 3.3 V too). The firmware finds the baud rate itself and reads NMEA (ATGM336H, NEO-6M, ...) or u-blox UBX. A module that needs 5 V (e.g. Beitian BE-220) does **not** fit this layout. | 12–18 |
| 3 | **PC817C** optocoupler, DIP-4 | 2 | Sold in cheap packs; the second one is a spare. Must be the **4-pin** through-hole version (PC827/PC847 are 8/16 pins; "PC817C SMD"/"S" types don't fit). A PhotoMOS relay (AQY212EH, TLP222A) fits the same holes and works either way round. | 0.1–0.5 |
| 4 | Resistor 330 Ω, ¼ W | 1 | R1. A resistor assortment kit is handy. | – |
| 5 | Resistor 100 kΩ, ¼ W | 1 | R2 | – |
| 6 | Screw terminal, 2-pin, 5.08 mm pitch, e.g. KF301-2P | 1 | J1, for the remote wires. 5.0 mm pitch fits too; 3.5 / 3.81 mm don't. | 0.3 |
| 7 | Perfboard 5 × 7 cm, 2.54 mm, double-sided with plated holes, the common green one with `50*70MM`, letters A–R and numbers 1–24 printed on it | 1 | The guide uses its printed hole names. Packs of several are cheap | 1 |
| 8 | Female pin header 1×8, 2.54 mm | 2 | The SuperMini plugs in, so it can be swapped and wires fit underneath | 0.5 |
| 9 | Male pin header 1×4, 2.54 mm | 1 | GPS connector at M2–M5 | 0.2 |
| 10 | 4 female–female Dupont jumper wires, 20–30 cm | 4 | Board header to the GPS module's pins | 1 |
| 11 | Insulated hookup wire, 26–30 AWG (silicone or wire-wrap) | 1 m | W1–W3, and the remote wires | 2 |
| 12 | Bare tinned copper wire, 0.4–0.6 mm | – | Trails T1–T7; the resistor leg offcuts are enough | – |
| 13 | **Spare garage remote** for your door, already working | 1 | It stays in use as the transmitter | own / 15–30 |
| 14 | USB car charger + USB-C cable | 1 | On a socket that **switches off with the ignition** | 10 |
| 15 | Small enclosure (e.g. 70 × 50 × 25 mm) | 1 | Or 3D-print one | 3 |
| 16 | Heat-shrink tubing, double-sided tape / Velcro | – | | – |

Tools: temperature-controlled soldering iron (~330 °C, fine tip), solder 0.5–0.8 mm (leaded Sn60/63
is the easiest), flux pen, flush cutters, tweezers, multimeter with continuity beep.

**Total:** about €25–35 without the remote and charger. The GPS module is the biggest item.

## Layout

![perfboard layout, top and bottom view](img/layout.svg)

The guide is drawn for the common green **50 × 70 mm** perfboard (24 × 18 holes) that has
`50*70MM`, the letters **A–R** and the numbers **1–24** printed on one side. Every hole is named by
that print: **printed letter + printed number**, e.g. C11 = row C, column 11.

- **Parts go on the printed side.** Hold it so you can read the print: `50*70MM` at the top, the
  letters up the left edge with **A at the bottom**, the numbers along the bottom edge with **1 on
  the left**. That's the left half of the drawing, and the SuperMini sits there **chip side up with
  USB-C on the left**.
- **Soldering happens on the other side.** Turn the board over like a page: row A stays at the
  bottom, column 1 is now on the **right**. That's the right half of the drawing. There's no print
  on that side (the drawing shows it faded), so find your way by the solder joints of the parts.
- The circuit uses rows **B–M** and columns **1–18**. Row A, rows N–R and columns 19–24 stay empty.

`make_layout.py` draws all the pictures in `img/` and checks that the trails and wires produce
exactly the circuit above.

### Bridge, trail or wire?

| Connection | Use | Here |
|------------|-----|------|
| Two **neighbouring** holes (one step) | a short trail, or a **solder bridge**: heat both pads and feed solder until it flows across | T3 |
| A **straight run** over 2+ neighbouring holes | a **trail**: bare tinned wire laid flat over the pads, soldered at **every** pad. Don't chain solder blobs; they crack. | T1, T2, T4–T7 |
| Anything else (corners, long runs, crossing other connections, under the SuperMini) | **insulated wire**, soldered pad to pad on the bottom | W1, W2, W3 |

Keep trails centred on their row. A trail must never touch the pad beside it, so watch the parallel
trails T5/T6/T7 (three side by side: GND, 3V3, GPIO4). Leave every hole that isn't in the drawing unsoldered.

## Assembly

1. **Check the SuperMini.** The pin labels should read `5V G 3.3 4 3 2 1 0` on one side and
   `5 6 7 8 9 10 20 21` on the other. Hold it **chip and buttons facing up, USB-C on the left**:
   then `5V … 0` is the upper row and `5 … 21` the lower one, and that's how it goes onto the
   board. If its male pins came loose, solder them on now (long side down).
2. **Headers.** Board **printed side up**, print readable (A bottom left). Plug both 1×8 female
   headers onto the SuperMini and set it in chip side up, USB-C toward the left edge: the `5V … 0`
   row in **K2–K9** (5V in K2) and the `5 … 21` row in **E2–E9** (5 in E2).
   - The rows are 6 holes (15.24 mm) apart on the SuperMini. If yours don't line up with K and E,
     stop and measure.
   - Solder the header pins from the bottom, then pull the SuperMini off again.
   - **1×4 male header:** M2–M5 (the GPS connector), short pins through the board.

   ![step 1: headers](img/step1.svg)
3. **Parts on the printed side** (solder from the bottom, and keep the cut-off legs for the trails):
   - **R1 330 Ω:** C4 and C9, lying flat.
   - **R2 100 kΩ:** C10 and B10, standing upright with the body on C10 (bend the B10 leg down
     alongside the body).
   - **K1 PC817C:** **pin 1 (dot or notch) in C11**. The pins then go to C11, B11, B14 and C14.
   - **J1 screw terminal:** D18 (screw 1) and B18 (screw 2), with the wire openings toward the
     right edge.

   ![step 2: parts on top](img/step2.svg)
4. **Trails on the bottom** (board turned over like a page, column 1 on the right): T1 E4–D4–C4,
   T2 C9–C10–C11, T3 B10–B11, T4 B14 → B18 along row B, T5 K4–L4–M4, T6 K3–L3–M3, T7 K5–L5–M5.

   ![step 3: trails underneath](img/step3.svg)
5. **Wires on the bottom:**
   - **W1:** M2 → E2 (GPS TX → GPIO5).
   - **W2:** L3 → B11 (GND → K1 pin 2).
   - **W3:** C14 → D18 (K1 pin 4 → terminal 1).

   ![step 4: wires underneath](img/step4.svg)
6. **Measure before plugging anything in** (multimeter, SuperMini still unplugged):

   | Between | Expect |
   |---------|--------|
   | K4 (3V3) and K3 (GND) | **open, no beep**. If this beeps, find the short before going on. |
   | K2 (5V) and K3 (GND) | open |
   | K4 and M4, K3 and M3, K5 and M5, E2 and M2 | beep (connected) |
   | E4 (GPIO7) and C11 (K1 pin 1) | ~330 Ω |
   | C11 and K3 (GND) | ~100 kΩ (some meters show less: their test voltage lights the optocoupler's LED) |
   | B11 and K3 | beep |
   | Terminal screw 1 and C14 / screw 2 and B14 | beep |
   | Terminal screw 1 and screw 2 | open |
   | Every pair of neighbouring pads in K2–K9, E2–E9 and M2–M5 | open |
7. **GPS.** Connect the module with 4 female–female Dupont jumpers, by the labels **on the module**:
   **TX → M2, GND → M3, VCC → M4, RX → M5**.
   - Check VCC twice: it must go to M4 (3.3 V). Never connect it to the SuperMini's 5V pin.
   - If your module has a cable instead of pins, cut it and solder the jumpers on (wire colours are
     not standard, go by the labels).

   ![step 5: plug in and connect](img/step5.svg)
8. **Plug in the SuperMini** and flash it from the Mac, with the SuperMini on USB:

   ```bash
   cd firmware && . ~/esp/esp-idf/export.sh && idf.py build flash monitor
   ```

   If no `/dev/cu.usbmodem…` port shows up, hold BOOT while plugging in the USB.

## Bench test

1. **First start:** the log says `start: NO_HOME` and the blue LED blinks fast, because the setup
   Wi-Fi is on.
2. **GPS:** near a window, the log shows `receiver found at 9600 baud (NMEA)` (ATGM336H, NEO-6M; u-blox M9/M10
   modules show `115200 baud (UBX)`). Within about a minute the panel shows a fix.
3. **Panel:** on the phone, join **GarageDoor-XXXX** (password `garagedoor`), set your own password,
   then tap **Press the remote once**. A multimeter in continuity mode across the two terminal screws
   beeps briefly (red probe on screw 1: the optocoupler only conducts that way).
4. **Remote:** open the spare remote and solder two thin wires across the button's contacts (the two
   sides it connects).
   - Find the **+ side**: battery in, multimeter on DC volts across the two contacts. If it reads
     positive, the red probe is on the + side; if negative, the black one is.
   - **+ side → J1 screw 1, − side → screw 2.** Test press again: the door reacts.
   - Nothing happens? Swap the two wires once. Still nothing: this remote's button carries more
     current than the PC817C switches, use a PhotoMOS relay (see Parts list).

## Install in the car

- **Board:** put it in the enclosure and mount it out of direct sun (console, glovebox).
  - Wi-Fi is only used for setup, with the phone right next to it, so the board's position doesn't
    matter for range. That was different for the old beacon.
  - Still, don't put the SuperMini's antenna end (opposite the USB-C) against metal.
- **GPS module:** put it (or its antenna) where it sees the sky, e.g. on the dashboard under the
  windscreen, ceramic side up, and run the cable to the box.
- **Power:** USB-C from the ignition-switched charger.
- **Setup:** follow `docs/user-guide.md` from "Set it up".
