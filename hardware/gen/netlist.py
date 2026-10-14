"""Single source of truth for the garageDoor-pro board: parts, nets and placement.

Both the schematic (make_schematic.py) and the PCB (make_pcb.py) are generated from this file,
so they cannot drift apart. Runs under the system Python and KiCad's bundled Python 3.9.
"""

BOARD_W = 60.0   # mm
BOARD_H = 31.0
ANTENNA_KEEPOUT_X = 6.2  # no copper of any kind left of this line (ESP32 PCB antenna)

# ref: (value, symbol lib_id, footprint "lib:name", LCSC, MPN, description)
PARTS = {
    "U1": ("ESP32-C3-MINI-1-H4X", "Espressif:ESP32-C3-MINI-1", "garageDoor:ESP32-C3-MINI-1",
           "C41349510", "ESP32-C3-MINI-1-H4X", "Wi-Fi/BLE MCU module, 4 MB flash, -40..105 C"),
    "U2": ("MAX-M10S", "RF_GPS:MAX-M10S", "RF_GPS:ublox_MAX",
           "C4153167", "MAX-M10S-00B", "u-blox M10 GNSS receiver"),
    "U3": ("AP2112K-3.3", "Regulator_Linear:AP2112K-3.3", "Package_TO_SOT_SMD:SOT-23-5",
           "C51118", "AP2112K-3.3TRG1", "3.3 V 600 mA LDO"),
    "U4": ("USBLC6-2SC6", "Power_Protection:USBLC6-2SC6", "Package_TO_SOT_SMD:SOT-23-6",
           "C7519", "USBLC6-2SC6", "USB data line ESD protection"),
    "K1": ("CPC1017N", "Relay_SolidState:CPC1017N", "Package_SO:SOP-4_3.8x4.1mm_P2.54mm",
           "C81521", "CPC1017NTR", "PhotoMOS relay 60 V 100 mA, isolated switch output"),
    "J1": ("USB-C", "Connector:USB_C_Receptacle_USB2.0_16P",
           "Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12",
           "C165948", "TYPE-C-31-M-12", "USB-C receptacle, power + data"),
    "J2": ("U.FL GNSS antenna", "Connector:Conn_Coaxial",
           "Connector_Coaxial:U.FL_Hirose_U.FL-R-SMT-1_Vertical",
           "C88373", "U.FL-R-SMT-1(10)", "Active GNSS antenna (3.3 V)"),
    "J3": ("Remote button", "Connector:Screw_Terminal_01x02",
           "TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-2-5.08_1x02_P5.08mm_Horizontal",
           "C474952", "KF128-5.08-2P", "2-pin screw terminal, 5.08 mm, 0.2-2.5 mm2"),
    "F1": ("500mA", "Device:Polyfuse", "Fuse:Fuse_1206_3216Metric",
           "C22472478", "SMD1206-050C-6V", "PTC resettable fuse 6 V 500 mA hold"),
    "D1": ("SMF5.0A", "Device:D_Zener", "Diode_SMD:D_SOD-123F",
           "C1509112", "SMF5.0A", "5 V unidirectional TVS on VBUS"),
    "D2": ("RED", "Device:LED", "LED_SMD:LED_0603_1608Metric",
           "C2286", "KT-0603R", "Pressing indicator"),
    "D3": ("GREEN", "Device:LED", "LED_SMD:LED_0603_1608Metric",
           "C12624", "KT-0603G", "Status LED"),
    "L1": ("27nH", "Device:L", "Inductor_SMD:L_0402_1005Metric",
           "C12669", "LQG15HS27NJ02D", "Antenna bias-T inductor"),
    "SW1": ("SETUP", "Switch:SW_Push", "Button_Switch_SMD:SW_Push_1P1T_XKB_TS-1187A",
            "C318884", "TS-1187A-B-A-B", "BOOT / SETUP button"),
    "R1": ("10R", "Device:R", "Resistor_SMD:R_1206_3216Metric",
           "C17903", "1206W4F100JT5E", "Antenna supply current limit 0.25 W"),
    "R2": ("10k", "Device:R", "Resistor_SMD:R_0402_1005Metric", "C25744", "0402WGF1002TCE", "EN pull-up"),
    "R3": ("10k", "Device:R", "Resistor_SMD:R_0402_1005Metric", "C25744", "0402WGF1002TCE", "GPIO9 pull-up"),
    "R4": ("10k", "Device:R", "Resistor_SMD:R_0402_1005Metric", "C25744", "0402WGF1002TCE", "GPIO8 pull-up"),
    "R5": ("10k", "Device:R", "Resistor_SMD:R_0402_1005Metric", "C25744", "0402WGF1002TCE", "GPIO2 pull-up"),
    "R6": ("5.1k", "Device:R", "Resistor_SMD:R_0402_1005Metric", "C25905", "0402WGF5101TCE", "CC1 pull-down"),
    "R7": ("5.1k", "Device:R", "Resistor_SMD:R_0402_1005Metric", "C25905", "0402WGF5101TCE", "CC2 pull-down"),
    "R8": ("330R", "Device:R", "Resistor_SMD:R_0402_1005Metric", "C25104", "0402WGF3300TCE", "PhotoMOS LED current"),
    "R9": ("100k", "Device:R", "Resistor_SMD:R_0402_1005Metric", "C25741", "0402WGF1003TCE", "Switch off during boot"),
    "R10": ("1k", "Device:R", "Resistor_SMD:R_0603_1608Metric", "C21190", "0603WAF1001T5E", "Red LED"),
    "R11": ("1k", "Device:R", "Resistor_SMD:R_0603_1608Metric", "C21190", "0603WAF1001T5E", "Green LED"),
    "C1": ("10nF", "Device:C", "Capacitor_SMD:C_0402_1005Metric", "C15195", "CL05B103KB5NNNC", "Bias-T decoupling"),
    "C2": ("47pF C0G", "Device:C", "Capacitor_SMD:C_0402_1005Metric", "C1567", "0402CG470J500NT", "RF DC block"),
    "C3": ("10uF", "Device:C", "Capacitor_SMD:C_0603_1608Metric", "C19702", "CL10A106KP8NNNC", "LDO input"),
    "C4": ("10uF", "Device:C", "Capacitor_SMD:C_0603_1608Metric", "C19702", "CL10A106KP8NNNC", "LDO output"),
    "C5": ("10uF", "Device:C", "Capacitor_SMD:C_0603_1608Metric", "C19702", "CL10A106KP8NNNC", "ESP32 supply"),
    "C6": ("100nF", "Device:C", "Capacitor_SMD:C_0402_1005Metric", "C60474", "CC0402KRX7R7BB104", "ESP32 supply"),
    "C7": ("10uF", "Device:C", "Capacitor_SMD:C_0603_1608Metric", "C19702", "CL10A106KP8NNNC", "GNSS supply"),
    "C8": ("100nF", "Device:C", "Capacitor_SMD:C_0402_1005Metric", "C60474", "CC0402KRX7R7BB104", "GNSS supply"),
    "C9": ("1uF", "Device:C", "Capacitor_SMD:C_0402_1005Metric", "C14445", "CL05A105KP5NNNC", "EN reset delay"),
}

