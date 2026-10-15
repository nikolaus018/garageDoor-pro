// Shared application state for the web panel.
#pragma once

#include <stdbool.h>
#include <stdint.h>

#include "esp_err.h"
#include "settings.h"
#include "trip.h"

typedef struct {
    trip_state_t state;
    trip_parked_t parked;
    double distance_m;          // < 0 unknown
    bool have_fix;              // any NAV-PVT received
    trip_fix_t fix;             // last fix
    bool fix_usable;
    uint32_t gnss_age_s;        // since last NAV-PVT, UINT32_MAX if none
    uint16_t presses_remaining;
    uint32_t uptime_s;
} app_status_t;

void app_get_status(app_status_t *out);
// Sets home to the current GPS position. Returns NULL on success, else a message.
const char *app_set_home_here(void);
const char *app_set_home(int32_t lat_e7, int32_t lon_e7);
// Applies radius / press settings (the home fields of `s` are ignored).
const char *app_apply_settings(const settings_t *s);
void app_test_press(void);
