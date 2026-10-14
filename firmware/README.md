# garageDoor-pro firmware

ESP-IDF v6.1, target ESP32-C3 (ESP32-C3-MINI-1-H4X on the garageDoor-pro board).

## Build, test, flash

```bash
cd firmware && . ~/esp/esp-idf/export.sh && idf.py build
```

```bash
firmware/test/run.sh
```

The second command runs the host unit tests for the hardware-independent parts (UBX protocol,
distance, leaving/arriving state machine), with AddressSanitizer and UBSan.

The board's USB-C goes straight to the ESP32-C3 (native USB), so flashing needs no buttons:

```bash
idf.py -p /dev/cu.usbmodem* flash monitor
```

A brand-new module that will not enter download mode: hold SETUP while plugging in USB.

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

Fixes are used only with gnssFixOK, ≤ 50 m accuracy and ≥ 4 satellites. The GNSS receiver is
configured on every boot (UBX NAV-PVT 1 Hz, 115200 baud, automotive model, RAM only); if it goes
silent the firmware reconfigures it after 10 s and hardware-resets it after 30 s.

## Button and LED

| Button | Effect |
|--------|--------|
| hold 3 s (LED goes solid), release | setup Wi-Fi on for 10 minutes of inactivity |
| hold 10 s (LED flickers), release | factory reset: forget home, settings and password |

Green LED, one pattern every 3 s: **1 flash** GPS fix, **2** no fix, **3** home not set; fast
blinking = setup Wi-Fi on. Red LED = the remote is being pressed.

## Web panel

Setup Wi-Fi `GarageDoor-XXXX`, WPA2, default password `garagedoor`. Phones open the panel
automatically (captive portal), otherwise go to http://192.168.4.1. Until the default password is
changed, the panel only shows status and the password form.

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
| `main/ubx.c`, `main/geo.c` | UBX frames/parser, distance (pure C, unit-tested) |
| `main/gnss.c` | MAX-M10S UART driver and configuration |
| `main/presser.c` | PhotoMOS output: 150 ms presses every 2 s |
| `main/settings.c` | NVS: settings and the parked state |
| `main/ui.c` | LED patterns, SETUP button |
| `main/web.c`, `main/www/index.html` | soft AP, captive portal, HTTP API, OTA |
| `components/dns_server` | captive-portal DNS, from the ESP-IDF example (Unlicense / CC0) |
