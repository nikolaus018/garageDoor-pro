# garageDoor: installation and setup

## What you need

- the garageDoor board, flashed (see `firmware/README.md`)
- an active GNSS antenna with U.FL plug
- a spare remote for your garage door, already working with the door
- a USB car charger and a USB-C cable, on a socket that switches off with the ignition

## 1. Wire the remote

Open the spare remote and find the button that opens the door. Solder two thin wires across the
button's two contacts (the two sides that the button connects when pressed). Put the other ends
into the screw terminal marked **REMOTE**. Polarity does not matter.

Keep the remote's battery in it: the board only "presses" the button, the remote transmits.

## 2. Install in the car

- Mount the board out of direct sun (console, glovebox, behind a trim panel), not on top of the
  dashboard. The board is rated to 85 °C.
- Place the antenna where it sees the sky: on the dashboard under the windscreen, or under a
  plastic trim near the rear window. Plug it into **ANT**.
- Connect USB-C to the car charger. Check that the socket really switches off with the ignition:
  the board relies on starting with the car.

## 3. Set it up

1. Park at home, with the antenna seeing the sky (outdoors, not in the underground garage), and
   switch the ignition on. A new board opens its setup Wi-Fi by itself (green LED blinks fast).
   Later you open it by holding the SETUP button for 3 s.
2. On your phone, join the Wi-Fi **GarageDoor-XXXX**, password `garagedoor`. The panel opens by
   itself; if not, browse to http://192.168.4.1.
3. Choose your own Wi-Fi password and reconnect with it.
4. Wait until the panel shows a GPS fix, then tap **Set home to where the car is now**.
5. Tap **Press the remote once** and check that the door reacts.
6. Optional: adjust the radii. Arriving starts inside the arrive radius (default 150 m), and you
   count as gone beyond the leave radius (default 300 m). If the door opens too late when you
   come home, increase the arrive radius; the board keeps pressing for 3 minutes.

The setup Wi-Fi switches itself off after 10 minutes without use.

## Everyday use

- **Leaving:** starting the car in the garage presses the remote 10 times (every 2 s). Extra
  presses while the door moves just keep it open.
- **Arriving:** when GPS puts you inside the arrive radius, it presses every 2 s until you switch
  the car off (at most 3 minutes).
- Starting the car anywhere else does nothing.
- Driving past home without stopping: the door opens briefly and then closes on its own timer.

## LED codes

Green, every 3 s: 1 flash = GPS fix, 2 = no fix yet (normal in the garage), 3 = home not set.
Fast blinking = setup Wi-Fi is on. Red = pressing the remote.

## Factory reset

Hold SETUP for 10 s (the LED flickers), then release. Home, settings and the Wi-Fi password are
erased; set it up again from step 3.
