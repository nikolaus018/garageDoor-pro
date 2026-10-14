// Drives the isolated switch (PhotoMOS / optocoupler) across the remote's button: 150 ms presses every 2 s.
#pragma once

#include <stdbool.h>
#include <stdint.h>

#define PRESS_PULSE_MS 150
#define PRESS_PERIOD_MS 2000

void presser_init(void);
void presser_press(uint16_t count);              // replaces any running sequence; first press now
void presser_press_for(uint16_t seconds);
void presser_stop(void);
uint16_t presser_remaining(void);