# Bare copper test pads on the bottom side (not assembled) and mounting holes.
TEST_POINTS = {
    "TP1": "+3V3", "TP2": "GND", "TP3": "GPS_SAFEBOOT", "TP4": "GPS_PPS", "TP5": "IO0",
    "TP6": "IO1", "TP7": "IO3", "TP8": "U0RXD", "TP9": "U0TXD", "TP10": "VIN_5V",
}
MOUNTING_HOLES = ["H1", "H2"]

ESP_GND = ["1", "2", "11", "14"] + [str(n) for n in range(36, 54)]
ESP_NC = ["4", "7", "9", "10", "15", "17", "24", "25", "28", "29", "32", "33", "34", "35"]

NETS = {
    "GND": [("U1", p) for p in ESP_GND] + [
        ("U2", "1"), ("U2", "10"), ("U2", "12"), ("U3", "2"), ("U4", "2"), ("K1", "2"),
        ("J1", "A1"), ("J1", "A12"), ("J1", "B1"), ("J1", "B12"), ("J1", "SH"), ("J2", "2"),
        ("D1", "2"), ("D2", "1"), ("D3", "1"), ("SW1", "2"), ("R6", "2"), ("R7", "2"), ("R9", "2"),
        ("C1", "2"), ("C3", "2"), ("C4", "2"), ("C5", "2"), ("C6", "2"), ("C7", "2"), ("C8", "2"),
        ("C9", "2"), ("TP2", "1")],
    "+3V3": [("U3", "5"), ("U1", "3"), ("U2", "7"), ("U2", "8"), ("C4", "1"), ("C5", "1"), ("C6", "1"),
             ("C7", "1"), ("C8", "1"), ("R2", "1"), ("R3", "1"), ("R4", "1"), ("R5", "1"), ("TP1", "1")],
    "VBUS": [("J1", "A4"), ("J1", "A9"), ("J1", "B4"), ("J1", "B9"), ("F1", "1")],
    "VIN_5V": [("F1", "2"), ("D1", "1"), ("C3", "1"), ("U3", "1"), ("U3", "3"), ("U4", "5"), ("TP10", "1")],
    "USB_DP": [("J1", "A6"), ("J1", "B6"), ("U4", "1"), ("U4", "6"), ("U1", "27")],
    "USB_DM": [("J1", "A7"), ("J1", "B7"), ("U4", "3"), ("U4", "4"), ("U1", "26")],
    "CC1": [("J1", "A5"), ("R6", "1")],
    "CC2": [("J1", "B5"), ("R7", "1")],
    "EN": [("U1", "8"), ("R2", "2"), ("C9", "1")],
    "IO2": [("U1", "5"), ("R5", "2")],
    "IO8": [("U1", "22"), ("R4", "2")],
    "BTN_IO9": [("U1", "23"), ("R3", "2"), ("SW1", "1")],
    "LED_STATUS": [("U1", "16"), ("R11", "1")],
    "LED_G_A": [("R11", "2"), ("D3", "2")],
    "SWITCH": [("U1", "21"), ("R8", "1"), ("R9", "1"), ("R10", "1")],
    "K1_LED_A": [("R8", "2"), ("K1", "1")],
    "LED_R_A": [("R10", "2"), ("D2", "2")],
    "OUT_A": [("K1", "4"), ("J3", "1")],
    "OUT_B": [("K1", "3"), ("J3", "2")],
    "GPS_TX": [("U2", "2"), ("U1", "19")],     # GNSS TXD -> ESP GPIO5 (UART1 RX)
    "GPS_RX": [("U2", "3"), ("U1", "18")],     # GNSS RXD <- ESP GPIO4 (UART1 TX)
    "GPS_RESET_N": [("U2", "9"), ("U1", "20")],
    "GPS_PPS": [("U2", "4"), ("TP4", "1")],
    "GPS_SAFEBOOT": [("U2", "18"), ("TP3", "1")],
    "VCC_RF": [("U2", "14"), ("R1", "1")],
    "ANT_BIAS": [("R1", "2"), ("C1", "1"), ("L1", "1")],
    "ANT_FEED": [("L1", "2"), ("C2", "2"), ("J2", "1")],
    "GPS_RF_IN": [("U2", "11"), ("C2", "1")],
    "IO0": [("U1", "12"), ("TP5", "1")],
    "IO1": [("U1", "13"), ("TP6", "1")],
    "IO3": [("U1", "6"), ("TP7", "1")],
    "U0RXD": [("U1", "30"), ("TP8", "1")],
    "U0TXD": [("U1", "31"), ("TP9", "1")],
}

