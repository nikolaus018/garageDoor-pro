// Drives the NPN transistor across the remote's button: 400 ms presses every 2 s.
#pragma once

#include <stdbool.h>
#include <stdint.h>

// 400 ms like a person's press: fixed-code remotes repeat a ~50 ms frame while the button is down,
// and receivers often want several identical frames.
#define PRESS_PULSE_MS 400
#define PRESS_PERIOD_MS 2000
#define HOLD_TEST_MS 5000   // the panel's wiring test: long enough to read a multimeter

void presser_init(void);
void presser_press(uint16_t count);              // replaces any running sequence; first press now
void presser_press_for(uint16_t seconds);
void presser_hold(uint16_t ms);                  // replaces any running sequence; switch closed for ms
void presser_stop(void);
uint16_t presser_remaining(void);
bool presser_holding(void);
