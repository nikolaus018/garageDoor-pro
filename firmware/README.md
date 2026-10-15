# garageDoor-pro firmware

ESP-IDF v6.1. One firmware for three boards (menuconfig: garageDoor -> Board, pin maps in
`main/board.h`):

| Board | Build | Status LED / button |
|-------|-------|---------------------|
| **ESP32-C3 SuperMini on perfboard** (the prototype, `prototype/README.md`) | default: `idf.py build` | on-board blue LED (GPIO8) / BOOT (GPIO9) |
| ESP32-S3 DevKitC on perfboard | `idf.py set-target esp32s3 build` | LED + 1 kΩ on GPIO10 / BOOT (GPIO0) |
| garageDoor-pro PCB v1.0 | `idf.py -D SDKCONFIG_DEFAULTS="sdkconfig.defaults;sdkconfig.defaults.pcb-v1" build` | green LED (GPIO10) / SETUP (GPIO9) |

All boards: GPIO4 → GPS RX, GPIO5 ← GPS TX, GPIO7 → remote switch (PhotoMOS on the PCB, PC817C on the perfboard; high = pressed).

## Build, test, flash

```bash
cd firmware && . ~/esp/esp-idf/export.sh && idf.py build
```

```bash
firmware/test/run.sh
```

The second command runs the host unit tests for the hardware-independent parts (UBX and NMEA
parsing, distance, leaving/arriving state machine), with AddressSanitizer and UBSan.

The USB-C on the SuperMini and on the PCB goes straight to the ESP32-C3 (native USB), so flashing
needs no buttons:

```bash
idf.py -p /dev/cu.usbmodem* flash monitor
```

If no `/dev/cu.usbmodem…` port appears: hold BOOT/SETUP while plugging in the USB cable.

`test/mock_panel.py` serves the web panel with a fake board API at http://localhost:8765 for
trying UI changes without hardware.

## Behaviour

| Event | What happens |
|-------|--------------|
| Car starts, last parked **at home** | presses the remote 10× (every 2 s); once GPS shows you are beyond the leave radius (300 m), it saves "away" |
| Car starts, last parked **away** | waits for GPS |
| GPS inside the arrive radius (150 m) while away | saves "home", presses every 2 s for 180 s (until the car switches off) |
| Drove past home without stopping (beyond the leave radius again) | stops pressing, saves "away" |
| Home not set | nothing is pressed; the setup Wi-Fi opens on every start |

Fixes are used only when valid, ≤ 50 m accuracy and ≥ 4 satellites.

GPS: on every boot the firmware sends the u-blox M9/M10 configuration (UBX NAV-PVT 1 Hz, 115200
baud, automotive model, RAM only) at 115200/9600/38400/57600/230400 baud, then listens at each rate
until it finds valid data. Receivers that don't understand UBX keep sending NMEA, and the firmware
then uses their GGA sentences (accuracy estimated from HDOP). So any GPS module with a UART works.
If the data stops for 10 s it searches again; after a full fruitless scan it hardware-resets the
receiver (PCB only, the modules have no reset pin).

## Button and LED

| Button | Effect |
|--------|--------|
| hold 3 s (LED goes solid), release | setup Wi-Fi on for 10 minutes of inactivity |
| hold 10 s (LED flickers), release | factory reset: forget home and settings |

Status LED, one pattern every 3 s: **1 flash** GPS fix, **2** no fix, **3** home not set; fast
blinking = setup Wi-Fi on. PCB only: red LED = the remote is being pressed.

## Web panel

Setup Wi-Fi `GarageDoor-XXXX`, open (no password). Phones open the panel automatically (captive
portal), otherwise go to http://192.168.4.1. It only runs during setup and switches off after 10
minutes without use.

- **Set home to where the car is now** (needs a GPS fix), or enter coordinates
- Arrive / leave radius, presses on leaving, arrival pressing duration
- **Press the remote once** (test)
- Firmware update: upload `build/garageDoor_pro.bin`. The image is verified before it is
  activated; a new image that does not run for 60 s is rolled back by the bootloader.

## Layout

| File | |
|------|---|
| `main/app.c` | startup, glue between GNSS, state machine, presser, LED and web panel |
| `main/trip.c` | leaving / arriving state machine (pure C, unit-tested) |
| `main/ubx.c`, `main/nmea.c`, `main/geo.c` | UBX frames/parser, NMEA GGA parser, distance (pure C, unit-tested) |
| `main/gnss.c` | GPS driver: u-blox configuration, baud-rate search, UBX/NMEA |
| `main/board.h`, `main/Kconfig.projbuild` | pin maps and the board choice |
| `main/presser.c` | remote switch output: 150 ms presses every 2 s |
| `main/settings.c` | NVS: settings and the parked state |
| `main/ui.c` | LED patterns, SETUP button |
| `main/web.c`, `main/www/index.html` | soft AP, captive portal, HTTP API, OTA |
| `components/dns_server` | captive-portal DNS, from the ESP-IDF example (Unlicense / CC0) |