# Unconnected pins: get a no-connect flag in the schematic.
NO_CONNECT = [("U1", p) for p in ESP_NC] + [
    ("U2", "5"), ("U2", "6"), ("U2", "13"), ("U2", "15"), ("U2", "16"), ("U2", "17"),
    ("U3", "4"), ("J1", "A8"), ("J1", "B8"),
]

# PCB placement: ref -> (x, y, rotation_deg, side). Board origin is its top-left corner.
PLACEMENT = {
    "U1": (8.56, 16.0, 90, "F"),     # antenna to the left board edge
    "J1": (24.0, 4.18, 180, "F"),    # USB-C on the top edge, opening up
    "U4": (19.8, 12.6, 0, "F"),
    "R7": (22.9, 11.4, 90, "F"),
    "R6": (26.2, 11.4, 90, "F"),
    "F1": (32.8, 6.4, 0, "F"),
    "D1": (32.8, 9.6, 180, "F"),
    "U3": (32.8, 13.4, 0, "F"),
    "C3": (36.4, 9.8, 90, "F"),
    "C4": (36.4, 13.6, 90, "F"),
    "U2": (44.0, 14.2, 0, "F"),
    "C7": (35.0, 17.4, 90, "F"),
    "C8": (36.7, 17.4, 90, "F"),
    "C2": (51.1, 17.5, 0, "F"),      # RF line: U2 RF_IN -> C2 -> ANT_FEED -> J2
    "L1": (52.6, 15.9, 270, "F"),    # pad 2 (ANT_FEED) faces the RF line below
    "R1": (52.4, 13.2, 0, "F"),      # VCC_RF (left) -> ANT_BIAS (right)
    "C1": (55.7, 13.2, 0, "F"),
    "J2": (55.75, 17.5, 0, "F"),
    "R3": (20.0, 16.0, 90, "F"),
    "R4": (21.4, 16.0, 90, "F"),
    "R5": (22.8, 16.0, 90, "F"),
    "C5": (8.0, 24.4, 0, "F"),
    "C6": (10.6, 24.4, 0, "F"),
    "R2": (12.8, 24.4, 0, "F"),
    "C9": (15.0, 24.4, 0, "F"),
    "SW1": (20.2, 26.6, 0, "F"),
    "K1": (28.5, 26.0, 0, "F"),
    "R8": (25.6, 21.4, 90, "F"),
    "R9": (27.0, 21.4, 90, "F"),
    "R10": (11.6, 27.0, 0, "F"),
    "D2": (11.6, 29.3, 180, "F"),
    "R11": (8.0, 27.0, 0, "F"),
    "D3": (8.0, 29.3, 180, "F"),
    "J3": (36.0, BOARD_H - 5.6, 0, "F"),  # wire entry 1 mm inside the bottom edge
    # bottom-side test pads: two columns, labels to the right
    "TP1": (44.6, 21.4, 0, "B"), "TP2": (44.6, 23.4, 0, "B"), "TP3": (44.6, 25.4, 0, "B"),
    "TP4": (44.6, 27.4, 0, "B"), "TP10": (44.6, 29.4, 0, "B"),
    "TP5": (54.0, 21.4, 0, "B"), "TP6": (54.0, 23.4, 0, "B"), "TP7": (54.0, 25.4, 0, "B"),
    "TP8": (54.0, 27.4, 0, "B"), "TP9": (54.0, 29.4, 0, "B"),
    "H1": (56.5, 3.5, 0, "F"),
    "H2": (14.0, 3.5, 0, "F"),
}

