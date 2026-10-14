#include "ubx.h"

#include <string.h>

enum { S_SYNC1, S_SYNC2, S_CLASS, S_ID, S_LEN1, S_LEN2, S_PAYLOAD, S_CK_A, S_CK_B };

static void checksum(const uint8_t *data, size_t len, uint8_t *a, uint8_t *b)
{
    uint8_t ca = 0, cb = 0;
    for (size_t i = 0; i < len; i++) {
        ca += data[i];
        cb += ca;
    }
    *a = ca;
    *b = cb;
}

static size_t key_value_size(uint32_t key)
{
    switch ((key >> 28) & 0x7) {  // size bits of the key ID
    case 1: return 1;  // L (one bit, stored in a byte)
    case 2: return 1;
    case 3: return 2;
    case 4: return 4;
    case 5: return 8;
    default: return 0;
    }
}

size_t ubx_build_valset(uint8_t *buf, size_t buf_len, uint8_t layers, const ubx_cfg_item_t *items, size_t count)
{
    size_t payload = 4;
    for (size_t i = 0; i < count; i++) {
        size_t vs = key_value_size(items[i].key);
        if (vs == 0 || vs == 8) {
            return 0;
        }
        payload += 4 + vs;
    }
    size_t total = 6 + payload + 2;
    if (total > buf_len || payload > 0xFFFF) {
        return 0;
    }
    uint8_t *p = buf;
    *p++ = UBX_SYNC1;
    *p++ = UBX_SYNC2;
    *p++ = UBX_CLASS_CFG;
    *p++ = UBX_ID_CFG_VALSET;
    *p++ = payload & 0xFF;
    *p++ = payload >> 8;
    *p++ = 0;       // version
    *p++ = layers;
    *p++ = 0;       // reserved
    *p++ = 0;
    for (size_t i = 0; i < count; i++) {
        uint32_t k = items[i].key;
        for (int b = 0; b < 4; b++) {
            *p++ = (k >> (8 * b)) & 0xFF;
        }
        size_t vs = key_value_size(k);
        for (size_t b = 0; b < vs; b++) {
            *p++ = (items[i].value >> (8 * b)) & 0xFF;
        }
    }
    checksum(buf + 2, 4 + payload, &p[0], &p[1]);
    return total;
}

void ubx_parser_reset(ubx_parser_t *p)
{
    memset(p, 0, sizeof(*p));
    p->state = S_SYNC1;
}

static void ck_add(ubx_parser_t *p, uint8_t b)
{
    p->ck_a += b;
    p->ck_b += p->ck_a;
}

bool ubx_parser_feed(ubx_parser_t *p, uint8_t b)
{
    switch (p->state) {
    case S_SYNC1:
        if (b == UBX_SYNC1) {
            p->state = S_SYNC2;
        }
        return false;
    case S_SYNC2:
        p->state = (b == UBX_SYNC2) ? S_CLASS : (b == UBX_SYNC1 ? S_SYNC2 : S_SYNC1);
        p->ck_a = p->ck_b = 0;
        return false;
    case S_CLASS:
        p->cls = b;
        ck_add(p, b);
        p->state = S_ID;
        return false;
    case S_ID:
        p->id = b;
        ck_add(p, b);
        p->state = S_LEN1;
        return false;
    case S_LEN1:
        p->len = b;
        ck_add(p, b);
        p->state = S_LEN2;
        return false;
    case S_LEN2:
        p->len |= (uint16_t)b << 8;
        ck_add(p, b);
        p->pos = 0;
        if (p->len > UBX_MAX_PAYLOAD) {
            p->state = S_SYNC1;  // not a message we care about, or garbage
        } else {
            p->state = p->len ? S_PAYLOAD : S_CK_A;
        }
        return false;
    case S_PAYLOAD:
        p->payload[p->pos++] = b;
        ck_add(p, b);
        if (p->pos == p->len) {
            p->state = S_CK_A;
        }
        return false;
    case S_CK_A:
        p->state = (b == p->ck_a) ? S_CK_B : S_SYNC1;
        return false;
    case S_CK_B:
        p->state = S_SYNC1;
        return b == p->ck_b;
    default:
        p->state = S_SYNC1;
        return false;
    }
}

static uint32_t u4(const uint8_t *d)
{
    return (uint32_t)d[0] | (uint32_t)d[1] << 8 | (uint32_t)d[2] << 16 | (uint32_t)d[3] << 24;
}

bool ubx_decode_nav_pvt(const uint8_t *d, uint16_t len, ubx_nav_pvt_t *out)
{
    if (len != UBX_NAV_PVT_LEN) {
        return false;
    }
    out->fix_type = d[20];
    out->fix_ok = (d[21] & 0x01) != 0;
    out->num_sv = d[23];
    out->lon_e7 = (int32_t)u4(d + 24);
    out->lat_e7 = (int32_t)u4(d + 28);
    out->h_acc_mm = u4(d + 40);
    out->ground_speed_mm_s = (int32_t)u4(d + 60);
    return true;
}
