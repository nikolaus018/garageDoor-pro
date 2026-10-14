// User settings and the parked state, persisted in NVS.
#pragma once

#include <stdbool.h>
#include <stdint.h>

#include "esp_err.h"
#include "trip.h"

#define SETTINGS_DEFAULT_AP_PASSWORD "garagedoor"

typedef struct {
    bool home_set;
    int32_t home_lat_e7, home_lon_e7;
    uint16_t arrive_radius_m;     // default 150
    uint16_t leave_radius_m;      // default 300, always > arrive_radius_m
    uint8_t leave_presses;        // default 10
    uint16_t arrive_duration_s;   // default 180
    char ap_password[64];         // WPA2, 8..63 characters
    bool password_changed;        // false until the user replaced the default password
} settings_t;

esp_err_t settings_init(void);           // initialises NVS and loads (defaults if empty)
settings_t settings_get(void);
esp_err_t settings_set(const settings_t *s);  // validates, stores and applies
esp_err_t settings_factory_reset(void);
trip_parked_t settings_get_parked(void);
esp_err_t settings_set_parked(trip_parked_t p);
// Fills a trip config from the current settings.
trip_config_t settings_trip_config(void);
// Validation shared with the web panel. Returns NULL if ok, else a message.
const char *settings_validate(const settings_t *s);
