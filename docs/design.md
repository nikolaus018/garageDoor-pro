# garageDoor-pro: design

One small board that lives in the car and opens the garage door on its own: when you leave
home and when you arrive. No phone, no app. Successor to the legacy setup in
`~/Documents/garageDoor` (tag `legacy-v1`: car ESP32 + BLE + iOS Shortcuts).

## Behaviour

The board is powered from a car USB socket that switches off with the ignition, so it boots
when the car starts and dies when it stops. The underground garage has no GPS reception, so
the board remembers in flash where it was last parked.

```
boot, parked HOME   -> LEAVING:  press 10x (every 2 s), then wait until GPS shows we left
                                 the zone (> leave radius)            -> save AWAY
boot, parked AWAY   -> AWAY:     wait for GPS
GPS inside arrive radius while AWAY
                    -> ARRIVING: save HOME, press every 2 s for up to 3 min
```

- Two radii (hysteresis) so GPS jitter at the edge doesn't flap: arrive at about 150 m, leave at about 300 m.
  Both are configurable.
- First boot (nothing saved) counts as HOME.
- Extra presses while the door moves just keep it open longer (checked on the real door).
- Compared with legacy: it only presses on start when the car was parked at home, and arrival
  detection needs no phone.

## Web panel

- Hold the button for 3 s: the board opens a WPA2 Wi-Fi network `GarageDoor-XXXX` for 10 minutes.
  The status LED blinks while it's open. Connect your phone and open `http://192.168.4.1`
  (a captive portal opens it automatically).
- **Set home to where the car is now**: park at home, tap the button, and the board stores its
  current GPS fix. Coordinates can also be typed in by hand.
  - It can't use the phone's location, because browsers only allow that on HTTPS pages.
  - It can't show a map, because the phone has no internet while it's on the board's network.
- Settings: arrive/leave radius, number of presses on leaving, arrival press duration,
  Wi-Fi password.
- Live status: GPS fix and satellites, distance to home, current state (HOME/AWAY/...), and a
  **Test press** button.
- Firmware update by uploading a `.bin` file (OTA).
- Wi-Fi is off the rest of the time, which also keeps 2.4 GHz noise away from the GPS.

## Block diagram

```
USB-C ──► PTC fuse ─► TVS ─► AP2112K-3.3 ──► 3V3
  │ CC1/CC2: 5.1 kΩ to GND (so C-to-C car chargers supply 5 V)
  └ D+/D− ─► USBLC6-2 ─► ESP32-C3 native USB (power, flashing, logs)

ESP32-C3-MINI-1-H4X
  ├ UART1 ◄──► MAX-M10S GPS ◄── bias-T ◄── U.FL ◄── active GNSS antenna (3.3 V type)
  ├ GPIO ──► AQY212GS PhotoMOS ──► 2-pin screw terminal ──► spare garage remote's button
  ├ GPIO ──► status LED, press LED
  └ GPIO9 ◄─ button (BOOT when held at reset, SETUP at runtime)
```

## Parts

LCSC stock and prices were checked live on 2026-10-14. "Ext" means a JLCPCB extended part,
which adds a small one-off loading fee per order.

| Ref | Function | Part | LCSC | Stock | ≈ $/pc | Temp |
|-----|----------|------|------|------:|-------:|------|
| U1 | MCU, Wi-Fi/BLE, PCB antenna | Espressif ESP32-C3-MINI-1-H4X (Ext) | C41349510 | 1,411 | 2.98 | −40…105 °C |
| U2 | GNSS receiver | u-blox MAX-M10S-00B (Ext) | C4153167 | 1,064 | 10.94 | −40…85 °C |
| U3 | 3.3 V LDO, 600 mA | Diodes AP2112K-3.3TRG1 | C51118 | 13,425 | 0.17 | −40…85 °C |
| U4 | USB ESD protection | ST USBLC6-2SC6 | C7519 | 28,430 | 0.18 | −40…125 °C |
| K1 | Isolated switch output, 60 V / 1 A, either polarity | Panasonic AQY212GS PhotoMOS, SOP-4 (Ext) | C719745 | 389 | 1.17 | −40…85 °C |
| K1 alt | Same footprint and pinout | Toshiba TLP172A(TP,F) | C99477 | 2,194 | 1.64 | −40…85 °C |
| J1 | Power/data | USB-C receptacle 16-pin, TYPE-C-31-M-12 (Ext) | C165948 | 366,450 | 0.19 | |
| J2 | GNSS antenna | Hirose U.FL-R-SMT-1(10) (Ext) | C88373 | 24,160 | 0.23 | −40…90 °C |
| J3 | Remote wires | KEFA KF128-5.08-2P screw terminal, 0.2–2.5 mm² (Ext, THT) | C474952 | 57,780 | 0.19 | −40…105 °C |
| L1 | Antenna bias-T, 27 nH, >500 Ω @ L1, ≥300 mA | Murata LQW15A/LQG15H series, 0402 | at schematic | | | |
| F1, D1 | VBUS polyfuse ~500 mA hold, 5 V TVS | at schematic (basic parts preferred) | | | | |
| — | Resistors, capacitors, LEDs, tactile switch | JLCPCB basic parts | at schematic | | | |

Expected BOM: about 18–20 $ per board at prototype quantities. The GPS module is more than half of it.

Not used, on purpose:
- **No V_BCKP backup supercap.** Typical SMD supercaps are rated to only 60 °C, which a parked car
  exceeds. Leaving uses the saved state, and on arrival the GPS has been running for the whole
  drive. A cold start takes about 25–30 s, which matters only on very short trips. Per the u-blox
  manual, V_BCKP is **left open**.
