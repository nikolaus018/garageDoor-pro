#include "nmea.h"

#include <stdlib.h>
#include <string.h>

void nmea_parser_reset(nmea_parser_t *p)
{
    memset(p, 0, sizeof(*p));
}

static int hexval(char c)
{
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    return -1;
}

// "4807.038" + 'N' (ddmm.mmmm) -> 1e-7 degrees. Returns false on malformed input.
static bool coord(const char *v, char hemi, int deg_digits, int32_t *out)
{
    if (strlen(v) < (size_t)deg_digits + 2) {
        return false;
    }
    for (int i = 0; i < deg_digits; i++) {
        if (v[i] < '0' || v[i] > '9') return false;
    }
    int deg = 0;
    for (int i = 0; i < deg_digits; i++) {
        deg = deg * 10 + (v[i] - '0');
    }
    char *end;
    double minutes = strtod(v + deg_digits, &end);
    if (*end || minutes < 0 || minutes >= 60) {
        return false;
    }
    double d = deg + minutes / 60.0;
    if (hemi == 'S' || hemi == 'W') {
        d = -d;
    } else if (hemi != 'N' && hemi != 'E') {
        return false;
    }
    *out = (int32_t)(d * 1e7 + (d >= 0 ? 0.5 : -0.5));
    return true;
}

bool nmea_decode_gga(const char *s, nmea_gga_t *out)
{
    // Talker ID (GP, GN, GL, GA, BD, ...) then "GGA".
    if (strlen(s) < 6 || strncmp(s + 2, "GGA,", 4) != 0) {
        return false;
    }
    char copy[NMEA_MAX_LEN];
    strncpy(copy, s, sizeof copy - 1);
    copy[sizeof copy - 1] = 0;

    const char *f[15] = { 0 };
    int n = 0;
    char *p = copy;
    while (n < 15) {
        f[n++] = p;
        char *comma = strchr(p, ',');
        if (!comma) break;
        *comma = 0;
        p = comma + 1;
    }
    if (n < 9) {
        return false;
    }
    // 0 id, 1 time, 2 lat, 3 N/S, 4 lon, 5 E/W, 6 quality, 7 satellites, 8 HDOP
    memset(out, 0, sizeof(*out));
    int quality = atoi(f[6]);
    out->num_sv = (uint8_t)atoi(f[7]);
    out->fix = quality >= 1 && quality <= 5 && *f[2] && *f[4];
    if (!out->fix) {
        return true;  // valid sentence, no fix (normal while searching)
    }
    if (!coord(f[2], f[3][0], 2, &out->lat_e7) || !coord(f[4], f[5][0], 3, &out->lon_e7)) {
        return false;
    }
    double hdop = *f[8] ? strtod(f[8], NULL) : 99.0;
    out->h_acc_mm = (uint32_t)(hdop * NMEA_UERE_MM);
    return true;
}

bool nmea_feed(nmea_parser_t *p, char c, nmea_gga_t *out)
{
    if (c == '$') {
        p->in_sentence = true;
        p->len = 0;
        return false;
    }
    if (!p->in_sentence) {
        return false;
    }
    if (c == '\r' || c == '\n') {
        p->in_sentence = false;
        p->buf[p->len] = 0;
        char *star = strrchr(p->buf, '*');
        if (!star || star[1] == 0 || star[2] == 0) {
            return false;
        }
        int hi = hexval(star[1]), lo = hexval(star[2]);
        if (hi < 0 || lo < 0) {
            return false;
        }
        uint8_t sum = 0;
        for (char *q = p->buf; q < star; q++) {
            sum ^= (uint8_t)*q;
        }
        if (sum != (uint8_t)(hi << 4 | lo)) {
            return false;
        }
        *star = 0;
        return nmea_decode_gga(p->buf, out);
    }
    if (p->len >= NMEA_MAX_LEN - 1) {
        p->in_sentence = false;  // too long: not a sentence we handle
        return false;
    }
    p->buf[p->len++] = c;
    return false;
}