TEST_POINT_FOOTPRINT = "TestPoint:TestPoint_Pad_D1.0mm"
MOUNTING_HOLE_FOOTPRINT = "MountingHole:MountingHole_2.7mm_M2.5"

# Net classes (applied in the KiCad project file).
NET_CLASSES = {
    "Power": {"nets": ["VBUS", "VIN_5V", "+3V3", "GND"], "track": 0.5, "clearance": 0.2},
    "RF": {"nets": ["GPS_RF_IN", "ANT_FEED"], "track": 0.36, "clearance": 0.25},
    "USB": {"nets": ["USB_DP", "USB_DM"], "track": 0.25, "clearance": 0.15},
}


POWER_NETS = ("GND", "+3V3")
TEST_POINT_LABELS = {"TP1": "3V3", "TP2": "GND", "TP3": "SAFEBOOT", "TP4": "PPS", "TP5": "IO0", "TP6": "IO1",
                     "TP7": "IO3", "TP8": "RXD0", "TP9": "TXD0", "TP10": "5V"}


def pcb_net_name(net):
    """KiCad names nets from local schematic labels with the sheet path, e.g. /USB_DP."""
    return net if net in POWER_NETS else "/" + net


def pin_nets():
    """(ref, pin) -> net name, validating that no pin sits on two nets."""
    out = {}
    for net, pins in NETS.items():
        for rp in pins:
            if rp in out:
                raise ValueError(f"{rp} is on both {out[rp]} and {net}")
            out[rp] = net
    for ref, net in TEST_POINTS.items():
        if (ref, "1") not in out:
            raise ValueError(f"test point {ref} not on net {net}")
        if out[(ref, "1")] != net:
            raise ValueError(f"{ref} on {out[(ref, '1')]}, expected {net}")
    for rp in NO_CONNECT:
        if rp in out:
            raise ValueError(f"{rp} is marked no-connect but on net {out[rp]}")
    return out
