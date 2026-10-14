// MAX-M10S driver: configures UBX NAV-PVT at 1 Hz / 115200 baud and reports fixes.
#pragma once

#include "trip.h"

typedef void (*gnss_fix_cb_t)(const trip_fix_t *fix);

void gnss_start(gnss_fix_cb_t cb);
// Seconds since the last NAV-PVT message (receiver alive), UINT32_MAX if none yet.
uint32_t gnss_seconds_since_message(void);
