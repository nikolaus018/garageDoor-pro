// GPS driver: u-blox M9/M10 via UBX NAV-PVT (configured at boot), or any module's NMEA GGA output.
#pragma once

#include "trip.h"

typedef void (*gnss_fix_cb_t)(const trip_fix_t *fix);
typedef enum { GNSS_NONE, GNSS_UBX, GNSS_NMEA } gnss_protocol_t;

void gnss_start(gnss_fix_cb_t cb);
// Seconds since the last NAV-PVT message (receiver alive), UINT32_MAX if none yet.
uint32_t gnss_seconds_since_message(void);
gnss_protocol_t gnss_protocol(void);
