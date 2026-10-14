#include "trip.h"

#include "geo.h"

bool trip_fix_usable(const trip_fix_t *fix)
{
    return fix->valid && fix->h_acc_mm <= TRIP_MAX_H_ACC_MM && fix->num_sv >= TRIP_MIN_SATELLITES;
}

unsigned trip_start(trip_t *t, const trip_config_t *cfg, trip_parked_t saved)
{
    t->distance_m = -1;
    t->parked = (saved == PARKED_AWAY) ? PARKED_AWAY : PARKED_HOME;  // nothing saved yet: home
    if (!cfg->home_set) {
        t->state = TRIP_NO_HOME;
        return TRIP_ACT_NONE;
    }
    if (t->parked == PARKED_HOME) {
        t->state = TRIP_LEAVING;
        return TRIP_ACT_PRESS_LEAVE;
    }
    t->state = TRIP_AWAY;
    return TRIP_ACT_NONE;
}

static unsigned set_parked(trip_t *t, trip_parked_t p)
{
    if (t->parked == p) {
        return TRIP_ACT_NONE;
    }
    t->parked = p;
    return TRIP_ACT_SAVE_PARKED;
}

unsigned trip_on_fix(trip_t *t, const trip_config_t *cfg, const trip_fix_t *fix)
{
    if (!cfg->home_set || t->state == TRIP_NO_HOME || !trip_fix_usable(fix)) {
        return TRIP_ACT_NONE;
    }
    double d = geo_distance_m(cfg->home_lat_e7, cfg->home_lon_e7, fix->lat_e7, fix->lon_e7);
    t->distance_m = d;

    switch (t->state) {
    case TRIP_LEAVING:
        if (d > cfg->leave_radius_m) {
            t->state = TRIP_AWAY;
            return set_parked(t, PARKED_AWAY);
        }
        return TRIP_ACT_NONE;
    case TRIP_AWAY:
        if (d < cfg->arrive_radius_m) {
            t->state = TRIP_ARRIVED;
            return set_parked(t, PARKED_HOME) | TRIP_ACT_PRESS_ARRIVE;
        }
        return TRIP_ACT_NONE;
    case TRIP_ARRIVED:
        if (d > cfg->leave_radius_m) {   // drove past home without stopping
            t->state = TRIP_AWAY;
            return set_parked(t, PARKED_AWAY) | TRIP_ACT_STOP_PRESSING;
        }
        return TRIP_ACT_NONE;
    default:
        return TRIP_ACT_NONE;
    }
}

unsigned trip_on_home_set(trip_t *t, const trip_config_t *cfg)
{
    (void)cfg;
    t->state = TRIP_LEAVING;   // parked at home; the next drive away sets AWAY
    t->distance_m = 0;
    return set_parked(t, PARKED_HOME);
}

const char *trip_state_name(trip_state_t s)
{
    switch (s) {
    case TRIP_NO_HOME: return "NO_HOME";
    case TRIP_LEAVING: return "LEAVING";
    case TRIP_AWAY: return "AWAY";
    case TRIP_ARRIVED: return "ARRIVED";
    default: return "?";
    }
}