- **No on-board GPS antenna.** The board will sit behind a dashboard or in a console. A cheap
  magnetic active antenna on the dashboard or under the windscreen receives far better.

## Circuit notes

**Power**
- USB-C: CC1 and CC2 each get 5.1 kΩ to GND, so USB-C-to-C chargers turn on 5 V.
- VBUS goes through the polyfuse, then the 5 V TVS, then the AP2112K (10 µF in, 10 µF out).
- Budget: ESP32-C3 Wi-Fi TX peaks around 350 mA, GPS about 25 mA plus the antenna about 10 mA,
  PhotoMOS LED about 6 mA. The 600 mA LDO has headroom. LDO loss in normal operation
  (Wi-Fi off) is about (5 − 3.3) V × 60 mA ≈ 0.1 W.

**ESP32-C3-MINI-1-H4X** (Espressif hardware design guidelines)
- EN: 10 kΩ pull-up and 1 µF to GND (power-on reset delay).
- Strapping pins: GPIO2 and GPIO8 get 10 kΩ pull-ups, GPIO9 a 10 kΩ pull-up plus the button to GND.
- USB D− and D+ (GPIO18/19) go straight to the USB-C pins through the USBLC6. No USB-serial chip
  and no auto-reset circuit are needed, because esptool resets the chip through USB.
- PCB antenna at a board edge with the keep-out area from the datasheet: **no copper on any layer
  under or beside it**. That's the lesson from the legacy beacon on perfboard.

**MAX-M10S** (integration manual UBX-20053088 R05)
- VCC and V_IO tied to 3V3 (option 1, 3.3 V design), 10 µF + 100 nF at the pins. No series
  resistance above 0.2 Ω.
- VIO_SEL open (3.3 V), V_BCKP open, LNA_EN not connected, SDA/SCL open.
- RESET_N to an ESP GPIO driven open-drain (low ≥ 1 ms resets the module).
- SAFEBOOT_N to a test pad only (recovery).
- TXD/RXD to ESP UART1. The module defaults to 9600 baud; the firmware raises it.
  UART0 (GPIO20/21) is not used for the GPS, because the ESP ROM prints boot messages on it.
- Active antenna bias-T (manual Figure 28 and appendix C): VCC_RF → R 10 Ω (0.25 W) → L 27 nH → RF
  line, with C 10 nF X7R from the R/L node to GND, plus a 47 pF C0G DC block in the RF line.
- RF_IN to U.FL: 50 Ω grounded coplanar waveguide, as short as possible, with ground vias along both sides.

**Switch output**
- GPIO drives the AQY212GS LED through 330 Ω (about 6 mA), with 100 kΩ pull-down so it stays off
  during boot.
- The same GPIO drives a red "pressing" LED through 1 kΩ.
- The output side goes to the screw terminal and is fully isolated, so polarity doesn't matter.
  Unpowered, the switch is open.

**Status**: one green LED (heartbeat / setup mode / GPS fix blink codes).

## Pin assignment (ESP32-C3)

| GPIO | Use | Notes |
|------|-----|-------|
| 4 | UART1 TX → GPS RXD | |
| 5 | UART1 RX ← GPS TXD | |
| 6 | GPS RESET_N | open-drain |
| 7 | Switch (PhotoMOS + press LED) | 100 kΩ pull-down |
| 10 | Status LED | |
| 9 | Button: BOOT / SETUP | 10 kΩ pull-up, strapping |
| 2, 8 | not used | 10 kΩ pull-ups, strapping |
| 18, 19 | USB D−, D+ | native USB Serial/JTAG |
| 0, 1, 3, 20, 21 | spare | to test pads |

## PCB

- 4 layers (signal, GND, 3V3, signal). With a solid ground plane right under the top layer, 50 Ω
  RF lines and good GPS performance are easy, and JLCPCB's 4-layer prototypes cost about the same
  as 2-layer.
- About 50 × 30 mm. ESP antenna overhangs one short edge; USB-C and screw terminal on the
  opposite edge; U.FL next to the GPS module, away from the ESP antenna.
- 2 × M2.5 mounting holes. Test pads for 3V3, GND, SAFEBOOT_N and spare GPIOs.
- Assembly: JLCPCB SMT on the top side only, plus the screw terminal (THT).

## Environment

Every active part is rated for at least −40…85 °C, and the ESP module to 105 °C. Mount the board out of
direct sun: in a console or glovebox, not on top of the dashboard. Only the antenna needs sky view.

## Firmware outline (ESP-IDF v6.1, target esp32c3)

- GPS: UBX protocol (NAV-PVT at 1 Hz) at 115200 baud, configured on every boot.
  Use a fix only when it is 3D, hAcc < 50 m and at least 5 satellites are used.
- State machine as above, NVS for state and settings, distance by haversine.
- Wi-Fi SoftAP + captive portal + `esp_http_server` with a small embedded HTML/JS page.
- OTA: the panel uploads a `.bin`, written with the `esp_ota_*` API into a second app partition
  (rollback if the new image doesn't boot).
- Logs over the native USB console.

## Next steps

1. Schematic in KiCad 10, ERC clean (kicad-cli).
2. PCB layout, DRC clean, JLCPCB fab and assembly files (Gerbers, BOM, CPL).
3. Firmware, developed against the schematic's pin map.
4. Order 5 assembled boards and an active GNSS antenna (3–5 V, SMA→U.FL pigtail or U.FL cable).
