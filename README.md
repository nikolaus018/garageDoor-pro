# garageDoor-pro

All-in-one board that opens the garage door when you leave home and when you arrive: ESP32-C3 +
u-blox MAX-M10S GPS + PhotoMOS switch output, powered over USB-C from the car. Home is set from a
small Wi-Fi web panel.

- [docs/design.md](docs/design.md): behaviour, parts (with LCSC numbers), circuit notes, pin map, PCB plan
- `hardware/`: KiCad 10 project (coming next)
- `firmware/`: ESP-IDF v6.1 firmware (after the schematic)

The working predecessor lives in `~/Documents/garageDoor` (tag `legacy-v1`).
