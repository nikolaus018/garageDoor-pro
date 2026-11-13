// User settings and the parked state, persisted in NVS.
#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "esp_err.h"
#include "trip.h"

typedef struct {
    bool home_set;
    int32_t home_lat_e7, home_lon_e7;
    uint16_t arrive_radius_m;     // default 150
    uint16_t leave_radius_m;      // default 300, always > arrive_radius_m
    uint8_t leave_presses;        // default 10
    uint16_t arrive_duration_s;   // default 180
} settings_t;

esp_err_t settings_init(void);           // initialises NVS and loads (defaults if empty)
settings_t settings_get(void);
esp_err_t settings_set(const settings_t *s);  // validates, stores and applies
esp_err_t settings_factory_reset(void);
trip_parked_t settings_get_parked(void);
esp_err_t settings_set_parked(trip_parked_t p);
// Boot number, counted up by settings_init (0 if NVS could not store it).
uint16_t settings_boot_count(void);

// Event log in NVS (starts and every change of state or parked), so a missed press can be traced
// back afterwards in the web panel. Keeps the last SETTINGS_LOG_LEN entries.
#define SETTINGS_LOG_LEN 16
typedef struct {
    uint16_t boot;
    uint8_t state;      // trip_state_t
    uint8_t parked;     // trip_parked_t
    uint32_t uptime_s;
    int32_t distance_m; // -1 unknown
    uint16_t acc_m;     // accuracy of the last fix, 0xFFFF none
    uint8_t sats;
    uint8_t start;      // 1: board started, 0: change while driving
} settings_log_entry_t;
void settings_log_add(const settings_log_entry_t *e);
// Copies the entries, oldest first. Returns how many.
size_t settings_log_get(settings_log_entry_t *out, size_t max);

// Fills a trip config from the current settings.
trip_config_t settings_trip_config(void);
// Validation shared with the web panel. Returns NULL if ok, else a message.
const char *settings_validate(const settings_t *s);
