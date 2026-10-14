// Green status LED patterns and the SETUP button.
//
// LED (one flash pattern every 3 s): 1 flash = GPS fix, 2 = no GPS fix, 3 = home not set.
// Fast blinking = setup Wi-Fi is on. Solid while holding the button past 3 s (release: setup),
// rapid flicker past 10 s (release: factory reset).
#pragma once

#include <stdbool.h>

typedef enum { UI_FIX, UI_NO_FIX, UI_NO_HOME } ui_status_t;

typedef struct {
    void (*on_setup)(void);           // button held 3-10 s
    void (*on_factory_reset)(void);   // button held >= 10 s
} ui_callbacks_t;

void ui_start(const ui_callbacks_t *cb);
void ui_set_status(ui_status_t s);
void ui_set_setup_mode(bool on);
