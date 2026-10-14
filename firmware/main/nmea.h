// Minimal NMEA 0183 reader: GGA sentences only (position, fix quality, satellites, HDOP).
// Fallback for GPS modules that don't speak u-blox UBX (NEO-6M, ATGM336H, ...).
// Pure C, unit-tested on the host in firmware/test.
#pragma once

#include <stdbool.h>
#include <stdint.h>

#define NMEA_MAX_LEN 96
#define NMEA_UERE_MM 5000   // HDOP x 5 m: rough horizontal accuracy estimate (NMEA has no hAcc)

typedef struct {
    char buf[NMEA_MAX_LEN];
    uint8_t len;
    bool in_sentence;
} nmea_parser_t;

typedef struct {
    bool fix;            // quality >= 1
    uint8_t num_sv;
    int32_t lat_e7, lon_e7;
    uint32_t h_acc_mm;   // estimated from HDOP
} nmea_gga_t;

void nmea_parser_reset(nmea_parser_t *p);
// Feeds one byte. Returns true when a complete GGA sentence with a valid checksum was decoded.
bool nmea_feed(nmea_parser_t *p, char c, nmea_gga_t *out);
// Decodes one sentence without '$' and without "*hh" (e.g. "GNGGA,....").
bool nmea_decode_gga(const char *sentence, nmea_gga_t *out);
