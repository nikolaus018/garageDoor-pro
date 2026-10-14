// Leaving / arriving logic. Pure C (no ESP-IDF), unit-tested on the host in firmware/test.
//
// The board is powered by the car, so it boots when the car starts. The garage is underground
// (no GPS there), so we remember in flash whether the car was last parked at home:
//
//   boot, parked HOME  -> LEAVING:  press the remote now; once GPS shows we are further than the
//                                   leave radius from home -> AWAY (saved)
//   boot, parked AWAY  -> AWAY:     wait for GPS
//   AWAY, GPS inside the arrive radius -> ARRIVED: save HOME, press for the arrival duration
//   ARRIVED, GPS beyond the leave radius again (drove past) -> AWAY: save, stop pressing
//   no home set yet    -> NO_HOME:  do nothing until home is set in the web panel
#pragma once

#include <stdbool.h>
#include <stdint.h>

typedef enum { TRIP_NO_HOME, TRIP_LEAVING, TRIP_AWAY, TRIP_ARRIVED } trip_state_t;
typedef enum { PARKED_HOME = 1, PARKED_AWAY = 2 } trip_parked_t;

enum {  // bit set returned by the trip_* functions
    TRIP_ACT_NONE = 0,
    TRIP_ACT_PRESS_LEAVE = 1 << 0,    // press the remote for leaving (count from settings)
    TRIP_ACT_PRESS_ARRIVE = 1 << 1,   // press the remote for arriving (duration from settings)
    TRIP_ACT_STOP_PRESSING = 1 << 2,
    TRIP_ACT_SAVE_PARKED = 1 << 3,    // persist trip_t.parked
};

typedef struct {
    bool home_set;
    int32_t home_lat_e7, home_lon_e7;
    uint16_t arrive_radius_m;
    uint16_t leave_radius_m;   // > arrive_radius_m, hysteresis against GPS jitter
} trip_config_t;

typedef struct {
    bool valid;          // receiver reports a fix (gnssFixOK, 2D/3D)
    int32_t lat_e7, lon_e7;
    uint32_t h_acc_mm;
    uint8_t num_sv;
} trip_fix_t;

typedef struct {
    trip_state_t state;
    trip_parked_t parked;
    double distance_m;   // to home from the last usable fix, < 0 if unknown
} trip_t;

#define TRIP_MAX_H_ACC_MM 50000
#define TRIP_MIN_SATELLITES 4

bool trip_fix_usable(const trip_fix_t *fix);
unsigned trip_start(trip_t *t, const trip_config_t *cfg, trip_parked_t saved);
unsigned trip_on_fix(trip_t *t, const trip_config_t *cfg, const trip_fix_t *fix);
// The user set home to where the car is right now: it is parked at home.
unsigned trip_on_home_set(trip_t *t, const trip_config_t *cfg);
const char *trip_state_name(trip_state_t s);
