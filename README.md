# garageDoor-pro

Opens the garage door when you leave home and when you arrive: an ESP32-C3, a GPS and an isolated
switch output wired to a spare remote, powered over USB-C from the car. Home is set from a small
Wi-Fi web panel.

**What gets built now:** the perfboard prototype from ready-made modules, see
**[prototype/README.md](prototype/README.md)** (parts list, layout, assembly, test). The custom PCB
below is the later, integrated version; the firmware runs on both.

| | |
|---|---|
| [prototype/README.md](prototype/README.md) | **perfboard build: parts, layout, assembly, bench test** |
| [docs/design.md](docs/design.md) | behaviour, parts, circuit and PCB decisions |
| [docs/user-guide.md](docs/user-guide.md) | installing in the car and setting it up |
| [hardware/ORDERING.md](hardware/ORDERING.md) | (later) ordering the custom PCB from JLCPCB, bring-up checklist |
| [firmware/README.md](firmware/README.md) | build, flash, OTA, LED codes |
| `hardware/production/` | Gerbers, BOM, CPL, schematic PDF, renders, STEP |
| `hardware/gen/` | the generator: `netlist.py` is the single source for schematic and PCB |

![PCB version](hardware/production/render-iso.png)
