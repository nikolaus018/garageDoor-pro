// u-blox UBX protocol: frame builder, streaming parser and NAV-PVT decoding.
// Pure C (no ESP-IDF), unit-tested on the host in firmware/test.
#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define UBX_SYNC1 0xB5
#define UBX_SYNC2 0x62
#define UBX_MAX_PAYLOAD 256

#define UBX_CLASS_NAV 0x01
#define UBX_ID_NAV_PVT 0x07
#define UBX_NAV_PVT_LEN 92
#define UBX_CLASS_CFG 0x06
#define UBX_ID_CFG_VALSET 0x8A
#define UBX_CLASS_ACK 0x05

// Configuration keys (u-blox M10 SPG 5.10 interface description, UBX-21035062).
#define UBX_CFG_UART1_BAUDRATE 0x40520001u          // U4
#define UBX_CFG_UART1OUTPROT_UBX 0x10740001u        // L
#define UBX_CFG_UART1OUTPROT_NMEA 0x10740002u       // L
#define UBX_CFG_UART1INPROT_UBX 0x10730001u         // L
#define UBX_CFG_MSGOUT_UBX_NAV_PVT_UART1 0x20910007u  // U1
#define UBX_CFG_NAVSPG_DYNMODEL 0x20110021u         // E1
#define UBX_CFG_RATE_MEAS 0x30210001u               // U2, ms
#define UBX_DYNMODEL_AUTOMOTIVE 4

#define UBX_LAYER_RAM 0x01

typedef struct {
    uint32_t key;
    uint32_t value;  // size taken from the key's size bits
} ubx_cfg_item_t;

// Builds a UBX-CFG-VALSET frame into buf. Returns the frame length, or 0 if buf is too small.
size_t ubx_build_valset(uint8_t *buf, size_t buf_len, uint8_t layers, const ubx_cfg_item_t *items, size_t count);

typedef struct {
    uint8_t state;
    uint8_t cls, id;
    uint16_t len, pos;
    uint8_t ck_a, ck_b;
    uint8_t payload[UBX_MAX_PAYLOAD];
} ubx_parser_t;

void ubx_parser_reset(ubx_parser_t *p);
// Feeds one byte. Returns true when a complete frame with a valid checksum has arrived;
// p->cls, p->id, p->len and p->payload then hold it until the next call.
bool ubx_parser_feed(ubx_parser_t *p, uint8_t byte);

typedef struct {
    uint8_t fix_type;    // 0 none, 2 2D, 3 3D, ...
    bool fix_ok;         // flags bit 0 (gnssFixOK)
    uint8_t num_sv;
    int32_t lon_e7, lat_e7;
    uint32_t h_acc_mm;
    int32_t ground_speed_mm_s;
} ubx_nav_pvt_t;

bool ubx_decode_nav_pvt(const uint8_t *payload, uint16_t len, ubx_nav_pvt_t *out);
