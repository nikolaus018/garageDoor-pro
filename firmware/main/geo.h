// Great-circle distance between two points given in 1e-7 degrees. Pure C, host-tested.
#pragma once

#include <stdint.h>

double geo_distance_m(int32_t lat1_e7, int32_t lon1_e7, int32_t lat2_e7, int32_t lon2_e7);
