# Prototype build (perfboard)

The garageDoor board, built by hand from ready-made modules on a perfboard. It runs the same firmware
as the PCB version, and the build takes about an hour.

```
                ESP32-C3 SuperMini
car USB-C ────► USB-C
                3V3   ────────────────────────────────────► GPS VCC
                GND   ────────────────────────────────────► GPS GND
                GPIO5 ◄──────────────────────────────────── GPS TX
                GPIO4 ────────────────────────────────────► GPS RX

                GPIO7 ──┬── R1 330Ω ──┬── 1 ┌──────────┐ 4 ──► screw 1 ─┐  across the
                        │             │     │    K1    │  (C)   (+ side)├─ remote's
                     R3 1k       R2 100k    │  PC817C  │                │  button
                        │             │     │  opto-   │                │
                  D1 red LED          │     │ coupler  │  (E)   (− side)│
                        │             │     │          │                │
                GND  ───┴─────────────┴── 2 └──────────┘ 3 ──► screw 2 ─┘
                GPIO8: blue LED on the SuperMini (status)   GPIO9: BOOT button (= SETUP)
```

![what connects to what](img/wiring.svg)

- **R1** sets the optocoupler's LED current (~6 mA).
- **R2** keeps the switch off while the ESP32 boots.
- **R3 and D1:** the red LED lights whenever the board presses the remote. If it flashes and the
  remote doesn't react, the problem is on the remote side of K1.
