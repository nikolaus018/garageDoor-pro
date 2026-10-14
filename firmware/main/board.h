// Pin maps. Pick the board in menuconfig ("garageDoor" -> "Board"); see docs/prototype-build.md.
#pragma once

#include "driver/gpio.h"
#include "sdkconfig.h"

#define GNSS_UART UART_NUM_1

#if CONFIG_GARAGE_BOARD_PCB_V1
// garageDoor-pro PCB v1.0 (hardware/gen/netlist.py)
#define PIN_GPS_TX_TO_GNSS   GPIO_NUM_4   // UART1 TX -> receiver RXD
#define PIN_GPS_RX_FROM_GNSS GPIO_NUM_5   // UART1 RX <- receiver TXD
#define PIN_GPS_RESET_N      GPIO_NUM_6   // open-drain, low >= 1 ms resets the receiver
#define HAS_GPS_RESET        1
#define PIN_SWITCH           GPIO_NUM_7   // high closes the PhotoMOS (remote button) + red LED
#define PIN_BUTTON           GPIO_NUM_9   // BOOT / SETUP, active low
#define PIN_LED_STATUS       GPIO_NUM_10
#define LED_ACTIVE_LOW       0

#elif CONFIG_GARAGE_BOARD_C3_SUPERMINI
// ESP32-C3 SuperMini: on-board BOOT button (GPIO9) and blue LED (GPIO8, lights when low)
#define PIN_GPS_TX_TO_GNSS   GPIO_NUM_4
#define PIN_GPS_RX_FROM_GNSS GPIO_NUM_5
#define HAS_GPS_RESET        0            // GPS modules usually don't bring out reset
#define PIN_SWITCH           GPIO_NUM_7
#define PIN_BUTTON           GPIO_NUM_9
#define PIN_LED_STATUS       GPIO_NUM_8
#define LED_ACTIVE_LOW       1

#elif CONFIG_GARAGE_BOARD_S3_DEVKIT
// ESP32-S3 DevKitC: BOOT button on GPIO0; its RGB LED needs a driver, so use an external LED
#define PIN_GPS_TX_TO_GNSS   GPIO_NUM_4
#define PIN_GPS_RX_FROM_GNSS GPIO_NUM_5
#define HAS_GPS_RESET        0
#define PIN_SWITCH           GPIO_NUM_7
#define PIN_BUTTON           GPIO_NUM_0
#define PIN_LED_STATUS       GPIO_NUM_10  // optional: LED + 1k to GND
#define LED_ACTIVE_LOW       0

#else
#error "No garageDoor board selected (menuconfig: garageDoor -> Board)"
#endif
