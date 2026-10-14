// garageDoor-pro v1.0 pin map (hardware/gen/netlist.py).
#pragma once

#include "driver/gpio.h"

#define PIN_GPS_TX_TO_GNSS   GPIO_NUM_4   // UART1 TX -> MAX-M10S RXD
#define PIN_GPS_RX_FROM_GNSS GPIO_NUM_5   // UART1 RX <- MAX-M10S TXD
#define PIN_GPS_RESET_N      GPIO_NUM_6   // open-drain, low >= 1 ms resets the receiver
#define PIN_SWITCH           GPIO_NUM_7   // high closes the PhotoMOS (remote button) + red LED
#define PIN_BUTTON           GPIO_NUM_9   // BOOT / SETUP button, active low (10k pull-up)
#define PIN_LED_STATUS       GPIO_NUM_10  // green status LED, active high

#define GNSS_UART UART_NUM_1