- **The PC817C** connects the two screw-terminal wires like a pressed button, and it's fully
  isolated from the rest of the board. Unpowered, it stays open. Its output is a transistor, so
  **polarity matters**: terminal 1 goes to the button's **+ side**, terminal 2 to the **− side**
  (see Bench test). It switches up to ~10–20 mA, plenty for a remote's button that only signals
  the remote's chip. Some remotes' buttons switch the whole remote on instead; see
  [If the remote doesn't react](#if-the-remote-doesnt-react).

## Parts list

| # | Part | Qty | Notes | ~€ |
|---|------|----:|-------|---:|
| 1 | **ESP32-C3 SuperMini** | 2 | Get the **standard** one, not "SuperMini **Plus**": the Plus has different pins and an RGB LED on GPIO8. The second one is a spare. | 3 each |
| 2 | **GPS module with UART that runs on 3.3 V**, e.g. **ATGM336H** or **GY-NEO6MV2**, with its antenna | 1 | Powered from the SuperMini's **3V3** pin (most of these modules are 2.7–3.6 V only; boards with their own regulator work on 3.3 V too). The firmware finds the baud rate itself and reads NMEA (ATGM336H, NEO-6M, ...) or u-blox UBX. A module that needs 5 V (e.g. Beitian BE-220) does **not** fit this layout. | 12–18 |
| 3 | **PC817C** optocoupler, DIP-4 | 2 | K1. Sold in cheap packs; the second one is a spare. Must be the **4-pin** through-hole version (PC827/PC847 are 8/16 pins; "PC817C SMD"/"S" types don't fit). | 0.1–0.5 |
| 4 | Resistor 330 Ω, ¼ W | 1 | R1. A resistor assortment kit is handy. | – |
| 5 | Resistor 100 kΩ, ¼ W | 1 | R2 | – |
| 6 | Resistor 1 kΩ, ¼ W | 1 | R3 | – |
| 7 | LED red, **3 mm** | 1 | D1. A 5 mm LED doesn't fit between R2 and the board edge. | 0.1 |
| 8 | Screw terminal, 2-pin, 5.08 mm pitch, e.g. KF301-2P | 1 | J1, for the remote wires. 5.0 mm pitch fits too; 3.5 / 3.81 mm don't. | 0.3 |
| 9 | Perfboard **4 × 6 cm**, 2.54 mm, double-sided with plated holes, **20 × 14 holes**, numbers 1–20 and letters A–N printed on it | 1 | The guide uses its printed hole names. Check the print direction before you start (Layout). Packs of several are cheap. | 1 |
| 10 | Female pin header 1×8, 2.54 mm | 2 | The SuperMini plugs in, so it can be swapped and wires fit underneath | 0.5 |
| 11 | Male pin header 1×4, 2.54 mm | 1 | GPS connector at M2–M5 | 0.2 |
| 12 | 4 female–female Dupont jumper wires, 20–30 cm | 4 | Board header to the GPS module's pins | 1 |
| 13 | Insulated hookup wire, 26–30 AWG (silicone or wire-wrap) | 1 m | W1, W2, and the remote wires | 2 |
| 14 | Bare tinned copper wire, 0.4–0.6 mm | – | Trails T1–T10; the resistor leg offcuts are enough | – |
| 15 | **Spare garage remote** for your door, already working | 1 | It stays in use as the transmitter | own / 15–30 |
| 16 | USB car charger + USB-C cable | 1 | On a socket that **switches off with the ignition**. Some SuperMini clones lack the USB-C resistors that a C-to-C cable needs and get no power from a USB-C charger (or a USB-C-only Mac): if it shows no sign of life (no LED at all, no `/dev/cu.usbmodem…` port on the Mac), use a **USB-A charger with an A-to-C cable** (and a USB-A hub or adapter on the Mac). | 10 |
| 17 | Small enclosure (e.g. 70 × 50 × 25 mm) | 1 | Or 3D-print one | 3 |
| 18 | Heat-shrink tubing, double-sided tape / Velcro | – | | – |

Tools: temperature-controlled soldering iron (~330 °C, fine tip), solder 0.5–0.8 mm (leaded Sn60/63
is the easiest), flux pen, flush cutters, tweezers, multimeter with continuity beep.

**Total:** about €25–35 without the remote and charger. The GPS module is the biggest item.

## Layout

![perfboard layout, top and bottom view](img/layout.svg)

The guide is drawn for the green **40 × 60 mm** perfboard (20 × 14 holes) that has `40*60MM`, the
numbers **1–20** and the letters **A–N** printed on one side. Every hole is named by that print: **printed letter + printed
number**, e.g. C11 = row C, column 11.

- **Check the print direction first.** Hold the board printed side up with `40*60MM` at the top and
  the numbers along the bottom, **1 on the left**. The letters must run up the left edge with **A at
  the bottom**.
  - If A is at the **top** instead, stop: on that board the hole names come out mirrored, and the
    SuperMini would end up with its pins swapped. Use a board printed the other way, or ask for the
    layout to be mirrored first.
- **Parts go on the printed side.** That's the left half of the drawing, and the SuperMini sits
  there **chip side up with USB-C on the left**.
- **Soldering happens on the other side.** Turn the board over like a page: the SuperMini's USB-C
  end is now on the **right**, the screw terminal on the left. That's the right half of the drawing.
  That side has **no print at all**, so the drawing shows none either: dashed outlines mark where
  the parts sit on the other side, and every solder joint is labelled (SuperMini pin names, GPS
  pins, K1 pins 1–4, J1 screws 1/2, D1+ / D1−). The trails and wires below are described by those
  joints.
- The circuit uses rows **A–M** and columns **1–18**. Row N and columns 19–20 stay empty.

`make_layout.py` draws all the pictures in `img/` and checks that the trails and wires produce
exactly the circuit above.

### Bridge, trail or wire?

| Connection | Use | Here |
|------------|-----|------|
| Two **neighbouring** holes (one step) | a short trail, or a **solder bridge**: heat both pads and feed solder until it flows across | T3, T9, T10, and the first step of T8 |
| A **straight run** over 2+ neighbouring holes | a **trail**: bare tinned wire laid flat over the pads, soldered at **every** pad. Don't chain solder blobs; they crack. | T1, T2, T4–T8 |
| Anything else (long runs, crossing other connections, under the SuperMini) | **insulated wire**, soldered pad to pad on the bottom | W1, W2 |

Keep trails centred on their row. A trail must never touch the pad beside it, so watch the parallel
trails T5/T6/T7 (three side by side: GND, 3V3, GPIO4) and T4/T8 (the two terminal wires).
Leave every hole that isn't in the drawing unsoldered.

## Assembly

1. **Check the SuperMini.** The pin labels should read `5V G 3.3 4 3 2 1 0` on one side and
   `5 6 7 8 9 10 20 21` on the other. Hold it **chip and buttons facing up, USB-C on the left**:
   then `5V … 0` is the upper row and `5 … 21` the lower one, and that's how it goes onto the
   board. If its male pins came loose, solder them on now (long side down).
2. **Headers.** Board **printed side up**, 1 on the left, A at the bottom (Layout). Plug both 1×8
   female headers onto the SuperMini and set it in chip side up, USB-C toward the left edge: the
   `5V … 0` row in **K2–K9** (5V in K2) and the `5 … 21` row in **E2–E9** (5 in E2).
   - The rows are 6 holes (15.24 mm) apart on the SuperMini. If yours don't line up with K and E,
     stop and measure.
   - Solder **all 16** header pins from the bottom, then pull the SuperMini off again. The unused
     ones hold the module in place.
   - **No female headers?** Solder the SuperMini in directly with the male pins it came with: pins
     long side down through K2–K9 and E2–E9, SuperMini on top (check the orientation twice), solder
     on top, then from the bottom, and trim the long ends flush underneath. Test-fit a USB-C cable
     before going on: the module now sits only about 2.5 mm above the board.
   - **1×4 male header:** M2–M5 (the GPS connector), short pins through the board.

   ![step 1: headers](img/step1.svg)
3. **Parts on the printed side** (solder from the bottom, and keep the cut-off legs for the trails):
   - **R1 330 Ω:** C4 and C9, lying flat.
   - **R2 100 kΩ:** C10 and B10, standing upright with the body on C10 (bend the B10 leg down
     alongside the body).
   - **R3 1 kΩ:** A4 and A8, lying flat along the bottom edge.
   - **D1 red LED:** **long leg (+) in A9**, short leg (the flat side of the rim, −) in A10.
   - **K1 PC817C:** **pin 1 (dot or notch) in C11**. The pins then go to C11, B11, B14 and C14.
   - **J1 screw terminal:** D18 (screw 1) and B18 (screw 2), with the wire openings toward the
     right edge.

   ![step 2: parts on top](img/step2.svg)
4. **Trails on the bottom** (board turned over like a page: no print, USB-C end on the right).
   Hole names in brackets are the printed ones from the parts side, for cross-checking:
   - **T1:** SuperMini pin 7 → R1 → R3, straight down 4 pads (E4–D4–C4–B4–A4). B4 has no part, the
     trail just passes it.
   - **T2:** R1's other leg → R2's upper leg → K1 pin 1, 3 pads in a row (C9–C10–C11).
   - **T3:** R2's lower leg → K1 pin 2, neighbours (B10–B11).
   - **T4:** K1 pin 3 → J1 screw 2, 5 pads along the row (B14–B18).
   - **T5:** SuperMini 3V3 → GPS VCC, straight, 3 pads (K4–L4–M4).
   - **T6:** SuperMini G → GPS GND (K3–L3–M3).
   - **T7:** SuperMini pin 4 → GPS RX (K5–L5–M5).
   - **T8:** K1 pin 4 → J1 screw 1. Bridge K1 pin 4 one step **away from pin 3** (C14–D14), then a
     trail along that row to screw 1 (D14–D18). K1 pin 1 is in the same row as pin 4, three holes
     along: nothing on the output side goes there.
   - **T9:** R3's leg next to the LED → D1+, neighbours (A8–A9).
   - **T10:** D1− → R2's lower leg, neighbours (A10–B10). R2's lower leg is GND.

   ![step 3: trails underneath](img/step3.svg)
5. **Wires on the bottom:**
   - **W1:** GPS TX → SuperMini pin 5 (M2 → E2).
   - **W2:** the middle pad of T6 → K1 pin 2 (L3 → B11).

   ![step 4: wires underneath](img/step4.svg)
6. **Measure before plugging anything in** (multimeter, SuperMini unplugged or, if soldered in, the
   USB cable out). The pads go through the board, so measure on the printed side, where you can read
   the names. With the SuperMini soldered in, the "open" checks between its pins may show a high
   resistance through the module instead of nothing; only a beep is a fault:

   | Between | Expect |
   |---------|--------|
   | K4 (3V3) and K3 (GND) | **open, no beep**. If this beeps, find the short before going on. |
   | K2 (5V) and K3 (GND) | open |
   | K4 and M4, K3 and M3, K5 and M5, E2 and M2 | beep (connected) |
   | E4 (GPIO7) and A4 (R3) | beep |
   | E4 (GPIO7) and C11 (K1 pin 1) | ~330 Ω |
   | C11 and K3 (GND) | ~100 kΩ (some meters show less: their test voltage lights K1's LED) |
   | B11 and K3, A10 and K3 | beep |
   | A8 and A9 | beep |
   | Screw 1 and C14 / screw 2 and B14 | beep |
   | Screw 1 and screw 2 | open |
   | Screw 1 and C11, screw 1 and E4, screw 1 and K3, screw 2 and K3 | **open**: the terminal side must not touch anything but K1 pins 3 and 4 |
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

Careful near the real door: once home is set and the board last stopped at home, **every power-up
presses the remote 10 times** (that's "leaving"). Test away from the door or with the remote's
battery out until the wiring is proven.

1. **First start:** the log says `start: NO_HOME` and the blue LED blinks fast, because the setup
   Wi-Fi is on.
2. **GPS:** near a window, the log shows `receiver found at 9600 baud (NMEA)` (ATGM336H, NEO-6M; u-blox M9/M10
   modules show `115200 baud (UBX)`). Within about a minute the panel shows a fix.
3. **Switch:** on the phone, join **GarageDoor-XXXX** (open, no password), then tap **Press the
   remote once**. **The red LED D1 flashes.**
   - No flash: GPIO7 isn't reaching R3/D1. Check T1 and that D1's long leg is in A9.
   - Then, remote not connected yet: multimeter on Ω, red probe on screw 1, black on screw 2, and
     tap **Hold the remote for 5 s**. D1 stays lit and the meter drops from open to a low reading
     (typically under 1 kΩ) for 5 s. Still open: the PC817C isn't switching; check T2, T3, W2
     and that its dot is in C11.
4. **Remote, on its own first:** open the spare remote and solder two thin wires across the
   button's contacts (the two sides it connects). Keep them short and away from the remote's
   antenna (the copper loop or wire near its edge). Touch the two free wire ends together: the
   remote must transmit (its LED lights, the door reacts).
   - Nothing happens: the problem is the wires or joints on the remote. Fix that first; the board
     can't do better than a pressed button.
5. **Remote on the board:** find the button's **+ side**: battery in, multimeter on DC volts across
   the two button contacts. If it reads positive, the red probe is on the + side; if negative, the
   black one is. **+ side → J1 screw 1, − side → screw 2.** Tap **Press the remote once**: D1
   flashes, the remote's LED lights and the door reacts.

## If the remote doesn't react

D1 flashes, the remote works on its own (Bench test step 4), but pressing through the board does
nothing:

1. Check the wires in J1 and the measurements above (screw 1 ↔ C14, screw 2 ↔ B14). Tap **Hold
   the remote for 5 s** and watch the remote's LED: it should stay lit for the whole 5 s.
2. Swap the two remote wires in J1 once. The PC817C only conducts from screw 1 to screw 2.
3. Still nothing: this remote's button carries more current than the PC817C can switch (many cheap
   433 MHz remotes switch their battery on with the button). A **PhotoMOS relay** (AQY212EH,
   TLP222A or G3VM-61A1, DIP-4) goes into the same four holes, pin 1 in C11, and works either way
   round.

## Install in the car

- **Board:** put it in the enclosure and mount it out of direct sun (console, glovebox).
  - Wi-Fi is only used for setup, with the phone right next to it, so the board's position doesn't
    matter for range.
  - Still, don't put the SuperMini's antenna end (opposite the USB-C) against metal.
- **GPS module:** put it (or its antenna) where it sees the sky, e.g. on the dashboard under the
  windscreen, ceramic side up, and run the cable to the box.
- **Power:** USB-C from the ignition-switched charger.
- **Setup:** follow `docs/user-guide.md` from "Set it up".
