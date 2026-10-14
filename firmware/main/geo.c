#include "geo.h"

#include <math.h>

#define EARTH_RADIUS_M 6371008.8
#define DEG_TO_RAD (M_PI / 180.0)

double geo_distance_m(int32_t lat1_e7, int32_t lon1_e7, int32_t lat2_e7, int32_t lon2_e7)
{
    double lat1 = lat1_e7 * 1e-7 * DEG_TO_RAD;
    double lat2 = lat2_e7 * 1e-7 * DEG_TO_RAD;
    double dlat = lat2 - lat1;
    double dlon = (lon2_e7 - (double)lon1_e7) * 1e-7 * DEG_TO_RAD;
    double s1 = sin(dlat / 2), s2 = sin(dlon / 2);
    double a = s1 * s1 + cos(lat1) * cos(lat2) * s2 * s2;
    return 2 * EARTH_RADIUS_M * atan2(sqrt(a), sqrt(1 - a));
}
