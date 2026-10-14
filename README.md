# garageDoor-pro

All-in-one board that opens the garage door when you leave home and when you arrive: an
ESP32-C3, a u-blox MAX-M10S GPS and an isolated switch output wired to a spare remote, powered
over USB-C from the car. Home is set from a small Wi-Fi web panel.

![board](hardware/production/render-iso.png)

| | |
|---|---|
| [docs/design.md](docs/design.md) | behaviour, parts, circuit and PCB decisions |
| [docs/user-guide.md](docs/user-guide.md) | installing in the car and setting it up |
| [hardware/ORDERING.md](hardware/ORDERING.md) | ordering assembled boards from JLCPCB, bring-up checklist |
| [firmware/README.md](firmware/README.md) | build, flash, OTA, LED codes |
| `hardware/production/` | Gerbers, BOM, CPL, schematic PDF, renders, STEP |
| `hardware/gen/` | the generator: `netlist.py` is the single source for schematic and PCB |

The working predecessor lives in `~/Documents/garageDoor` (tag `legacy-v1`).
